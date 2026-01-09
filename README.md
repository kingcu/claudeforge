# Claudeforge

Centralized usage tracking for Claude Code across multiple machines.

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

### 2. Install and configure the client

```bash
# Install
pip install -e ./client

# Run interactive setup
forge setup
```

The setup wizard will prompt for:
- **Server URL**: Your forge server address (e.g., `http://192.168.1.100:8420`)
- **API Key**: The `FORGE_API_KEY` from step 1
- **Auto-sync hook**: Optionally install a Claude Code hook for automatic hourly syncing

### 3. View your stats

```bash
# View aggregated usage graph
forge tokens

# View local-only stats (no server needed)
forge tokens --local
```

## Automatic Syncing

The `forge setup` command can install a Claude Code hook that automatically syncs your usage data. When enabled:

- Runs on every Claude prompt
- Only syncs if last sync was more than 1 hour ago
- Queues syncs for retry if server is unreachable
- Runs silently in the background

You can also manually trigger a sync anytime:

```bash
forge sync
```

## Commands

| Command | Description |
|---------|-------------|
| `forge setup` | Interactive setup wizard |
| `forge sync` | Sync local stats to server |
| `forge sync --force` | Force sync even if recently synced |
| `forge sync --status` | Show pending sync count |
| `forge sync --retry` | Retry failed syncs |
| `forge tokens` | Show daily token usage graph |
| `forge tokens --local` | Show local data only |
| `forge tokens -d 7` | Show last 7 days |
| `forge config show` | Show current config |
| `forge config set <key> <value>` | Set config value |

---

## How It Works

Claude Code stores usage stats locally in `~/.claude/stats-cache.json`. Claudeforge syncs this data to a central server so you can view aggregated usage across all your machines.

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

You can edit this directly or use `forge config set`:

```bash
forge config set server-url http://localhost:8420
forge config set api-key YOUR_API_KEY
forge config set hostname my-machine
```

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
