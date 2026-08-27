"""Mixin: 文件操作：EP 项目新建/打开/保存、配置、变量列表"""

import logging

import numpy as np
from pathlib import Path

from src.gui.i18n import T
from PySide6.QtWidgets import QFileDialog, QMessageBox

from src.core.ep_project import EpProject
from src.core.utils import load_config, squeeze_sv
from src.gui.workers import MergeFilesWorker, MergeResult

logger = logging.getLogger(__name__)

RECENT_FILE = Path.home() / ".echogram" / "recent.json"
MAX_RECENT = 10


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
    def _reset_analysis_state(self):
        """Reset transient analysis results when switching projects."""
        self._noise_mask_manual = None
        self._bottom_line = None
        self._bottom_manually_edited = False
        self._schools_mask = None
        self._schools_df = None
        self._integration_df = None
        self._real_sed_df = None
        self._ds_Sv_analysis = None
        self._analysis_region_enabled = False
        if hasattr(self, "echogram"):
            self.echogram.set_bottom_line(None)
            self.echogram.set_noise_mask(None)
            self.echogram.set_school_mask(None)
        if hasattr(self, "_set_overlay_actions_enabled"):
            self._set_overlay_actions_enabled(False)

    """文件操作：EP 项目新建/打开/保存、配置、变量列表"""

    # ═══════════════════════════════════════════════════════
    # EP 项目：新建
    # ═══════════════════════════════════════════════════════

    def _new_project(self):
        """新建项目：选择多个 .raw 文件 → 合并 → 显示"""
        paths, _ = QFileDialog.getOpenFileNames(
            self, T("new_project"), "",
            "Raw Files (*.raw);;All Files (*)"
        )
        if not paths:
            return

        self._reset_analysis_state()

        # 按文件名排序
        raw_files = sorted([Path(p) for p in paths])

        if self._config is None:
            self._apply_default_config()
        assert self._config is not None

        # 记录原始文件（供 .ep 保存）
        self._current_raw_files = raw_files

        # 启动合并加载（边加载边显示）
        self.statusbar.show_progress(T("msg_loading_files", n=len(raw_files)))
        self._current_worker = MergeFilesWorker(raw_files, self._config)
        self._current_worker.finished.connect(self._on_merge_finished)
        self._current_worker.error.connect(self._on_worker_error)
        self._current_worker.progress.connect(self.statusbar.set_status)
        self._current_worker.progress_num.connect(self.statusbar.set_progress_value)
        self._current_worker.start()

    def _on_file_ready(self, ds_Sv, cur: int, total: int):
        """兼容旧信号：只更新轻量状态，不复制完整 Sv。"""
        n_pings = ds_Sv.sizes.get("ping_time", 0)
        self.statusbar.set_status(T("msg_files_merged", n=n_pings) + f"  [{cur}/{total}]")

    def _on_merge_finished(self, merge_result):
        if self._current_worker is not None:
            self._echodata = getattr(self._current_worker, "echodata", None)
        if isinstance(merge_result, MergeResult):
            ds_Sv = merge_result.dataset
            if merge_result.failed_files:
                details = "\n".join(
                    f"{item.path} [{item.stage}]: {item.error}\n{item.traceback}"
                    for item in merge_result.failed_files
                )
                self._append_error_message(
                    f"部分 raw 文件处理失败，已继续合并成功文件：\n{details}"
                )
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

    # ═══════════════════════════════════════════════════════
    # EP 项目：保存
    # ═══════════════════════════════════════════════════════

    def _save_project(self):
        """保存当前项目为 .ep 文件"""
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
            proj.surface_depth = self._surface_depth_m
            if self._bottom_line is not None:
                proj.bottom_line = self._bottom_line
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

            saved = proj.save(Path(path))
            _save_recent(str(saved))
            self._current_project_path = saved
            self.statusbar.set_status(T("msg_project_saved", path=str(saved)))
        except Exception as e:
            QMessageBox.critical(self, T("dialog_error"), f"{e}")

    # ═══════════════════════════════════════════════════════
    # EP 项目：打开
    # ═══════════════════════════════════════════════════════

    def _open_project(self):
        """打开 .ep 项目文件"""
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

            # 记录项目信息
            self._reset_analysis_state()
            self._current_raw_files = proj.raw_files
            self._current_project_path = Path(path)
            self._config = proj.config

            # 从 .raw 重新计算 Sv
            self.statusbar.show_progress(T("msg_loading_files", n=len(proj.raw_files)))
            self._current_worker = MergeFilesWorker(proj.raw_files, proj.config)
            self._current_worker.finished.connect(
                lambda ds: self._on_project_loaded(ds, proj)
            )
            self._current_worker.error.connect(self._on_worker_error)
            self._current_worker.progress.connect(self.statusbar.set_status)
            self._current_worker.progress_num.connect(self.statusbar.set_progress_value)
            self._current_worker.start()

            _save_recent(str(path))
        except Exception as e:
            QMessageBox.critical(self, T("dialog_error"), f"{e}")

    def _on_project_loaded(self, ds_Sv, proj: EpProject):
        """项目加载完成 → 显示 + 恢复分析结果"""
        if self._current_worker is not None:
            self._echodata = getattr(self._current_worker, "echodata", None)
        if isinstance(ds_Sv, MergeResult):
            if ds_Sv.failed_files:
                details = "\n".join(
                    f"{item.path} [{item.stage}]: {item.error}\n{item.traceback}"
                    for item in ds_Sv.failed_files
                )
                self._append_error_message(
                    f"部分 raw 文件处理失败，已继续合并成功文件：\n{details}"
                )
            ds_Sv = ds_Sv.dataset
        self.statusbar.hide_progress()

        # 缓存并显示 Sv
        sv = squeeze_sv(ds_Sv["Sv"].values)
        self._file_cache["merged"] = {
            "sv": sv.astype(np.float32),
            "ds": ds_Sv,
            "bottom": proj.bottom_line,
            "noise_mask": None,
            "school_mask": proj.school_mask,
            "surface_depth_m": proj.surface_depth,
        }
        self._apply_sv_to_display(ds_Sv, sv)

        # 恢复分析结果
        if proj.bottom_line is not None:
            self._bottom_line = proj.bottom_line
            self.echogram.set_bottom_line(proj.bottom_line)
        if proj.school_mask is not None:
            self._schools_mask = proj.school_mask
            self.echogram.set_school_mask(proj.school_mask)
        if proj.noise_mask is not None:
            self._noise_mask_manual = proj.noise_mask
            self.echogram.set_noise_mask(proj.noise_mask)
        if proj.schools_df is not None:
            self._schools_df = proj.schools_df
        if proj.integration_df is not None:
            self._integration_df = proj.integration_df
            self.stats_dialog.update_integration(proj.integration_df)
        if proj.sed_df is not None:
            self._real_sed_df = proj.sed_df
            self.stats_dialog.update_real_sed(proj.sed_df)

        # 恢复表线深度到 UI spin box
        self._surface_depth_m = proj.surface_depth
        spin = self.property_panel.processing.spin_surface
        spin.blockSignals(True)
        spin.setValue(proj.surface_depth)
        spin.blockSignals(False)
        self._apply_analysis_region_to_ds()
        self._update_surface_line_render()

        self.statusbar.set_status(T("msg_project_opened", name=Path(self._current_project_path).name))

    # ═══════════════════════════════════════════════════════
    # 配置
    # ═══════════════════════════════════════════════════════

    def _open_config(self):
        path, _ = QFileDialog.getOpenFileName(
            self, T("open_config"), "", "YAML (*.yaml *.yml);;All (*)"
        )
        if path:
            try:
                self._config = load_config(path)
                from src.core.utils import validate_config
                errors = validate_config(self._config)
                if errors:
                    QMessageBox.warning(self, T("dialog_warning"), "\n".join(errors))
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
        sv = optimize_array_dtype(sv)
        self._ds_Sv = ds_Sv
        self._ds_Sv_analysis = None
        self._set_overlay_actions_enabled(True)
        self._update_variable_list(ds_Sv, sv)
        self.echogram.set_data(sv)
        # 底部导航缩略图
        if hasattr(self, "nav_bar"):
            self.nav_bar.set_thumbnail(sv)
        self._update_file_info(ds_Sv)
        self._update_surface_line_render()
        log_memory_usage("load")

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

    def _save_file_state(self):
        """保存当前文件状态到缓存"""
        cache = self._file_cache.get("merged")
        if cache is None:
            return
        cache["bottom"] = self._bottom_line
        cache["noise_mask"] = self._noise_mask_manual
        cache["school_mask"] = self._schools_mask
        cache["surface_depth_m"] = self._surface_depth_m
