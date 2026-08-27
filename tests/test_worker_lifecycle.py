import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, Signal
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
