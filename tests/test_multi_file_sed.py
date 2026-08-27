from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import xarray as xr


def _dataset(times):
    times = np.asarray(times, dtype="datetime64[ns]")
    return xr.Dataset(
        {"Sv": (("ping_time", "range_sample"), np.zeros((len(times), 2)))},
        coords={
            "ping_time": times,
            "echo_range": ("range_sample", np.array([0.0, 10.0])),
        },
    )


def _install_sed_mocks(monkeypatch, targets_by_echodata, times_by_echodata, bad_path=None):
    import echopype as ep

    from src.core import acoustic, sed

    opened = []
    echodata_by_path = {
        path: object() for path in times_by_echodata if isinstance(path, Path)
    }
    local_times = {
        echodata_by_path[path]: times for path, times in times_by_echodata.items()
    }

    def open_single_file(path, config):
        opened.append(path)
        if path == bad_path:
            raise OSError("broken raw")
        return echodata_by_path[path]

    monkeypatch.setattr(acoustic, "open_single_file", open_single_file)
    monkeypatch.setattr(acoustic, "_detect_waveform_mode", lambda echodata: ("CW", "complex"))
    monkeypatch.setattr(
        "echopype.calibrate.compute_TS",
        lambda echodata, **kwargs: xr.Dataset(coords={"ping_time": local_times[echodata]}),
    )
    monkeypatch.setattr(
        sed,
        "detect_single_targets_real",
        lambda echodata, ds_ts, config: targets_by_echodata[echodata].copy(),
    )
    aggregated = []

    def aggregate(targets, ds_sv, config):
        aggregated.append(targets.copy())
        return pd.DataFrame({"n_targets": [len(targets)]})

    monkeypatch.setattr(sed, "aggregate_targets_to_grid", aggregate)

    def fail_combine(*args, **kwargs):
        raise AssertionError("multi-file SED must not combine EchoData")

    monkeypatch.setattr(ep, "combine_echodata", fail_combine)
    return opened, echodata_by_path, aggregated


def test_multi_file_sed_maps_ping_time_filters_region_and_aggregates_once(monkeypatch):
    from src.gui.workers import MultiFileRealSedWorker

    t = np.array(
        ["2026-01-01T00:00:00", "2026-01-01T00:00:01", "2026-01-01T00:00:02", "2026-01-01T00:00:03"],
        dtype="datetime64[ns]",
    )
    first, second = Path("first.raw"), Path("second.raw")
    times_by_path = {first: t[[0, 2]], second: t[[1, 3]]}
    placeholder_targets = {}
    opened, echodata_by_path, aggregated = _install_sed_mocks(
        monkeypatch, placeholder_targets, times_by_path
    )
    placeholder_targets.update(
        {
            echodata_by_path[first]: pd.DataFrame(
                {"target_id": [1, 2], "ping_idx": [0, 1], "range_m": [1.0, 5.0], "ts_db": [-40.0, -41.0]}
            ),
            echodata_by_path[second]: pd.DataFrame(
                {"target_id": [1], "ping_idx": [0], "range_m": [4.0], "ts_db": [-42.0]}
            ),
        }
    )

    worker = MultiFileRealSedWorker(
        [first, second],
        _dataset(t),
        {},
        upper_depth_m=np.full(4, 2.0),
        lower_depth_m=np.full(4, 8.0),
    )
    finished, errors = [], []
    worker.finished.connect(finished.append)
    worker.error.connect(errors.append)
    worker.run()

    assert errors == []
    assert opened == [first, second]
    assert len(aggregated) == 1
    result = finished[0]
    assert result.failed_files == ()
    assert result.targets_df["target_id"].tolist() == [1, 2]
    assert result.targets_df["ping_idx"].tolist() == [1, 2]
    assert result.targets_df["local_ping_index"].tolist() == [0, 1]
    assert result.targets_df["source_file"].tolist() == ["second.raw", "first.raw"]
    pd.testing.assert_frame_equal(result.targets_df, aggregated[0])
    assert result.grid_df["n_targets"].tolist() == [2]


def test_multi_file_sed_continues_after_partial_failure(monkeypatch):
    from src.gui.workers import MultiFileRealSedWorker

    t = np.array(["2026-01-01", "2026-01-02"], dtype="datetime64[ns]")
    good, bad = Path("good.raw"), Path("bad.raw")
    targets = {}
    opened, echodata_by_path, _ = _install_sed_mocks(
        monkeypatch, targets, {good: t[:1], bad: t[1:]}, bad_path=bad
    )
    targets[echodata_by_path[good]] = pd.DataFrame(
        {"target_id": [1], "ping_idx": [0], "range_m": [5.0], "ts_db": [-40.0]}
    )

    worker = MultiFileRealSedWorker([good, bad], _dataset(t), {})
    finished, errors, progress = [], [], []
    worker.finished.connect(finished.append)
    worker.error.connect(errors.append)
    worker.progress.connect(progress.append)
    worker.run()

    assert errors == []
    assert opened == [good, bad]
    assert [failure.path for failure in finished[0].failed_files] == ["bad.raw"]
    assert any("bad.raw" in message for message in progress)


def test_multi_file_sed_errors_only_when_all_files_fail(monkeypatch):
    from src.core import acoustic
    from src.gui.workers import MultiFileRealSedWorker

    paths = [Path("bad1.raw"), Path("bad2.raw")]
    monkeypatch.setattr(acoustic, "open_single_file", lambda path, config: (_ for _ in ()).throw(OSError(path.name)))
    worker = MultiFileRealSedWorker(paths, _dataset(np.array(["2026-01-01"], dtype="datetime64[ns]")), {})
    finished, errors = [], []
    worker.finished.connect(finished.append)
    worker.error.connect(errors.append)
    worker.run()

    assert finished == []
    assert len(errors) == 1
    assert "bad1.raw" in errors[0]
    assert "bad2.raw" in errors[0]


def test_multi_file_sed_stops_safely_when_interruption_is_requested(monkeypatch):
    from src.gui.workers import MultiFileRealSedWorker

    t = np.array(["2026-01-01", "2026-01-02"], dtype="datetime64[ns]")
    first, second = Path("first.raw"), Path("second.raw")
    targets = {}
    opened, echodata_by_path, aggregated = _install_sed_mocks(
        monkeypatch, targets, {first: t[:1], second: t[1:]}
    )
    for echodata in echodata_by_path.values():
        targets[echodata] = pd.DataFrame(columns=["target_id", "ping_idx", "range_m", "ts_db"])

    worker = MultiFileRealSedWorker([first, second], _dataset(t), {})
    monkeypatch.setattr(worker, "isInterruptionRequested", lambda: bool(opened))
    finished, errors = [], []
    worker.finished.connect(finished.append)
    worker.error.connect(errors.append)
    worker.run()

    assert opened == [first]
    assert aggregated == []
    assert finished == []
    assert errors == []


def test_single_file_sed_keeps_legacy_result_and_accepts_optional_boundaries(monkeypatch):
    from src.core import acoustic, sed
    from src.gui.workers import RealSedWorker

    times = np.array(["2026-01-01", "2026-01-02"], dtype="datetime64[ns]")
    echodata = object()
    monkeypatch.setattr(acoustic, "_detect_waveform_mode", lambda value: ("CW", "complex"))
    monkeypatch.setattr(
        "echopype.calibrate.compute_TS",
        lambda value, **kwargs: xr.Dataset(coords={"ping_time": times}),
    )
    monkeypatch.setattr(
        sed,
        "detect_single_targets_real",
        lambda *args: pd.DataFrame(
            {"target_id": [1, 2], "ping_idx": [0, 1], "range_m": [1.0, 5.0], "ts_db": [-40.0, -41.0]}
        ),
    )
    monkeypatch.setattr(
        sed,
        "aggregate_targets_to_grid",
        lambda targets, ds, config: pd.DataFrame({"n_targets": [len(targets)]}),
    )

    worker = RealSedWorker(
        echodata,
        _dataset(times),
        {},
        upper_depth_m=np.full(2, 2.0),
        lower_depth_m=np.full(2, 8.0),
    )
    finished, errors = [], []
    worker.finished.connect(finished.append)
    worker.error.connect(errors.append)
    worker.run()

    assert errors == []
    targets_df, grid_df = finished[0]
    assert targets_df["ping_idx"].tolist() == [1]
    assert grid_df["n_targets"].tolist() == [1]


def test_analysis_mixin_resolves_active_region_for_global_pings():
    from src.core.lines import LineManager
    from src.core.region import AnalysisRegion
    from src.gui.handlers.analysis_handlers import AnalysisMixin

    times = np.array(["2026-01-01", "2026-01-02"], dtype="datetime64[ns]")
    lines = LineManager()
    lines.set_line_data("bottom", [8.0, 9.0], ping_times=times, kind="detected")
    host = SimpleNamespace(
        _ds_Sv=_dataset(times),
        line_manager=lines,
        analysis_region=AnalysisRegion("surface", "bottom"),
    )

    upper, lower = AnalysisMixin._get_sed_region_boundaries(host)

    np.testing.assert_array_equal(upper, [2.0, 2.0])
    np.testing.assert_array_equal(lower, [8.0, 9.0])
