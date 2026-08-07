"""状态栏组件 - 基于 Echoview 设计的专业风格

布局：[深度] [Sv值] [缩放] [坐标] [文件信息] [GPS] [时间]
"""

import math
from datetime import datetime
from PySide6.QtWidgets import QStatusBar, QProgressBar, QLabel, QWidget, QHBoxLayout
from PySide6.QtCore import Qt, QTimer


class MainStatusBar(QStatusBar):
    """底部状态栏 - Echoview 风格
    
    显示：
    - 流水线步骤
    - 状态信息
    - 当前文件
    - 深度信息
    - Sv 值
    - 缩放比例
    - 坐标信息
    - GPS 坐标
    - 时间戳
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # ─── 流水线步骤 ───
        self.lbl_step = QLabel("")
        self.lbl_step.setStyleSheet("color: #e53e3e; font-weight: bold; padding: 0 8px;")
        self.addWidget(self.lbl_step)
        
        # ─── 状态信息 ───
        self.lbl_status = QLabel("Ready - Import Raw files to start")
        self.addWidget(self.lbl_status, 1)
        
        # ─── 分隔符 ───
        self.addWidget(self._separator())
        
        # ─── 深度信息 ───
        self.lbl_depth = QLabel("Depth: -- m")
        self.lbl_depth.setMinimumWidth(100)
        self.lbl_depth.setStyleSheet("padding: 0 8px;")
        self.addPermanentWidget(self.lbl_depth)
        
        # ─── Sv 值 ───
        self.lbl_sv = QLabel("Sv: -- dB")
        self.lbl_sv.setMinimumWidth(110)
        self.lbl_sv.setStyleSheet("padding: 0 8px;")
        self.addPermanentWidget(self.lbl_sv)
        
        # ─── 分隔符 ───
        self.addPermanentWidget(self._separator())
        
        # ─── 缩放比例 ───
        self.lbl_zoom = QLabel("Zoom: 1.0x")
        self.lbl_zoom.setMinimumWidth(100)
        self.lbl_zoom.setStyleSheet("padding: 0 8px;")
        self.addPermanentWidget(self.lbl_zoom)
        
        # ─── 分隔符 ───
        self.addPermanentWidget(self._separator())
        
        # ─── 坐标信息 ───
        self.lbl_coords = QLabel("Ping: -- | Sample: --")
        self.lbl_coords.setStyleSheet("padding: 0 8px;")
        self.addPermanentWidget(self.lbl_coords)
        
        # ─── 分隔符 ───
        self.addPermanentWidget(self._separator())
        
        # ─── 当前文件 ───
        self.lbl_file = QLabel("")
        self.lbl_file.setStyleSheet("color: #4a5568; padding: 0 8px;")
        self.lbl_file.setMaximumWidth(200)
        self.addPermanentWidget(self.lbl_file)
        
        # ─── 分隔符 ───
        self.addPermanentWidget(self._separator())
        
        # ─── GPS 坐标 ───
        self.lbl_gps = QLabel("GPS: --")
        self.lbl_gps.setMinimumWidth(180)
        self.lbl_gps.setStyleSheet("padding: 0 8px;")
        self.addPermanentWidget(self.lbl_gps)
        
        # ─── 分隔符 ───
        self.addPermanentWidget(self._separator())
        
        # ─── 时间戳 ───
        self.lbl_time = QLabel(datetime.now().strftime("%Y/%m/%d %H:%M:%S"))
        self.lbl_time.setStyleSheet("padding: 0 8px;")
        self.addPermanentWidget(self.lbl_time)
        
        # ─── 进度条 ───
        self.progress = QProgressBar()
        self.progress.setMaximumWidth(200)
        self.progress.setVisible(False)
        self.addPermanentWidget(self.progress)
        
        # ─── 更新时间 ───
        self._timer = QTimer()
        self._timer.timeout.connect(self._update_time)
        self._timer.start(1000)
    
    def _separator(self):
        """创建分隔符"""
        sep = QLabel("|")
        sep.setStyleSheet("color: #999; padding: 0 4px;")
        return sep
    
    def _update_time(self):
        """更新时间戳"""
        self.lbl_time.setText(datetime.now().strftime("%Y/%m/%d %H:%M:%S"))
    
    def set_step(self, text: str):
        """设置流水线步骤"""
        self.lbl_step.setText(text)
    
    def set_status(self, text: str):
        """设置状态信息"""
        self.lbl_status.setText(text)
    
    def set_coords(self, ping: float, depth: float):
        """设置坐标信息"""
        self.lbl_coords.setText(f"Ping: {ping:.0f} | Sample: {depth:.0f}")
    
    def set_depth_info(self, depth_m: float):
        """显示实际深度（米）"""
        if math.isnan(depth_m):
            self.lbl_depth.setText("Depth: -- m")
        else:
            self.lbl_depth.setText(f"Depth: {depth_m:.1f} m")
    
    def set_sv(self, _ping: float, _depth: float, sv: float):
        """设置 Sv 值"""
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
    
    def set_gps_info(self, lat: float = None, lon: float = None):
        """设置 GPS 坐标"""
        if lat is None or lon is None:
            self.lbl_gps.setText("GPS: --")
        else:
            self.lbl_gps.setText(f"GPS: {lat:.4f}° N {lon:.4f}° E")
    
    def show_progress(self, text: str = ""):
        """显示进度条"""
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)  # 不确定进度模式
        if text:
            self.lbl_status.setText(text)
    
    def hide_progress(self):
        """隐藏进度条"""
        self.progress.setVisible(False)
