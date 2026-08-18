"""Mixin: 文件操作：导入、批量处理、文件缓存、切换、变量列表"""

import logging
import traceback

import numpy as np
import pandas as pd
from pathlib import Path

from src.gui.i18n import T
from PySide6.QtWidgets import QFileDialog, QMessageBox

from src.core.utils import load_config, squeeze_sv
from src.gui.fileset import Fileset
from src.gui.fileset_tree import BatchImportDialog
from src.gui.workers import (
    BatchProcessWorker,
    ComputeSvWorker,
    LoadFileWorker,
)

logger = logging.getLogger(__name__)


class FileMixin:
    """文件操作：导入、批量处理、文件缓存、切换、变量列表"""

    def _import_raw(self):
        """打开批量导入对话框"""
        dlg = BatchImportDialog(self)
        dlg.fileset_created.connect(self.fileset_tree.add_fileset)
        dlg.exec()

    def _open_config(self):
        path, _ = QFileDialog.getOpenFileName(
            self, T("open_config"), "", "YAML (*.yaml *.yml);;All (*)"
        )
        if path:
            try:
                self._config = load_config(path)
                # 配置验证
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

    # ═══════════════════════════════════════════════════════
    # 批量处理（并行）
    # ═══════════════════════════════════════════════════════

    def _batch_process_files(self):
        """批量处理多个 raw 文件（后台并行）"""
        paths, _ = QFileDialog.getOpenFileNames(
            self, T("batch_process"), str(Path.cwd()), "Raw (*.raw);;All (*)"
        )
        if not paths:
            return
        if self._batch_worker is not None and self._batch_worker.isRunning():
            QMessageBox.information(self, T("dialog_info"), T("msg_batch_in_progress"))
            return
        if self._config is None:
            self._apply_default_config()
        assert self._config is not None

        raw_files = [Path(p) for p in paths]
        self.statusbar.show_progress(T("msg_batch_processing", n=len(raw_files)))
        self._batch_results = {}

        worker = BatchProcessWorker(raw_files, self._config, max_workers=2)
        worker.progress.connect(self.statusbar.set_status)
        worker.file_finished.connect(self._on_batch_file_finished)
        worker.file_error.connect(self._on_batch_file_error)
        worker.all_finished.connect(self._on_batch_all_finished)
        self._batch_worker = worker
        worker.start()

    def _on_batch_file_finished(self, path_str: str, ds_Sv):
        """单个文件处理完成 → 缓存结果"""
        try:
            sv = squeeze_sv(ds_Sv["Sv"].values)
            self._file_cache[path_str] = {
                "sv": sv.astype(np.float32),
                "ds": ds_Sv,
                "bottom": None,
                "noise_mask": None,
                "school_mask": None,
                "surface_depth_m": self._surface_depth_m,
            }
            self._batch_results[path_str] = ds_Sv
        except Exception:
            logger.exception("批量处理结果缓存失败: %s", path_str)

    def _on_batch_file_error(self, path_str: str, error_msg: str):
        """单个文件处理失败"""
        logger.error("批量处理失败 %s:\n%s", path_str, error_msg)

    def _on_batch_all_finished(self, success: int, error: int):
        """批量处理全部完成 → 更新队列并显示第一个成功文件"""
        new_paths = [Path(p) for p in self._batch_results]
        if new_paths:
            # 当前队列为空 → 设为新队列并显示第一个；否则追加到队尾
            if not self._raw_file_queue:
                self._raw_file_queue = list(new_paths)
                self._raw_queue_index = 0
                first = self._file_cache[str(self._raw_file_queue[0])]
                self._apply_sv_to_display(first["ds"], first["sv"])
            else:
                for p in new_paths:
                    if p not in self._raw_file_queue:
                        self._raw_file_queue.append(p)

        self.statusbar.hide_progress()
        self._batch_worker = None
        self._batch_results = {}
        self.statusbar.set_status(T("msg_batch_done", ok=success, fail=error))
        QMessageBox.information(
            self, T("msg_batch_result_title"), T("msg_batch_result", ok=success, fail=error)
        )

    def _on_fileset_selected(self, fileset: Fileset):
        """选中文件集后自动逐个加载全部 raw 文件，缓存 Sv 数据"""
        self._current_fileset = fileset
        self._file_cache.clear()
        self._raw_file_queue = list(fileset.files)
        self._raw_queue_index = 0

        if fileset.files:
            self.statusbar.set_status(
                T("msg_fileset_selected", name=fileset.name, count=fileset.file_count)
            )
            self._load_file_and_cache(fileset.files[0])
        else:
            self.statusbar.set_status(
                T("msg_fileset_empty", name=fileset.name)
            )

    def _load_file_and_cache(self, path: Path):
        """加载 raw → Sv，缓存结果，然后自动处理队列中下一个"""
        if not path.exists():
            logger.debug("File not found: %s, skipping", path)
            self._on_cache_load_error(f"{path.name}", path)
            return

        self.statusbar.show_progress(f"[{self._raw_queue_index + 1}/{len(self._raw_file_queue)}]: {path.name}")

        if self._config is None:
            self._apply_default_config()
        assert self._config is not None
        if "sonar_model" not in self._config.get("processing", {}):
            self._config["processing"]["sonar_model"] = "EK80"

        logger.debug("Starting LoadFileWorker for %s", path.name)
        self._current_worker = LoadFileWorker(path, self._config)
        self._current_worker.finished.connect(lambda ed, p=path: self._on_cached_file_loaded(ed, p))
        self._current_worker.error.connect(lambda msg, p=path: self._on_cache_load_error(msg, p))
        self._current_worker.progress.connect(self.statusbar.set_status)
        self._current_worker.start()

    def _on_cached_file_loaded(self, echodata, path: Path):
        """文件加载完成 → 计算 Sv → 缓存"""
        self._echodata = echodata
        self.statusbar.show_progress(f"[{self._raw_queue_index + 1}/{len(self._raw_file_queue)}]: {path.name}")

        assert self._config is not None
        self._current_worker = ComputeSvWorker(echodata, self._config)
        self._current_worker.finished.connect(lambda ds, p=path: self._on_cached_sv_computed(ds, p))
        self._current_worker.error.connect(lambda msg, p=path: self._on_cache_load_error(msg, p))
        self._current_worker.progress.connect(self.statusbar.set_status)
        self._current_worker.start()

    def _apply_sv_to_display(self, ds_Sv, sv):
        """将 Sv 数据应用到显示：优化内存 + 更新渲染器"""
        from src.core.utils import log_memory_usage, optimize_array_dtype
        # 内存优化：float64 → float32
        sv = optimize_array_dtype(sv)
        self._ds_Sv = ds_Sv
        self._update_variable_list(ds_Sv, sv)
        self.echogram.set_data(sv)
        self._update_file_info(ds_Sv)
        self._update_surface_line_render()
        log_memory_usage("load")

    def _on_cached_sv_computed(self, ds_Sv, path: Path):
        """Sv 计算完成 → 缓存 → 显示 → 自动加载下一个"""
        sv = squeeze_sv(ds_Sv["Sv"].values)

        # 缓存（只存 Sv+depth，噪声和底部由用户手动触发）
        self._file_cache[str(path)] = {
            "sv": sv.astype(np.float32),
            "ds": ds_Sv,
            "bottom": None,
            "noise_mask": None,
            "school_mask": None,
            "surface_depth_m": self._surface_depth_m,
        }

        is_first = (self._raw_queue_index == 0)
        if is_first:
            # 第一个文件：显示 + 更新变量列表
            self._apply_sv_to_display(ds_Sv, sv)
            self.statusbar.hide_progress()
            self.statusbar.set_status(
                T("msg_file_switched", cur=1, total=len(self._raw_file_queue), name=path.name)
            )

        # 加载下一个
        self._raw_queue_index += 1
        if self._raw_queue_index < len(self._raw_file_queue):
            next_path = self._raw_file_queue[self._raw_queue_index]
            self._load_file_and_cache(next_path)
        else:
            # 全部加载完成
            total = len(self._raw_file_queue)
            self.statusbar.hide_progress()
            self.statusbar.set_status(
                T("msg_all_cached", total=total)
            )
            self._raw_queue_index = 0  # 重置

    def _on_cache_load_error(self, msg, path: Path):
        """某个文件加载失败，跳过继续"""
        self.statusbar.set_status(f"⚠ {path.name}: {msg}")
        self._raw_queue_index += 1
        if self._raw_queue_index < len(self._raw_file_queue):
            self._load_file_and_cache(self._raw_file_queue[self._raw_queue_index])

    def _switch_file(self, delta: int):
        """右键翻页 — 切换到上一个/下一个已缓存文件，恢复完整状态"""
        n_queue = len(self._raw_file_queue)
        n_cache = len(self._file_cache)
        logger.debug("_switch_file(delta=%d), queue=%d, cache=%d, idx=%d", delta, n_queue, n_cache, self._raw_queue_index)

        # 如果队列为空但有当前文件集，自动初始化
        if n_queue == 0 and self._current_fileset is not None:
            self._on_fileset_selected(self._current_fileset)
            n_queue = len(self._raw_file_queue)
            n_cache = len(self._file_cache)

        if n_queue == 0:
            self.statusbar.set_status(T("msg_no_loaded_files"))
            return

        new_idx = self._raw_queue_index + delta
        if new_idx < 0 or new_idx >= n_queue:
            self.statusbar.set_status(T("msg_boundary_reached", cur=self._raw_queue_index + 1, total=n_queue))
            return
        self._raw_queue_index = new_idx
        path = self._raw_file_queue[new_idx]
        key = str(path)
        cached = self._file_cache.get(key)
        if cached is None:
            self.statusbar.set_status(T("msg_file_not_cached", name=path.name, cached=n_cache, total=n_queue))
            return

        self._ds_Sv = cached["ds"]
        sv = cached["sv"]
        logger.debug("Switching to %s, sv.shape=%s", path.name, sv.shape)

        # 恢复变量列表
        self._update_variable_list(cached["ds"], sv)

        # 显示当前选中的变量数据
        current_var = self.variable_list.currentItem()
        if current_var:
            key_name = self._display_to_key.get(current_var.text(), "Sv")
            display_data = self._variable_cache.get(key_name, sv)
            self.echogram.set_data(display_data)
        else:
            self.echogram.set_data(sv)

        # 恢复底线
        bottom = cached.get("bottom")
        if bottom is not None:
            self._bottom_line = bottom
            self.echogram.set_bottom_line(bottom)
        else:
            self._bottom_line = None
            self.echogram.set_bottom_line(None)

        # 恢复表线深度
        self._surface_depth_m = cached.get("surface_depth_m", 2.0)
        spin_surface = self.property_panel.processing.spin_surface
        spin_surface.blockSignals(True)
        spin_surface.setValue(self._surface_depth_m)
        spin_surface.blockSignals(False)
        self._update_surface_line_render()

        # 恢复噪声 mask
        self._noise_mask_manual = cached.get("noise_mask")
        self.echogram.set_noise_mask(self._noise_mask_manual)

        # 恢复鱼群 mask
        self._schools_mask = cached.get("school_mask")
        self.echogram.set_school_mask(self._schools_mask)

        # 重建分析区域（确保 _ds_Sv_analysis 与当前底线/表线一致）
        self._apply_analysis_region_to_ds()

        self.statusbar.set_status(
            T("msg_file_switched", cur=new_idx + 1, total=n_queue, name=path.name)
        )
        self.statusbar.set_file_info(f"[{new_idx + 1}/{n_queue}] {path.name}")

    def _on_channel_selected(self, channel: str):
        self._current_channel = channel
        self.statusbar.set_status(T("msg_frequency", ch=channel))

    def _load_file(self, path: Path):
        """双击文件树中的文件 → 在已有队列中定位，不破坏缓存"""
        if not path.exists():
            QMessageBox.warning(self, T("dialog_error"), f"{path}")
            return
        # 尝试在当前队列中定位
        key = str(path)
        for i, q in enumerate(self._raw_file_queue):
            if str(q) == key:
                self._raw_queue_index = i
                self._switch_file(0)
                return
        # 不在队列中 → 追加
        self._raw_file_queue.append(path)
        self._raw_queue_index = len(self._raw_file_queue) - 1
        self._load_file_and_cache(path)

    # ═══════════════════════════════════════════════════════
    # 变量列表统一管理
    # ═══════════════════════════════════════════════════════

    def _update_variable_list(self, ds_Sv, sv_raw=None):
        """统一更新变量列表和缓存映射。

        Parameters
        ----------
        ds_Sv : xr.Dataset
            数据集（可能包含 Sv 和 Sv_corrected）
        sv_raw : np.ndarray, optional
            原始 Sv 2D 数组。若为 None 则从 ds_Sv 提取。
        """
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
        """将当前文件的状态（底线、噪声、鱼群、表线）保存到缓存"""
        if not self._raw_file_queue or self._raw_queue_index >= len(self._raw_file_queue):
            return
        key = str(self._raw_file_queue[self._raw_queue_index])
        if key not in self._file_cache:
            return
        cache = self._file_cache[key]
        cache["bottom"] = self._bottom_line
        cache["noise_mask"] = self._noise_mask_manual
        cache["school_mask"] = self._schools_mask
        cache["surface_depth_m"] = self._surface_depth_m

    # ═══════════════════════════════════════════════════════
    # 处理流水线
    # ═══════════════════════════════════════════════════════

