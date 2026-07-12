"""底部状态栏"""

import math
from PySide6.QtWidgets import QStatusBar, QProgressBar, QLabel


class MainStatusBar(QStatusBar):
    """底部状态栏：进度条 + 状态信息 + 坐标 + Sv 值"""

    def __init__(self, parent=None):
        super().__init__(parent)

        # 流水线步骤
        self.lbl_step = QLabel("")
        self.lbl_step.setStyleSheet("color: #e53e3e; font-weight: bold; padding: 0 8px;")
        self.addWidget(self.lbl_step)

        # 状态信息
        self.lbl_status = QLabel("就绪 — 请导入 Raw 文件")
        self.addWidget(self.lbl_status, 1)

        # 当前文件
        self.lbl_file = QLabel("")
        self.lbl_file.setStyleSheet("color: #4a5568; padding: 0 8px;")
        self.addPermanentWidget(self.lbl_file)

        # 坐标显示
        self.lbl_coords = QLabel("Ping: -- | Sample: --")
        self.addPermanentWidget(self.lbl_coords)

        # 深度(m)
        self.lbl_depth = QLabel("Depth: -- m")
        self.lbl_depth.setMinimumWidth(100)
        self.addPermanentWidget(self.lbl_depth)

        # Sv 值
        self.lbl_sv = QLabel("Sv: -- dB")
        self.lbl_sv.setMinimumWidth(110)
        self.addPermanentWidget(self.lbl_sv)

        # 缩放比例
        self.lbl_zoom = QLabel("Zoom: 1.0x")
        self.lbl_zoom.setMinimumWidth(100)
        self.addPermanentWidget(self.lbl_zoom)

        # 进度条
        self.progress = QProgressBar()
        self.progress.setMaximumWidth(200)
        self.progress.setVisible(False)
        self.addPermanentWidget(self.progress)

    def set_step(self, text: str):
        self.lbl_step.setText(text)

    def set_status(self, text: str):
        self.lbl_status.setText(text)

    def set_coords(self, ping: float, depth: float):
        self.lbl_coords.setText(f"Ping: {ping:.0f} | Sample: {depth:.0f}")

    def set_depth_info(self, depth_m: float):
        """显示实际深度（米）"""
        if math.isnan(depth_m):
            self.lbl_depth.setText("Depth: -- m")
        else:
            self.lbl_depth.setText(f"Depth: {depth_m:.1f} m")

    def set_sv(self, _ping: float, _depth: float, sv: float):
        if math.isnan(sv):
            self.lbl_sv.setText("Sv: -- dB")
        else:
            self.lbl_sv.setText(f"Sv: {sv:.1f} dB")

    def set_file_info(self, text: str):
        """显示当前文件名和索引"""
        self.lbl_file.setText(text)

    def set_zoom_info(self, zoom_x: float, zoom_y: float):
        """显示缩放比例"""
        self.lbl_zoom.setText(f"Zoom: {zoom_x:.1f}x")

    def show_progress(self, text: str = ""):
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)  # 不确定进度模式
        if text:
            self.lbl_status.setText(text)

    def hide_progress(self):
        self.progress.setVisible(False)
