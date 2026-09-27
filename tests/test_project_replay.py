"""保存快照重算：输入校验、确定性结果、原始数据保护。"""

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from src.core.ep_project import EpProject
from src.core.region import AnalysisRegion
from src.core.replay import replay_project


def test_replay_is_repeatable_and_refuses_changed_raw(tmp_path, monkeypatch):
    from src.core import acoustic
    raw = tmp_path / "survey.raw"
    raw.write_bytes(b"survey")
    project = EpProject([raw], {"integration": {"esu_size": 2, "layer_width": 2}})
    project.surface_depth = 0
    project.line_manager.set_offset("surface", 0)
    project.processing_state = {"noise_applied": False, "noise_enabled": False}
    project.analysis_region = AnalysisRegion("surface", "bottom")
    project.analysis_region_enabled = False
    project.compute_checksums()
    path = project.save(tmp_path / "survey.ep")
    ds = xr.Dataset({"Sv": (("ping_time", "range_sample"), np.full((2, 3), -50.))},
                    coords={"ping_time": [0, 1], "range_sample": [0, 1, 2],
                            "echo_range": ("range_sample", [1., 2., 3.])})
    monkeypatch.setattr(acoustic, "open_single_file", lambda *args: object())
    monkeypatch.setattr(acoustic, "compute_sv", lambda *args: ds.copy(deep=True))
    monkeypatch.setattr(
        "src.core.processing.crop_sv_by_line_region",
        lambda *_args: pytest.fail("disabled analysis region must not crop replay data"),
    )
    replay_project(path, tmp_path / "one")
    replay_project(path, tmp_path / "two")
    pd.testing.assert_frame_equal(pd.read_csv(tmp_path / "one/integration.csv"),
                                  pd.read_csv(tmp_path / "two/integration.csv"))
    assert (tmp_path / "one/manifest.json").is_file()
    manifest = (tmp_path / "one/manifest.json").read_text(encoding="utf-8")
    assert '"analysis_region_enabled": false' in manifest
    assert '"saved_region"' not in manifest
    np.testing.assert_allclose(ds.Sv, -50.)
    with pytest.raises(FileExistsError):
        replay_project(path, tmp_path / "one")
    raw.write_bytes(b"changed")
    with pytest.raises(ValueError, match="校验"):
        replay_project(path, tmp_path / "changed")
    assert not (tmp_path / "changed").exists()


def test_gui_integration_worker_uses_replay_preparation_pipeline(monkeypatch, tmp_path):
    from src.core import processing
    from src.gui.workers import IntegrationWorker

    source = xr.Dataset(
        {"Sv": (("ping_time", "range_sample"), np.full((1, 2), -50.0))},
        coords={"ping_time": [0], "range_sample": [0, 1]},
    )
    raw_file = tmp_path / "input.raw"
    raw_file.write_bytes(b"raw input")
    processed = source.assign(Sv_corrected=source.Sv.copy())
    analysis = processed.isel(range_sample=slice(0, 1))
    calls = []
    result = object()
    monkeypatch.setattr(
        processing, "prepare_analysis_dataset",
        lambda *args: (calls.append(args) or processed, analysis),
    )

    import src.core.integration as integration

    monkeypatch.setattr(integration, "create_integration_grid", lambda ds, **_kwargs: ds)
    monkeypatch.setattr(integration, "integrate", lambda ds, *_args, **_kwargs: result)
    worker = IntegrationWorker(
        source, {"integration": {}}, noise_enabled=False,
        manual_mask=np.array([[False, True]]), region_enabled=True,
        channel_id="channel-a", raw_paths=[raw_file],
    )
    emitted = []
    worker.finished.connect(emitted.append)
    worker.run()

    assert calls and calls[0][0] is source
    assert calls[0][2] is False
    assert calls[0][3].tolist() == [[False, True]]
    assert calls[0][-1] is True
    assert worker.analysis_dataset is analysis
    assert worker.processed_dataset is processed
    assert worker.run_metadata["kind"] == "integration_run"
    assert worker.run_metadata["channel_id"] == "channel-a"
    assert worker.run_metadata["inputs"][0]["sha256"]
    assert worker.run_metadata["inputs"][0]["stable_during_hash"] is True
    assert worker.run_metadata["effective_settings"]["manual_mask"]["true_count"] == 1
    assert worker.run_metadata["effective_settings"]["integration"]["esu_size"] == 500.0
    assert worker.run_metadata["implementation_sha256"]
    assert emitted == [result]
