"""应用启动欢迎页。"""

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
)


class WelcomeDialog(QDialog):
    """提供新建、打开和最近项目入口；关闭后主窗口保持空白。"""

    new_project_requested = Signal()
    open_project_requested = Signal()
    recent_project_requested = Signal(str)

    def __init__(self, recent_projects: list[str], parent=None):
        super().__init__(parent)
        self.setObjectName("welcomeDialog")
        self.setWindowTitle("欢迎使用")
        self.setModal(False)
        self.resize(440, 300)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setObjectName("welcomeCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 20, 22, 18)
        card_layout.setSpacing(10)

        title = QLabel("欢迎使用")
        title.setObjectName("welcomeTitle")
        card_layout.addWidget(title)
        subtitle = QLabel("导入声学数据或打开已有项目，开始分析。")
        subtitle.setObjectName("welcomeSubtitle")
        card_layout.addWidget(subtitle)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        self.new_button = QPushButton("导入 .raw")
        self.new_button.setObjectName("importRawButton")
        self.new_button.setProperty("cssClass", "primary")
        self.open_button = QPushButton("打开项目")
        self.open_button.setObjectName("openProjectButton")
        buttons.addWidget(self.new_button)
        buttons.addWidget(self.open_button)
        card_layout.addLayout(buttons)

        recent_title = QLabel("最近项目")
        recent_title.setObjectName("recentProjectsTitle")
        card_layout.addWidget(recent_title)
        self.recent_list = QListWidget()
        self.recent_list.setObjectName("recentProjects")
        for project in recent_projects:
            self.recent_list.addItem(f"{Path(project).name} — {project}")
            self.recent_list.item(self.recent_list.count() - 1).setData(256, project)
        card_layout.addWidget(self.recent_list, 1)
        layout.addWidget(card)
        self.new_button.clicked.connect(self.new_project_requested)
        self.open_button.clicked.connect(self.open_project_requested)
        self.recent_list.itemActivated.connect(lambda item: self.recent_project_requested.emit(item.data(256)))
