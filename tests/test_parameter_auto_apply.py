"""处理参数按功能独立自动应用的回归测试。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_processing_tab_exposes_independent_parameter_groups(qapp):
    """噪声、底线、鱼群、积分和 SED 参数应拥有独立变更信号。"""
    from src.gui.property_panel import ProcessingTab

    tab = ProcessingTab()
    for name in (
        "noise_params_changed",
        "bottom_params_changed",
        "school_params_changed",
        "integration_params_changed",
        "real_sed_params_changed",
    ):
        assert hasattr(tab, name)

    bottom_spy = QSignalSpy(tab.bottom_params_changed)
    school_spy = QSignalSpy(tab.school_params_changed)
    tab.spin_bottom_thr.setValue(-41.0)

    assert bottom_spy.count() == 1
    assert school_spy.count() == 0


def test_bottom_parameter_change_is_debounced_and_applied(qapp, monkeypatch):
    """底线参数变更应在防抖后自动触发底线处理。"""
    from src.gui.main_window import MainWindow

    window = MainWindow()
    calls = []
    window._ds_Sv = object()
    monkeypatch.setattr(window, "_detect_bottom", lambda: calls.append("bottom"))
    try:
        window._on_bottom_params_changed({"threshold": -41.0})
        QTest.qWait(650)
        assert calls == ["bottom"]
    finally:
        window.close()


def test_noise_change_marks_downstream_results_stale(qapp):
    """噪声参数变化只触发噪声处理，并标记下游结果过期。"""
    from src.gui.main_window import MainWindow

    window = MainWindow()
    try:
        window._on_noise_params_changed({"SNR_threshold": "4dB"})
        assert {"bottom", "schools", "integration"}.issubset(window._stale_results)
    finally:
        window.close()


def test_old_worker_result_is_ignored_after_a_new_parameter_run(qapp):
    """参数连续变化时，旧 Worker 完成结果不能覆盖新结果。"""
    from src.gui.main_window import MainWindow

    class FakeSignal:
        def __init__(self):
            self._slots = []

        def connect(self, slot):
            self._slots.append(slot)

        def emit(self, value):
            for slot in self._slots:
                slot(value)

    class FakeWorker:
        def __init__(self):
            self.finished = FakeSignal()
            self.error = FakeSignal()
            self.progress = FakeSignal()

    window = MainWindow()
    old_worker = FakeWorker()
    new_worker = FakeWorker()
    results = []
    try:
        window._connect_latest_worker(old_worker, results.append)
        window._connect_latest_worker(new_worker, results.append)
        window._current_worker = new_worker

        old_worker.finished.emit("old")
        new_worker.finished.emit("new")

        assert results == ["new"]
    finally:
        window.close()
