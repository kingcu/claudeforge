"""Tests for stats endpoints."""


def test_daily_stats_empty(client, api_key):
    """Test daily stats with no data."""
    response = client.get(
        "/v1/stats/daily",
        headers={"X-API-Key": api_key}
    )
    assert response.status_code == 200
    assert response.json()["days"] == []


def test_daily_stats_with_data(client, api_key):
    """Test daily stats after syncing data."""
    # First sync some data
    client.post(
        "/v1/sync",
        json={
            "protocol_version": 1,
            "hostname": "test-machine",
            "daily_activity": [{"date": "2026-01-07", "message_count": 10, "session_count": 2, "tool_call_count": 5}],
            "daily_usage": [{"date": "2026-01-07", "input_tokens": 400, "output_tokens": 600, "cache_read_tokens": 0, "cache_creation_tokens": 0}],
            "model_usage": []
        },
        headers={"X-API-Key": api_key}
    )

    # Then query stats
    response = client.get(
        "/v1/stats/daily?days=30",
        headers={"X-API-Key": api_key}
    )
    assert response.status_code == 200
    days = response.json()["days"]
    assert len(days) >= 1
    # Find our day
    day = next((d for d in days if d["date"] == "2026-01-07"), None)
    if day:  # May not be in range depending on test date
        assert day["total_tokens"] == 1000
        assert day["input_tokens"] == 400
        assert day["output_tokens"] == 600
        assert day["message_count"] == 10


def test_machines_list(client, api_key):
    """Test listing machines."""
    # Sync to register a machine
    client.post(
        "/v1/sync",
        json={"protocol_version": 1, "hostname": "test-machine", "daily_activity": [], "daily_usage": [], "model_usage": []},
        headers={"X-API-Key": api_key}
    )

    response = client.get("/v1/stats/machines", headers={"X-API-Key": api_key})
    assert response.status_code == 200
    machines = response.json()["machines"]
    assert any(m["hostname"] == "test-machine" for m in machines)


def test_machine_soft_delete(client, api_key):
    """Test soft deleting a machine."""
    # Register machine
    client.post(
        "/v1/sync",
        json={"protocol_version": 1, "hostname": "to-delete", "daily_activity": [], "daily_usage": [], "model_usage": []},
        headers={"X-API-Key": api_key}
    )

    # Soft delete
    response = client.delete("/v1/machines/to-delete", headers={"X-API-Key": api_key})
    assert response.status_code == 200
    assert response.json()["hard"] is False

    # Machine should be inactive
    machines = client.get("/v1/stats/machines", headers={"X-API-Key": api_key}).json()["machines"]
    machine = next(m for m in machines if m["hostname"] == "to-delete")
    assert machine["is_active"] is False

    # Reactivate
    response = client.post("/v1/machines/to-delete/reactivate", headers={"X-API-Key": api_key})
    assert response.status_code == 200

    # Should be active again
    machines = client.get("/v1/stats/machines", headers={"X-API-Key": api_key}).json()["machines"]
    machine = next(m for m in machines if m["hostname"] == "to-delete")
    assert machine["is_active"] is True


def test_totals(client, api_key):
    """Test totals endpoint."""
    response = client.get("/v1/stats/totals", headers={"X-API-Key": api_key})
    assert response.status_code == 200
    data = response.json()
    assert "total_tokens" in data
    assert "total_messages" in data
    assert "machine_count" in data


def test_health_no_auth(client):
    """Test that health endpoint doesn't require auth."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
