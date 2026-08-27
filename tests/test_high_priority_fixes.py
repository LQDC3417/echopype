"""高优先级代码审查问题的回归测试。"""

import numpy as np
import xarray as xr
import pytest
from pathlib import Path

from src.core.integration import IntegrationGrid, integrate
from src.core.merge import _resample_sv
from src.core.noise import apply_noise_reduction, estimate_noise_de_robertis
from src.core.export import export_to_zarr
from src.core import acoustic
from src.gui.handlers.file_handlers import FileMixin
from src.gui.handlers.processing_handlers import ProcessingMixin
from src.gui.workers import apply_manual_mask


def _make_sv_dataset(values, echo_range=None):
    values = np.asarray(values, dtype=float)
    dims = ("ping_time", "range_sample")
    coords = {
        "ping_time": np.arange(values.shape[0]),
        "range_sample": np.arange(values.shape[1]),
    }
    ds = xr.Dataset({"Sv": (dims, values)}, coords=coords)
    if echo_range is not None:
        ds = ds.assign_coords(echo_range=("range_sample", np.asarray(echo_range, dtype=float)))
    return ds


def test_integration_threshold_excludes_samples_from_abc():
    ds = _make_sv_dataset([[-80.0, -30.0]], echo_range=[0.0, 1.0])
    grid = IntegrationGrid(
        n_intervals=1,
        n_layers=1,
        ping_start=np.array([0]),
        ping_end=np.array([1]),
        depth_start=np.array([0.0]),
        depth_end=np.array([2.0]),
    )

    result = integrate(ds, grid, min_threshold=-70.0, max_threshold=0.0)

    expected = 4 * np.pi * 10 ** (-30.0 / 10.0)
    assert result.n_good[0, 0] == 1
    assert result.abc[0, 0] == pytest.approx(expected)


def test_noise_reduction_adapts_windows_to_small_dataset():
    sv = np.full((10, 20), -40.0)

    noise, per_ping = estimate_noise_de_robertis(
        sv,
        np.arange(20.0),
        ping_num=40,
        range_sample_num=50,
    )

    assert noise.shape == sv.shape
    assert per_ping.shape == (10,)


def test_noise_reduction_keeps_channel_specific_results():
    values = np.stack([
        np.full((2, 3), -30.0),
        np.full((2, 3), -10.0),
    ])
    ds = xr.Dataset(
        {
            "Sv": (("channel", "ping_time", "range_sample"), values),
            "depth": (("ping_time", "range_sample"), [[1.0, 2.0, 3.0]] * 2),
        },
        coords={
            "channel": [1, 2],
            "ping_time": [0, 1],
            "range_sample": [0, 1, 2],
        },
    )

    result = apply_noise_reduction(
        ds,
        {"noise_removal": {"ping_num": 1, "range_sample_num": 1, "snr_threshold": -999}},
    )

    means = np.nanmean(result["Sv_corrected"].values, axis=(1, 2))
    assert means.tolist() == pytest.approx([-30.0, -10.0])


def test_merge_resampling_handles_descending_echo_range():
    ds = _make_sv_dataset([[1.0, 2.0, 3.0]], echo_range=[3.0, 2.0, 1.0])

    result = _resample_sv(ds, np.array([1.0, 2.0, 3.0]))

    assert result.tolist() == [[3.0, 2.0, 1.0]]


def test_manual_mask_does_not_modify_raw_sv():
    ds = _make_sv_dataset([[1.0, 2.0, 3.0]])
    original = ds["Sv"].values.copy()

    apply_manual_mask(ds, np.array([[True, False, False]]))

    assert np.array_equal(ds["Sv"].values, original)
    assert np.isnan(ds["Sv_corrected"].values[0, 0])


def test_analysis_region_switch_keeps_full_dataset_when_disabled():
    ds = _make_sv_dataset(np.arange(12, dtype=float).reshape(3, 4))
    host = type("Host", (), {})()
    host._ds_Sv = ds
    host._ds_Sv_analysis = None
    host._analysis_region_enabled = False
    host._surface_depth_m = 1.0
    host._bottom_line = np.array([2, 2, 2])

    ProcessingMixin._apply_analysis_region_to_ds(host)

    assert host._ds_Sv_analysis is ds


def test_reset_analysis_state_clears_previous_project_results():
    class Echogram:
        def __init__(self):
            self.bottom = object()
            self.noise = object()
            self.school = object()

        def set_bottom_line(self, value):
            self.bottom = value

        def set_noise_mask(self, value):
            self.noise = value

        def set_school_mask(self, value):
            self.school = value

    host = type("Host", (), {})()
    host.echogram = Echogram()
    host._noise_mask_manual = object()
    host._bottom_line = object()
    host._bottom_manually_edited = True
    host._schools_mask = object()
    host._schools_df = object()
    host._integration_df = object()
    host._real_sed_df = object()
    host._ds_Sv_analysis = object()

    FileMixin._reset_analysis_state(host)

    assert host._noise_mask_manual is None
    assert host._bottom_line is None
    assert host._schools_mask is None
    assert host._schools_df is None
    assert host._integration_df is None
    assert host._real_sed_df is None
    assert host._ds_Sv_analysis is None
    assert host.echogram.bottom is None
    assert host.echogram.noise is None
    assert host.echogram.school is None


def test_zarr_export_refuses_to_remove_existing_output(tmp_path, monkeypatch):
    output = tmp_path / "sv_data.zarr"
    output.mkdir()
    marker = output / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    monkeypatch.setattr(xr.Dataset, "to_zarr", lambda *args, **kwargs: None)

    with pytest.raises(FileExistsError):
        export_to_zarr(_make_sv_dataset([[1.0]]), output)

    assert marker.exists()


def test_process_all_files_reports_partial_open_failure(monkeypatch):
    good = Path("good.raw")
    bad = Path("bad.raw")
    monkeypatch.setattr(acoustic, "load_raw_files", lambda config: [good, bad])
    monkeypatch.setattr(acoustic, "open_single_file", lambda path, config: object())

    def open_with_failure(path, config):
        if path == bad:
            raise OSError("broken raw file")
        return object()

    monkeypatch.setattr(acoustic, "open_single_file", open_with_failure)
    monkeypatch.setattr(acoustic, "process_single_file", lambda ed, config: _make_sv_dataset([[1.0]]))

    with pytest.raises(RuntimeError, match="bad.raw"):
        acoustic.process_all_files({})
