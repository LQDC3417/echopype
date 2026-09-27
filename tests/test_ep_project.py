import h5py
import numpy as np
import pandas as pd

from src.core.ep_project import EpProject, PROJECT_VERSION
from src.core.region import AnalysisRegion


def test_ep_project_11_round_trips_lines_region_and_display_settings(tmp_path):
    project = EpProject([tmp_path / "source.raw"])
    ping_times = np.array(["2026-08-27T01:00:00", "2026-08-27T01:00:01"], dtype="datetime64[ns]")
    project.line_manager.set_line_data("bottom", [20.0, 21.0], ping_times, kind="detected")
    project.line_manager.add_line("near_bottom", "Near Bottom", reference_id="bottom", offset_m=-1.0)
    project.analysis_region = AnalysisRegion("surface", "bottom")
    project.analysis_region_enabled = False
    project.display_settings = {"colormap": "viridis", "vmin": -80.0, "vmax": -35.0}

    path = project.save(tmp_path / "project.ep")
    loaded = EpProject.load(path)

    assert PROJECT_VERSION == "1.3"
    assert loaded.get_line_manager().get("near_bottom").offset_m == -1.0
    assert loaded.analysis_region == AnalysisRegion("surface", "bottom")
    assert loaded.analysis_region_enabled is False
    assert loaded.display_settings == {"colormap": "viridis", "vmin": -80.0, "vmax": -35.0}
    np.testing.assert_allclose(loaded.get_line_manager().get("bottom").values, [20.0, 21.0])
    assert loaded.get_line_manager().get("bottom").ping_times.dtype == np.dtype("datetime64[ns]")


def test_ep_project_migrates_legacy_surface_and_bottom_fields(tmp_path):
    path = tmp_path / "legacy.ep"
    with h5py.File(path, "w") as handle:
        metadata = handle.create_group("metadata")
        metadata.create_dataset("raw_files", data=[])
        metadata.create_dataset("raw_checksums", data=[])
        metadata.create_dataset("config", data="{}")
        metadata.attrs["version"] = "1.0"
        analysis = handle.create_group("analysis")
        analysis.create_dataset("surface_depth", data=4.5)
        analysis.create_dataset("bottom_line", data=np.array([18.0, 19.0], dtype=np.float32))

    loaded = EpProject.load(path)

    assert loaded.provenance == {}
    assert loaded.processing_state == {}
    assert loaded.analysis_region_enabled is False
    assert loaded.get_line_manager().get("surface").offset_m == 4.5
    assert loaded.get_line_manager().get("bottom").kind == "detected"
    assert loaded.analysis_region_enabled is False
    np.testing.assert_allclose(loaded.get_line_manager().get("bottom").values, [18.0, 19.0])


def test_ep_project_legacy_region_defaults_to_enabled(tmp_path):
    path = tmp_path / "legacy-region.ep"
    with h5py.File(path, "w") as handle:
        metadata = handle.create_group("metadata")
        metadata.create_dataset("raw_files", data=[])
        metadata.create_dataset("raw_checksums", data=[])
        metadata.create_dataset("config", data="{}")
        analysis = handle.create_group("analysis")
        analysis.create_dataset(
            "analysis_region",
            data='{"upper_line_id":"surface","lower_line_id":"bottom"}',
        )

    loaded = EpProject.load(path)

    assert loaded.analysis_region == AnalysisRegion("surface", "bottom")
    assert loaded.analysis_region_enabled is True


def test_line_model_surface_offset_is_authoritative_when_saving(tmp_path):
    project = EpProject()
    project.line_manager.set_offset("surface", 7.5)

    path = project.save(tmp_path / "surface.ep")
    loaded = EpProject.load(path)

    assert loaded.surface_depth == 7.5
    assert loaded.line_manager.get("surface").offset_m == 7.5
    with h5py.File(path, "r") as handle:
        assert float(handle["analysis/surface_depth"][()]) == 7.5


def test_new_project_keeps_writing_legacy_bottom_field_from_line_model(tmp_path):
    project = EpProject()
    project.line_manager.set_line_data("bottom", [30.0, 31.0], kind="manual")

    path = project.save(tmp_path / "bottom.ep")

    with h5py.File(path, "r") as handle:
        np.testing.assert_allclose(handle["analysis/bottom_line"][()], [30.0, 31.0])


def test_ep_project_round_trips_sed_targets_and_grid_separately(tmp_path):
    project = EpProject()
    targets = pd.DataFrame(
        {
            "target_id": [1],
            "ping_idx": [3],
            "range_m": [12.5],
            "ts_db": [-55.5],
        }
    )
    grid = pd.DataFrame(
        {
            "interval": [0],
            "ping_start": [0],
            "ping_end": [9],
            "depth_start": [2.5],
            "depth_end": [20.5],
            "n_targets": [1],
        }
    )
    project.sed_df = targets
    project.sed_grid_df = grid

    loaded = EpProject.load(project.save(tmp_path / "sed.ep"))

    pd.testing.assert_frame_equal(loaded.sed_df, targets)
    pd.testing.assert_frame_equal(loaded.sed_grid_df, grid)


def test_ep_project_round_trips_result_table_values_types_and_index_losslessly(tmp_path):
    index = pd.Index([31, 47], name="record_id")
    frame = pd.DataFrame(
        {
            "tiny": np.array([1.23456789e-11, np.nan]),
            "float32": np.array([1.25, np.nan], dtype=np.float32),
            "count": pd.array([7, pd.NA], dtype="Int64"),
            "enabled": pd.array([True, pd.NA], dtype="boolean"),
            "when": pd.to_datetime(["2026-09-26T12:34:56.123456789", None]),
            "label": np.array(["淡水调查", None], dtype=object),
            "text": pd.array(["中文", pd.NA], dtype="string"),
        },
        index=index,
    )
    project = EpProject()
    project.integration_df = frame

    loaded = EpProject.load(project.save(tmp_path / "precise.ep"))

    pd.testing.assert_frame_equal(loaded.integration_df, frame, check_exact=True)
    assert loaded.schools_df is None


def test_ep_project_round_trips_per_channel_result_provenance(tmp_path):
    provenance = {
        "integration": {
            "kind": "integration_run",
            "channel_id": "WBT 401661-15 ES200-7C_ES",
            "inputs": [{"path": "survey.raw", "sha256": "abc123"}],
            "effective_settings": {"noise_enabled": False, "manual_mask": None},
        }
    }
    project = EpProject()
    project.channel_states["WBT 401661-15 ES200-7C_ES"] = {
        "result_provenance": provenance,
    }

    loaded = EpProject.load(project.save(tmp_path / "run-provenance.ep"))

    assert loaded.channel_states["WBT 401661-15 ES200-7C_ES"]["result_provenance"] == provenance


def test_ep_project_distinguishes_empty_result_table_from_none(tmp_path):
    project = EpProject()
    project.schools_df = pd.DataFrame(
        {"label": pd.Series([], dtype="string"), "count": pd.Series([], dtype="int64")},
        index=pd.Index([], dtype="int64", name="record_id"),
    )

    loaded = EpProject.load(project.save(tmp_path / "empty.ep"))

    assert loaded.integration_df is None
    pd.testing.assert_frame_equal(loaded.schools_df, project.schools_df, check_exact=True)


def test_ep_project_reads_legacy_json_result_table(tmp_path):
    path = tmp_path / "legacy-results.ep"
    with h5py.File(path, "w") as handle:
        metadata = handle.create_group("metadata")
        metadata.create_dataset("raw_files", data=[])
        metadata.create_dataset("raw_checksums", data=[])
        metadata.create_dataset("config", data="{}")
        metadata.attrs["version"] = "1.2"
        results = handle.create_group("results")
        results.create_dataset("integration_df", data='[{"count":1,"station":"湖区"}]')

    loaded = EpProject.load(path)

    assert loaded.integration_df.to_dict(orient="records") == [
        {"count": 1, "station": "湖区"}
    ]


def test_unsupported_result_objects_do_not_replace_existing_project(tmp_path):
    path = tmp_path / "existing.ep"
    original = EpProject()
    original.integration_df = pd.DataFrame({"count": [3]})
    original.save(path)
    original_bytes = path.read_bytes()

    changed = EpProject()
    changed.integration_df = pd.DataFrame({"value": [object()]})
    try:
        changed.save(path)
    except TypeError as exc:
        assert "不支持的 DataFrame 列类型" in str(exc)
    else:
        raise AssertionError("不支持的对象列必须拒绝保存")

    assert path.read_bytes() == original_bytes
    pd.testing.assert_frame_equal(EpProject.load(path).integration_df, original.integration_df)
