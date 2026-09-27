from __future__ import annotations

import configparser
from dataclasses import dataclass
from pathlib import Path

from codex_usage_monitor.app_paths import ensure_app_dirs, settings_dir

REFRESH_INTERVAL_CHOICES = (1, 5, 10, 15, 30)


@dataclass(frozen=True)
class AppSettingsValues:
    refresh_interval_minutes: int = 5
    start_with_windows: bool = False
    codex_executable_path: str = ""


class AppSettings:
    def __init__(self, settings_path: str | Path | None = None) -> None:
        if settings_path is None:
            ensure_app_dirs()
            path = settings_dir() / "settings.ini"
        else:
            path = Path(settings_path)
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._config = configparser.ConfigParser()
        self._config.read(path, encoding="utf-8")

    def load(self) -> AppSettingsValues:
        return AppSettingsValues(
            refresh_interval_minutes=self._refresh_interval(),
            start_with_windows=self._get_bool("startup", "start_with_windows", False),
            codex_executable_path=self._get_str("codex", "executable_path", ""),
        )

    def save(self, values: AppSettingsValues) -> None:
        self._set("refresh", "interval_minutes", str(values.refresh_interval_minutes))
        self._set("startup", "start_with_windows", str(values.start_with_windows))
        self._set("codex", "executable_path", values.codex_executable_path)
        self._sync()

    def _refresh_interval(self) -> int:
        value = self._get_int("refresh", "interval_minutes", 5)
        return value if value in REFRESH_INTERVAL_CHOICES else 5

    def _set(self, section: str, key: str, value: str) -> None:
        if not self._config.has_section(section):
            self._config.add_section(section)
        self._config.set(section, key, value)

    def _sync(self) -> None:
        with self.path.open("w", encoding="utf-8") as handle:
            self._config.write(handle)

    def _get_str(self, section: str, key: str, default: str) -> str:
        return self._config.get(section, key, fallback=default)

    def _get_int(self, section: str, key: str, default: int) -> int:
        try:
            return self._config.getint(section, key, fallback=default)
        except ValueError:
            return default

    def _get_bool(self, section: str, key: str, default: bool) -> bool:
        try:
            return self._config.getboolean(section, key, fallback=default)
        except ValueError:
            return default
