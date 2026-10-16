"""Persistent user settings (JSON, stored in the app-data directory)."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

from utils.filesystem import DEFAULT_SCAN_EXCLUDES, app_data_dir
from utils.logging_config import get_logger

logger = get_logger("app_settings")


@dataclass
class AppSettings:
    appearance: str = "light"  # "light" or "dark"
    default_output_dir: str = ""
    default_output_mode: str = "one_file"  # "one_file" | "one_folder"
    default_console_mode: str = "console"  # "console" | "windowed"
    log_verbosity: str = "info"  # "info" | "debug"
    scanner_excludes: list[str] = field(default_factory=lambda: sorted(DEFAULT_SCAN_EXCLUDES))
    custom_interpreter: str = ""  # empty = use PyForge's own interpreter


def _settings_path():
    return app_data_dir() / "settings.json"


def load_settings() -> AppSettings:
    path = _settings_path()
    if not path.exists():
        return AppSettings()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        defaults = asdict(AppSettings())
        defaults.update({k: v for k, v in data.items() if k in defaults})
        return AppSettings(**defaults)
    except (json.JSONDecodeError, OSError, TypeError) as exc:
        logger.warning("Could not load settings (%s); using defaults.", exc)
        return AppSettings()


def save_settings(settings: AppSettings) -> None:
    path = _settings_path()
    try:
        path.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
    except OSError as exc:
        logger.error("Could not save settings: %s", exc)
