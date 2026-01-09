"""Tests for sync endpoint."""


def test_sync_creates_machine(client, api_key):
    """Test that sync creates machine on first call."""
    import uuid
    unique_hostname = f"test-machine-{uuid.uuid4().hex[:8]}"
    response = client.post(
        "/v1/sync",
        json={
            "protocol_version": 1,
            "hostname": unique_hostname,
            "daily_activity": [],
            "daily_tokens": [],
            "model_usage": []
        },
        headers={"X-API-Key": api_key}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["machine_registered"] is True


def test_sync_idempotent(client, api_key):
    """Test that repeated syncs don't create duplicates."""
    payload = {
        "protocol_version": 1,
        "hostname": "test-machine",
        "daily_activity": [{"date": "2026-01-07", "message_count": 10, "session_count": 1, "tool_call_count": 5}],
        "daily_tokens": [{"date": "2026-01-07", "model": "claude-opus", "tokens": 1000}],
        "model_usage": []
    }

    # First sync
    r1 = client.post("/v1/sync", json=payload, headers={"X-API-Key": api_key})
    assert r1.status_code == 200

    # Second sync (same data)
    r2 = client.post("/v1/sync", json=payload, headers={"X-API-Key": api_key})
    assert r2.status_code == 200
    assert r2.json()["machine_registered"] is False


def test_sync_requires_auth(client):
    """Test that sync requires API key."""
    response = client.post("/v1/sync", json={"protocol_version": 1, "hostname": "x"})
    assert response.status_code in [401, 403, 422]


def test_sync_rejects_wrong_key(client):
    """Test that wrong API key is rejected."""
    response = client.post(
        "/v1/sync",
        json={
            "protocol_version": 1,
            "hostname": "test-machine",
            "daily_activity": [],
            "daily_tokens": [],
            "model_usage": []
        },
        headers={"X-API-Key": "wrong-key"}
    )
    assert response.status_code == 401
