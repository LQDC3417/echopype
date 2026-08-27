"""主工具栏与 Echogram 交互工具栏。"""

from enum import Enum

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QLabel,
    QToolBar,
    QToolButton,
)

from src.gui.icons import icon
from src.gui.i18n import T


class MouseMode(Enum):
    NAVIGATE = 0
    SELECT_NOISE = 1
    DRAW_BOTTOM = 2  # 兼容旧调用方
    DRAW_LINE = 2
    INSPECT = 3
    PAN = 4


class StandardToolBar(QToolBar):
    """文件、撤销和导出操作；不再提供全局 Run All。"""

    open_clicked = Signal()
    open_config_clicked = Signal()
    save_config_clicked = Signal()
    run_clicked = Signal()  # 兼容既有 signal 连接，不创建入口
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
    """导航、平移和明确的线段选择/绘制入口。"""

    mode_changed = Signal(MouseMode)
    line_selected = Signal(str)
    draw_line_requested = Signal()
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
        self.addWidget(self._label("编辑线段"))
        self.line_combo = QComboBox()
        self.line_combo.setMinimumWidth(130)
        self.line_combo.currentIndexChanged.connect(lambda _: self.line_selected.emit(self.line_combo.currentData() or ""))
        self.addWidget(self.line_combo)
        self.draw_line_action = self._act("绘制线段", self.draw_line_requested, "ruler")
        self.addAction(self.draw_line_action)

    def _update_mode_items(self):
        self.mode_combo.blockSignals(True)
        current = self.mode_combo.currentIndex()
        self.mode_combo.clear()
        self.mode_combo.addItems([T("mode_navigate"), T("mode_select_noise"), T("mode_draw_bottom"), T("mode_inspect"), T("mode_pan")])
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

    def set_editable_lines(self, lines) -> None:
        """更新可绘制线段列表；选择本身不改变绘制模式。"""
        current = self.line_combo.currentData()
        self.line_combo.blockSignals(True)
        self.line_combo.clear()
        for line in lines:
            self.line_combo.addItem(line.name, line.id)
        index = self.line_combo.findData(current)
        self.line_combo.setCurrentIndex(max(index, 0))
        self.line_combo.blockSignals(False)
