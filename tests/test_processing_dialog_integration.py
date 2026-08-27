from PySide6.QtWidgets import QApplication

from src.gui.property_panel import ProcessingTab


def test_processing_groups_are_exposed_for_feature_dialogs():
    QApplication.instance() or QApplication([])
    tab = ProcessingTab()

    assert tab.noise_group.title()
    assert tab.school_group.title()
    assert tab.integration_group.title()
    assert tab.real_sed_group.title()


def test_hidden_processing_tab_has_no_apply_all_entry():
    QApplication.instance() or QApplication([])
    tab = ProcessingTab()

    assert not hasattr(tab, "btn_apply_all")
