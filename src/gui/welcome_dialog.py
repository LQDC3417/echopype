"""应用启动欢迎页。"""

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QListWidget, QPushButton, QVBoxLayout


class WelcomeDialog(QDialog):
    """提供新建、打开和最近项目入口；关闭后主窗口保持空白。"""

    new_project_requested = Signal()
    open_project_requested = Signal()
    recent_project_requested = Signal(str)

    def __init__(self, recent_projects: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("欢迎使用")
        self.setModal(False)
        self.resize(460, 280)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("创建或打开一个 .ep 项目"))
        buttons = QHBoxLayout()
        self.new_button = QPushButton("新建项目（导入 .raw）")
        self.open_button = QPushButton("打开 .ep 项目")
        buttons.addWidget(self.new_button)
        buttons.addWidget(self.open_button)
        layout.addLayout(buttons)
        self.recent_list = QListWidget()
        for project in recent_projects:
            self.recent_list.addItem(f"{Path(project).name} — {project}")
            self.recent_list.item(self.recent_list.count() - 1).setData(256, project)
        layout.addWidget(QLabel("最近项目"))
        layout.addWidget(self.recent_list, 1)
        self.new_button.clicked.connect(self.new_project_requested)
        self.open_button.clicked.connect(self.open_project_requested)
        self.recent_list.itemActivated.connect(lambda item: self.recent_project_requested.emit(item.data(256)))
