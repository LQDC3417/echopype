"""左侧面板 — Matecho风格

集成文件树、变量列表、频率选择、滤波器快速控制

设计参考Matecho界面：
- 文件树（可折叠）
- 频率/通道选择
- 回波类型选择
- 滤波器快速开关
- 变量列表
"""

import logging
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class QuickControlsWidget(QWidget):
    """快速控制面板 — 频率选择、回波类型、滤波器开关"""

    # 信号
    frequency_changed = Signal(str)  # 频率/通道变更
    echotype_changed = Signal(str)  # 回波类型变更
    filter_toggled = Signal(str, bool)  # 滤波器开关 (名称, 状态)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)

        # ── 频率/通道选择 ──
        freq_group = QGroupBox("频率选择")
        freq_layout = QVBoxLayout()
        freq_layout.setSpacing(4)
        freq_layout.setContentsMargins(8, 12, 8, 8)

        self.combo_frequency = QComboBox()
        self.combo_frequency.setToolTip("选择工作频率/通道")
        self.combo_frequency.currentTextChanged.connect(self.frequency_changed)
        freq_layout.addWidget(self.combo_frequency)

        freq_group.setLayout(freq_layout)
        layout.addWidget(freq_group)

        # ── 回波类型选择 ──
        echo_group = QGroupBox("显示类型")
        echo_layout = QVBoxLayout()
        echo_layout.setSpacing(4)
        echo_layout.setContentsMargins(8, 12, 8, 8)

        self.combo_echotype = QComboBox()
        self.combo_echotype.addItems(["Sv (原始)", "Sv (去噪)", "噪声", "SNR"])
        self.combo_echotype.setToolTip("选择显示的回波数据类型")
        self.combo_echotype.currentTextChanged.connect(self._on_echotype_changed)
        echo_layout.addWidget(self.combo_echotype)

        echo_group.setLayout(echo_layout)
        layout.addWidget(echo_group)

        # ── 滤波器快速开关 ──
        filter_group = QGroupBox("滤波器")
        filter_layout = QVBoxLayout()
        filter_layout.setSpacing(4)
        filter_layout.setContentsMargins(8, 12, 8, 8)

        self.chk_noise = QCheckBox("噪声去除")
        self.chk_noise.setChecked(True)
        self.chk_noise.setToolTip("启用/禁用噪声去除")
        self.chk_noise.toggled.connect(lambda v: self.filter_toggled.emit("noise", v))

        self.chk_bottom = QCheckBox("底部检测")
        self.chk_bottom.setChecked(True)
        self.chk_bottom.setToolTip("显示/隐藏底部检测线")
        self.chk_bottom.toggled.connect(lambda v: self.filter_toggled.emit("bottom", v))

        self.chk_schools = QCheckBox("鱼群显示")
        self.chk_schools.setChecked(True)
        self.chk_schools.setToolTip("显示/隐藏鱼群叠加")
        self.chk_schools.toggled.connect(lambda v: self.filter_toggled.emit("schools", v))

        filter_layout.addWidget(self.chk_noise)
        filter_layout.addWidget(self.chk_bottom)
        filter_layout.addWidget(self.chk_schools)

        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)

        layout.addStretch()

    def set_frequencies(self, channels: list[str]):
        """设置可用频率列表"""
        self.combo_frequency.blockSignals(True)
        self.combo_frequency.clear()
        self.combo_frequency.addItems(channels)
        self.combo_frequency.blockSignals(False)

    def _on_echotype_changed(self, text: str):
        """回波类型变更"""
        # 提取key部分："Sv (原始)" → "Sv"
        key = text.split(" ")[0] if text else "Sv"
        self.echotype_changed.emit(key)


class VariableListWidget(QListWidget):
    """变量列表组件"""

    variable_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._variables = {}
        self.currentTextChanged.connect(self._on_selection)

    def add_variable(self, name: str, data, label: str = None):
        """添加变量"""
        self._variables[name] = data
        display = label or name
        items = self.findItems(display, Qt.MatchExactly)
        if not items:
            self.addItem(display)
        if self.count() == 1:
            self.setCurrentRow(0)

    def get_variable(self, name: str):
        return self._variables.get(name)

    def clear_variables(self):
        self._variables.clear()
        self.clear()

    def _on_selection(self, text: str):
        if text:
            self.variable_selected.emit(text)

    def get_current_data(self):
        """获取当前选中变量的数据"""
        item = self.currentItem()
        if item:
            return self._variables.get(item.text())
        return None


class LeftPanel(QWidget):
    """左侧面板 — 集成文件树、变量列表、快速控制"""

    # 信号
    fileset_selected = Signal(object)
    file_selected = Signal(object)
    channel_selected = Signal(str)
    frequency_changed = Signal(str)
    echotype_changed = Signal(str)
    filter_toggled = Signal(str, bool)
    variable_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(6)
        layout.setContentsMargins(6, 6, 6, 6)

        # ── 快速控制面板 ──
        self.quick_controls = QuickControlsWidget()
        layout.addWidget(self.quick_controls)

        # ── 变量列表 ──
        var_group = QGroupBox("变量列表")
        var_layout = QVBoxLayout()
        var_layout.setSpacing(4)
        var_layout.setContentsMargins(8, 12, 8, 8)

        self.variable_list = VariableListWidget()
        self.variable_list.variable_selected.connect(self.variable_selected)
        var_layout.addWidget(self.variable_list)

        var_group.setLayout(var_layout)
        layout.addWidget(var_group, 1)  # 占据剩余空间

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    def set_frequencies(self, channels: list[str]):
        """设置可用频率"""
        self.quick_controls.set_frequencies(channels)

    def add_variable(self, name: str, data, label: str = None):
        """添加变量"""
        self.variable_list.add_variable(name, data, label)

    def clear_variables(self):
        """清空变量"""
        self.variable_list.clear_variables()

    def get_current_data(self):
        """获取当前选中的变量数据"""
        return self.variable_list.get_current_data()
