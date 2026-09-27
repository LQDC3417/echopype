"""高优先级代码审查问题的回归测试。"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from src.core import acoustic
from src.core.export import export_to_zarr
from src.core.integration import IntegrationGrid, integrate
from src.core.merge import _resample_sv
from src.core.noise import (
    _legacy_apply_noise_reduction,
    apply_noise_reduction,
    estimate_noise_de_robertis,
)
from src.gui.handlers.file_handlers import FileMixin
from src.gui.handlers import interaction_handlers
from src.gui.handlers.interaction_handlers import InteractionMixin
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


def test_noise_reduction_covers_partial_ping_window():
    sv = np.full((25, 8), -80.0)

    noise, per_ping = estimate_noise_de_robertis(
        sv,
        np.arange(8.0),
        ping_num=10,
        range_sample_num=4,
    )

    assert noise.shape == sv.shape
    assert per_ping.shape == (25,)


def test_noise_reduction_uses_partial_range_window_in_db():
    sv = np.full((10, 4), -80.0)
    sv[:, 3] = -120.0

    _noise, per_ping = estimate_noise_de_robertis(
        sv,
        np.arange(4.0),
        ping_num=10,
        range_sample_num=3,
        noise_max=0.0,
    )

    assert per_ping.tolist() == pytest.approx([-120.0] * 10)


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


def test_legacy_noise_reduction_uses_configured_threshold_in_passive_mode():
    ds = _make_sv_dataset([[-40.0, -42.0], [-41.0, -43.0]])

    result = _legacy_apply_noise_reduction(
        ds,
        {
            "noise_removal": {
                "mode": "passive",
                "snr_threshold": -999.0,
                "low_Sv_dB": -150.0,
            }
        },
    )

    assert result["Sv_corrected"].values.tolist() == ds["Sv"].values.tolist()


def test_merge_resampling_handles_descending_echo_range():
    ds = _make_sv_dataset([[1.0, 2.0, 3.0]], echo_range=[3.0, 2.0, 1.0])

    result = _resample_sv(ds, np.array([1.0, 2.0, 3.0]))

    assert result.tolist() == [[3.0, 2.0, 1.0]]


def test_manual_mask_does_not_modify_raw_sv():
    ds = _make_sv_dataset([[1.0, 2.0, 3.0]])
    original = ds["Sv"].values.copy()

    corrected = apply_manual_mask(ds, np.array([[True, False, False]]))

    assert np.array_equal(ds["Sv"].values, original)
    assert np.isnan(corrected["Sv_corrected"].values[0, 0])


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
    host._channel_config_snapshot = lambda: {}

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


def test_noise_region_undo_keeps_the_previous_mask_snapshot():
    class Echogram:
        def set_noise_mask(self, _value):
            pass

    class RegionTable:
        def add_region(self, **_kwargs):
            pass

    host = type("Host", (), {})()
    host._ds_Sv = _make_sv_dataset([[1.0, 2.0], [3.0, 4.0]])
    host._noise_mask_manual = None
    host._undo_stack = []
    host._redo_stack = []
    host.echogram = Echogram()
    host.region_table = RegionTable()
    host._save_file_state = lambda: None
    host._apply_noise_params = lambda automatic=True: None

    InteractionMixin._add_noise_region(host, 0, 0, 1, 1)

    assert len(host._undo_stack) == 1
    assert host._undo_stack[0][0] == "noise_mask"
    assert host._undo_stack[0][1] is None


def test_undo_noise_mask_reapplies_noise_processing():
    class Echogram:
        def set_noise_mask(self, value):
            self.value = value

    class StatusBar:
        def set_status(self, _value):
            pass

    host = type("Host", (), {})()
    host._noise_mask_manual = np.array([[True]])
    host._undo_stack = [("noise_mask", None)]
    host._redo_stack = []
    host.echogram = Echogram()
    host.statusbar = StatusBar()
    host.noise_apply_calls = 0
    host.save_calls = 0
    host.stale_results = []

    def apply_noise(automatic=True):
        host.noise_apply_calls += 1

    def save_state():
        host.save_calls += 1

    def mark_results_stale(*names):
        host.stale_results.append(names)

    host._apply_noise_params = apply_noise
    host._save_file_state = save_state
    host._mark_results_stale = mark_results_stale

    InteractionMixin._undo(host)

    assert host._noise_mask_manual is None
    assert host.noise_apply_calls == 1
    assert host.save_calls == 1
    assert host.stale_results == [("noise", "bottom", "schools", "integration", "real_sed")]


def test_export_grid_uses_integration_dataframe(monkeypatch, tmp_path):
    class ExportDialog:
        Accepted = 1

        def __init__(self, _parent):
            pass

        def exec(self):
            return self.Accepted

        def get_formats(self):
            return ["csv"]

        def get_content(self):
            return {"sv": False, "schools": False, "grid": True}

    class StatusBar:
        def set_status(self, _value):
            pass

    exported = {}

    def export_density(df, path):
        exported["dataframe"] = df
        exported["path"] = path
        return path

    monkeypatch.setattr(interaction_handlers, "ExportDialog", ExportDialog)
    monkeypatch.setattr("src.core.export.export_density_to_csv", export_density)

    host = type("Host", (), {})()
    host._config = {"output": {"dir": str(tmp_path)}}
    host._ds_Sv = None
    host._schools_df = None
    host._integration_df = pd.DataFrame({"density_ind_ha": [1.0]})
    host.statusbar = StatusBar()
    host._ensure_result_exportable = lambda *_names: True
    host._input_incomplete = False

    InteractionMixin._export(host)

    assert exported["dataframe"] is host._integration_df
    assert exported["path"] == tmp_path / "grid_stats.csv"


def test_zarr_export_refuses_to_remove_existing_output(tmp_path, monkeypatch):
    output = tmp_path / "sv_data.zarr"
    output.mkdir()
    marker = output / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    monkeypatch.setattr(xr.Dataset, "to_zarr", lambda *args, **kwargs: None)

    with pytest.raises(FileExistsError):
        export_to_zarr(_make_sv_dataset([[1.0]]), output)

    assert marker.exists()


def test_process_all_files_keeps_successes_and_records_partial_open_failure(monkeypatch):
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

    result = acoustic.process_all_files({})

    assert result["Sv"].values.tolist() == [[1.0]]
    assert result.attrs["failed_raw_files"] == ["bad.raw"]


def test_process_all_files_processes_each_raw_without_combining_echodata(monkeypatch):
    first = Path("first.raw")
    second = Path("second.raw")
    echodata = {first: object(), second: object()}
    processed = {
        echodata[first]: _make_sv_dataset([[1.0, 1.0]]),
        echodata[second]: _make_sv_dataset([[2.0, 2.0]]).assign_coords(ping_time=[1]),
    }
    for dataset, bottom in zip(processed.values(), [10.0, 11.0]):
        dataset.coords["ping_time"] = np.asarray(dataset.ping_time.values, dtype="datetime64[ns]")
        dataset.coords["echo_range"] = ("range_sample", [1.0, 2.0])
        dataset["Sv_corrected"] = dataset["Sv"] - 1.0
        dataset["bottom_depth"] = ("ping_time", [bottom])
    monkeypatch.setattr(acoustic, "load_raw_files", lambda config: [first, second])
    monkeypatch.setattr(acoustic, "open_single_file", lambda path, config: echodata[path])
    calls = []
    monkeypatch.setattr(
        acoustic,
        "process_single_file",
        lambda value, config: calls.append(value) or processed[value],
    )

    import echopype as ep

    monkeypatch.setattr(
        ep,
        "combine_echodata",
        lambda *args, **kwargs: pytest.fail("CLI must not combine all EchoData objects"),
    )

    result = acoustic.process_all_files({})

    assert calls == [echodata[first], echodata[second]]
    assert result.sizes["ping_time"] == 2
    assert result["Sv"].values[0, :, 0].tolist() == [1.0, 2.0]
    assert result["Sv_corrected"].values[0, :, 0].tolist() == [0.0, 1.0]
    assert result["bottom_depth"].values.tolist() == [10.0, 11.0]
