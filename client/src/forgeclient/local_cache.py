"""Local cache for offline operation and pending syncs."""
import json
from pathlib import Path
from datetime import datetime
from typing import Optional
import httpx

CACHE_DIR = Path.home() / ".claudeforge" / "cache"
PENDING_SYNCS = CACHE_DIR / "pending_syncs.json"
LAST_SERVER_DATA = CACHE_DIR / "last_server_data.json"
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
