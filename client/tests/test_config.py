"""Tests for config module."""


def test_load_default_config(temp_config_dir):
    """Test loading config with no file."""
    from forgeclient.config import load_config
    config = load_config()
    assert config["server_url"] is None
    assert config["api_key"] is None


def test_save_and_load_config(temp_config_dir):
    """Test saving and loading config."""
    from forgeclient.config import save_config, load_config

    save_config({"server_url": "http://localhost:8000", "api_key": "test-key"})
    config = load_config()

    assert config["server_url"] == "http://localhost:8000"
    assert config["api_key"] == "test-key"


def test_set_config_value(temp_config_dir):
    """Test setting individual config values."""
    from forgeclient.config import set_config_value, get_config_value

    set_config_value("server_url", "http://example.com")
    assert get_config_value("server_url") == "http://example.com"
