"""GUI 错误日志面板回归测试。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QMessageBox


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_worker_error_is_written_to_scrollable_panel_without_modal_dialog(qapp, monkeypatch):
    """Worker 错误应进入可滚动日志，不能用模态错误框阻塞主窗口。"""
    from src.gui.main_window import MainWindow

    def fail_if_modal(*_args, **_kwargs):
        raise AssertionError("worker error must not open a modal QMessageBox")

    monkeypatch.setattr(QMessageBox, "critical", fail_if_modal)
    window = MainWindow()
    try:
        traceback_text = "Traceback (most recent call last):\nOSError: bad.raw"
        window._on_worker_error(traceback_text)
        assert traceback_text in window._message_text.toPlainText()
        assert window._message_text.verticalScrollBar().maximum() >= 0
    finally:
        window.close()


def test_empty_bottom_result_is_reported_in_message_panel(qapp):
    """底线算法返回全空结果时，GUI 应明确提示原因而不是静默空白。"""
    import numpy as np
    import xarray as xr

    from src.gui.main_window import MainWindow

    window = MainWindow()
    try:
        window._ds_Sv = xr.Dataset(
            {"Sv": (("ping_time", "range_sample"), np.zeros((3, 2)))}
        )
        window._on_bottom_detected(np.full(3, np.nan))
        assert "结果全部为空" in window._message_text.toPlainText()
    finally:
        window.close()
