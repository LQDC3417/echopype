"""工具栏组件 - 基于 Echoview 设计的专业风格

设计原则：
- 中文为默认语言，可切换英文
- Qt 内置标准图标（QStyle.StandardPixmap），深色主题自动适配
- 状态一目了然（选中态、禁用态）
- 参数控件紧凑排列
- 参照 Echoview 布局：单行工具栏 + 紧凑控件
"""

from enum import Enum

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QLabel,
    QSlider,
    QToolBar,
    QToolButton,
)

from src.gui.icons import icon
from src.gui.i18n import T


class MouseMode(Enum):
    NAVIGATE = 0
    SELECT_NOISE = 1
    DRAW_BOTTOM = 2
    INSPECT = 3
    PAN = 4


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
        self.setIconSize(QSize(22, 22))
        self.setToolButtonStyle(Qt.ToolButtonIconOnly)

        # ─── 文件操作 ───
        self.addAction(self._act(T("toolbar_import"), self.open_clicked, "import", "Ctrl+I"))
        self.addAction(self._act(T("toolbar_open_config"), self.open_config_clicked, "open", "Ctrl+O"))
        self.addAction(self._act(T("toolbar_save_config"), self.save_config_clicked, "save", "Ctrl+Shift+S"))
        self.addSeparator()

        # ─── 流程控制 ───
        self._run_act = self._act(T("toolbar_run_all"), self.run_clicked, "run", "F5")
        self.addAction(self._run_act)
        self.addSeparator()

        # ─── 撤销/重做 ───
        self.addAction(self._act(T("toolbar_undo"), self.undo_clicked, "undo", "Ctrl+Z"))
        self.addAction(self._act(T("toolbar_redo"), self.redo_clicked, "redo", "Ctrl+Y"))
        self.addSeparator()

        # ─── 导出 ───
        self.addAction(self._act(T("toolbar_export"), self.export_clicked, "export", "Ctrl+E"))

    def _act(self, text, signal, icon_name, shortcut=None):
        a = QAction(text, self)
        a.setIcon(icon(icon_name))
        a.setToolTip(text)
        a.setStatusTip(text)
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
        self.setIconSize(QSize(22, 22))
        self.setToolButtonStyle(Qt.ToolButtonIconOnly)

        # ─── 鼠标模式 ───
        self.mode_combo = QComboBox()
        self._update_mode_items()
        self.mode_combo.hide()
        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)
        self._mode_buttons = {}
        for mode, icon_name, label in (
            (MouseMode.NAVIGATE, "pointer", T("mode_navigate")),
            (MouseMode.SELECT_NOISE, "noise", T("mode_select_noise")),
            (MouseMode.DRAW_BOTTOM, "bottom", T("mode_draw_bottom")),
            (MouseMode.INSPECT, "inspect", T("mode_inspect")),
        ):
            self._add_mode_button(mode, icon_name, label)
        self.pan_button = self._add_mode_button(MouseMode.PAN, "pan_open", T("mode_pan"))
        self.pan_button.setObjectName("panToolButton")
        self.mode_combo.currentIndexChanged.connect(self._on_mode_index_changed)

        self.addSeparator()

        # ─── 视图控制 ───
        self.addAction(self._act(T("toolbar_reset"), self.reset_view_clicked, "reset"))
        self.addAction(self._act(T("toolbar_fit"), self.fit_view_clicked, "fit"))

        self.addSeparator()

        # ─── 文件翻页 ───
        self.addAction(self._act(T("toolbar_prev"), self.prev_file_clicked, "prev"))
        self.addAction(self._act(T("toolbar_next"), self.next_file_clicked, "next"))

        self.addSeparator()

        # ─── 颜色映射 ───
        color_icon = QToolButton(self)
        color_icon.setIcon(icon("palette"))
        color_icon.setToolTip(T("toolbar_color"))
        color_icon.setAccessibleName(T("toolbar_color"))
        color_icon.setEnabled(False)
        self.addWidget(color_icon)
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
            T("mode_pan"),
        ])
        self.mode_combo.setCurrentIndex(current if current >= 0 else 0)
        if hasattr(self, "pan_button"):
            self.pan_button.setChecked(self.mode_combo.currentIndex() == MouseMode.PAN.value)
        self.mode_combo.blockSignals(False)

    def _on_mode_index_changed(self, index: int):
        button = getattr(self, "_mode_buttons", {}).get(MouseMode(index))
        if button is not None:
            button.setChecked(True)
        self.mode_changed.emit(MouseMode(index))

    def _add_mode_button(self, mode: MouseMode, icon_name: str, label: str) -> QToolButton:
        button = QToolButton(self)
        button.setCheckable(True)
        button.setIcon(icon(icon_name))
        button.setIconSize(QSize(22, 22))
        button.setToolTip(label)
        button.setAccessibleName(label)
        button.clicked.connect(lambda checked=False, selected=mode: self._select_mode(selected))
        self._mode_group.addButton(button, mode.value)
        self._mode_buttons[mode] = button
        self.addWidget(button)
        return button

    def _select_mode(self, mode: MouseMode) -> None:
        """图标工具与保留的模式选择状态始终同步。"""
        self._mode_buttons[mode].setChecked(True)
        if self.mode_combo.currentIndex() != mode.value:
            self.mode_combo.setCurrentIndex(mode.value)

    def retranslate_ui(self):
        """重新翻译界面文本（语言切换时调用）"""
        self._update_mode_items()

    def _act(self, text, signal, icon_name, shortcut=None):
        a = QAction(text, self)
        a.setIcon(icon(icon_name))
        a.setToolTip(text)
        a.setStatusTip(text)
        if shortcut:
            a.setShortcut(shortcut)
        a.triggered.connect(signal)
        return a

    def _label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #8a8a92; font-size: 11px;")
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

    def set_display_values(self, cmap: str, vmin: float, vmax: float) -> None:
        """同步右侧显示设置，避免工具栏和属性面板各自维护一份状态。"""
        self.cmap_combo.blockSignals(True)
        self.slider_vmin.blockSignals(True)
        self.slider_vmax.blockSignals(True)
        self.cmap_combo.setCurrentText(cmap)
        self.slider_vmin.setValue(round(vmin))
        self.slider_vmax.setValue(round(vmax))
        self.cmap_combo.blockSignals(False)
        self.slider_vmin.blockSignals(False)
        self.slider_vmax.blockSignals(False)
        self.lbl_vmin.setText(str(round(vmin)))
        self.lbl_vmax.setText(str(round(vmax)))

