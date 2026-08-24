"""Echogram 底部导航滑块 — 缩略图 + 可拖动视口矩形

功能（参照 Echoview）：
- 绘制全部数据缩略图（低分辨率）
- 当前可见范围用半透明矩形高亮
- 拖动矩形 → 更新主视图 offset_x（水平导航）
- 未放大（可见范围 ≈ 全部）时自动隐藏
"""

import logging

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

logger = logging.getLogger(__name__)


class EchogramNavBar(QWidget):
    """底部缩略图导航滑块"""

    view_moved = Signal(float, float)  # (start_ratio, end_ratio)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(48)
        self._thumb: np.ndarray | None = None  # 缩略图 (H, W) 灰度 0-255
        self._view_ratio = (0.0, 1.0)  # 当前可见范围
        self._dragging = False

    # ── 数据 ────────────────────────────────────────────────

    def set_thumbnail(self, sv: np.ndarray | None) -> None:
        """设置缩略图（下采样 Sv 数组）"""
        if sv is None:
            self._thumb = None
            self._view_ratio = (0.0, 1.0)
            self.update()
            return
        # 下采样到固定宽度（保持纵横比）
        target_w = 800
        h, w = sv.shape
        if w == 0 or h == 0:
            self._thumb = None
            return
        step_w = max(1, w // target_w)
        thumb = sv[:, ::step_w]
        # 再限制高度
        target_h = 40
        step_h = max(1, thumb.shape[0] // target_h)
        thumb = thumb[::step_h, :]
        # 归一化到 0-255（按有限值）
        valid = np.isfinite(thumb)
        if not np.any(valid):
            self._thumb = np.zeros_like(thumb, dtype=np.uint8)
        else:
            vmin = np.nanmin(thumb)
            vmax = np.nanmax(thumb)
            span = (vmax - vmin) or 1.0
            norm = np.clip((thumb - vmin) / span, 0, 1)
            norm[~valid] = 0.5
            self._thumb = (norm * 255).astype(np.uint8)
        self.update()

    def set_view_ratio(self, start: float, end: float) -> None:
        """更新当前可见范围（0-1）"""
        self._view_ratio = (start, end)
        # 未放大（覆盖全部）时隐藏
        self.setVisible((end - start) < 0.999)
        self.update()

    # ── 绘制 ────────────────────────────────────────────────

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            painter.end()
            return

        # 背景
        painter.fillRect(0, 0, w, h, QColor(30, 34, 42))

        if self._thumb is None:
            painter.setPen(QColor(100, 110, 125))
            painter.drawText(8, h // 2 + 4, "加载数据后显示导航")
            painter.end()
            return

        # 绘制缩略图（拉伸填满）
        thumb_h = h - 8
        thumb_w = w - 8
        if self._thumb is not None and thumb_w > 0 and thumb_h > 0:
            img = self._thumb.astype(np.uint8)
            # 转为 QImage 并拉伸
            from PySide6.QtGui import QImage
            qimg = QImage(img.data, img.shape[1], img.shape[0], img.strides[0], QImage.Format_Grayscale8)
            painter.drawImage(4, 4, qimg.scaled(thumb_w, thumb_h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))

        # 视口矩形
        start, end = self._view_ratio
        x0 = 4 + start * thumb_w
        x1 = 4 + end * thumb_w
        painter.setBrush(QColor(70, 140, 220, 60))
        painter.setPen(QColor(110, 180, 255, 200))
        painter.drawRect(int(x0), 4, max(1, int(x1 - x0)), thumb_h)

        painter.end()

    # ── 交互 ────────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        if self._thumb is None:
            return
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._move_to(event.position().x())

    def mouseMoveEvent(self, event) -> None:
        if self._dragging:
            self._move_to(event.position().x())

    def mouseReleaseEvent(self, event) -> None:
        self._dragging = False

    def _move_to(self, x: float) -> None:
        """将视口中心移动到 x 位置"""
        w = max(self.width(), 1)
        thumb_w = w - 8
        if thumb_w <= 0:
            return
        # 视口宽度比例
        start, end = self._view_ratio
        view_w = end - start
        center = (x - 4) / thumb_w
        center = max(view_w / 2, min(1 - view_w / 2, center))
        new_start = center - view_w / 2
        new_end = center + view_w / 2
        self._view_ratio = (new_start, new_end)
        self.view_moved.emit(new_start, new_end)
        self.update()
