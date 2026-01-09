"""FastAPI application."""
import logging
import sys
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db, get_db
from .auth import verify_api_key
from .models import HealthResponse
from .routers import sync, stats, machines

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Forge Server",
    version="0.1.0",
    description="Central server for Claude Code usage tracking"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Initialize database on startup
@app.on_event("startup")
async def startup():
    init_db()
    logger.info("Database initialized")


# Health check (no auth)
@app.get("/health", response_model=HealthResponse)
async def health_check():
    try:
        with get_db() as conn:
            version = conn.execute(
                "SELECT MAX(version) FROM schema_version"
            ).fetchone()[0]
        return HealthResponse(
            status="healthy",
            database="connected",
            schema_version=version
        )
    except Exception as e:
        return HealthResponse(
            status="unhealthy",
            database=str(e),
            schema_version=None
        )


# Include routers with auth dependency
app.include_router(sync.router, prefix="/v1", dependencies=[Depends(verify_api_key)])
app.include_router(stats.router, prefix="/v1", dependencies=[Depends(verify_api_key)])
app.include_router(machines.router, prefix="/v1", dependencies=[Depends(verify_api_key)])
