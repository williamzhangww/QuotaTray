from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from codex_usage_monitor.models import UsageSnapshot, UsageWindow, format_countdown
from codex_usage_monitor.ui.formatters import update_status


@dataclass(frozen=True)
class TrayMeterView:
    remaining_percent: int | None
    tooltip: str
    loading: bool = False
    low_weekly: bool = False


def remaining_percent_from_used(used_percent: int | None) -> int | None:
    if used_percent is None:
        return None
    return max(0, min(100, 100 - int(used_percent)))


def window_remaining_percent(window: UsageWindow | None) -> int | None:
    if window is None:
        return None
    return remaining_percent_from_used(window.used_percent)


def build_tray_meter_view(
    usage: UsageSnapshot | None,
    refresh_interval_minutes: int,
    last_updated: datetime | None,
    refresh_failed: bool = False,
    now: datetime | None = None,
) -> TrayMeterView:
    if usage is None:
        tooltip = "QuotaTray — loading..." if not refresh_failed else "QuotaTray — unavailable"
        return TrayMeterView(None, tooltip, loading=True)
    if not usage.is_available:
        return TrayMeterView(None, "QuotaTray — unavailable", loading=True)

    primary_remaining = window_remaining_percent(usage.primary)
    weekly_remaining = window_remaining_percent(usage.secondary)
    low_weekly = weekly_remaining is not None and weekly_remaining < 10
    displayed_remaining = weekly_remaining if low_weekly else primary_remaining
    tooltip = build_tray_meter_tooltip(
        usage,
        refresh_interval_minutes,
        last_updated,
        refresh_failed,
        now,
    )
    return TrayMeterView(
        displayed_remaining,
        tooltip,
        loading=displayed_remaining is None,
        low_weekly=low_weekly,
    )


def build_tray_meter_tooltip(
    usage: UsageSnapshot,
    refresh_interval_minutes: int,
    last_updated: datetime | None,
    refresh_failed: bool = False,
    now: datetime | None = None,
) -> str:
    status = update_status(last_updated, refresh_interval_minutes, refresh_failed, now)
    lines = ["QuotaTray", ""]
    if window_remaining_percent(usage.secondary) != 0:
        lines.extend([_window_tooltip("5-hour", usage.primary, now), ""])
    lines.append(_window_tooltip("Weekly", usage.secondary, now))
    if refresh_failed:
        lines.extend(["", status.text])
    elif status.is_stale or (usage.stale and usage.error):
        lines.extend(["", "Data may be stale"])
    if usage.reset_credits and usage.reset_credits.available_count > 0:
        count = usage.reset_credits.available_count
        label = "Reset credit" if count == 1 else "Reset credits"
        lines.extend(["", f"{label}: {count}"])
    return "\n".join(lines)


def render_remaining_icon(
    remaining_percent: int,
    palette=None,
    dpr: float | None = None,
    alert: bool = False,
):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
    from PySide6.QtWidgets import QApplication

    scale = _render_scale(dpr)
    logical_size = 24
    physical_size = logical_size * scale
    pixmap = QPixmap(physical_size, physical_size)
    pixmap.setDevicePixelRatio(scale)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.TextAntialiasing, True)

    if alert:
        background = QColor(220, 38, 38)
        border = QColor(127, 29, 29)
        foreground = QColor(0, 0, 0)
    else:
        app_palette = palette or QApplication.palette()
        base = app_palette.window().color()
        is_dark = base.lightness() < 128
        background = QColor(24, 27, 31, 245) if is_dark else QColor(248, 250, 252, 245)
        border = QColor(91, 99, 112, 220) if is_dark else QColor(74, 85, 104, 220)
        foreground = QColor(255, 255, 255) if is_dark else QColor(17, 24, 39)

    painter.setPen(border)
    painter.setBrush(background)
    painter.drawRoundedRect(1, 1, logical_size - 2, logical_size - 2, 4, 4)
    painter.setPen(foreground)

    text = str(max(0, min(100, int(remaining_percent))))
    font = _fit_font(painter, text, logical_size - 4, 15, 5)
    painter.setFont(font)
    painter.drawText(0, 1, logical_size, logical_size - 2, Qt.AlignCenter, text)
    painter.end()
    return QIcon(pixmap)


def _window_tooltip(label: str, window: UsageWindow | None, now: datetime | None) -> str:
    remaining = window_remaining_percent(window)
    remaining_text = "unknown" if remaining is None else f"{remaining}%"
    return f"{label} remaining: {remaining_text}\n{_reset_line(window, now)}"


def _reset_line(window: UsageWindow | None, now: datetime | None) -> str:
    if window is None or window.reset_at is None:
        return "Reset time unavailable"
    return f"Resets in {format_countdown(window.reset_at, now)}"


def _fit_font(painter, text: str, max_width: int, start_size: int, min_size: int):
    from PySide6.QtGui import QFont

    font = QFont("Segoe UI", start_size)
    font.setBold(True)
    while font.pointSize() > min_size:
        painter.setFont(font)
        if painter.fontMetrics().horizontalAdvance(text) <= max_width:
            break
        font.setPointSize(font.pointSize() - 1)
    return font


def _render_scale(dpr: float | None) -> int:
    from PySide6.QtWidgets import QApplication

    if dpr is None:
        screen = QApplication.primaryScreen()
        dpr = screen.devicePixelRatio() if screen else 1.0
    return max(3, min(6, round(float(dpr) * 4)))
