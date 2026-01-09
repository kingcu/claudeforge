"""Tests for Claude Code stats parser."""
from pathlib import Path


def test_build_sync_payload_empty(temp_config_dir, monkeypatch):
    """Test payload with no stats file."""
    import forgeclient.claude_code as cc_module
    monkeypatch.setattr(cc_module, "STATS_CACHE_PATH", Path("/nonexistent"))
    from forgeclient.claude_code import build_sync_payload
    payload = build_sync_payload()
    assert payload["protocol_version"] == 1
    assert payload["daily_activity"] == []
    assert payload["daily_tokens"] == []
    assert payload["model_usage"] == []


def test_build_sync_payload_with_data(temp_config_dir, tmp_path, monkeypatch):
    """Test payload with valid stats file."""
    import forgeclient.claude_code as cc_module

    # Create mock stats file
    stats_file = tmp_path / "stats-cache.json"
    stats_file.write_text('''{
        "dailyActivity": [
            {"date": "2026-01-07", "messageCount": 10, "sessionCount": 2, "toolCallCount": 5}
        ],
        "dailyModelTokens": [
            {"date": "2026-01-07", "tokensByModel": {"claude-opus": 1000}}
        ],
        "modelUsage": {
            "claude-opus": {"inputTokens": 500, "outputTokens": 500, "cacheReadInputTokens": 0, "cacheCreationInputTokens": 0}
        }
    }''')

    monkeypatch.setattr(cc_module, "STATS_CACHE_PATH", stats_file)
    from forgeclient.claude_code import build_sync_payload

    payload = build_sync_payload()
    assert len(payload["daily_activity"]) == 1
    assert payload["daily_activity"][0]["message_count"] == 10
    assert len(payload["daily_tokens"]) == 1
    assert payload["daily_tokens"][0]["tokens"] == 1000
    assert len(payload["model_usage"]) == 1


def test_get_local_daily_stats_empty(temp_config_dir, monkeypatch):
    """Test local stats with no file."""
    import forgeclient.claude_code as cc_module
    monkeypatch.setattr(cc_module, "STATS_CACHE_PATH", Path("/nonexistent"))
    from forgeclient.claude_code import get_local_daily_stats

    stats = get_local_daily_stats()
    assert stats == []
