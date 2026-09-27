from __future__ import annotations

import sys
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup, QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon


STYLE_NUMBER_LABEL = "number_label"
STYLE_NUMBER_ONLY = "number_only"
VALUES_NORMAL = "82 / 29"
VALUES_HUNDRED = "100 / 31"


@dataclass(frozen=True)
class MeterValues:
    primary: int
    weekly: int


class TrayMeterPoc:
    def __init__(self) -> None:
        self.style = STYLE_NUMBER_LABEL
        self.values = MeterValues(82, 29)

        self.menu = QMenu()
        self._build_menu()

        self.primary = QSystemTrayIcon()
        self.weekly = QSystemTrayIcon()
        self.primary.setContextMenu(self.menu)
        self.weekly.setContextMenu(self.menu)

        self.refresh_icons()
        self.primary.show()
        self.weekly.show()

    def _build_menu(self) -> None:
        style_menu = self.menu.addMenu("Style")
        self.style_group = QActionGroup(self.menu)
        self.style_group.setExclusive(True)

        self.number_label_action = QAction("Number + Label", self.style_group)
        self.number_label_action.setCheckable(True)
        self.number_label_action.setChecked(True)
        self.number_only_action = QAction("Number Only", self.style_group)
        self.number_only_action.setCheckable(True)
        style_menu.addAction(self.number_label_action)
        style_menu.addAction(self.number_only_action)

        values_menu = self.menu.addMenu("Test Values")
        self.values_group = QActionGroup(self.menu)
        self.values_group.setExclusive(True)

        self.normal_values_action = QAction(VALUES_NORMAL, self.values_group)
        self.normal_values_action.setCheckable(True)
        self.normal_values_action.setChecked(True)
        self.hundred_values_action = QAction(VALUES_HUNDRED, self.values_group)
        self.hundred_values_action.setCheckable(True)
        values_menu.addAction(self.normal_values_action)
        values_menu.addAction(self.hundred_values_action)

        self.menu.addSeparator()
        self.exit_action = self.menu.addAction("Exit POC")

        self.number_label_action.triggered.connect(lambda: self.set_style(STYLE_NUMBER_LABEL))
        self.number_only_action.triggered.connect(lambda: self.set_style(STYLE_NUMBER_ONLY))
        self.normal_values_action.triggered.connect(lambda: self.set_values(MeterValues(82, 29)))
        self.hundred_values_action.triggered.connect(lambda: self.set_values(MeterValues(100, 31)))
        self.exit_action.triggered.connect(QApplication.instance().quit)

    def set_style(self, style: str) -> None:
        self.style = style
        self.refresh_icons()

    def set_values(self, values: MeterValues) -> None:
        self.values = values
        self.refresh_icons()

    def refresh_icons(self) -> None:
        self.primary.setIcon(make_meter_icon(self.values.primary, "5H", self.style))
        self.weekly.setIcon(make_meter_icon(self.values.weekly, "W", self.style))
        self.primary.setToolTip(
            f"Codex — 5 Hour\n{self.values.primary}% used\nResets in 2h 48m"
        )
        self.weekly.setToolTip(
            f"Codex — Weekly\n{self.values.weekly}% used\nResets in 6d 16h"
        )


def make_meter_icon(value: int, label: str, style: str) -> QIcon:
    scale = _device_scale()
    logical_size = 24
    physical_size = logical_size * scale
    pixmap = QPixmap(physical_size, physical_size)
    pixmap.setDevicePixelRatio(scale)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.TextAntialiasing, True)

    text = str(value)
    palette = QApplication.palette()
    window = palette.window().color()
    is_dark = window.lightness() < 128
    background = QColor(24, 27, 31, 245) if is_dark else QColor(248, 250, 252, 245)
    border = QColor(91, 99, 112, 220) if is_dark else QColor(74, 85, 104, 220)
    foreground = QColor(255, 255, 255) if is_dark else QColor(17, 24, 39)

    painter.setPen(border)
    painter.setBrush(background)
    painter.drawRoundedRect(1, 1, logical_size - 2, logical_size - 2, 4, 4)
    painter.setPen(foreground)

    if style == STYLE_NUMBER_ONLY:
        number_font = _fit_font(painter, text, logical_size - 4, 15, 5, bold=True)
        painter.setFont(number_font)
        painter.drawText(0, 1, logical_size, logical_size - 2, Qt.AlignCenter, text)
    else:
        number_font = _fit_font(painter, text, logical_size - 4, 13, 5, bold=True)
        label_font = _fit_font(painter, label, logical_size - 4, 8, 5, bold=True)
        painter.setFont(number_font)
        painter.drawText(0, 1, logical_size, 14, Qt.AlignCenter, text)
        painter.setFont(label_font)
        painter.drawText(0, 13, logical_size, 9, Qt.AlignCenter, label)

    painter.end()
    return QIcon(pixmap)


def _fit_font(
    painter: QPainter,
    text: str,
    max_width: int,
    start_size: int,
    min_size: int,
    bold: bool,
) -> QFont:
    font = QFont("Segoe UI", start_size)
    font.setBold(bold)
    while font.pointSize() > min_size:
        painter.setFont(font)
        if painter.fontMetrics().horizontalAdvance(text) <= max_width:
            break
        font.setPointSize(font.pointSize() - 1)
    return font


def _device_scale() -> int:
    screen = QApplication.primaryScreen()
    if screen is None:
        return 4
    return max(3, min(6, round(screen.devicePixelRatio() * 4)))


def main() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    if not QSystemTrayIcon.isSystemTrayAvailable():
        print("System tray is not available.", file=sys.stderr)
        return 1
    TrayMeterPoc()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
