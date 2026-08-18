"""Mixin: 处理流水线：Sv计算、噪声去除、底部检测、鱼群检测、密度估算、网格分析"""

import logging
import traceback

import numpy as np
import pandas as pd
from src.gui.i18n import T
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QInputDialog, QMessageBox

from src.core.utils import squeeze_sv
from src.gui.workers import (
    ComputeSvWorker,
    DetectSchoolsWorker,
    DetectSeafloorWorker,
    ComputeDensityWorker as DensityWorker,
    GridWorker,
    IntegrationWorker,
    NoiseRemovalWorker,
)

logger = logging.getLogger(__name__)


class ProcessingMixin:
    """处理流水线：Sv计算、噪声去除、底部检测、鱼群检测、密度估算、网格分析"""

    def _compute_sv(self):
        if self._echodata is None or self._config is None:
            return
        self.pipeline_step.emit(T("pipeline_sv"))
        self.statusbar.show_progress(T("msg_computing_sv"))
        self._current_worker = ComputeSvWorker(self._echodata, self._config)
        self._current_worker.finished.connect(self._on_sv_computed)
        self._current_worker.error.connect(self._on_worker_error)
        self._current_worker.progress.connect(self.statusbar.set_status)
        self._current_worker.start()

    def _on_sv_computed(self, ds_Sv):
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
        self._noise_timer.start()

    def _apply_all_params(self):
        """应用全部参数：保存配置 → 更新config → 触发处理"""
        if self._ds_Sv is None:
            QMessageBox.warning(self, T("dialog_warning"), T("msg_load_data_first"))
            return

        # 保存配置到QSettings
        self.property_panel.save_settings()

        # 从UI获取所有配置并更新config
        ui_config = self.property_panel.get_all_config()
        self._config = ui_config

        # 更新状态栏
        self.statusbar.set_status(T("msg_params_applied"))

        # 触发噪声去除（第一步）
        self._apply_noise_params()

    def _apply_noise_params(self):
        if self._ds_Sv is None or self._config is None:
            return
        # 从 UI 同步噪声参数到 config
        self._config.setdefault("processing", {})["noise_removal"] = (
            self.property_panel.processing.get_noise_config()
        )
        self.pipeline_step.emit(T("pipeline_noise"))
        self.statusbar.show_progress(T("msg_removing_noise"))
        self._current_worker = NoiseRemovalWorker(
            self._ds_Sv, self._config, self._noise_mask_manual
        )
        self._current_worker.finished.connect(self._on_noise_removed)
        self._current_worker.error.connect(self._on_worker_error)
        self._current_worker.start()

    def _on_noise_removed(self, ds_Sv):
        self._ds_Sv = ds_Sv
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
        if self._bottom_line is not None:
            self.echogram.set_bottom_line(self._bottom_line)

        # 同步更新缓存中当前文件的 ds
        if self._raw_file_queue and self._raw_queue_index < len(self._raw_file_queue):
            key = str(self._raw_file_queue[self._raw_queue_index])
            if key in self._file_cache:
                self._file_cache[key]["ds"] = ds_Sv

        if getattr(self, "_run_all_chain", False):
            QTimer.singleShot(200, self._detect_bottom)

    def _detect_bottom(self):
        if self._ds_Sv is None or self._config is None:
            QMessageBox.warning(self, T("dialog_warning"), T("msg_load_data_first"))
            return
        # 手动编辑过的底线不自动覆盖
        if self._bottom_manually_edited and self._bottom_line is not None:
            self.statusbar.set_status(T("msg_bottom_manually_edited"))
            return
        # 同步 UI 参数到 config
        self._config.setdefault("processing", {})["bottom_detection"] = {
            **self._config.get("processing", {}).get("bottom_detection", {}),
            **self.property_panel.processing.get_bottom_config(),
        }
        self.pipeline_step.emit(T("pipeline_bottom"))
        self.statusbar.show_progress(T("msg_detecting_bottom"))
        self._current_worker = DetectSeafloorWorker(self._ds_Sv, self._config)
        self._current_worker.finished.connect(self._on_bottom_detected)
        self._current_worker.error.connect(self._on_worker_error)
        self._current_worker.progress.connect(self.statusbar.set_status)
        self._current_worker.start()

    def _on_bottom_detected(self, bottom):
        self._bottom_line = np.asarray(bottom, dtype=np.float32)
        self.echogram.set_bottom_line(self._bottom_line)
        self.statusbar.hide_progress()

        # 缓存底线到当前文件
        self._save_file_state()

        # 自动启用分析区域（表线~底线）
        self._analysis_region_enabled = True
        self.echogram.set_analysis_region_enabled(True)
        self._apply_analysis_region_to_ds()

        self.statusbar.set_status(T("msg_bottom_detected"))

        # 自动切换到绘制底线模式（不阻塞信号，让 mode_changed 正常触发）
        if not getattr(self, "_run_all_chain", False):
            self.echo_toolbar.mode_combo.setCurrentIndex(2)  # DRAW_BOTTOM

        if getattr(self, "_run_all_chain", False):
            QTimer.singleShot(200, self._detect_schools)

    def _on_bottom_line_edited(self, bottom):
        self._bottom_line = bottom
        self._bottom_manually_edited = True  # 标记手动编辑
        self.echogram.set_bottom_line(bottom)
        self._save_file_state()
        self._apply_analysis_region_to_ds()
        self.statusbar.set_status(T("msg_bottom_line_updated"))

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

        from src.core.region import crop_sv_by_region
        self._ds_Sv_analysis = crop_sv_by_region(
            self._ds_Sv,
            surface_depth_m=self._surface_depth_m if self._surface_depth_m > 0 else None,
            bottom_sample_indices=self._bottom_line,
        )

    def _get_analysis_ds(self):
        """返回裁剪后的 ds_Sv（表线→底线水体区域）。

        所有分析操作统一调用此方法，确保只在水体区域进行。
        当 surface/bottom 均未设置时回退返回完整数据（不裁剪）。
        """
        if self._ds_Sv is None:
            return None
        if self._ds_Sv_analysis is None:
            self._apply_analysis_region_to_ds()
        return self._ds_Sv_analysis if self._ds_Sv_analysis is not None else self._ds_Sv

    def _update_surface_line_render(self):
        """将表线深度(m)转为 sample index 并传给渲染器"""
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
            self._surface_depth_m = val
            self.property_panel.processing.spin_surface.setValue(val)
            self._update_surface_line_render()
            self._apply_analysis_region_to_ds()
            self.statusbar.set_status(T("msg_surface_depth", val=val))

    def _on_analysis_region_toggle(self, enabled: bool):
        """切换分析区域限定：开启时裁剪 ds_Sv，关闭时恢复完整数据"""
        self._analysis_region_enabled = enabled
        self.echogram.set_analysis_region_enabled(enabled)
        self._apply_analysis_region_to_ds()
        if enabled:
            if self._ds_Sv_analysis is not None:
                n_pings = len(self._ds_Sv_analysis["ping_time"])
                n_samples = len(self._ds_Sv_analysis["range_sample"])
                self.statusbar.set_status(
                    T("msg_analysis_region_on")
                )
            else:
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
        self._current_worker = DetectSchoolsWorker(ds_for_detect, self._config)
        self._current_worker.finished.connect(self._on_schools_detected)
        self._current_worker.error.connect(self._on_worker_error)
        self._current_worker.start()

    def _on_schools_detected(self, mask):
        # 将 mask 转换为 xr.DataArray
        import xarray as xr

        from src.core.school import schools_to_dataframe
        mask_da = xr.DataArray(mask) if not isinstance(mask, xr.DataArray) else mask
        self._schools_mask = mask_da.values if hasattr(mask_da, "values") else mask_da
        self.echogram.set_school_mask(self._schools_mask)
        n_pixels = int(np.sum(self._schools_mask)) if self._schools_mask.dtype == bool else 0
        
        # 将 mask 转换为 DataFrame
        schools_df = schools_to_dataframe(mask_da, self._ds_Sv)
        self._schools_df = schools_df
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
            QTimer.singleShot(200, self._compute_density)
    def _compute_density(self):
        if self._ds_Sv is None or self._config is None:
            QMessageBox.warning(self, T("dialog_warning"), T("msg_load_data_first"))
            return
        # 同步 UI 参数到 config
        density_ui = self.property_panel.processing.get_density_config()
        self._config.setdefault("density", {}).update(density_ui)
        self.pipeline_step.emit(T("pipeline_density"))
        schools_df = self._schools_df if self._schools_df is not None else pd.DataFrame()
        self.statusbar.show_progress(T("msg_computing_density"))
        ds_for_density = self._get_analysis_ds()
        self._current_worker = DensityWorker(schools_df, ds_for_density, self._config)
        self._current_worker.finished.connect(self._on_density_computed)
        self._current_worker.error.connect(self._on_worker_error)
        self._current_worker.start()

    def _on_density_computed(self, df):
        self._density_df = df
        self.stats_dialog.update_density(df)
        self.property_panel.stats.update_density(df)
        self.statusbar.hide_progress()
        self.statusbar.set_status(T("msg_density_computed"))
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

    def _run_grid_analysis(self):
        if self._ds_Sv is None or self._config is None:
            QMessageBox.warning(self, T("dialog_warning"), T("msg_load_data_first"))
            return
        grid_cfg = self.property_panel.processing.get_grid_config()
        density_cfg = self.property_panel.processing.get_density_config()

        # 统一使用 _get_analysis_ds() 获取裁剪后的数据（表线→底线区域）
        ds_for_grid = self._get_analysis_ds()
        if ds_for_grid is None:
            QMessageBox.warning(self, T("dialog_warning"), T("msg_load_data_first"))
            return

        # 计算底线深度（米）：直接从 bottom_depth 变量取最大正值
        bottom_depth_m = None
        if "bottom_depth" in ds_for_grid:
            bd = ds_for_grid["bottom_depth"].values
            if bd.ndim > 1:
                bd = bd.flatten()
            valid_bd = bd[np.isfinite(bd)]
            positive_bd = valid_bd[valid_bd > 0]
            if len(positive_bd) > 0:
                bottom_depth_m = float(np.max(positive_bd))
            elif len(valid_bd) > 0:
                bottom_depth_m = float(np.max(valid_bd))

        self.statusbar.show_progress(T("msg_grid_analysis"))
        self._ds_for_grid = ds_for_grid
        self._current_worker = GridWorker(
            ds_for_grid, self._surface_depth_m, grid_cfg, density_cfg,
            bottom_depth_m=bottom_depth_m
        )
        self._current_worker.finished.connect(self._on_grid_done)
        self._current_worker.error.connect(self._on_worker_error)
        self._current_worker.progress.connect(self.statusbar.set_status)
        self._current_worker.start()

    def _on_grid_done(self, df):
        self._grid_df = df
        self.stats_dialog.update_grid(df)
        self.statusbar.hide_progress()
        self.statusbar.set_status(T("msg_grid_done", n=len(df)))
        # 网格颜色叠加到回波图（使用裁剪后数据，确保坐标一致）
        self.echogram.set_grid_data(df, self._ds_for_grid, color_by="mean_sv")
        # 显示统计对话框
        self._show_stats()

    def _run_integration(self):
        """运行回声积分分析"""
        if self._ds_Sv is None or self._config is None:
            QMessageBox.warning(self, T("dialog_warning"), T("msg_load_data_first"))
            return

        # 从 UI 同步积分配置到 config
        integ_cfg = self.property_panel.processing.get_integration_config()
        self._config.setdefault("integration", {}).update(integ_cfg)

        # 统一使用 _get_analysis_ds() 获取裁剪后的数据（表线→底线区域）
        ds_for_integ = self._get_analysis_ds()
        if ds_for_integ is None:
            QMessageBox.warning(self, T("dialog_warning"), T("msg_load_data_first"))
            return

        # 计算底线最大深度（米），用于限制积分层范围（与网格分析一致）
        max_depth_m = None
        if "bottom_depth" in ds_for_integ:
            bd = ds_for_integ["bottom_depth"].values
            if bd.ndim > 1:
                bd = bd.flatten()
            valid_bd = bd[np.isfinite(bd)]
            positive_bd = valid_bd[valid_bd > 0]
            if len(positive_bd) > 0:
                max_depth_m = float(np.max(positive_bd))
            elif len(valid_bd) > 0:
                max_depth_m = float(np.max(valid_bd))

        self.statusbar.show_progress(T("msg_integration_running"))
        self._ds_for_integration = ds_for_integ
        self._current_worker = IntegrationWorker(
            ds_for_integ, self._config,
            surface_depth_m=self._surface_depth_m,
            max_depth_m=max_depth_m,
        )
        self._current_worker.finished.connect(self._on_integration_done)
        self._current_worker.error.connect(self._on_worker_error)
        self._current_worker.progress.connect(self.statusbar.set_status)
        self._current_worker.start()

    def _on_integration_done(self, result):
        """回声积分完成 → 展示结果表格"""
        self._integration_result = result
        self.statusbar.hide_progress()
        df = result.to_dataframe()
        self._integration_df = df
        self.stats_dialog.update_integration(df)
        self.statusbar.set_status(T("msg_integration_done", n=len(df)))
        self._show_stats()

    # ═══════════════════════════════════════════════════════
    # 质量检查
    # ═══════════════════════════════════════════════════════

