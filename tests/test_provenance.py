import json
from datetime import datetime

import numpy as np

from src.core.ep_project import EpProject
from src.core.provenance import config_input_fingerprint
from src.core.region import AnalysisRegion


def test_fingerprint_is_order_independent_but_tracks_configuration():
    first = config_input_fingerprint({"b": {"y": 2, "x": 1}, "a": 3}, {"b.raw": "b", "a.raw": "a"})
    assert first == config_input_fingerprint({"a": 3, "b": {"x": 1, "y": 2}}, {"a.raw": "a", "b.raw": "b"})
    assert first != config_input_fingerprint({"a": 4, "b": {"x": 1, "y": 2}}, {"a.raw": "a", "b.raw": "b"})


def test_snapshot_round_trip_and_independent_manifest(tmp_path):
    raw = tmp_path / "source.raw"
    raw.write_bytes(b"acoustic sample")
    project = EpProject([raw], {"threshold_db": -65})
    project.compute_checksums()
    project.processing_state = {"noise_applied": True, "stale_results": []}
    project.line_manager.set_line_data("bottom", [10.0, 11.0], kind="manual")
    project.analysis_region = AnalysisRegion("surface", "bottom")
    project.noise_mask = np.array([[True, False], [False, True]])

    loaded = EpProject.load(project.save(tmp_path / "snapshot.ep"))
    assert loaded.provenance == project.provenance
    assert loaded.processing_state == project.processing_state
    assert loaded.provenance["kind"] == "project_snapshot"
    assert datetime.fromisoformat(loaded.provenance["generated_at_utc"]).utcoffset().total_seconds() == 0
    assert set(loaded.provenance["versions"]) == {"python", "echopype", "numpy", "xarray"}
    manifest = json.loads(loaded.export_manifest(tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["config_input_fingerprint"] == loaded.provenance["config_input_fingerprint"]
    assert manifest["noise_mask"]["true_count"] == 2
    assert manifest["analysis_region"] == {"upper_line_id": "surface", "lower_line_id": "bottom"}
    assert manifest["inputs"][0]["checksum"] == project.raw_checksums[str(raw)]
    assert manifest["lines"] == loaded.provenance["lines"]
    assert manifest["results_status"] == "unverified"
    loaded.config["threshold_db"] = -70
    assert loaded.provenance["config"]["threshold_db"] == -65
    assert loaded.build_manifest()["config_input_fingerprint"] != manifest["config_input_fingerprint"]
