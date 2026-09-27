from __future__ import annotations

import logging
import os
import sys
import traceback

from codex_usage_monitor.app_paths import ensure_app_dirs
from codex_usage_monitor.config import load_config
from codex_usage_monitor.logging_config import setup_logging
from codex_usage_monitor.settings import AppSettings, AppSettingsValues
from codex_usage_monitor.windows_instance import WindowsInstanceGuard
from codex_usage_monitor.runtime_prerequisite import VC_RUNTIME_REGISTRY_KEY, is_compatible_runtime

logger = logging.getLogger(__name__)


def _has_system_vc_runtime() -> bool:
    if sys.platform != "win32" or sys.maxsize <= 2**32:
        return False
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            VC_RUNTIME_REGISTRY_KEY,
            0,
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
        ) as key:
            state = {
                name: winreg.QueryValueEx(key, name)[0]
                for name in ("Installed", "Version", "Major", "Minor", "Bld")
            }
    except (OSError, ImportError):
        return False
    return is_compatible_runtime(state, "x64")


def _show_runtime_requirement() -> None:
    import ctypes

    ctypes.windll.user32.MessageBoxW(
        None,
        "QuotaTray requires the Microsoft Visual C++ Redistributable (x64).\n\n"
        "Install the Microsoft official x64 package, then run QuotaTray again.\n"
        "https://aka.ms/vc14/vc_redist.x64.exe",
        "QuotaTray prerequisite required",
        0x10,
    )


def main() -> int:
    if sys.platform == "win32" and not _has_system_vc_runtime():
        _show_runtime_requirement()
        return 1
    quit_requested = "--quit" in sys.argv
    windows_guard = WindowsInstanceGuard()
    if not windows_guard.try_acquire():
        windows_guard.notify_existing(quit_requested)
        if quit_requested:
            windows_guard.wait_until_released(10000)
        windows_guard.close()
        os._exit(0)
    if quit_requested:
        windows_guard.close()
        return 0

    ensure_app_dirs()
    setup_logging()
    sys.excepthook = _excepthook
    logger.info("App start")

    from PySide6.QtCore import Qt, QThread, QTimer
    from PySide6.QtWidgets import QApplication, QMessageBox

    from codex_usage_monitor.process_guard import terminate_duplicate_app_processes
    from codex_usage_monitor.single_instance import SingleInstanceGuard
    from codex_usage_monitor.ui.tray import TrayController, UsageWorker

    config = load_config()
    app_settings = AppSettings()
    existing_values = app_settings.load()
    if existing_values.refresh_interval_minutes == 5 and config.refresh_interval_minutes != 5:
        app_settings.save(
            AppSettingsValues(
                refresh_interval_minutes=config.refresh_interval_minutes,
                start_with_windows=existing_values.start_with_windows,
                codex_executable_path=existing_values.codex_executable_path,
            )
        )
    values = app_settings.load()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    guard = SingleInstanceGuard(lambda _message: None)
    if not guard.try_acquire(b"quit" if "--quit" in sys.argv else b"show"):
        windows_guard.close()
        os._exit(0)
    windows_guard.create_events()

    controller = TrayController(
        app=app,
        refresh_interval_minutes=values.refresh_interval_minutes,
        app_settings=app_settings,
        before_force_exit=lambda: _close_guards(guard, windows_guard),
    )
    guard.on_message = lambda message: controller.exit() if message == "quit" else None
    event_timer = QTimer()
    event_timer.setInterval(500)
    event_timer.timeout.connect(lambda: _poll_windows_events(windows_guard, controller))
    process_guard_timer = QTimer()
    process_guard_timer.setInterval(2000)
    process_guard_timer.timeout.connect(
        lambda: _terminate_duplicate_processes(terminate_duplicate_app_processes)
    )

    thread = QThread()
    worker = UsageWorker(app_settings)
    worker.moveToThread(thread)

    controller.refreshRequested.connect(worker.refresh)
    controller.stopWorkerRequested.connect(worker.stop, Qt.BlockingQueuedConnection)
    worker.usageReady.connect(controller.on_usage_ready)
    worker.usageFailed.connect(controller.on_usage_failed)
    app.aboutToQuit.connect(worker.stop, Qt.BlockingQueuedConnection)
    app.aboutToQuit.connect(thread.quit)

    thread.start()
    event_timer.start()
    process_guard_timer.start()
    try:
        controller.start()
        exit_code = app.exec()
        return exit_code
    except Exception:
        logger.exception("Unhandled exception in main loop")
        QMessageBox.critical(None, "QuotaTray", "Unexpected error. See app.log.")
        return 1
    finally:
        guard.close()
        windows_guard.close()
        thread.quit()
        thread.wait(5000)


def _poll_windows_events(windows_guard: WindowsInstanceGuard, controller) -> None:
    if windows_guard.consume_quit():
        controller.exit()
    else:
        windows_guard.consume_show()


def _close_guards(guard, windows_guard: WindowsInstanceGuard) -> None:
    guard.close()
    windows_guard.close()


def _terminate_duplicate_processes(terminator) -> None:
    terminated = terminator()
    if terminated:
        logger.warning("Terminated duplicate app processes: %s", ",".join(map(str, terminated)))


def _excepthook(exc_type, exc, tb) -> None:
    logger.error("Unhandled exception: %s", "".join(traceback.format_exception(exc_type, exc, tb)))
    sys.__excepthook__(exc_type, exc, tb)


if __name__ == "__main__":
    raise SystemExit(main())
