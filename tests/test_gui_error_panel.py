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
