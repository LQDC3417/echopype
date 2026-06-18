"""变量列表组件 — 显示可用的声学变量"""

from PySide6.QtWidgets import QListWidget
from PySide6.QtCore import Signal, Qt


class VariableListWidget(QListWidget):
    """左侧变量列表，类似 Echoview 的 Variable 列表"""

    variable_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMaximumWidth(200)
        self.setMinimumWidth(120)
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
