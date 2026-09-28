"""Mixin: 交互操作：鼠标/区域交互、撤销重做、视图控制、导出"""

import logging

import numpy as np

from src.gui.i18n import T
from PySide6.QtWidgets import QFileDialog, QMessageBox

from src.core.utils import squeeze_sv
from src.gui.export_dialog import ExportDialog
from src.gui.toolbars import MouseMode

logger = logging.getLogger(__name__)


class InteractionMixin:
    """交互操作：鼠标/区域交互、撤销重做、视图控制、导出"""

    def _on_mode_changed(self, mode: MouseMode):
        self._current_mode = mode
        self.statusbar.set_status(T("msg_mode", mode=mode.name))

    def _update_depth_at_cursor(self, ping: float, sample: float):
        """将 sample index 转为实际深度(m)并更新状态栏（含 ping 时间戳）"""
        if self._ds_Sv is None:
            return
        # 时间戳：ping index → ping_time（参照 Echoview 状态栏）
        try:
            pt = self._ds_Sv["ping_time"].values
            pidx = round(ping)
            if 0 <= pidx < len(pt):
                self.statusbar.set_ping_time(pt[pidx])
            else:
                self.statusbar.set_ping_time(None)
        except Exception:
            self.statusbar.set_ping_time(None)
        if "echo_range" in self._ds_Sv:
            er = self._ds_Sv["echo_range"]
            if "channel" in er.dims:
                er = er.isel(channel=0)
            pidx = round(ping)
            if not 0 <= pidx < self._ds_Sv.sizes["ping_time"]:
                self.statusbar.set_depth_info(float('nan'))
                return
            if "ping_time" in er.dims:
                er = er.isel(ping_time=pidx)
            er_vals = er.values
            idx = round(sample)
            if 0 <= idx < len(er_vals):
                self.statusbar.set_depth_info(float(er_vals[idx]))
            else:
                self.statusbar.set_depth_info(float('nan'))
        else:
            self.statusbar.set_depth_info(float('nan'))

    def _on_region_selected(self, x1, y1, x2, y2):
        if self._current_mode == MouseMode.SELECT_NOISE:
            self._add_noise_region(x1, y1, x2, y2)
        elif self._current_mode == MouseMode.INSPECT:
            self._inspect_region(x1, y1, x2, y2)

    def _add_noise_region(self, x1, y1, x2, y2):
        if self._ds_Sv is None:
            return
        sv = squeeze_sv(self._ds_Sv["Sv"].values)
        h, w = sv.shape
        previous_mask = (
            self._noise_mask_manual.copy()
            if self._noise_mask_manual is not None
            else None
        )

        if self._noise_mask_manual is None:
            self._noise_mask_manual = np.zeros((h, w), dtype=bool)

        px1 = max(0, int(min(x1, x2)))
        py1 = max(0, int(min(y1, y2)))
        px2 = min(h, int(max(x1, x2)))
        py2 = min(w, int(max(y1, y2)))

        if px2 <= px1 or py2 <= py1:
            self._noise_mask_manual = previous_mask
            return

        self._noise_mask_manual[px1:px2, py1:py2] = True
        self._undo_stack.append(("noise_mask", previous_mask))
        self._redo_stack.clear()

        self.echogram.set_noise_mask(self._noise_mask_manual)
        self.region_table.add_region(
            name=T("region_noise"), region_type=T("region_noise"),
            ping_range=f"{px1}-{px2}", depth_range=f"{py1}-{py2}",
            area=(px2 - px1) * (py2 - py1), mean_sv=0.0,
        )
        self._save_file_state()
        if hasattr(self, "_mark_results_stale"):
            self._mark_results_stale("noise", "bottom", "schools", "integration", "real_sed")
        self._apply_noise_params(automatic=getattr(self, "_noise_enabled", None) is True)

    def _inspect_region(self, x1, y1, x2, y2):
        if self._ds_Sv is None:
            return
        sv = self.echogram.get_data()
        if sv is None:
            return

        px1, px2 = int(min(x1, x2)), int(max(x1, x2))
        py1, py2 = int(min(y1, y2)), int(max(y1, y2))
        px1, py1 = max(0, px1), max(0, py1)
        px2 = min(sv.shape[0], px2)
        py2 = min(sv.shape[1], py2)

        if px2 <= px1 or py2 <= py1:
            return

        region_data = sv[px1:px2, py1:py2]
        valid = region_data[np.isfinite(region_data)]
        if len(valid) == 0:
            return

        # Sv 为对数值，必须在线性域平均后转换回 dB。
        mean_sv = float(10 * np.log10(np.mean(10.0 ** (valid / 10.0))))
        self.region_table.add_region(
            name=T("region_inspect"), region_type=T("region_inspect"),
            ping_range=f"{px1}-{px2}", depth_range=f"{py1}-{py2}",
            area=(px2 - px1) * (py2 - py1), mean_sv=mean_sv,
        )
        self.statusbar.set_status(T("msg_region_sv_avg", val=mean_sv))

    def _on_region_deleted(self, region_id: int):
        self.region_table.remove_region(region_id)

    def _on_variable_selected(self, display_name: str):
        # 变量列表显示 "Sv (原始)"，缓存 key 是 "Sv"
        key = self._display_to_key.get(display_name, display_name)
        data = self._variable_cache.get(key)
        if data is not None:
            self.echogram.set_data(data)

    # ═══════════════════════════════════════════════════════
    # 撤销/重做
    # ═══════════════════════════════════════════════════════

    def _restore_noise_mask(self, mask):
        """恢复手动噪声 mask，并同步重新计算依赖的去噪结果。"""
        self._noise_mask_manual = mask.copy() if mask is not None else None
        self.echogram.set_noise_mask(self._noise_mask_manual)
        self._save_file_state()
        if hasattr(self, "_mark_results_stale"):
            self._mark_results_stale("noise", "bottom", "schools", "integration", "real_sed")
        self._apply_noise_params(automatic=getattr(self, "_noise_enabled", None) is True)

    def _undo(self):
        if not self._undo_stack:
            return
        action_type, data = self._undo_stack.pop()
        if action_type == "noise_mask":
            current = self._noise_mask_manual.copy() if self._noise_mask_manual is not None else None
            self._redo_stack.append(("noise_mask", current))
            InteractionMixin._restore_noise_mask(self, data)
            self.statusbar.set_status(T("undo"))

    def _redo(self):
        if not self._redo_stack:
            return
        action_type, data = self._redo_stack.pop()
        if action_type == "noise_mask":
            current = self._noise_mask_manual.copy() if self._noise_mask_manual is not None else None
            self._undo_stack.append(("noise_mask", current))
            InteractionMixin._restore_noise_mask(self, data)
            self.statusbar.set_status(T("redo"))

    # ═══════════════════════════════════════════════════════
    # 视图
    # ═══════════════════════════════════════════════════════

    def _reset_view(self):
        self.echogram.reset_view()

    def _fit_view(self):
        self.echogram.reset_view()

    def _clear_noise_regions(self):
        if self._noise_mask_manual is None:
            return
        self._undo_stack.append(("noise_mask", self._noise_mask_manual.copy()))
        self._redo_stack.clear()
        InteractionMixin._restore_noise_mask(self, None)
        self.statusbar.set_status(T("msg_noise_cleared"))

    def _clear_schools(self):
        self._schools_mask = None
        self._schools_df = None
        self.echogram.set_school_mask(None)
        self._save_file_state()
        self.statusbar.set_status(T("msg_schools_cleared"))

    # ═══════════════════════════════════════════════════════
    # 导出
    # ═══════════════════════════════════════════════════════

    def _export(self):
        dlg = ExportDialog(self)
        if dlg.exec() != ExportDialog.Accepted:
            return

        from src.core.export import (
            export_schools_to_csv,
        )
        from src.core.utils import get_output_dir

        formats = dlg.get_formats()
        content = dlg.get_content()
        if not formats:
            QMessageBox.warning(self, T("dialog_warning"), T("msg_load_data_first"))
            return

        required_results = []
        if content.get("schools"):
            required_results.append("schools")
        if content.get("grid"):
            required_results.append("integration")
        if content.get("sv") and self._ds_Sv is not None and "Sv_corrected" in self._ds_Sv:
            required_results.append("noise")
        if required_results and not self._ensure_result_exportable(*required_results):
            return

        output_dir = get_output_dir(self._config)
        exported = []
        sv_stem = "sv_data_partial" if self._input_incomplete else "sv_data"

        # 按内容导出
        if content.get("sv") and self._ds_Sv is not None:
            from src.core.export import (
                export_sv_to_csv,
                export_to_netcdf,
                export_to_zarr,
            )
            if "zarr" in formats:
                try:
                    exported.append(export_to_zarr(self._get_analysis_ds(), output_dir / f"{sv_stem}.zarr"))
                except FileExistsError as exc:
                    QMessageBox.warning(self, T("dialog_warning"), str(exc))
                    return
            if "netcdf" in formats:
                exported.append(export_to_netcdf(self._get_analysis_ds(), output_dir / f"{sv_stem}.nc"))
            if "csv" in formats:
                exported.append(export_sv_to_csv(self._get_analysis_ds(), output_dir / f"{sv_stem}.csv"))

        if content.get("schools") and self._schools_df is not None and not self._schools_df.empty:
            if "csv" in formats:
                exported.append(export_schools_to_csv(self._schools_df, output_dir / "schools.csv"))

        grid_df = getattr(self, "_integration_df", None)
        if content.get("grid") and grid_df is not None and not grid_df.empty:
            if "csv" in formats:
                from src.core.export import export_density_to_csv
                exported.append(export_density_to_csv(grid_df, output_dir / "grid_stats.csv"))

        if "excel" in formats:
            schools = self._schools_df if content.get("schools") else None
            from src.core.export import export_to_excel
            exported.append(export_to_excel(schools, grid_df if content.get("grid") else None, output_dir / "results.xlsx"))

        self.statusbar.set_status(T("msg_export_done", n=len(exported), dir=output_dir))

    def _export_schools(self):
        if self._schools_df is None or self._schools_df.empty:
            QMessageBox.warning(self, T("dialog_warning"), T("msg_detect_schools_first"))
            return
        if not self._ensure_result_exportable("schools"):
            return
        path, _ = QFileDialog.getSaveFileName(self, T("menu_export_schools"), "", "CSV (*.csv)")
        if path:
            self._schools_df.to_csv(path, index=False, encoding="utf-8-sig")
            self.statusbar.set_status(f"{T('export_school_list')}: {path}")

    # ═══════════════════════════════════════════════════════
    # 其他
    # ═══════════════════════════════════════════════════════

    def _show_about(self):
        QMessageBox.about(self, T("about_title"),
            T("about_html")
        )

    def _on_worker_error(self, msg):
        self._run_all_chain = False
        self.statusbar.hide_progress()
        self.statusbar.set_status(f"{T('dialog_error')}: {msg}")
        QMessageBox.critical(self, T("dialog_processing_error"), msg)

