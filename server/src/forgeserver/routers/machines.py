"""Machine management endpoints."""
from fastapi import APIRouter, HTTPException, Query

from ..db import delete_machine, reactivate_machine

router = APIRouter(prefix="/machines", tags=["machines"])


@router.delete("/{hostname}")
async def remove_machine(hostname: str, hard: bool = Query(default=False)):
    """
    Remove a machine.
    - hard=False (default): Soft delete, excludes from stats but keeps data
    - hard=True: Permanently delete machine and all associated data
    """
    if delete_machine(hostname, hard=hard):
        return {"status": "deleted", "hard": hard}
    raise HTTPException(status_code=404, detail="Machine not found")


@router.post("/{hostname}/reactivate")
async def reactivate(hostname: str):
    """Reactivate a soft-deleted machine."""
    if reactivate_machine(hostname):
        return {"status": "reactivated"}
    raise HTTPException(status_code=404, detail="Machine not found")
