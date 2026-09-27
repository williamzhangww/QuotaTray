from __future__ import annotations

import os
from pathlib import Path

APP_DIR_NAME = "QuotaTray"


def app_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / APP_DIR_NAME
    return Path.home() / "AppData" / "Local" / APP_DIR_NAME


def logs_dir() -> Path:
    return app_data_dir() / "logs"


def settings_dir() -> Path:
    return app_data_dir() / "settings"


def database_path() -> Path:
    return app_data_dir() / "usage.db"


def ensure_app_dirs() -> None:
    app_data_dir().mkdir(parents=True, exist_ok=True)
    logs_dir().mkdir(parents=True, exist_ok=True)
    settings_dir().mkdir(parents=True, exist_ok=True)
