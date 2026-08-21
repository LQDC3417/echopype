"""Mixin: 文件操作：导入、配置、变量列表"""

import logging

import numpy as np
from pathlib import Path

from src.gui.i18n import T
from PySide6.QtWidgets import QFileDialog, QMessageBox

from src.core.utils import load_config, squeeze_sv
from src.gui.workers import MergeFilesWorker

logger = logging.getLogger(__name__)


class FileMixin:
    """文件操作：导入、配置、变量列表"""

    def _import_raw(self):
        """直接选择 .raw 文件导入"""
        paths, _ = QFileDialog.getOpenFileNames(
            self, T("import_raw_files"), "",
            "Raw Files (*.raw);;All Files (*)"
        )
        if not paths:
            return

        # 按文件名排序
        raw_files = sorted([Path(p) for p in paths])

        if self._config is None:
            self._apply_default_config()
        assert self._config is not None

        # 启动合并加载
        self.statusbar.show_progress(T("msg_loading_files", n=len(raw_files)))
        self._current_worker = MergeFilesWorker(raw_files, self._config)
        self._current_worker.finished.connect(self._on_merge_finished)
        self._current_worker.error.connect(self._on_worker_error)
        self._current_worker.progress.connect(self.statusbar.set_status)
        self._current_worker.start()

    def _on_merge_finished(self, ds_Sv):
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
        self._update_variable_list(ds_Sv, sv)
        self.echogram.set_data(sv)
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
