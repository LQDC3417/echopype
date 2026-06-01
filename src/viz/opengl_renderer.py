"""OpenGL Echogram 渲染器

高性能 echogram 渲染，支持缩放、平移、叠加层与框选交互。
依赖: PyOpenGL, matplotlib, numpy, PySide6
"""

from typing import Optional, Tuple

import matplotlib.cm as cm
import numpy as np

try:
    from OpenGL.GL import (
        GL_BLEND,
        GL_CLAMP_TO_EDGE,
        GL_COLOR_BUFFER_BIT,
        GL_DEPTH_BUFFER_BIT,
        GL_LINEAR,
        GL_LINES,
        GL_LINE_STRIP,
        GL_MODELVIEW,
        GL_NEAREST,
        GL_ONE_MINUS_SRC_ALPHA,
        GL_PROJECTION,
        GL_QUADS,
        GL_RGBA,
        GL_SMOOTH,
        GL_SRC_ALPHA,
        GL_TEXTURE_2D,
        GL_TEXTURE_MAG_FILTER,
        GL_TEXTURE_MIN_FILTER,
        GL_TEXTURE_WRAP_S,
        GL_TEXTURE_WRAP_T,
        GL_UNPACK_ALIGNMENT,
        GL_UNSIGNED_BYTE,
        glBindTexture,
        glBlendFunc,
        glClear,
        glClearColor,
        glColor4f,
        glDisable,
        glEnable,
        glEnd,
        glGenTextures,
        glLineWidth,
        glLoadIdentity,
        glMatrixMode,
        glOrtho,
        glPixelStorei,
        glShadeModel,
        glTexCoord2f,
        glTexImage2D,
        glTexParameteri,
        glVertex2f,
        glBegin,
    )
except ImportError:
    raise ImportError(
        "需要安装 PyOpenGL: pip install PyOpenGL PyOpenGL-accelerate"
    )

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent, QWheelEvent
from PySide6.QtOpenGLWidgets import QOpenGLWidget


class EchogramRenderer(QOpenGLWidget):
    """OpenGL Echogram 渲染器

    将 Sv 数据转为 RGB 纹理上传 GPU，渲染为 2D 四边形。
    支持滚轮缩放、中键平移、左键框选，以及噪声/底部/鱼群叠加层。
    """

    # 信号
    mouse_moved = Signal(float, float)  # (ping_index, depth)
    region_selected = Signal(float, float, float, float)  # (x0, y0, x1, y1)

    def __init__(self, parent=None):
        super().__init__(parent)

        # 数据
        self._sv_data: Optional[np.ndarray] = None  # (n_pings, n_samples)
        self._noise_mask: Optional[np.ndarray] = None
        self._bottom_line: Optional[np.ndarray] = None  # (n_pings,)
        self._school_mask: Optional[np.ndarray] = None

        # 颜色映射
        self._cmap_name: str = "jet"
        self._vmin: float = -80.0
        self._vmax: float = -40.0

        # 纹理
        self._texture_id: int = 0
        self._texture_dirty: bool = True

        # 视口变换: 数据坐标 -> 屏幕坐标
        self._offset_x: float = 0.0
        self._offset_y: float = 0.0
        self._zoom: float = 1.0

        # 鼠标交互状态
        self._panning: bool = False
        self._pan_start: Optional[Tuple[float, float]] = None
        self._selecting: bool = False
        self._select_start: Optional[Tuple[float, float]] = None
        self._select_end: Optional[Tuple[float, float]] = None

        # 数据尺寸
        self._data_w: int = 0
        self._data_h: int = 0

    # ── 数据设置 ──────────────────────────────────────────────

    def set_data(self, sv_data: np.ndarray) -> None:
        """设置 Sv 数据 (n_pings, n_samples)"""
        self._sv_data = sv_data.astype(np.float32)
        self._data_h, self._data_w = sv_data.shape
        self._texture_dirty = True
        self.update()

    def set_noise_mask(self, mask: np.ndarray) -> None:
        """设置噪声 mask，与 Sv 数据同形状"""
        self._noise_mask = mask.astype(bool)
        self.update()

    def set_bottom_line(self, bottom: np.ndarray) -> None:
        """设置底部线 (n_pings,) — 每个 ping 的底部采样索引"""
        self._bottom_line = bottom.astype(np.float32)
        self.update()

    def set_school_mask(self, mask: np.ndarray) -> None:
        """设置鱼群 mask，与 Sv 数据同形状"""
        self._school_mask = mask.astype(bool)
        self.update()

    def set_colormap(
        self, name: str = "jet", vmin: float = -80.0, vmax: float = -40.0
    ) -> None:
        """设置颜色映射"""
        self._cmap_name = name
        self._vmin = vmin
        self._vmax = vmax
        self._texture_dirty = True
        self.update()

    # ── OpenGL 生命周期 ───────────────────────────────────────

    def initializeGL(self) -> None:
        """初始化 OpenGL 状态"""
        glClearColor(0.0, 0.0, 0.0, 1.0)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glShadeModel(GL_SMOOTH)
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1)

        # 创建纹理
        self._texture_id = int(glGenTextures(1))

    def resizeGL(self, w: int, h: int) -> None:
        """视口调整"""
        glViewport(0, 0, w, h)
        self._setup_projection(w, h)

    def _setup_projection(self, w: int, h: int) -> None:
        """设置正交投影"""
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0, w, h, 0, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

    def paintGL(self) -> None:
        """渲染 echogram + 叠加层"""
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        if self._sv_data is None:
            return

        w = self.width()
        h = self.height()

        # 应用变换: 平移 + 缩放
        self._setup_projection(w, h)

        # 绘制 echogram 纹理
        self._draw_echogram_texture()

        # 叠加层
        if self._noise_mask is not None:
            self._draw_noise_overlay()
        if self._bottom_line is not None:
            self._draw_bottom_line()
        if self._school_mask is not None:
            self._draw_school_overlay()
        if self._selecting and self._select_start and self._select_end:
            self._draw_selection_rect()

    # ── 纹理生成与渲染 ────────────────────────────────────────

    def _sv_to_rgb(self) -> np.ndarray:
        """将 Sv 数据映射为 RGBA 纹理数组 (H, W, 4) uint8"""
        cmap = cm.get_cmap(self._cmap_name)
        # 归一化到 [0, 1]
        norm = (self._sv_data - self._vmin) / (self._vmax - self._vmin)
        norm = np.clip(norm, 0.0, 1.0)
        # 应用 colormap -> (H, W, 4) float [0,1]
        rgba = cmap(norm)
        return (rgba * 255).astype(np.uint8)

    def _upload_texture(self) -> None:
        """上传纹理数据到 GPU"""
        if self._sv_data is None:
            return

        rgba = self._sv_to_rgb()
        tex_h, tex_w = rgba.shape[:2]

        # 找到最近的 2 的幂尺寸（部分驱动需要）
        glBindTexture(GL_TEXTURE_2D, self._texture_id)

        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)

        glTexImage2D(
            GL_TEXTURE_2D,
            0,
            GL_RGBA,
            tex_w,
            tex_h,
            0,
            GL_RGBA,
            GL_UNSIGNED_BYTE,
            rgba,
        )
        self._texture_dirty = False

    def _draw_echogram_texture(self) -> None:
        """渲染 echogram 纹理为带变换的四边形"""
        if self._texture_dirty:
            self._upload_texture()

        glBindTexture(GL_TEXTURE_2D, self._texture_id)
        glEnable(GL_TEXTURE_2D)

        # 计算屏幕范围
        sx = self._offset_x
        sy = self._offset_y
        sw = self._data_w * self._zoom
        sh = self._data_h * self._zoom

        glColor4f(1.0, 1.0, 1.0, 1.0)
        glBegin(GL_QUADS)
        glTexCoord2f(0, 0); glVertex2f(sx, sy)
        glTexCoord2f(1, 0); glVertex2f(sx + sw, sy)
        glTexCoord2f(1, 1); glVertex2f(sx + sw, sy + sh)
        glTexCoord2f(0, 1); glVertex2f(sx, sy + sh)
        glEnd()

        glDisable(GL_TEXTURE_2D)

    # ── 叠加层渲染 ────────────────────────────────────────────

    def _draw_noise_overlay(self) -> None:
        """半透明灰色噪声 mask"""
        if self._noise_mask is None:
            return

        glColor4f(0.3, 0.3, 0.3, 0.5)
        mask = self._noise_mask
        h, w = mask.shape
        # 逐列绘制噪声区间（简化：整列有噪声就画半透明矩形）
        for ping in range(w):
            col = mask[:, ping]
            if not np.any(col):
                continue
            ranges = self._find_runs(col)
            for start, end in ranges:
                x0 = self._offset_x + ping * self._zoom
                x1 = x0 + self._zoom
                y0 = self._offset_y + start * self._zoom
                y1 = self._offset_y + end * self._zoom
                glBegin(GL_QUADS)
                glVertex2f(x0, y0)
                glVertex2f(x1, y0)
                glVertex2f(x1, y1)
                glVertex2f(x0, y1)
                glEnd()

    def _draw_bottom_line(self) -> None:
        """白色底部折线"""
        if self._bottom_line is None:
            return

        glColor4f(1.0, 1.0, 1.0, 1.0)
        glLineWidth(2.0)
        glBegin(GL_LINE_STRIP)
        for i, val in enumerate(self._bottom_line):
            if np.isnan(val):
                glEnd()
                glBegin(GL_LINE_STRIP)
                continue
            x = self._offset_x + i * self._zoom
            y = self._offset_y + val * self._zoom
            glVertex2f(x, y)
        glEnd()

    def _draw_school_overlay(self) -> None:
        """半透明绿色鱼群边界"""
        if self._school_mask is None:
            return

        # 简化：绘制鱼群区域的半透明填充
        glColor4f(0.0, 1.0, 0.0, 0.25)
        mask = self._school_mask
        h, w = mask.shape
        for ping in range(w):
            col = mask[:, ping]
            if not np.any(col):
                continue
            ranges = self._find_runs(col)
            for start, end in ranges:
                x0 = self._offset_x + ping * self._zoom
                x1 = x0 + self._zoom
                y0 = self._offset_y + start * self._zoom
                y1 = self._offset_y + end * self._zoom
                glBegin(GL_QUADS)
                glVertex2f(x0, y0)
                glVertex2f(x1, y0)
                glVertex2f(x1, y1)
                glVertex2f(x0, y1)
                glEnd()

        # 绘制边界线
        glColor4f(0.0, 1.0, 0.0, 0.8)
        glLineWidth(1.0)
        # 简单边界检测：mask 与非 mask 相邻的像素
        for y in range(h):
            for x in range(w):
                if not mask[y, x]:
                    continue
                # 右边界
                if x == w - 1 or not mask[y, x + 1]:
                    px = self._offset_x + (x + 1) * self._zoom
                    y0 = self._offset_y + y * self._zoom
                    y1 = y0 + self._zoom
                    glBegin(GL_LINES)
                    glVertex2f(px, y0)
                    glVertex2f(px, y1)
                    glEnd()
                # 下边界
                if y == h - 1 or not mask[y + 1, x]:
                    py = self._offset_y + (y + 1) * self._zoom
                    x0 = self._offset_x + x * self._zoom
                    x1 = x0 + self._zoom
                    glBegin(GL_LINES)
                    glVertex2f(x0, py)
                    glVertex2f(x1, py)
                    glEnd()

    def _draw_selection_rect(self) -> None:
        """半透明蓝色框选矩形"""
        if not (self._select_start and self._select_end):
            return

        x0, y0 = self._select_start
        x1, y1 = self._select_end

        glColor4f(0.2, 0.4, 1.0, 0.3)
        glBegin(GL_QUADS)
        glVertex2f(x0, y0)
        glVertex2f(x1, y0)
        glVertex2f(x1, y1)
        glVertex2f(x0, y1)
        glEnd()

        glColor4f(0.2, 0.4, 1.0, 0.8)
        glLineWidth(1.5)
        glBegin(GL_LINE_STRIP)
        glVertex2f(x0, y0)
        glVertex2f(x1, y0)
        glVertex2f(x1, y1)
        glVertex2f(x0, y1)
        glVertex2f(x0, y0)
        glEnd()

    # ── 鼠标交互 ──────────────────────────────────────────────

    def wheelEvent(self, event: QWheelEvent) -> None:
        """滚轮缩放 — 以鼠标位置为中心"""
        pos = event.pos()
        sx, sy = float(pos.x()), float(pos.y())

        # 数据坐标（缩放前）
        data_x = (sx - self._offset_x) / self._zoom
        data_y = (sy - self._offset_y) / self._zoom

        # 缩放因子
        delta = event.angleDelta().y()
        factor = 1.15 if delta > 0 else 1.0 / 1.15
        self._zoom = max(0.1, min(50.0, self._zoom * factor))

        # 调整偏移使鼠标下数据点不动
        self._offset_x = sx - data_x * self._zoom
        self._offset_y = sy - data_y * self._zoom

        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """鼠标按下"""
        sx, sy = float(event.x()), float(event.y())

        if event.button() == Qt.MiddleButton:
            self._panning = True
            self._pan_start = (sx, sy)
            self.setCursor(Qt.ClosedHandCursor)

        elif event.button() == Qt.LeftButton:
            self._selecting = True
            self._select_start = (sx, sy)
            self._select_end = (sx, sy)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """鼠标移动"""
        sx, sy = float(event.x()), float(event.y())

        # 发射坐标信号
        data_x, data_y = self._screen_to_data(sx, sy)
        self.mouse_moved.emit(data_x, data_y)

        if self._panning and self._pan_start:
            dx = sx - self._pan_start[0]
            dy = sy - self._pan_start[1]
            self._offset_x += dx
            self._offset_y += dy
            self._pan_start = (sx, sy)
            self.update()

        elif self._selecting:
            self._select_end = (sx, sy)
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """鼠标释放"""
        if event.button() == Qt.MiddleButton:
            self._panning = False
            self._pan_start = None
            self.setCursor(Qt.ArrowCursor)

        elif event.button() == Qt.LeftButton and self._selecting:
            self._selecting = False
            if self._select_start and self._select_end:
                x0, y0 = self._screen_to_data(*self._select_start)
                x1, y1 = self._screen_to_data(*self._select_end)
                # 归一化坐标
                self.region_selected.emit(
                    min(x0, x1), min(y0, y1),
                    max(x0, x1), max(y0, y1),
                )
            self._select_start = None
            self._select_end = None
            self.update()

    # ── 坐标转换 ──────────────────────────────────────────────

    def _screen_to_data(self, sx: float, sy: float) -> Tuple[float, float]:
        """屏幕坐标 → 数据坐标 (ping_index, sample_index)"""
        data_x = (sx - self._offset_x) / self._zoom
        data_y = (sy - self._offset_y) / self._zoom
        return data_x, data_y

    def _data_to_screen(self, dx: float, dy: float) -> Tuple[float, float]:
        """数据坐标 → 屏幕坐标"""
        sx = dx * self._zoom + self._offset_x
        sy = dy * self._zoom + self._offset_y
        return sx, sy

    # ── 视图控制 ──────────────────────────────────────────────

    def reset_view(self) -> None:
        """重置视图到默认状态"""
        self._offset_x = 0.0
        self._offset_y = 0.0
        self._zoom = 1.0
        self._selecting = False
        self._select_start = None
        self._select_end = None
        self.update()

    # ── 工具方法 ──────────────────────────────────────────────

    @staticmethod
    def _find_runs(arr: np.ndarray) -> list:
        """找到布尔数组中 True 的连续区间 [(start, end), ...]"""
        runs = []
        in_run = False
        start = 0
        for i, val in enumerate(arr):
            if val and not in_run:
                start = i
                in_run = True
            elif not val and in_run:
                runs.append((start, i))
                in_run = False
        if in_run:
            runs.append((start, len(arr)))
        return runs
