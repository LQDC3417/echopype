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
from pathlib import Path

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
    GL_SCISSOR_TEST,
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
    glScissor,
    glTexCoord2f,
    glTexImage2D,
    glTexParameteri,
    glVertex2f,
    glViewport,
)

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QWheelEvent
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtWidgets import QMenu, QToolTip

from src.gui.toolbars import MouseMode
from src.viz.color_legend import ColorLegend

logger = logging.getLogger(__name__)


class EchogramRenderer(QOpenGLWidget):
    """OpenGL Echogram 渲染器"""

    mouse_moved = Signal(float, float)  # (ping_index, sample_index)
    region_selected = Signal(float, float, float, float)
    line_edited = Signal(str, object)  # line_id, sample-index values
    bottom_line_edited = Signal(object)  # np.ndarray — 编辑后的底线
    sv_at_cursor = Signal(float, float, float)  # (ping, depth, sv_value)
    surface_line_requested = Signal()  # 右键请求设置表线
    analysis_region_requested = Signal()
    analysis_region_toggle = Signal(bool)  # 分析区域限定开关
    re_detect_bottom = Signal()  # 重新检测底部
    update_bottom_requested = Signal()  # 手动更新/保存当前底线
    display_settings_requested = Signal()
    noise_removal_requested = Signal()
    school_detection_requested = Signal()
    integration_requested = Signal()
    real_sed_requested = Signal()
    file_page_requested = Signal(int)  # delta: -1=上一页, +1=下一页
    zoom_changed = Signal(float, float)  # 相对于全图的 X/Y 倍率

    MAX_TEX_SIZE_FALLBACK = 16384  # GPU 查询失败时的保底值

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(200, 200)

        # 数据: (n_pings, n_samples)
        self._sv_data = None
        self._noise_mask = None
        self._bottom_line = None  # (n_pings,) sample indices
        self._surface_line = None  # float — 表线深度(in sample index units)
        self._named_lines: dict[str, np.ndarray] = {}
        self._named_line_colors: dict[str, str] = {}
        self._active_line_id = "bottom"
        self._school_mask = None
        self._single_targets = None  # np.ndarray (N, 2) — ping_idx, sample_idx
        self._overlay_visibility = {
            "noise": True,
            "bottom": True,
            "school": True,
            "grid": True,
        }

        # 网格叠加
        self._grid_cells = None   # list[dict] — ping_start/end, depth_lo/hi (sample index)
        self._grid_values = None  # np.ndarray — 每格的着色值（如 mean_sv）
        self._grid_vmin = -70.0
        self._grid_vmax = -20.0
        self._grid_colors_cache = None   # 缓存的颜色数组 (N, 3) RGB
        self._grid_colors_dirty = True   # 颜色缓存是否需要更新
        self._grid_alpha = 0.28          # 网格填充透明度（浅色仪器风）
        self._grid_meta = None           # {"n_cells", "vmin", "vmax", "color_by"}
        self._grid_drawn_cells = 0       # 本帧实际绘制的单元数（诊断）

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
        self._line_undo_stacks: dict[str, list[np.ndarray]] = {}
        self._line_redo_stacks: dict[str, list[np.ndarray]] = {}
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
        self._view_size = None
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
        self._file_seams = []
        self.legend = ColorLegend(self)
        self._layout_legend()

        # 启用鼠标追踪（用于悬停检测）
        self.setMouseTracking(True)

        # 右键菜单通过 contextMenuEvent 处理

    def _emit_prev_page(self):
        self.file_page_requested.emit(-1)

    def _emit_next_page(self):
        self.file_page_requested.emit(1)

    # ── 数据设置 ──────────────────────────────────────────────

    def set_data(self, sv_data: np.ndarray) -> None:
        if self._sv_data is not None and self._sv_data.shape != sv_data.shape:
            self._file_seams = []
        self._sv_data = sv_data.astype(np.float32)
        self._n_pings = sv_data.shape[0]
        self._n_samples = sv_data.shape[1]
        self._texture_dirty = True
        self._fit_to_view()
        self.legend.update()
        self.update()

    def set_file_sources(self, sources, times) -> None:
        """按排序后的来源变更位置标记接缝，变量切换不改变接缝。"""
        self._file_seams = []
        if sources is not None and len(sources) == self._n_pings:
            for i in np.flatnonzero(np.asarray(sources)[1:] != np.asarray(sources)[:-1]) + 1:
                label = f"{Path(str(sources[i - 1])).name} → {Path(str(sources[i])).name}\n{times[i]}"
                self._file_seams.append((int(i), label))
        self.update()

    def get_data(self) -> np.ndarray | None:
        """返回当前显示变量，供区域检查读取。"""
        return self._sv_data

    def set_noise_mask(self, mask) -> None:
        if mask is None:
            self._noise_mask = None
        else:
            self._noise_mask = mask.astype(bool)
        self.update()

    def set_bottom_line(self, bottom: np.ndarray | None) -> None:
        if bottom is None:
            self._bottom_line = None
            self._named_lines.pop("bottom", None)
        else:
            self._bottom_line = np.asarray(bottom, dtype=np.float32).copy()
            self._named_lines["bottom"] = self._bottom_line.copy()
        self.update()

    def set_lines(
        self,
        lines: dict[str, np.ndarray],
        *,
        colors: dict[str, str] | None = None,
    ) -> None:
        """设置所有可见线段；保留 surface/bottom 旧接口的同步行为。"""
        self._named_lines = {key: np.asarray(value, dtype=np.float32).copy() for key, value in lines.items()}
        self._named_line_colors = {
            key: str(value)
            for key, value in (colors or {}).items()
            if key in self._named_lines
        }
        self._bottom_line = self._named_lines.get("bottom")
        surface = self._named_lines.get("surface")
        self._surface_line = float(surface[0]) if surface is not None and len(surface) else None
        current_ids = set(self._named_lines)
        self._line_undo_stacks = {
            key: value for key, value in self._line_undo_stacks.items() if key in current_ids
        }
        self._line_redo_stacks = {
            key: value for key, value in self._line_redo_stacks.items() if key in current_ids
        }
        self.update()

    def get_lines(self) -> dict[str, np.ndarray]:
        return {key: value.copy() for key, value in self._named_lines.items()}

    def set_active_line(self, line_id: str) -> None:
        """选择绘制目标；选择本身不会修改线段。"""
        self._active_line_id = str(line_id)

    def get_bottom_line(self) -> np.ndarray | None:
        """获取当前底线数据（只读副本）"""
        if self._bottom_line is None:
            return None
        return self._bottom_line.copy()

    def set_surface_line(self, depth_samples: float) -> None:
        """设置表线深度（sample index 单位），None 表示关闭"""
        self._surface_line = depth_samples
        if depth_samples is None:
            self._named_lines.pop("surface", None)
        else:
            count = max(1, self._n_pings)
            self._named_lines["surface"] = np.full(count, depth_samples, dtype=np.float32)
        self.update()

    def set_school_mask(self, mask) -> None:
        if mask is None:
            self._school_mask = None
        else:
            self._school_mask = mask.astype(bool)
        self.update()

    def set_grid_data(self, grid_df, ds_Sv=None, color_by: str = "mean_Sv") -> None:
        """设置 ESU/积分网格叠加数据。

        Parameters
        ----------
        grid_df : pd.DataFrame
            含 ping_start/end 与 depth_start/end 或 depth_lo/hi；着色列如 mean_Sv / abc
        ds_Sv : xr.Dataset, optional
            用于将深度米转换为 sample index
        color_by : str
            着色指标列名（自动兼容 mean_Sv/mean_sv 大小写）
        """
        if grid_df is None or grid_df.empty:
            self.clear_grid_overlay()
            return

        # 列名兼容
        col = color_by
        if col not in grid_df.columns:
            for alt in (color_by.lower(), color_by.upper(), "mean_Sv", "mean_sv", "abc"):
                if alt in grid_df.columns:
                    col = alt
                    break
        depth_lo_col = "depth_lo" if "depth_lo" in grid_df.columns else "depth_start"
        depth_hi_col = "depth_hi" if "depth_hi" in grid_df.columns else "depth_end"

        echo_range = None
        if ds_Sv is not None and "echo_range" in ds_Sv:
            echo_range = np.asarray(ds_Sv["echo_range"].values, dtype=np.float64)
            while echo_range.ndim > 1:
                echo_range = echo_range[0]

        cells = []
        values = []
        labels = []
        for _, row in grid_df.iterrows():
            ping_start = int(row["ping_start"])
            ping_end = int(row["ping_end"])
            depth_lo = float(row.get(depth_lo_col, 0.0))
            depth_hi = float(row.get(depth_hi_col, self._n_samples))

            if echo_range is not None and echo_range.size > 1:
                # 深度边界的 exclusive end：两侧都用 side=left
                sample_start = int(np.searchsorted(echo_range, depth_lo, side="left"))
                sample_end = int(np.searchsorted(echo_range, depth_hi, side="left"))
            else:
                # 无除数据时按米或索引直接使用（旧路径）
                sample_start = int(depth_lo)
                sample_end = int(depth_hi)

            # 至少 1 个采样厚度，避免空单元
            if sample_end <= sample_start:
                sample_end = sample_start + 1
            if self._n_samples and sample_end > self._n_samples:
                sample_end = self._n_samples
            if sample_start < 0:
                sample_start = 0
            if sample_end <= sample_start:
                continue

            cells.append({
                "ping_start": ping_start,
                "ping_end": ping_end,
                "sample_start": sample_start,
                "sample_end": sample_end,
                "interval": int(row.get("interval", 0)),
                "layer": int(row.get("layer", 0)),
            })
            try:
                values.append(float(row[col]))
            except (TypeError, ValueError):
                values.append(np.nan)
            labels.append(f"{row[col]:.1f}" if col in ("mean_Sv", "mean_sv", "min_Sv", "max_Sv")
                          else f"{row[col]:.3g}")

        if not cells:
            self.clear_grid_overlay()
            return

        self._grid_cells = cells
        self._grid_values = np.array(values, dtype=np.float32)
        self._grid_label_fmt = col
        finite = self._grid_values[np.isfinite(self._grid_values)]
        if finite.size:
            self._grid_vmin = float(np.nanmin(finite))
            self._grid_vmax = float(np.nanmax(finite))
            if self._grid_vmin == self._grid_vmax:
                self._grid_vmax = self._grid_vmin + 1.0
        self._grid_meta = {
            "n_cells": len(cells),
            "vmin": self._grid_vmin,
            "vmax": self._grid_vmax,
            "color_by": col,
        }
        self._grid_colors_dirty = True
        self._overlay_visibility["grid"] = True
        self.update()

    def clear_grid_overlay(self) -> None:
        """清除网格叠加"""
        self._grid_cells = None
        self._grid_values = None
        self._grid_colors_cache = None
        self._grid_colors_dirty = True
        self._grid_meta = None
        self._grid_drawn_cells = 0
        self.update()

    def set_grid_alpha(self, alpha: float) -> None:
        """网格填充透明度 0–1。"""
        self._grid_alpha = float(min(1.0, max(0.0, alpha)))
        self.update()

    def grid_summary(self) -> dict | None:
        return dict(self._grid_meta) if self._grid_meta else None

    def set_single_targets(self, targets_df) -> None:
        """设置单体目标标记。

        Parameters
        ----------
        targets_df : pd.DataFrame or None
            单体目标检测结果，需含 ping_idx_center / depth_idx_center 列
        """
        if targets_df is None or targets_df.empty:
            self._single_targets = None
        else:
            # 兼容两种列名：简化版 (ping_idx_center/depth_idx_center) 和真实 SED (ping_idx/sample_idx)
            if "ping_idx_center" in targets_df.columns:
                pings = np.asarray(targets_df["ping_idx_center"].values, dtype=np.float32)
                samples = np.asarray(targets_df["depth_idx_center"].values, dtype=np.float32)
            else:
                pings = np.asarray(targets_df["ping_idx"].values, dtype=np.float32)
                samples = np.asarray(targets_df["sample_idx"].values, dtype=np.float32)
            self._single_targets = np.column_stack([pings, samples])
        self.update()

    def clear_single_targets(self) -> None:
        """清除单体目标标记"""
        self._single_targets = None
        self.update()

    def set_colormap(self, name: str = "jet", vmin: float = -70.0, vmax: float = -20.0) -> None:
        self._cmap_name = "gray" if name == "grayscale" else name
        self._vmin = vmin
        self._vmax = vmax
        self._texture_dirty = True
        self._layout_legend()
        self._resize_view()
        self.legend.update()
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
        self.setCursor(Qt.OpenHandCursor if mode == MouseMode.PAN else Qt.ArrowCursor)

    def set_overlay_visible(self, overlay: str, visible: bool) -> None:
        """只切换 overlay 的显示状态，保留已计算的结果缓存。"""
        if overlay not in self._overlay_visibility:
            raise ValueError(f"unknown overlay: {overlay}")
        self._overlay_visibility[overlay] = bool(visible)
        self.update()

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
        ratio = self.devicePixelRatioF()
        glViewport(0, 0, round(w * ratio), round(h * ratio))

    def _plot_rect(self):
        return QRect(0, 0, max(1, self.width() - self.legend.width()), max(1, self.height()))

    def _layout_legend(self):
        width = self.legend.preferred_width()
        self.legend.setGeometry(max(1, self.width() - width), 0, width, self.height())

    def resizeEvent(self, event):
        self._layout_legend()
        self._resize_view()
        super().resizeEvent(event)

    def _resize_view(self):
        if self._n_pings and self._n_samples:
            rect = self._plot_rect()
            # 第一次显示时 Qt 的 oldSize 可能为 (-1, -1)，使用实际适配过的尺寸。
            if self._view_size is None:
                self._fit_to_view()
                return
            old_width, old_height = self._view_size
            self._zoom_x *= rect.width() / max(1, old_width)
            self._offset_x *= rect.width() / max(1, old_width)
            self._zoom_y *= rect.height() / max(1, old_height)
            self._offset_y *= rect.height() / max(1, old_height)
            self._constrain_view()
            self._view_size = (rect.width(), rect.height())
            self._emit_zoom()

    def paintGL(self) -> None:
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        if self._sv_data is None:
            return

        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0, self.width(), self.height(), 0, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        rect = self._plot_rect()
        ratio = self.devicePixelRatioF()
        glEnable(GL_SCISSOR_TEST)
        glScissor(0, 0, round(rect.width() * ratio), round(rect.height() * ratio))
        self._draw_echogram_texture()

        # 网格叠加在 echogram 之上、底线/鱼群之下
        if self._grid_cells is not None and self._overlay_visibility.get("grid", True):
            self._draw_grid_overlay()
        if self._noise_mask is not None and self._overlay_visibility["noise"]:
            self._draw_noise_overlay()
        if self._named_lines:
            self._draw_named_lines()
        if self._school_mask is not None and self._overlay_visibility["school"]:
            self._draw_school_overlay()
        if self._single_targets is not None:
            self._draw_single_targets()
        if self._selecting and self._select_start and self._select_end:
            self._draw_selection_rect()

        # 底线绘制预览
        if self._bottom_draw_points:
            self._draw_bottom_preview()

        self._draw_file_seams()
        # 叠加信息文字
        if self._channel_text or self._cmap_name:
            self._draw_overlay_text()

        glDisable(GL_SCISSOR_TEST)
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
        rgba[~np.isfinite(data_T)] = (112 / 255, 119 / 255, 128 / 255, 1)
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
        glTexCoord2f(0, 0)
        glVertex2f(sx, sy)
        glTexCoord2f(1, 0)
        glVertex2f(sx + sw, sy)
        glTexCoord2f(1, 1)
        glVertex2f(sx + sw, sy + sh)
        glTexCoord2f(0, 1)
        glVertex2f(sx, sy + sh)
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
        h, _w = mask.shape
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

    def _draw_named_lines(self) -> None:
        """绘制当前可见命名线；颜色按稳定插入顺序分配。"""
        palette = (
            (0.2, 1.0, 0.4, 0.9),
            (0.8, 0.6, 0.0, 1.0),
            (1.0, 0.35, 0.35, 0.95),
            (0.7, 0.5, 1.0, 0.95),
            (0.3, 0.7, 1.0, 0.95),
        )
        for index, (line_id, values) in enumerate(self._named_lines.items()):
            if line_id == "bottom" and not self._overlay_visibility["bottom"]:
                continue
            color = self._hex_color_to_rgba(self._named_line_colors.get(line_id))
            if color is None:
                color = palette[index % len(palette)]
            self._draw_named_line(values, color, dashed=line_id == "surface")

    @staticmethod
    def _hex_color_to_rgba(value: str | None) -> tuple[float, float, float, float] | None:
        if not value:
            return None
        text = str(value).lstrip("#")
        if len(text) != 6:
            return None
        try:
            rgb = tuple(int(text[index:index + 2], 16) / 255.0 for index in (0, 2, 4))
        except ValueError:
            return None
        return (*rgb, 1.0)

    def _draw_named_line(self, values: np.ndarray, color: tuple, *, dashed: bool = False) -> None:
        line = np.asarray(values, dtype=np.float32).reshape(-1)
        if line.size == 0:
            return
        base_width = 2.0
        zoom_factor = min(self._zoom_x, self._zoom_y)
        line_width = base_width * min(2.0, max(0.5, zoom_factor * 0.5))
        if dashed:
            glEnable(GL_LINE_STIPPLE)
            glLineStipple(4, 0x0F0F)
        glColor4f(*color)
        glLineWidth(line_width)
        if line.size == 1:
            indices = np.array([0, max(0, self._n_pings - 1)], dtype=np.int64)
            line = np.repeat(line, max(1, self._n_pings))
        else:
            indices = self._decimate_bottom_line(line)
        glBegin(GL_LINE_STRIP)
        for i in indices:
            val = line[i]
            if not np.isfinite(val):
                glEnd()
                glBegin(GL_LINE_STRIP)
                continue
            x = self._offset_x + i * self._zoom_x
            y = self._offset_y + val * self._zoom_y
            glVertex2f(x, y)
        glEnd()
        if dashed:
            glDisable(GL_LINE_STIPPLE)

    def _draw_bottom_line(self) -> None:
        """兼容旧调用方绘制 Bottom。"""
        if self._bottom_line is None:
            return
        self._draw_named_line(self._bottom_line, self._bottom_line_color)

    @staticmethod
    def _decimate_bottom_line(bottom: np.ndarray, max_points: int = 20_000) -> np.ndarray:
        """为显示抽样超长底线，保留端点和 NaN 断线边界。"""
        values = np.asarray(bottom)
        n = values.size
        if n <= max_points:
            return np.arange(n, dtype=np.int64)

        finite = np.isfinite(values)
        boundaries = np.flatnonzero(finite[1:] != finite[:-1]) + 1
        mandatory = np.unique(
            np.concatenate((np.array([0, n - 1], dtype=np.int64), boundaries, boundaries - 1))
        )
        if len(mandatory) >= max_points:
            selected = np.linspace(0, len(mandatory) - 1, max_points, dtype=np.int64)
            result = mandatory[selected]
            result[-1] = n - 1
            return np.unique(result)

        remaining = max_points - len(mandatory)
        sampled = np.linspace(0, n - 1, remaining, dtype=np.int64)
        return np.unique(np.concatenate((mandatory, sampled)))

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

    def _visible_grid_indices(self):
        """视口裁剪：只返回与绘图区相交的单元索引。"""
        width = max(1, self.width() - self.legend.width())
        height = max(1, self.height())
        # 数据坐标 → 屏幕：screen = offset + index * zoom；求数据范围
        # x: 0..n_pings → offset .. offset+n*zoom
        # 反解 ping 范围
        if self._zoom_x == 0 or self._zoom_y == 0:
            return range(len(self._grid_cells))
        ping_lo = (0 - self._offset_x) / self._zoom_x
        ping_hi = (width - self._offset_x) / self._zoom_x
        sample_lo = (0 - self._offset_y) / self._zoom_y
        sample_hi = (height - self._offset_y) / self._zoom_y
        # 重叠判定时 ping 与 sample 轴可能翻转（offset 后）
        x0, x1 = min(ping_lo, ping_hi), max(ping_lo, ping_hi)
        y0, y1 = min(sample_lo, sample_hi), max(sample_lo, sample_hi)
        out = []
        for i, cell in enumerate(self._grid_cells):
            if (cell["ping_end"] < x0 or cell["ping_start"] > x1
                    or cell["sample_end"] < y0 or cell["sample_start"] > y1):
                continue
            out.append(i)
        return out

    def _draw_grid_overlay(self) -> None:
        """绘制 ESU 网格：半透明填充 + 适配浅色底的描边 + 标签（视口裁剪）。"""
        if not self._grid_cells or self._grid_values is None:
            return

        if self._grid_colors_dirty or self._grid_colors_cache is None:
            self._build_grid_colors_cache()
        colors = self._grid_colors_cache
        if colors is None:
            return

        indices = self._visible_grid_indices()
        self._grid_drawn_cells = len(indices)
        if not indices:
            return

        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        alpha = self._grid_alpha

        glBegin(GL_QUADS)
        for i in indices:
            cell = self._grid_cells[i]
            r, g, b = colors[i]
            if not np.isfinite(self._grid_values[i]):
                continue
            glColor4f(r, g, b, alpha)
            x0 = self._offset_x + cell["ping_start"] * self._zoom_x
            x1 = self._offset_x + cell["ping_end"] * self._zoom_x
            y0 = self._offset_y + cell["sample_start"] * self._zoom_y
            y1 = self._offset_y + cell["sample_end"] * self._zoom_y
            glVertex2f(x0, y0)
            glVertex2f(x1, y0)
            glVertex2f(x1, y1)
            glVertex2f(x0, y1)
        glEnd()

        # 浅色仪器风：深色描边，避免白底上白线不可见
        glColor4f(0.12, 0.16, 0.2, 0.55)
        glLineWidth(1.0)
        glBegin(GL_LINES)
        for i in indices:
            cell = self._grid_cells[i]
            x0 = self._offset_x + cell["ping_start"] * self._zoom_x
            x1 = self._offset_x + cell["ping_end"] * self._zoom_x
            y0 = self._offset_y + cell["sample_start"] * self._zoom_y
            y1 = self._offset_y + cell["sample_end"] * self._zoom_y
            glVertex2f(x0, y0)
            glVertex2f(x1, y0)
            glVertex2f(x0, y1)
            glVertex2f(x1, y1)
            glVertex2f(x0, y0)
            glVertex2f(x0, y1)
            glVertex2f(x1, y0)
            glVertex2f(x1, y1)
        glEnd()

        self._draw_grid_labels(indices)

    def _build_grid_colors_cache(self) -> None:
        """构建网格颜色缓存数组"""
        try:
            from matplotlib import colormaps
            cmap = colormaps[self._cmap_name]
        except (ImportError, AttributeError):
            from matplotlib import cm
            cmap = cm.get_cmap(self._cmap_name)

        span = self._grid_vmax - self._grid_vmin
        if span == 0:
            span = 1.0

        n = len(self._grid_cells)
        colors = np.zeros((n, 3), dtype=np.float32)

        for i, val in enumerate(self._grid_values):
            norm = np.clip((val - self._grid_vmin) / span, 0, 1)
            r, g, b, _ = cmap(norm)
            colors[i] = [r, g, b]

        self._grid_colors_cache = colors
        self._grid_colors_dirty = False

    def _draw_grid_labels(self, indices=None) -> None:
        """在足够大的网格单元内绘制指标数值标签（默认只画视口内单元）。"""
        min_cell_width = 48
        min_cell_height = 16
        if indices is None:
            indices = range(len(self._grid_cells))

        labels_to_draw = []
        for i in indices:
            cell = self._grid_cells[i]
            cell_w = (cell["ping_end"] - cell["ping_start"]) * self._zoom_x
            cell_h = (cell["sample_end"] - cell["sample_start"]) * self._zoom_y

            if cell_w >= min_cell_width and cell_h >= min_cell_height:
                if not np.isfinite(self._grid_values[i]):
                    continue
                x0 = self._offset_x + cell["ping_start"] * self._zoom_x
                x1 = self._offset_x + cell["ping_end"] * self._zoom_x
                y0 = self._offset_y + cell["sample_start"] * self._zoom_y
                y1 = self._offset_y + cell["sample_end"] * self._zoom_y
                cx = (x0 + x1) / 2
                cy = (y0 + y1) / 2
                val = self._grid_values[i]
                labels_to_draw.append((cx, cy, val, cell_w))

        if not labels_to_draw:
            return

        # 使用 QPainter 绘制文字（在 OpenGL 上下文之上）
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setClipRect(self._plot_rect())

        for cx, cy, val, cell_w in labels_to_draw:
            # 根据单元格大小调整字体
            font_size = max(8, min(12, int(cell_w / 8)))
            font = QFont("Consolas", font_size)
            painter.setFont(font)

            # 文字颜色：深色背景用白色，浅色背景用黑色
            # 这里简化为使用黑色带白色描边效果
            text = f"{val:.1f}"

            # 绘制文字阴影（提高可读性）
            painter.setPen(QColor(255, 255, 255, 200))
            painter.drawText(int(cx - 20), int(cy - 8), 40, 16,
                           Qt.AlignCenter | Qt.AlignVCenter, text)

            # 绘制主文字
            painter.setPen(QColor(0, 0, 0, 220))
            painter.drawText(int(cx - 21), int(cy - 9), 40, 16,
                           Qt.AlignCenter | Qt.AlignVCenter, text)

        painter.end()
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
                glVertex2f(x0, y0)
                glVertex2f(x1, y0)
                glVertex2f(x1, y1)
                glVertex2f(x0, y1)
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
            glVertex2f(x0, py)
            glVertex2f(x1, py)
        # 右边界线段
        for i in range(len(right_pings)):
            p, s = int(right_pings[i]), int(right_samples[i])
            px = self._offset_x + (p + 1) * self._zoom_x
            y0 = self._offset_y + s * self._zoom_y
            glVertex2f(px, y0)
            glVertex2f(px, y0 + self._zoom_y)
        glEnd()

    def _draw_single_targets(self) -> None:
        """绘制单体目标标记（红色十字）。"""
        if self._single_targets is None:
            return
        glColor4f(1.0, 0.25, 0.2, 0.95)
        glLineWidth(1.5)
        half_x = self._zoom_x * 0.35
        half_y = self._zoom_y * 0.35
        glBegin(GL_LINES)
        for ping, sample in self._single_targets:
            x = self._offset_x + ping * self._zoom_x
            y = self._offset_y + sample * self._zoom_y
            glVertex2f(x - half_x, y)
            glVertex2f(x + half_x, y)
            glVertex2f(x, y - half_y)
            glVertex2f(x, y + half_y)
        glEnd()

    def _draw_selection_rect(self) -> None:
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
        pos = event.position()
        if not self._n_pings or not self._n_samples or not self._plot_rect().contains(pos.toPoint()):
            event.accept()
            return
        sx, sy = float(pos.x()), float(pos.y())
        data_x, data_y = self._screen_to_data(sx, sy)
        # 高精度滚轮按实际步长缩放，零增量不能被误判为缩小。
        steps = event.angleDelta().y() / 120
        if not steps:
            steps = event.pixelDelta().y() / 120
        if not steps:
            event.accept()
            return
        factor = 1.05 ** max(-20, min(20, steps))
        rect = self._plot_rect()
        fit_x, fit_y = rect.width() / self._n_pings, rect.height() / self._n_samples
        self._zoom_x = min(max(fit_x, self._zoom_x * factor), max(fit_x, 100.0))
        self._zoom_y = min(max(fit_y, self._zoom_y * factor), max(fit_y, 100.0))
        self._offset_x = sx - data_x * self._zoom_x
        self._offset_y = sy - data_y * self._zoom_y
        self._constrain_view()
        self._emit_zoom()
        self.update()
        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if not self._plot_rect().contains(event.position().toPoint()):
            return
        sx, sy = float(event.position().x()), float(event.position().y())

        if event.button() == Qt.MiddleButton:
            self._panning = True
            self._pan_start = (sx, sy)
            self.setCursor(Qt.ClosedHandCursor)
            return

        if event.button() == Qt.LeftButton:
            if self._mouse_mode == MouseMode.PAN:
                self._panning = True
                self._pan_start = (sx, sy)
                self.setCursor(Qt.ClosedHandCursor)
            elif self._mouse_mode == MouseMode.NAVIGATE or self._mouse_mode == MouseMode.SELECT_NOISE or self._mouse_mode == MouseMode.INSPECT:
                self._selecting = True
                self._select_start = (sx, sy)
                self._select_end = (sx, sy)

            elif self._mouse_mode == MouseMode.DRAW_BOTTOM:
                # 开始自由手绘
                self._bottom_drawing = True
                self._bottom_editing = True
                # 保存当前底线状态到撤销栈
                self._save_line_undo()
                # 添加第一个绘制点
                px, py = self._screen_to_data(sx, sy)
                self._bottom_draw_points.append((px, py))
                self.setCursor(Qt.CrossCursor)
                self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        sx, sy = float(event.position().x()), float(event.position().y())
        rect = self._plot_rect()
        if not rect.contains(event.position().toPoint()) and not (self._panning or self._selecting or self._bottom_drawing):
            return
        sx, sy = min(max(0., sx), rect.width()), min(max(0., sy), rect.height())
        data_x, data_y = self._screen_to_data(sx, sy)
        self.mouse_moved.emit(data_x, data_y)

        # 发射 Sv 值
        ping_idx = round(data_x)
        sample_idx = round(data_y)
        sv_val = self._get_sv_at(ping_idx, sample_idx)
        self.sv_at_cursor.emit(data_x, data_y, sv_val)
        if not (self._panning or self._selecting or self._bottom_drawing):
            seam = next((label for ping, label in self._file_seams
                         if abs(self._data_to_screen(ping, 0)[0] - sx) <= 5), None)
            if seam:
                QToolTip.showText(event.globalPosition().toPoint(), seam, self)
            else:
                QToolTip.hideText()

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
            self._constrain_view()
            self._emit_zoom()
            self.update()

        elif self._selecting:
            self._select_end = (sx, sy)
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MiddleButton:
            self._panning = False
            self._pan_start = None
            self.setCursor(Qt.OpenHandCursor if self._mouse_mode == MouseMode.PAN else Qt.ArrowCursor)

        elif event.button() == Qt.LeftButton:
            if self._panning and self._mouse_mode == MouseMode.PAN:
                self._panning = False
                self._pan_start = None
                self.setCursor(Qt.OpenHandCursor)
                return

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
            self._undo_line()
        elif event.key() == Qt.Key_Y and event.modifiers() & Qt.ControlModifier:
            # Ctrl+Y ??????
            self._redo_line()

    def contextMenuEvent(self, event) -> None:
        """Qt 右键事件 → 显示上下文菜单"""
        self._show_context_menu(event.pos())

    def _show_context_menu(self, pos) -> None:
        """显示右键菜单"""
        menu = QMenu(self)
        if not self._plot_rect().contains(pos):
            return
        from src.gui.icons import icon
        menu.addAction(icon("reset"), "重置视图", self.reset_view)
        menu.addAction(icon("fit"), "适应窗口", self._fit_to_view_and_update)
        menu.addSeparator()

        # ── 翻页 ──
        act_prev = menu.addAction(icon("prev"), "上一页")
        act_prev.triggered.connect(self._emit_prev_page)
        act_next = menu.addAction(icon("next"), "下一页")
        act_next.triggered.connect(self._emit_next_page)
        menu.addSeparator()

        # 显示当前位置信息
        sx, sy = float(pos.x()), float(pos.y())
        px, py = self._screen_to_data(sx, sy)
        ping_idx = round(px)
        sample_idx = round(py)
        sv_val = self._get_sv_at(ping_idx, sample_idx)
        if not np.isnan(sv_val):
            menu.addAction(f"Ping: {ping_idx} | Sample: {sample_idx} | Sv: {sv_val:.1f} dB").setEnabled(False)
            menu.addSeparator()

        # ── 表线 / 分析区域 ──
        menu.addAction(icon("ruler"), "设置表线深度...", lambda: self.surface_line_requested.emit())
        menu.addAction(icon("ruler"), "分析区域...", self.analysis_region_requested.emit)
        act_analysis = menu.addAction("限定分析区域（表线~底线）")
        act_analysis.setCheckable(True)
        act_analysis.setChecked(self._analysis_region_enabled)
        act_analysis.triggered.connect(
            lambda checked: self.analysis_region_toggle.emit(checked)
        )
        menu.addSeparator()

        data_menu = menu.addMenu("数据")
        data_menu.addAction("噪声去除...", self.noise_removal_requested.emit)
        data_menu.addAction("鱼群检测...", self.school_detection_requested.emit)
        data_menu.addAction("回声积分...", self.integration_requested.emit)
        data_menu.addAction("SED 单体目标检测...", self.real_sed_requested.emit)
        menu.addSeparator()

        menu.addAction(icon("bottom"), "重新检测底部", lambda: self.re_detect_bottom.emit())

        # ── 更新底线（有底线时始终可见）──
        if self._bottom_line is not None:
            menu.addAction(icon("save"), "更新底线", lambda: self.update_bottom_requested.emit())

        # ── 底线绘制模式菜单 ──
        if self._mouse_mode == MouseMode.DRAW_BOTTOM:
            menu.addSeparator()
            if self._bottom_draw_points:
                menu.addAction("完成绘制", self._finish_bottom_drawing)
                menu.addAction("清除绘制点", self._clear_bottom_drawing)
            if self._line_undo_stacks.get(self._active_line_id):
                menu.addAction(icon("undo"), "撤销 (Ctrl+Z)", self._undo_line)

        menu.exec_(self.mapToGlobal(pos))

    # ── 底线编辑 ──────────────────────────────────────────────

    def _save_line_undo(self) -> None:
        line = self._named_lines.get(self._active_line_id)
        if line is None:
            return
        undo = self._line_undo_stacks.setdefault(self._active_line_id, [])
        undo.append(line.copy())
        if len(undo) > self._max_undo_steps:
            undo.pop(0)
        self._line_redo_stacks.setdefault(self._active_line_id, []).clear()

    def _undo_line(self) -> None:
        undo = self._line_undo_stacks.get(self._active_line_id, [])
        if not undo:
            return
        current = self._named_lines.get(self._active_line_id)
        if current is not None:
            self._line_redo_stacks.setdefault(self._active_line_id, []).append(current.copy())
        self._set_active_line_values(undo.pop())
        self._bottom_draw_points.clear()
        self._bottom_editing = False
        self._emit_active_line_edited()
        self.update()

    def _redo_line(self) -> None:
        redo = self._line_redo_stacks.get(self._active_line_id, [])
        if not redo:
            return
        current = self._named_lines.get(self._active_line_id)
        if current is not None:
            self._line_undo_stacks.setdefault(self._active_line_id, []).append(current.copy())
        self._set_active_line_values(redo.pop())
        self._bottom_draw_points.clear()
        self._bottom_editing = False
        self._emit_active_line_edited()
        self.update()

    def _set_active_line_values(self, values: np.ndarray) -> None:
        copied = np.asarray(values, dtype=np.float32).copy()
        self._named_lines[self._active_line_id] = copied
        if self._active_line_id == "bottom":
            self._bottom_line = copied
        elif self._active_line_id == "surface" and len(copied):
            self._surface_line = float(copied[0])

    def _emit_active_line_edited(self) -> None:
        values = self._named_lines[self._active_line_id].copy()
        self.line_edited.emit(self._active_line_id, values)
        if self._active_line_id == "bottom":
            self.bottom_line_edited.emit(values)

    def _save_bottom_undo(self) -> None:
        """兼容旧 Bottom 编辑 API。"""
        self._save_line_undo()

    def _undo_bottom(self) -> None:
        self._undo_line()

    def _redo_bottom(self) -> None:
        self._redo_line()

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
        ping_min = max(0, round(min(pings)))
        ping_max = min(self._n_pings - 1, round(max(pings)))

        if ping_min > ping_max:
            self._bottom_draw_points.clear()
            return

        # ????????????
        active_values = self._named_lines.get(self._active_line_id)
        if active_values is None or len(active_values) != self._n_pings:
            active_values = np.full(self._n_pings, np.nan, dtype=np.float32)
            self._set_active_line_values(active_values)

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
                    active_values[ping_idx] = left[1]
                else:
                    # ????
                    t = (ping_idx - left[0]) / max(1e-6, right[0] - left[0])
                    active_values[ping_idx] = left[1] + t * (right[1] - left[1])
            elif left is not None:
                active_values[ping_idx] = left[1]
            elif right is not None:
                active_values[ping_idx] = right[1]

        # ?????
        self._bottom_draw_points.clear()
        self._bottom_editing = False

        # ??????
        self._set_active_line_values(active_values)
        self._emit_active_line_edited()
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
        painter.setClipRect(self._plot_rect())
        font = QFont(self.font())
        font.setPointSize(10)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255, 200))

        y = 22
        if self._channel_text:
            painter.drawText(10, y, self._channel_text)
            y += 20
        if self._cmap_name:
            painter.drawText(10, y, f"Colormap: {self._cmap_name}  [{self._vmin:.0f}, {self._vmax:.0f}] dB")
        painter.end()

    def _fit_to_view_and_update(self):
        self._fit_to_view()
        self.update()

    # ── 视图控制 ──────────────────────────────────────────────

    def _fit_to_view(self) -> None:
        if self._n_pings == 0 or self._n_samples == 0:
            return
        rect = self._plot_rect()
        self._zoom_x = rect.width() / self._n_pings
        self._zoom_y = rect.height() / self._n_samples
        self._offset_x = self._offset_y = 0.0
        self._view_size = (rect.width(), rect.height())
        self._emit_zoom()

    def _constrain_view(self):
        if not self._n_pings or not self._n_samples:
            return
        rect = self._plot_rect()
        self._zoom_x = max(rect.width() / self._n_pings, self._zoom_x)
        self._zoom_y = max(rect.height() / self._n_samples, self._zoom_y)
        self._offset_x = min(0., max(rect.width() - self._n_pings * self._zoom_x, self._offset_x))
        self._offset_y = min(0., max(rect.height() - self._n_samples * self._zoom_y, self._offset_y))

    def _emit_zoom(self):
        if self._n_pings and self._n_samples:
            rect = self._plot_rect()
            self.zoom_changed.emit(self._zoom_x * self._n_pings / rect.width(),
                                   self._zoom_y * self._n_samples / rect.height())

    def _draw_file_seams(self):
        rect = self._plot_rect()
        glDisable(GL_TEXTURE_2D)
        glColor4f(1., 1., 1., 0.9)
        glLineWidth(1.5)
        glEnable(GL_LINE_STIPPLE)
        glLineStipple(2, 0x00FF)
        glBegin(GL_LINES)
        for ping, _ in self._file_seams:
            x, _ = self._data_to_screen(ping, 0)
            if 0 <= x < rect.width():
                glVertex2f(x, 0)
                glVertex2f(x, rect.height())
        glEnd()
        glDisable(GL_LINE_STIPPLE)

    def reset_view(self) -> None:
        self._selecting = False
        self._select_start = None
        self._select_end = None
        self._fit_to_view()
        self.update()

    # ── 导航（底部缩略图滑块联动）───────────────────────────

    def get_view_ratio(self) -> tuple:
        """返回当前可见 ping 范围比例 (start, end)，取值 [0,1]。

        用于底部缩略图滑块绘制视口矩形。
        """
        if self._n_pings == 0:
            return (0.0, 1.0)
        ww = self._plot_rect().width()
        start = -self._offset_x / self._zoom_x / self._n_pings
        end = (ww - self._offset_x) / self._zoom_x / self._n_pings
        start = max(0.0, min(1.0, start))
        end = max(start, min(1.0, end))
        return (start, end)

    def set_view_ratio(self, start: float, end: float) -> None:
        """根据滑块位置设置可见 ping 范围。

        保持当前 zoom 不变，只调整 offset_x 使 [start, end] 范围居中于视图。
        """
        if self._n_pings == 0 or self._zoom_x <= 0:
            return
        ww = self._plot_rect().width()
        # 目标：可见区域中心对应 [start,end] 的中心
        center_ping = ((start + end) / 2) * self._n_pings
        self._offset_x = ww / 2 - center_ping * self._zoom_x
        self._constrain_view()
        self._emit_zoom()
        self.update()

    def get_ping_count(self) -> int:
        return self._n_pings

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
