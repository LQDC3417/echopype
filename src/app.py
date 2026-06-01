"""Echogram GUI 应用入口"""

import sys
import os

# 修复 Windows 中文环境
os.environ["PYTHONUTF8"] = "1"

from PySide6.QtWidgets import QApplication
from src.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Echogram GUI")
    app.setApplicationVersion("1.0.0")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
