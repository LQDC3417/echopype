"""底部状态栏"""

from PySide6.QtWidgets import QStatusBar, QProgressBar, QLabel


class MainStatusBar(QStatusBar):
    """底部状态栏：进度条 + 状态信息 + 坐标"""

    def __init__(self, parent=None):
        super().__init__(parent)

        # 状态信息
        self.lbl_status = QLabel("就绪")
        self.addWidget(self.lbl_status, 1)

        # 坐标显示
        self.lbl_coords = QLabel("Ping: -- | Depth: --")
        self.addPermanentWidget(self.lbl_coords)

        # 进度条
        self.progress = QProgressBar()
        self.progress.setMaximumWidth(200)
        self.progress.setVisible(False)
        self.addPermanentWidget(self.progress)

    def set_status(self, text: str):
        self.lbl_status.setText(text)

    def set_coords(self, ping: float, depth: float):
        self.lbl_coords.setText(f"Ping: {ping:.1f} | Depth: {depth:.1f} m")

    def show_progress(self, text: str = ""):
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)  # 不确定进度模式
        if text:
            self.lbl_status.setText(text)

    def hide_progress(self):
        self.progress.setVisible(False)
