from PySide6.QtWidgets import QApplication, QInputDialog

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


def test_line_manager_can_use_active_line_as_reference(monkeypatch):
    from src.gui.main_window import MainWindow

    QApplication.instance() or QApplication([])
    references = []
    monkeypatch.setattr(QInputDialog, "getText", lambda *args: ("Derived", True))

    def get_item(*args):
        references.extend(args[3])
        return "", False

    monkeypatch.setattr(QInputDialog, "getItem", get_item)
    window = MainWindow()
    try:
        window._show_line_manager()
        assert "Surface" in references
    finally:
        window.close()


def test_line_manager_avoids_reusing_existing_line_id(monkeypatch):
    from src.gui.main_window import MainWindow

    QApplication.instance() or QApplication([])
    monkeypatch.setattr(QInputDialog, "getText", lambda *args: ("New line", True))
    monkeypatch.setattr(QInputDialog, "getItem", lambda *args: ("Surface", True))
    monkeypatch.setattr(QInputDialog, "getDouble", lambda *args: (1.0, True))
    window = MainWindow()
    try:
        window.line_manager.add_line("line_3", "Existing", reference_id="surface")
        window._show_line_manager()
        assert window.line_manager.get("line_4").name == "New line"
    finally:
        window.close()


def test_line_manager_syncs_and_persists_new_line_immediately(monkeypatch):
    from src.gui.main_window import MainWindow

    QApplication.instance() or QApplication([])
    monkeypatch.setattr(QInputDialog, "getText", lambda *args: ("Near bottom", True))
    monkeypatch.setattr(QInputDialog, "getItem", lambda *args: ("Surface", True))
    monkeypatch.setattr(QInputDialog, "getDouble", lambda *args: (1.0, True))
    window = MainWindow()
    calls = []
    monkeypatch.setattr(window, "_sync_lines_to_renderer", lambda: calls.append("sync"))
    monkeypatch.setattr(window, "_save_file_state", lambda: calls.append("save"))
    try:
        window._show_line_manager()

        assert window.line_manager.get("line_2").name == "Near bottom"
        assert calls == ["sync", "save"]
    finally:
        window.close()
