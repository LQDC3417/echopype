"""Mixin: 处理流水线：Sv计算、噪声去除、底部检测、鱼群检测、网格分析"""

import logging
from copy import deepcopy

import numpy as np
from src.gui.i18n import T
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QInputDialog, QMessageBox

from src.core.utils import squeeze_sv
from src.gui.workers import (
    ComputeSvWorker,
    BottomDetectionResult,
    DetectSchoolsWorker,
    DetectSeafloorWorker,
    IntegrationWorker,
    NoiseRemovalWorker,
)

logger = logging.getLogger(__name__)


class ProcessingMixin:
    """处理流水线：Sv计算、噪声去除、底部检测、鱼群检测、网格分析"""

    def _compute_sv(self):
        if self._echodata is None or self._config is None:
            return
        self.pipeline_step.emit(T("pipeline_sv"))
        self.statusbar.show_progress(T("msg_computing_sv"))
        worker = ComputeSvWorker(self._echodata, self._config)
        worker.progress.connect(self.statusbar.set_status)
        if not self._start_worker(worker, self._on_sv_computed):
            return

    def _on_sv_computed(self, ds_Sv):
        self._noise_applied = False
        self._ds_Sv = ds_Sv
        self._ds_Sv_analysis = None  # 清除裁剪缓存，等待后续重新裁剪
        self.statusbar.hide_progress()
        self.statusbar.set_status(T("msg_sv_computed"))

        sv = squeeze_sv(ds_Sv["Sv"].values)

        self._apply_sv_to_display(ds_Sv, sv)

        # 链式处理
        if getattr(self, "_run_all_chain", False):
            QTimer.singleShot(200, self._apply_noise_params)

    def _on_noise_params_changed(self, params):
        self._merge_ui_config({"processing": {"noise_removal": params}})
        self._mark_results_stale("noise", "bottom", "schools", "integration", "real_sed")

    def _on_bottom_params_changed(self, params):
        self._merge_ui_config({"processing": {"bottom_detection": params}})
        self._mark_results_stale("schools", "integration", "real_sed")

    def _on_school_params_changed(self, params):
        self._merge_ui_config({"school_detection": params})
        self._mark_results_stale("schools")

    def _on_integration_params_changed(self, params):
        self._merge_ui_config({"integration": params})
        self._mark_results_stale("integration")

    def _on_real_sed_params_changed(self, params):
        self._merge_ui_config({"single_target_real": params})
        self._mark_results_stale("real_sed")

    def _merge_ui_config(self, updates):
        """只更新界面负责的配置字段，保留调查与设备配置。"""
        if self._config is None:
            self._config = {}

        def merge(target, patch):
            for key, value in patch.items():
                if isinstance(value, dict) and isinstance(target.get(key), dict):
                    merge(target[key], value)
                elif isinstance(value, dict):
                    target[key] = deepcopy(value)
                else:
                    target[key] = deepcopy(value)

        merge(self._config, updates)

    def _apply_all_params(self):
        """保存面板配置；分析由用户通过对应按钮明确启动。"""
        self.property_panel.save_settings()
        self._merge_ui_config(self.property_panel.get_all_config())
        self.statusbar.set_status(T("msg_params_applied"))

    def _on_noise_policy_changed(self, check_state):
        """明确保存重算时是否运行自动去噪；部分勾选表示旧项目策略未知。"""
        if int(check_state) == int(Qt.PartiallyChecked):
            self._noise_enabled = None
            return
        enabled = int(check_state) == int(Qt.Checked)
        if self._noise_enabled is enabled:
            return
        self._noise_enabled = enabled
        if enabled:
            self._mark_results_stale("noise", "bottom", "schools", "integration", "real_sed")
        elif self._ds_Sv is not None:
            self._channel_corrected.pop(self._current_channel, None)
            self._activate_channel(self._current_channel, restore_state=False)
            if self._noise_mask_manual is not None:
                self._apply_noise_params(automatic=False)
                return
            self._noise_applied = False
            self.echogram.set_data(squeeze_sv(self._ds_Sv["Sv"].values))
            self._mark_results_stale("noise", "bottom", "schools", "integration", "real_sed")

    def _apply_noise_params(self, automatic=True):
        if self._ds_Sv is None or self._config is None:
            return
        # 从 UI 同步噪声参数到 config
        self._merge_ui_config({"processing": {"noise_removal":
            self.property_panel.processing.get_noise_config()}})
        self.pipeline_step.emit(T("pipeline_noise"))
        self.statusbar.show_progress(T("msg_removing_noise"))
        analysis_ds = self._get_analysis_ds() if self._analysis_region_enabled else None
        worker = NoiseRemovalWorker(
            self._ds_Sv, self._config, self._noise_mask_manual,
            analysis_ds=analysis_ds if automatic else None, automatic=automatic,
        )
        if not self._start_worker(worker, self._on_noise_removed):
            return
        if automatic:
            self._noise_enabled = True
            checkbox = self.property_panel.processing.chk_noise_enabled
            checkbox.blockSignals(True)
            checkbox.setCheckState(Qt.Checked)
            checkbox.blockSignals(False)
        self._mark_results_stale("noise", "bottom", "schools", "integration", "real_sed")

    def _on_noise_removed(self, ds_Sv):
        self._noise_applied = "Sv_corrected" in ds_Sv
        self._stale_results.discard("noise")
        self._mark_results_stale("bottom", "schools", "integration", "real_sed")
        self._ds_Sv = ds_Sv
        if "Sv_corrected" in ds_Sv:
            self._channel_corrected[self._current_channel] = ds_Sv["Sv_corrected"].copy(deep=False)
        self._ds_Sv_analysis = None  # 清除裁剪缓存，等待后续重新裁剪
        self.statusbar.hide_progress()

        # 更新变量列表（保留原始 Sv，新增 Sv_corrected）
        sv_raw = ds_Sv["Sv"].values
        if sv_raw.ndim == 3:
            sv_raw = sv_raw[0]
        self._update_variable_list(ds_Sv, sv_raw)

        # 显示去噪后的数据
        if "Sv_corrected" in ds_Sv:
            sv_display = ds_Sv["Sv_corrected"].values
            if sv_display.ndim == 3:
                sv_display = sv_display[0]
            self.echogram.set_data(sv_display)
            self.statusbar.set_status(T("msg_noise_removed"))
        else:
            self.echogram.set_data(sv_raw)
            self.statusbar.set_status(T("msg_noise_removed"))

        # 恢复手动编辑的底线（set_data 不清除底线，但重新渲染可能需要恢复）
        if hasattr(self, "line_manager"):
            self._sync_lines_to_renderer()
        elif self._bottom_line is not None:
            self.echogram.set_bottom_line(self._bottom_line)

        # 同步更新缓存中当前文件的 ds
        cache = self._file_cache.get("merged")
        if cache is not None:
            cache["ds"] = self._ds_Sv_all

        if getattr(self, "_run_all_chain", False):
            QTimer.singleShot(200, self._detect_bottom)
        elif getattr(self, "_continue_integration_after_noise", False):
            self._continue_integration_after_noise = False
            QTimer.singleShot(0, self._run_integration)

    def _detect_bottom(self):
        if self._ds_Sv is None or self._config is None:
            QMessageBox.warning(self, T("dialog_warning"), T("msg_load_data_first"))
            return
        # 手动编辑过的底线不自动覆盖
        if self._bottom_manually_edited and self._bottom_line is not None:
            self.statusbar.set_status(T("msg_bottom_manually_edited"))
            if getattr(self, "_run_all_chain", False):
                QTimer.singleShot(200, self._detect_schools)
            return
        # 同步 UI 参数到 config
        self._config.setdefault("processing", {})["bottom_detection"] = {
            **self._config.get("processing", {}).get("bottom_detection", {}),
            **self.property_panel.processing.get_bottom_config(),
        }
        self.pipeline_step.emit(T("pipeline_bottom"))
        self.statusbar.show_progress(T("msg_detecting_bottom"))
        worker = DetectSeafloorWorker(self._ds_Sv, self._config)
        worker.progress.connect(self.statusbar.set_status)
        if not self._start_worker(worker, self._on_bottom_detected):
            return
        self._mark_results_stale("bottom", "schools", "integration", "real_sed")
    def _on_bottom_detected(self, bottom_result):
        if isinstance(bottom_result, BottomDetectionResult):
            bottom = bottom_result.indices
            valid_count = bottom_result.valid_count
            total_count = bottom_result.total_count
        else:
            # 兼容旧版 worker 返回的 ndarray。
            bottom = bottom_result
            valid_count = int(np.isfinite(bottom).sum())
            total_count = int(np.asarray(bottom).size)

        self._bottom_line = np.asarray(bottom, dtype=np.float32).reshape(-1)
        expected = int(self._ds_Sv.sizes.get("ping_time", 0))
        if expected and len(self._bottom_line) != expected:
            self._on_worker_error(
                f"底线检测结果长度异常：得到 {len(self._bottom_line)} 个点，期望 {expected} 个点"
            )
            return
        self._stale_results.discard("bottom")
        valid_count = int(np.isfinite(bottom).sum())
        if valid_count == 0:
            self._run_all_chain = False
            self._invalidate_analysis_region_cache()
            if hasattr(self, "line_manager"):
                self.line_manager.set_line_data(
                    self.line_manager.BOTTOM_ID,
                    self._bottom_line,
                    np.asarray(self._ds_Sv["ping_time"].values),
                    kind="detected",
                )
            self.echogram.set_bottom_line(self._bottom_line)
            self.statusbar.hide_progress()
            message = f"底线检测完成，但结果全部为空：有效点 0/{total_count}"
            self.statusbar.set_status(message)
            self._append_error_message(message)
            return
        if hasattr(self, "line_manager"):
            from src.core.region import _echo_range_2d, sample_indices_to_depths

            ping_times = np.asarray(self._ds_Sv["ping_time"].values)
            echo_range = _echo_range_2d(self._ds_Sv, len(ping_times))
            bottom_depth_m = sample_indices_to_depths(echo_range, bottom)
            self.line_manager.set_line_data(
                self.line_manager.BOTTOM_ID,
                bottom_depth_m,
                ping_times,
                kind="detected",
            )
            self._sync_lines_to_renderer()
        else:
            self.echogram.set_bottom_line(self._bottom_line)
        self.statusbar.hide_progress()

        self._stale_results.discard("bottom")
        # 缓存底线到当前文件
        self._save_file_state()

        # 自动启用分析区域（表线~底线）
        self._analysis_region_enabled = True
        if hasattr(self, "line_manager") and getattr(self, "analysis_region", None) is None:
            from src.core.region import AnalysisRegion

            self.analysis_region = AnalysisRegion(
                self.line_manager.SURFACE_ID,
                self.line_manager.BOTTOM_ID,
            )
        self.echogram.set_analysis_region_enabled(True)
        self._apply_analysis_region_to_ds()

        self.statusbar.set_status(T("msg_bottom_detected"))

        # 自动切换到绘制底线模式（不阻塞信号，让 mode_changed 正常触发）
        if not getattr(self, "_run_all_chain", False):
            self.echo_toolbar.mode_combo.setCurrentIndex(2)  # DRAW_BOTTOM

        if getattr(self, "_run_all_chain", False):
            QTimer.singleShot(200, self._detect_schools)

    def _on_line_edited(self, line_id: str, sample_values):
        """将 Renderer 的 sample-index 线写回以米为单位的通用线模型。"""
        if self._ds_Sv is None or not hasattr(self, "line_manager"):
            return
        from src.core.region import _echo_range_2d, sample_indices_to_depths

        samples = np.asarray(sample_values, dtype=np.float32).reshape(-1)
        ping_times = np.asarray(self._ds_Sv["ping_time"].values)
        if len(samples) != len(ping_times):
            self._append_error_message(
                f"线段 {line_id} 点数异常：得到 {len(samples)}，预期 {len(ping_times)}"
            )
            return
        echo_range = _echo_range_2d(self._ds_Sv, len(ping_times))
        depths_m = sample_indices_to_depths(echo_range, samples)
        self.line_manager.set_line_data(line_id, depths_m, ping_times, kind="manual")
        if line_id == self.line_manager.BOTTOM_ID:
            self._bottom_line = samples.copy()
            self._bottom_manually_edited = True
        self._invalidate_analysis_region_cache()
        self._sync_lines_to_renderer()
        self._save_file_state()
        self.statusbar.set_status(f"线段已更新: {self.line_manager.get(line_id).name}")

    def _on_bottom_line_edited(self, bottom):
        """兼容旧 Bottom signal；新代码应连接 ``line_edited``。"""
        self._on_line_edited(self.line_manager.BOTTOM_ID, bottom)

    def _invalidate_analysis_region_cache(self) -> None:
        self._ds_Sv_analysis = None
        self._analysis_region_cache_key = None
        if hasattr(self, "_mark_results_stale"):
            self._mark_results_stale("schools", "integration", "real_sed")

    def _sync_lines_to_renderer(self) -> None:
        """解析可见米深线，并转换为 Renderer 使用的 sample index。"""
        if self._ds_Sv is None or not hasattr(self, "line_manager"):
            return
        from src.core.region import _echo_range_2d, depths_to_sample_indices

        ping_times = np.asarray(self._ds_Sv["ping_time"].values)
        echo_range = _echo_range_2d(self._ds_Sv, len(ping_times))
        visible_lines = {}
        visible_colors = {}
        for line in self.line_manager:
            if not line.visible:
                continue
            depths_m = self.line_manager.resolve_for_pings(line.id, ping_times)
            visible_lines[line.id] = depths_to_sample_indices(echo_range, depths_m)
            visible_colors[line.id] = line.color
        try:
            self.echogram.set_lines(visible_lines, colors=visible_colors)
        except TypeError:
            # 兼容旧版 Renderer 以及只接受一个参数的测试替身。
            self.echogram.set_lines(visible_lines)
        active_line_id = getattr(self, "_active_line_id", None)
        if active_line_id and hasattr(self.echogram, "set_active_line"):
            self.echogram.set_active_line(active_line_id)

    def _start_draw_bottom(self):
        """切换到绘制底线模式"""
        self.echo_toolbar.mode_combo.setCurrentIndex(2)  # DRAW_BOTTOM
        # 不阻塞信号，让 mode_changed 正常触发，确保 _on_mode_changed 和 set_mouse_mode 都被调用
        self.statusbar.set_status(T("msg_draw_bottom_mode"))

    def _on_update_bottom(self):
        """右键 → 更新底线：显式保存当前底线状态"""
        bottom = self.echogram.get_bottom_line()
        if bottom is not None:
            self._bottom_line = bottom
            self._save_file_state()
            self._apply_analysis_region_to_ds()
            self.statusbar.set_status(T("msg_bottom_updated"))

    def _on_surface_line_changed(self, depth_m: float):
        """表线深度变更"""
        self._surface_depth_m = depth_m
        if hasattr(self, "line_manager"):
            self.line_manager.set_reference(self.line_manager.SURFACE_ID, self.line_manager.ZERO_ID)
            self.line_manager.set_offset(self.line_manager.SURFACE_ID, depth_m)
            self._invalidate_analysis_region_cache()
        self._update_surface_line_render()
        self._save_file_state()
        self._apply_analysis_region_to_ds()

    def _surface_depth_to_sample(self) -> float | None:
        """将表线深度(m)转为 sample index，用于后端分析区域限定。"""
        if self._ds_Sv is None:
            return None
        from src.core.region import get_surface_sample
        return get_surface_sample(self._ds_Sv, self._surface_depth_m)

    def _apply_analysis_region_to_ds(self):
        """根据分析区域（表线~底线）裁剪 ds_Sv，生成 _ds_Sv_analysis。

        始终执行裁剪（不受 _analysis_region_enabled 开关控制），
        确保所有分析操作一致地只在表线→底线水体区域进行。
        """
        if self._ds_Sv is None:
            self._ds_Sv_analysis = None
            return

        if not self._analysis_region_enabled:
            self._ds_Sv_analysis = self._ds_Sv
            self._analysis_region_cache_key = (id(self._ds_Sv), False)
            return

        line_manager = getattr(self, "line_manager", None)
        region = getattr(self, "analysis_region", None)
        if line_manager is not None and region is not None:
            from src.core.region import crop_sv_by_line_region

            self._ds_Sv_analysis, excluded = crop_sv_by_line_region(
                self._ds_Sv, line_manager, region
            )
            self._analysis_region_cache_key = self._current_analysis_region_cache_key()
            if excluded:
                message = f"分析区域排除 {excluded} 个边界缺失、交叉或越界的 ping"
                if hasattr(self, "_append_error_message"):
                    self._append_error_message(message)
                self.statusbar.set_status(message)
            return

        from src.core.region import crop_sv_by_region
        self._ds_Sv_analysis = crop_sv_by_region(
            self._ds_Sv,
            surface_depth_m=self._surface_depth_m if self._surface_depth_m > 0 else None,
            bottom_sample_indices=self._bottom_line,
        )
        self._analysis_region_cache_key = self._current_analysis_region_cache_key()

    def _current_analysis_region_cache_key(self):
        line_manager = getattr(self, "line_manager", None)
        region = getattr(self, "analysis_region", None)
        region_key = None if region is None else (region.upper_line_id, region.lower_line_id)
        return (
            id(self._ds_Sv),
            bool(self._analysis_region_enabled),
            None if line_manager is None else line_manager.revision,
            region_key,
        )

    def _get_analysis_ds(self):
        """返回裁剪后的 ds_Sv（表线→底线水体区域）。

        所有分析操作统一调用此方法，确保只在水体区域进行。
        当 surface/bottom 均未设置时回退返回完整数据（不裁剪）。
        """
        if self._ds_Sv is None:
            return None
        cache_key = self._current_analysis_region_cache_key()
        if self._ds_Sv_analysis is None or self._analysis_region_cache_key != cache_key:
            self._apply_analysis_region_to_ds()
        return self._ds_Sv_analysis if self._ds_Sv_analysis is not None else self._ds_Sv

    def _update_surface_line_render(self):
        """将表线深度(m)转为 sample index 并传给渲染器"""
        if hasattr(self, "line_manager"):
            self._sync_lines_to_renderer()
            return
        idx = self._surface_depth_to_sample()
        if idx is not None:
            self.echogram.set_surface_line(float(idx))

    def _on_surface_line_dialog(self):
        """右键 → 弹出设置表线深度对话框"""
        val, ok = QInputDialog.getDouble(
            self, T("surface_group"),
            T("surface_depth"),
            self._surface_depth_m, 0, 50, 1
        )
        if ok:
            spin = self.property_panel.processing.spin_surface
            spin.blockSignals(True)
            spin.setValue(val)
            spin.blockSignals(False)
            self._on_surface_line_changed(val)

    def _on_analysis_region_toggle(self, enabled: bool):
        """切换分析区域限定：开启时裁剪 ds_Sv，关闭时恢复完整数据"""
        if self._analysis_region_enabled == bool(enabled):
            return
        self._analysis_region_enabled = enabled
        self.echogram.set_analysis_region_enabled(enabled)
        self._apply_analysis_region_to_ds()
        self._mark_results_stale("noise", "bottom", "schools", "integration", "real_sed")
        if enabled:
            self.statusbar.set_status(T("msg_analysis_region_on"))
        else:
            self.statusbar.set_status(T("msg_analysis_region_off"))

    def _detect_schools(self):
        if self._ds_Sv is None or self._config is None:
            QMessageBox.warning(self, T("dialog_warning"), T("msg_load_data_first"))
            return
        # 同步 UI 参数到 config
        self._config.setdefault("school_detection", {}).update(
            self.property_panel.processing.get_school_config()
        )
        self.pipeline_step.emit(T("pipeline_schools"))
        self.statusbar.show_progress(T("msg_detecting_schools"))
        ds_for_detect = self._get_analysis_ds()
        worker = DetectSchoolsWorker(ds_for_detect, self._config)
        if not self._start_worker(worker, self._on_schools_detected):
            return
        self._mark_results_stale("schools")

    def _on_schools_detected(self, mask):
        # 将 mask 转换为 xr.DataArray
        import xarray as xr

        from src.core.school import schools_to_dataframe
        mask_da = xr.DataArray(mask) if not isinstance(mask, xr.DataArray) else mask
        self._incomplete_results.discard("schools")
        self._stale_results.discard("schools")
        self._schools_mask = mask_da.values if hasattr(mask_da, "values") else mask_da
        self.echogram.set_school_mask(self._schools_mask)
        n_pixels = int(np.sum(self._schools_mask)) if self._schools_mask.dtype == bool else 0

        # 将 mask 转换为 DataFrame
        schools_df = schools_to_dataframe(mask_da, self._ds_Sv)
        self._schools_df = schools_df
        self._stale_results.discard("schools")
        self.stats_dialog.update_schools(schools_df)
        self.property_panel.stats.update_schools(schools_df)
        self.statusbar.hide_progress()
        self.statusbar.set_status(T("msg_schools_detected", n=n_pixels))

        # 缓存鱼群状态
        self._save_file_state()

        for _, row in schools_df.iterrows():
            self.region_table.add_region(
                name=f"{T('region_school')} {int(row.get('school_id', 0))}",
                region_type=T("region_school"),
                ping_range=f"{row.get('ping_start', 0)}-{row.get('ping_end', 0)}",
                depth_range=f"{row.get('depth_start', 0):.1f}-{row.get('depth_end', 0):.1f} m",
                area=row.get("area", 0),
                mean_sv=row.get("mean_sv", 0),
            )

        if getattr(self, "_run_all_chain", False):
            # 链式流程到此结束（密度估算已移除）
            self._run_all_chain = False
            self.pipeline_done.emit()

    def _run_all(self):
        if self._echodata is None or self._run_all_chain:
            QMessageBox.warning(self, T("dialog_warning"), T("msg_import_first"))
            return
        self._run_all_chain = True
        self._compute_sv()

    def _show_stats(self):
        """显示统计对话框"""
        self.stats_dialog.show()
        self.stats_dialog.raise_()
        self.stats_dialog.activateWindow()


    def _run_integration(self):
        """运行回声积分分析"""
        if self._ds_Sv is None or self._config is None:
            QMessageBox.warning(self, T("dialog_warning"), T("msg_load_data_first"))
            return
        active_worker = getattr(self, "_current_worker", None)
        if active_worker is not None and active_worker.isRunning():
            return
        if getattr(self, "_noise_enabled", False) is None:
            QMessageBox.information(
                self, T("dialog_warning"),
                "当前项目的自动去噪策略尚未确认，请先在处理面板明确选择后再重算。",
            )
            return

        # 从 UI 同步积分配置到 config
        integ_cfg = self.property_panel.processing.get_integration_config()
        self._config.setdefault("integration", {}).update(integ_cfg)

        if self._noise_enabled and (
            not self._noise_applied or "noise" in self._stale_results
        ):
            self._continue_integration_after_noise = True
            self._apply_noise_params(automatic=True)
            return

        self._mark_results_stale("integration")

        self.statusbar.show_progress(T("msg_integration_running"))
        worker = IntegrationWorker(
            self._ds_Sv, self._config,
            surface_depth_m=self._surface_depth_m,
            noise_enabled=self._noise_enabled,
            manual_mask=self._noise_mask_manual,
            line_manager=self.line_manager,
            analysis_region=self.analysis_region,
            region_enabled=self._analysis_region_enabled,
            channel_id=self._current_channel,
            raw_paths=getattr(self, "_current_raw_files", ()),
        )
        worker.progress.connect(self.statusbar.set_status)
        self._start_worker(worker, self._on_integration_done)

    def _on_integration_done(self, result):
        """回声积分完成 → 展示结果表格 + echogram 网格叠加"""
        worker = self._current_worker
        if worker is not None and worker.run_metadata is not None:
            state = self._channel_states.setdefault(self._current_channel, {})
            state.setdefault("result_provenance", {})["integration"] = worker.run_metadata
        if worker is not None and worker.analysis_dataset is not None:
            self._ds_for_integration = worker.analysis_dataset
            self._ds_Sv_analysis = worker.analysis_dataset
        if worker is not None and worker.processed_dataset is not None:
            self._ds_Sv = worker.processed_dataset
            self._noise_applied = "Sv_corrected" in self._ds_Sv
            self._channel_corrected.pop(self._current_channel, None)
            if self._noise_applied:
                self._channel_corrected[self._current_channel] = self._ds_Sv["Sv_corrected"].copy(deep=False)
            self._stale_results.discard("noise")
            cache = self._file_cache.get("merged")
            if cache is not None:
                cache["ds"] = self._ds_Sv_all
        self._incomplete_results.discard("integration")
        self._stale_results.discard("integration")
        self._integration_result = result
        self._stale_results.discard("integration")
        self.statusbar.hide_progress()
        df = result.to_dataframe()
        self._integration_df = df
        self.stats_dialog.update_integration(df)
        self.property_panel.update_integration_preview(df)
        self.property_panel.show_task("integration")
        self.statusbar.set_status(T("msg_integration_done", n=len(df)))
        # echogram 网格叠加（按 mean_Sv 着色，列名映射到渲染器期望格式）
        try:
            overlay_df = df.rename(columns={"depth_start": "depth_lo", "depth_end": "depth_hi"})
            self.echogram.set_grid_data(overlay_df, self._ds_for_integration, color_by="mean_Sv")
            summary = self.echogram.grid_summary() if hasattr(self.echogram, "grid_summary") else None
            if summary:
                self.statusbar.set_status(
                    f"{T('msg_integration_done', n=len(df))} · ESU {summary.get('n_cells', 0)} "
                    f"({summary.get('color_by', 'mean_Sv')} "
                    f"{summary.get('vmin', 0):.1f}~{summary.get('vmax', 0):.1f} dB)"
                )
        except Exception:
            logger.exception("积分结果叠加到 echogram 失败")
        # 结果已在右栏 Echo Integration 页预览；仍同步对话框数据源

    # ═══════════════════════════════════════════════════════
    # 质量检查
    # ═══════════════════════════════════════════════════════

