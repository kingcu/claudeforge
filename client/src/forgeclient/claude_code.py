"""Parse Claude Code's stats-cache.json and session files."""
import json
import socket
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
from collections import defaultdict

from .config import load_config

STATS_CACHE_PATH = Path.home() / ".claude" / "stats-cache.json"
CLAUDE_PROJECTS_PATH = Path.home() / ".claude" / "projects"
PROTOCOL_VERSION = 1


def load_stats_cache() -> Optional[dict]:
    """Load and parse ~/.claude/stats-cache.json."""
    if not STATS_CACHE_PATH.exists():
        return None
    try:
        return json.loads(STATS_CACHE_PATH.read_text())
    except (json.JSONDecodeError, IOError):
        return None


def get_hostname() -> str:
    """Get hostname from config or system."""
    config = load_config()
    if config.get("hostname"):
        return config["hostname"]
    return socket.gethostname()


def build_sync_payload(days: int = 365) -> dict:
    """
    Build sync payload from session files and stats-cache.json.

    Args:
        days: Number of days of history to include (default: all within limit)

    Returns:
        Dict matching SyncRequest schema
    """
    stats = load_stats_cache()
    cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

    # Parse daily activity from stats-cache (per-day, NOT per-model)
    daily_activity = []
    if stats:
        for entry in stats.get("dailyActivity", []):
            if entry["date"] >= cutoff:
                daily_activity.append({
                    "date": entry["date"],
                    "message_count": entry.get("messageCount", 0),
                    "session_count": entry.get("sessionCount", 0),
                    "tool_call_count": entry.get("toolCallCount", 0)
                })

    # Parse daily usage from session files (full breakdown)
    daily_usage = _get_daily_usage_from_sessions(days)

    # Parse cumulative model usage from stats-cache
    model_usage = []
    if stats:
        for model, usage in stats.get("modelUsage", {}).items():
            model_usage.append({
                "model": model,
                "input_tokens": usage.get("inputTokens", 0),
                "output_tokens": usage.get("outputTokens", 0),
                "cache_read_tokens": usage.get("cacheReadInputTokens", 0),
                "cache_creation_tokens": usage.get("cacheCreationInputTokens", 0)
            })

    return {
        "protocol_version": PROTOCOL_VERSION,
        "hostname": get_hostname(),
        "daily_activity": daily_activity,
        "daily_usage": daily_usage,
        "model_usage": model_usage
    }


def _get_daily_usage_from_sessions(days: int = 365) -> list[dict]:
    """Parse session files for daily usage with full token breakdown."""
    if not CLAUDE_PROJECTS_PATH.exists():
        return []

    cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

    # Aggregate by date
    daily_data = defaultdict(lambda: {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_creation_tokens": 0,
    })

    for jsonl_file in CLAUDE_PROJECTS_PATH.glob("*/*.jsonl"):
        try:
            with open(jsonl_file, 'r') as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        if entry.get("type") != "assistant":
                            continue

                        message = entry.get("message", {})
                        usage = message.get("usage", {})
                        if not usage:
                            continue

                        timestamp = entry.get("timestamp")
                        if not timestamp:
                            continue

                        date = timestamp[:10]
                        if date < cutoff:
                            continue

                        daily_data[date]["input_tokens"] += usage.get("input_tokens", 0)
                        daily_data[date]["output_tokens"] += usage.get("output_tokens", 0)
                        daily_data[date]["cache_read_tokens"] += usage.get("cache_read_input_tokens", 0)
                        daily_data[date]["cache_creation_tokens"] += usage.get("cache_creation_input_tokens", 0)

                    except json.JSONDecodeError:
                        continue
        except (IOError, OSError):
            continue

    return [
        {
            "date": date,
            "input_tokens": daily_data[date]["input_tokens"],
            "output_tokens": daily_data[date]["output_tokens"],
            "cache_read_tokens": daily_data[date]["cache_read_tokens"],
            "cache_creation_tokens": daily_data[date]["cache_creation_tokens"],
        }
        for date in sorted(daily_data.keys())
    ]


def get_local_model_usage() -> list[dict]:
    """Get cumulative model usage from local cache."""
    stats = load_stats_cache()
    if not stats:
        return []

    result = []
    for model, usage in stats.get("modelUsage", {}).items():
        result.append({
            "model": model,
            "input_tokens": usage.get("inputTokens", 0),
            "output_tokens": usage.get("outputTokens", 0),
            "cache_read_tokens": usage.get("cacheReadInputTokens", 0),
            "cache_creation_tokens": usage.get("cacheCreationInputTokens", 0),
        })
    return result


def get_local_summary() -> dict:
    """Get summary stats from local cache."""
    stats = load_stats_cache()
    if not stats:
        return {}

    return {
        "total_sessions": stats.get("totalSessions", 0),
        "total_messages": stats.get("totalMessages", 0),
        "first_session_date": stats.get("firstSessionDate"),
    }


def get_local_daily_stats(days: int = 30) -> list[dict]:
    """Get daily stats from local cache only (for --local mode).

    This uses stats-cache.json which only has output tokens, not cache breakdown.
    For full breakdown, use get_daily_stats_from_sessions().
    """
    stats = load_stats_cache()
    if not stats:
        return []

    cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

    # Build date -> data map
    activity_map = {
        e["date"]: e for e in stats.get("dailyActivity", [])
        if e["date"] >= cutoff
    }

    tokens_map = {}
    for entry in stats.get("dailyModelTokens", []):
        if entry["date"] >= cutoff:
            tokens_map[entry["date"]] = sum(entry.get("tokensByModel", {}).values())

    # Combine
    all_dates = sorted(set(activity_map.keys()) | set(tokens_map.keys()))
    result = []
    for date in all_dates:
        activity = activity_map.get(date, {})
        result.append({
            "date": date,
            "total_tokens": tokens_map.get(date, 0),
            "message_count": activity.get("messageCount", 0),
            "session_count": activity.get("sessionCount", 0),
            "tool_call_count": activity.get("toolCallCount", 0),
            "machines": [get_hostname()]
        })

    return result


def get_daily_stats_from_sessions(days: int = 30) -> list[dict]:
    """Parse session JSONL files to get daily stats with full token breakdown.

    This reads the actual session files which contain per-message usage data
    including input_tokens, output_tokens, cache_read_input_tokens, and
    cache_creation_input_tokens.
    """
    if not CLAUDE_PROJECTS_PATH.exists():
        return []

    cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

    # Aggregate by date
    daily_data = defaultdict(lambda: {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_creation_tokens": 0,
        "message_count": 0,
    })

    # Find all session JSONL files
    for jsonl_file in CLAUDE_PROJECTS_PATH.glob("*/*.jsonl"):
        try:
            with open(jsonl_file, 'r') as f:
                for line in f:
                    try:
                        entry = json.loads(line)

                        # Only process assistant messages with usage data
                        if entry.get("type") != "assistant":
                            continue

                        message = entry.get("message", {})
                        usage = message.get("usage", {})
                        if not usage:
                            continue

                        # Get date from timestamp
                        timestamp = entry.get("timestamp")
                        if not timestamp:
                            continue

                        # Parse ISO timestamp and get date
                        date = timestamp[:10]  # YYYY-MM-DD
                        if date < cutoff:
                            continue

                        # Accumulate tokens
                        daily_data[date]["input_tokens"] += usage.get("input_tokens", 0)
                        daily_data[date]["output_tokens"] += usage.get("output_tokens", 0)
                        daily_data[date]["cache_read_tokens"] += usage.get("cache_read_input_tokens", 0)
                        daily_data[date]["cache_creation_tokens"] += usage.get("cache_creation_input_tokens", 0)
                        daily_data[date]["message_count"] += 1

                    except json.JSONDecodeError:
                        continue
        except (IOError, OSError):
            continue

    # Convert to list sorted by date
    result = []
    for date in sorted(daily_data.keys()):
        data = daily_data[date]
        total = (data["input_tokens"] + data["output_tokens"] +
                 data["cache_read_tokens"] + data["cache_creation_tokens"])
        result.append({
            "date": date,
            "total_tokens": total,
            "input_tokens": data["input_tokens"],
            "output_tokens": data["output_tokens"],
            "cache_read_tokens": data["cache_read_tokens"],
            "cache_creation_tokens": data["cache_creation_tokens"],
            "message_count": data["message_count"],
            "machines": [get_hostname()]
        })

    return result


def get_model_usage_from_sessions() -> list[dict]:
    """Parse session JSONL files to get model usage with full token breakdown.

    This reads the actual session files which contain per-message usage data,
    aggregated by model. More accurate than stats-cache.json which may be stale.
    """
    if not CLAUDE_PROJECTS_PATH.exists():
        return []

    # Aggregate by model
    model_data = defaultdict(lambda: {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_creation_tokens": 0,
        "message_count": 0,
    })

    # Find all session JSONL files
    for jsonl_file in CLAUDE_PROJECTS_PATH.glob("*/*.jsonl"):
        try:
            with open(jsonl_file, 'r') as f:
                for line in f:
                    try:
                        entry = json.loads(line)

                        # Only process assistant messages with usage data
                        if entry.get("type") != "assistant":
                            continue

                        message = entry.get("message", {})
                        usage = message.get("usage", {})
                        if not usage:
                            continue

                        # Get model from message
                        model = message.get("model", "unknown")

                        # Accumulate tokens
                        model_data[model]["input_tokens"] += usage.get("input_tokens", 0)
                        model_data[model]["output_tokens"] += usage.get("output_tokens", 0)
                        model_data[model]["cache_read_tokens"] += usage.get("cache_read_input_tokens", 0)
                        model_data[model]["cache_creation_tokens"] += usage.get("cache_creation_input_tokens", 0)
                        model_data[model]["message_count"] += 1

                    except json.JSONDecodeError:
                        continue
        except (IOError, OSError):
            continue

    # Convert to list
    return [
        {
            "model": model,
            "input_tokens": data["input_tokens"],
            "output_tokens": data["output_tokens"],
            "cache_read_tokens": data["cache_read_tokens"],
            "cache_creation_tokens": data["cache_creation_tokens"],
        }
        for model, data in sorted(model_data.items())
    ]


def get_summary_from_sessions() -> dict:
    """Get summary stats from session files."""
    if not CLAUDE_PROJECTS_PATH.exists():
        return {}

    total_messages = 0
    total_sessions = 0
    first_date = None

    for jsonl_file in CLAUDE_PROJECTS_PATH.glob("*/*.jsonl"):
        total_sessions += 1
        try:
            with open(jsonl_file, 'r') as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        if entry.get("type") == "assistant":
                            total_messages += 1
                            timestamp = entry.get("timestamp")
                            if timestamp:
                                date = timestamp[:10]
                                if first_date is None or date < first_date:
                                    first_date = date
                    except json.JSONDecodeError:
                        continue
        except (IOError, OSError):
            continue

    return {
        "total_sessions": total_sessions,
        "total_messages": total_messages,
        "first_session_date": first_date,
    }
