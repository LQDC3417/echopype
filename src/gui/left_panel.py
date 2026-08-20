"""左侧面板 — 变量列表（参照 Echoview / Matecho 风格）

2026-08-20 重构：移除 QuickControlsWidget（频率选择/回波类型/滤波器开关）。
三者均为未接线的死控件（信号无接收者，set_frequencies 从未被调用）：
- 频率选择实际由 FilesetTreeWidget 的 ch_combo 负责
- 显示类型切换实际由变量列表（Sv / Sv_corrected）负责
- 滤波器开关无对应实现

保留：变量列表（variable_selected → echogram.set_data 真实接线）。
"""

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGroupBox,
    QListWidget,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.gui.i18n import T

logger = logging.getLogger(__name__)


class VariableListWidget(QListWidget):
    """变量列表组件"""

    variable_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._variables = {}
        self.currentTextChanged.connect(self._on_selection)

    def add_variable(self, name: str, data, label: str | None = None):
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
    """左侧面板 — 变量列表"""

    # 信号
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

        # ── 变量列表 ──
        var_group = QGroupBox(T("panel_variables"))
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

    def add_variable(self, name: str, data, label: str | None = None):
        """添加变量"""
        self.variable_list.add_variable(name, data, label)

    def clear_variables(self):
        """清空变量"""
        self.variable_list.clear_variables()

    def get_current_data(self):
        """获取当前选中的变量数据"""
        return self.variable_list.get_current_data()
