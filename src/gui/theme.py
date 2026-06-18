"""Echogram GUI 深色主题 — 专业声学软件风格"""

DARK_THEME = """
QMainWindow, QWidget {
    background-color: #1a1a2e;
    color: #e0e0e0;
    font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
    font-size: 12px;
}
QMenuBar {
    background-color: #16213e;
    color: #e0e0e0;
    border-bottom: 1px solid #0f3460;
    padding: 2px;
}
QMenuBar::item:selected {
    background-color: #0f3460;
    border-radius: 4px;
}
QMenu {
    background-color: #16213e;
    color: #e0e0e0;
    border: 1px solid #0f3460;
    border-radius: 4px;
    padding: 4px;
}
QMenu::item:selected {
    background-color: #0f3460;
}
QMenu::separator {
    height: 1px;
    background: #0f3460;
    margin: 4px 8px;
}
QToolBar {
    background-color: #16213e;
    border-bottom: 1px solid #0f3460;
    padding: 4px;
    spacing: 4px;
}
QToolBar QToolButton {
    background-color: #1a1a2e;
    color: #e0e0e0;
    border: 1px solid #0f3460;
    border-radius: 4px;
    padding: 4px 10px;
    margin: 1px;
}
QToolBar QToolButton:hover {
    background-color: #0f3460;
    border-color: #533483;
}
QToolBar QToolButton:pressed {
    background-color: #533483;
}
QComboBox {
    background-color: #1a1a2e;
    color: #e0e0e0;
    border: 1px solid #0f3460;
    border-radius: 4px;
    padding: 4px 8px;
    min-width: 60px;
}
QComboBox:hover {
    border-color: #533483;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox QAbstractItemView {
    background-color: #16213e;
    color: #e0e0e0;
    selection-background-color: #0f3460;
    border: 1px solid #0f3460;
}
QSlider::groove:horizontal {
    height: 4px;
    background: #0f3460;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #533483;
    border: 1px solid #e94560;
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}
QSlider::handle:horizontal:hover {
    background: #e94560;
}
QLabel {
    color: #c0c0c0;
    padding: 1px;
}
QTreeView, QListView, QListWidget {
    background-color: #1a1a2e;
    color: #e0e0e0;
    border: 1px solid #0f3460;
    border-radius: 4px;
    outline: none;
}
QTreeView::item, QListWidget::item {
    padding: 3px 6px;
    border-radius: 3px;
}
QTreeView::item:selected, QListWidget::item:selected {
    background-color: #0f3460;
    color: #ffffff;
}
QTreeView::item:hover, QListWidget::item:hover {
    background-color: #16213e;
}
QHeaderView::section {
    background-color: #16213e;
    color: #e0e0e0;
    border: 1px solid #0f3460;
    padding: 4px;
}
QTableWidget {
    background-color: #1a1a2e;
    color: #e0e0e0;
    gridline-color: #0f3460;
    border: 1px solid #0f3460;
    border-radius: 4px;
}
QTableWidget::item {
    padding: 2px 4px;
}
QTableWidget::item:selected {
    background-color: #0f3460;
}
QGroupBox {
    color: #e94560;
    border: 1px solid #0f3460;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 14px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}
QSpinBox, QDoubleSpinBox {
    background-color: #1a1a2e;
    color: #e0e0e0;
    border: 1px solid #0f3460;
    border-radius: 4px;
    padding: 3px 6px;
}
QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #533483;
}
QPushButton {
    background-color: #0f3460;
    color: #e0e0e0;
    border: 1px solid #533483;
    border-radius: 4px;
    padding: 5px 14px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #533483;
    border-color: #e94560;
}
QPushButton:pressed {
    background-color: #e94560;
}
QSplitter::handle {
    background-color: #0f3460;
}
QSplitter::handle:horizontal {
    width: 3px;
}
QSplitter::handle:vertical {
    height: 3px;
}
QTabWidget::pane {
    border: 1px solid #0f3460;
    border-radius: 4px;
    background-color: #1a1a2e;
}
QTabBar::tab {
    background-color: #16213e;
    color: #c0c0c0;
    border: 1px solid #0f3460;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    padding: 6px 14px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background-color: #1a1a2e;
    color: #e94560;
    border-bottom: 2px solid #e94560;
}
QScrollBar:vertical {
    background: #1a1a2e;
    width: 10px;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background: #0f3460;
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: #533483;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background: #1a1a2e;
    height: 10px;
    border-radius: 5px;
}
QScrollBar::handle:horizontal {
    background: #0f3460;
    border-radius: 5px;
    min-width: 30px;
}
QScrollBar::handle:horizontal:hover {
    background: #533483;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}
QStatusBar {
    background-color: #16213e;
    color: #c0c0c0;
    border-top: 1px solid #0f3460;
}
QStatusBar QLabel {
    color: #c0c0c0;
    padding: 0 6px;
}
QProgressBar {
    background-color: #1a1a2e;
    border: 1px solid #0f3460;
    border-radius: 4px;
    text-align: center;
    color: #e0e0e0;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #533483, stop:1 #e94560);
    border-radius: 3px;
}
QToolTip {
    background-color: #16213e;
    color: #e0e0e0;
    border: 1px solid #e94560;
    border-radius: 4px;
    padding: 4px;
}
"""
