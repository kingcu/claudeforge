"""Local cache for offline operation and pending syncs."""
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
import httpx

CACHE_DIR = Path.home() / ".claudeforge" / "cache"
PENDING_SYNCS = CACHE_DIR / "pending_syncs.json"
LAST_SERVER_DATA = CACHE_DIR / "last_server_data.json"
USAGE_SNAPSHOTS = CACHE_DIR / "usage_snapshots.json"
MAX_PENDING_SYNCS = 100


def _load_json(path: Path) -> Optional[list | dict]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, IOError):
        return None


def _save_json(path: Path, data: list | dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def queue_sync(payload: dict) -> bool:
    """Queue a sync for later retry."""
    pending = _load_json(PENDING_SYNCS) or []

    if len(pending) >= MAX_PENDING_SYNCS:
        pending = pending[1:]  # Remove oldest

    pending.append({
        "payload": payload,
        "queued_at": datetime.now().isoformat()
    })
    _save_json(PENDING_SYNCS, pending)
    return True


def get_pending_count() -> int:
    """Return count of pending syncs."""
    pending = _load_json(PENDING_SYNCS) or []
    return len(pending)


def list_pending() -> list[dict]:
    """Return pending syncs with metadata."""
    return _load_json(PENDING_SYNCS) or []


def clear_pending() -> None:
    """Clear all pending syncs."""
    _save_json(PENDING_SYNCS, [])


def process_pending_syncs(server_url: str, api_key: str, timeout: float = 30.0) -> tuple[int, int]:
    """Try to sync pending items. Returns (success_count, fail_count)."""
    pending = _load_json(PENDING_SYNCS) or []
    if not pending:
        return 0, 0

    success = 0
    remaining = []

    with httpx.Client(timeout=timeout) as client:
        for item in pending:
            try:
                response = client.post(
                    f"{server_url}/v1/sync",
                    json=item["payload"],
                    headers={"X-API-Key": api_key}
                )
                response.raise_for_status()
                success += 1
            except Exception:
                remaining.append(item)

    _save_json(PENDING_SYNCS, remaining)
    return success, len(remaining)


def save_server_data(data: dict) -> None:
    """Cache server response for offline display."""
    _save_json(LAST_SERVER_DATA, {
        "data": data,
        "cached_at": datetime.now().isoformat()
    })


def load_server_data() -> Optional[dict]:
    """Load cached server data."""
    cached = _load_json(LAST_SERVER_DATA)
    return cached.get("data") if cached else None


def save_usage_snapshot(model_usage: list[dict]) -> None:
    """
    Save a daily snapshot of cumulative model usage.
    Only saves one snapshot per day (overwrites if same day).
    """
    if not model_usage:
        return

    today = datetime.now().strftime('%Y-%m-%d')
    snapshots = _load_json(USAGE_SNAPSHOTS) or {}

    # Store snapshot keyed by date
    snapshots[today] = {
        "model_usage": model_usage,
        "captured_at": datetime.now().isoformat()
    }

    _save_json(USAGE_SNAPSHOTS, snapshots)


def get_usage_snapshots() -> dict:
    """Load all usage snapshots."""
    return _load_json(USAGE_SNAPSHOTS) or {}


def compute_daily_deltas(days: int = 30) -> list[dict]:
    """
    Compute daily token deltas from snapshots.
    Returns list of daily records with full breakdown.
    """
    snapshots = get_usage_snapshots()
    if not snapshots:
        return []

    # Sort dates
    sorted_dates = sorted(snapshots.keys())
    if len(sorted_dates) < 2:
        return []  # Need at least 2 snapshots to compute deltas

    # Filter to requested day range
    cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    sorted_dates = [d for d in sorted_dates if d >= cutoff]

    results = []
    for i in range(1, len(sorted_dates)):
        prev_date = sorted_dates[i - 1]
        curr_date = sorted_dates[i]

        prev_usage = {u["model"]: u for u in snapshots[prev_date]["model_usage"]}
        curr_usage = {u["model"]: u for u in snapshots[curr_date]["model_usage"]}

        # Sum deltas across all models for this day
        day_input = 0
        day_output = 0
        day_cache_read = 0
        day_cache_create = 0

        all_models = set(prev_usage.keys()) | set(curr_usage.keys())
        for model in all_models:
            prev = prev_usage.get(model, {})
            curr = curr_usage.get(model, {})

            day_input += max(0, curr.get("input_tokens", 0) - prev.get("input_tokens", 0))
            day_output += max(0, curr.get("output_tokens", 0) - prev.get("output_tokens", 0))
            day_cache_read += max(0, curr.get("cache_read_tokens", 0) - prev.get("cache_read_tokens", 0))
            day_cache_create += max(0, curr.get("cache_creation_tokens", 0) - prev.get("cache_creation_tokens", 0))

        total = day_input + day_output + day_cache_read + day_cache_create

        results.append({
            "date": curr_date,
            "total_tokens": total,
            "input_tokens": day_input,
            "output_tokens": day_output,
            "cache_read_tokens": day_cache_read,
            "cache_creation_tokens": day_cache_create,
        })

    return results
