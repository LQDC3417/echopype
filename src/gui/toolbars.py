"""工具栏组件"""

from enum import Enum
from PySide6.QtWidgets import QToolBar, QComboBox
from PySide6.QtGui import QAction
from PySide6.QtCore import Signal


class MouseMode(Enum):
    NAVIGATE = 0
    SELECT_NOISE = 1
    DRAW_BOTTOM = 2
    ADJUST_BOTTOM = 3
    INSPECT = 4


class MainToolBar(QToolBar):
    """主工具栏"""

    open_clicked = Signal()
    run_clicked = Signal()
    undo_clicked = Signal()
    export_clicked = Signal()
    reset_view_clicked = Signal()
    mode_changed = Signal(MouseMode)
    colormap_changed = Signal(str, float, float)

    def __init__(self, parent=None):
        super().__init__("主工具栏", parent)
        self.setMovable(False)

        # 打开文件
        self.act_open = QAction("打开", self)
        self.act_open.triggered.connect(self.open_clicked)
        self.addAction(self.act_open)

        # 运行全部
        self.act_run = QAction("运行全部", self)
        self.act_run.triggered.connect(self.run_clicked)
        self.addAction(self.act_run)

        self.addSeparator()

        # 撤销
        self.act_undo = QAction("撤销", self)
        self.act_undo.setShortcut("Ctrl+Z")
        self.act_undo.triggered.connect(self.undo_clicked)
        self.addAction(self.act_undo)

        # 重置视图
        self.act_reset = QAction("重置视图", self)
        self.act_reset.triggered.connect(self.reset_view_clicked)
        self.addAction(self.act_reset)

        self.addSeparator()

        # 鼠标模式
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "导航", "框选噪声", "绘制底部线", "调整底部线", "查看鱼群"
        ])
        self.mode_combo.currentIndexChanged.connect(
            lambda idx: self.mode_changed.emit(MouseMode(idx))
        )
        self.addWidget(self.mode_combo)

        self.addSeparator()

        # 颜色映射
        self.cmap_combo = QComboBox()
        self.cmap_combo.addItems(["jet", "viridis", "inferno", "grayscale"])
        self.cmap_combo.currentTextChanged.connect(self._on_cmap_changed)
        self.addWidget(self.cmap_combo)

        self.addSeparator()

        # 导出
        self.act_export = QAction("导出", self)
        self.act_export.triggered.connect(self.export_clicked)
        self.addAction(self.act_export)

    def _on_cmap_changed(self, name):
        if name == "grayscale":
            name = "gray"
        self.colormap_changed.emit(name, -70, -20)
