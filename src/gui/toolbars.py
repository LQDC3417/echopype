"""工具栏组件 - 基于 Echoview 设计的专业风格

设计原则：
- 中文为默认语言，可切换英文
- 简洁的文字标签，无 emoji
- 状态一目了然（选中态、禁用态）
- 参数控件紧凑排列
- 参照 Echoview 布局：单行工具栏 + 紧凑控件
"""

from enum import Enum

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QComboBox,
    QLabel,
    QSlider,
    QToolBar,
    QWidget,
)

from src.gui.i18n import T


class MouseMode(Enum):
    NAVIGATE = 0
    SELECT_NOISE = 1
    DRAW_BOTTOM = 2
    INSPECT = 3


class StandardToolBar(QToolBar):
    """标准工具栏 - 文件操作 + 流程控制

    布局（参照 Echoview）：[导入] [打开配置] [保存配置] | [全部运行] | [撤销] [重做] | [导出]
    """

    open_clicked = Signal()
    open_config_clicked = Signal()
    save_config_clicked = Signal()
    run_clicked = Signal()
    undo_clicked = Signal()
    redo_clicked = Signal()
    export_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__("Standard", parent)
        self.setMovable(False)
        self.setObjectName("StandardToolBar")
        self.setIconSize(QSize(16, 16))
        self.setToolButtonStyle(Qt.ToolButtonTextOnly)

        # ─── 文件操作 ───
        self.addAction(self._act(T("toolbar_import"), self.open_clicked, "Ctrl+I"))
        self.addAction(self._act(T("toolbar_open_config"), self.open_config_clicked, "Ctrl+O"))
        self.addAction(self._act(T("toolbar_save_config"), self.save_config_clicked, "Ctrl+Shift+S"))
        self.addSeparator()

        # ─── 流程控制 ───
        self._run_act = self._act(T("toolbar_run_all"), self.run_clicked, "F5")
        self.addAction(self._run_act)
        self.addSeparator()

        # ─── 撤销/重做 ───
        self.addAction(self._act(T("toolbar_undo"), self.undo_clicked, "Ctrl+Z"))
        self.addAction(self._act(T("toolbar_redo"), self.redo_clicked, "Ctrl+Y"))
        self.addSeparator()

        # ─── 导出 ───
        self.addAction(self._act(T("toolbar_export"), self.export_clicked, "Ctrl+E"))

    def _act(self, text, signal, shortcut=None):
        a = QAction(text, self)
        if shortcut:
            a.setShortcut(shortcut)
        a.triggered.connect(signal)
        return a


class EchogramToolBar(QToolBar):
    """Echogram 工具栏 - 交互模式 + 显示控制

    布局（参照 Echoview）：[模式▼] | [重置] [适应] | [<上一个] [下一个>] | [颜色▼] [Sv min ~ max]
    """

    mode_changed = Signal(MouseMode)
    colormap_changed = Signal(str, float, float)
    reset_view_clicked = Signal()
    fit_view_clicked = Signal()
    prev_file_clicked = Signal()
    next_file_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__("Echogram", parent)
        self.setMovable(False)
        self.setObjectName("EchogramToolBar")
        self.setIconSize(QSize(16, 16))
        self.setToolButtonStyle(Qt.ToolButtonTextOnly)

        # ─── 鼠标模式 ───
        self.addWidget(self._label(T("toolbar_mode")))
        self.mode_combo = QComboBox()
        self._update_mode_items()
        self.mode_combo.setMinimumWidth(100)
        self.mode_combo.currentIndexChanged.connect(
            lambda idx: self.mode_changed.emit(MouseMode(idx))
        )
        self.addWidget(self.mode_combo)

        self.addSeparator()

        # ─── 视图控制 ───
        self.addAction(self._act(T("toolbar_reset"), self.reset_view_clicked))
        self.addAction(self._act(T("toolbar_fit"), self.fit_view_clicked))

        self.addSeparator()

        # ─── 文件翻页 ───
        self.addAction(self._act(T("toolbar_prev"), self.prev_file_clicked))
        self.addAction(self._act(T("toolbar_next"), self.next_file_clicked))

        self.addSeparator()

        # ─── 颜色映射 ───
        self.addWidget(self._label(T("toolbar_color")))
        self.cmap_combo = QComboBox()
        self.cmap_combo.addItems(["jet", "viridis", "inferno", "gray"])
        self.cmap_combo.setMinimumWidth(80)
        self.cmap_combo.currentTextChanged.connect(self._on_cmap_changed)
        self.addWidget(self.cmap_combo)

        self.addSeparator()

        # ─── Sv 范围（参照 Echoview: 紧凑滑块）───
        self.addWidget(self._label(T("toolbar_sv")))

        self.slider_vmin = QSlider(Qt.Horizontal)
        self.slider_vmin.setRange(-100, 0)
        self.slider_vmin.setValue(-70)
        self.slider_vmin.setFixedWidth(100)
        self.addWidget(self.slider_vmin)

        self.lbl_vmin = QLabel("-70")
        self.lbl_vmin.setFixedWidth(30)
        self.lbl_vmin.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.addWidget(self.lbl_vmin)

        self.lbl_tilde = self._label("~")
        self.addWidget(self.lbl_tilde)

        self.slider_vmax = QSlider(Qt.Horizontal)
        self.slider_vmax.setRange(-100, 0)
        self.slider_vmax.setValue(-20)
        self.slider_vmax.setFixedWidth(100)
        self.addWidget(self.slider_vmax)

        self.lbl_vmax = QLabel("-20")
        self.lbl_vmax.setFixedWidth(30)
        self.lbl_vmax.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.addWidget(self.lbl_vmax)

        self.slider_vmin.valueChanged.connect(self._on_sv_range_changed)
        self.slider_vmax.valueChanged.connect(self._on_sv_range_changed)

    def _update_mode_items(self):
        """更新模式下拉框的文本（语言切换时调用）"""
        self.mode_combo.blockSignals(True)
        current = self.mode_combo.currentIndex()
        self.mode_combo.clear()
        self.mode_combo.addItems([
            T("mode_navigate"),
            T("mode_select_noise"),
            T("mode_draw_bottom"),
            T("mode_inspect"),
        ])
        self.mode_combo.setCurrentIndex(current if current >= 0 else 0)
        self.mode_combo.blockSignals(False)

    def retranslate_ui(self):
        """重新翻译界面文本（语言切换时调用）"""
        self._update_mode_items()

    def _act(self, text, signal, shortcut=None):
        a = QAction(text, self)
        if shortcut:
            a.setShortcut(shortcut)
        a.triggered.connect(signal)
        return a

    def _label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #666; font-size: 11px;")
        return lbl

    def _on_cmap_changed(self, cmap):
        vmin = self.slider_vmin.value()
        vmax = self.slider_vmax.value()
        self.colormap_changed.emit(cmap, vmin, vmax)

    def _on_sv_range_changed(self, _):
        vmin = self.slider_vmin.value()
        vmax = self.slider_vmax.value()
        self.lbl_vmin.setText(str(vmin))
        self.lbl_vmax.setText(str(vmax))
        cmap = self.cmap_combo.currentText()
        self.colormap_changed.emit(cmap, vmin, vmax)
