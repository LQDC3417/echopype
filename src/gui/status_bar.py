"""状态栏组件 - 参照 Echoview 设计的专业风格

布局（参照 Echoview 底部状态栏）：
[流水线步骤] [状态信息] | [深度] [Sv值] [缩放] | [坐标] [文件名] | [GPS] [时间] [进度条]
"""

import math
from datetime import datetime

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel, QProgressBar, QStatusBar

from src.gui.i18n import T


def _format_dms(value: float, is_lat: bool) -> str:
    """将十进制度转换为度分秒格式

    Args:
        value: 十进制度数
        is_lat: True表示纬度（N/S），False表示经度（E/W）

    Returns:
        格式化字符串，如 "38° 03.444' N"
    """
    # 负值处理：先取绝对值计算度分秒，方向用原始符号决定
    is_negative = value < 0
    abs_value = abs(value)

    # 度取整数部分
    degrees = int(abs_value)

    # 分 = (小数*60)，保留3位小数
    minutes_decimal = (abs_value - degrees) * 60

    # 方向后缀
    if is_lat:
        direction = "S" if is_negative else "N"
    else:
        direction = "W" if is_negative else "E"

    # 格式化输出：度° 分.秒' 方向
    # 分钟需要格式化为3位小数，整数部分需要2位
    minutes_int = int(minutes_decimal)
    minutes_decimal_part = f"{minutes_decimal - minutes_int:.3f}"[1:]  # 取小数点及后面

    return f"{degrees}° {minutes_int:02d}{minutes_decimal_part}' {direction}"


class MainStatusBar(QStatusBar):
    """底部状态栏 — 参照 Echoview 风格

    信息区域（从左到右）：
    1. 流水线步骤（红色粗体）
    2. 状态信息（弹性区域）
    3. 深度信息
    4. Sv 值
    5. 缩放比例
    6. 坐标信息
    7. 当前文件
    8. GPS 坐标
    9. 时间戳
    10. 进度条
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # ─── 流水线步骤 ───
        self.lbl_step = QLabel("")
        self.lbl_step.setStyleSheet("color: #e53e3e; font-weight: bold; padding: 0 8px;")
        self.addWidget(self.lbl_step)

        # ─── 状态信息 ───
        self.lbl_status = QLabel(T("status_ready"))
        self.addWidget(self.lbl_status, 1)

        # ─── 分隔符 ───
        self.addWidget(self._separator())

        # ─── 深度信息 ───
        self.lbl_depth = QLabel(T("status_depth"))
        self.lbl_depth.setMinimumWidth(100)
        self.lbl_depth.setStyleSheet("padding: 0 8px;")
        self.addPermanentWidget(self.lbl_depth)

        # ─── Sv 值 ───
        self.lbl_sv = QLabel(T("status_sv"))
        self.lbl_sv.setMinimumWidth(110)
        self.lbl_sv.setStyleSheet("padding: 0 8px;")
        self.addPermanentWidget(self.lbl_sv)

        # ─── 分隔符 ───
        self.addPermanentWidget(self._separator())

        # ─── 缩放比例 ───
        self.lbl_zoom = QLabel(T("status_zoom"))
        self.lbl_zoom.setMinimumWidth(100)
        self.lbl_zoom.setStyleSheet("padding: 0 8px;")
        self.addPermanentWidget(self.lbl_zoom)

        # ─── 分隔符 ───
        self.addPermanentWidget(self._separator())

        # ─── 坐标信息 ───
        self.lbl_coords = QLabel(T("status_coords"))
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
        self.lbl_gps = QLabel(T("status_gps"))
        self.lbl_gps.setMinimumWidth(180)
        self.lbl_gps.setStyleSheet("padding: 0 8px;")
        self.addPermanentWidget(self.lbl_gps)

        # ─── 分隔符 ───
        self.addPermanentWidget(self._separator())

        # ─── 时间戳 ───
        self.lbl_time = QLabel(T("status_time"))
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
        # 注意：这里不再自动更新时间，时间由 set_ping_time 方法设置
        pass

    def set_step(self, text: str):
        """设置流水线步骤"""
        self.lbl_step.setText(text)

    def set_status(self, text: str):
        """设置状态信息"""
        self.lbl_status.setText(text)

    def set_coords(self, ping: float, depth: float):
        """设置坐标信息"""
        self.lbl_coords.setText(T("status_coords_fmt", ping=ping, sample=depth))

    def set_depth_info(self, depth_m: float):
        """显示实际深度（米）"""
        if math.isnan(depth_m):
            self.lbl_depth.setText(T("status_depth"))
        else:
            self.lbl_depth.setText(T("status_depth_fmt", val=depth_m))

    def set_sv(self, _ping: float, _depth: float, sv: float):
        """设置 Sv 值"""
        if math.isnan(sv):
            self.lbl_sv.setText(T("status_sv"))
        else:
            self.lbl_sv.setText(T("status_sv_fmt", val=sv))

    def set_file_info(self, text: str):
        """显示当前文件名和索引"""
        self.lbl_file.setText(text)

    def set_zoom_info(self, zoom_x: float, zoom_y: float):
        """显示缩放比例"""
        self.lbl_zoom.setText(T("status_zoom_fmt", val=zoom_x))

    def set_gps_info(self, lat: float | None = None, lon: float | None = None):
        """设置 GPS 坐标（度分秒格式）"""
        if lat is None or lon is None:
            self.lbl_gps.setText(T("status_gps"))
        else:
            self.lbl_gps.setText(f"{_format_dms(lat, True)} {_format_dms(lon, False)}")

    def set_ping_time(self, dt=None):
        """设置 ping 时间戳

        Args:
            dt: datetime 对象或 numpy datetime64，None 时显示占位文本
        """
        if dt is None:
            self.lbl_time.setText(T("status_time"))
        else:
            # 处理 numpy datetime64 类型
            if hasattr(dt, 'astype'):
                # numpy datetime64 转换为 datetime
                dt = dt.astype('datetime64[ms]').astype(datetime)
            # 格式化时间
            time_str = dt.strftime("%Y/%m/%d %H:%M:%S")
            self.lbl_time.setText(T("status_time_fmt", t=time_str))

    def show_progress(self, text: str = ""):
        """显示进度条"""
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)  # 不确定进度模式
        if text:
            self.lbl_status.setText(text)

    def hide_progress(self):
        """隐藏进度条"""
        self.progress.setVisible(False)
