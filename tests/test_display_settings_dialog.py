import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication, QDialog

from src.gui.display_settings_dialog import DisplaySettingsDialog
from src.gui.main_window import MainWindow


def test_display_settings_apply_validates_and_emits_without_closing():
    QApplication.instance() or QApplication([])
    dialog = DisplaySettingsDialog("jet", -70.0, -20.0)
    spy = QSignalSpy(dialog.settings_applied)
    dialog.cmap_combo.setCurrentText("viridis")
    dialog.vmin_spin.setValue(-80.0)
    dialog.vmax_spin.setValue(-30.0)

    dialog.apply_button.click()

    assert spy.count() == 1
    assert spy.at(0) == ["viridis", -80.0, -30.0]
    assert dialog.result() == 0


def test_display_settings_rejects_inverted_range():
    QApplication.instance() or QApplication([])
    dialog = DisplaySettingsDialog("jet", -70.0, -20.0)
    spy = QSignalSpy(dialog.settings_applied)
    dialog.vmin_spin.setValue(-10.0)
    dialog.vmax_spin.setValue(-30.0)

    dialog.apply_button.click()

    assert spy.count() == 0
    assert dialog.error_label.text()


def test_display_settings_cancel_discards_unapplied_changes():
    QApplication.instance() or QApplication([])
    dialog = DisplaySettingsDialog("jet", -70.0, -20.0)
    spy = QSignalSpy(dialog.settings_applied)
    dialog.cmap_combo.setCurrentText("gray")

    dialog.cancel_button.click()

    assert spy.count() == 0
    assert dialog.result() == QDialog.DialogCode.Rejected


def test_display_settings_ok_applies_and_closes():
    QApplication.instance() or QApplication([])
    dialog = DisplaySettingsDialog("jet", -70.0, -20.0)
    spy = QSignalSpy(dialog.settings_applied)

    dialog.ok_button.click()

    assert spy.count() == 1
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_main_window_applies_and_remembers_display_settings():
    QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        window._apply_display_settings("inferno", -85.0, -25.0)
        assert window.display_settings == {
            "colormap": "inferno",
            "vmin": -85.0,
            "vmax": -25.0,
        }
        assert window.echogram._cmap_name == "inferno"
    finally:
        window.close()
