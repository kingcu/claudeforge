"""Sync logic for forge client."""
import httpx
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass

from .config import load_config, save_config
from .local_cache import queue_sync, process_pending_syncs, save_server_data
from .claude_code import build_sync_payload

logger = logging.getLogger(__name__)

SYNC_TIMEOUT = 30.0  # seconds


@dataclass
class SyncResult:
    status: str  # "success", "queued", "skipped", "error"
    message: str = ""
    records_synced: int = 0


def parse_datetime(s: str) -> datetime:
    """Parse ISO datetime string."""
    return datetime.fromisoformat(s.replace("Z", "+00:00").replace("+00:00", ""))


def maybe_auto_sync(force: bool = False) -> SyncResult:
    """
    Auto-sync if:
    - force=True, OR
    - last_sync is None, OR
    - last_sync was > 1 hour ago

    Returns SyncResult with status and any error message.
    """
    config = load_config()

    if not config.get("server_url"):
        return SyncResult(status="skipped", message="Server not configured")

    if not config.get("api_key"):
        return SyncResult(status="skipped", message="API key not configured")

    last_sync = config.get("last_sync")

    should_sync = (
        force or
        last_sync is None or
        (datetime.now() - parse_datetime(last_sync)) > timedelta(hours=1)
    )

    if not should_sync:
        return SyncResult(status="skipped", message="Recently synced")

    return do_sync(config)


def do_sync(config: dict) -> SyncResult:
    """Perform the actual sync."""
    server_url = config["server_url"]
    api_key = config["api_key"]

    # First, try to process any pending syncs
    pending_success, pending_fail = process_pending_syncs(server_url, api_key)
    if pending_success > 0:
        logger.info(f"Processed {pending_success} pending syncs")

    try:
        payload = build_sync_payload()
        with httpx.Client(timeout=SYNC_TIMEOUT) as client:
            response = client.post(
                f"{server_url}/v1/sync",
                json=payload,
                headers={"X-API-Key": api_key}
            )
            response.raise_for_status()
            result = response.json()

        save_config({
            **config,
            "last_sync": datetime.now().isoformat(),
            "last_sync_success": True,
            "last_error": None
        })
        return SyncResult(
            status="success",
            records_synced=result.get("records_upserted", 0)
        )
    except httpx.RequestError as e:
        logger.warning(f"Sync failed: {e}")
        queue_sync(build_sync_payload())
        save_config({
            **config,
            "last_sync": datetime.now().isoformat(),
            "last_sync_success": False,
            "last_error": str(e)
        })
        return SyncResult(status="queued", message=f"Server unreachable: {e}")
    except httpx.HTTPStatusError as e:
        logger.error(f"Sync rejected: {e.response.status_code}")
        return SyncResult(status="error", message=f"Server error: {e.response.status_code}")


def test_connection(server_url: str, api_key: str) -> tuple[bool, str]:
    """Test server connection and auth. Returns (success, message)."""
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"{server_url}/v1/stats/machines",
                headers={"X-API-Key": api_key}
            )
            response.raise_for_status()
            return True, "Connected"
    except httpx.ConnectError:
        return False, "Could not connect to server"
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            return False, "Invalid API key"
        return False, f"Server error: {e.response.status_code}"
    except Exception as e:
        return False, str(e)


def fetch_daily_stats(days: int = 30) -> list[dict] | None:
    """Fetch daily stats from server. Returns None on failure."""
    config = load_config()
    if not config.get("server_url") or not config.get("api_key"):
        return None

    try:
        with httpx.Client(timeout=SYNC_TIMEOUT) as client:
            response = client.get(
                f"{config['server_url']}/v1/stats/daily",
                params={"days": days},
                headers={"X-API-Key": config["api_key"]}
            )
            response.raise_for_status()
            data = response.json()
            save_server_data(data)
            return data.get("days", [])
    except Exception as e:
        logger.warning(f"Failed to fetch stats: {e}")
        return None
