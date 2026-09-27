from __future__ import annotations

import sys
from pathlib import Path

import codex_usage_monitor.release_metadata as release_metadata_module
import codex_usage_monitor.main as main_module
import codex_usage_monitor.resources as resources_module
from codex_usage_monitor.app_paths import app_data_dir, database_path, logs_dir, settings_dir
from codex_usage_monitor.config import load_config
from codex_usage_monitor.providers import codex_usage_provider
from codex_usage_monitor import process_guard
from codex_usage_monitor.release_metadata import release_metadata, version_tuple
from codex_usage_monitor.startup import APP_RUN_VALUE, StartupManager
from codex_usage_monitor.version import __version__
from codex_usage_monitor.windows_instance import MUTEX_NAME, QUIT_EVENT_NAME, SHOW_EVENT_NAME, WAIT_TIMEOUT
from tools.generate_release_metadata import _installer_version_text, _version_info_text


def test_release_version_consistency() -> None:
    metadata = release_metadata()

    assert __version__ == "0.8.0"
    assert metadata.version == __version__
    assert version_tuple() == (0, 8, 0, 0)


def test_frozen_resource_path_helper(monkeypatch, tmp_path) -> None:
    fake_exe = tmp_path / "Programs" / "CodexUsageMonitor" / "QuotaTray.exe"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(fake_exe))

    assert resources_module.app_base_dir() == fake_exe.parent
    assert resources_module.resource_path("_internal", "assets", "app.ico") == fake_exe.parent / "_internal" / "assets" / "app.ico"


def test_install_safe_app_data_paths_do_not_use_install_dir(monkeypatch, tmp_path) -> None:
    install_dir = tmp_path / "Programs" / "CodexUsageMonitor"
    local_app_data = tmp_path / "LocalAppData"
    install_dir.mkdir(parents=True)
    monkeypatch.chdir(install_dir)
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))

    assert app_data_dir() == local_app_data / "CodexUsageMonitor"
    assert database_path() == local_app_data / "CodexUsageMonitor" / "usage.db"
    assert logs_dir() == local_app_data / "CodexUsageMonitor" / "logs"
    assert settings_dir() == local_app_data / "CodexUsageMonitor" / "settings"


def test_frozen_mode_ignores_cwd_legacy_config(monkeypatch, tmp_path) -> None:
    install_dir = tmp_path / "Programs" / "CodexUsageMonitor"
    install_dir.mkdir(parents=True)
    (install_dir / "config.json").write_text('{"refresh_interval_minutes": 30}', encoding="utf-8")
    monkeypatch.chdir(install_dir)
    monkeypatch.setattr("codex_usage_monitor.config.is_frozen", lambda: True)

    assert load_config().refresh_interval_minutes == 5


def test_startup_cleanup_helper_removes_run_value() -> None:
    registry = FakeRegistry()
    manager = StartupManager(registry)

    manager.enable(r"C:\Users\me\AppData\Local\Programs\CodexUsageMonitor\CodexUsageMonitor.exe")
    manager.cleanup()

    assert APP_RUN_VALUE not in registry.values


def test_codex_discovery_source_has_no_developer_absolute_path() -> None:
    source = Path(codex_usage_provider.__file__).read_text(encoding="utf-8")

    assert r"C:\Users" not in source
    assert r"CodexUsageMonitor\dist" not in source
    assert ".sandbox-bin" in source
    assert "WindowsApps" in source


def test_generated_release_metadata_uses_single_version_source() -> None:
    metadata = release_metadata_module.release_metadata()
    version_info = _version_info_text(metadata, release_metadata_module.version_tuple())
    installer_info = _installer_version_text(metadata)

    assert metadata.name == "QuotaTray"
    assert metadata.exe_name == "QuotaTray.exe"
    assert metadata.publisher == "QuotaTray Project"
    assert f"FileVersion', '{__version__}'" in version_info
    assert f"ProductVersion', '{__version__}'" in version_info
    assert f'#define MyAppVersion "{__version__}"' in installer_info
    assert "OpenAI" not in metadata.publisher


def test_tray_menu_no_longer_exposes_details_or_taskbar_dock() -> None:
    source = Path("src/codex_usage_monitor/ui/tray.py").read_text(encoding="utf-8")

    assert "Open Details" not in source
    assert "details_action" not in source
    assert "open_details" not in source
    assert "Taskbar Dock" not in source
    assert "Reset Dock Position" not in source


def test_windows_instance_names_are_stable() -> None:
    assert MUTEX_NAME == "Local\\CodexUsageMonitor.SingleInstance.Mutex"
    assert SHOW_EVENT_NAME == "Local\\CodexUsageMonitor.SingleInstance.Show"
    assert QUIT_EVENT_NAME == "Local\\CodexUsageMonitor.SingleInstance.Quit"
    assert WAIT_TIMEOUT == 258
    assert hasattr(main_module.WindowsInstanceGuard, "wait_until_released")


def test_duplicate_process_scan_excludes_quit_helpers(monkeypatch) -> None:
    captured = {}

    class Result:
        stdout = '"ProcessId","ExecutablePath"\r\n"123","C:\\Apps\\QuotaTray.exe"\r\n'

    def fake_run(command, **kwargs):
        captured["command"] = command
        return Result()

    monkeypatch.setattr(process_guard.subprocess, "run", fake_run)
    assert process_guard._quotatray_processes() == [(123, r"C:\Apps\QuotaTray.exe")]
    command_text = captured["command"][-1]
    assert "--quit" in command_text
    assert "Win32_Process" in command_text



def test_quit_command_without_existing_instance_exits_before_app_start(monkeypatch) -> None:
    calls: list[str] = []

    class FakeWindowsGuard:
        def try_acquire(self) -> bool:
            return True

        def close(self) -> None:
            calls.append("close")

    monkeypatch.setattr(sys, "argv", ["CodexUsageMonitor.exe", "--quit"])
    monkeypatch.setattr(main_module, "WindowsInstanceGuard", FakeWindowsGuard)
    monkeypatch.setattr(main_module, "ensure_app_dirs", lambda: calls.append("ensure_app_dirs"))
    monkeypatch.setattr(main_module, "setup_logging", lambda: calls.append("setup_logging"))

    assert main_module.main() == 0
    assert calls == ["close"]


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
