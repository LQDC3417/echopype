from PySide6.QtWidgets import QApplication

from src.gui.toolbars import EchogramToolBar, StandardToolBar
from src.gui.welcome_dialog import WelcomeDialog


def test_echogram_toolbar_has_line_selector_and_no_display_range_controls():
    QApplication.instance() or QApplication([])
    toolbar = EchogramToolBar()

    assert hasattr(toolbar, "line_combo")
    assert hasattr(toolbar, "draw_line_action")
    assert not hasattr(toolbar, "cmap_combo")
    assert not hasattr(toolbar, "slider_vmin")


def test_standard_toolbar_does_not_expose_run_all_action():
    QApplication.instance() or QApplication([])
    toolbar = StandardToolBar()

    assert not hasattr(toolbar, "_run_act")


def test_welcome_dialog_exposes_new_and_open_project_actions():
    QApplication.instance() or QApplication([])
    dialog = WelcomeDialog([])

    assert dialog.new_button.text()
    assert dialog.open_button.text()
