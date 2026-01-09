"""Configuration management for forge client."""
import json
from pathlib import Path
from typing import Optional

CONFIG_DIR = Path.home() / ".claudeforge"
CONFIG_PATH = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "server_url": None,
    "api_key": None,
    "hostname": None,  # None = use socket.gethostname()
    "last_sync": None,
    "last_sync_success": True,
    "last_error": None
}


def load_config() -> dict:
    """Load config from file, with defaults."""
    config = DEFAULT_CONFIG.copy()
    if CONFIG_PATH.exists():
        try:
            stored = json.loads(CONFIG_PATH.read_text())
            config.update(stored)
        except (json.JSONDecodeError, IOError):
            pass
    return config


def save_config(config: dict) -> None:
    """Save config to file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2))


def get_config_value(key: str) -> Optional[str]:
    """Get a single config value."""
    return load_config().get(key)


def set_config_value(key: str, value: str) -> None:
    """Set a single config value."""
    config = load_config()
    config[key] = value
    save_config(config)
