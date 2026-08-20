"""Mixin: 高级分析：质量检查、多频分析、单体目标检测、Sv统计、Transect分段"""

import logging

from src.gui.i18n import T
from PySide6.QtWidgets import QMessageBox

from src.gui.workers import (
    MultifreqAnalysisWorker,
    QualityCheckWorker,
    RealSedWorker,
    SvStatsWorker,
    TransectSplitWorker,
)

logger = logging.getLogger(__name__)


class AnalysisMixin:
    """高级分析：质量检查、多频分析、单体目标检测、Sv统计、Transect分段"""

    def _run_quality_check(self):
        """运行数据质量检查"""
        if self._ds_Sv is None:
            QMessageBox.warning(self, T("dialog_warning"), T("msg_load_data_first"))
            return
        self.statusbar.show_progress(T("msg_quality_checking"))
        self._current_worker = QualityCheckWorker(
            self._get_analysis_ds(), self._bottom_line
        )
        self._current_worker.finished.connect(self._on_quality_done)
        self._current_worker.error.connect(self._on_worker_error)
        self._current_worker.progress.connect(self.statusbar.set_status)
        self._current_worker.start()

    def _on_quality_done(self, result):
        """质量检查完成 → 弹窗显示结果"""
        self.statusbar.hide_progress()
        sv_check = result.get("sv", {})
        bl_check = result.get("bottom")

        lines = [f"═══ {T('quality_title')} ═══\n"]

        # Sv 检查
        valid_icon = "✅" if sv_check.get("valid") else "⚠️"
        lines.append(f"{valid_icon} {T('quality_report_sv_data', pings=sv_check.get('total_pings', 0), samples=sv_check.get('total_samples', 0))}")
        sv_range = sv_check.get("sv_range", (0, 0))
        lines.append(f"   {T('quality_report_sv_range', min=sv_range[0], max=sv_range[1])}")
        lines.append(f"   {T('quality_report_nan', ratio=sv_check.get('nan_ratio', 0))}")
        for w in sv_check.get("warnings", []):
            lines.append(f"   ⚠ {w}")

        # 底线检查
        if bl_check:
            lines.append("")
            bl_icon = "✅" if bl_check.get("valid") else "⚠️"
            lines.append(f"{bl_icon} {T('quality_report_bottom', n=bl_check.get('valid_pings', 0))}")
            lines.append(f"   {T('quality_report_nan', ratio=bl_check.get('nan_ratio', 0))}")
            for w in bl_check.get("warnings", []):
                lines.append(f"   ⚠ {w}")

        all_valid = sv_check.get("valid", False) and (bl_check is None or bl_check.get("valid", False))
        title = T("quality_report_title_pass") if all_valid else T("quality_report_title_fail")
        QMessageBox.information(self, title, "\n".join(lines))

    # ═══════════════════════════════════════════════════════
    # 多频分析
    # ═══════════════════════════════════════════════════════

    def _run_multifreq_analysis(self):
        """运行多频率分析"""
        if self._ds_Sv is None or self._config is None:
            QMessageBox.warning(self, T("dialog_warning"), T("msg_load_data_first"))
            return
        self.statusbar.show_progress(T("msg_multifreq_analyzing"))
        self._current_worker = MultifreqAnalysisWorker(
            self._get_analysis_ds(), self._config
        )
        self._current_worker.finished.connect(self._on_multifreq_done)
        self._current_worker.error.connect(self._on_worker_error)
        self._current_worker.progress.connect(self.statusbar.set_status)
        self._current_worker.start()

    def _on_multifreq_done(self, result):
        """多频分析完成 → 弹窗显示结果"""
        self.statusbar.hide_progress()
        channel_summary = result.get("channel_summary")
        freq_comparison = result.get("freq_comparison")
        channels = result.get("channels", [])

        lines = [f"═══ {T('multifreq_title')} ═══\n"]
        lines.append(f"{T('msg_multifreq_channels', n=len(channels))}\n")

        # 通道摘要
        if channel_summary is not None and not channel_summary.empty:
            lines.append(f"── {T('msg_channel_info')} ──")
            for _, row in channel_summary.iterrows():
                freq_mhz = row.get("frequency_Hz", 0) / 1e6 if row.get("frequency_Hz") else 0
                lines.append(f"  {row['channel']}: {freq_mhz:.1f} MHz, {row.get('n_pings', 0)} pings")

        # 频率对比
        if freq_comparison is not None and not freq_comparison.empty:
            lines.append(f"\n── {T('msg_freq_comparison')} ──")
            for _, row in freq_comparison.iterrows():
                freq_mhz = row.get("frequency_Hz", 0) / 1e6 if row.get("frequency_Hz") else 0
                lines.append(f"  {row['channel']}: mean_abc={row.get('mean_abc', 0):.4f}")

        QMessageBox.information(self, T("msg_multifreq_title"), "\n".join(lines))

    # ═══════════════════════════════════════════════════════
    # 单体目标检测
    # ═══════════════════════════════════════════════════════

    def _run_real_sed(self):
        """运行真实单体目标检测（分裂波束 SED）"""
        if self._echodata is None:
            QMessageBox.warning(self, T("dialog_warning"), T("msg_load_data_first"))
            return
        # 从 UI 同步配置
        rs_cfg = self.property_panel.processing.get_real_sed_config()
        self._config.setdefault("single_target_real", {}).update(rs_cfg)
        self.statusbar.show_progress(T("msg_real_sed_running"))
        self._current_worker = RealSedWorker(self._echodata, self._config)
        self._current_worker.finished.connect(self._on_real_sed_done)
        self._current_worker.error.connect(self._on_worker_error)
        self._current_worker.progress.connect(self.statusbar.set_status)
        self._current_worker.start()

    def _on_real_sed_done(self, targets_df):
        """真实 SED 完成 → 展示结果表格 + echogram 叠加"""
        self.statusbar.hide_progress()
        n = len(targets_df) if targets_df is not None and not targets_df.empty else 0
        if n == 0:
            self.echogram.clear_single_targets()
            QMessageBox.information(self, T("msg_real_sed_done"), T("msg_real_sed_none"))
            return
        self._real_sed_df = targets_df
        self.stats_dialog.update_real_sed(targets_df)
        self.echogram.set_single_targets(targets_df)
        self.statusbar.set_status(T("msg_real_sed_done", n=n))
        self._show_stats()

    # ═══════════════════════════════════════════════════════
    # Sv 统计摘要
    # ═══════════════════════════════════════════════════════

    def _run_sv_stats(self):
        """Sv 统计摘要"""
        if self._ds_Sv is None:
            QMessageBox.warning(self, T("dialog_warning"), T("msg_load_data_first"))
            return
        self.statusbar.show_progress(T("msg_sv_stats"))
        self._current_worker = SvStatsWorker(self._get_analysis_ds())
        self._current_worker.finished.connect(self._on_sv_stats_done)
        self._current_worker.error.connect(self._on_worker_error)
        self._current_worker.progress.connect(self.statusbar.set_status)
        self._current_worker.start()

    def _on_sv_stats_done(self, result):
        self.statusbar.hide_progress()
        if result is None or result.empty:
            QMessageBox.information(self, T("msg_sv_stats_title"), T("msg_no_sv_stats"))
            return
        lines = [f"═══ {T('msg_sv_stats_title')} ═══\n"]
        for _, row in result.iterrows():
            lines.append(f"Transect {row.get('transect_id', '?')}: {row.get('n_pings', 0)} pings")
            lines.append(f"  {T('msg_mean')}: {row.get('mean_sv', 0):.1f} dB, {T('msg_median')}: {row.get('median_sv', 0):.1f} dB")
            lines.append(f"  {T('msg_p5_p95')}: [{row.get('p5_sv', 0):.1f}, {row.get('p95_sv', 0):.1f}] dB")
            lines.append(f"  NaN: {row.get('nan_ratio', 0):.1%}")
        QMessageBox.information(self, T("msg_sv_stats_title"), "\n".join(lines))

    # ═══════════════════════════════════════════════════════
    # Transect 分段
    # ═══════════════════════════════════════════════════════

    def _run_transect_split(self):
        """Transect 分段"""
        if self._ds_Sv is None:
            QMessageBox.warning(self, T("dialog_warning"), T("msg_load_data_first"))
            return
        self.statusbar.show_progress(T("msg_transect_split"))
        self._current_worker = TransectSplitWorker(self._get_analysis_ds())
        self._current_worker.finished.connect(self._on_transect_split_done)
        self._current_worker.error.connect(self._on_worker_error)
        self._current_worker.progress.connect(self.statusbar.set_status)
        self._current_worker.start()

    def _on_transect_split_done(self, result):
        self.statusbar.hide_progress()
        n = result.get("n_transects", 0)
        QMessageBox.information(self, T("msg_transect_split"), T("msg_transect_split_done", n=n))

    def _update_file_info(self, ds_Sv):
        """更新状态栏文件信息"""
        if ds_Sv is None:
            return
        info_parts = []
        if "channel" in ds_Sv:
            info_parts.append(str(ds_Sv["channel"].values[0]))
        if "ping_time" in ds_Sv:
            n_pings = len(ds_Sv["ping_time"])
            info_parts.append(f"{n_pings} pings")
        if "range_sample" in ds_Sv:
            n_samples = len(ds_Sv["range_sample"])
            info_parts.append(f"{n_samples} samples")
        self.statusbar.set_status(" | ".join(info_parts))
        # 同步属性面板文件信息
        self.property_panel.file_info.update_info(ds_Sv)

    # ═══════════════════════════════════════════════════════
    # 交互
    # ═══════════════════════════════════════════════════════
