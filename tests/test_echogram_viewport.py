"""全图下限、滚轮锚点和独立图例的实际事件回归。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PySide6.QtCore import QPoint, QPointF, QSize, Qt
from PySide6.QtGui import QWheelEvent, QResizeEvent
from PySide6.QtWidgets import QApplication

from src.viz.opengl_renderer import EchogramRenderer


@pytest.fixture
def renderer():
    app = QApplication.instance() or QApplication([])
    widget = EchogramRenderer()
    widget.resize(900, 600)
    widget._layout_legend()
    widget.set_data(np.full((200, 100), -50., dtype=np.float32))
    yield widget
    widget.close()
    assert app is not None


def wheel(widget, delta=120, x=300, y=250, pixels=0):
    event = QWheelEvent(QPointF(x, y), QPointF(x, y), QPoint(0, pixels), QPoint(0, delta),
                        Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False)
    widget.wheelEvent(event)


def assert_covered(widget):
    rect = widget._plot_rect()
    assert widget._offset_x <= 0
    assert widget._offset_y <= 0
    assert widget._offset_x + widget._n_pings * widget._zoom_x >= rect.width() - 1e-8
    assert widget._offset_y + widget._n_samples * widget._zoom_y >= rect.height() - 1e-8
    assert rect.right() < widget.legend.geometry().left()


def test_wheel_is_gentle_anchored_and_stops_at_full_view(renderer):
    anchor = renderer._screen_to_data(300, 250)
    baseline = renderer._zoom_x
    wheel(renderer)
    assert renderer._zoom_x == pytest.approx(baseline * 1.05)
    assert renderer._screen_to_data(300, 250) == pytest.approx(anchor)
    wheel(renderer, delta=0)
    assert renderer._zoom_x == pytest.approx(baseline * 1.05)
    wheel(renderer, delta=12)
    assert renderer._zoom_x == pytest.approx(baseline * 1.05 ** 1.1)
    for _ in range(150):
        wheel(renderer, delta=-120, x=1, y=1)
    assert renderer.get_view_ratio() == pytest.approx((0., 1.))
    assert (renderer._offset_x, renderer._offset_y) == pytest.approx((0., 0.))
    assert renderer._zoom_x == pytest.approx(baseline)
    assert_covered(renderer)


def test_legend_scroll_and_navigation_cannot_expose_empty_space(renderer):
    baseline = renderer._zoom_x
    wheel(renderer, x=renderer.legend.x() + 5)
    assert renderer._zoom_x == baseline
    for _ in range(30):
        wheel(renderer, pixels=12, delta=0)
    for start, end in ((-1, 0), (1, 2), (0, 1)):
        renderer.set_view_ratio(start, end)
        assert_covered(renderer)
    old = renderer.size()
    renderer.resize(1100, 720)
    renderer.resizeEvent(QResizeEvent(renderer.size(), old))
    assert_covered(renderer)
    renderer.reset_view()
    assert renderer._data_to_screen(200, 100) == pytest.approx((renderer._plot_rect().width(), 720))


def test_sources_and_missing_values_remain_distinct(renderer):
    renderer.set_file_sources(["a.raw"] * 100 + ["b.raw"] * 100, np.arange(200))
    assert renderer._file_seams == [(100, "a.raw → b.raw\n100")]
    data = renderer.get_data().copy()
    data[0, 0] = np.nan
    renderer.set_data(data)
    assert renderer._file_seams[0][0] == 100
    assert renderer._sv_to_rgba()[0, 0].tolist() == [112, 119, 128, 255]


def test_first_show_with_invalid_old_size_keeps_full_view(renderer):
    renderer.resizeEvent(QResizeEvent(renderer.size(), QSize(-1, -1)))
    assert renderer.get_view_ratio() == pytest.approx((0., 1.))
    assert renderer._zoom_y * renderer._n_samples == pytest.approx(renderer.height())
