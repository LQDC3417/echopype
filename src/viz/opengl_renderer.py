"""OpenGL Echogram 渲染器

高性能 echogram 渲染，支持缩放、平移、叠加层与框选交互。
依赖: PyOpenGL, matplotlib, numpy, PySide6

数据约定 (参照 Echoview):
- Sv 数据: (n_pings, n_samples) — ping 为横轴(X), range_sample 为纵轴(Y)
- 纹理: (n_samples, n_pings, 4) — 转置后上传
- 屏幕坐标: X=ping (左→右), Y=depth (上=表面, 下=水底)
- 独立 X/Y 缩放, 自动保持数据纵横比
"""

import logging

import numpy as np
from matplotlib import cm
from OpenGL.GL import (
    GL_BLEND,
    GL_CLAMP_TO_EDGE,
    GL_COLOR_BUFFER_BIT,
    GL_DEPTH_BUFFER_BIT,
    GL_LINE_SMOOTH,
    GL_LINE_SMOOTH_HINT,
    GL_LINE_STIPPLE,
    GL_LINE_STRIP,
    GL_LINEAR,
    GL_LINES,
    GL_MAX_TEXTURE_SIZE,
    GL_MODELVIEW,
    GL_NEAREST,
    GL_NICEST,
    GL_ONE_MINUS_SRC_ALPHA,
    GL_PROJECTION,
    GL_QUADS,
    GL_RGBA,
    GL_SRC_ALPHA,
    GL_TEXTURE_2D,
    GL_TEXTURE_MAG_FILTER,
    GL_TEXTURE_MIN_FILTER,
    GL_TEXTURE_WRAP_S,
    GL_TEXTURE_WRAP_T,
    GL_UNPACK_ALIGNMENT,
    GL_UNSIGNED_BYTE,
    glBegin,
    glBindTexture,
    glBlendFunc,
    glClear,
    glClearColor,
    glColor4f,
    glDisable,
    glEnable,
    glEnd,
    glGenTextures,
    glGetIntegerv,
    glHint,
    glLineStipple,
    glLineWidth,
    glLoadIdentity,
    glMatrixMode,
    glOrtho,
    glPixelStorei,
    glTexCoord2f,
    glTexImage2D,
    glTexParameteri,
    glVertex2f,
    glViewport,
)

logger = logging.getLogger(__name__)

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QWheelEvent
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtWidgets import QMenu

from src.gui.toolbars import MouseMode


class EchogramRenderer(QOpenGLWidget):
    """OpenGL Echogram 渲染器"""

    mouse_moved = Signal(float, float)  # (ping_index, sample_index)
    region_selected = Signal(float, float, float, float)
    bottom_line_edited = Signal(object)  # np.ndarray — 编辑后的底线
    sv_at_cursor = Signal(float, float, float)  # (ping, depth, sv_value)
    surface_line_requested = Signal()  # 右键请求设置表线
    analysis_region_toggle = Signal(bool)  # 分析区域限定开关
    re_detect_bottom = Signal()  # 重新检测底部
    update_bottom_requested = Signal()  # 手动更新/保存当前底线
    file_page_requested = Signal(int)  # delta: -1=上一页, +1=下一页
    zoom_changed = Signal(float, float)  # (zoom_x, zoom_y)

    MAX_TEX_SIZE_FALLBACK = 16384  # GPU 查询失败时的保底值

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(200, 200)

        # 数据: (n_pings, n_samples)
        self._sv_data = None
        self._noise_mask = None
        self._bottom_line = None  # (n_pings,) sample indices
        self._surface_line = None  # float — 表线深度(in sample index units)
        self._school_mask = None

        # 网格叠加
        self._grid_cells = None   # list[dict] — ping_start/end, depth_lo/hi (sample index)
        self._grid_values = None  # np.ndarray — 每格的着色值（如 mean_sv）
        self._grid_vmin = -70.0
        self._grid_vmax = -20.0

        # ??????????
        self._bottom_line_color = (0.8, 0.6, 0.0, 1.0)  # ???
        self._bottom_line_width = 2.0
        self._surface_line_color = (0.2, 1.0, 0.4, 0.8)  # ???
        self._surface_line_width = 1.5
        self._preview_line_color = (1.0, 0.5, 0.0, 0.8)  # ??
        self._preview_line_width = 2.0
        
        # ??????
        self._draw_precision = 1.0  # ???????1.0?????
        self._smooth_window_size = 5  # ??????
        self._enable_smoothing = True  # ????????



        # 鼠标模式
        self._mouse_mode = MouseMode.NAVIGATE

        # 底线编辑状态
        self._bottom_editing = False
        self._bottom_drawing = False  # 是否正在按住左键绘制
        self._bottom_draw_points = []  # 手绘模式收集的点 [(ping, sample), ...]
        self._bottom_undo_stack = []  # ????????????
        self._bottom_redo_stack = []  # ?????????????
        self._max_undo_steps = 50  # ??????


        # 颜色映射
        self._cmap_name = "jet"
        self._vmin = -70.0
        self._vmax = -20.0

        # 纹理
        self._texture_id = 0
        self._texture_dirty = True
        self._tex_w = 0
        self._tex_h = 0
        self._downsample_x = 1
        self._downsample_y = 1

        # 视口变换
        self._offset_x = 0.0
        self._offset_y = 0.0
        self._zoom_x = 1.0
        self._zoom_y = 1.0
        self._max_tex_size = self.MAX_TEX_SIZE_FALLBACK  # initializeGL 后更新为 GPU 真实值

        # 鼠标状态
        self._panning = False
        self._pan_start = None
        self._selecting = False
        self._select_start = None
        self._select_end = None

        # 数据尺寸
        self._n_pings = 0
        self._n_samples = 0

        # 通道信息叠加
        self._channel_text = ""
        self._analysis_region_enabled = False

        # 启用鼠标追踪（用于悬停检测）
        self.setMouseTracking(True)

        # 右键菜单通过 contextMenuEvent 处理

    def _emit_prev_page(self):
        self.file_page_requested.emit(-1)

    def _emit_next_page(self):
        self.file_page_requested.emit(1)

    # ── 数据设置 ──────────────────────────────────────────────

    def set_data(self, sv_data: np.ndarray) -> None:
        self._sv_data = sv_data.astype(np.float32)
        self._n_pings = sv_data.shape[0]
        self._n_samples = sv_data.shape[1]
        self._texture_dirty = True
        self._fit_to_view()
        self.update()

    def set_noise_mask(self, mask) -> None:
        if mask is None:
            self._noise_mask = None
        else:
            self._noise_mask = mask.astype(bool)
        self.update()

    def set_bottom_line(self, bottom: np.ndarray | None) -> None:
        if bottom is None:
            self._bottom_line = None
        else:
            self._bottom_line = np.asarray(bottom, dtype=np.float32)
        self.update()

    def get_bottom_line(self) -> np.ndarray | None:
        """获取当前底线数据（只读副本）"""
        if self._bottom_line is None:
            return None
        return self._bottom_line.copy()

    def set_surface_line(self, depth_samples: float) -> None:
        """设置表线深度（sample index 单位），None 表示关闭"""
        self._surface_line = depth_samples
        self.update()

    def set_school_mask(self, mask) -> None:
        if mask is None:
            self._school_mask = None
        else:
            self._school_mask = mask.astype(bool)
        self.update()

    def set_grid_data(self, grid_df, ds_Sv=None, color_by: str = "mean_sv") -> None:
        """设置网格叠加数据。

        Parameters
        ----------
        grid_df : pd.DataFrame
            网格分析结果，含 ping_start/end, depth_lo/hi, mean_sv 等列
        ds_Sv : xr.Dataset, optional
            用于将深度米转换为 sample index
        color_by : str
            着色指标列名，默认 "mean_sv"
        """
        if grid_df is None or grid_df.empty:
            self._grid_cells = None
            self._grid_values = None
            self.update()
            return

        cells = []
        values = []

        # 尝试获取深度→sample 转换信息
        echo_range = None
        if ds_Sv is not None and "echo_range" in ds_Sv:
            echo_range = ds_Sv["echo_range"].values
            if echo_range.ndim == 2:
                echo_range = echo_range[0]  # 取第一 ping

        for _, row in grid_df.iterrows():
            ping_start = int(row["ping_start"])
            ping_end = int(row["ping_end"])

            # 深度 → sample index 转换
            if echo_range is not None:
                depth_lo = float(row["depth_lo"])
                depth_hi = float(row["depth_hi"])
                sample_start = int(np.searchsorted(echo_range, depth_lo))
                sample_end = int(np.searchsorted(echo_range, depth_hi))
            else:
                # 无除数据时用 ping_start/end 直接作为索引
                sample_start = int(row.get("depth_lo", 0))
                sample_end = int(row.get("depth_hi", self._n_samples))

            cells.append({
                "ping_start": ping_start,
                "ping_end": ping_end,
                "sample_start": sample_start,
                "sample_end": sample_end,
            })
            values.append(float(row.get(color_by, 0)))

        self._grid_cells = cells
        self._grid_values = np.array(values, dtype=np.float32)
        if len(values) > 0:
            self._grid_vmin = float(np.nanmin(self._grid_values))
            self._grid_vmax = float(np.nanmax(self._grid_values))
            if self._grid_vmin == self._grid_vmax:
                self._grid_vmax = self._grid_vmin + 1.0
        self.update()

    def clear_grid_overlay(self) -> None:
        """清除网格叠加"""
        self._grid_cells = None
        self._grid_values = None
        self.update()

    def set_colormap(self, name: str = "jet", vmin: float = -70.0, vmax: float = -20.0) -> None:
        self._cmap_name = "gray" if name == "grayscale" else name
        self._vmin = vmin
        self._vmax = vmax
        self._texture_dirty = True
        self.update()

    def set_channel_info(self, text: str) -> None:
        """设置频率/通道信息叠加文字"""
        self._channel_text = text
        self.update()

    def set_mouse_mode(self, mode) -> None:
        # 支持 int 和 MouseMode 两种输入
        if isinstance(mode, int):
            mode = MouseMode(mode)
        self._mouse_mode = mode
        # 退出正在进行的编辑
        if mode != MouseMode.DRAW_BOTTOM:
            self._bottom_draw_points.clear()
            self._bottom_editing = False
            self._bottom_drawing = False

    def set_analysis_region_enabled(self, enabled: bool) -> None:
        """设置分析区域限定标志"""
        self._analysis_region_enabled = enabled
        self.update()


    def initializeGL(self) -> None:
        glClearColor(1.0, 1.0, 1.0, 1.0)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
        
        # ???????
        glEnable(GL_LINE_SMOOTH)
        glHint(GL_LINE_SMOOTH_HINT, GL_NICEST)
        
        self._texture_id = int(glGenTextures(1))
        # ?? GPU ???????????
        max_size = glGetIntegerv(GL_MAX_TEXTURE_SIZE)
        self._max_tex_size = int(max_size) if max_size else self.MAX_TEX_SIZE_FALLBACK

    def resizeGL(self, w: int, h: int) -> None:
        glViewport(0, 0, w, h)

    def paintGL(self) -> None:
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        if self._sv_data is None:
            return

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
        if self._surface_line is not None:
            self._draw_surface_line()
        if self._school_mask is not None:
            self._draw_school_overlay()
        if self._grid_cells is not None:
            self._draw_grid_overlay()
        if self._selecting and self._select_start and self._select_end:
            self._draw_selection_rect()

        # 底线绘制预览
        if self._bottom_draw_points:
            self._draw_bottom_preview()

        # 叠加信息文字
        if self._channel_text or self._cmap_name:
            self._draw_overlay_text()

        # 右侧渐变色图例（colorbar）
        if self._sv_data is not None:
            self._draw_colorbar()

    # ── 纹理生成与渲染 ────────────────────────────────────────

    def _sv_to_rgba(self, ping_start: int = 0, ping_end: int = -1,
                    sample_start: int = 0, sample_end: int = -1) -> np.ndarray:
        """Sv 数据 → RGBA 纹理数组。

        (n_pings, n_samples) → 转置 → (n_samples, n_pings, 4)
        仅转置，不做 flipud。OpenGL 纹理坐标 (0,0) 位于 quad 顶部，
        对应 sample=0（水面附近），纹理坐标 (1,1) 对应最深 sample。

        Parameters
        ----------
        ping_start, ping_end : int
            Ping 范围（用于视口裁剪）
        sample_start, sample_end : int
            Sample 范围（用于视口裁剪）
        """
        # 视口裁剪：仅处理可见区域
        if ping_end < 0:
            ping_end = self._n_pings
        if sample_end < 0:
            sample_end = self._n_samples

        # 边界检查
        ping_start = max(0, min(ping_start, self._n_pings))
        ping_end = max(ping_start, min(ping_end, self._n_pings))
        sample_start = max(0, min(sample_start, self._n_samples))
        sample_end = max(sample_start, min(sample_end, self._n_samples))

        # 裁剪数据
        data_slice = self._sv_data[ping_start:ping_end, sample_start:sample_end]

        # matplotlib ≥3.7 推荐 colormaps[name]，回退兼容旧版
        try:
            from matplotlib import colormaps
            cmap = colormaps[self._cmap_name]
        except (ImportError, AttributeError):
            cmap = cm.get_cmap(self._cmap_name)
        data_T = data_slice.T
        span = self._vmax - self._vmin
        if span == 0:
            span = 1.0
        norm = np.clip((data_T - self._vmin) / span, 0, 1)
        rgba = cmap(norm)
        return (rgba * 255).astype(np.uint8)

    def _upload_texture(self) -> None:
        if self._sv_data is None:
            return
        rgba = self._sv_to_rgba()
        tex_h, tex_w = rgba.shape[:2]
        self._downsample_x = 1
        self._downsample_y = 1
        if tex_w > self._max_tex_size:
            self._downsample_x = int(np.ceil(tex_w / self._max_tex_size))
        if tex_h > self._max_tex_size:
            self._downsample_y = int(np.ceil(tex_h / self._max_tex_size))
        if self._downsample_x > 1 or self._downsample_y > 1:
            rgba = rgba[::self._downsample_y, ::self._downsample_x]
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
        if self._texture_dirty:
            self._upload_texture()
        glBindTexture(GL_TEXTURE_2D, self._texture_id)
        glEnable(GL_TEXTURE_2D)
        sx = self._offset_x
        sy = self._offset_y
        sw = self._n_pings * self._zoom_x
        sh = self._n_samples * self._zoom_y
        glColor4f(1.0, 1.0, 1.0, 1.0)
        glBegin(GL_QUADS)
        glTexCoord2f(0, 0); glVertex2f(sx, sy)
        glTexCoord2f(1, 0); glVertex2f(sx + sw, sy)
        glTexCoord2f(1, 1); glVertex2f(sx + sw, sy + sh)
        glTexCoord2f(0, 1); glVertex2f(sx, sy + sh)
        glEnd()
        glDisable(GL_TEXTURE_2D)

    # ── 坐标转换 ──────────────────────────────────────────────

    def _data_to_screen(self, ping_idx: float, sample_idx: float) -> tuple:
        sx = self._offset_x + ping_idx * self._zoom_x
        sy = self._offset_y + sample_idx * self._zoom_y
        return sx, sy

    def _screen_to_data(self, sx: float, sy: float) -> tuple:
        px = (sx - self._offset_x) / self._zoom_x
        py = (sy - self._offset_y) / self._zoom_y
        return px, py

    def _get_sv_at(self, ping: int, sample: int) -> float:
        if self._sv_data is None:
            return float('nan')
        if 0 <= ping < self._n_pings and 0 <= sample < self._n_samples:
            return float(self._sv_data[ping, sample])
        return float('nan')

    # ── 叠加层渲染 ────────────────────────────────────────────

    def _draw_noise_overlay(self) -> None:
        mask = self._noise_mask
        if mask is None:
            return
        glColor4f(0.3, 0.3, 0.3, 0.5)
        h, w = mask.shape
        # 批量收集所有 quad 顶点
        verts = []
        for ping in range(h):
            row = mask[ping, :]
            if not np.any(row):
                continue
            x0 = self._offset_x + ping * self._zoom_x
            x1 = x0 + self._zoom_x
            for start, end in self._find_runs(row):
                y0 = self._offset_y + start * self._zoom_y
                y1 = self._offset_y + end * self._zoom_y
                verts.extend([(x0,y0),(x1,y0),(x1,y1),(x0,y1)])
        if verts:
            glBegin(GL_QUADS)
            for v in verts:
                glVertex2f(v[0], v[1])
            glEnd()

    def _draw_bottom_line(self) -> None:
        """???? ? ???????????????"""
        bl = self._bottom_line
        if bl is None or bl.ndim == 0:
            return
        
        # ?????????????????????
        base_width = 2.0
        zoom_factor = min(self._zoom_x, self._zoom_y)
        line_width = base_width * min(2.0, max(0.5, zoom_factor * 0.5))
        
        # ?????????Echoview ??
        glColor4f(0.8, 0.6, 0.0, 1.0)
        glLineWidth(line_width)
        
        # ??GL_LINE_STRIP??????
        glBegin(GL_LINE_STRIP)
        for i, val in enumerate(bl):
            if np.isnan(val):
                # ??NaN???????????????
                glEnd()
                glBegin(GL_LINE_STRIP)
                continue
            x = self._offset_x + i * self._zoom_x
            y = self._offset_y + val * self._zoom_y
            glVertex2f(x, y)
        glEnd()

    def _draw_surface_line(self) -> None:
        """???? ? ???????????????"""
        sl = self._surface_line
        if sl is None:
            return
        
        # ?????????????
        base_width = 1.5
        zoom_factor = min(self._zoom_x, self._zoom_y)
        line_width = base_width * min(2.0, max(0.5, zoom_factor * 0.5))
        
        # ??????
        glEnable(GL_LINE_STIPPLE)
        glLineStipple(4, 0x0F0F)  # ?????4?????0x0F0F??
        
        # ????????????
        glColor4f(0.2, 1.0, 0.4, 0.8)
        glLineWidth(line_width)
        
        # ???????????
        y = self._offset_y + sl * self._zoom_y
        x0 = self._offset_x
        x1 = self._offset_x + self._n_pings * self._zoom_x
        
        # ??????
        glBegin(GL_LINES)
        glVertex2f(x0, y)
        glVertex2f(x1, y)
        glEnd()
        
        glDisable(GL_LINE_STIPPLE)

    def _draw_grid_overlay(self) -> None:
        """绘制网格单元叠加（半透明彩色矩形 + 边框）"""
        if not self._grid_cells or self._grid_values is None:
            return

        try:
            from matplotlib import colormaps
            cmap = colormaps[self._cmap_name]
        except (ImportError, AttributeError):
            from matplotlib import cm
            cmap = cm.get_cmap(self._cmap_name)

        span = self._grid_vmax - self._grid_vmin
        if span == 0:
            span = 1.0

        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        # 绘制填充矩形（半透明）
        glBegin(GL_QUADS)
        for i, cell in enumerate(self._grid_cells):
            val = self._grid_values[i]
            norm = np.clip((val - self._grid_vmin) / span, 0, 1)
            r, g, b, _ = cmap(norm)
            glColor4f(r, g, b, 0.35)

            x0 = self._offset_x + cell["ping_start"] * self._zoom_x
            x1 = self._offset_x + cell["ping_end"] * self._zoom_x
            y0 = self._offset_y + cell["sample_start"] * self._zoom_y
            y1 = self._offset_y + cell["sample_end"] * self._zoom_y

            glVertex2f(x0, y0)
            glVertex2f(x1, y0)
            glVertex2f(x1, y1)
            glVertex2f(x0, y1)
        glEnd()

        # 绘制边框（深色实线）
        glColor4f(0.2, 0.2, 0.2, 0.6)
        glLineWidth(1.0)
        glBegin(GL_LINES)
        for cell in self._grid_cells:
            x0 = self._offset_x + cell["ping_start"] * self._zoom_x
            x1 = self._offset_x + cell["ping_end"] * self._zoom_x
            y0 = self._offset_y + cell["sample_start"] * self._zoom_y
            y1 = self._offset_y + cell["sample_end"] * self._zoom_y
            # 上
            glVertex2f(x0, y0); glVertex2f(x1, y0)
            # 下
            glVertex2f(x0, y1); glVertex2f(x1, y1)
            # 左
            glVertex2f(x0, y0); glVertex2f(x0, y1)
            # 右
            glVertex2f(x1, y0); glVertex2f(x1, y1)
        glEnd()

    def _draw_bottom_preview(self) -> None:
        """???????? ? ??????????"""
        if not self._bottom_draw_points:
            return
        
        # ??????????
        points = self._smooth_draw_points(self._bottom_draw_points, window_size=3)
        
        # ??????????????
        base_width = 2.0
        zoom_factor = min(self._zoom_x, self._zoom_y)
        line_width = base_width * min(2.0, max(0.5, zoom_factor * 0.5))
        
        # ???????????
        glColor4f(1.0, 0.5, 0.0, 0.8)
        glLineWidth(line_width)
        
        # ?????????
        glBegin(GL_LINE_STRIP)
        for ping, sample in points:
            x = self._offset_x + ping * self._zoom_x
            y = self._offset_y + sample * self._zoom_y
            glVertex2f(x, y)
        glEnd()

    def _draw_school_overlay(self) -> None:
        mask = self._school_mask
        if mask is None:
            return
        h, w = mask.shape  # (n_pings, n_samples)
        # 填充半透明绿色
        glColor4f(0.0, 1.0, 0.0, 0.25)
        glBegin(GL_QUADS)
        for ping in range(h):
            row = mask[ping, :]
            if not np.any(row):
                continue
            for start, end in self._find_runs(row):
                x0 = self._offset_x + ping * self._zoom_x
                x1 = x0 + self._zoom_x
                y0 = self._offset_y + start * self._zoom_y
                y1 = self._offset_y + end * self._zoom_y
                glVertex2f(x0, y0); glVertex2f(x1, y0)
                glVertex2f(x1, y1); glVertex2f(x0, y1)
        glEnd()
        # 边界线条 — 批量绘制
        self._draw_school_boundaries(mask, h, w)

    def _draw_school_boundaries(self, mask, h, w) -> None:
        """绘制鱼群边界线条 — 向量化边界检测，Echoview 风格深色边界"""
        # 向量化检测边界（避免 Python 双重循环）
        # 下边界：mask 为 True 且下方为 False 或越界
        bottom_edge = mask.copy()
        bottom_edge[:-1, :] &= ~mask[1:, :]
        # 右边界：mask 为 True 且右方为 False 或越界
        right_edge = mask.copy()
        right_edge[:, :-1] &= ~mask[:, 1:]

        # 提取边界坐标
        bottom_pings, bottom_samples = np.where(bottom_edge)
        right_pings, right_samples = np.where(right_edge)

        glColor4f(0.0, 0.5, 0.0, 0.9)
        glLineWidth(1.5)
        glBegin(GL_LINES)
        # 下边界线段
        for i in range(len(bottom_pings)):
            p, s = int(bottom_pings[i]), int(bottom_samples[i])
            py = self._offset_y + (s + 1) * self._zoom_y
            x0 = self._offset_x + p * self._zoom_x
            x1 = x0 + self._zoom_x
            glVertex2f(x0, py); glVertex2f(x1, py)
        # 右边界线段
        for i in range(len(right_pings)):
            p, s = int(right_pings[i]), int(right_samples[i])
            px = self._offset_x + (p + 1) * self._zoom_x
            y0 = self._offset_y + s * self._zoom_y
            glVertex2f(px, y0); glVertex2f(px, y0 + self._zoom_y)
        glEnd()

    def _draw_selection_rect(self) -> None:
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
        data_x, data_y = self._screen_to_data(sx, sy)
        delta = event.angleDelta().y()
        factor = 1.15 if delta > 0 else 1.0 / 1.15
        self._zoom_x = max(0.01, min(100.0, self._zoom_x * factor))
        self._zoom_y = max(0.01, min(100.0, self._zoom_y * factor))
        self._offset_x = sx - data_x * self._zoom_x
        self._offset_y = sy - data_y * self._zoom_y
        self.zoom_changed.emit(self._zoom_x, self._zoom_y)
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        sx, sy = float(event.x()), float(event.y())

        if event.button() == Qt.MiddleButton:
            self._panning = True
            self._pan_start = (sx, sy)
            self.setCursor(Qt.ClosedHandCursor)
            return

        if event.button() == Qt.LeftButton:
            if self._mouse_mode == MouseMode.NAVIGATE or self._mouse_mode == MouseMode.SELECT_NOISE or self._mouse_mode == MouseMode.INSPECT:
                self._selecting = True
                self._select_start = (sx, sy)
                self._select_end = (sx, sy)

            elif self._mouse_mode == MouseMode.DRAW_BOTTOM:
                # 开始自由手绘
                self._bottom_drawing = True
                self._bottom_editing = True
                # 保存当前底线状态到撤销栈
                self._save_bottom_undo()
                # 添加第一个绘制点
                px, py = self._screen_to_data(sx, sy)
                self._bottom_draw_points.append((px, py))
                self.setCursor(Qt.CrossCursor)
                self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        sx, sy = float(event.x()), float(event.y())
        data_x, data_y = self._screen_to_data(sx, sy)
        self.mouse_moved.emit(data_x, data_y)

        # 发射 Sv 值
        ping_idx = int(round(data_x))
        sample_idx = int(round(data_y))
        sv_val = self._get_sv_at(ping_idx, sample_idx)
        self.sv_at_cursor.emit(data_x, data_y, sv_val)

        # 自由手绘中 — 持续收集采样点
        if self._bottom_drawing and self._mouse_mode == MouseMode.DRAW_BOTTOM:
            px, py = self._screen_to_data(sx, sy)
            # 限制在数据范围内
            py = max(0, min(self._n_samples - 1, py))
            self._bottom_draw_points.append((px, py))
            self.update()
            return

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

        elif event.button() == Qt.LeftButton:
            # 自由手绘结束 — 应用绘制结果
            if self._bottom_drawing and self._mouse_mode == MouseMode.DRAW_BOTTOM:
                self._bottom_drawing = False
                self.setCursor(Qt.ArrowCursor)
                # 应用手绘到底线（分段替换）
                if self._bottom_draw_points:
                    self._apply_drawn_segment()
                return

            if self._selecting:
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

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        # 双击不触发特殊行为（使用右键菜单完成绘制）
        pass

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            # ??????
            self._bottom_draw_points.clear()
            self._bottom_editing = False
            self._bottom_drawing = False
            self.update()
        elif event.key() == Qt.Key_Z and event.modifiers() & Qt.ControlModifier:
            # Ctrl+Z ??????
            self._undo_bottom()
        elif event.key() == Qt.Key_Y and event.modifiers() & Qt.ControlModifier:
            # Ctrl+Y ??????
            self._redo_bottom()

    def contextMenuEvent(self, event) -> None:
        """Qt 右键事件 → 显示上下文菜单"""
        self._show_context_menu(event.pos())

    def _show_context_menu(self, pos) -> None:
        """显示右键菜单"""
        menu = QMenu(self)
        menu.addAction("🔄 重置视图", self.reset_view)
        menu.addAction("⬜ 适应窗口", self._fit_to_view_and_update)
        menu.addSeparator()

        # ── 翻页 ──
        act_prev = menu.addAction("◀ 上一页")
        act_prev.triggered.connect(self._emit_prev_page)
        act_next = menu.addAction("▶ 下一页")
        act_next.triggered.connect(self._emit_next_page)
        menu.addSeparator()

        # 显示当前位置信息
        sx, sy = float(pos.x()), float(pos.y())
        px, py = self._screen_to_data(sx, sy)
        ping_idx = int(round(px))
        sample_idx = int(round(py))
        sv_val = self._get_sv_at(ping_idx, sample_idx)
        if not np.isnan(sv_val):
            menu.addAction(f"📍 Ping: {ping_idx} | Sample: {sample_idx} | Sv: {sv_val:.1f} dB").setEnabled(False)
            menu.addSeparator()

        # ── 表线 / 分析区域 ──
        menu.addAction("📏 设置表线深度...", lambda: self.surface_line_requested.emit())
        act_analysis = menu.addAction("📐 限定分析区域（表线~底线）")
        act_analysis.setCheckable(True)
        act_analysis.setChecked(self._analysis_region_enabled)
        act_analysis.triggered.connect(
            lambda checked: self.analysis_region_toggle.emit(checked)
        )
        menu.addSeparator()

        menu.addAction("🔍 重新检测底部", lambda: self.re_detect_bottom.emit())

        # ── 更新底线（有底线时始终可见）──
        if self._bottom_line is not None:
            menu.addAction("💾 更新底线", lambda: self.update_bottom_requested.emit())

        # ── 底线绘制模式菜单 ──
        if self._mouse_mode == MouseMode.DRAW_BOTTOM:
            menu.addSeparator()
            if self._bottom_draw_points:
                menu.addAction("✅ 完成绘制", self._finish_bottom_drawing)
                menu.addAction("🗑 清除绘制点", self._clear_bottom_drawing)
            if self._bottom_undo_stack:
                menu.addAction("↩ 撤销 (Ctrl+Z)", self._undo_bottom)

        menu.exec_(self.mapToGlobal(pos))

    # ── 底线编辑 ──────────────────────────────────────────────

    def _save_bottom_undo(self):
        """???????????????????"""
        if self._bottom_line is not None:
            # ??????????
            self._bottom_undo_stack.append(self._bottom_line.copy())
            
            # ???????
            if len(self._bottom_undo_stack) > self._max_undo_steps:
                self._bottom_undo_stack.pop(0)
            
            # ????????????????????
            self._bottom_redo_stack.clear()

    def _undo_bottom(self):
        """??????????????????"""
        if not self._bottom_undo_stack:
            return
        
        # ??????????
        if self._bottom_line is not None:
            self._bottom_redo_stack.append(self._bottom_line.copy())
        
        # ????????
        self._bottom_line = self._bottom_undo_stack.pop()
        self._bottom_draw_points.clear()
        self._bottom_editing = False
        self.bottom_line_edited.emit(self._bottom_line.copy())
        self.update()

    def _redo_bottom(self):
        """???????????????"""
        if not self._bottom_redo_stack:
            return
        
        # ??????????
        if self._bottom_line is not None:
            self._bottom_undo_stack.append(self._bottom_line.copy())
        
        # ????????
        self._bottom_line = self._bottom_redo_stack.pop()
        self._bottom_draw_points.clear()
        self._bottom_editing = False
        self.bottom_line_edited.emit(self._bottom_line.copy())
        self.update()

    def _smooth_draw_points(self, points, window_size=None):
        """???????????????"""
        # ???????????
        if window_size is None:
            window_size = self._smooth_window_size
        
        # ?????????????????
        if not self._enable_smoothing:
            return points
        
        # ????????????
        adjusted_window = max(3, int(window_size * self._draw_precision))
        
        if len(points) < adjusted_window:
            return points
        
        # ??????????
        smoothed = []
        for i in range(len(points)):
            # ??????
            start = max(0, i - adjusted_window // 2)
            end = min(len(points), i + adjusted_window // 2 + 1)
            
            # ??????????
            avg_ping = sum(p[0] for p in points[start:end]) / (end - start)
            avg_sample = sum(p[1] for p in points[start:end]) / (end - start)
            smoothed.append((avg_ping, avg_sample))
        
        return smoothed

    def _apply_drawn_segment(self):
        """????????????????"""
        if not self._bottom_draw_points:
            return
        
        # ???????????????
        points = self._smooth_draw_points(self._bottom_draw_points, window_size=5)
        
        if len(points) < 2:
            self._bottom_draw_points.clear()
            return
        
        # ??????? Ping ??
        pings = [p[0] for p in points]
        ping_min = max(0, int(round(min(pings))))
        ping_max = min(self._n_pings - 1, int(round(max(pings))))
        
        if ping_min > ping_max:
            self._bottom_draw_points.clear()
            return
        
        # ????????????
        if self._bottom_line is None:
            self._bottom_line = np.full(self._n_pings, np.nan, dtype=np.float32)
        
        # ????? ping ??
        sorted_points = sorted(points, key=lambda p: p[0])
        
        # ????????????????
        for ping_idx in range(ping_min, ping_max + 1):
            # ?? ping_idx ????????????
            left = None
            right = None
            for i, (p, s) in enumerate(sorted_points):
                if p <= ping_idx:
                    left = (p, s, i)
                if p >= ping_idx and right is None:
                    right = (p, s, i)
            
            if left is not None and right is not None:
                if left[2] == right[2]:
                    # ????
                    self._bottom_line[ping_idx] = left[1]
                else:
                    # ????
                    t = (ping_idx - left[0]) / max(1e-6, right[0] - left[0])
                    self._bottom_line[ping_idx] = left[1] + t * (right[1] - left[1])
            elif left is not None:
                self._bottom_line[ping_idx] = left[1]
            elif right is not None:
                self._bottom_line[ping_idx] = right[1]
        
        # ?????
        self._bottom_draw_points.clear()
        self._bottom_editing = False
        
        # ??????
        self.bottom_line_edited.emit(self._bottom_line.copy())
        self.update()

    def _finish_bottom_drawing(self):
        """完成手绘底线（右键菜单调用）"""
        if self._bottom_draw_points:
            self._apply_drawn_segment()

    def _clear_bottom_drawing(self):
        """清除当前绘制点"""
        self._bottom_draw_points.clear()
        self._bottom_editing = False
        self._bottom_drawing = False
        self.update()

    def _draw_overlay_text(self):
        """在左上角渲染叠加文字"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        font = QFont("Segoe UI", 10, QFont.Bold)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255, 200))

        y = 22
        if self._channel_text:
            painter.drawText(10, y, self._channel_text)
            y += 20
        if self._cmap_name:
            painter.drawText(10, y, f"Colormap: {self._cmap_name}  [{self._vmin:.0f}, {self._vmax:.0f}] dB")
        painter.end()

    def _draw_colorbar(self) -> None:
        """在 echogram 右侧绘制渐变色图例（colorbar）

        布局：
        - 色条位于右侧边缘，与 echogram 等高
        - 右侧标注刻度值（Sv dB）
        """
        if self._sv_data is None:
            return

        # ── 布局参数 ──
        margin_right = 55   # 色条右侧留给刻度文字的宽度
        bar_width = 20      # 色条宽度（像素）
        bar_margin = 8      # 色条与 echogram 右边缘的间距

        w = self.width()
        h = self.height()

        # 色条位置：紧贴 echogram 右侧
        bar_x = self._offset_x + self._n_pings * self._zoom_x + bar_margin
        bar_y = self._offset_y
        bar_h = self._n_samples * self._zoom_y

        # 安全裁剪：确保色条不超出窗口
        bar_x = max(bar_x, 0)
        if bar_x + bar_width > w - margin_right:
            return  # 空间不足，跳过绘制

        # ── 获取 colormap ──
        try:
            from matplotlib import colormaps
            cmap = colormaps[self._cmap_name]
        except (ImportError, AttributeError):
            cmap = cm.get_cmap(self._cmap_name)

        # ── 用 QPainter 绘制渐变色条（比逐像素 OpenGL quad 更简洁）──
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 绘制渐变色条：从上到下，采样 colormap
        n_steps = max(int(bar_h), 1)
        for i in range(n_steps):
            # 归一化坐标：top=vmax, bottom=vmin（与 echogram Y 轴一致）
            t = 1.0 - i / max(n_steps - 1, 1)  # 顶部=1(vmax), 底部=0(vmin)
            r, g, b, _ = cmap(t)
            painter.setPen(QColor(int(r * 255), int(g * 255), int(b * 255)))
            painter.drawLine(int(bar_x), int(bar_y + i), int(bar_x + bar_width), int(bar_y + i))

        # ── 绘制刻度文字 ──
        font = QFont("Segoe UI", 9)
        painter.setFont(font)
        painter.setPen(QColor(0, 0, 0))  # 黑色文字

        # 自动计算刻度数量（目标每 60~80 像素一个刻度）
        target_spacing = 70
        n_ticks = max(2, min(10, int(bar_h / target_spacing) + 1))

        for i in range(n_ticks):
            t = i / (n_ticks - 1)  # 0=底部(vmin), 1=顶部(vmax)
            value = self._vmin + t * (self._vmax - self._vmin)
            tick_y = bar_y + bar_h - t * bar_h  # 底部=vmin, 顶部=vmax

            # 刻度线
            painter.drawLine(
                int(bar_x + bar_width), int(tick_y),
                int(bar_x + bar_width + 4), int(tick_y)
            )

            # 刻度标签
            label = f"{value:.0f}"
            painter.drawText(int(bar_x + bar_width + 7), int(tick_y + 4), label)

        # ── 标注单位 ──
        unit_font = QFont("Segoe UI", 8, QFont.Bold)
        painter.setFont(unit_font)
        painter.drawText(int(bar_x), int(bar_y - 8), "Sv (dB)")

        painter.end()

    def _fit_to_view_and_update(self):
        self._fit_to_view()
        self.update()

    # ── 视图控制 ──────────────────────────────────────────────

    def _fit_to_view(self) -> None:
        if self._n_pings == 0 or self._n_samples == 0:
            return
        ww = max(self.width(), 200)
        wh = max(self.height(), 200)
        margin = 0.05
        avail_w = ww * (1 - 2 * margin)
        avail_h = wh * (1 - 2 * margin)
        self._zoom_x = avail_w / self._n_pings
        self._zoom_y = avail_h / self._n_samples
        data_screen_w = self._n_pings * self._zoom_x
        data_screen_h = self._n_samples * self._zoom_y
        self._offset_x = (ww - data_screen_w) / 2
        self._offset_y = (wh - data_screen_h) / 2

    def reset_view(self) -> None:
        self._selecting = False
        self._select_start = None
        self._select_end = None
        self._fit_to_view()
        self.update()

    # ── 工具方法 ──────────────────────────────────────────────

    @staticmethod
    def _find_runs(arr: np.ndarray) -> list:
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
