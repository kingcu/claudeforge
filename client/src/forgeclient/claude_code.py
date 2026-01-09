"""Parse Claude Code's stats-cache.json and build sync payloads."""
import json
import socket
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

from .config import load_config

STATS_CACHE_PATH = Path.home() / ".claude" / "stats-cache.json"
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
    Build sync payload from stats-cache.json.

    Args:
        days: Number of days of history to include (default: all within limit)

    Returns:
        Dict matching SyncRequest schema
    """
    stats = load_stats_cache()
    if not stats:
        return {
            "protocol_version": PROTOCOL_VERSION,
            "hostname": get_hostname(),
            "daily_activity": [],
            "daily_tokens": [],
            "model_usage": []
        }

    cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

    # Parse daily activity (per-day, NOT per-model)
    daily_activity = []
    for entry in stats.get("dailyActivity", []):
        if entry["date"] >= cutoff:
            daily_activity.append({
                "date": entry["date"],
                "message_count": entry.get("messageCount", 0),
                "session_count": entry.get("sessionCount", 0),
                "tool_call_count": entry.get("toolCallCount", 0)
            })

    # Parse daily tokens (per-day per-model)
    daily_tokens = []
    for entry in stats.get("dailyModelTokens", []):
        if entry["date"] >= cutoff:
            for model, tokens in entry.get("tokensByModel", {}).items():
                daily_tokens.append({
                    "date": entry["date"],
                    "model": model,
                    "tokens": tokens
                })

    # Parse cumulative model usage
    model_usage = []
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
        "daily_tokens": daily_tokens,
        "model_usage": model_usage
    }


def get_local_daily_stats(days: int = 30) -> list[dict]:
    """Get daily stats from local cache only (for --local mode)."""
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
