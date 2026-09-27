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
    renderer._zoom_x *= 2
    renderer._zoom_y *= 2
    renderer.set_view_ratio(0.25, 0.75)
    renderer._offset_y = -150
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


def test_renderer_accepts_multiple_named_lines(qapp):
    from src.viz.opengl_renderer import EchogramRenderer

    renderer = EchogramRenderer()
    try:
        renderer.set_lines({"surface": [2.0, 2.0], "bottom": [20.0, 21.0]})
        assert set(renderer.get_lines()) == {"surface", "bottom"}
    finally:
        renderer.close()


def test_renderer_preserves_named_line_colors(qapp):
    from src.viz.opengl_renderer import EchogramRenderer

    renderer = EchogramRenderer()
    try:
        colors = {"surface": "#123456", "bottom": "#abcdef"}
        renderer.set_lines(
            {"surface": [2.0, 2.0], "bottom": [20.0, 21.0]}, colors=colors
        )
        assert renderer._named_line_colors == colors

        drawn = []
        renderer._draw_named_line = lambda values, color, *, dashed=False: drawn.append(
            (color, dashed)
        )
        renderer._draw_named_lines()
        assert drawn[0][0] == pytest.approx((0x12 / 255, 0x34 / 255, 0x56 / 255, 1.0))
        assert drawn[1][0] == pytest.approx((0xAB / 255, 0xCD / 255, 0xEF / 255, 1.0))
    finally:
        renderer.close()


def test_replacing_named_lines_removes_legacy_line_residue(qapp):
    from src.viz.opengl_renderer import EchogramRenderer

    renderer = EchogramRenderer()
    try:
        renderer.set_lines({"surface": [2.0, 2.0], "bottom": [20.0, 21.0]})
        renderer.set_lines({"custom": [7.0, 8.0]})

        assert set(renderer.get_lines()) == {"custom"}
        assert renderer.get_bottom_line() is None
        assert renderer._surface_line is None
    finally:
        renderer.close()


def test_active_line_edit_and_undo_are_isolated_per_line(qapp):
    from src.viz.opengl_renderer import EchogramRenderer

    renderer = EchogramRenderer()
    emitted = []
    renderer.line_edited.connect(lambda line_id, values: emitted.append((line_id, values.copy())))
    try:
        renderer.set_data(np.zeros((6, 20), dtype=np.float32))
        renderer.set_lines({"first": np.full(6, 5.0), "second": np.full(6, 10.0)})
        renderer.set_active_line("first")
        renderer._enable_smoothing = False
        renderer._save_line_undo()
        renderer._bottom_draw_points = [(1.0, 7.0), (3.0, 9.0)]
        renderer._apply_drawn_segment()
        edited_first = renderer.get_lines()["first"].copy()

        renderer.set_active_line("second")
        renderer._save_line_undo()
        renderer._bottom_draw_points = [(1.0, 12.0), (3.0, 14.0)]
        renderer._apply_drawn_segment()
        renderer._undo_line()

        assert emitted[0][0] == "first"
        assert emitted[1][0] == "second"
        assert emitted[-1][0] == "second"
        np.testing.assert_allclose(renderer.get_lines()["first"], edited_first, equal_nan=True)
        np.testing.assert_allclose(renderer.get_lines()["second"], np.full(6, 10.0))
    finally:
        renderer.close()
