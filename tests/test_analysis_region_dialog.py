from PySide6.QtWidgets import QApplication

from src.gui.analysis_region_dialog import AnalysisRegionDialog


def test_analysis_region_dialog_applies_distinct_boundaries():
    QApplication.instance() or QApplication([])
    dialog = AnalysisRegionDialog(
        [("surface", "Surface"), ("bottom", "Bottom")],
        upper_line_id="surface",
        lower_line_id="bottom",
    )
    applied = []
    dialog.region_applied.connect(lambda upper, lower: applied.append((upper, lower)))

    assert dialog.apply_changes()
    assert applied == [("surface", "bottom")]


def test_analysis_region_dialog_rejects_same_boundary():
    QApplication.instance() or QApplication([])
    dialog = AnalysisRegionDialog(
        [("surface", "Surface"), ("bottom", "Bottom")],
        upper_line_id="surface",
        lower_line_id="bottom",
    )
    dialog.lower_combo.setCurrentIndex(0)

    assert not dialog.apply_changes()
    assert "different" in dialog.error_label.text().lower()
