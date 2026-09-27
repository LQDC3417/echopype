"""Echogram 图例显示设置对话框。"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)


class DisplaySettingsDialog(QDialog):
    """编辑 colormap 和 Sv 范围，Apply 后保持窗口打开。"""

    settings_applied = Signal(str, float, float)

    def __init__(self, colormap: str, vmin: float, vmax: float, parent=None):
        super().__init__(parent)
        self.setWindowTitle("图例显示设置")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.cmap_combo = QComboBox()
        self.cmap_combo.addItems(["jet", "viridis", "inferno", "gray"])
        self.cmap_combo.setCurrentText("gray" if colormap == "grayscale" else colormap)
        self.vmin_spin = self._range_spin(vmin)
        self.vmax_spin = self._range_spin(vmax)
        form.addRow("Colormap", self.cmap_combo)
        form.addRow("Sv 最小值 (dB)", self.vmin_spin)
        form.addRow("Sv 最大值 (dB)", self.vmax_spin)
        layout.addLayout(form)
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #B42318;")
        layout.addWidget(self.error_label)
        buttons = QHBoxLayout()
        self.apply_button = QPushButton("应用")
        self.ok_button = QPushButton("确定")
        self.cancel_button = QPushButton("取消")
        buttons.addStretch(1)
        buttons.addWidget(self.apply_button)
        buttons.addWidget(self.ok_button)
        buttons.addWidget(self.cancel_button)
        layout.addLayout(buttons)
        self.apply_button.clicked.connect(self.apply_settings)
        self.ok_button.clicked.connect(self._accept_with_apply)
        self.cancel_button.clicked.connect(self.reject)

    @staticmethod
    def _range_spin(value: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(-200.0, 100.0)
        spin.setDecimals(1)
        spin.setValue(float(value))
        return spin

    def apply_settings(self) -> bool:
        vmin = self.vmin_spin.value()
        vmax = self.vmax_spin.value()
        if vmin >= vmax:
            self.error_label.setText("Sv 最小值必须小于最大值")
            return False
        self.error_label.clear()
        self.settings_applied.emit(self.cmap_combo.currentText(), vmin, vmax)
        return True

    def _accept_with_apply(self) -> None:
        if self.apply_settings():
            self.accept()
