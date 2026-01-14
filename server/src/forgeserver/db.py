"""SQLite database setup and queries."""
import os
import logging
import sqlite3
from contextlib import contextmanager

from .models import SyncRequest, DailyStatsRecord

logger = logging.getLogger(__name__)

DATABASE_PATH = os.environ.get("DATABASE_PATH", "usage.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS machines (
    id INTEGER PRIMARY KEY,
    hostname TEXT UNIQUE NOT NULL,
    first_seen TEXT NOT NULL DEFAULT (datetime('now')),
    last_sync TEXT NOT NULL DEFAULT (datetime('now')),
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS daily_activity (
    id INTEGER PRIMARY KEY,
    hostname TEXT NOT NULL,
    date TEXT NOT NULL,
    message_count INTEGER NOT NULL DEFAULT 0,
    session_count INTEGER NOT NULL DEFAULT 0,
    tool_call_count INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(hostname, date),
    FOREIGN KEY (hostname) REFERENCES machines(hostname) ON DELETE CASCADE,
    CHECK(message_count >= 0),
    CHECK(session_count >= 0),
    CHECK(tool_call_count >= 0)
);

CREATE TABLE IF NOT EXISTS daily_usage (
    id INTEGER PRIMARY KEY,
    hostname TEXT NOT NULL,
    date TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cache_read_tokens INTEGER NOT NULL DEFAULT 0,
    cache_creation_tokens INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(hostname, date),
    FOREIGN KEY (hostname) REFERENCES machines(hostname) ON DELETE CASCADE,
    CHECK(input_tokens >= 0),
    CHECK(output_tokens >= 0),
    CHECK(cache_read_tokens >= 0),
    CHECK(cache_creation_tokens >= 0)
);

CREATE TABLE IF NOT EXISTS model_usage (
    id INTEGER PRIMARY KEY,
    hostname TEXT NOT NULL,
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cache_read_tokens INTEGER NOT NULL DEFAULT 0,
    cache_creation_tokens INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(hostname, model),
    FOREIGN KEY (hostname) REFERENCES machines(hostname) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS raw_usage (
    id INTEGER PRIMARY KEY,
    hostname TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cache_read_tokens INTEGER NOT NULL DEFAULT 0,
    cache_creation_tokens INTEGER NOT NULL DEFAULT 0,
    UNIQUE(hostname, timestamp, model),
    FOREIGN KEY (hostname) REFERENCES machines(hostname) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_daily_activity_date ON daily_activity(date);
CREATE INDEX IF NOT EXISTS idx_daily_activity_hostname ON daily_activity(hostname);
CREATE INDEX IF NOT EXISTS idx_daily_usage_date ON daily_usage(date);
CREATE INDEX IF NOT EXISTS idx_daily_usage_hostname ON daily_usage(hostname);
CREATE INDEX IF NOT EXISTS idx_model_usage_hostname ON model_usage(hostname);
CREATE INDEX IF NOT EXISTS idx_raw_usage_timestamp ON raw_usage(timestamp);
CREATE INDEX IF NOT EXISTS idx_raw_usage_hostname ON raw_usage(hostname);
"""


def init_db():
    """Initialize database with schema."""
    with get_db() as conn:
        conn.executescript(SCHEMA)
        # Insert initial schema version if not exists
        conn.execute("""
            INSERT OR IGNORE INTO schema_version (version) VALUES (1)
        """)


@contextmanager
def get_db():
    """Get database connection with FK enabled and auto-commit/rollback."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def sync_usage(request: SyncRequest) -> tuple[int, bool]:
    """
    Sync all usage data in a single transaction.
    Returns (records_upserted, machine_was_registered).
    """
    count = 0
    registered = False

    with get_db() as conn:
        # Check if machine exists
        existing = conn.execute(
            "SELECT id FROM machines WHERE hostname = ?",
            (request.hostname,)
        ).fetchone()
        registered = existing is None

        # Upsert machine
        conn.execute("""
            INSERT INTO machines (hostname)
            VALUES (?)
            ON CONFLICT(hostname) DO UPDATE SET
                last_sync = datetime('now'),
                is_active = 1
        """, (request.hostname,))

        # Upsert daily activity
        for record in request.daily_activity:
            conn.execute("""
                INSERT INTO daily_activity
                    (hostname, date, message_count, session_count, tool_call_count, updated_at)
                VALUES (?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(hostname, date) DO UPDATE SET
                    message_count = excluded.message_count,
                    session_count = excluded.session_count,
                    tool_call_count = excluded.tool_call_count,
                    updated_at = datetime('now')
            """, (request.hostname, record.date, record.message_count,
                  record.session_count, record.tool_call_count))
            count += 1

        # Upsert daily usage (full token breakdown)
        for record in request.daily_usage:
            conn.execute("""
                INSERT INTO daily_usage
                    (hostname, date, input_tokens, output_tokens,
                     cache_read_tokens, cache_creation_tokens, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(hostname, date) DO UPDATE SET
                    input_tokens = excluded.input_tokens,
                    output_tokens = excluded.output_tokens,
                    cache_read_tokens = excluded.cache_read_tokens,
                    cache_creation_tokens = excluded.cache_creation_tokens,
                    updated_at = datetime('now')
            """, (request.hostname, record.date, record.input_tokens,
                  record.output_tokens, record.cache_read_tokens,
                  record.cache_creation_tokens))
            count += 1

        # Upsert model usage
        for record in request.model_usage:
            conn.execute("""
                INSERT INTO model_usage
                    (hostname, model, input_tokens, output_tokens,
                     cache_read_tokens, cache_creation_tokens, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(hostname, model) DO UPDATE SET
                    input_tokens = excluded.input_tokens,
                    output_tokens = excluded.output_tokens,
                    cache_read_tokens = excluded.cache_read_tokens,
                    cache_creation_tokens = excluded.cache_creation_tokens,
                    updated_at = datetime('now')
            """, (request.hostname, record.model, record.input_tokens,
                  record.output_tokens, record.cache_read_tokens,
                  record.cache_creation_tokens))
            count += 1

        for record in request.raw_usage:
            conn.execute("""
                INSERT INTO raw_usage
                    (hostname, timestamp, model, input_tokens, output_tokens,
                     cache_read_tokens, cache_creation_tokens)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(hostname, timestamp, model) DO UPDATE SET
                    input_tokens = excluded.input_tokens,
                    output_tokens = excluded.output_tokens,
                    cache_read_tokens = excluded.cache_read_tokens,
                    cache_creation_tokens = excluded.cache_creation_tokens
            """, (request.hostname, record.timestamp, record.model,
                  record.input_tokens, record.output_tokens,
                  record.cache_read_tokens, record.cache_creation_tokens))
            count += 1

        logger.info(f"Synced {count} records for {request.hostname}")

    return count, registered


def get_daily_stats(days: int = 30) -> list[DailyStatsRecord]:
    """Get aggregated daily stats for active machines."""
    with get_db() as conn:
        # Query usage aggregated by date (full breakdown)
        rows = conn.execute("""
            SELECT
                du.date,
                SUM(du.input_tokens) as input_tokens,
                SUM(du.output_tokens) as output_tokens,
                SUM(du.cache_read_tokens) as cache_read_tokens,
                SUM(du.cache_creation_tokens) as cache_creation_tokens,
                GROUP_CONCAT(DISTINCT du.hostname) as machines
            FROM daily_usage du
            JOIN machines m ON du.hostname = m.hostname AND m.is_active = 1
            WHERE du.date >= date('now', ?)
            GROUP BY du.date
            ORDER BY du.date ASC
        """, (f'-{days} days',)).fetchall()

        # Query activity aggregated by date
        activity_rows = conn.execute("""
            SELECT
                da.date,
                SUM(da.message_count) as message_count,
                SUM(da.session_count) as session_count,
                SUM(da.tool_call_count) as tool_call_count
            FROM daily_activity da
            JOIN machines m ON da.hostname = m.hostname AND m.is_active = 1
            WHERE da.date >= date('now', ?)
            GROUP BY da.date
        """, (f'-{days} days',)).fetchall()

        # Build activity lookup (convert sqlite3.Row to dict for .get() support)
        activity_map = {r['date']: dict(r) for r in activity_rows}

        return [
            DailyStatsRecord(
                date=row['date'],
                total_tokens=(row['input_tokens'] + row['output_tokens'] +
                              row['cache_read_tokens'] + row['cache_creation_tokens']),
                input_tokens=row['input_tokens'],
                output_tokens=row['output_tokens'],
                cache_read_tokens=row['cache_read_tokens'],
                cache_creation_tokens=row['cache_creation_tokens'],
                message_count=activity_map.get(row['date'], {}).get('message_count', 0) or 0,
                session_count=activity_map.get(row['date'], {}).get('session_count', 0) or 0,
                tool_call_count=activity_map.get(row['date'], {}).get('tool_call_count', 0) or 0,
                machines=row['machines'].split(',') if row['machines'] else []
            )
            for row in rows
        ]


def get_machines() -> list[dict]:
    """Get all machines with their status."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT hostname, first_seen, last_sync, is_active
            FROM machines
            ORDER BY last_sync DESC
        """).fetchall()
        return [dict(r) for r in rows]


def get_model_stats(days: int = 30) -> list[dict]:
    """Get usage aggregated by model."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT
                mu.model,
                SUM(mu.input_tokens) as input_tokens,
                SUM(mu.output_tokens) as output_tokens,
                SUM(mu.cache_read_tokens) as cache_read_tokens,
                SUM(mu.cache_creation_tokens) as cache_creation_tokens
            FROM model_usage mu
            JOIN machines m ON mu.hostname = m.hostname AND m.is_active = 1
            GROUP BY mu.model
            ORDER BY (SUM(mu.input_tokens) + SUM(mu.output_tokens)) DESC
        """).fetchall()
        return [
            {
                "model": r['model'],
                "input_tokens": r['input_tokens'],
                "output_tokens": r['output_tokens'],
                "cache_read_tokens": r['cache_read_tokens'],
                "cache_creation_tokens": r['cache_creation_tokens'],
                "total_tokens": r['input_tokens'] + r['output_tokens'] + r['cache_read_tokens'] + r['cache_creation_tokens']
            }
            for r in rows
        ]


def get_totals() -> dict:
    """Get all-time totals."""
    with get_db() as conn:
        tokens = conn.execute("""
            SELECT
                COALESCE(SUM(input_tokens + output_tokens + cache_read_tokens + cache_creation_tokens), 0) as total
            FROM daily_usage du
            JOIN machines m ON du.hostname = m.hostname AND m.is_active = 1
        """).fetchone()['total']

        activity = conn.execute("""
            SELECT
                COALESCE(SUM(message_count), 0) as messages,
                COALESCE(SUM(session_count), 0) as sessions
            FROM daily_activity da
            JOIN machines m ON da.hostname = m.hostname AND m.is_active = 1
        """).fetchone()

        machine_count = conn.execute("""
            SELECT COUNT(*) as cnt FROM machines WHERE is_active = 1
        """).fetchone()['cnt']

        dates = conn.execute("""
            SELECT MIN(date) as first, MAX(date) as last
            FROM daily_usage du
            JOIN machines m ON du.hostname = m.hostname AND m.is_active = 1
        """).fetchone()

        return {
            "total_tokens": tokens,
            "total_messages": activity['messages'],
            "total_sessions": activity['sessions'],
            "machine_count": machine_count,
            "first_activity": dates['first'],
            "last_activity": dates['last']
        }


def delete_machine(hostname: str, hard: bool = False) -> bool:
    """Delete or deactivate a machine. Returns True if found."""
    with get_db() as conn:
        if hard:
            result = conn.execute(
                "DELETE FROM machines WHERE hostname = ?", (hostname,)
            )
        else:
            result = conn.execute(
                "UPDATE machines SET is_active = 0 WHERE hostname = ?", (hostname,)
            )
        return result.rowcount > 0


def reactivate_machine(hostname: str) -> bool:
    """Reactivate a soft-deleted machine. Returns True if found."""
    with get_db() as conn:
        result = conn.execute(
            "UPDATE machines SET is_active = 1 WHERE hostname = ?", (hostname,)
        )
        return result.rowcount > 0


def get_machine_stats(hostname: str, days: int = 30) -> list[DailyStatsRecord]:
    """Get daily stats for a single machine."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT
                du.date,
                du.input_tokens,
                du.output_tokens,
                du.cache_read_tokens,
                du.cache_creation_tokens
            FROM daily_usage du
            WHERE du.hostname = ? AND du.date >= date('now', ?)
            ORDER BY du.date ASC
        """, (hostname, f'-{days} days')).fetchall()

        activity_rows = conn.execute("""
            SELECT date, message_count, session_count, tool_call_count
            FROM daily_activity
            WHERE hostname = ? AND date >= date('now', ?)
        """, (hostname, f'-{days} days')).fetchall()

        activity_map = {r['date']: dict(r) for r in activity_rows}

        return [
            DailyStatsRecord(
                date=row['date'],
                total_tokens=(row['input_tokens'] + row['output_tokens'] +
                              row['cache_read_tokens'] + row['cache_creation_tokens']),
                input_tokens=row['input_tokens'],
                output_tokens=row['output_tokens'],
                cache_read_tokens=row['cache_read_tokens'],
                cache_creation_tokens=row['cache_creation_tokens'],
                message_count=activity_map.get(row['date'], {}).get('message_count', 0) or 0,
                session_count=activity_map.get(row['date'], {}).get('session_count', 0) or 0,
                tool_call_count=activity_map.get(row['date'], {}).get('tool_call_count', 0) or 0,
                machines=[hostname]
            )
            for row in rows
        ]
