"""Test fixtures for client tests."""
import pytest
from pathlib import Path


@pytest.fixture
def temp_config_dir(tmp_path, monkeypatch):
    """Use temporary config directory."""
    import forgeclient.config as config_module
    monkeypatch.setattr(config_module, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config_module, "CONFIG_PATH", tmp_path / "config.json")
    return tmp_path


@pytest.fixture
def temp_cache_dir(tmp_path, monkeypatch):
    """Use temporary cache directory."""
    import forgeclient.local_cache as cache_module
    cache_dir = tmp_path / "cache"
    monkeypatch.setattr(cache_module, "CACHE_DIR", cache_dir)
    monkeypatch.setattr(cache_module, "PENDING_SYNCS", cache_dir / "pending_syncs.json")
    monkeypatch.setattr(cache_module, "LAST_SERVER_DATA", cache_dir / "last_server_data.json")
    return cache_dir
