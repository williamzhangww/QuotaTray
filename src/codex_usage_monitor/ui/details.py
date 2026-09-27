from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from codex_usage_monitor.models import DailyQuotaUsage
from codex_usage_monitor.ui.formatters import DetailRow, DetailsViewModel, format_history_daily_usage


class DetailsWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("QuotaTray Details")
        self.setMinimumSize(560, 560)

        self.plan = QLabel("Plan unavailable")
        self.plan.setObjectName("title")
        self.updated = QLabel("")
        self.updated.setObjectName("muted")

        self.current_limits = RowGroup("Current Limits")
        self.usage_pace = RowGroup("Usage & Pace")
        self.reset_credits = RowGroup("Reset Credits")
        self.history_title = QLabel("Last 7 days")
        self.history_title.setObjectName("sectionTitle")
        self.history_note = QLabel("Weekly quota used per day")
        self.history_note.setObjectName("muted")
        self.history = DailyHistoryChart()

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        layout.addWidget(self.plan)
        layout.addWidget(self.updated)
        layout.addWidget(self.current_limits)
        layout.addWidget(self.usage_pace)
        layout.addWidget(self.reset_credits)
        layout.addWidget(self.history_title)
        layout.addWidget(self.history_note)
        layout.addWidget(self.history)
        layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        self._apply_style()

    def _apply_style(self) -> None:
        base = self.palette().window().color()
        is_dark = base.lightness() < 128
        background = "#202124" if is_dark else "#f7f8fa"
        panel = "#26292e" if is_dark else "#ffffff"
        foreground = "#f3f5f7" if is_dark else "#20242a"
        secondary = "#a9b0ba" if is_dark else "#687281"
        border = "#3a3f48" if is_dark else "#d8dde5"
        self.setStyleSheet(
            """
            QWidget {
                background: %s;
                color: %s;
                font-family: "Segoe UI";
                font-size: 12px;
            }
            #title {
                font-size: 18px;
                font-weight: 700;
            }
            #sectionTitle {
                font-size: 13px;
                font-weight: 700;
            }
            #muted {
                color: %s;
            }
            QFrame {
                background: %s;
                border: 1px solid %s;
                border-radius: 6px;
            }
            QFrame QLabel {
                background: transparent;
                border: none;
            }
            #groupTitle {
                font-weight: 700;
            }
            #rowLabel {
                color: %s;
            }
            """
            % (background, foreground, secondary, panel, border, secondary)
        )

    def set_model(self, model: DetailsViewModel) -> None:
        self.plan.setText(f"QuotaTray · {model.plan}")
        self.updated.setText(model.update_status.text)
        self.current_limits.set_rows(model.current_limits)
        self.usage_pace.set_rows(model.usage_pace)
        self.reset_credits.setVisible(model.show_reset_credits)
        self.reset_credits.set_rows(model.reset_credits)
        self.history.set_days(model.history)


class RowGroup(QFrame):
    def __init__(self, title: str) -> None:
        super().__init__()
        self.title = QLabel(title)
        self.title.setObjectName("groupTitle")
        self.grid = QGridLayout()
        self.grid.setColumnStretch(1, 1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        layout.addWidget(self.title)
        layout.addLayout(self.grid)

    def set_rows(self, rows: tuple[DetailRow, ...]) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if not rows:
            rows = (DetailRow("Status", "unavailable"),)
        for row_index, row in enumerate(rows):
            label = QLabel(row.label)
            label.setObjectName("rowLabel")
            value = QLabel(row.value)
            value.setTextInteractionFlags(Qt.TextSelectableByMouse)
            value.setWordWrap(True)
            if row.tooltip:
                value.setToolTip(row.tooltip)
            self.grid.addWidget(label, row_index, 0, Qt.AlignTop)
            self.grid.addWidget(value, row_index, 1)


class DailyHistoryChart(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self._days: tuple[DailyQuotaUsage, ...] = ()
        self.setMinimumHeight(190)
        self.setSizePolicy(self.sizePolicy().horizontalPolicy(), self.sizePolicy().verticalPolicy())

    def sizeHint(self) -> QSize:  # type: ignore[override]
        return QSize(460, 190)

    def set_days(self, days: tuple[DailyQuotaUsage, ...]) -> None:
        self._days = days
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        is_dark = self.palette().window().color().lightness() < 128
        secondary = QColor("#a9b0ba" if is_dark else "#687281")
        foreground = QColor("#f3f5f7" if is_dark else "#20242a")
        track = QColor("#343942" if is_dark else "#edf0f4")
        complete = QColor("#5aa39a" if is_dark else "#2f8f83")
        partial = QColor("#8ab7b0" if is_dark else "#8ab7b0")
        rect = self.rect().adjusted(14, 14, -14, -14)
        if not self._days:
            painter.setPen(secondary)
            painter.drawText(rect, Qt.AlignCenter, "No history yet")
            return

        max_pp = max((day.consumed_pp or 0 for day in self._days), default=0)
        scale = max(10, max_pp)
        row_height = max(18, rect.height() // max(1, len(self._days)))
        label_width = 80
        value_width = 70
        bar_x = rect.left() + label_width
        bar_w = max(40, rect.width() - label_width - value_width)
        font = QFont(painter.font())
        font.setPointSize(9)
        painter.setFont(font)

        for index, day in enumerate(self._days):
            y = rect.top() + index * row_height
            center_y = y + row_height // 2
            painter.setPen(secondary)
            painter.drawText(rect.left(), y, label_width - 8, row_height, Qt.AlignVCenter, day.label)

            painter.setPen(Qt.NoPen)
            painter.setBrush(track)
            painter.drawRoundedRect(bar_x, center_y - 5, bar_w, 10, 3, 3)
            if day.consumed_pp is not None:
                fill_w = int(bar_w * min(day.consumed_pp, scale) / scale)
                painter.setBrush(complete if day.complete else partial)
                painter.drawRoundedRect(bar_x, center_y - 5, fill_w, 10, 3, 3)
                text = format_history_daily_usage(day)
            else:
                text = format_history_daily_usage(day)
            painter.setPen(QPen(foreground))
            painter.drawText(bar_x + bar_w + 10, y, value_width - 10, row_height, Qt.AlignVCenter, text)
        painter.end()
