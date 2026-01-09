"""API key authentication and rate limiting."""
import os
import time
import secrets
from fastapi import HTTPException, Security, Request
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key")

# Simple rate limiting: track request counts per minute
request_counts: dict[str, list[float]] = {}
RATE_LIMIT = 60  # requests per minute


async def verify_api_key(request: Request, api_key: str = Security(api_key_header)):
    """Verify API key and apply rate limiting."""
    expected = os.environ.get("FORGE_API_KEY")
    if not expected:
        raise HTTPException(status_code=500, detail="Server API key not configured")
    if not secrets.compare_digest(api_key, expected):
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Rate limiting
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    if client_ip not in request_counts:
        request_counts[client_ip] = []
    request_counts[client_ip] = [t for t in request_counts[client_ip] if now - t < 60]
    if len(request_counts[client_ip]) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    request_counts[client_ip].append(now)

    return api_key
