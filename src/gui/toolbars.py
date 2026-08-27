"""主工具栏与 Echogram 交互工具栏。"""

from enum import Enum

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QComboBox, QLabel, QStyle, QToolBar

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
        self.setIconSize(QSize(16, 16))
        self.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.addAction(self._act(T("toolbar_import"), self.open_clicked, "Ctrl+I", QStyle.SP_DialogOpenButton))
        self.addAction(self._act(T("toolbar_open_config"), self.open_config_clicked, "Ctrl+O", QStyle.SP_DirOpenIcon))
        self.addAction(self._act(T("toolbar_save_config"), self.save_config_clicked, "Ctrl+Shift+S", QStyle.SP_DialogSaveButton))
        self.addSeparator()
        self.addAction(self._act(T("toolbar_undo"), self.undo_clicked, "Ctrl+Z", QStyle.SP_ArrowBack))
        self.addAction(self._act(T("toolbar_redo"), self.redo_clicked, "Ctrl+Y", QStyle.SP_ArrowForward))
        self.addSeparator()
        self.addAction(self._act(T("toolbar_export"), self.export_clicked, "Ctrl+E", QStyle.SP_DialogSaveButton))

    def _act(self, text, signal, shortcut=None, icon_standard=None):
        action = QAction(text, self)
        if shortcut:
            action.setShortcut(shortcut)
        if icon_standard is not None:
            action.setIcon(self.style().standardIcon(icon_standard))
        action.triggered.connect(signal)
        return action


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
        self.setIconSize(QSize(16, 16))
        self.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.addWidget(self._label(T("toolbar_mode")))
        self.mode_combo = QComboBox()
        self._update_mode_items()
        self.mode_combo.setMinimumWidth(100)
        self.mode_combo.currentIndexChanged.connect(lambda index: self.mode_changed.emit(MouseMode(index)))
        self.addWidget(self.mode_combo)
        self.addSeparator()
        self.addAction(self._act(T("toolbar_reset"), self.reset_view_clicked, None, QStyle.SP_BrowserReload))
        self.addAction(self._act(T("toolbar_fit"), self.fit_view_clicked, None, QStyle.SP_ArrowUp))
        self.addSeparator()
        self.addAction(self._act(T("toolbar_prev"), self.prev_file_clicked, None, QStyle.SP_ArrowLeft))
        self.addAction(self._act(T("toolbar_next"), self.next_file_clicked, None, QStyle.SP_ArrowRight))
        self.addSeparator()
        self.addWidget(self._label("编辑线段"))
        self.line_combo = QComboBox()
        self.line_combo.setMinimumWidth(130)
        self.line_combo.currentIndexChanged.connect(lambda _: self.line_selected.emit(self.line_combo.currentData() or ""))
        self.addWidget(self.line_combo)
        self.draw_line_action = self._act("绘制线段", self.draw_line_requested, None, QStyle.SP_FileDialogDetailedView)
        self.addAction(self.draw_line_action)

    def _update_mode_items(self):
        self.mode_combo.blockSignals(True)
        current = self.mode_combo.currentIndex()
        self.mode_combo.clear()
        self.mode_combo.addItems([T("mode_navigate"), T("mode_select_noise"), T("mode_draw_bottom"), T("mode_inspect"), T("mode_pan")])
        self.mode_combo.setCurrentIndex(current if current >= 0 else 0)
        self.mode_combo.blockSignals(False)

    def retranslate_ui(self):
        self._update_mode_items()

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

    def _act(self, text, signal, shortcut=None, icon_standard=None):
        action = QAction(text, self)
        if shortcut:
            action.setShortcut(shortcut)
        if icon_standard is not None:
            action.setIcon(self.style().standardIcon(icon_standard))
        action.triggered.connect(signal)
        return action

    @staticmethod
    def _label(text):
        label = QLabel(text)
        label.setStyleSheet("color: #8a8a92; font-size: 11px;")
        return label
