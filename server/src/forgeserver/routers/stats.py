"""Stats endpoints for querying aggregated usage data."""
from fastapi import APIRouter, Query

from ..db import get_daily_stats, get_machines, get_model_stats, get_totals, get_machine_stats
from ..models import (
    DailyStatsResponse,
    MachinesResponse,
    MachineRecord,
    ModelsResponse,
    ModelStatsRecord,
    TotalsResponse,
)

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/daily", response_model=DailyStatsResponse)
async def daily_stats(days: int = Query(default=30, ge=1, le=365)):
    """Get aggregated daily usage across all active machines."""
    data = get_daily_stats(days)
    return DailyStatsResponse(days=data)


@router.get("/machines", response_model=MachinesResponse)
async def list_machines():
    """List all registered machines."""
    data = get_machines()
    return MachinesResponse(
        machines=[
            MachineRecord(
                hostname=m['hostname'],
                first_seen=m['first_seen'],
                last_sync=m['last_sync'],
                is_active=bool(m['is_active'])
            )
            for m in data
        ]
    )


@router.get("/models", response_model=ModelsResponse)
async def model_stats(days: int = Query(default=30, ge=1, le=365)):
    """Get usage breakdown by model."""
    data = get_model_stats(days)
    return ModelsResponse(
        models=[
            ModelStatsRecord(
                model=m['model'],
                total_tokens=m['total_tokens'],
                input_tokens=m['input_tokens'],
                output_tokens=m['output_tokens'],
                cache_read_tokens=m['cache_read_tokens']
            )
            for m in data
        ]
    )


@router.get("/totals", response_model=TotalsResponse)
async def totals():
    """Get all-time usage totals."""
    data = get_totals()
    return TotalsResponse(**data)


@router.get("/machine/{hostname}", response_model=DailyStatsResponse)
async def machine_stats(hostname: str, days: int = Query(default=30, ge=1, le=365)):
    """Get daily stats for a single machine."""
    data = get_machine_stats(hostname, days)
    return DailyStatsResponse(days=data)
