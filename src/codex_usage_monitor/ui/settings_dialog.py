from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from codex_usage_monitor.settings import (
    REFRESH_INTERVAL_CHOICES,
    AppSettings,
    AppSettingsValues,
)
from codex_usage_monitor.startup import StartupManager


class SettingsDialog(QDialog):
    def __init__(
        self,
        app_settings: AppSettings,
        startup_manager: StartupManager,
        executable_path: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.app_settings = app_settings
        self.startup_manager = startup_manager
        self.executable_path = executable_path
        values = app_settings.load()

        self.refresh = QComboBox()
        for minutes in REFRESH_INTERVAL_CHOICES:
            label = "1 minute" if minutes == 1 else f"{minutes} minutes"
            self.refresh.addItem(label, minutes)
        index = self.refresh.findData(values.refresh_interval_minutes)
        self.refresh.setCurrentIndex(index if index >= 0 else 1)

        self.startup = QCheckBox()
        self.startup.setChecked(startup_manager.is_enabled())
        self.startup.setEnabled(startup_manager.can_register())
        self.codex_path = QLineEdit(values.codex_executable_path)
        self.codex_path.setPlaceholderText("Auto-detect")
        browse = QPushButton("Browse")
        browse.clicked.connect(self._browse_codex)

        path_row = QHBoxLayout()
        path_row.addWidget(self.codex_path)
        path_row.addWidget(browse)

        self.startup.setText("Start with Windows")
        general = QGroupBox("General")
        general_form = QFormLayout(general)
        general_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        general_form.addRow("Refresh interval", self.refresh)
        general_form.addRow("", self.startup)

        advanced = QGroupBox("Codex")
        advanced_form = QFormLayout(advanced)
        advanced_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        advanced_form.addRow("Executable path", path_row)

        save = QPushButton("Save")
        cancel = QPushButton("Cancel")
        save.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(save)
        buttons.addWidget(cancel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        layout.addWidget(general)
        layout.addWidget(advanced)
        layout.addLayout(buttons)
        self.setMinimumWidth(420)

    def values(self) -> AppSettingsValues:
        return AppSettingsValues(
            refresh_interval_minutes=int(self.refresh.currentData()),
            start_with_windows=self.startup.isChecked(),
            codex_executable_path=self.codex_path.text().strip(),
        )

    def accept(self) -> None:  # type: ignore[override]
        values = self.values()
        self.app_settings.save(values)
        if self.startup_manager.can_register():
            if values.start_with_windows:
                self.startup_manager.enable(self.executable_path)
            else:
                self.startup_manager.disable()
        super().accept()

    def _browse_codex(self) -> None:
        start = str(Path.home())
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select codex.exe",
            start,
            "Executables (*.exe);;All files (*.*)",
        )
        if path:
            self.codex_path.setText(path)
