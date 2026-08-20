"""区域列表面板 — 底部可折叠面板，显示分析区域

参照 Echoview 底部 Region Browser 面板
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMenu,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
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


class RegionBrowserWidget(QWidget):
    """Region Browser 容器：导航按钮行 + 区域表格（参照 Echoview 底部面板）

    信号：
    - region_selected(int)：双击区域
    - region_deleted(int)：右键删除
    - region_export(int)：右键导出
    """
    region_selected = Signal(int)
    region_deleted = Signal(int)
    region_export = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # 导航按钮行（参照 Echoview Region Browser 的 Prev/Next）
        nav = QHBoxLayout()
        nav.setSpacing(4)
        self.btn_prev = QPushButton(T("region_prev"))
        self.btn_prev.setToolTip(T("region_prev"))
        self.btn_prev.clicked.connect(self._select_prev)
        self.btn_next = QPushButton(T("region_next"))
        self.btn_next.setToolTip(T("region_next"))
        self.btn_next.clicked.connect(self._select_next)
        nav.addWidget(self.btn_prev)
        nav.addWidget(self.btn_next)
        nav.addStretch()
        layout.addLayout(nav)

        self.table = RegionTableWidget()
        self.table.region_selected.connect(self.region_selected)
        self.table.region_deleted.connect(self.region_deleted)
        self.table.region_export.connect(self.region_export)
        layout.addWidget(self.table, 1)

    def _select_prev(self):
        """选中上一个区域行"""
        row = self.table.currentRow()
        if row > 0:
            self.table.selectRow(row - 1)
            self.table.setCurrentCell(row - 1, 0)
            self.table.scrollTo(self.table.model().index(row - 1, 0))

    def _select_next(self):
        """选中下一个区域行"""
        row = self.table.currentRow()
        if row < self.table.rowCount() - 1:
            self.table.selectRow(row + 1)
            self.table.setCurrentCell(row + 1, 0)
            self.table.scrollTo(self.table.model().index(row + 1, 0))
