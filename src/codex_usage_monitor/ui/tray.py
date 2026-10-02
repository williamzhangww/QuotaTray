from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, QTimer, Signal, Slot
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from codex_usage_monitor import version
from codex_usage_monitor.app_paths import app_data_dir
from codex_usage_monitor.models import AnalyticsSnapshot, UsageSnapshot
from codex_usage_monitor.providers import CodexUsageProvider
from codex_usage_monitor.resources import resource_path
from codex_usage_monitor.settings import AppSettings, AppSettingsValues
from codex_usage_monitor.services import AnalyticsService
from codex_usage_monitor.startup import StartupManager
from codex_usage_monitor.storage import HistoryRepository
from codex_usage_monitor.ui.settings_dialog import SettingsDialog
from codex_usage_monitor.ui.tray_meter_icon import build_tray_meter_view, render_remaining_icon

logger = logging.getLogger(__name__)


class UsageWorker(QObject):
    usageReady = Signal(object)
    usageFailed = Signal(str)

    def __init__(self, app_settings: AppSettings, db_path: str | None = None) -> None:
        super().__init__()
        self.app_settings = app_settings
        self._provider: CodexUsageProvider | None = None
        self._repository = HistoryRepository(db_path=db_path)
        self._analytics = AnalyticsService(self._repository)

    @Slot()
    def refresh(self) -> None:
        try:
            if self._provider is None:
                codex_path = self.app_settings.load().codex_executable_path or None
                self._provider = CodexUsageProvider(codex_exe=codex_path)
            usage = self._provider.get_usage()
            inserted = self._repository.insert_snapshot(usage)
            analytics = self._analytics.build_snapshot(usage)
            logger.info(
                "Refresh success: plan=%s primary=%s secondary=%s inserted=%s",
                usage.plan,
                usage.primary.used_percent if usage.primary else None,
                usage.secondary.used_percent if usage.secondary else None,
                inserted,
            )
            self.usageReady.emit((usage, analytics))
        except Exception as exc:
            logger.warning("Refresh failed: %s", exc)
            self.usageFailed.emit(str(exc))

    @Slot()
    def stop(self) -> None:
        if self._provider is not None:
            self._provider.close()
            self._provider = None


class TrayController(QObject):
    refreshRequested = Signal()
    stopWorkerRequested = Signal()

    def __init__(
        self,
        app: QApplication,
        refresh_interval_minutes: int,
        app_settings: AppSettings,
        before_force_exit: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        self.app = app
        self.app_settings = app_settings
        self.startup_manager = StartupManager()
        self.before_force_exit = before_force_exit
        self.last_usage: UsageSnapshot | None = None
        self.last_analytics: AnalyticsSnapshot | None = None
        self.last_updated: datetime | None = None
        self.refresh_failed = False

        self.tray = QSystemTrayIcon(_app_icon(), self)
        self.tray.setToolTip("QuotaTray — loading...")
        self.menu = QMenu()
        self.refresh_action = QAction("Refresh Now", self.menu)
        self.settings_action = QAction("Settings", self.menu)
        self.open_data_action = QAction("Open Data Folder", self.menu)
        self.about_action = QAction("About", self.menu)
        self.exit_action = QAction("Exit", self.menu)
        self.menu.addAction(self.refresh_action)
        self.menu.addAction(self.settings_action)
        self.menu.addAction(self.open_data_action)
        self.menu.addSeparator()
        self.menu.addAction(self.about_action)
        self.menu.addAction(self.exit_action)
        self.tray.setContextMenu(self.menu)

        self.refresh_action.triggered.connect(self.refresh_now)
        self.settings_action.triggered.connect(self.open_settings)
        self.open_data_action.triggered.connect(self.open_data_folder)
        self.about_action.triggered.connect(self.open_about)
        self.exit_action.triggered.connect(self.exit)

        self.timer = QTimer(self)
        self.timer.setInterval(max(1, refresh_interval_minutes) * 60 * 1000)
        self.timer.timeout.connect(self.refresh_now)

    def start(self) -> None:
        self.tray.show()
        self.timer.start()
        self.refresh_now()

    @Slot()
    def refresh_now(self) -> None:
        self.refresh_action.setEnabled(False)
        if self.last_usage is None:
            self.tray.setToolTip("QuotaTray — loading...")
        self.refreshRequested.emit()

    @Slot(object)
    def on_usage_ready(self, payload: object) -> None:
        usage, analytics = payload
        self.last_usage = usage
        self.last_analytics = analytics
        self.last_updated = datetime.now(timezone.utc)
        self.refresh_failed = False
        self.refresh_action.setEnabled(True)
        self._update_tray_meter(usage)

    @Slot(str)
    def on_usage_failed(self, error: str) -> None:
        self.refresh_action.setEnabled(True)
        self.refresh_failed = True
        if self.last_usage:
            self.last_usage = self.last_usage.mark_stale(error)
            self._update_tray_meter(self.last_usage, refresh_failed=True)
        else:
            self.tray.setIcon(_app_icon())
            self.tray.setToolTip("QuotaTray — unavailable")

    @Slot()
    def exit(self) -> None:
        self.timer.stop()
        logger.info("App exit")
        self.stopWorkerRequested.emit()
        self.tray.hide()
        if self.before_force_exit is not None:
            self.before_force_exit()
        _force_process_exit()

    @Slot()
    def open_settings(self) -> None:
        dialog = SettingsDialog(
            self.app_settings,
            self.startup_manager,
            _current_executable_path(),
            self.menu,
        )
        if dialog.exec():
            values = self.app_settings.load()
            self.timer.setInterval(max(1, values.refresh_interval_minutes) * 60 * 1000)
            self.stopWorkerRequested.emit()
            self.refresh_now()

    @Slot()
    def open_about(self) -> None:
        QMessageBox.about(
            self.menu,
            "About QuotaTray",
            "QuotaTray\n\n"
            f"Version {version.__version__}\n\n"
            "An unofficial Windows tray monitor\n"
            "for OpenAI Codex usage limits.\n\n"
            "Unofficial third-party project.\n"
            "Not affiliated with or endorsed by OpenAI.",
        )

    @Slot()
    def open_data_folder(self) -> None:
        app_data_dir().mkdir(parents=True, exist_ok=True)
        os.startfile(app_data_dir())

    def _update_tray_meter(self, usage: UsageSnapshot, refresh_failed: bool = False) -> None:
        view = build_tray_meter_view(
            usage,
            self.timer.interval() // 60000,
            self.last_updated,
            refresh_failed,
        )
        if view.remaining_percent is None:
            self.tray.setIcon(_app_icon())
        else:
            self.tray.setIcon(render_remaining_icon(view.remaining_percent, alert=view.low_weekly))
        self.tray.setToolTip(view.tooltip)


def _app_icon() -> QIcon:
    icon_path = resource_path("assets", "app.ico")
    return QIcon(str(icon_path)) if icon_path.exists() else QIcon()


def _current_executable_path() -> str:
    if getattr(sys, "frozen", False):
        return sys.executable
    return str(Path(sys.executable))


def _force_process_exit() -> None:
    logging.shutdown()
    os._exit(0)
