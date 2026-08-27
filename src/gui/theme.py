"""Echogram GUI 深色主题 — 专业声学软件风格（参照 Echoview 16）

设计方向：深色沉浸式、专业、高对比度。
色彩体系：深灰黑底 + 青绿强调 + 浅灰文字。
- 背景：深灰黑 #1e1e22（主窗口）/ #26262c（面板）
- 强调：青绿 #00b4d8（主按钮/选中/hover/焦点/进度条）
- 文字：主 #e0e0e6 / 次 #8a8a92 / 禁用 #5a5a62
"""

DARK_THEME = """
/* ═══════════════════════════════════════════════════════════
   深色主题
   ═══════════════════════════════════════════════════════════ */

QMainWindow, QWidget {
    background-color: #15191e;
    color: #e0e0e6;
    font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
    font-size: 12px;
}

/* ── 菜单栏 ── */
QMenuBar {
    background-color: #26262c;
    color: #e0e0e6;
    border-bottom: 1px solid #3a3a42;
    padding: 2px;
    spacing: 2px;
}
QMenuBar::item {
    padding: 4px 10px;
    border-radius: 4px;
}
QMenuBar::item:selected {
    background-color: #2d2d35;
    color: #00b4d8;
}
QMenuBar::item:pressed {
    background-color: #383842;
}

QMenu {
    background-color: #26262c;
    color: #e0e0e6;
    border: 1px solid #3a3a42;
    border-radius: 6px;
    padding: 4px;
}
QMenu::item {
    padding: 6px 24px 6px 12px;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #2d2d35;
    color: #00b4d8;
}
QMenu::separator {
    height: 1px;
    background: #3a3a42;
    margin: 4px 8px;
}
QMenu::item:disabled {
    color: #5a5a62;
}

/* ── 工具栏 ── */
QToolBar {
    background-color: #15191e;
    border-bottom: 1px solid #34414d;
    padding: 5px 8px;
    spacing: 4px;
}
QToolBar QToolButton {
    background-color: transparent;
    color: #e0e0e6;
    border: 1px solid #34414d;
    border-radius: 5px;
    min-width: 28px;
    min-height: 28px;
    padding: 3px;
    margin: 0;
    font-size: 12px;
}
QToolBar QToolButton:hover {
    background-color: #222b34;
    border-color: #00cbea;
}
QToolBar QToolButton:pressed {
    background-color: #293641;
}
QToolBar QToolButton:checked {
    background-color: #113743;
    color: #00cbea;
    border-color: #00cbea;
}
QToolBar::separator {
    width: 1px;
    background: #34414d;
    margin: 5px 6px;
}

/* ── 下拉框 ── */
QComboBox {
    background-color: #26262c;
    color: #e0e0e6;
    border: 1px solid #3a3a42;
    border-radius: 4px;
    padding: 4px 8px;
    min-width: 70px;
}
QComboBox:hover {
    border-color: #00b4d8;
}
QComboBox:focus {
    border-color: #00b4d8;
    outline: none;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox QAbstractItemView {
    background-color: #26262c;
    color: #e0e0e6;
    selection-background-color: #2d2d35;
    selection-color: #00b4d8;
    border: 1px solid #3a3a42;
    border-radius: 4px;
    outline: none;
}

/* ── 滑块 ── */
QSlider::groove:horizontal {
    height: 4px;
    background: #3a3a42;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #00b4d8;
    border: none;
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}
QSlider::handle:horizontal:hover {
    background: #33c5e1;
}

/* ── 标签 ── */
QLabel {
    color: #e0e0e6;
    padding: 1px;
}

/* ── 树视图 / 列表 ── */
QTreeView, QListView, QListWidget {
    background-color: #26262c;
    color: #e0e0e6;
    border: 1px solid #3a3a42;
    border-radius: 6px;
    outline: none;
    alternate-background-color: #222226;
}
QTreeView::item, QListWidget::item {
    padding: 4px 6px;
    border-radius: 4px;
}
QTreeView::item:selected, QListWidget::item:selected {
    background-color: #2d2d35;
    color: #00b4d8;
}
QTreeView::item:hover, QListWidget::item:hover {
    background-color: #2a2a30;
}

/* ── 表头 ── */
QHeaderView::section {
    background-color: #2a2a30;
    color: #8a8a92;
    border: none;
    border-right: 1px solid #3a3a42;
    border-bottom: 1px solid #3a3a42;
    padding: 5px 8px;
    font-weight: normal;
}

/* ── 表格 ── */
QTableWidget {
    background-color: #26262c;
    color: #e0e0e6;
    gridline-color: #33333b;
    border: 1px solid #3a3a42;
    border-radius: 6px;
}
QTableWidget::item {
    padding: 3px 6px;
}
QTableWidget::item:selected {
    background-color: #2d2d35;
    color: #00b4d8;
}

/* ── 分组框 ── */
QGroupBox {
    color: #cdd8e1;
    border: 1px solid #34414d;
    border-radius: 6px;
    margin-top: 8px;
    padding-top: 16px;
    font-weight: bold;
    font-size: 11px;
    background-color: #1b2128;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: #8fa2b1;
}

/* ── 数值输入 ── */
QSpinBox, QDoubleSpinBox {
    background-color: #26262c;
    color: #e0e0e6;
    border: 1px solid #3a3a42;
    border-radius: 4px;
    padding: 4px 6px;
    selection-background-color: #00b4d8;
    selection-color: #06262a;
}
QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #00b4d8;
}
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {
    background-color: #2a2a30;
    border: none;
    width: 16px;
}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: #383842;
}

/* ── 按钮 ── */
QPushButton {
    background-color: #26262c;
    color: #e0e0e6;
    border: 1px solid #3a3a42;
    border-radius: 5px;
    padding: 6px 14px;
    font-weight: normal;
}
QPushButton:hover {
    background-color: #2d2d35;
    border-color: #00b4d8;
}
QPushButton:pressed {
    background-color: #383842;
}
QPushButton:disabled {
    background-color: #1e1e22;
    color: #5a5a62;
    border-color: #33333b;
}

/* 主要操作按钮（青绿强调） */
QPushButton[cssClass="primary"] {
    background-color: #00b4d8;
    color: #06262a;
    border-color: #00b4d8;
    font-weight: bold;
}
QPushButton[cssClass="primary"]:hover {
    background-color: #33c5e1;
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
    background-color: #3a3a42;
}
QSplitter::handle:horizontal {
    width: 2px;
}
QSplitter::handle:vertical {
    height: 2px;
}
QSplitter::handle:hover {
    background-color: #00b4d8;
}

/* ── 标签页 ── */
QTabWidget::pane {
    border: none;
    border-radius: 0;
    background-color: #15191e;
    top: -1px;
}
QTabBar::tab {
    background-color: #15191e;
    color: #8fa2b1;
    border: 1px solid #34414d;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 7px 16px;
    margin-right: 2px;
    font-size: 11px;
}
QTabBar::tab:selected {
    background-color: #1b2128;
    color: #d7e1e8;
    border-bottom: 2px solid #00cbea;
}
QTabBar::tab:hover:!selected {
    background-color: #2d2d35;
    color: #e0e0e6;
}

/* ── 滚动条 ── */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    border-radius: 4px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #3a3a42;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: #4a4a54;
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
    background: #3a3a42;
    border-radius: 4px;
    min-width: 30px;
}
QScrollBar::handle:horizontal:hover {
    background: #4a4a54;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
}

/* ── 状态栏 ── */
QStatusBar {
    background-color: #26262c;
    color: #8a8a92;
    border-top: 1px solid #3a3a42;
    font-size: 11px;
}
QStatusBar QLabel {
    color: #8a8a92;
    padding: 0 8px;
}
QStatusBar::item {
    border: none;
}

/* ── 进度条 ── */
QProgressBar {
    background-color: #33333b;
    border: none;
    border-radius: 4px;
    text-align: center;
    color: #e0e0e6;
    font-size: 10px;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #00b4d8, stop:1 #33c5e1);
    border-radius: 4px;
}

/* ── 提示框 ── */
QToolTip {
    background-color: #26262c;
    color: #e0e0e6;
    border: 1px solid #3a3a42;
    border-radius: 4px;
    padding: 6px;
    font-size: 11px;
}

/* ── 对话框 ── */
QDialog {
    background-color: #1e1e22;
}

QMessageBox {
    background-color: #26262c;
}
QMessageBox QLabel {
    color: #e0e0e6;
}
QMessageBox QPushButton {
    min-width: 80px;
}

/* ── 输入框 ── */
QLineEdit {
    background-color: #26262c;
    color: #e0e0e6;
    border: 1px solid #3a3a42;
    border-radius: 4px;
    padding: 5px 8px;
    selection-background-color: #00b4d8;
    selection-color: #06262a;
}
QLineEdit:focus {
    border-color: #00b4d8;
}

/* ── 复选框 ── */
QCheckBox {
    color: #e0e0e6;
    spacing: 6px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #3a3a42;
    border-radius: 3px;
    background-color: #26262c;
}
QCheckBox::indicator:checked {
    background-color: #00b4d8;
    border-color: #00b4d8;
}
QCheckBox::indicator:hover {
    border-color: #00b4d8;
}

/* ── 单选按钮 ── */
QRadioButton {
    color: #e0e0e6;
    spacing: 6px;
}
QRadioButton::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #3a3a42;
    border-radius: 8px;
    background-color: #26262c;
}
QRadioButton::indicator:checked {
    background-color: #00b4d8;
    border-color: #00b4d8;
}
QRadioButton::indicator:hover {
    border-color: #00b4d8;
}

/* ── 停靠窗口（Echoview 紧凑风格）── */
QDockWidget {
    color: #e0e0e6;
    font-size: 11px;
    font-weight: bold;
    titlebar-close-icon: none;
}
QDockWidget::title {
    background-color: #15191e;
    color: #8fa2b1;
    padding: 4px 8px;
    border-bottom: 1px solid #3a3a42;
    text-align: left;
}
QDockWidget::close-button, QDockWidget::float-button {
    border: none;
    background: transparent;
    padding: 2px;
    color: #8a8a92;
}
QDockWidget::close-button:hover, QDockWidget::float-button:hover {
    background: #383842;
    border-radius: 3px;
}

/* ── 工具提示区域 ── */
QWhatsThis {
    background-color: #26262c;
    color: #e0e0e6;
    border: 1px solid #3a3a42;
}
"""

# 保留 LIGHT_THEME 引用兼容旧代码
LIGHT_THEME = DARK_THEME
