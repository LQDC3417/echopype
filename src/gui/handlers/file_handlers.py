"""Mixin: 文件操作：EP 项目新建/打开/保存、配置、变量列表"""

import logging
from copy import deepcopy

import numpy as np
import pandas as pd
from pathlib import Path

from src.gui.i18n import T
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QMessageBox

from src.core.ep_project import EpProject
from src.core.lines import LineManager
from src.core.region import AnalysisRegion
from src.core.utils import load_config, squeeze_sv
from src.gui.workers import MergeFilesWorker, MergeResult

logger = logging.getLogger(__name__)

RECENT_FILE = Path.home() / ".echogram" / "recent.json"
MAX_RECENT = 10


def _channel_id(value) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


def _load_recent() -> list[str]:
    """读取最近打开的项目列表"""
    import json
    if RECENT_FILE.exists():
        try:
            return json.loads(RECENT_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save_recent(path: str) -> None:
    """保存最近打开的项目列表"""
    import json
    recent = _load_recent()
    if path in recent:
        recent.remove(path)
    recent.insert(0, path)
    RECENT_FILE.parent.mkdir(parents=True, exist_ok=True)
    RECENT_FILE.write_text(json.dumps(recent[:MAX_RECENT], ensure_ascii=False), encoding="utf-8")


class FileMixin:
    _CHANNEL_CONFIG_PATHS = (
        ("processing", "noise_removal"),
        ("processing", "bottom_detection"),
        ("school_detection",),
        ("integration",),
        ("single_target_real",),
        ("surface_line",),
    )

    def _channel_config_snapshot(self):
        config = self._config or {}
        snapshot = {}
        for path in self._CHANNEL_CONFIG_PATHS:
            current = config
            for key in path:
                current = current.get(key, {}) if isinstance(current, dict) else {}
            target = snapshot
            for key in path[:-1]:
                target = target.setdefault(key, {})
            target[path[-1]] = deepcopy(current)
        return snapshot

    def _capture_active_channel_state(self):
        channel = getattr(self, "_current_channel", "")
        if not channel or self._ds_Sv is None:
            return
        previous_state = self._channel_states.get(channel, {})
        self._channel_states[channel] = {
            "config": self._channel_config_snapshot(),
            "lines": self.line_manager.to_records(),
            "surface_depth": float(self._surface_depth_m),
            "bottom_line": None if self._bottom_line is None else np.asarray(self._bottom_line).copy(),
            "bottom_manually_edited": bool(self._bottom_manually_edited),
            "analysis_region": None if self.analysis_region is None else (
                self.analysis_region.upper_line_id, self.analysis_region.lower_line_id
            ),
            "analysis_region_enabled": bool(self._analysis_region_enabled),
            "noise_mask": None if self._noise_mask_manual is None else np.asarray(self._noise_mask_manual).copy(),
            "school_mask": None if self._schools_mask is None else np.asarray(self._schools_mask).copy(),
            "schools_df": None if self._schools_df is None else self._schools_df.copy(deep=True),
            "integration_df": None if self._integration_df is None else self._integration_df.copy(deep=True),
            "sed_df": None if self._real_sed_df is None else self._real_sed_df.copy(deep=True),
            "sed_grid_df": None if self._real_sed_grid_df is None else self._real_sed_grid_df.copy(deep=True),
            "stale_results": sorted(self._stale_results),
            "incomplete_results": sorted(self._incomplete_results),
            "result_provenance": deepcopy(previous_state.get("result_provenance", {})),
            "noise_enabled": getattr(self, "_noise_enabled", False),
            "noise_applied": bool(getattr(self, "_noise_applied", False)),
            "undo_stack": deepcopy(self._undo_stack),
            "redo_stack": deepcopy(self._redo_stack),
        }

    def _restore_channel_config(self, snapshot):
        if not snapshot:
            snapshot = self._project_channel_config
        if hasattr(self, "_merge_ui_config"):
            self._merge_ui_config(snapshot)
        panel = getattr(self, "property_panel", None)
        if panel is not None and hasattr(panel.processing, "load_from_config"):
            panel.processing.blockSignals(True)
            try:
                panel.processing.load_from_config(self._config or {})
            finally:
                panel.processing.blockSignals(False)
            from PySide6.QtCore import Qt
            checkbox = panel.processing.chk_noise_enabled
            checkbox.blockSignals(True)
            policy = getattr(self, "_noise_enabled", False)
            checkbox.setCheckState(
                Qt.PartiallyChecked if policy is None
                else Qt.Checked if policy else Qt.Unchecked
            )
            checkbox.blockSignals(False)

    def _clear_channel_results(self):
        import pandas as pd

        self._schools_df = None
        self._integration_df = None
        self._real_sed_df = None
        self._real_sed_grid_df = None
        self.stats_dialog.update_schools(pd.DataFrame())
        self.stats_dialog.update_integration(None)
        self.stats_dialog.update_real_sed(None)
        self.property_panel.update_integration_preview(None)

    def _activate_channel(self, channel_id, restore_state=True, force_restore=False):
        """切换到指定通道视图；活动 Dataset 与全通道原始数据共享原始数组。"""
        source = getattr(self, "_ds_Sv_all", None)
        if source is None:
            return
        old_channel = getattr(self, "_current_channel", "")
        channel_id = str(channel_id)
        if restore_state and old_channel and old_channel != channel_id:
            self._capture_active_channel_state()
        if "channel" in source["Sv"].dims:
            channel_values = list(source["channel"].values)
            available = {_channel_id(value): value for value in channel_values}
            if channel_id not in available:
                raise ValueError(f"数据中不存在声学通道：{channel_id}")
            active = source.sel(channel=[available[channel_id]])
        else:
            active = source
            channel_id = _channel_id(np.asarray(source["channel"].values).reshape(-1)[0]) if "channel" in source.coords else "single"
        corrected = self._channel_corrected.get(channel_id)
        if corrected is not None:
            active = active.assign(Sv_corrected=corrected)
        self._current_channel = channel_id
        self._ds_Sv = active
        self._ds_Sv_analysis = None

        if restore_state and (old_channel != channel_id or force_restore):
            state = self._channel_states.get(channel_id)
            if state is None:
                self.line_manager = LineManager()
                self._surface_depth_m = float(
                    (self._config or {}).get("surface_line", {}).get("depth_m", 2.0)
                )
                self._bottom_line = None
                self._bottom_manually_edited = False
                self.analysis_region = None
                self._analysis_region_enabled = False
                self._noise_mask_manual = None
                self._schools_mask = None
                self._stale_results = set()
                self._incomplete_results = set()
                self._noise_enabled = False
                self._noise_applied = corrected is not None
                self._undo_stack = []
                self._redo_stack = []
                self._clear_channel_results()
                self._restore_channel_config(self._project_channel_config)
            else:
                self._noise_enabled = state.get(
                    "noise_enabled", getattr(self, "_noise_enabled", False)
                )
                self._restore_channel_config(state.get("config"))
                self.line_manager = LineManager.from_records(state.get("lines", ()))
                self._surface_depth_m = float(state.get("surface_depth", 2.0))
                self._bottom_line = state.get("bottom_line")
                self._bottom_manually_edited = bool(state.get("bottom_manually_edited", False))
                bounds = state.get("analysis_region")
                self.analysis_region = AnalysisRegion(*bounds) if bounds else None
                self._analysis_region_enabled = bool(state.get("analysis_region_enabled", False))
                self._noise_mask_manual = state.get("noise_mask")
                self._schools_mask = state.get("school_mask")
                self._schools_df = state.get("schools_df")
                self._integration_df = state.get("integration_df")
                self._real_sed_df = state.get("sed_df")
                self._real_sed_grid_df = state.get("sed_grid_df")
                self._stale_results = set(state.get("stale_results", ()))
                self._incomplete_results = set(state.get("incomplete_results", ()))
                self._noise_applied = corrected is not None
                self._undo_stack = deepcopy(state.get("undo_stack", []))
                self._redo_stack = deepcopy(state.get("redo_stack", []))
                self.stats_dialog.update_schools(self._schools_df if self._schools_df is not None else pd.DataFrame())
                self.stats_dialog.update_integration(self._integration_df)
                self.stats_dialog.update_real_sed(self._real_sed_grid_df)
                self.property_panel.update_integration_preview(self._integration_df)

            if self._noise_mask_manual is not None and corrected is None:
                from src.core.processing import apply_manual_mask
                self._ds_Sv = apply_manual_mask(self._ds_Sv, self._noise_mask_manual)
                self._channel_corrected[channel_id] = self._ds_Sv["Sv_corrected"].copy(deep=False)

        variable = "Sv_corrected" if "Sv_corrected" in self._ds_Sv else "Sv"
        sv = squeeze_sv(self._ds_Sv[variable].values)
        self._update_variable_list(self._ds_Sv, squeeze_sv(self._ds_Sv["Sv"].values))
        if old_channel != channel_id:
            self.echogram.clear_grid_overlay()
            self.echogram.clear_single_targets()
        self.echogram.set_data(sv)
        self.nav_bar.set_thumbnail(sv)
        self.echogram.set_bottom_line(self._bottom_line)
        self.echogram.set_noise_mask(self._noise_mask_manual)
        self.echogram.set_school_mask(self._schools_mask)
        self.echogram.set_analysis_region_enabled(self._analysis_region_enabled)
        self._apply_analysis_region_to_ds()
        self._sync_lines_to_renderer()
        self.echo_toolbar.set_editable_lines(self.line_manager.editable_lines())
        self._refresh_workbench()

    def _on_channel_selected(self, index):
        channel_id = self.property_panel.processing.combo_channel.itemData(index)
        if channel_id is not None and str(channel_id) != self._current_channel:
            self._activate_channel(channel_id)

    def _reset_analysis_state(self):
        """Reset transient analysis results when switching projects."""
        self._noise_mask_manual = None
        self._noise_applied = False
        self._stale_results = set()
        self._channel_states = {}
        self._channel_corrected = {}
        self._ds_Sv_all = None
        self._current_channel = ""
        self._noise_enabled = False
        self._continue_integration_after_noise = False
        self._input_incomplete = False
        self._incomplete_results = set()
        self._bottom_line = None
        self._bottom_manually_edited = False
        self._schools_mask = None
        self._schools_df = None
        self._integration_df = None
        self._real_sed_df = None
        self._real_sed_grid_df = None
        self._ds_Sv_analysis = None
        self._analysis_region_enabled = False
        self.line_manager = LineManager()
        self.analysis_region = None
        self.display_settings = {"colormap": "jet", "vmin": -90.0, "vmax": -30.0}
        self._active_line_id = LineManager.SURFACE_ID
        self._surface_depth_m = 2.0
        self._current_project_path = None
        self._project_channel_config = self._channel_config_snapshot()
        if hasattr(self, "echogram"):
            self.echogram.set_bottom_line(None)
            self.echogram.set_noise_mask(None)
            self.echogram.set_school_mask(None)
            if hasattr(self.echogram, "set_analysis_region_enabled"):
                self.echogram.set_analysis_region_enabled(False)
            if hasattr(self.echogram, "clear_grid_overlay"):
                self.echogram.clear_grid_overlay()
            if hasattr(self.echogram, "clear_single_targets"):
                self.echogram.clear_single_targets()
        if hasattr(self, "_set_overlay_actions_enabled"):
            self._set_overlay_actions_enabled(False)
        if hasattr(self, "echogram") and hasattr(self.echogram, "set_lines"):
            self.echogram.set_lines({})
        if hasattr(self, "echogram") and hasattr(self.echogram, "set_colormap"):
            self.echogram.set_colormap("jet", -90.0, -30.0)
        if hasattr(self, "_apply_display_settings"):
            self._apply_display_settings("jet", -90.0, -30.0)
        if hasattr(self, "echo_toolbar"):
            self.echo_toolbar.set_editable_lines(self.line_manager.editable_lines())

    def _restore_project_results(self, proj: EpProject) -> None:
        """恢复独立保存的分析结果及其对应视图。"""
        if proj.school_mask is not None:
            self._schools_mask = proj.school_mask
            self.echogram.set_school_mask(proj.school_mask)
        if proj.noise_mask is not None:
            self._noise_mask_manual = proj.noise_mask
            self.echogram.set_noise_mask(proj.noise_mask)
        if proj.schools_df is not None:
            self._schools_df = proj.schools_df
            self.stats_dialog.update_schools(proj.schools_df)
            if hasattr(self, "property_panel"):
                self.property_panel.stats.update_schools(proj.schools_df)
        if proj.integration_df is not None:
            self._integration_df = proj.integration_df
            self.stats_dialog.update_integration(proj.integration_df)
        if proj.sed_df is not None:
            self._real_sed_df = proj.sed_df
            self.echogram.set_single_targets(proj.sed_df)
        sed_grid_df = getattr(proj, "sed_grid_df", None)
        if sed_grid_df is not None:
            self._real_sed_grid_df = sed_grid_df
            self.stats_dialog.update_real_sed(sed_grid_df)

    def _copy_gui_state_to_project(self, proj: EpProject) -> None:
        """将当前 GUI 的项目级状态复制到持久化模型。"""
        self._capture_active_channel_state()
        proj.selected_channel_id = str(getattr(self, "_current_channel", ""))
        proj.channel_states = deepcopy(getattr(self, "_channel_states", {}))
        proj.line_manager = LineManager.from_records(self.line_manager.to_records())
        if self.analysis_region is None:
            proj.analysis_region = None
        else:
            proj.analysis_region = AnalysisRegion(
                self.analysis_region.upper_line_id,
                self.analysis_region.lower_line_id,
            )
        proj.analysis_region_enabled = bool(self._analysis_region_enabled)
        proj.display_settings = dict(self.display_settings)
        proj.processing_state = {
            "noise_applied": bool(getattr(self, "_noise_applied", False)),
            "noise_enabled": getattr(self, "_noise_enabled", False),
            "stale_results": sorted(getattr(self, "_stale_results", ())),
            "input_incomplete": bool(getattr(self, "_input_incomplete", False)),
            "incomplete_results": sorted(getattr(self, "_incomplete_results", ())),
            "reference_results_status": "unverified",
            "replay_policy": "current_snapshot_region_not_historical_operation_order",
        }

        surface = proj.line_manager.get(LineManager.SURFACE_ID)
        proj.surface_depth = float(surface.offset_m)
        bottom = proj.line_manager._lines.get(LineManager.BOTTOM_ID)
        if bottom is not None and bottom.values is not None:
            proj.bottom_line = bottom.values.copy()
        elif self._bottom_line is not None:
            proj.bottom_line = np.asarray(self._bottom_line, dtype=np.float32).copy()

    def _restore_project_gui_state(self, proj: EpProject) -> None:
        """从持久化模型恢复 GUI 的项目级状态，避免跨项目残留。"""
        self.line_manager = LineManager.from_records(proj.line_manager.to_records())
        if proj.analysis_region is None:
            self.analysis_region = None
        else:
            self.analysis_region = AnalysisRegion(
                proj.analysis_region.upper_line_id,
                proj.analysis_region.lower_line_id,
            )
        self.display_settings = dict(proj.display_settings)

        surface = self.line_manager.get(LineManager.SURFACE_ID)
        self._surface_depth_m = (
            float(surface.offset_m) if surface.kind == "derived" else float(proj.surface_depth)
        )
        bottom = self.line_manager._lines.get(LineManager.BOTTOM_ID)
        self._bottom_manually_edited = bottom is not None and bottom.kind == "manual"
        if bottom is not None and bottom.values is not None:
            self._bottom_line = bottom.values.copy()
        elif proj.bottom_line is not None:
            self._bottom_line = np.asarray(proj.bottom_line, dtype=np.float32).copy()
        else:
            self._bottom_line = None
        self._ds_Sv_analysis = None
        self._analysis_region_enabled = bool(
            getattr(proj, "analysis_region_enabled", self.analysis_region is not None)
        )

        if hasattr(self, "echogram"):
            self.echogram.set_bottom_line(self._bottom_line)
            if hasattr(self.echogram, "set_analysis_region_enabled"):
                self.echogram.set_analysis_region_enabled(self._analysis_region_enabled)
            if hasattr(self.echogram, "set_colormap"):
                self.echogram.set_colormap(
                    self.display_settings["colormap"],
                    float(self.display_settings["vmin"]),
                    float(self.display_settings["vmax"]),
                )
            if hasattr(self, "_apply_display_settings"):
                self._apply_display_settings(**self.display_settings)
        if hasattr(self, "echo_toolbar"):
            self.echo_toolbar.set_editable_lines(self.line_manager.editable_lines())

    """文件操作：EP 项目新建/打开/保存、配置、变量列表"""

    # ═══════════════════════════════════════════════════════
    # EP 项目：新建
    # ═══════════════════════════════════════════════════════

    def _new_project(self):
        """新建项目：选择多个 .raw 文件 → 合并 → 显示"""
        if self._current_worker is not None and self._current_worker.isRunning():
            self.statusbar.set_status("请等待当前后台任务完成后再切换项目")
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self, T("new_project"), "",
            "Raw Files (*.raw);;All Files (*)"
        )
        if not paths:
            return

        # 按文件名排序
        raw_files = sorted([Path(p) for p in paths])

        if self._config is None:
            self._apply_default_config()
        assert self._config is not None

        # 启动合并加载（边加载边显示）
        self.statusbar.show_progress(T("msg_loading_files", n=len(raw_files)))
        worker = MergeFilesWorker(raw_files, self._config)
        worker.progress.connect(self.statusbar.set_status)
        worker.progress_num.connect(self.statusbar.set_progress_value)
        if not self._start_worker(worker, lambda result: self._on_merge_finished(result, raw_files)):
            return

    def _on_file_ready(self, ds_Sv, cur: int, total: int):
        """兼容旧信号：只更新轻量状态，不复制完整 Sv。"""
        n_pings = ds_Sv.sizes.get("ping_time", 0)
        self.statusbar.set_status(T("msg_files_merged", n=n_pings) + f"  [{cur}/{total}]")

    def _on_merge_finished(self, merge_result, raw_files=None):
        self._reset_analysis_state()
        if raw_files is not None:
            self._current_raw_files = list(raw_files)
        if self._current_worker is not None:
            self._echodata = getattr(self._current_worker, "echodata", None)
        if isinstance(merge_result, MergeResult):
            if merge_result.loaded_paths:
                self._current_raw_files = list(merge_result.loaded_paths)
            ds_Sv = merge_result.dataset
            if merge_result.failed_files:
                self._input_incomplete = True
                details = "\n".join(
                    f"{item.path} [{item.stage}]: {item.error}\n{item.traceback}"
                    for item in merge_result.failed_files
                )
                self._append_error_message(
                    f"部分 raw 文件处理失败，已继续合并成功文件：\n{details}"
                )
                choice = QMessageBox.question(
                    self, T("dialog_warning"),
                    "部分 RAW 文件处理失败。是否明确接受成功文件作为本次调查的完整输入范围？",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
                )
                if choice == QMessageBox.Yes:
                    self._input_incomplete = False
                    self.statusbar.set_status("已确认以成功加载的 RAW 子集作为本次完整分析范围")
        else:
            ds_Sv = merge_result
        """合并加载完成 → 缓存 + 显示"""
        self.statusbar.hide_progress()

        # 缓存
        sv = squeeze_sv(ds_Sv["Sv"].values)
        self._file_cache["merged"] = {
            "sv": sv.astype(np.float32),
            "ds": ds_Sv,
            "bottom": None,
            "noise_mask": None,
            "school_mask": None,
            "surface_depth_m": self._surface_depth_m,
        }

        # 显示
        self._apply_sv_to_display(ds_Sv, sv)
        n_pings = ds_Sv.sizes["ping_time"]
        self.statusbar.set_status(T("msg_files_merged", n=n_pings))
        duplicate_count = ds_Sv.attrs.get("merge_duplicate_count", 0)
        gap_indices = ds_Sv.attrs.get("merge_gap_ping_indices", "[]")
        if duplicate_count or gap_indices != "[]":
            self.statusbar.set_status(f"文件合并完成：{n_pings} pings；重复 ping 去重 {duplicate_count} 个；时间断档后 ping：{gap_indices}")

    # ═══════════════════════════════════════════════════════
    # EP 项目：保存
    # ═══════════════════════════════════════════════════════

    def _save_project(self):
        """保存当前项目为 .ep 文件"""
        worker = getattr(self, "_current_worker", None)
        if worker is not None and worker.isRunning():
            self.statusbar.set_status("请等待当前处理完成后保存快照")
            return
        if not hasattr(self, "_current_raw_files") or not self._current_raw_files:
            QMessageBox.warning(self, T("dialog_warning"), T("msg_no_project"))
            return

        # 默认保存到第一个 .raw 同目录
        default_path = self._current_raw_files[0].with_suffix(".ep")
        path, _ = QFileDialog.getSaveFileName(
            self, T("save_project"), str(default_path), "EP Project (*.ep)"
        )
        if not path:
            return

        try:
            proj = EpProject(self._current_raw_files, self._config)
            proj.compute_checksums()

            # 保存分析结果
            self._copy_gui_state_to_project(proj)
            if self._schools_mask is not None:
                proj.school_mask = self._schools_mask
            if self._noise_mask_manual is not None:
                proj.noise_mask = self._noise_mask_manual
            if hasattr(self, "_schools_df") and self._schools_df is not None:
                proj.schools_df = self._schools_df
            if hasattr(self, "_integration_df") and self._integration_df is not None:
                proj.integration_df = self._integration_df
            if hasattr(self, "_real_sed_df") and self._real_sed_df is not None:
                proj.sed_df = self._real_sed_df
            if hasattr(self, "_real_sed_grid_df") and self._real_sed_grid_df is not None:
                proj.sed_grid_df = self._real_sed_grid_df

            saved = proj.save(Path(path))
            _save_recent(str(saved))
            self._current_project_path = saved
            self.statusbar.set_status(T("msg_project_saved", path=str(saved)))
            if hasattr(self, "_refresh_workbench"):
                self._refresh_workbench()
        except Exception as e:
            QMessageBox.critical(self, T("dialog_error"), f"{e}")

    # ═══════════════════════════════════════════════════════
    # EP 项目：打开
    # ═══════════════════════════════════════════════════════

    def _open_project(self):
        """打开 .ep 项目文件"""
        if self._current_worker is not None and self._current_worker.isRunning():
            self.statusbar.set_status("请等待当前后台任务完成后再切换项目")
            return
        path, _ = QFileDialog.getOpenFileName(
            self, T("open_project"), "", "EP Project (*.ep);;All Files (*)"
        )
        if not path:
            return

        try:
            proj = EpProject.load(Path(path))

            # 完整性检查：所有 .raw 文件必须存在
            all_ok, missing = proj.verify_raw_files()
            if not all_ok:
                missing_list = "\n".join(str(p) for p in missing[:20])
                QMessageBox.critical(
                    self, T("dialog_error"),
                    T("msg_project_raw_missing", files=missing_list)
                )
                return

            # 从 .raw 重新计算 Sv
            self.statusbar.show_progress(T("msg_loading_files", n=len(proj.raw_files)))
            worker = MergeFilesWorker(proj.raw_files, proj.config)
            worker.progress.connect(self.statusbar.set_status)
            worker.progress_num.connect(self.statusbar.set_progress_value)
            if not self._start_worker(worker, lambda ds: self._on_project_loaded(ds, proj, Path(path))):
                return

            _save_recent(str(path))
        except Exception as e:
            QMessageBox.critical(self, T("dialog_error"), f"{e}")

    def _on_project_loaded(self, ds_Sv, proj: EpProject, project_path=None):
        """项目加载完成 → 显示 + 恢复分析结果"""
        if isinstance(ds_Sv, MergeResult):
            if ds_Sv.failed_files:
                self.statusbar.hide_progress()
                self._append_error_message("项目加载失败：部分 raw 无法处理，保留当前项目，避免分析线和 mask 错位。")
                return
            ds_Sv = ds_Sv.dataset
        selected_channel = _channel_id(getattr(proj, "selected_channel_id", "") or "")
        if selected_channel and "channel" in ds_Sv["Sv"].dims:
            available = [_channel_id(value) for value in ds_Sv["channel"].values]
            if selected_channel not in available:
                self.statusbar.hide_progress()
                self._append_error_message(
                    f"项目记录的通道 {selected_channel} 不存在于重新校准数据中；未切换到其他通道。"
                )
                return
        expected_shape = (ds_Sv.sizes["ping_time"], ds_Sv.sizes["range_sample"])
        if any(mask is not None and mask.shape != expected_shape for mask in (proj.noise_mask, proj.school_mask)):
            self.statusbar.hide_progress()
            self._append_error_message("项目掩膜与当前拼接网格不一致，已保留当前项目。请重新导入 RAW 并检查分析区域，原项目文件未修改。")
            return
        self._reset_analysis_state()
        self._current_raw_files = proj.raw_files
        self._current_project_path = project_path
        self._config = proj.config
        self._noise_enabled = proj.processing_state.get("noise_enabled")
        self._project_channel_config = self._channel_config_snapshot()
        processing = self.property_panel.processing
        processing.blockSignals(True)
        try:
            processing.load_from_config(self._config)
        finally:
            processing.blockSignals(False)
        self._channel_states = deepcopy(getattr(proj, "channel_states", {}))
        self._current_channel = getattr(proj, "selected_channel_id", "") or ""
        self._input_incomplete = bool(proj.processing_state.get("input_incomplete", False))
        self._incomplete_results = set(proj.processing_state.get("incomplete_results", ()))
        if self._current_worker is not None:
            self._echodata = getattr(self._current_worker, "echodata", None)
        self.statusbar.hide_progress()

        self._restore_project_gui_state(proj)

        # 缓存并显示 Sv
        sv = squeeze_sv(ds_Sv["Sv"].values)
        self._file_cache["merged"] = {
            "sv": sv.astype(np.float32),
            "ds": ds_Sv,
            "bottom": self._bottom_line,
            "noise_mask": None,
            "school_mask": proj.school_mask,
            "surface_depth_m": self._surface_depth_m,
        }
        self._apply_sv_to_display(ds_Sv, sv)

        self._restore_project_results(proj)
        if self._channel_states:
            self._activate_channel(self._current_channel, force_restore=True)
        elif "channel" in ds_Sv["Sv"].dims:
            # 旧项目只有一份全局状态；仅绑定到实际首通道并标为历史待核验。
            self._capture_active_channel_state()
        # 重开仅重新校准，旧结果是历史快照，不能冒充当前计算结果。
        if proj.noise_mask is not None:
            from src.core.processing import apply_manual_mask
            self._ds_Sv = apply_manual_mask(self._ds_Sv, proj.noise_mask)
            self._channel_corrected[self._current_channel] = self._ds_Sv["Sv_corrected"].copy(deep=False)
            self._file_cache["merged"]["ds"] = self._ds_Sv_all
            self._update_variable_list(self._ds_Sv)
            corrected_sv = squeeze_sv(self._ds_Sv["Sv_corrected"].values)
            self.echogram.set_data(corrected_sv)
            self.nav_bar.set_thumbnail(corrected_sv)
        self._stale_results.update(proj.processing_state.get("stale_results", ()))
        for name, value in (("schools", proj.schools_df), ("integration", proj.integration_df), ("real_sed", proj.sed_df)):
            if value is not None:
                self._stale_results.add(name)
        if proj.processing_state.get("noise_applied"):
            self._stale_results.add("noise")

        # 恢复表线深度到 UI spin box
        spin = self.property_panel.processing.spin_surface
        spin.blockSignals(True)
        spin.setValue(self._surface_depth_m)
        spin.blockSignals(False)
        self._apply_analysis_region_to_ds()
        self._update_surface_line_render()

        self.statusbar.set_status(T("msg_project_opened", name=Path(self._current_project_path).name if self._current_project_path else ""))
        if self._noise_enabled is None:
            self.property_panel.processing.chk_noise_enabled.setCheckState(Qt.PartiallyChecked)
            self.statusbar.set_status("旧项目未区分去噪策略与内存处理状态，请在重算去噪设置中明确选择后再运行快照重算")
        if self._stale_results:
            self.statusbar.set_status("项目已打开：历史结果待核验，当前为重新校准数据；可按已保存快照独立重算积分")

    # ═══════════════════════════════════════════════════════
    # 配置
    # ═══════════════════════════════════════════════════════

    def _open_config(self):
        path, _ = QFileDialog.getOpenFileName(
            self, T("open_config"), "", "YAML (*.yaml *.yml);;All (*)"
        )
        if path:
            try:
                config = load_config(path)
                from src.core.utils import validate_config
                errors = validate_config(config)
                if errors:
                    QMessageBox.warning(self, T("dialog_warning"), "\n".join(errors))
                    return
                self._config = config
                self.statusbar.set_status(T("msg_config_loaded", path=path))
                self.property_panel.processing.load_from_config(self._config)
            except Exception as e:
                QMessageBox.critical(self, T("dialog_error"), f"{e}")

    def _save_config(self):
        if self._config is None:
            QMessageBox.warning(self, T("dialog_warning"), T("msg_no_config"))
            return
        path, _ = QFileDialog.getSaveFileName(self, T("save_config"), "", "YAML (*.yaml)")
        if path:
            import yaml
            with open(path, "w", encoding="utf-8") as f:
                yaml.dump(self._config, f, allow_unicode=True, default_flow_style=False)
            self.statusbar.set_status(T("msg_config_saved", path=path))

    def _apply_sv_to_display(self, ds_Sv, sv):
        """将 Sv 数据应用到显示：优化内存 + 更新渲染器"""
        from src.core.utils import log_memory_usage, optimize_array_dtype
        self._ds_Sv_all = ds_Sv
        channel_ids = [_channel_id(value) for value in ds_Sv["channel"].values] if "channel" in ds_Sv.dims else []
        if channel_ids:
            if self._current_channel not in channel_ids:
                self._current_channel = channel_ids[0]
            items = []
            for channel_id in channel_ids:
                label = channel_id
                if "frequency_nominal" in ds_Sv:
                    frequency = ds_Sv["frequency_nominal"]
                    if "channel" in frequency.dims:
                        frequency = frequency.sel(channel=channel_id)
                    values = np.asarray(frequency.values).reshape(-1)
                    if values.size and np.isfinite(values[0]):
                        label = f"{float(values[0]) / 1000:g} kHz · {channel_id}"
                items.append((label, channel_id))
            self.property_panel.set_channels(items)
            combo = self.property_panel.processing.combo_channel
            combo.blockSignals(True)
            combo.setCurrentIndex(combo.findData(self._current_channel))
            combo.blockSignals(False)
        self._activate_channel(self._current_channel or "single", restore_state=False)
        self._ds_Sv_analysis = None
        self._set_overlay_actions_enabled(True)
        display_var = "Sv_corrected" if "Sv_corrected" in self._ds_Sv else "Sv"
        self.echogram.set_data(optimize_array_dtype(squeeze_sv(self._ds_Sv[display_var].values)))
        if hasattr(self.echogram, "set_file_sources"):
            sources = ds_Sv.source_file.values if "source_file" in ds_Sv else None
            self.echogram.set_file_sources(sources, ds_Sv.ping_time.values)
        # 底部导航缩略图
        if hasattr(self, "nav_bar"):
            self.nav_bar.set_thumbnail(squeeze_sv(self._ds_Sv[display_var].values))
        self._update_file_info(ds_Sv)
        self._update_surface_line_render()
        log_memory_usage("load")
        if hasattr(self, "_refresh_workbench"):
            self._refresh_workbench()

    # ═══════════════════════════════════════════════════════
    # 变量列表管理
    # ═══════════════════════════════════════════════════════

    def _update_variable_list(self, ds_Sv, sv_raw=None):
        """更新变量列表和缓存映射"""
        self.variable_list.clear_variables()
        self._variable_cache.clear()
        self._display_to_key.clear()

        # 原始 Sv
        if sv_raw is None:
            sv_raw = ds_Sv["Sv"].values
            if sv_raw.ndim == 3:
                sv_raw = sv_raw[0]
        self._variable_cache["Sv"] = sv_raw
        self._display_to_key[T("display_sv_raw")] = "Sv"
        self.variable_list.add_variable("Sv", sv_raw, T("display_sv_raw"))

        # 去噪后 Sv_corrected
        if "Sv_corrected" in ds_Sv:
            sv_c = ds_Sv["Sv_corrected"].values
            if sv_c.ndim == 3:
                sv_c = sv_c[0]
            self._variable_cache["Sv_corrected"] = sv_c
            self._display_to_key[T("display_sv_corrected")] = "Sv_corrected"
            self.variable_list.add_variable("Sv_corrected", sv_c, T("display_sv_corrected"))

        # 通道列表始终从全通道数据读取，显示标签保留原始 channel ID。
        source = getattr(self, "_ds_Sv_all", None)
        if source is None:
            source = ds_Sv
        channels = []
        try:
            if "channel" in source["Sv"].dims:
                for channel in source["channel"].values:
                    channel_id = _channel_id(channel)
                    label = channel_id
                    if "frequency_nominal" in source:
                        frequency = source["frequency_nominal"]
                        if "channel" in frequency.dims:
                            frequency = frequency.sel(channel=channel)
                        values = np.asarray(frequency.values).reshape(-1)
                        if values.size and np.isfinite(values[0]):
                            label = f"{float(values[0]) / 1000:g} kHz · {channel_id}"
                    channels.append((label, channel_id))
        except Exception:
            logger.exception("读取声学通道列表失败")
        if channels:
            self.property_panel.set_channels(channels)

    def _save_file_state(self):
        """保存当前文件状态到缓存"""
        cache = self._file_cache.get("merged")
        if cache is None:
            return
        cache["bottom"] = self._bottom_line
        cache["noise_mask"] = self._noise_mask_manual
        cache["school_mask"] = self._schools_mask
        cache["surface_depth_m"] = self._surface_depth_m
