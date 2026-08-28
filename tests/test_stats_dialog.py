import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pandas as pd
from PySide6.QtWidgets import QApplication

from src.gui.i18n import T
from src.gui.stats_dialog import StatsDialog


def test_export_current_real_sed_tab_exports_real_sed_results(monkeypatch):
    QApplication.instance() or QApplication([])
    dialog = StatsDialog()
    dialog._real_sed_df = pd.DataFrame({"n_targets": [1]})
    exported = []
    monkeypatch.setattr(
        dialog,
        "_export_dataframe",
        lambda dataframe, name: exported.append((dataframe, name)),
    )
    dialog.tabs.setCurrentIndex(2)

    dialog._on_export_clicked()

    assert exported == [(dialog._real_sed_df, T("stats_tab_real_sed"))]
