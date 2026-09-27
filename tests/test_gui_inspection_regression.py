"""光标深度与区域声学统计回归。"""

from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest
import xarray as xr

from src.gui.handlers.interaction_handlers import InteractionMixin


def _host():
    ds = xr.Dataset(
        {
            "Sv": (("ping_time", "range_sample"), np.full((2, 2), -90.0)),
            "echo_range": (("range_sample", "ping_time"), [[1., 10.], [2., 20.]]),
        },
        coords={"ping_time": [0, 1]},
    )
    return SimpleNamespace(
        _ds_Sv=ds, statusbar=Mock(), echogram=Mock(), region_table=Mock(),
        _noise_mask_manual=None, _undo_stack=[], _redo_stack=[],
    )


def test_cursor_depth_uses_actual_ping_and_handles_outside_view():
    host = _host()
    InteractionMixin._update_depth_at_cursor(host, 1, 1)
    host.statusbar.set_depth_info.assert_called_with(20.)
    InteractionMixin._update_depth_at_cursor(host, 9, 1)
    assert np.isnan(host.statusbar.set_depth_info.call_args.args[0])


def test_inspection_averages_displayed_sv_in_linear_domain():
    host = _host()
    host.echogram.get_data.return_value = np.array([[-40., -60.], [np.nan, np.inf]])
    InteractionMixin._inspect_region(host, 0, 0, 2, 2)
    assert host.region_table.add_region.call_args.kwargs["mean_sv"] == pytest.approx(
        10 * np.log10((1e-4 + 1e-6) / 2)
    )


def test_empty_noise_selection_does_not_create_history_or_start_processing():
    host = _host()
    InteractionMixin._add_noise_region(host, 9, 9, 10, 10)
    assert host._noise_mask_manual is None
    assert host._undo_stack == []
    host.echogram.set_noise_mask.assert_not_called()


def test_pipeline_continues_after_preserving_manual_bottom(monkeypatch):
    from src.gui.handlers.processing_handlers import ProcessingMixin, QTimer

    host = _host()
    host._config = {}
    host._bottom_manually_edited = True
    host._bottom_line = np.array([1., 1.])
    host._run_all_chain = True
    host._detect_schools = Mock()
    monkeypatch.setattr(QTimer, "singleShot", lambda delay, callback: callback())
    ProcessingMixin._detect_bottom(host)
    host._detect_schools.assert_called_once()
