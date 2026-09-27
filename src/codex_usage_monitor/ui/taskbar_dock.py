from __future__ import annotations

from datetime import datetime
from typing import Callable

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QMenu, QWidget

from codex_usage_monitor.models import UsageSnapshot
from codex_usage_monitor.taskbar import (
    Point,
    Rect,
    Size,
    recover_saved_position,
    recommended_dock_position,
)
from codex_usage_monitor.ui.formatters import build_taskbar_dock_view


class TaskbarDock(QWidget):
    refreshRequested = Signal()
    settingsRequested = Signal()
    displayModeRequested = Signal(str)
    resetPositionRequested = Signal()
    exitRequested = Signal()

    def __init__(
        self,
        position_saved: Callable[[QPoint, bool], None] | None = None,
    ) -> None:
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setWindowTitle("QuotaTray Dock")
        self._position_saved = position_saved
        self._drag_offset: QPoint | None = None
        self._refresh_interval_minutes = 5
        self._last_updated: datetime | None = None
        self._last_usage: UsageSnapshot | None = None
        self._refresh_failed = False

        self.label = QLabel("5H — · unknown | W — · unknown", self)
        self.label.setObjectName("dockText")
        self.label.setAlignment(Qt.AlignCenter)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.label)

        self._menu = QMenu(self)
        self._refresh_action = self._menu.addAction("Refresh Now")
        self._settings_action = self._menu.addAction("Settings")
        self._menu.addSeparator()
        self._floating_action = self._menu.addAction("Switch to Floating Widget")
        self._tray_only_action = self._menu.addAction("Tray Only")
        self._reset_position_action = self._menu.addAction("Reset Dock Position")
        self._menu.addSeparator()
        self._exit_action = self._menu.addAction("Exit")

        self._refresh_action.triggered.connect(self.refreshRequested)
        self._settings_action.triggered.connect(self.settingsRequested)
        self._floating_action.triggered.connect(
            lambda: self.displayModeRequested.emit("floating_widget")
        )
        self._tray_only_action.triggered.connect(lambda: self.displayModeRequested.emit("tray_only"))
        self._reset_position_action.triggered.connect(self.resetPositionRequested)
        self._exit_action.triggered.connect(self.exitRequested)

        self._apply_style()
        self.adjustSize()

    def _apply_style(self) -> None:
        palette = QApplication.palette()
        base = palette.window().color()
        is_dark = base.lightness() < 128
        background = "rgba(32, 33, 36, 238)" if is_dark else "rgba(251, 251, 252, 238)"
        foreground = "#f4f6f8" if is_dark else "#1f2328"
        border = "#3a3f46" if is_dark else "#d7dce3"
        warning = "#d9a441" if is_dark else "#8a6100"
        self.setStyleSheet(
            """
            TaskbarDock {
                background: %s;
                border: 1px solid %s;
                border-radius: 6px;
            }
            #dockText {
                background: transparent;
                color: %s;
                font-family: "Segoe UI";
                font-size: 12px;
                font-weight: 600;
                padding: 7px 11px;
            }
            #dockText[stale="true"] {
                color: %s;
            }
            """
            % (background, border, foreground, warning)
        )

    def sizeHint(self):  # type: ignore[override]
        hint = self.label.sizeHint()
        return hint.expandedTo(hint)

    def set_refresh_interval_minutes(self, minutes: int) -> None:
        self._refresh_interval_minutes = max(1, minutes)

    def set_usage(
        self,
        usage: UsageSnapshot | None,
        last_updated: datetime | None = None,
        refresh_failed: bool = False,
        error: str | None = None,
    ) -> None:
        if last_updated is not None:
            self._last_updated = last_updated
        self._last_usage = usage
        self._refresh_failed = refresh_failed
        view = build_taskbar_dock_view(
            usage,
            self._refresh_interval_minutes,
            self._last_updated,
            refresh_failed,
        )
        if usage is None and error:
            self.setToolTip(f"QuotaTray\n\nUsage unavailable\n{error}")
        else:
            self.setToolTip(view.tooltip)
        self.label.setText(view.text)
        self.label.setProperty("stale", "true" if view.is_stale else "false")
        self.label.style().unpolish(self.label)
        self.label.style().polish(self.label)
        self.adjustSize()

    def show_at_recommended_position(
        self,
        saved_position: tuple[int, int] | None,
        manual_position: bool,
    ) -> None:
        self.adjustSize()
        fallback = self.recommended_position()
        if manual_position:
            point = recover_saved_position(
                _point_from_tuple(saved_position),
                self._dock_size(),
                self._visible_areas(),
                fallback,
            )
        else:
            point = fallback
        self.move(point.x, point.y)
        self.show()

    def reset_position(self) -> None:
        point = self.recommended_position()
        self.move(point.x, point.y)
        if self._position_saved is not None:
            self._position_saved(self.pos(), False)

    def recommended_position(self) -> Point:
        screen = QApplication.screenAt(self.pos()) or QApplication.primaryScreen()
        if screen is None:
            return Point(40, 40)
        return recommended_dock_position(
            _rect_from_qrect(screen.geometry()),
            _rect_from_qrect(screen.availableGeometry()),
            self._dock_size(),
        )

    def ensure_visible(self) -> None:
        point = recover_saved_position(
            Point(self.x(), self.y()),
            self._dock_size(),
            self._visible_areas(),
            self.recommended_position(),
        )
        self.move(point.x, point.y)

    def contextMenuEvent(self, event) -> None:  # type: ignore[override]
        self._menu.popup(event.globalPos())
        event.accept()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        elif event.button() == Qt.RightButton:
            self._menu.popup(event.globalPosition().toPoint())
            event.accept()

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if self._drag_offset is not None and self._position_saved is not None:
            self._position_saved(self.pos(), True)
        self._drag_offset = None
        event.accept()

    def _dock_size(self) -> Size:
        size = self.sizeHint()
        return Size(size.width(), size.height())

    def _visible_areas(self) -> tuple[Rect, ...]:
        return tuple(_rect_from_qrect(screen.availableGeometry()) for screen in QApplication.screens())


def _point_from_tuple(value: tuple[int, int] | None) -> Point | None:
    if value is None:
        return None
    return Point(value[0], value[1])


def _rect_from_qrect(value) -> Rect:
    return Rect(value.left(), value.top(), value.width(), value.height())
