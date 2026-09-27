"""淡水调查导航的源文件、流程信号及任务状态。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from src.gui.left_panel import LeftPanel


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_survey_navigation_tracks_sources_and_emits_actions(qapp):
    panel = LeftPanel()
    actions = []
    panel.workflow_requested.connect(actions.append)
    try:
        panel.workflow_buttons["import"].click()
        panel.workflow_buttons["integration"].click()
        assert actions == ["import"]
        panel.update_survey(
            ["D:/survey/first.raw", "D:/survey/second.raw"],
            {"reservoir": {"name": "测试水库"}},
            has_data=True,
            project_path="D:/survey/test.ep",
        )
        assert panel.project_summary.text() == "测试水库"
        assert panel.project_summary.toolTip() == "D:/survey/test.ep"
        assert panel.file_list.count() == 2
        assert panel.file_list.item(1).text() == "02  second.raw"
        assert panel.file_list.item(1).data(Qt.ItemDataRole.UserRole) == "D:/survey/second.raw"
        assert "待检查质量与分析区域" in panel.survey_status.text()
        for key in ("quality", "region", "integration", "save", "survey"):
            panel.workflow_buttons[key].click()
        assert actions == ["import", "quality", "region", "integration", "save", "survey"]

        panel.update_survey(has_data=True, busy=True)
        assert all(not button.isEnabled() for button in panel.workflow_buttons.values())
        panel.workflow_buttons["save"].click()
        assert len(actions) == 6
        assert "正在处理" in panel.survey_status.text()

        panel.update_survey(has_data=True, has_results=True)
        assert "已有分析结果" in panel.survey_status.text()
        panel.update_survey(
            has_data=True, has_results=True, stale_results=["回声积分"],
            status_text="底线已修改",
        )
        assert "待重算：回声积分" in panel.survey_status.text()
        assert "底线已修改" in panel.survey_status.text()
        panel.update_survey()
        assert panel.file_list.count() == 0
        assert panel.project_summary.text() == "当前无项目"
        assert not panel.workflow_buttons["save"].isEnabled()
    finally:
        panel.close()


def test_survey_navigation_preserves_variable_api(qapp):
    panel = LeftPanel()
    try:
        data = object()
        panel.add_variable("38 kHz", data)
        assert panel.get_current_data() is data
        panel.update_survey(has_data=True)
        assert panel.get_current_data() is data
        panel.clear_variables()
        assert panel.get_current_data() is None
    finally:
        panel.close()


def test_saved_snapshot_reopens_with_mask_and_unverified_results(qapp, tmp_path):
    import numpy as np
    import pandas as pd
    import xarray as xr
    from src.core.ep_project import EpProject
    from src.gui.main_window import MainWindow

    project = EpProject(config={"reservoir": {"name": "淡水验证"}, "integration": {"esu_size": 25}})
    project.line_manager.set_line_data("bottom", [8., 8.], kind="manual")
    project.noise_mask = np.array([[True, False], [False, False]])
    project.processing_state = {"noise_applied": True}
    project.integration_df = pd.DataFrame({"mean_Sv": [-50.]})
    path = project.save(tmp_path / "survey.ep")
    ds = xr.Dataset({"Sv": (("ping_time", "range_sample"), np.full((2, 2), -50.))},
                    coords={"ping_time": pd.date_range("2026-01-01", periods=2, freq="s"),
                            "range_sample": [0, 1], "echo_range": ("range_sample", [3., 4.])})
    window = MainWindow()
    try:
        window._on_project_loaded(ds, EpProject.load(path), path)
        window._refresh_workbench()
        assert window._bottom_manually_edited
        assert {"integration", "noise"} <= window._stale_results
        assert np.isnan(window._ds_Sv.Sv_corrected.values[0, 0])
        assert np.isfinite(ds.Sv.values).all()
        assert window.left_panel.project_summary.text() == "淡水验证"
        assert "25 pings" in window.left_panel.survey_status.text()
        snapshot = EpProject()
        window._copy_gui_state_to_project(snapshot)
        assert snapshot.processing_state["noise_applied"] is False
    finally:
        window.close()


def test_old_project_mask_on_different_merge_grid_keeps_current_project(qapp):
    import numpy as np
    import xarray as xr
    from src.core.ep_project import EpProject
    from src.gui.main_window import MainWindow

    window = MainWindow()
    before = window._ds_Sv
    project = EpProject()
    project.noise_mask = np.zeros((2, 2), dtype=bool)
    ds = xr.Dataset({"Sv": (("ping_time", "range_sample"), np.zeros((2, 3)))})
    try:
        window._on_project_loaded(ds, project)
        assert window._ds_Sv is before
    finally:
        window.close()
