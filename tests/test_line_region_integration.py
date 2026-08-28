import numpy as np
import xarray as xr

from src.core.lines import LineManager
from src.core.region import AnalysisRegion, crop_sv_by_line_region
from src.gui.handlers.processing_handlers import ProcessingMixin


def _dataset():
    ping_times = np.array([10, 20, 30])
    echo_range = np.broadcast_to(np.arange(5.0), (3, 5)).copy()
    return xr.Dataset(
        {
            "Sv": (("ping_time", "range_sample"), np.full((3, 5), -50.0)),
            "echo_range": (("ping_time", "range_sample"), echo_range),
        },
        coords={"ping_time": ping_times, "range_sample": np.arange(5)},
    )


def _manager():
    manager = LineManager()
    manager.set_line_data("upper", [1.0, np.nan, 3.0], [10, 20, 30])
    manager.set_line_data("lower", [3.0, 4.0, 2.0], [10, 20, 30])
    return manager


def test_crop_resolves_arbitrary_lines_by_ping_time_and_excludes_invalid_pings():
    cropped, excluded = crop_sv_by_line_region(
        _dataset(), _manager(), AnalysisRegion("upper", "lower")
    )

    assert excluded == 2
    valid = np.isfinite(cropped["Sv"].values)
    np.testing.assert_array_equal(valid[0], [False, True, True, True, False])
    assert not valid[1:].any()


class _Echogram:
    def __init__(self):
        self.lines = None
        self.colors = None

    def set_lines(self, lines, colors=None):
        self.lines = lines
        self.colors = colors

    def set_bottom_line(self, _line):
        pass


class _StatusBar:
    def __init__(self):
        self.messages = []

    def set_status(self, message):
        self.messages.append(message)


class _Host(ProcessingMixin):
    def __init__(self):
        self._ds_Sv = _dataset()
        self._ds_Sv_analysis = None
        self._analysis_region_cache_key = None
        self._analysis_region_enabled = True
        self.line_manager = _manager()
        self.analysis_region = AnalysisRegion("upper", "lower")
        self._active_line_id = "upper"
        self.echogram = _Echogram()
        self.statusbar = _StatusBar()
        self.saved = 0
        self.errors = []

    def _save_file_state(self):
        self.saved += 1

    def _append_error_message(self, message):
        self.errors.append(message)


def test_processing_edit_converts_renderer_samples_to_metres_and_manual_line():
    host = _Host()
    host.line_manager.add_line("derived", "Derived", reference_id="upper", offset_m=1.0)
    host._active_line_id = "derived"

    host._on_line_edited("derived", np.array([2.0, 3.0, 4.0]))

    line = host.line_manager.get("derived")
    assert line.kind == "manual"
    assert line.reference_id is None
    np.testing.assert_allclose(line.values, [2.0, 3.0, 4.0])
    np.testing.assert_array_equal(line.ping_times, [10, 20, 30])
    assert host._ds_Sv_analysis is None


def test_processing_region_cache_invalidates_when_line_manager_changes():
    host = _Host()
    first = host._get_analysis_ds()

    host.line_manager.set_line_data("lower", [4.0, 4.0, 4.0], [10, 20, 30])
    second = host._get_analysis_ds()

    assert second is not first
    assert np.isfinite(second["Sv"].values[0]).sum() == 4
    assert any("2" in message for message in host.errors)


def test_processing_sync_passes_persisted_line_colors_to_renderer():
    host = _Host()

    host._sync_lines_to_renderer()

    assert host.echogram.colors["upper"] == host.line_manager.get("upper").color
    assert host.echogram.colors["lower"] == host.line_manager.get("lower").color
