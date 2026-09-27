import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, Signal
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from src.gui.main_window import MainWindow


class _RunningWorker(QObject):
    finished = Signal(object)
    error = Signal(str)

    def __init__(self):
        super().__init__()
        self.interruption_requested = False
        self.running = True

    def isRunning(self):
        return self.running

    def requestInterruption(self):
        self.interruption_requested = True

    def wait(self, _timeout):
        raise AssertionError("GUI must not block waiting before switching projects")


class _StartableWorker(_RunningWorker):
    progress = Signal(str)

    def __init__(self):
        super().__init__()
        self.running = False
        self.start_calls = 0

    def start(self):
        self.start_calls += 1
        self.running = True


class _CloseEvent:
    def __init__(self):
        self.ignored = False

    def ignore(self):
        self.ignored = True


def test_close_is_deferred_while_worker_is_running():
    QApplication.instance() or QApplication([])
    window = MainWindow()
    worker = _RunningWorker()
    event = _CloseEvent()
    window._current_worker = worker

    window.closeEvent(event)

    assert event.ignored
    assert worker.interruption_requested
    assert window._close_pending


def test_open_recent_does_not_drop_a_running_worker():
    QApplication.instance() or QApplication([])
    window = MainWindow()
    worker = _RunningWorker()
    window._current_worker = worker

    window._open_recent("not-opened.ep")

    assert window._current_worker is worker


def test_deferred_close_finishes_without_waiting_for_custom_finished_signal():
    QApplication.instance() or QApplication([])
    window = MainWindow()
    worker = _RunningWorker()
    window._current_worker = worker
    window._close_pending = True
    worker.running = False

    window._complete_deferred_close(worker)

    assert window._current_worker is None
    assert not window._close_pending


def test_start_worker_refuses_to_start_a_second_running_task():
    QApplication.instance() or QApplication([])
    window = MainWindow()
    first = _StartableWorker()
    second = _StartableWorker()

    try:
        assert window._start_worker(first, lambda _result: None)
        assert first.start_calls == 1
        assert not window._start_worker(second, lambda _result: None)
        assert second.start_calls == 0
        assert window._current_worker is first
    finally:
        first.running = False
        window.close()


def test_finished_worker_is_released_after_result_callback():
    QApplication.instance() or QApplication([])
    window = MainWindow()
    worker = _StartableWorker()
    results = []
    window._current_worker = worker
    worker.running = False

    try:
        window._connect_latest_worker(worker, results.append)
        worker.finished.emit("done")
        QApplication.processEvents()

        assert results == ["done"]
        assert window._current_worker is None
    finally:
        window.close()


def test_pending_parameter_timer_is_cancelled_before_close():
    QApplication.instance() or QApplication([])
    window = MainWindow()
    calls = []

    try:
        window._schedule_parameter_apply("test", lambda: calls.append("run"), interval_ms=1)
        timer = window._parameter_timers["test"]

        window._cancel_pending_work()
        QTest.qWait(20)

        assert not timer.isActive()
        assert window._parameter_callbacks == {}
        assert calls == []
    finally:
        window.close()
