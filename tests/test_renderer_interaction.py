"""Echogram 长底线和手爪平移回归测试。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _mouse_event(event_type, x, y, button, buttons):
    return QMouseEvent(
        event_type,
        QPointF(x, y),
        button,
        buttons,
        Qt.NoModifier,
    )


def test_long_bottom_line_is_decimated_for_display(qapp):
    """超长底线显示顶点数应受限，同时保留首尾点和断线。"""
    from src.viz.opengl_renderer import EchogramRenderer

    values = np.linspace(100.0, 500.0, 200_000, dtype=np.float32)
    values[50_000:60_000] = np.nan
    renderer = EchogramRenderer()
    try:
        indices = renderer._decimate_bottom_line(values, max_points=2_000)
        assert len(indices) <= 2_000
        assert indices[0] == 0
        assert indices[-1] == len(values) - 1
        assert np.any((indices >= 50_000) & (indices < 60_000))
    finally:
        renderer.close()


def test_pan_mode_uses_left_drag_to_move_echogram(qapp):
    """手爪模式下左键拖动应改变 Echogram 视口偏移。"""
    from src.gui.toolbars import MouseMode
    from src.viz.opengl_renderer import EchogramRenderer

    assert hasattr(MouseMode, "PAN")
    renderer = EchogramRenderer()
    renderer.resize(800, 600)
    renderer.set_data(np.zeros((100, 50), dtype=np.float32))
    renderer.set_mouse_mode(MouseMode.PAN)
    before = (renderer._offset_x, renderer._offset_y)
    try:
        renderer.mousePressEvent(
            _mouse_event(QEvent.Type.MouseButtonPress, 100, 100, Qt.LeftButton, Qt.LeftButton)
        )
        renderer.mouseMoveEvent(
            _mouse_event(QEvent.Type.MouseMove, 160, 140, Qt.NoButton, Qt.LeftButton)
        )
        renderer.mouseReleaseEvent(
            _mouse_event(QEvent.Type.MouseButtonRelease, 160, 140, Qt.LeftButton, Qt.NoButton)
        )
        after = (renderer._offset_x, renderer._offset_y)
        assert after != before
    finally:
        renderer.close()


def test_overlay_visibility_does_not_drop_cached_result(qapp):
    """关闭 overlay 只影响绘制，不应清除已计算的底线。"""
    from src.viz.opengl_renderer import EchogramRenderer

    renderer = EchogramRenderer()
    bottom = np.array([10.0, 11.0, 12.0], dtype=np.float32)
    try:
        renderer.set_bottom_line(bottom)
        renderer.set_overlay_visible("bottom", False)
        assert np.array_equal(renderer.get_bottom_line(), bottom)
        assert renderer._overlay_visibility["bottom"] is False
    finally:
        renderer.close()
