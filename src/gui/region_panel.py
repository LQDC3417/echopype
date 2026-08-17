"""区域列表面板 — 底部可折叠面板，显示分析区域

参照 Echoview 底部 Region Browser 面板
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QMenu,
    QTableWidget,
    QTableWidgetItem,
)

from src.gui.i18n import T


class RegionTableWidget(QTableWidget):
    """区域列表表格 — 参照 Echoview Region Browser"""

    region_selected = Signal(int)   # region_id
    region_deleted = Signal(int)
    region_export = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_headers()
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setAlternatingRowColors(True)
        self.horizontalHeader().setStretchLastSection(True)
        self.verticalHeader().setVisible(False)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.cellDoubleClicked.connect(self._on_double_click)
        self._next_id = 1

    def _setup_headers(self):
        """设置表头"""
        headers = T("region_headers")
        self.setColumnCount(len(headers))
        self.setHorizontalHeaderLabels(headers)

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
        act_del = QAction(T("region_delete"), self)
        act_del.triggered.connect(lambda: self.region_deleted.emit(rid))
        menu.addAction(act_del)
        act_exp = QAction(T("region_export_data"), self)
        act_exp.triggered.connect(lambda: self.region_export.emit(rid))
        menu.addAction(act_exp)
        menu.exec_(self.mapToGlobal(pos))
