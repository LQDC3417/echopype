"""ESU 网格叠加：列名兼容、深度转换、可见性与摘要。"""

import os

import numpy as np
import pandas as pd
import pytest
import xarray as xr

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _echo_range_ds(n_samples: int = 20) -> xr.Dataset:
    return xr.Dataset(
        {"echo_range": ("range_sample", np.arange(n_samples, dtype=np.float64))},
    )


def test_set_grid_data_column_alias_and_meta(qapp):
    from src.viz.opengl_renderer import EchogramRenderer

    r = EchogramRenderer()
    r.set_data(np.zeros((50, 20), dtype=np.float32))
    # 列名用 mean_Sv（积分真实列），depth_start/end
    df = pd.DataFrame(
        {
            "ping_start": [0, 20],
            "ping_end": [20, 40],
            "depth_start": [0.0, 5.0],
            "depth_end": [5.0, 10.0],
            "mean_Sv": [-55.0, -60.0],
            "interval": [0, 1],
            "layer": [0, 0],
        }
    )
    r.set_grid_data(df, _echo_range_ds(20), color_by="mean_Sv")
    assert r._grid_cells is not None and len(r._grid_cells) == 2
    meta = r.grid_summary()
    assert meta["color_by"] == "mean_Sv"
    assert meta["n_cells"] == 2
    assert r._overlay_visibility["grid"] is True
    # 深度 5–10 m → sample 5–10
    assert r._grid_cells[0]["sample_start"] == 0
    assert r._grid_cells[0]["sample_end"] == 5

    r.set_grid_data(None)
    assert r.grid_summary() is None
    assert r._grid_cells is None


def test_grid_visibility_and_alpha(qapp):
    from src.viz.opengl_renderer import EchogramRenderer

    r = EchogramRenderer()
    r.set_overlay_visible("grid", False)
    assert r._overlay_visibility["grid"] is False
    r.set_grid_alpha(0.5)
    assert r._grid_alpha == 0.5
    with pytest.raises(ValueError):
        r.set_overlay_visible("nope", True)


def test_display_panel_grid_checkbox(qapp):
    from src.gui.property_panel import DisplaySettingsPanel

    panel = DisplaySettingsPanel()
    try:
        assert panel.chk_grid_overlay.isChecked()
        assert panel.chk_grid_overlay.objectName() == "chkGridOverlay"
    finally:
        panel.close()
