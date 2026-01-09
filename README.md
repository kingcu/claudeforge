# Claudeforge

Centralized usage tracking for Claude Code across multiple machines.

## Problem

Claude Code stores usage stats locally in `~/.claude/stats-cache.json`. If you use Claude Code on multiple machines, there's no way to see aggregated usage across all of them.

## Solution

A client-server architecture where each machine syncs its local Claude Code stats to a central server.

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Work Laptop │     │ Home Desktop│     │ Other       │
│ forge sync  │────▶│ forge sync  │────▶│ forge sync  │
└─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │
       └───────────────────┴───────────────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │  Forge Server   │
                  │  (FastAPI+SQLite)│
                  └─────────────────┘
```

## Quick Start

### 1. Start the server

```bash
# Generate an API key
export FORGE_API_KEY=$(openssl rand -hex 32)
echo "FORGE_API_KEY=$FORGE_API_KEY" > .env

# Start server
docker compose up -d

# Verify it's running
curl http://localhost:8420/health
```

### 2. Install the client

```bash
pip install -e ./client
```

### 3. Configure the client

```bash
# Set server URL (use your server's address)
forge config set server-url http://localhost:8420

# Set API key (same as FORGE_API_KEY in .env)
forge config set api-key YOUR_API_KEY

# Verify config
forge config show
```

### 4. Sync and view stats

```bash
# Sync local stats to server
forge sync

# View aggregated usage graph
forge tokens

# View local-only stats (no server)
forge tokens --local
```

## Commands

| Command | Description |
|---------|-------------|
| `forge sync` | Sync local stats to server |
| `forge sync --force` | Force sync even if recently synced |
| `forge sync --status` | Show pending sync count |
| `forge sync --retry` | Retry failed syncs |
| `forge tokens` | Show daily token usage graph |
| `forge tokens --local` | Show local data only |
| `forge tokens -d 7` | Show last 7 days |
| `forge config show` | Show current config |
| `forge config set <key> <value>` | Set config value |

## Configuration

Client config is stored in `~/.claudeforge/config.json`:

```json
{
  "server_url": "http://localhost:8420",
  "api_key": "your-api-key",
  "hostname": null
}
```

- `server_url`: URL of your forge server
- `api_key`: API key for authentication
- `hostname`: Override machine hostname (default: auto-detected)

## Server API

All endpoints except `/health` require `X-API-Key` header.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check (no auth) |
| POST | `/v1/sync` | Submit usage data |
| GET | `/v1/stats/daily?days=30` | Aggregated daily stats |
| GET | `/v1/stats/totals` | All-time totals |
| GET | `/v1/stats/machines` | List synced machines |
| GET | `/v1/stats/models` | Usage by model |
| DELETE | `/v1/machines/{hostname}` | Remove a machine |

## Architecture

**Server** (`./server/`):
- FastAPI application
- SQLite database
- API key authentication with rate limiting
- Docker deployment

**Client** (`./client/`):
- Click CLI (`forge` command)
- Reads `~/.claude/stats-cache.json`
- Offline queue for resilience
- Rich terminal graphs

## Network Setup

The server needs to be reachable from all your machines. Options:

- **Tailscale** (recommended): Zero-config mesh VPN
- **LAN**: If all machines are on the same network
- **VPS**: Run on a public server with API key auth

## Development

```bash
# Run server tests
cd server && pip install -e ".[dev]" && pytest

# Run client tests
cd client && pip install -e ".[dev]" && pytest
```

## Data Model

The client reads Claude Code's `stats-cache.json` which contains:

- `dailyActivity`: Per-day message/session/tool counts (NOT per-model)
- `dailyModelTokens`: Per-day per-model token counts
- `modelUsage`: Cumulative per-model input/output/cache tokens

All data is synced idempotently - repeated syncs with the same data produce the same result.
