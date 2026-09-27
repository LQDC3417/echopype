"""Echogram GUI 应用入口 — Echoview 风格 v2.0"""

import os
import sys

# 修复 Windows 中文环境
os.environ["PYTHONUTF8"] = "1"

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from src.gui.main_window import MainWindow
from src.gui.theme import LIGHT_THEME


def main():
    # 高 DPI 适配
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    families = QFontDatabase.families()
    family = next((name for name in ("Microsoft YaHei UI", "Microsoft YaHei", "Noto Sans CJK SC") if name in families), app.font().family())
    app.setFont(QFont(family, 9))
    app.setApplicationName("Echogram")
    app.setApplicationVersion("2.0")
    app.setOrganizationName("FishAcoustics")
    app.setStyleSheet(LIGHT_THEME)

    window = MainWindow()
    window.show()
    from src.gui.handlers.file_handlers import _load_recent
    from src.gui.welcome_dialog import WelcomeDialog

    def show_welcome():
        dialog = WelcomeDialog(_load_recent(), window)
        dialog.new_project_requested.connect(window._new_project)
        dialog.open_project_requested.connect(window._open_project)
        dialog.recent_project_requested.connect(window._open_recent)
        dialog.show()
        window._welcome_dialog = dialog

    QTimer.singleShot(0, show_welcome)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
