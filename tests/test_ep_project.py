import h5py
import numpy as np

from src.core.ep_project import EpProject, PROJECT_VERSION
from src.core.region import AnalysisRegion


def test_ep_project_11_round_trips_lines_region_and_display_settings(tmp_path):
    project = EpProject([tmp_path / "source.raw"])
    ping_times = np.array(["2026-08-27T01:00:00", "2026-08-27T01:00:01"], dtype="datetime64[ns]")
    project.line_manager.set_line_data("bottom", [20.0, 21.0], ping_times, kind="detected")
    project.line_manager.add_line("near_bottom", "Near Bottom", reference_id="bottom", offset_m=-1.0)
    project.analysis_region = AnalysisRegion("surface", "bottom")
    project.display_settings = {"colormap": "viridis", "vmin": -80.0, "vmax": -35.0}

    path = project.save(tmp_path / "project.ep")
    loaded = EpProject.load(path)

    assert PROJECT_VERSION == "1.1"
    assert loaded.get_line_manager().get("near_bottom").offset_m == -1.0
    assert loaded.analysis_region == AnalysisRegion("surface", "bottom")
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

    assert loaded.get_line_manager().get("surface").offset_m == 4.5
    assert loaded.get_line_manager().get("bottom").kind == "detected"
    np.testing.assert_allclose(loaded.get_line_manager().get("bottom").values, [18.0, 19.0])


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
