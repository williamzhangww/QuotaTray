from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from codex_usage_monitor.models import RateLimitResetCredits, UsageSnapshot, UsageWindow
from codex_usage_monitor.settings import AppSettings
from codex_usage_monitor.ui.tray_meter_icon import (
    build_tray_meter_view,
    remaining_percent_from_used,
    render_remaining_icon,
    window_remaining_percent,
)


@pytest.fixture
def qapp():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_remaining_percent_from_used_examples() -> None:
    assert remaining_percent_from_used(0) == 100
    assert remaining_percent_from_used(78) == 22
    assert remaining_percent_from_used(100) == 0


def test_remaining_percent_clamps_invalid_values() -> None:
    assert remaining_percent_from_used(150) == 0
    assert remaining_percent_from_used(-25) == 100
    assert remaining_percent_from_used(None) is None


def test_tray_meter_tooltip_uses_remaining_for_primary_and_weekly() -> None:
    now = datetime(2026, 8, 26, 12, tzinfo=timezone.utc)
    view = build_tray_meter_view(_usage(now, 78, 28), 5, now, now=now)

    assert view.remaining_percent == 22
    assert "5-hour remaining: 22%" in view.tooltip
    assert "Weekly remaining: 72%" in view.tooltip
    assert "used" not in view.tooltip.lower()
    _assert_tooltip_has_no_update_timestamp(view.tooltip)


def test_tray_meter_tooltip_reset_countdowns() -> None:
    now = datetime(2026, 8, 26, 12, tzinfo=timezone.utc)
    view = build_tray_meter_view(_usage(now, 18, 69), 5, now, now=now)

    assert "Resets in 2h 48m" in view.tooltip
    assert "Resets in 6d 16h" in view.tooltip
    assert "2026-" not in view.tooltip
    _assert_tooltip_has_no_update_timestamp(view.tooltip)


def test_tray_meter_tooltip_has_no_update_line_or_trailing_blank_lines() -> None:
    now = datetime(2026, 8, 26, 12, tzinfo=timezone.utc)
    view = build_tray_meter_view(_usage(now, 78, 28), 5, now, now=now)

    assert view.tooltip == (
        "QuotaTray\n\n"
        "5-hour remaining: 22%\n"
        "Resets in 2h 48m\n\n"
        "Weekly remaining: 72%\n"
        "Resets in 6d 16h"
    )
    assert not view.tooltip.endswith("\n")
    _assert_tooltip_has_no_update_timestamp(view.tooltip)


def test_tray_meter_stale_tooltip() -> None:
    now = datetime(2026, 8, 26, 12, tzinfo=timezone.utc)
    view = build_tray_meter_view(_usage(now, 78, 28), 5, now - timedelta(minutes=17), now=now)

    assert view.remaining_percent == 22
    assert "Data may be stale" in view.tooltip
    _assert_tooltip_has_no_update_timestamp(view.tooltip)


def test_tray_meter_failed_tooltip_keeps_last_number() -> None:
    now = datetime(2026, 8, 26, 12, tzinfo=timezone.utc)
    view = build_tray_meter_view(_usage(now, 78, 28), 5, now, refresh_failed=True, now=now)

    assert view.remaining_percent == 22
    assert "Update failed" in view.tooltip
    _assert_tooltip_has_no_update_timestamp(view.tooltip)


def test_tray_meter_reset_credit_tooltip() -> None:
    now = datetime(2026, 8, 26, 12, tzinfo=timezone.utc)
    view = build_tray_meter_view(_usage(now, 78, 28, reset_credits=1), 5, now, now=now)

    assert view.tooltip.endswith("Reset credit: 1")
    assert "Reset credit: 1 available" not in view.tooltip
    _assert_tooltip_has_no_update_timestamp(view.tooltip)


def test_tray_meter_reset_credit_plural_tooltip() -> None:
    now = datetime(2026, 8, 26, 12, tzinfo=timezone.utc)
    view = build_tray_meter_view(_usage(now, 78, 28, reset_credits=2), 5, now, now=now)

    assert "Reset credits: 2" in view.tooltip
    _assert_tooltip_has_no_update_timestamp(view.tooltip)


def test_tray_meter_hides_missing_reset_credit() -> None:
    now = datetime(2026, 8, 26, 12, tzinfo=timezone.utc)
    view = build_tray_meter_view(_usage(now, 78, 28), 5, now, now=now)

    assert "Reset credit" not in view.tooltip
    assert view.tooltip.endswith("Resets in 6d 16h")
    _assert_tooltip_has_no_update_timestamp(view.tooltip)


def test_tray_meter_no_data_loading_state() -> None:
    view = build_tray_meter_view(None, 5, None)

    assert view.remaining_percent is None
    assert view.loading is True
    assert view.tooltip == "QuotaTray — loading..."


def test_settings_dialog_saves_values_and_startup_path(qapp, tmp_path) -> None:
    from codex_usage_monitor.ui.settings_dialog import SettingsDialog

    class FakeStartup:
        def __init__(self):
            self.path = None
            self.disabled = False

        def can_register(self):
            return True

        def is_enabled(self):
            return False

        def enable(self, path):
            self.path = str(path)

        def disable(self):
            self.disabled = True

    startup = FakeStartup()
    settings = AppSettings(tmp_path / "settings.ini")
    executable = str(tmp_path / "QuotaTray.exe")
    dialog = SettingsDialog(settings, startup, executable)
    assert dialog.windowTitle() == "Settings"

    dialog.refresh.setCurrentIndex(dialog.refresh.findData(10))
    dialog.startup.setChecked(True)
    dialog.codex_path.setText(r"C:\Apps\codex.exe")
    dialog.accept()

    saved = settings.load()
    assert saved.refresh_interval_minutes == 10
    assert saved.start_with_windows is True
    assert saved.codex_executable_path == r"C:\Apps\codex.exe"
    assert startup.path == executable
    assert startup.disabled is False


def test_tray_meter_icon_rendering_one_digit(qapp) -> None:
    from PySide6.QtGui import QIcon

    icon = render_remaining_icon(7, dpr=1.0)

    assert isinstance(icon, QIcon)
    assert icon.isNull() is False


def test_tray_meter_icon_rendering_two_digits(qapp) -> None:
    from PySide6.QtGui import QIcon

    icon = render_remaining_icon(22, dpr=1.0)

    assert isinstance(icon, QIcon)
    assert icon.isNull() is False


def test_tray_meter_icon_rendering_three_digit_100(qapp) -> None:
    from PySide6.QtGui import QIcon

    icon = render_remaining_icon(100, dpr=1.0)

    assert isinstance(icon, QIcon)
    assert icon.isNull() is False


def test_legacy_widget_settings_are_ignored_without_rewrite(tmp_path) -> None:
    path = tmp_path / "settings.ini"
    original = (
        "[ui]\ndisplay_mode = floating_widget\n"
        "[widget]\nshow_on_startup = false\nalways_on_top = false\n"
        "position = 12,34\nshow_reset_credit_section = false\n"
        "[taskbar_dock]\nposition = 56,78\nmanual_position = true\n"
        "[refresh]\ninterval_minutes = 15\n"
    )
    path.write_text(original, encoding="utf-8")

    values = AppSettings(path).load()

    assert values.refresh_interval_minutes == 15
    assert values.start_with_windows is False
    assert path.read_text(encoding="utf-8") == original


def test_tray_menu_has_only_supported_actions(qapp, tmp_path) -> None:
    from codex_usage_monitor.ui.tray import TrayController

    controller = TrayController(qapp, 5, AppSettings(tmp_path / "settings.ini"))
    actions = controller.menu.actions()
    assert [None if action.isSeparator() else action.text() for action in actions] == [
        "Refresh Now", "Settings", "Open Data Folder", None, "About", "Exit",
    ]
    assert [action for action in actions if not action.isSeparator()] == [
        controller.refresh_action, controller.settings_action, controller.open_data_action,
        controller.about_action, controller.exit_action,
    ]


@pytest.mark.parametrize("override_version", [None, "9.8.7-test"])
def test_about_action_displays_unified_version(qapp, tmp_path, monkeypatch, override_version) -> None:
    from codex_usage_monitor import version
    from codex_usage_monitor.ui.tray import QMessageBox, TrayController

    if override_version is not None:
        monkeypatch.setattr(version, "__version__", override_version)
    calls = []
    monkeypatch.setattr(QMessageBox, "about", lambda *args: calls.append(args))
    controller = TrayController(qapp, 5, AppSettings(tmp_path / "settings.ini"))
    controller.about_action.trigger()
    assert calls == [(
        controller.menu,
        "About QuotaTray",
        f"QuotaTray\n\nVersion {version.__version__}\n\n"
        "An unofficial Windows tray monitor\nfor OpenAI Codex usage limits.\n\n"
        "Unofficial third-party project.\n"
        "Not affiliated with or endorsed by OpenAI.",
    )]


def test_window_remaining_handles_missing_window() -> None:
    assert window_remaining_percent(None) is None


@pytest.mark.parametrize("primary,weekly,expected", [(0, 0, 100), (40, 30, 60), (0, 100, 0), (70, 100, 0), (0, 125, 0), (0, 99, 100), (100, 30, 0)])
def test_effective_quota(primary, weekly, expected) -> None:
    now = datetime(2026, 8, 26, 12, tzinfo=timezone.utc)
    view = build_tray_meter_view(_usage(now, primary, weekly, reset_credits=1), 5, now, now=now)
    assert view.remaining_percent == expected
    assert ("5-hour remaining:" in view.tooltip) == (weekly < 100)
    assert f"Weekly remaining: {max(0, 100 - weekly)}%" in view.tooltip
    assert "Resets in 6d 16h" in view.tooltip
    _assert_tooltip_has_no_update_timestamp(view.tooltip)
    assert "Reset credit: 1" in view.tooltip


def test_weekly_recovery_restores_primary() -> None:
    now = datetime(2026, 8, 26, 12, tzinfo=timezone.utc)
    views = [build_tray_meter_view(_usage(now, 40, weekly), 5, now, now=now) for weekly in (100, 99)]
    assert [v.remaining_percent for v in views] == [0, 60]
    assert "5-hour" not in views[0].tooltip
    assert "5-hour remaining: 60%" in views[1].tooltip
    assert views[0].tooltip == "QuotaTray\n\nWeekly remaining: 0%\nResets in 6d 16h"
    _assert_tooltip_has_no_update_timestamp(views[0].tooltip)


@pytest.mark.parametrize("secondary", [None, UsageWindow()])
def test_missing_weekly_does_not_override_primary(secondary) -> None:
    usage = UsageSnapshot(primary=UsageWindow(40, 300), secondary=secondary)
    view = build_tray_meter_view(usage, 5, None)
    assert view.remaining_percent == 60
    assert "5-hour remaining: 60%" in view.tooltip
    assert "Weekly remaining: unknown" in view.tooltip
    _assert_tooltip_has_no_update_timestamp(view.tooltip)


def _usage(
    now: datetime,
    primary_used: int,
    weekly_used: int,
    reset_credits: int = 0,
) -> UsageSnapshot:
    return UsageSnapshot(
        primary=UsageWindow(primary_used, 300, now + timedelta(hours=2, minutes=48)),
        secondary=UsageWindow(weekly_used, 10080, now + timedelta(days=6, hours=16)),
        reset_credits=RateLimitResetCredits(reset_credits, ()),
    )


def _assert_tooltip_has_no_update_timestamp(tooltip: str) -> None:
    for forbidden in ("Updated just now", "Updated", "Last updated"):
        assert forbidden not in tooltip
