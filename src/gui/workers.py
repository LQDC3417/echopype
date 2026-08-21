"""后台处理工作线程（增强版）

功能增强：
- MergeFilesWorker: 多文件合并加载（按时间顺序拼接 echogram）
- IntegrationWorker 支持 pings/distance EDSU 与 ABC 积分
- 改进错误处理，提供更友好的错误信息
- 添加进度百分比信号
- 支持取消操作
"""

import logging
import traceback
from src.gui.i18n import T
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import xarray as xr
from PySide6.QtCore import QThread, Signal


logger = logging.getLogger(__name__)


def apply_manual_mask(ds, manual_mask):
    """将手动框选的噪声 mask 应用到数据集（写入 Sv_corrected，不覆盖原始 Sv）。"""
    if manual_mask is None:
        return ds
    target = ds["Sv_corrected"] if "Sv_corrected" in ds else ds["Sv"]
    sv_arr = target.values.copy()
    if sv_arr.ndim == 3:
        sv_arr = sv_arr[0]
    if manual_mask.shape == sv_arr.shape:
        sv_arr[manual_mask] = np.nan
        if target.ndim == 3:
            target.values[0, :, :] = sv_arr
        else:
            target.values[:] = sv_arr
        if "Sv_corrected" not in ds:
            ds["Sv_corrected"] = target
    return ds


class LoadFileWorker(QThread):
    """加载 raw 文件"""
    finished = Signal(object)  # EchoData
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, raw_file: Path, config: dict):
        super().__init__()
        self.raw_file = raw_file
        self.config = config

    def run(self):
        try:
            from src.core.acoustic import open_single_file
            self.progress.emit(f"{self.raw_file.name}")
            echodata = open_single_file(self.raw_file, self.config)
            self.finished.emit(echodata)
        except Exception:
            self.error.emit(traceback.format_exc())


class ComputeSvWorker(QThread):
    """计算 Sv"""
    finished = Signal(object)  # xr.Dataset
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, echodata, config: dict):
        super().__init__()
        self.echodata = echodata
        self.config = config

    def run(self):
        try:
            from src.core.acoustic import compute_sv
            self.progress.emit(T("msg_computing_sv"))
            ds_Sv = compute_sv(self.echodata, self.config)
            self.finished.emit(ds_Sv)
        except Exception:
            self.error.emit(traceback.format_exc())


class MergeFilesWorker(QThread):
    """多文件合并加载 — 按时间顺序拼接成一个 echogram

    流程：逐个 .raw → open_single_file → compute_sv → 沿 ping_time 拼接
    """
    finished = Signal(object)  # xr.Dataset（合并后）
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, raw_files: list[Path], config: dict):
        super().__init__()
        self.raw_files = raw_files
        self.config = config

    def run(self):
        try:
            from src.core.acoustic import compute_sv, open_single_file

            ds_list = []
            total = len(self.raw_files)
            for i, path in enumerate(self.raw_files):
                self.progress.emit(T("msg_loading_file", cur=i+1, total=total, name=path.name))

                # 加载
                echodata = open_single_file(path, self.config)

                # 计算 Sv + depth + GPS
                ds = compute_sv(echodata, self.config)

                # 只保留第一个 channel
                if "channel" in ds.dims:
                    ds = ds.isel(channel=0)

                ds_list.append(ds)

            # 沿 ping_time 拼接
            if len(ds_list) == 1:
                merged = ds_list[0]
            else:
                self.progress.emit(T("msg_merging_files", n=len(ds_list)))
                merged = xr.concat(ds_list, dim="ping_time")

            self.finished.emit(merged)

        except Exception:
            self.error.emit(traceback.format_exc())


class NoiseRemovalWorker(QThread):
    """噪声去除"""
    finished = Signal(object)  # xr.Dataset
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, ds_Sv, config: dict, manual_mask=None):
        super().__init__()
        self.ds_Sv = ds_Sv
        self.config = config
        self.manual_mask = manual_mask

    def run(self):
        try:
            from echopype.clean import remove_background_noise
            noise_cfg = self.config.get("processing", {}).get("noise_removal", {})
            self.progress.emit(T("msg_removing_noise"))
            # echopype 0.11.1: remove_background_noise 装饰器 @add_processing_level("L*B")
            # 要求输入带 input_processing_level 属性，缺失时抛 RuntimeError
            if "input_processing_level" not in self.ds_Sv.attrs:
                self.ds_Sv.attrs["input_processing_level"] = "L2A"
            ds = remove_background_noise(
                self.ds_Sv,
                ping_num=noise_cfg.get("ping_num", 5),
                range_sample_num=noise_cfg.get("range_sample_num", 10),
                SNR_threshold=noise_cfg.get("SNR_threshold", "3.0dB"),
            )
            ds = apply_manual_mask(ds, self.manual_mask)
            self.finished.emit(ds)
        except Exception:
            self.error.emit(traceback.format_exc())


class DetectSeafloorWorker(QThread):
    """底部检测 — 支持 basic/enhanced/afsc 三种方法"""
    finished = Signal(object)  # np.ndarray (n_pings,) — sample indices
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, ds_Sv, config: dict):
        super().__init__()
        self.ds_Sv = ds_Sv
        self.config = config

    def run(self):
        try:
            from src.core.bottom_detection import detect_bottom
            from src.core.region import (
                bottom_depth_to_sample_indices,
                get_echo_range_1d,
            )

            bottom_cfg = self.config.get("processing", {}).get("bottom_detection", {})
            method = bottom_cfg.get("method", "basic")
            offset_m = bottom_cfg.get("offset_m", 0.5)

            self.progress.emit(T("msg_bottom_detection", method=method))

            # 调用统一底部检测接口
            bottom_depth_m = detect_bottom(
                self.ds_Sv,
                method=method,
                offset_m=offset_m,
                # basic 参数
                threshold=bottom_cfg.get("threshold", -50.0),
                bin_skip_from_surface=bottom_cfg.get("bin_skip_from_surface", 200),
                # enhanced 参数
                peak_threshold=bottom_cfg.get("peak_threshold", -40.0),
                discrimination_threshold=bottom_cfg.get("discrimination_threshold", -50.0),
                saturation_threshold=bottom_cfg.get("saturation_threshold", -60.0),
                validation_window=bottom_cfg.get("validation_window", 15),
                validation_threshold=bottom_cfg.get("validation_threshold", 3.0),
                smoothing_window=bottom_cfg.get("smoothing_window", 11),
                # afsc 参数
                search_min=bottom_cfg.get("search_min", 10.0),
                window_len=bottom_cfg.get("window_len", 11),
                backstep=bottom_cfg.get("backstep", 35.0),
            )

            # 转换：深度(m) → sample index
            er = get_echo_range_1d(self.ds_Sv)
            if er is None:
                er = np.arange(self.ds_Sv.sizes["range_sample"], dtype=float)

            bottom_indices = bottom_depth_to_sample_indices(bottom_depth_m, er)
            self.finished.emit(bottom_indices)
        except Exception:
            self.error.emit(traceback.format_exc())


class DetectSchoolsWorker(QThread):
    """鱼群检测"""
    finished = Signal(object)  # DataFrame
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, ds_Sv, config: dict):
        super().__init__()
        self.ds_Sv = ds_Sv
        self.config = config

    def run(self):
        try:
            from src.core.school import detect_schools
            self.progress.emit(T("msg_detecting_schools"))
            df = detect_schools(self.ds_Sv, self.config)
            self.finished.emit(df)
        except Exception:
            self.error.emit(traceback.format_exc())


class BatchProcessWorker(QThread):
    """批量处理多个 raw 文件（并行处理）

    信号：
    - file_started(str): 文件开始处理
    - file_finished(str, object): 文件处理完成
    - file_error(str, str): 文件处理失败
    - all_finished(int, int): 全部完成 (成功数, 失败数)
    - progress(str): 进度信息
    """

    file_started = Signal(str)
    file_finished = Signal(str, object)  # (path_str, ds_Sv)
    file_error = Signal(str, str)  # (path_str, error_msg)
    all_finished = Signal(int, int)  # (success_count, error_count)
    progress = Signal(str)

    def __init__(self, raw_files: list[Path], config: dict, max_workers: int = 2):
        super().__init__()
        self.raw_files = raw_files
        self.config = config
        self.max_workers = max_workers
        self._cancelled = False

    def cancel(self):
        """取消批量处理"""
        self._cancelled = True

    def _process_single_file(self, raw_file: Path) -> tuple[str, object, str]:
        """处理单个文件（在线程中执行）。"""
        path_str = str(raw_file)
        try:
            from src.core.acoustic import open_single_file, process_single_file

            if self._cancelled:
                return path_str, None, "Cancelled"

            echodata = open_single_file(raw_file, self.config)

            if self._cancelled:
                return path_str, None, "Cancelled"

            ds_Sv = process_single_file(echodata, self.config)
            return path_str, ds_Sv, ""

        except Exception:
            return path_str, None, traceback.format_exc()

    def run(self):
        """并行处理所有文件"""
        total = len(self.raw_files)
        success_count = 0
        error_count = 0

        self.progress.emit(T("msg_batch_processing", n=total))

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_file = {
                executor.submit(self._process_single_file, rf): rf
                for rf in self.raw_files
            }

            for future in as_completed(future_to_file):
                if self._cancelled:
                    self.progress.emit("Cancelled")
                    break

                path_str, ds_Sv, error_msg = future.result()
                raw_file = future_to_file[future]

                if error_msg:
                    error_count += 1
                    self.file_error.emit(path_str, error_msg)
                    self.progress.emit(T("batch_file_fail", done=success_count + error_count, total=total, name=raw_file.name))
                else:
                    success_count += 1
                    self.file_finished.emit(path_str, ds_Sv)
                    self.progress.emit(T("batch_file_ok", done=success_count + error_count, total=total, name=raw_file.name))

        self.all_finished.emit(success_count, error_count)
        self.progress.emit(T("msg_batch_done", ok=success_count, fail=error_count))


class QualityCheckWorker(QThread):
    """数据质量检查工作线程

    信号：
    - finished(dict): 质量检查结果
    - error(str): 错误信息
    - progress(str): 进度信息
    """
    finished = Signal(dict)
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, ds_Sv, bottom=None):
        super().__init__()
        self.ds_Sv = ds_Sv
        self.bottom = bottom

    def run(self):
        try:
            from src.core.quality import check_bottom_line, check_sv_quality

            self.progress.emit(T("msg_quality_checking"))
            sv_result = check_sv_quality(self.ds_Sv)

            bl_result = None
            if self.bottom is not None:
                self.progress.emit(T("msg_quality_checking"))
                n_samples = self.ds_Sv.sizes.get("range_sample", 0)
                bl_result = check_bottom_line(self.bottom, n_samples)

            self.finished.emit({"sv": sv_result, "bottom": bl_result})

        except Exception:
            self.error.emit(traceback.format_exc())


class MultifreqAnalysisWorker(QThread):
    """多频率分析工作线程

    信号：
    - finished(object): 分析结果 (channel_summary, freq_comparison)
    - error(str): 错误信息
    - progress(str): 进度信息
    """
    finished = Signal(object)
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, ds_Sv, config, channels=None):
        super().__init__()
        self.ds_Sv = ds_Sv
        self.config = config
        self.channels = channels

    def run(self):
        try:
            from src.core.multifreq import (
                compare_frequencies,
                get_channel_summary,
                list_channels,
            )

            self.progress.emit(T("msg_multifreq_analyzing"))
            channel_summary = get_channel_summary(self.ds_Sv)

            channels = list_channels(self.ds_Sv)
            freq_comparison = None
            if len(channels) >= 2:
                self.progress.emit(T("msg_multifreq_analyzing"))
                freq_comparison = compare_frequencies(self.ds_Sv, self.config, self.channels)
            else:
                self.progress.emit("--")

            self.finished.emit({
                "channel_summary": channel_summary,
                "freq_comparison": freq_comparison,
                "channels": channels,
            })

        except Exception:
            self.error.emit(traceback.format_exc())


class RealSedWorker(QThread):
    """真实单体目标检测（分裂波束 SED）工作线程

    流程：compute_TS → detect_single_targets_real（阈值+脉冲长度+测角+补偿）
          → aggregate_targets_to_grid（按积分网格聚合 TS 统计）

    finished 信号发送 tuple(targets_df, grid_df)：
    - targets_df: 逐目标结果（用于 echogram 叠加）
    - grid_df: 网格聚合结果（用于 StatsDialog 表格展示）
    """
    finished = Signal(object)
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, echodata, ds_Sv, config):
        super().__init__()
        self.echodata = echodata
        self.ds_Sv = ds_Sv
        self.config = config

    def run(self):
        try:
            from src.core.acoustic import _detect_waveform_mode
            from echopype.calibrate import compute_TS
            from src.core.sed import aggregate_targets_to_grid, detect_single_targets_real

            self.progress.emit(T("msg_real_sed_running"))
            wm, em = _detect_waveform_mode(self.echodata)
            ds_TS = compute_TS(self.echodata, waveform_mode=wm, encode_mode=em)
            targets_df = detect_single_targets_real(self.echodata, ds_TS, self.config)

            # 按积分网格聚合（即使 targets_df 为空也输出全 NaN 网格）
            grid_df = aggregate_targets_to_grid(targets_df, self.ds_Sv, self.config)
            self.finished.emit((targets_df, grid_df))

        except Exception:
            self.error.emit(traceback.format_exc())


class SvStatsWorker(QThread):
    """Sv 统计摘要工作线程"""
    finished = Signal(object)
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, ds_Sv):
        super().__init__()
        self.ds_Sv = ds_Sv

    def run(self):
        try:
            from src.core.density import sv_statistics_summary
            self.progress.emit(T("msg_sv_stats"))
            result = sv_statistics_summary(self.ds_Sv)
            self.finished.emit(result)
        except Exception:
            self.error.emit(traceback.format_exc())


class TransectSplitWorker(QThread):
    """Transect 分段工作线程"""
    finished = Signal(object)
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, ds_Sv, method="time_gap", max_gap_s=60.0):
        super().__init__()
        self.ds_Sv = ds_Sv
        self.method = method
        self.max_gap_s = max_gap_s

    def run(self):
        try:
            from src.core.multifreq import get_channel_summary, split_transects
            self.progress.emit(T("msg_transect_split"))
            transect_ids = split_transects(self.ds_Sv, method=self.method, max_gap_s=self.max_gap_s)
            n_transects = int(transect_ids.max()) + 1 if len(transect_ids) > 0 else 0
            summary = get_channel_summary(self.ds_Sv)
            self.finished.emit({
                "transect_ids": transect_ids,
                "n_transects": n_transects,
                "channel_summary": summary,
            })
        except Exception:
            self.error.emit(traceback.format_exc())

class IntegrationWorker(QThread):
    """回声积分工作线程

    信号：
    - finished(object): IntegrationResult 积分结果
    - error(str): 错误信息
    - progress(str): 进度信息
    - progress_percent(int): 进度百分比 (0-100)
    """
    finished = Signal(object)
    error = Signal(str)
    progress = Signal(str)
    progress_percent = Signal(int)

    def __init__(self, ds_Sv, config, surface_depth_m=0.0, max_depth_m=None):
        super().__init__()
        self.ds_Sv = ds_Sv
        self.config = config
        self.surface_depth_m = surface_depth_m
        self.max_depth_m = max_depth_m

    def run(self):
        try:
            from src.core.integration import (
                ESUType,
                create_integration_grid,
                integrate,
            )

            cfg = self.config.get("integration", {})
            esu_type = ESUType(cfg.get("esu_type", "pings"))
            esu_size = float(cfg.get("esu_size", 500.0))
            layer_width = float(cfg.get("layer_width", 5.0))
            min_threshold = float(cfg.get("min_threshold", -70.0))
            max_threshold = float(cfg.get("max_threshold", 0.0))
            ts_default = float(cfg.get("ts_default", -30.0))

            self.progress.emit(T("msg_integration_running"))
            grid = create_integration_grid(
                self.ds_Sv,
                esu_type=esu_type,
                esu_size=esu_size,
                layer_width=layer_width,
                surface_depth_m=self.surface_depth_m,
                max_depth_m=self.max_depth_m,
            )

            def _progress_cb(current: int, total: int):
                if total > 0:
                    self.progress_percent.emit(int(current / total * 100))

            result = integrate(
                self.ds_Sv,
                grid,
                min_threshold=min_threshold,
                max_threshold=max_threshold,
                exclude_below_bottom=False,
                ts_default_db=ts_default,
                progress_callback=_progress_cb,
            )
            self.finished.emit(result)

        except Exception:
            self.error.emit(traceback.format_exc())
