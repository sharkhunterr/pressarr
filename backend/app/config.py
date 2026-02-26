"""Application configuration with YAML file + environment variable override."""

import os
import secrets
from pathlib import Path

import yaml


class Config:
    """Configuration loaded from YAML with PRESSARR__* env overrides."""

    def __init__(self) -> None:
        self.config_path = Path(
            os.environ.get("PRESSARR__CONFIG_PATH", "/config/pressarr.yml")
        )
        self.db_path = Path(
            os.environ.get("PRESSARR__DB_PATH", "/config/pressarr.db")
        )
        self.port: int = 8585
        self.log_level: str = "info"
        self.api_key: str = ""
        self.auth_enabled: bool = False

        # Scheduler intervals (seconds)
        self.rss_sync_interval: int = 1800  # 30 minutes
        self.download_check_interval: int = 30
        self.history_purge_interval: int = 86400  # 24 hours
        self.forecast_refresh_interval: int = 86400
        self.metadata_refresh_interval: int = 86400
        self.history_retention_days: int = 365

        # Naming template
        self.naming_template: str = (
            "{titre_magazine}/{titre_magazine} - {numero} ({annee}-{mois}).{format}"
        )

        # Metadata sources
        self.google_books_api_key: str = ""
        self.internet_archive_enabled: bool = True

        # Download path for IA direct downloads
        self.download_path: str = "/tmp/pressarr_downloads"

        self._load_yaml()
        self._apply_env_overrides()

    def _load_yaml(self) -> None:
        """Load configuration from YAML file if it exists."""
        if not self.config_path.exists():
            return

        with open(self.config_path) as f:
            data = yaml.safe_load(f) or {}

        self.port = data.get("port", self.port)
        self.log_level = data.get("log_level", self.log_level)
        self.api_key = data.get("api_key", self.api_key)
        self.auth_enabled = data.get("auth_enabled", self.auth_enabled)
        self.db_path = Path(data.get("db_path", str(self.db_path)))
        self.naming_template = data.get("naming_template", self.naming_template)

        metadata = data.get("metadata", {})
        self.google_books_api_key = metadata.get(
            "google_books_api_key", self.google_books_api_key
        )
        self.internet_archive_enabled = metadata.get(
            "internet_archive_enabled", self.internet_archive_enabled
        )

        self.download_path = data.get("download_path", self.download_path)

        scheduler = data.get("scheduler", {})
        self.rss_sync_interval = scheduler.get(
            "rss_sync_interval", self.rss_sync_interval
        )
        self.download_check_interval = scheduler.get(
            "download_check_interval", self.download_check_interval
        )
        self.history_purge_interval = scheduler.get(
            "history_purge_interval", self.history_purge_interval
        )
        self.forecast_refresh_interval = scheduler.get(
            "forecast_refresh_interval", self.forecast_refresh_interval
        )
        self.history_retention_days = scheduler.get(
            "history_retention_days", self.history_retention_days
        )

    def _apply_env_overrides(self) -> None:
        """Override config with PRESSARR__* environment variables."""
        prefix = "PRESSARR__"
        for key, value in os.environ.items():
            if not key.startswith(prefix):
                continue
            config_key = key[len(prefix):].lower()
            if config_key == "port":
                self.port = int(value)
            elif config_key == "log_level":
                self.log_level = value
            elif config_key == "api_key":
                self.api_key = value
            elif config_key == "auth_enabled":
                self.auth_enabled = value.lower() in ("true", "1", "yes")
            elif config_key == "db_path":
                self.db_path = Path(value)
            elif config_key == "config_path":
                pass  # Already handled in __init__
            elif config_key == "naming_template":
                self.naming_template = value

    def generate_api_key(self) -> str:
        """Generate a new API key and persist it to config."""
        self.api_key = secrets.token_hex(16)
        self.save()
        return self.api_key

    def save(self) -> None:
        """Save current configuration to YAML file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "port": self.port,
            "log_level": self.log_level,
            "api_key": self.api_key,
            "auth_enabled": self.auth_enabled,
            "db_path": str(self.db_path),
            "naming_template": self.naming_template,
            "download_path": self.download_path,
            "metadata": {
                "google_books_api_key": self.google_books_api_key,
                "internet_archive_enabled": self.internet_archive_enabled,
            },
            "scheduler": {
                "rss_sync_interval": self.rss_sync_interval,
                "download_check_interval": self.download_check_interval,
                "history_purge_interval": self.history_purge_interval,
                "forecast_refresh_interval": self.forecast_refresh_interval,
                "history_retention_days": self.history_retention_days,
            },
        }
        with open(self.config_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
