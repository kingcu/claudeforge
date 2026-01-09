"""Pydantic schemas for request/response models."""
from pydantic import BaseModel, Field, field_validator
from datetime import datetime

PROTOCOL_VERSION = 1
MAX_SYNC_DAYS = 365


# === Request Models ===

class DailyActivityRecord(BaseModel):
    """Per-day activity stats (NOT per-model)."""
    date: str
    message_count: int = Field(ge=0, default=0)
    session_count: int = Field(ge=0, default=0)
    tool_call_count: int = Field(ge=0, default=0)

    @field_validator('date')
    @classmethod
    def validate_date_format(cls, v):
        parsed = datetime.strptime(v, '%Y-%m-%d')
        if (datetime.now() - parsed).days > MAX_SYNC_DAYS:
            raise ValueError(f'Date too old (max {MAX_SYNC_DAYS} days)')
        if parsed.date() > datetime.now().date():
            raise ValueError('Future dates not allowed')
        return v


class DailyUsageRecord(BaseModel):
    """Per-day token usage with full breakdown."""
    date: str
    input_tokens: int = Field(ge=0, default=0)
    output_tokens: int = Field(ge=0, default=0)
    cache_read_tokens: int = Field(ge=0, default=0)
    cache_creation_tokens: int = Field(ge=0, default=0)

    @field_validator('date')
    @classmethod
    def validate_date_format(cls, v):
        parsed = datetime.strptime(v, '%Y-%m-%d')
        if (datetime.now() - parsed).days > MAX_SYNC_DAYS:
            raise ValueError(f'Date too old (max {MAX_SYNC_DAYS} days)')
        if parsed.date() > datetime.now().date():
            raise ValueError('Future dates not allowed')
        return v


class ModelUsageRecord(BaseModel):
    """Cumulative per-model usage."""
    model: str = Field(min_length=1)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cache_read_tokens: int = Field(ge=0, default=0)
    cache_creation_tokens: int = Field(ge=0, default=0)


class SyncRequest(BaseModel):
    protocol_version: int = Field(ge=1, le=PROTOCOL_VERSION)
    hostname: str = Field(min_length=1, max_length=255)
    daily_activity: list[DailyActivityRecord] = Field(default_factory=list, max_length=MAX_SYNC_DAYS)
    daily_usage: list[DailyUsageRecord] = Field(default_factory=list, max_length=MAX_SYNC_DAYS)
    model_usage: list[ModelUsageRecord] = Field(default_factory=list)


# === Response Models ===

class SyncResponse(BaseModel):
    status: str  # "success"
    protocol_version: int
    records_upserted: int
    machine_registered: bool
    server_time: str


class ErrorResponse(BaseModel):
    detail: str


class DailyStatsRecord(BaseModel):
    """Response record for daily stats."""
    date: str
    total_tokens: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int
    message_count: int
    session_count: int
    tool_call_count: int
    machines: list[str]  # which machines contributed


class DailyStatsResponse(BaseModel):
    days: list[DailyStatsRecord]


class MachineRecord(BaseModel):
    hostname: str
    first_seen: str
    last_sync: str
    is_active: bool


class MachinesResponse(BaseModel):
    machines: list[MachineRecord]


class ModelStatsRecord(BaseModel):
    model: str
    total_tokens: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int


class ModelsResponse(BaseModel):
    models: list[ModelStatsRecord]


class TotalsResponse(BaseModel):
    total_tokens: int
    total_messages: int
    total_sessions: int
    machine_count: int
    first_activity: str | None
    last_activity: str | None


class HealthResponse(BaseModel):
    status: str
    database: str
    schema_version: int | None
