"""OpenGL Echogram 渲染器

高性能 echogram 渲染，支持缩放、平移、叠加层与框选交互。
依赖: PyOpenGL, matplotlib, numpy, PySide6

数据约定:
- Sv 数据: (n_pings, n_samples) — ping 为横轴, range_sample 为纵轴
- 纹理: (n_samples, n_pings, 4) — 转置后上传, 表面在上, 水底在下
- 屏幕坐标: X=ping, Y=depth (上=表面, 下=水底)
"""

import numpy as np
import matplotlib.cm as cm

from OpenGL.GL import (
    GL_BLEND, GL_CLAMP_TO_EDGE, GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT,
    GL_LINEAR, GL_LINES, GL_LINE_STRIP, GL_MODELVIEW, GL_NEAREST,
    GL_ONE_MINUS_SRC_ALPHA, GL_PROJECTION, GL_QUADS, GL_RGBA,
    GL_SRC_ALPHA, GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER,
    GL_TEXTURE_MIN_FILTER, GL_TEXTURE_WRAP_S, GL_TEXTURE_WRAP_T,
    GL_UNPACK_ALIGNMENT, GL_UNSIGNED_BYTE,
    glBindTexture, glBlendFunc, glClear, glClearColor, glColor4f,
    glDisable, glEnable, glEnd, glGenTextures, glLineWidth,
    glLoadIdentity, glMatrixMode, glOrtho, glPixelStorei,
    glTexCoord2f, glTexImage2D, glTexParameteri,
    glVertex2f, glViewport, glBegin,
)

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent, QWheelEvent
from PySide6.QtOpenGLWidgets import QOpenGLWidget


class EchogramRenderer(QOpenGLWidget):
    """OpenGL Echogram 渲染器"""

    mouse_moved = Signal(float, float)  # (ping_index, depth_sample_index)
    region_selected = Signal(float, float, float, float)  # (ping0, sample0, ping1, sample1)

    # 最大纹理尺寸
    MAX_TEX_SIZE = 16384

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(200, 200)

        # 数据: (n_pings, n_samples)
        self._sv_data = None
        self._noise_mask = None
        self._bottom_line = None  # (n_pings,) — 每个 ping 的底部采样索引
        self._school_mask = None

        # 颜色映射
        self._cmap_name = "jet"
        self._vmin = -70.0
        self._vmax = -20.0

        # 纹理
        self._texture_id = 0
        self._texture_dirty = True
        self._tex_w = 0
        self._tex_h = 0

        # 视口变换
        self._offset_x = 0.0
        self._offset_y = 0.0
        self._zoom = 1.0

        # 鼠标状态
        self._panning = False
        self._pan_start = None
        self._selecting = False
        self._select_start = None
        self._select_end = None

        # 数据尺寸
        self._data_w = 0  # n_pings
        self._data_h = 0  # n_samples

    # ── 数据设置 ──────────────────────────────────────────────

    def set_data(self, sv_data: np.ndarray) -> None:
        """设置 Sv 数据 (n_pings, n_samples)"""
        self._sv_data = sv_data.astype(np.float32)
        self._data_w = sv_data.shape[1]  # n_pings (横轴)
        self._data_h = sv_data.shape[0]  # n_samples (纵轴)
        self._texture_dirty = True
        self.update()

    def set_noise_mask(self, mask: np.ndarray) -> None:
        """设置噪声 mask"""
        self._noise_mask = mask.astype(bool)
        self.update()

    def set_bottom_line(self, bottom: np.ndarray) -> None:
        """设置底部线 (n_pings,)"""
        self._bottom_line = np.asarray(bottom, dtype=np.float32)
        self.update()

    def set_school_mask(self, mask: np.ndarray) -> None:
        """设置鱼群 mask"""
        self._school_mask = mask.astype(bool)
        self.update()

    def set_colormap(self, name: str = "jet", vmin: float = -70.0, vmax: float = -20.0) -> None:
        """设置颜色映射"""
        self._cmap_name = name
        self._vmin = vmin
        self._vmax = vmax
        self._texture_dirty = True
        self.update()

    # ── OpenGL 生命周期 ───────────────────────────────────────

    def initializeGL(self) -> None:
        glClearColor(0.0, 0.0, 0.0, 1.0)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
        self._texture_id = int(glGenTextures(1))

    def resizeGL(self, w: int, h: int) -> None:
        glViewport(0, 0, w, h)

    def paintGL(self) -> None:
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        if self._sv_data is None:
            return

        # 正交投影: 屏幕坐标 (左上=0,0)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0, self.width(), self.height(), 0, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        self._draw_echogram_texture()

        if self._noise_mask is not None:
            self._draw_noise_overlay()
        if self._bottom_line is not None:
            self._draw_bottom_line()
        if self._school_mask is not None:
            self._draw_school_overlay()
        if self._selecting and self._select_start and self._select_end:
            self._draw_selection_rect()

    # ── 纹理生成与渲染 ────────────────────────────────────────

    def _sv_to_rgba(self) -> np.ndarray:
        """将 Sv 数据转为 RGBA 纹理数组 (n_samples, n_pings, 4)

        数据 (n_pings, n_samples) 转置为 (n_samples, n_pings) 以便:
        - 纹理宽度 = n_pings (横轴)
        - 纹理高度 = n_samples (纵轴, 表面在上)
        """
        cmap = cm.get_cmap(self._cmap_name)
        # 转置: (n_pings, n_samples) -> (n_samples, n_pings)
        data_T = self._sv_data.T
        norm = np.clip((data_T - self._vmin) / (self._vmax - self._vmin), 0, 1)
        rgba = cmap(norm)
        return (rgba * 255).astype(np.uint8)

    def _upload_texture(self) -> None:
        """上传纹理到 GPU，自动降采样"""
        if self._sv_data is None:
            return

        rgba = self._sv_to_rgba()
        tex_h, tex_w = rgba.shape[:2]

        # 降采样
        if tex_w > self.MAX_TEX_SIZE or tex_h > self.MAX_TEX_SIZE:
            step_x = max(1, int(np.ceil(tex_w / self.MAX_TEX_SIZE)))
            step_y = max(1, int(np.ceil(tex_h / self.MAX_TEX_SIZE)))
            rgba = rgba[::step_y, ::step_x]
            tex_h, tex_w = rgba.shape[:2]

        glBindTexture(GL_TEXTURE_2D, self._texture_id)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, tex_w, tex_h, 0,
                     GL_RGBA, GL_UNSIGNED_BYTE, rgba)
        self._tex_w = tex_w
        self._tex_h = tex_h
        self._texture_dirty = False

    def _draw_echogram_texture(self) -> None:
        """渲染 echogram 纹理"""
        if self._texture_dirty:
            self._upload_texture()

        glBindTexture(GL_TEXTURE_2D, self._texture_id)
        glEnable(GL_TEXTURE_2D)

        # 屏幕范围: X=ping方向, Y=depth方向
        sx = self._offset_x
        sy = self._offset_y
        sw = self._data_w * self._zoom  # ping 方向宽度
        sh = self._data_h * self._zoom  # depth 方向高度

        glColor4f(1.0, 1.0, 1.0, 1.0)
        glBegin(GL_QUADS)
        glTexCoord2f(0, 0); glVertex2f(sx, sy)           # 左上 = ping0, surface
        glTexCoord2f(1, 0); glVertex2f(sx + sw, sy)       # 右上 = pingN, surface
        glTexCoord2f(1, 1); glVertex2f(sx + sw, sy + sh)  # 右下 = pingN, bottom
        glTexCoord2f(0, 1); glVertex2f(sx, sy + sh)       # 左下 = ping0, bottom
        glEnd()
        glDisable(GL_TEXTURE_2D)

    # ── 叠加层渲染 ────────────────────────────────────────────

    def _draw_noise_overlay(self) -> None:
        """半透明灰色噪声 mask"""
        mask = self._noise_mask
        if mask is None:
            return
        glColor4f(0.3, 0.3, 0.3, 0.5)
        h, w = mask.shape
        for ping in range(w):
            col = mask[:, ping]
            if not np.any(col):
                continue
            for start, end in self._find_runs(col):
                x0 = self._offset_x + ping * self._zoom
                x1 = x0 + self._zoom
                y0 = self._offset_y + start * self._zoom
                y1 = self._offset_y + end * self._zoom
                glBegin(GL_QUADS)
                glVertex2f(x0, y0); glVertex2f(x1, y0)
                glVertex2f(x1, y1); glVertex2f(x0, y1)
                glEnd()

    def _draw_bottom_line(self) -> None:
        """白色底部折线"""
        bl = self._bottom_line
        if bl is None:
            return
        glColor4f(1.0, 1.0, 1.0, 1.0)
        glLineWidth(2.0)
        glBegin(GL_LINE_STRIP)
        for i, val in enumerate(bl):
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
        mask = self._school_mask
        if mask is None:
            return
        glColor4f(0.0, 1.0, 0.0, 0.25)
        h, w = mask.shape
        for ping in range(w):
            col = mask[:, ping]
            if not np.any(col):
                continue
            for start, end in self._find_runs(col):
                x0 = self._offset_x + ping * self._zoom
                x1 = x0 + self._zoom
                y0 = self._offset_y + start * self._zoom
                y1 = self._offset_y + end * self._zoom
                glBegin(GL_QUADS)
                glVertex2f(x0, y0); glVertex2f(x1, y0)
                glVertex2f(x1, y1); glVertex2f(x0, y1)
                glEnd()

        # 边界线
        glColor4f(0.0, 1.0, 0.0, 0.8)
        glLineWidth(1.0)
        for y in range(h):
            for x in range(w):
                if not mask[y, x]:
                    continue
                if x == w - 1 or not mask[y, x + 1]:
                    px = self._offset_x + (x + 1) * self._zoom
                    y0 = self._offset_y + y * self._zoom
                    glBegin(GL_LINES)
                    glVertex2f(px, y0); glVertex2f(px, y0 + self._zoom)
                    glEnd()
                if y == h - 1 or not mask[y + 1, x]:
                    py = self._offset_y + (y + 1) * self._zoom
                    x0 = self._offset_x + x * self._zoom
                    glBegin(GL_LINES)
                    glVertex2f(x0, py); glVertex2f(x0 + self._zoom, py)
                    glEnd()

    def _draw_selection_rect(self) -> None:
        """半透明蓝色框选矩形"""
        if not (self._select_start and self._select_end):
            return
        x0, y0 = self._select_start
        x1, y1 = self._select_end
        glColor4f(0.2, 0.4, 1.0, 0.3)
        glBegin(GL_QUADS)
        glVertex2f(x0, y0); glVertex2f(x1, y0)
        glVertex2f(x1, y1); glVertex2f(x0, y1)
        glEnd()
        glColor4f(0.2, 0.4, 1.0, 0.8)
        glLineWidth(1.5)
        glBegin(GL_LINE_STRIP)
        glVertex2f(x0, y0); glVertex2f(x1, y0)
        glVertex2f(x1, y1); glVertex2f(x0, y1)
        glVertex2f(x0, y0)
        glEnd()

    # ── 鼠标交互 ──────────────────────────────────────────────

    def wheelEvent(self, event: QWheelEvent) -> None:
        pos = event.position()
        sx, sy = float(pos.x()), float(pos.y())
        data_x = (sx - self._offset_x) / self._zoom
        data_y = (sy - self._offset_y) / self._zoom
        delta = event.angleDelta().y()
        factor = 1.15 if delta > 0 else 1.0 / 1.15
        self._zoom = max(0.05, min(50.0, self._zoom * factor))
        self._offset_x = sx - data_x * self._zoom
        self._offset_y = sy - data_y * self._zoom
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
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
        sx, sy = float(event.x()), float(event.y())
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
        if event.button() == Qt.MiddleButton:
            self._panning = False
            self._pan_start = None
            self.setCursor(Qt.ArrowCursor)
        elif event.button() == Qt.LeftButton and self._selecting:
            self._selecting = False
            if self._select_start and self._select_end:
                x0, y0 = self._screen_to_data(*self._select_start)
                x1, y1 = self._screen_to_data(*self._select_end)
                self.region_selected.emit(
                    min(x0, x1), min(y0, y1),
                    max(x0, x1), max(y0, y1),
                )
            self._select_start = None
            self._select_end = None
            self.update()

    # ── 坐标转换 ──────────────────────────────────────────────

    def _screen_to_data(self, sx: float, sy: float) -> tuple:
        """屏幕坐标 → 数据坐标 (ping_index, sample_index)"""
        return (sx - self._offset_x) / self._zoom, (sy - self._offset_y) / self._zoom

    # ── 视图控制 ──────────────────────────────────────────────

    def reset_view(self) -> None:
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
        """找到布尔数组中 True 的连续区间"""
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
