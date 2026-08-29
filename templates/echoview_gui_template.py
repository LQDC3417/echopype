"""Echoview 风格浅色 GUI 视觉模板。

该文件只用于审阅布局和视觉方向，不连接项目现有的数据处理逻辑。
运行：python templates/echoview_gui_template.py
"""

from __future__ import annotations

import math
import sys

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QAction, QColor, QFont, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDockWidget,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)


PALETTE = {
    "window": "#eaf1f8",
    "chrome": "#dce8f3",
    "chrome_dark": "#c6d8e8",
    "border": "#a9bfd2",
    "text": "#1e3448",
    "muted": "#5f7385",
    "active": "#e7f1fb",
    "accent": "#2778b8",
    "success": "#11a86b",
    "warning": "#d99522",
}


def build_stylesheet() -> str:
    """返回模板专用的浅色 Qt 样式。"""
    return f"""
        QWidget {{
            color: {PALETTE['text']};
            font-family: "Arial";
            font-size: 12px;
        }}
        QMainWindow, QDockWidget, QToolBar, QStatusBar {{
            background: {PALETTE['window']};
        }}
        QMenuBar, QToolBar {{
            background: {PALETTE['chrome']};
            border: 0;
        }}
        QMenuBar::item {{ padding: 6px 11px; }}
        QMenuBar::item:selected, QMenu::item:selected {{
            background: {PALETTE['active']};
            color: {PALETTE['accent']};
        }}
        QToolBar {{ padding: 4px 7px; spacing: 4px; border-bottom: 1px solid {PALETTE['border']}; }}
        QToolButton, QPushButton {{
            background: #f8fbfe;
            border: 1px solid {PALETTE['border']};
            border-radius: 3px;
            padding: 5px 9px;
        }}
        QToolButton:hover, QPushButton:hover {{ background: #ffffff; border-color: {PALETTE['accent']}; }}
        QDockWidget {{ titlebar-close-icon: none; border: 1px solid {PALETTE['border']}; }}
        QDockWidget::title {{
            background: {PALETTE['chrome_dark']};
            padding: 6px 8px;
            font-weight: 600;
        }}
        QTabWidget::pane, QTreeWidget, QListWidget, QTableWidget, QComboBox {{
            background: #f9fcff;
            border: 1px solid {PALETTE['border']};
        }}
        QTabBar::tab {{ padding: 6px 12px; background: {PALETTE['chrome']}; border: 1px solid {PALETTE['border']}; }}
        QTabBar::tab:selected {{ background: #f9fcff; color: {PALETTE['accent']}; }}
        QHeaderView::section {{ background: {PALETTE['chrome']}; border: 0; border-right: 1px solid {PALETTE['border']}; padding: 5px; }}
        QStatusBar {{ border-top: 1px solid {PALETTE['border']}; color: {PALETTE['muted']}; }}
    """


class EchogramCanvas(QWidget):
    """绘制用于审阅布局的静态 Echogram。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("echogramCanvas")
        self.setMinimumSize(640, 420)
        self.setAutoFillBackground(True)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.fillRect(self.rect(), QColor("#fdfefe"))

        plot = QRectF(55, 26, max(10, self.width() - 92), max(10, self.height() - 58))
        painter.setPen(QPen(QColor("#9eb6ca"), 1))
        painter.drawRect(plot)

        colors = ["#263b9b", "#087fc3", "#0bb59b", "#f4d43b", "#f38c22", "#ce293c"]
        for row in range(0, 58):
            for col in range(0, 125):
                wave = math.sin(col * 0.21 + row * 0.43) + math.sin(col * 0.09 - row * 0.17)
                signal = abs(wave) + (1.4 if 34 < row < 39 else 0)
                if signal > 1.3:
                    x = plot.left() + col / 125 * plot.width()
                    y = plot.top() + row / 58 * plot.height() * 0.78
                    color = QColor(colors[min(len(colors) - 1, int(signal * 1.8))])
                    painter.fillRect(QRectF(x, y, 4.5, 3.0), color)

        # 鱼群示意区域
        painter.setPen(Qt.NoPen)
        for i in range(26):
            x = plot.left() + 90 + i * 5
            y = plot.top() + 185 + math.sin(i * 0.55) * 14
            painter.fillRect(QRectF(x, y, 18, 5), QColor("#e33245" if i % 3 else "#f3bd2e"))

        # 网格、表线、底线和光标
        painter.setPen(QPen(QColor("#cbd8e3"), 1, Qt.DashLine))
        for fraction in (0.2, 0.4, 0.6, 0.8):
            y = plot.top() + plot.height() * fraction
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
        painter.setPen(QPen(QColor(PALETTE["success"]), 2))
        bottom_y = plot.top() + plot.height() * 0.69
        painter.drawLine(QPointF(plot.left(), bottom_y), QPointF(plot.right(), bottom_y - 4))
        painter.setPen(QPen(QColor("#303b45"), 1, Qt.DashLine))
        cursor_x = plot.left() + plot.width() * 0.57
        painter.drawLine(QPointF(cursor_x, plot.top()), QPointF(cursor_x, plot.bottom()))

        painter.setPen(QColor(PALETTE["muted"]))
        for index, label in enumerate(("0", "20", "40", "60", "80", "100")):
            y = plot.top() + index / 5 * plot.height()
            painter.drawText(QRectF(8, y - 8, 40, 16), Qt.AlignRight | Qt.AlignVCenter, label)
        painter.drawText(QRectF(plot.left(), plot.bottom() + 8, plot.width(), 20), Qt.AlignCenter, "Ping time")
        painter.drawText(QRectF(8, 4, 44, 18), Qt.AlignCenter, "Range (m)")


class ColorScale(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setMinimumWidth(58)

    def paintEvent(self, _event):
        painter = QPainter(self)
        bar = QRectF(12, 30, 16, max(20, self.height() - 58))
        gradient = QLinearGradient(0, bar.bottom(), 0, bar.top())
        for stop, color in ((0.0, "#27358f"), (0.25, "#0b99c2"), (0.5, "#13b77e"), (0.72, "#f4d32f"), (1.0, "#c9233a")):
            gradient.setColorAt(stop, QColor(color))
        painter.fillRect(bar, gradient)
        painter.setPen(QColor(PALETTE["text"]))
        painter.drawText(QRectF(0, 5, 52, 20), Qt.AlignCenter, "Sv dB")
        for i, value in enumerate((-30, -35, -40, -45, -50, -55, -60, -65)):
            y = bar.top() + i / 7 * bar.height()
            painter.drawText(QRectF(31, y - 8, 28, 16), Qt.AlignLeft | Qt.AlignVCenter, str(value))


def make_fileset_panel() -> QWidget:
    tabs = QTabWidget()
    variables = QTreeWidget()
    variables.setHeaderHidden(True)
    raw = QTreeWidgetItem(["Raw variables"])
    for name in ("Sv", "TS", "Sp", "Sa", "SS", "Angle"):
        QTreeWidgetItem(raw, [name])
    derived = QTreeWidgetItem(["Derived variables"])
    for name in ("NASC", "Depth", "Bottom depth"):
        QTreeWidgetItem(derived, [name])
    variables.addTopLevelItem(raw)
    variables.addTopLevelItem(derived)
    variables.expandAll()

    filesets = QListWidget()
    filesets.addItem(QListWidgetItem("✓  200 kHz Fileset 1: Sv"))
    filesets.addItem(QListWidgetItem("    20260518FHSK-D20260518-T015810.raw"))
    tabs.addTab(variables, "Variables")
    tabs.addTab(filesets, "Filesets")
    return tabs


def make_processing_panel() -> QWidget:
    tabs = QTabWidget()
    operations = QListWidget()
    for name in ("Background removal", "TVG", "Absorption", "Sound speed", "Bottom detection", "Integration"):
        operations.addItem(QListWidgetItem(name))
    properties = QWidget()
    form = QFormLayout(properties)
    for label, value in (("Frequency", "200 kHz"), ("Beam type", "Split"), ("Color table", "Rainbow"), ("Min Sv", "-65 dB"), ("Max Sv", "-30 dB")):
        form.addRow(QLabel(label), QLabel(value))
    tabs.addTab(operations, "Operations")
    tabs.addTab(properties, "Properties")
    return tabs


def make_bottom_panel() -> QWidget:
    tabs = QTabWidget()
    regions = QTableWidget(1, 5)
    regions.setHorizontalHeaderLabels(("Name", "Type", "Start", "End", "Length"))
    for column, value in enumerate(("Region 1", "User", "532.12 m", "589.47 m", "57.35 m")):
        regions.setItem(0, column, QTableWidgetItem(value))
    messages = QTableWidget(2, 4)
    messages.setHorizontalHeaderLabels(("Time", "Level", "Source", "Message"))
    rows = (("10:46:58", "Info", "Application", "Welcome to Echoview"), ("10:47:02", "Warning", "Fileset", "One measurement was skipped"))
    for row, values in enumerate(rows):
        for column, value in enumerate(values):
            messages.setItem(row, column, QTableWidgetItem(value))
    tabs.addTab(regions, "Region Browser")
    tabs.addTab(messages, "Messages")
    return tabs


class EchoviewTemplateWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setObjectName("echoviewTemplateWindow")
        self.setWindowTitle("Echoview · Fish Acoustic Workbench")
        self.resize(1480, 900)
        self.setStyleSheet(build_stylesheet())
        self._build_menu()
        self._build_toolbars()
        self._build_workspace()
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready · 200 kHz · Sv display")

    def _build_menu(self):
        menu = self.menuBar()
        for title in ("File", "Echogram", "View", "Window", "Help"):
            menu.addMenu(QMenu(title, self))

    def _build_toolbars(self):
        primary = QToolBar("Standard", self)
        primary.setMovable(False)
        for label in ("New", "Open", "Save", "Undo", "Redo"):
            primary.addAction(QAction(label, self))
        primary.addSeparator()
        mode = QComboBox()
        mode.addItems(("Sv", "TS", "Sp", "Depth"))
        primary.addWidget(mode)
        self.addToolBar(primary)

        analysis = QToolBar("Analysis", self)
        analysis.setMovable(False)
        for label in ("Select", "Pan", "Zoom", "Measure", "Region", "Bottom line", "Run"):
            analysis.addAction(QAction(label, self))
        self.addToolBar(analysis)

    def _build_workspace(self):
        center = QWidget()
        center_layout = QHBoxLayout(center)
        center_layout.setContentsMargins(6, 6, 6, 6)
        center_layout.setSpacing(0)
        center_layout.addWidget(EchogramCanvas(), 1)
        center_layout.addWidget(ColorScale())
        self.setCentralWidget(center)

        left = QDockWidget("Filesets", self)
        left.setObjectName("filesetDock")
        left.setWidget(make_fileset_panel())
        left.setMinimumWidth(238)
        self.addDockWidget(Qt.LeftDockWidgetArea, left)

        right = QDockWidget("Processing", self)
        right.setObjectName("processingDock")
        right.setWidget(make_processing_panel())
        right.setMinimumWidth(280)
        self.addDockWidget(Qt.RightDockWidgetArea, right)

        bottom = QDockWidget("Analysis", self)
        bottom.setObjectName("bottomDock")
        bottom.setWidget(make_bottom_panel())
        bottom.setMinimumHeight(170)
        self.addDockWidget(Qt.BottomDockWidgetArea, bottom)


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Arial", 10))
    window = EchoviewTemplateWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
