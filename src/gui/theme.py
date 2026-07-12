"""Echogram GUI 蓝白色主题 — 专业声学软件风格

设计方向：清爽、专业、高对比度。
色彩体系：白色底 + 深蓝强调 + 浅蓝辅助 + 深灰文字。
"""

LIGHT_THEME = """
/* ═══════════════════════════════════════════════════════════
   蓝白色主题
   ═══════════════════════════════════════════════════════════ */

QMainWindow, QWidget {
    background-color: #f5f7fa;
    color: #2c3e50;
    font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
    font-size: 12px;
}

/* ── 菜单栏 ── */
QMenuBar {
    background-color: #ffffff;
    color: #2c3e50;
    border-bottom: 1px solid #dce4ec;
    padding: 2px;
    spacing: 2px;
}
QMenuBar::item {
    padding: 4px 10px;
    border-radius: 4px;
}
QMenuBar::item:selected {
    background-color: #e8f0fe;
    color: #1a73e8;
}
QMenuBar::item:pressed {
    background-color: #d2e3fc;
}

QMenu {
    background-color: #ffffff;
    color: #2c3e50;
    border: 1px solid #dce4ec;
    border-radius: 6px;
    padding: 4px;
}
QMenu::item {
    padding: 6px 24px 6px 12px;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #e8f0fe;
    color: #1a73e8;
}
QMenu::separator {
    height: 1px;
    background: #dce4ec;
    margin: 4px 8px;
}
QMenu::item:disabled {
    color: #a0aec0;
}

/* ── 工具栏 ── */
QToolBar {
    background-color: #ffffff;
    border-bottom: 1px solid #dce4ec;
    padding: 3px;
    spacing: 2px;
}
QToolBar QToolButton {
    background-color: transparent;
    color: #2c3e50;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 4px 10px;
    margin: 1px;
    font-size: 12px;
}
QToolBar QToolButton:hover {
    background-color: #e8f0fe;
    border-color: #d2e3fc;
}
QToolBar QToolButton:pressed {
    background-color: #d2e3fc;
}
QToolBar QToolButton:checked {
    background-color: #1a73e8;
    color: #ffffff;
    border-color: #1a73e8;
}
QToolBar::separator {
    width: 1px;
    background: #dce4ec;
    margin: 4px 4px;
}

/* ── 下拉框 ── */
QComboBox {
    background-color: #ffffff;
    color: #2c3e50;
    border: 1px solid #dce4ec;
    border-radius: 4px;
    padding: 4px 8px;
    min-width: 70px;
}
QComboBox:hover {
    border-color: #1a73e8;
}
QComboBox:focus {
    border-color: #1a73e8;
    outline: none;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox QAbstractItemView {
    background-color: #ffffff;
    color: #2c3e50;
    selection-background-color: #e8f0fe;
    selection-color: #1a73e8;
    border: 1px solid #dce4ec;
    border-radius: 4px;
    outline: none;
}

/* ── 滑块 ── */
QSlider::groove:horizontal {
    height: 4px;
    background: #dce4ec;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #1a73e8;
    border: none;
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}
QSlider::handle:horizontal:hover {
    background: #4285f4;
}

/* ── 标签 ── */
QLabel {
    color: #4a5568;
    padding: 1px;
}

/* ── 树视图 / 列表 ── */
QTreeView, QListView, QListWidget {
    background-color: #ffffff;
    color: #2c3e50;
    border: 1px solid #dce4ec;
    border-radius: 6px;
    outline: none;
    alternate-background-color: #f8fafc;
}
QTreeView::item, QListWidget::item {
    padding: 4px 6px;
    border-radius: 4px;
}
QTreeView::item:selected, QListWidget::item:selected {
    background-color: #e8f0fe;
    color: #1a73e8;
}
QTreeView::item:hover, QListWidget::item:hover {
    background-color: #f0f4f8;
}

/* ── 表头 ── */
QHeaderView::section {
    background-color: #f0f4f8;
    color: #4a5568;
    border: none;
    border-right: 1px solid #dce4ec;
    border-bottom: 1px solid #dce4ec;
    padding: 5px 8px;
    font-weight: normal;
}

/* ── 表格 ── */
QTableWidget {
    background-color: #ffffff;
    color: #2c3e50;
    gridline-color: #e8ecf0;
    border: 1px solid #dce4ec;
    border-radius: 6px;
}
QTableWidget::item {
    padding: 3px 6px;
}
QTableWidget::item:selected {
    background-color: #e8f0fe;
    color: #1a73e8;
}

/* ── 分组框 ── */
QGroupBox {
    color: #1a73e8;
    border: 1px solid #dce4ec;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 16px;
    font-weight: bold;
    font-size: 11px;
    background-color: #ffffff;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: #1a73e8;
}

/* ── 数值输入 ── */
QSpinBox, QDoubleSpinBox {
    background-color: #ffffff;
    color: #2c3e50;
    border: 1px solid #dce4ec;
    border-radius: 4px;
    padding: 4px 6px;
    selection-background-color: #1a73e8;
    selection-color: #ffffff;
}
QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #1a73e8;
}
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {
    background-color: #f0f4f8;
    border: none;
    width: 16px;
}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: #d2e3fc;
}

/* ── 按钮 ── */
QPushButton {
    background-color: #ffffff;
    color: #2c3e50;
    border: 1px solid #dce4ec;
    border-radius: 5px;
    padding: 6px 14px;
    font-weight: normal;
}
QPushButton:hover {
    background-color: #e8f0fe;
    border-color: #1a73e8;
}
QPushButton:pressed {
    background-color: #d2e3fc;
}
QPushButton:disabled {
    background-color: #f5f7fa;
    color: #a0aec0;
    border-color: #e8ecf0;
}

/* 主要操作按钮（蓝色强调） */
QPushButton[cssClass="primary"] {
    background-color: #1a73e8;
    color: #ffffff;
    border-color: #1a73e8;
    font-weight: bold;
}
QPushButton[cssClass="primary"]:hover {
    background-color: #4285f4;
}

/* 危险操作按钮 */
QPushButton[cssClass="danger"] {
    background-color: #e53e3e;
    color: #ffffff;
    border-color: #e53e3e;
}
QPushButton[cssClass="danger"]:hover {
    background-color: #fc8181;
}

/* ── 分割器 ── */
QSplitter::handle {
    background-color: #dce4ec;
}
QSplitter::handle:horizontal {
    width: 2px;
}
QSplitter::handle:vertical {
    height: 2px;
}
QSplitter::handle:hover {
    background-color: #1a73e8;
}

/* ── 标签页 ── */
QTabWidget::pane {
    border: 1px solid #dce4ec;
    border-radius: 6px;
    background-color: #ffffff;
    top: -1px;
}
QTabBar::tab {
    background-color: #f0f4f8;
    color: #4a5568;
    border: 1px solid #dce4ec;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 6px 16px;
    margin-right: 2px;
    font-size: 11px;
}
QTabBar::tab:selected {
    background-color: #ffffff;
    color: #1a73e8;
    border-bottom: 2px solid #1a73e8;
}
QTabBar::tab:hover:!selected {
    background-color: #e8f0fe;
    color: #2c3e50;
}

/* ── 滚动条 ── */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    border-radius: 4px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #c4cdd5;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: #a0aec0;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}

QScrollBar:horizontal {
    background: transparent;
    height: 8px;
    border-radius: 4px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: #c4cdd5;
    border-radius: 4px;
    min-width: 30px;
}
QScrollBar::handle:horizontal:hover {
    background: #a0aec0;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
}

/* ── 状态栏 ── */
QStatusBar {
    background-color: #ffffff;
    color: #4a5568;
    border-top: 1px solid #dce4ec;
    font-size: 11px;
}
QStatusBar QLabel {
    color: #4a5568;
    padding: 0 8px;
}
QStatusBar::item {
    border: none;
}

/* ── 进度条 ── */
QProgressBar {
    background-color: #e8ecf0;
    border: none;
    border-radius: 4px;
    text-align: center;
    color: #2c3e50;
    font-size: 10px;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #1a73e8, stop:1 #4285f4);
    border-radius: 4px;
}

/* ── 提示框 ── */
QToolTip {
    background-color: #ffffff;
    color: #2c3e50;
    border: 1px solid #dce4ec;
    border-radius: 4px;
    padding: 6px;
    font-size: 11px;
}

/* ── 对话框 ── */
QDialog {
    background-color: #f5f7fa;
}

QMessageBox {
    background-color: #ffffff;
}
QMessageBox QLabel {
    color: #2c3e50;
}
QMessageBox QPushButton {
    min-width: 80px;
}

/* ── 输入框 ── */
QLineEdit {
    background-color: #ffffff;
    color: #2c3e50;
    border: 1px solid #dce4ec;
    border-radius: 4px;
    padding: 5px 8px;
    selection-background-color: #1a73e8;
    selection-color: #ffffff;
}
QLineEdit:focus {
    border-color: #1a73e8;
}

/* ── 复选框 ── */
QCheckBox {
    color: #2c3e50;
    spacing: 6px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #dce4ec;
    border-radius: 3px;
    background-color: #ffffff;
}
QCheckBox::indicator:checked {
    background-color: #1a73e8;
    border-color: #1a73e8;
}
QCheckBox::indicator:hover {
    border-color: #1a73e8;
}

/* ── 单选按钮 ── */
QRadioButton {
    color: #2c3e50;
    spacing: 6px;
}
QRadioButton::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #dce4ec;
    border-radius: 8px;
    background-color: #ffffff;
}
QRadioButton::indicator:checked {
    background-color: #1a73e8;
    border-color: #1a73e8;
}
QRadioButton::indicator:hover {
    border-color: #1a73e8;
}

/* ── 停靠窗口 ── */
QDockWidget {
    color: #2c3e50;
    titlebar-close-icon: none;
}
QDockWidget::title {
    background-color: #ffffff;
    padding: 6px;
    border-bottom: 1px solid #dce4ec;
    font-weight: bold;
}

/* ── 工具提示区域 ── */
QWhatsThis {
    background-color: #ffffff;
    color: #2c3e50;
    border: 1px solid #dce4ec;
}
"""

# 保留 DARK_THEME 引用以兼容旧代码
DARK_THEME = LIGHT_THEME
