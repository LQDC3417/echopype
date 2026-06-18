"""工具栏组件 — Echoview 专业风格"""

from enum import Enum
from PySide6.QtWidgets import QToolBar, QComboBox, QLabel, QSlider
from PySide6.QtGui import QAction
from PySide6.QtCore import Signal, Qt


class MouseMode(Enum):
    NAVIGATE = 0
    SELECT_NOISE = 1
    DRAW_BOTTOM = 2
    ADJUST_BOTTOM = 3
    INSPECT = 4


class StandardToolBar(QToolBar):
    """标准工具栏"""

    open_clicked = Signal()
    open_config_clicked = Signal()
    save_config_clicked = Signal()
    run_clicked = Signal()
    undo_clicked = Signal()
    redo_clicked = Signal()
    export_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__("标准", parent)
        self.setMovable(False)
        self.setObjectName("StandardToolBar")

        self.addAction(self._act("📥 导入 Raw", self.open_clicked))
        self.addAction(self._act("📂 配置", self.open_config_clicked))
        self.addAction(self._act("💾 保存", self.save_config_clicked))
        self.addSeparator()
        self.addAction(self._act("▶ 全部运行", self.run_clicked))
        self.addSeparator()
        self.addAction(self._act("↩ 撤销", self.undo_clicked))
        self.addAction(self._act("↪ 重做", self.redo_clicked))
        self.addSeparator()
        self.addAction(self._act("📊 导出", self.export_clicked))

    def _act(self, text, signal, shortcut=None):
        a = QAction(text, self)
        if shortcut:
            a.setShortcut(shortcut)
        a.triggered.connect(signal)
        return a


class EchogramToolBar(QToolBar):
    """Echogram 工具栏：交互模式 + 显示控制"""

    mode_changed = Signal(MouseMode)
    colormap_changed = Signal(str, float, float)
    reset_view_clicked = Signal()
    fit_view_clicked = Signal()
    prev_file_clicked = Signal()
    next_file_clicked = Signal()

    MODE_LABELS = ["🔍 导航", "🔲 框选噪声", "✏ 绘制底线", "🔧 调整底线", "📍 检查鱼群"]

    def __init__(self, parent=None):
        super().__init__("Echogram", parent)
        self.setMovable(False)
        self.setObjectName("EchogramToolBar")

        # 鼠标模式
        self.addWidget(QLabel(" 模式: "))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(self.MODE_LABELS)
        self.mode_combo.currentIndexChanged.connect(
            lambda idx: self.mode_changed.emit(MouseMode(idx))
        )
        self.addWidget(self.mode_combo)

        self.addSeparator()

        # 视图
        self.addAction(self._act("🔄 重置", self.reset_view_clicked))
        self.addAction(self._act("⬜ 适应", self.fit_view_clicked))

        self.addSeparator()

        # 文件翻页
        self.addAction(self._act("◀", self.prev_file_clicked))
        self.addAction(self._act("▶", self.next_file_clicked))

        self.addSeparator()

        # 颜色映射
        self.addWidget(QLabel(" 颜色: "))
        self.cmap_combo = QComboBox()
        self.cmap_combo.addItems(["jet", "viridis", "inferno", "grayscale"])
        self.cmap_combo.currentTextChanged.connect(self._on_cmap_changed)
        self.addWidget(self.cmap_combo)

        self.addSeparator()

        # Sv 范围
        self.addWidget(QLabel(" Sv: "))
        self.slider_vmin = QSlider(Qt.Horizontal)
        self.slider_vmin.setRange(-100, 0)
        self.slider_vmin.setValue(-70)
        self.slider_vmin.setFixedWidth(120)
        self.addWidget(self.slider_vmin)
        self.lbl_vmin = QLabel("-70")
        self.lbl_vmin.setFixedWidth(32)
        self.addWidget(self.lbl_vmin)

        self.addWidget(QLabel(" ~ "))
        self.slider_vmax = QSlider(Qt.Horizontal)
        self.slider_vmax.setRange(-100, 0)
        self.slider_vmax.setValue(-20)
        self.slider_vmax.setFixedWidth(120)
        self.addWidget(self.slider_vmax)
        self.lbl_vmax = QLabel("-20")
        self.lbl_vmax.setFixedWidth(32)
        self.addWidget(self.lbl_vmax)

        self.slider_vmin.valueChanged.connect(self._on_sv_range_changed)
        self.slider_vmax.valueChanged.connect(self._on_sv_range_changed)

        self._current_cmap = "jet"

    def _act(self, text, signal, shortcut=None):
        a = QAction(text, self)
        if shortcut:
            a.setShortcut(shortcut)
        a.triggered.connect(signal)
        return a

    def _on_cmap_changed(self, name):
        self._current_cmap = "gray" if name == "grayscale" else name
        vmin, vmax = self.get_sv_range()
        self.colormap_changed.emit(self._current_cmap, vmin, vmax)

    def _on_sv_range_changed(self):
        vmin = self.slider_vmin.value()
        vmax = self.slider_vmax.value()
        if vmin >= vmax:
            vmin = vmax - 1
            self.slider_vmin.blockSignals(True)
            self.slider_vmin.setValue(vmin)
            self.slider_vmin.blockSignals(False)
        self.lbl_vmin.setText(str(vmin))
        self.lbl_vmax.setText(str(vmax))
        self.colormap_changed.emit(self._current_cmap, float(vmin), float(vmax))

    def get_sv_range(self):
        return float(self.slider_vmin.value()), float(self.slider_vmax.value())
