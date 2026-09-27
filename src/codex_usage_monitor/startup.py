from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
# Keep the value name stable across the v0.7.3 to QuotaTray upgrade.
APP_RUN_VALUE = "CodexUsageMonitor"


class StartupManager:
    def __init__(self, registry: Any | None = None) -> None:
        if registry is None:
            import winreg as registry  # type: ignore[no-redef]
        self.registry = registry

    def can_register(self) -> bool:
        return bool(getattr(sys, "frozen", False))

    def enable(self, executable_path: str | Path) -> None:
        path = str(executable_path)
        with self.registry.OpenKey(
            self.registry.HKEY_CURRENT_USER,
            RUN_KEY,
            0,
            self.registry.KEY_SET_VALUE,
        ) as key:
            self.registry.SetValueEx(key, APP_RUN_VALUE, 0, self.registry.REG_SZ, f'"{path}"')

    def disable(self) -> None:
        self.cleanup()

    def cleanup(self) -> None:
        with self.registry.OpenKey(
            self.registry.HKEY_CURRENT_USER,
            RUN_KEY,
            0,
            self.registry.KEY_SET_VALUE,
        ) as key:
            try:
                self.registry.DeleteValue(key, APP_RUN_VALUE)
            except FileNotFoundError:
                pass

    def is_enabled(self) -> bool:
        try:
            with self.registry.OpenKey(
                self.registry.HKEY_CURRENT_USER,
                RUN_KEY,
                0,
                self.registry.KEY_READ,
            ) as key:
                self.registry.QueryValueEx(key, APP_RUN_VALUE)
            return True
        except FileNotFoundError:
            return False
