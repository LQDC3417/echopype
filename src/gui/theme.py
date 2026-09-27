"""Echogram GUI 浅色科学仪器主题 — ESP3 / MATLAB 工作台气质

Token 真源见 DESIGN.md §3a（v2 浅色仪器风）。
- 应用底 #E8EAED，面板 #F5F6F7，输入/表 #FFFFFF
- 强调 #0B6E99（科学蓝），选中浅底 #E3F2F8
- 不要在 handler 里散落 hex；改色只改这里。
"""

# 非 QSS 绘制（SVG / 色标）共用主题颜色。
CHROME_COLORS = {
    "panel": "#F5F6F7",
    "border": "#C5CAD0",
    "text": "#1F2933",
    "secondary": "#5C6773",
    "disabled": "#9AA3AD",
    "accent": "#0B6E99",
}

# 主样式表（Qt Widgets QSS）
APP_STYLESHEET = """
/* ═══════════════════════════════════════════════════════════
   浅色科学仪器主题
   ═══════════════════════════════════════════════════════════ */

QMainWindow, QWidget {
    background-color: #E8EAED;
    color: #1F2933;
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Noto Sans CJK SC", "Segoe UI", sans-serif;
    font-size: 12px;
}

/* ── 菜单栏 ── */
QMenuBar {
    background-color: #F5F6F7;
    color: #1F2933;
    border-bottom: 1px solid #C5CAD0;
    padding: 2px;
    spacing: 2px;
}
QMenuBar::item {
    padding: 4px 10px;
    border-radius: 3px;
}
QMenuBar::item:selected {
    background-color: #DDE2E7;
    color: #0B6E99;
}
QMenuBar::item:pressed {
    background-color: #DDE2E7;
}

QMenu {
    background-color: #FFFFFF;
    color: #1F2933;
    border: 1px solid #C5CAD0;
    border-radius: 4px;
    padding: 4px;
}
QMenu::item {
    padding: 5px 24px 5px 12px;
    border-radius: 3px;
}
QMenu::item:selected {
    background-color: #E3F2F8;
    color: #0B6E99;
}
QMenu::separator {
    height: 1px;
    background: #C5CAD0;
    margin: 4px 8px;
}
QMenu::item:disabled {
    color: #9AA3AD;
}

/* ── 工具栏 ── */
QToolBar {
    background-color: #F5F6F7;
    border-bottom: 1px solid #C5CAD0;
    padding: 4px 8px;
    spacing: 4px;
}
QToolBar QToolButton {
    background-color: transparent;
    color: #1F2933;
    border: 1px solid transparent;
    border-radius: 4px;
    min-width: 28px;
    min-height: 28px;
    padding: 3px;
    margin: 0;
    font-size: 12px;
}
QToolBar QToolButton:hover {
    background-color: #FFFFFF;
    border-color: #0B6E99;
}
QToolBar QToolButton:focus {
    border-color: #0B6E99;
    background-color: #E3F2F8;
}
QToolBar QToolButton:pressed {
    background-color: #DDE2E7;
}
QToolBar QToolButton:checked {
    background-color: #E3F2F8;
    color: #0B6E99;
    border-color: #0B6E99;
}
QToolBar::separator {
    width: 1px;
    background: #C5CAD0;
    margin: 5px 6px;
}

/* ── 下拉框 ── */
QComboBox {
    background-color: #FFFFFF;
    color: #1F2933;
    border: 1px solid #C5CAD0;
    border-radius: 3px;
    padding: 4px 8px;
    min-width: 70px;
}
QComboBox:hover {
    border-color: #0B6E99;
}
QComboBox:focus {
    border-color: #0B6E99;
    outline: none;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox QAbstractItemView {
    background-color: #FFFFFF;
    color: #1F2933;
    selection-background-color: #E3F2F8;
    selection-color: #0B6E99;
    border: 1px solid #C5CAD0;
    border-radius: 3px;
    outline: none;
}

/* ── 滑块 ── */
QSlider::groove:horizontal {
    height: 4px;
    background: #C5CAD0;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #0B6E99;
    border: none;
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}
QSlider::handle:horizontal:hover {
    background: #0E8AB8;
}

/* ── 标签 ── */
QLabel {
    color: #1F2933;
    padding: 1px;
    background: transparent;
}

/* ── 树视图 / 列表 ── */
QTreeView, QListView, QListWidget {
    background-color: #FFFFFF;
    color: #1F2933;
    border: 1px solid #C5CAD0;
    border-radius: 3px;
    outline: none;
    alternate-background-color: #F5F6F7;
}
QTreeView::item, QListWidget::item {
    padding: 4px 6px;
    border-radius: 2px;
}
QTreeView::item:selected, QListWidget::item:selected {
    background-color: #E3F2F8;
    color: #0B6E99;
}
QTreeView::item:hover, QListWidget::item:hover {
    background-color: #EEF1F4;
}

/* ── 表头 ── */
QHeaderView::section {
    background-color: #F5F6F7;
    color: #5C6773;
    border: none;
    border-right: 1px solid #C5CAD0;
    border-bottom: 1px solid #C5CAD0;
    padding: 5px 8px;
    font-weight: normal;
}

/* ── 表格 ── */
QTableWidget {
    background-color: #FFFFFF;
    color: #1F2933;
    gridline-color: #E1E5E9;
    border: 1px solid #C5CAD0;
    border-radius: 3px;
}
QTableWidget::item {
    padding: 3px 6px;
}
QTableWidget::item:selected {
    background-color: #E3F2F8;
    color: #0B6E99;
}

/* ── 分组框 ── */
QGroupBox {
    color: #1F2933;
    border: 1px solid #C5CAD0;
    border-radius: 4px;
    margin-top: 8px;
    padding-top: 6px;
    font-weight: bold;
    font-size: 11px;
    background-color: #F5F6F7;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: #5C6773;
}

/* ── 数值输入 ── */
QSpinBox, QDoubleSpinBox {
    background-color: #FFFFFF;
    color: #1F2933;
    border: 1px solid #C5CAD0;
    border-radius: 3px;
    padding: 4px 6px;
    selection-background-color: #0B6E99;
    selection-color: #FFFFFF;
}
QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #0B6E99;
}
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {
    background-color: #F5F6F7;
    border: none;
    width: 16px;
}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: #DDE2E7;
}

/* ── 按钮 ── */
QPushButton {
    background-color: #FFFFFF;
    color: #1F2933;
    border: 1px solid #C5CAD0;
    border-radius: 4px;
    padding: 6px 14px;
    font-weight: normal;
}
QPushButton:hover {
    background-color: #EEF1F4;
    border-color: #0B6E99;
}
QPushButton:pressed {
    background-color: #DDE2E7;
}
QPushButton:disabled {
    background-color: #F0F1F3;
    color: #9AA3AD;
    border-color: #D5D9DE;
}

QPushButton[cssClass="primary"] {
    background-color: #0B6E99;
    color: #FFFFFF;
    border-color: #0B6E99;
    font-weight: bold;
}
QPushButton[cssClass="primary"]:hover {
    background-color: #0E8AB8;
}
QPushButton[cssClass="primary"]:disabled {
    background-color: #B0C4D0;
    border-color: #B0C4D0;
    color: #F5F6F7;
}

QPushButton[cssClass="danger"] {
    background-color: #B42318;
    color: #FFFFFF;
    border-color: #B42318;
}
QPushButton[cssClass="danger"]:hover {
    background-color: #D92D20;
}

/* ── 欢迎页 ── */
QDialog#welcomeDialog {
    background-color: #E8EAED;
}
QFrame#welcomeCard {
    background-color: #FFFFFF;
    border: 1px solid #C5CAD0;
    border-radius: 6px;
}
QLabel#welcomeTitle {
    color: #1F2933;
    font-size: 16px;
    font-weight: 600;
}
QLabel#welcomeSubtitle, QLabel#recentProjectsTitle {
    color: #5C6773;
}
QLabel#recentProjectsTitle {
    margin-top: 4px;
    font-weight: 600;
}
QPushButton#importRawButton, QPushButton#openProjectButton {
    min-height: 30px;
}
QListWidget#recentProjects {
    border-color: #C5CAD0;
    border-radius: 3px;
}
QLabel#projectSummary {
    color: #1F2933;
    font-weight: 600;
}
QListWidget#viewList {
    border: none;
    border-radius: 0;
    background-color: transparent;
}
QListWidget#viewList::item:selected {
    background-color: #E3F2F8;
    color: #0B6E99;
    border-left: 2px solid #0B6E99;
}

/* ── 分割器 ── */
QSplitter::handle {
    background-color: #C5CAD0;
}
QSplitter::handle:horizontal {
    width: 2px;
}
QSplitter::handle:vertical {
    height: 2px;
}
QSplitter::handle:hover {
    background-color: #0B6E99;
}

/* ── 标签页 ── */
QTabWidget::pane {
    border: 1px solid #C5CAD0;
    border-radius: 0;
    background-color: #F5F6F7;
    top: -1px;
}
QTabBar::tab {
    background-color: #E8EAED;
    color: #5C6773;
    border: 1px solid #C5CAD0;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    padding: 6px 14px;
    margin-right: 2px;
    font-size: 11px;
}
QTabBar::tab:selected {
    background-color: #F5F6F7;
    color: #0B6E99;
    border-bottom: 2px solid #0B6E99;
}
QTabBar::tab:hover:!selected {
    background-color: #DDE2E7;
    color: #1F2933;
}
QTabWidget#propertyTaskTabs QTabBar::tab {
    padding: 7px 8px;
    margin-right: 0;
    border-radius: 0;
}
QTabWidget#propertyTaskTabs QTabBar::tab:selected {
    font-weight: bold;
}

/* ── 滚动条 ── */
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    border-radius: 4px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #C5CAD0;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: #9AA3AD;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}

QScrollBar:horizontal {
    background: transparent;
    height: 10px;
    border-radius: 4px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: #C5CAD0;
    border-radius: 4px;
    min-width: 30px;
}
QScrollBar::handle:horizontal:hover {
    background: #9AA3AD;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
}

/* ── 状态栏 ── */
QStatusBar {
    background-color: #F5F6F7;
    color: #5C6773;
    border-top: 1px solid #C5CAD0;
    font-size: 11px;
}
QStatusBar QLabel {
    color: #5C6773;
    padding: 0 8px;
}
QStatusBar::item {
    border: none;
}

/* ── 进度条 ── */
QProgressBar {
    background-color: #DDE2E7;
    border: 1px solid #C5CAD0;
    border-radius: 3px;
    text-align: center;
    color: #1F2933;
    font-size: 10px;
}
QProgressBar::chunk {
    background: #0B6E99;
    border-radius: 2px;
}

/* ── 提示框 ── */
QToolTip {
    background-color: #1F2933;
    color: #F5F6F7;
    border: 1px solid #1F2933;
    border-radius: 3px;
    padding: 6px;
    font-size: 11px;
}

/* ── 对话框 ── */
QDialog {
    background-color: #E8EAED;
}

QMessageBox {
    background-color: #F5F6F7;
}
QMessageBox QLabel {
    color: #1F2933;
}
QMessageBox QPushButton {
    min-width: 80px;
}

/* ── 输入框 ── */
QLineEdit {
    background-color: #FFFFFF;
    color: #1F2933;
    border: 1px solid #C5CAD0;
    border-radius: 3px;
    padding: 5px 8px;
    selection-background-color: #0B6E99;
    selection-color: #FFFFFF;
}
QLineEdit:focus {
    border-color: #0B6E99;
}

/* ── 复选框 / 单选 ── */
QCheckBox, QRadioButton {
    color: #1F2933;
    spacing: 6px;
}
QCheckBox::indicator, QRadioButton::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #9AA3AD;
    background-color: #FFFFFF;
}
QCheckBox::indicator {
    border-radius: 3px;
}
QRadioButton::indicator {
    border-radius: 8px;
}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background-color: #0B6E99;
    border-color: #0B6E99;
}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {
    border-color: #0B6E99;
}

/* ── 停靠窗口 ── */
QDockWidget {
    color: #1F2933;
    font-size: 11px;
    font-weight: bold;
    titlebar-close-icon: none;
}
QDockWidget::title {
    background-color: #F5F6F7;
    color: #5C6773;
    padding: 4px 8px;
    border-bottom: 1px solid #C5CAD0;
    text-align: left;
}
QDockWidget::close-button, QDockWidget::float-button {
    border: none;
    background: transparent;
    padding: 2px;
}
QDockWidget::close-button:hover, QDockWidget::float-button:hover {
    background: #DDE2E7;
    border-radius: 3px;
}

QWhatsThis {
    background-color: #FFFFFF;
    color: #1F2933;
    border: 1px solid #C5CAD0;
}

/* ── 工作台：Layer 树（ESP3）── */
QLabel#surveyStatus { color: #5C6773; font-size: 11px; }
QListWidget#surveyFiles {
    border-radius: 3px;
    font-size: 11px;
    background: #FFFFFF;
    border: 1px solid #C5CAD0;
}
QListWidget#layerTree {
    border: 1px solid #C5CAD0;
    border-radius: 3px;
    background: #FFFFFF;
    font-size: 11px;
}
QListWidget#layerTree::item {
    padding: 3px 6px;
}
QListWidget#layerTree::item:selected {
    background: #E3F2F8;
    color: #0B6E99;
}
QLabel#fileMetaHint {
    color: #5C6773;
    font-size: 10px;
}
/* 旧 survey 步骤钮：降为 ghost，不再像 CTA */
QPushButton#survey_import, QPushButton#survey_quality,
QPushButton#survey_region, QPushButton#survey_integration,
QPushButton#survey_save {
    text-align: left;
    padding: 5px 10px;
    border-radius: 3px;
    background: transparent;
    border: 1px solid #C5CAD0;
    color: #1F2933;
}
QPushButton#survey_metadata {
    text-align: left;
    padding: 5px 10px;
}
QPushButton#survey_import:hover, QPushButton#survey_quality:hover,
QPushButton#survey_region:hover, QPushButton#survey_integration:hover,
QPushButton#survey_save:hover {
    border-color: #0B6E99;
    background: #EEF1F4;
}
QPushButton#survey_import:disabled, QPushButton#survey_quality:disabled,
QPushButton#survey_region:disabled, QPushButton#survey_integration:disabled,
QPushButton#survey_save:disabled {
    color: #9AA3AD;
    border-color: #D5D9DE;
    background: #F0F1F3;
}
"""

# 对外真源：当前为浅色仪器主题
LIGHT_THEME = APP_STYLESHEET
# 兼容旧导入名（app.py / 历史代码）
DARK_THEME = APP_STYLESHEET

# OpenGL 绘图区清屏色（RGB 0–1），与 --bg-plot #FFFFFF 一致
PLOT_CLEAR_RGB = (1.0, 1.0, 1.0)
