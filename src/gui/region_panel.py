"""区域列表面板 — 底部可折叠面板，显示分析区域"""

from PySide6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, QMenu,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QAction


class RegionTableWidget(QTableWidget):
    """区域列表表格"""

    region_selected = Signal(int)   # region_id
    region_deleted = Signal(int)
    region_export = Signal(int)

    HEADERS = ["ID", "名称", "类型", "Ping 范围", "深度范围", "面积", "平均 Sv"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(len(self.HEADERS))
        self.setHorizontalHeaderLabels(self.HEADERS)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setAlternatingRowColors(True)
        self.horizontalHeader().setStretchLastSection(True)
        self.verticalHeader().setVisible(False)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.cellDoubleClicked.connect(self._on_double_click)
        self._next_id = 1

    def add_region(self, name: str, region_type: str,
                   ping_range: str, depth_range: str,
                   area: float, mean_sv: float) -> int:
        """添加区域到表格，返回 region_id"""
        rid = self._next_id
        self._next_id += 1
        row = self.rowCount()
        self.insertRow(row)
        vals = [str(rid), name, region_type, ping_range,
                depth_range, f"{area:.1f}", f"{mean_sv:.1f}"]
        for col, val in enumerate(vals):
            self.setItem(row, col, QTableWidgetItem(val))
        return rid

    def remove_region(self, region_id: int):
        for row in range(self.rowCount()):
            item = self.item(row, 0)
            if item and int(item.text()) == region_id:
                self.removeRow(row)
                return

    def _on_double_click(self, row, _col):
        item = self.item(row, 0)
        if item:
            self.region_selected.emit(int(item.text()))

    def _show_context_menu(self, pos):
        row = self.rowAt(pos.y())
        if row < 0:
            return
        item = self.item(row, 0)
        if not item:
            return
        rid = int(item.text())
        menu = QMenu(self)
        act_del = QAction("删除区域", self)
        act_del.triggered.connect(lambda: self.region_deleted.emit(rid))
        menu.addAction(act_del)
        act_exp = QAction("导出区域数据", self)
        act_exp.triggered.connect(lambda: self.region_export.emit(rid))
        menu.addAction(act_exp)
        menu.exec_(self.mapToGlobal(pos))
