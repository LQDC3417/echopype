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
        """将 sample index 转为实际深度(m)并更新状态栏"""
        if self._ds_Sv is None:
            return
        if "echo_range" in self._ds_Sv:
            er = self._ds_Sv["echo_range"]
            if "channel" in er.dims:
                er = er.isel(channel=0)
            er_vals = er.values
            if er_vals.ndim == 2:
                er_vals = er_vals[:, 0]
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

        if self._noise_mask_manual is None:
            self._noise_mask_manual = np.zeros((h, w), dtype=bool)

        px1 = max(0, int(min(x1, x2)))
        py1 = max(0, int(min(y1, y2)))
        px2 = min(h, int(max(x1, x2)))
        py2 = min(w, int(max(y1, y2)))

        self._noise_mask_manual[px1:px2, py1:py2] = True
        self._undo_stack.append(("noise_mask", self._noise_mask_manual.copy()))
        self._redo_stack.clear()

        self.echogram.set_noise_mask(self._noise_mask_manual)
        self.region_table.add_region(
            name=T("region_noise"), region_type=T("region_noise"),
            ping_range=f"{px1}-{px2}", depth_range=f"{py1}-{py2}",
            area=(px2 - px1) * (py2 - py1), mean_sv=0.0,
        )
        self._save_file_state()
        self._apply_noise_params()

    def _inspect_region(self, x1, y1, x2, y2):
        if self._ds_Sv is None:
            return
        sv = squeeze_sv(self._ds_Sv["Sv"].values)

        px1, px2 = int(min(x1, x2)), int(max(x1, x2))
        py1, py2 = int(min(y1, y2)), int(max(y1, y2))
        px1, py1 = max(0, px1), max(0, py1)
        px2 = min(sv.shape[0], px2)
        py2 = min(sv.shape[1], py2)

        if px2 <= px1 or py2 <= py1:
            return

        region_data = sv[px1:px2, py1:py2]
        valid = region_data[~np.isnan(region_data)]
        if len(valid) == 0:
            return

        mean_sv = float(np.mean(valid))
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

    def _undo(self):
        if not self._undo_stack:
            return
        action_type, data = self._undo_stack.pop()
        if action_type == "noise_mask":
            current = self._noise_mask_manual.copy() if self._noise_mask_manual is not None else None
            self._redo_stack.append(("noise_mask", current))
            self._noise_mask_manual = data
            self.echogram.set_noise_mask(data)
            self.statusbar.set_status(T("undo"))

    def _redo(self):
        if not self._redo_stack:
            return
        action_type, data = self._redo_stack.pop()
        if action_type == "noise_mask":
            current = self._noise_mask_manual.copy() if self._noise_mask_manual is not None else None
            self._undo_stack.append(("noise_mask", current))
            self._noise_mask_manual = data
            self.echogram.set_noise_mask(data)
            self.statusbar.set_status(T("redo"))

    # ═══════════════════════════════════════════════════════
    # 视图
    # ═══════════════════════════════════════════════════════

    def _reset_view(self):
        self.echogram.reset_view()

    def _fit_view(self):
        self.echogram.reset_view()

    def _clear_noise_regions(self):
        self._noise_mask_manual = None
        self.echogram.set_noise_mask(None)
        self._save_file_state()
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
            export_density_to_csv,
            export_schools_to_csv,
        )
        from src.core.utils import get_output_dir

        formats = dlg.get_formats()
        content = dlg.get_content()
        if not formats:
            QMessageBox.warning(self, T("dialog_warning"), T("msg_load_data_first"))
            return

        output_dir = get_output_dir(self._config)
        exported = []

        # 按内容导出
        if content.get("sv") and self._ds_Sv is not None:
            from src.core.export import (
                export_sv_to_csv,
                export_to_excel,
                export_to_netcdf,
            )
            if "netcdf" in formats:
                exported.append(export_to_netcdf(self._get_analysis_ds(), output_dir / "sv_data.nc"))
            if "csv" in formats:
                exported.append(export_sv_to_csv(self._get_analysis_ds(), output_dir / "sv_data.csv"))

        if content.get("schools") and self._schools_df is not None and not self._schools_df.empty:
            if "csv" in formats:
                exported.append(export_schools_to_csv(self._schools_df, output_dir / "schools.csv"))

        if content.get("density") and self._density_df is not None and not self._density_df.empty:
            if "csv" in formats:
                exported.append(export_density_to_csv(self._density_df, output_dir / "density.csv"))

        if content.get("grid") and hasattr(self, '_grid_df') and self._grid_df is not None:
            if "csv" in formats:
                exported.append(export_density_to_csv(self._grid_df, output_dir / "grid_stats.csv"))

        if "excel" in formats:
            schools = self._schools_df if content.get("schools") else None
            density = self._density_df if content.get("density") else None
            from src.core.export import export_to_excel
            exported.append(export_to_excel(schools, density, output_dir / "results.xlsx"))

        self.statusbar.set_status(T("msg_export_done", n=len(exported), dir=output_dir))

    def _export_schools(self):
        if self._schools_df is None or self._schools_df.empty:
            QMessageBox.warning(self, T("dialog_warning"), T("msg_detect_schools_first"))
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

