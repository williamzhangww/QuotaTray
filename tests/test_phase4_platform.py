from __future__ import annotations

import logging
from pathlib import Path

import pytest

from codex_usage_monitor import __version__
from codex_usage_monitor.app_paths import app_data_dir, database_path, logs_dir, settings_dir
from codex_usage_monitor.logging_config import LOG_FILE_NAME, setup_logging
from codex_usage_monitor.providers.codex_usage_provider import (
    CodexUsageProviderError,
    find_codex_executable,
)
from codex_usage_monitor.settings import (
    AppSettings,
    AppSettingsValues,
)
from codex_usage_monitor.single_instance import instance_lock_path, instance_server_name
from codex_usage_monitor.startup import APP_RUN_VALUE, StartupManager


def test_app_data_paths(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    assert app_data_dir() == tmp_path / "QuotaTray"
    assert database_path() == tmp_path / "QuotaTray" / "usage.db"
    assert logs_dir() == tmp_path / "QuotaTray" / "logs"
    assert settings_dir() == tmp_path / "QuotaTray" / "settings"


def test_settings_defaults(tmp_path) -> None:
    settings = AppSettings(tmp_path / "settings.ini")
    values = settings.load()

    assert values.refresh_interval_minutes == 5
    assert values.start_with_windows is False
    assert values.codex_executable_path == ""


def test_settings_persistence(tmp_path) -> None:
    settings = AppSettings(tmp_path / "settings.ini")
    settings.save(
        AppSettingsValues(
            refresh_interval_minutes=15,
            start_with_windows=True,
            codex_executable_path=r"C:\Codex\codex.exe",
        )
    )

    values = AppSettings(tmp_path / "settings.ini").load()

    assert values.refresh_interval_minutes == 15
    assert values.start_with_windows is True
    assert values.codex_executable_path == r"C:\Codex\codex.exe"


def test_codex_path_discovery_configured_path(tmp_path) -> None:
    codex = tmp_path / "codex.exe"
    codex.write_text("", encoding="utf-8")

    assert find_codex_executable(codex) == codex


def test_codex_path_discovery_invalid(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setenv("ProgramFiles", str(tmp_path / "programs"))
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    monkeypatch.setattr(
        "codex_usage_monitor.providers.codex_usage_provider.shutil.which",
        lambda _name: None,
    )

    with pytest.raises(CodexUsageProviderError, match="Codex executable not found"):
        find_codex_executable(tmp_path / "missing.exe")


def test_startup_registration_enable_disable() -> None:
    registry = FakeRegistry()
    manager = StartupManager(registry)

    manager.enable(r"C:\Apps\QuotaTray.exe")
    assert registry.values[APP_RUN_VALUE] == r'"C:\Apps\QuotaTray.exe"'
    assert manager.is_enabled() is True

    manager.disable()
    assert APP_RUN_VALUE not in registry.values
    assert manager.is_enabled() is False


def test_log_initialization(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    setup_logging()
    logging.getLogger("codex_usage_monitor.test").info("log smoke")

    assert (tmp_path / "QuotaTray" / "logs" / LOG_FILE_NAME).exists()


def test_version_source() -> None:
    assert __version__ == "0.8.1"


def test_single_instance_server_name() -> None:
    assert instance_server_name() == "QuotaTray.SingleInstance"


def test_single_instance_lock_path(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    assert instance_lock_path() == str(tmp_path / "QuotaTray" / "QuotaTray.lock")


class FakeRegistry:
    HKEY_CURRENT_USER = object()
    KEY_SET_VALUE = 1
    KEY_READ = 2
    REG_SZ = 1

    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def OpenKey(self, *_args):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def SetValueEx(self, _key, name, _reserved, _type, value):
        self.values[name] = value

    def DeleteValue(self, _key, name):
        if name not in self.values:
            raise FileNotFoundError(name)
        del self.values[name]

    def QueryValueEx(self, _key, name):
        if name not in self.values:
            raise FileNotFoundError(name)
        return self.values[name], self.REG_SZ
