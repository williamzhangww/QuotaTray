from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from codex_usage_monitor.resources import is_frozen, resource_path


@dataclass(frozen=True)
class AppConfig:
    refresh_interval_minutes: int = 5
    always_on_top: bool = True


def load_config(path: Path | None = None) -> AppConfig:
    if path is None and is_frozen():
        return AppConfig()
    config_path = path or resource_path("config.json")
    if not config_path.is_file():
        return AppConfig()
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return AppConfig()
    if not isinstance(raw, dict):
        return AppConfig()
    return AppConfig(
        refresh_interval_minutes=_positive_int(
            raw.get("refresh_interval_minutes"), 5
        ),
        always_on_top=bool(raw.get("always_on_top", True)),
    )


def _positive_int(value: object, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default
