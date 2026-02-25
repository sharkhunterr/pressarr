"""Configuration loader for Pressarr. Reads YAML + env overrides."""

from __future__ import annotations

import logging
import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_ENV_PREFIX = "PRESSARR__"


@dataclass
class SystemConfig:
    """Runtime configuration loaded from YAML + environment variables."""

    server_port: int = 8585
    server_host: str = "0.0.0.0"
    api_key: str = ""
    config_dir: str = "/config"
    magazines_dir: str = "/magazines"
    downloads_dir: str = "/downloads"
    log_level: str = "info"
    db_path: str = ""

    def __post_init__(self) -> None:
        if not self.db_path:
            self.db_path = str(Path(self.config_dir) / "pressarr.db")
        if not self.api_key:
            self.api_key = secrets.token_hex(16)


# Mapping from YAML nested keys to flat SystemConfig fields
_YAML_FIELD_MAP: dict[tuple[str, ...], str] = {
    ("server", "port"): "server_port",
    ("server", "host"): "server_host",
    ("api_key",): "api_key",
    ("paths", "config"): "config_dir",
    ("paths", "magazines"): "magazines_dir",
    ("paths", "downloads"): "downloads_dir",
    ("logging", "level"): "log_level",
}


def _load_yaml(config_path: Path) -> dict[str, Any]:
    """Load YAML config file. Returns empty dict if file doesn't exist."""
    if not config_path.exists():
        return {}
    try:
        with open(config_path) as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    except yaml.YAMLError as e:
        logger.warning("Invalid YAML in %s: %s — using defaults", config_path, e)
        return {}


def _get_nested(data: dict[str, Any], keys: tuple[str, ...]) -> Any:
    """Get a nested value from a dict using a tuple of keys."""
    current: Any = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def _apply_yaml(config: dict[str, Any], yaml_data: dict[str, Any]) -> None:
    """Apply YAML values to config dict, logging warnings for invalid values."""
    for yaml_keys, field_name in _YAML_FIELD_MAP.items():
        value = _get_nested(yaml_data, yaml_keys)
        if value is None:
            continue
        # Validate type matches expected
        default = SystemConfig().__dict__[field_name]
        expected_type = type(default) if default else str
        if field_name == "server_port":
            expected_type = int
        try:
            config[field_name] = expected_type(value)
        except (ValueError, TypeError):
            logger.warning(
                "Invalid value for %s: %r — using default %r",
                ".".join(yaml_keys),
                value,
                default,
            )


def _apply_env(config: dict[str, Any]) -> None:
    """Apply PRESSARR__SECTION__KEY environment variable overrides."""
    for key, value in os.environ.items():
        if not key.startswith(_ENV_PREFIX):
            continue
        # PRESSARR__SERVER__PORT -> ("server", "port")
        parts = key[len(_ENV_PREFIX) :].lower().split("__")
        yaml_keys = tuple(parts)
        field_name = _YAML_FIELD_MAP.get(yaml_keys)
        if field_name is None:
            continue
        # Cast to expected type
        default = SystemConfig().__dict__[field_name]
        expected_type = type(default) if default else str
        if field_name == "server_port":
            expected_type = int
        try:
            config[field_name] = expected_type(value)
        except (ValueError, TypeError):
            logger.warning("Invalid env value for %s=%r — ignoring", key, value)


def load_config(config_dir: str | None = None) -> SystemConfig:
    """Load configuration with priority: env > YAML > defaults.

    If config_dir is provided, it overrides the default /config path.
    Useful for development (e.g., ./config instead of /config).
    """
    # Determine config dir: explicit > env > default
    if config_dir is None:
        config_dir = os.environ.get(f"{_ENV_PREFIX}PATHS__CONFIG", "")

    # Dev fallback: if /config doesn't exist, use ./config
    if not config_dir:
        if Path("/config").exists():
            config_dir = "/config"
        else:
            config_dir = "./config"

    config_path = Path(config_dir) / "pressarr.yml"

    # Start with defaults
    config: dict[str, Any] = {}
    config["config_dir"] = config_dir

    # Layer 1: YAML
    yaml_data = _load_yaml(config_path)
    _apply_yaml(config, yaml_data)

    # Layer 2: Environment variables (override YAML)
    _apply_env(config)

    # Ensure config_dir from env/yaml is respected
    if "config_dir" not in config:
        config["config_dir"] = config_dir

    return SystemConfig(**config)


def write_default_config(config: SystemConfig) -> None:
    """Write the default configuration file with auto-generated API key."""
    config_path = Path(config.config_dir) / "pressarr.yml"
    if config_path.exists():
        return

    data = {
        "server": {
            "port": config.server_port,
            "host": config.server_host,
        },
        "api_key": config.api_key,
        "paths": {
            "config": config.config_dir,
            "magazines": config.magazines_dir,
            "downloads": config.downloads_dir,
        },
        "logging": {
            "level": config.log_level,
        },
    }

    Path(config.config_dir).mkdir(parents=True, exist_ok=True)
    with open(config_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    logger.info("Created default configuration at %s", config_path)
