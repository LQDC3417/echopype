from pathlib import Path

import numpy as np
import pandas as pd

from src.core.ep_project import EpProject
from src.core.lines import LineManager
from src.core.region import AnalysisRegion
from src.gui.handlers import file_handlers
from src.gui.handlers.file_handlers import FileMixin


class _StatusBar:
    def __init__(self):
        self.message = ""

    def set_status(self, message):
        self.message = message


class _Echogram:
    def __init__(self):
        self.bottom = object()
        self.noise = object()
        self.school = object()
        self.lines = None
        self.colormap = None
        self.single_targets = None

    def set_bottom_line(self, value):
        self.bottom = value

    def set_noise_mask(self, value):
        self.noise = value

    def set_school_mask(self, value):
        self.school = value

    def set_lines(self, lines):
        self.lines = lines

    def set_colormap(self, name, vmin, vmax):
        self.colormap = (name, vmin, vmax)

    def set_single_targets(self, value):
        self.single_targets = value


class _Toolbar:
    def __init__(self):
        self.lines = None

    def set_editable_lines(self, lines):
        self.lines = list(lines)


class _StatsDialog:
    def __init__(self):
        self.schools = None
        self.integration = None
        self.sed_grid = None

    def update_schools(self, value):
        self.schools = value

    def update_integration(self, value):
        self.integration = value

    def update_real_sed(self, value):
        self.sed_grid = value


class _Host(FileMixin):
    pass


class _RunningWorker:
    def isRunning(self):
        return True


def _host():
    host = _Host()
    host.echogram = _Echogram()
    host.echo_toolbar = _Toolbar()
    host.statusbar = _StatusBar()
    host._config = {}
    host._surface_depth_m = 2.0
    host._noise_mask_manual = None
    host._bottom_line = None
    host._bottom_manually_edited = False
    host._schools_mask = None
    host._schools_df = None
    host._integration_df = None
    host._real_sed_df = None
    host._real_sed_grid_df = None
    host.stats_dialog = _StatsDialog()
    host._ds_Sv_analysis = None
    host._analysis_region_enabled = False
    host.line_manager = LineManager()
    host.analysis_region = None
    host.display_settings = {"colormap": "jet", "vmin": -90.0, "vmax": -30.0}
    host._active_line_id = LineManager.SURFACE_ID
    return host


def test_save_project_copies_complete_gui_state(tmp_path, monkeypatch):
    raw_path = tmp_path / "source.raw"
    raw_path.write_bytes(b"raw")
    output = tmp_path / "state.ep"
    host = _host()
    host._current_raw_files = [raw_path]
    host.line_manager.set_offset("surface", 7.5)
    host.line_manager.set_line_data("bottom", [20.0, 21.0], kind="manual")
    host.line_manager.add_line("custom", "Custom", reference_id="bottom", offset_m=-1.5)
    host.analysis_region = AnalysisRegion("surface", "bottom")
    host.display_settings = {"colormap": "inferno", "vmin": -82.0, "vmax": -28.0}
    host._real_sed_df = pd.DataFrame(
        {"target_id": [1], "ping_idx": [3], "range_m": [12.5], "ts_db": [-55.5]}
    )
    host._real_sed_grid_df = pd.DataFrame({"interval": [0], "n_targets": [1]})

    monkeypatch.setattr(
        file_handlers.QFileDialog,
        "getSaveFileName",
        lambda *_args, **_kwargs: (str(output), "EP Project (*.ep)"),
    )
    monkeypatch.setattr(file_handlers, "_save_recent", lambda _path: None)

    FileMixin._save_project(host)
    loaded = EpProject.load(output)

    assert loaded.line_manager.get("surface").offset_m == 7.5
    assert loaded.line_manager.get("custom").offset_m == -1.5
    assert loaded.analysis_region == AnalysisRegion("surface", "bottom")
    assert loaded.display_settings == {"colormap": "inferno", "vmin": -82.0, "vmax": -28.0}
    np.testing.assert_allclose(loaded.bottom_line, [20.0, 21.0])
    pd.testing.assert_frame_equal(loaded.sed_df, host._real_sed_df)
    pd.testing.assert_frame_equal(loaded.sed_grid_df, host._real_sed_grid_df)


def test_restore_project_copies_new_state_into_gui():
    project = EpProject()
    project.line_manager.set_offset("surface", 6.5)
    project.line_manager.set_line_data("bottom", [25.0, 26.0], kind="detected")
    project.line_manager.add_line("custom", "Custom", reference_id="bottom", offset_m=-2.0)
    project.analysis_region = AnalysisRegion("surface", "bottom")
    project.display_settings = {"colormap": "gray", "vmin": -75.0, "vmax": -25.0}
    project.surface_depth = 6.5
    project.bottom_line = np.array([25.0, 26.0], dtype=np.float32)
    host = _host()

    FileMixin._restore_project_gui_state(host, project)

    assert host.line_manager is not project.line_manager
    assert host.line_manager.get("custom").offset_m == -2.0
    assert host.analysis_region == AnalysisRegion("surface", "bottom")
    assert host.display_settings == {"colormap": "gray", "vmin": -75.0, "vmax": -25.0}
    assert host._surface_depth_m == 6.5
    np.testing.assert_allclose(host._bottom_line, [25.0, 26.0])
    assert host.echogram.colormap == ("gray", -75.0, -25.0)
    assert [line.id for line in host.echo_toolbar.lines] == ["surface", "bottom", "custom"]


def test_restore_project_results_keeps_sed_targets_separate_from_grid():
    host = _host()
    project = EpProject()
    targets = pd.DataFrame(
        {"target_id": [1], "ping_idx": [3], "range_m": [12.5], "ts_db": [-55.5]}
    )
    grid = pd.DataFrame({"interval": [0], "n_targets": [1]})
    schools = pd.DataFrame({"school_id": [1]})
    integration = pd.DataFrame({"mean_Sv": [-60.0]})
    project.sed_df = targets
    project.sed_grid_df = grid
    project.schools_df = schools
    project.integration_df = integration

    FileMixin._restore_project_results(host, project)

    pd.testing.assert_frame_equal(host._real_sed_df, targets)
    pd.testing.assert_frame_equal(host._real_sed_grid_df, grid)
    assert host.echogram.single_targets is targets
    assert host.stats_dialog.sed_grid is grid
    assert host.stats_dialog.schools is schools
    assert host.stats_dialog.integration is integration


def test_reset_analysis_state_resets_project_gui_state():
    host = _host()
    host.line_manager.set_offset("surface", 8.0)
    host.line_manager.add_line("custom", "Custom", reference_id="surface")
    host.analysis_region = AnalysisRegion("surface", "custom")
    host.display_settings = {"colormap": "gray", "vmin": -70.0, "vmax": -20.0}
    host._active_line_id = "custom"
    host._surface_depth_m = 8.0
    host._current_project_path = Path("old.ep")

    FileMixin._reset_analysis_state(host)

    assert [line.id for line in host.line_manager] == ["zero", "surface"]
    assert host.analysis_region is None
    assert host.display_settings == {"colormap": "jet", "vmin": -90.0, "vmax": -30.0}
    assert host._active_line_id == "surface"
    assert host._surface_depth_m == 2.0
    assert host._current_project_path is None
    assert host.echogram.lines == {}
    assert host.echogram.colormap == ("jet", -90.0, -30.0)


def test_new_project_refuses_switch_while_worker_is_running(monkeypatch):
    host = _host()
    worker = _RunningWorker()
    host._current_worker = worker
    monkeypatch.setattr(
        file_handlers.QFileDialog,
        "getOpenFileNames",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("dialog opened")),
    )

    host._new_project()

    assert host._current_worker is worker
    assert "后台任务" in host.statusbar.message


def test_open_project_refuses_switch_while_worker_is_running(monkeypatch):
    host = _host()
    worker = _RunningWorker()
    host._current_worker = worker
    monkeypatch.setattr(
        file_handlers.QFileDialog,
        "getOpenFileName",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("dialog opened")),
    )

    host._open_project()

    assert host._current_worker is worker
    assert "后台任务" in host.statusbar.message
