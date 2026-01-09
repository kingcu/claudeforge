"""Test fixtures for server tests."""
import pytest
import tempfile
import os
from fastapi.testclient import TestClient


@pytest.fixture
def temp_db():
    """Create temporary database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        os.environ["DATABASE_PATH"] = f.name
        # Initialize the database schema
        from forgeserver.db import init_db
        init_db()
        yield f.name
    os.unlink(f.name)


@pytest.fixture
def api_key():
    """Set test API key."""
    os.environ["FORGE_API_KEY"] = "test-key-12345"
    return "test-key-12345"


@pytest.fixture
def client(temp_db, api_key):
    """Create test client."""
    from forgeserver.main import app
    return TestClient(app)
