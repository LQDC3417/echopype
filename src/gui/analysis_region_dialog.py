"""活动分析区域的上下边界设置窗口。"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
)


class AnalysisRegionDialog(QDialog):
    """选择两条不同的现有线作为分析区域边界。"""

    region_applied = Signal(str, str)

    def __init__(
        self,
        lines: list[tuple[str, str]],
        *,
        upper_line_id: str | None = None,
        lower_line_id: str | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("分析区域")
        self.upper_combo = QComboBox()
        self.lower_combo = QComboBox()
        for line_id, name in lines:
            self.upper_combo.addItem(name, line_id)
            self.lower_combo.addItem(name, line_id)
        self._select(self.upper_combo, upper_line_id)
        self._select(self.lower_combo, lower_line_id)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.addRow("在所选线以下", self.upper_combo)
        form.addRow("在所选线以上", self.lower_combo)
        layout.addLayout(form)
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #c62828;")
        layout.addWidget(self.error_label)
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.apply_changes)
        self.button_box.accepted.connect(self._accept_with_apply)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    @staticmethod
    def _select(combo: QComboBox, line_id: str | None) -> None:
        index = combo.findData(line_id)
        if index >= 0:
            combo.setCurrentIndex(index)

    def apply_changes(self) -> bool:
        upper = str(self.upper_combo.currentData() or "")
        lower = str(self.lower_combo.currentData() or "")
        if not upper or not lower or upper == lower:
            self.error_label.setText("Upper and lower boundaries must be different existing lines.")
            return False
        self.error_label.clear()
        self.region_applied.emit(upper, lower)
        return True

    def _accept_with_apply(self) -> None:
        if self.apply_changes():
            self.accept()
