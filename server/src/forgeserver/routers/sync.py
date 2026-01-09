"""Sync endpoint for receiving usage data from clients."""
from datetime import datetime
from fastapi import APIRouter

from ..db import sync_usage
from ..models import SyncRequest, SyncResponse, PROTOCOL_VERSION

router = APIRouter(tags=["sync"])


@router.post("/sync", response_model=SyncResponse)
async def sync(request: SyncRequest):
    """
    Receive and store usage data from a client.
    All data is upserted (idempotent).
    """
    count, registered = sync_usage(request)
    return SyncResponse(
        status="success",
        protocol_version=PROTOCOL_VERSION,
        records_upserted=count,
        machine_registered=registered,
        server_time=datetime.now().isoformat()
    )
