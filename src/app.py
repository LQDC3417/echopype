"""Echogram GUI 应用入口 — Echoview 风格 v2.0"""

import sys
import os

# 修复 Windows 中文环境
os.environ["PYTHONUTF8"] = "1"

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from src.gui.main_window import MainWindow
from src.gui.theme import DARK_THEME


def main():
    # 高 DPI 适配
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("Echogram")
    app.setApplicationVersion("2.0")
    app.setOrganizationName("FishAcoustics")
    app.setStyleSheet(DARK_THEME)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
