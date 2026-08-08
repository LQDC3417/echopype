"""后台处理工作线程（增强版）

功能增强：
- GridWorker 添加更详细的进度显示
- 改进错误处理，提供更友好的错误信息
- 添加进度百分比信号
- 支持取消操作
"""

import traceback
import logging
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from PySide6.QtCore import QThread, Signal
from pathlib import Path

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
            self.progress.emit(f"加载文件: {self.raw_file.name}")
            echodata = open_single_file(self.raw_file, self.config)
            self.finished.emit(echodata)
        except Exception as e:
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
            self.progress.emit("计算 Sv...")
            ds_Sv = compute_sv(self.echodata, self.config)
            self.finished.emit(ds_Sv)
        except Exception as e:
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
            self.progress.emit("去除背景噪声...")
            ds = remove_background_noise(
                self.ds_Sv,
                ping_num=noise_cfg.get("ping_num", 5),
                range_sample_num=noise_cfg.get("range_sample_num", 10),
                SNR_threshold=noise_cfg.get("SNR_threshold", "3.0dB"),
            )
            ds = apply_manual_mask(ds, self.manual_mask)
            self.finished.emit(ds)
        except Exception as e:
            self.error.emit(traceback.format_exc())


class DetectSeafloorWorker(QThread):
    """底部检测 — 使用 echopype detect_seafloor API"""
    finished = Signal(object)  # np.ndarray (n_pings,) — sample indices
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, ds_Sv, config: dict):
        super().__init__()
        self.ds_Sv = ds_Sv
        self.config = config

    def run(self):
        try:
            from echopype.mask import detect_seafloor
            from src.core.region import get_echo_range_1d, bottom_depth_to_sample_indices

            bottom_cfg = self.config.get("processing", {}).get("bottom_detection", {})
            threshold = bottom_cfg.get("threshold", -50.0)
            offset_m = bottom_cfg.get("offset_m", 0.5)
            bin_skip = bottom_cfg.get("bin_skip_from_surface", 200)
            method = bottom_cfg.get("method", "basic")

            ds = self.ds_Sv
            var_name = "Sv_corrected" if "Sv_corrected" in ds else "Sv"

            channel = str(ds["channel"].values[0]) if "channel" in ds else None

            params = {
                "var_name": var_name,
                "threshold": threshold,
                "offset_m": offset_m,
                "bin_skip_from_surface": bin_skip,
            }
            if channel:
                params["channel"] = channel

            self.progress.emit("echopype detect_seafloor ...")
            bottom_depth_m = detect_seafloor(ds, method=method, params=params)

            # 使用后端函数转换：深度(m) → sample index
            er = get_echo_range_1d(ds)
            if er is None:
                er = np.arange(ds.sizes["range_sample"], dtype=float)

            bottom_indices = bottom_depth_to_sample_indices(bottom_depth_m, er)
            self.finished.emit(bottom_indices)
        except Exception as e:
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
            school_cfg = self.config.get("school_detection", {})
            self.progress.emit("检测鱼群...")
            df = detect_schools(self.ds_Sv, school_cfg)
            self.finished.emit(df)
        except Exception as e:
            self.error.emit(traceback.format_exc())


class ComputeDensityWorker(QThread):
    """密度估算（裁剪）"""
    finished = Signal(object)  # DataFrame
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, schools_df, ds_Sv, config: dict):
        super().__init__()
        self.schools_df = schools_df
        self.ds_Sv = ds_Sv
        self.config = config

    def run(self):
        try:
            from src.core.density import estimate_density
            self.progress.emit("计算密度...")
            df = estimate_density(self.schools_df, self.ds_Sv, self.config)
            self.finished.emit(df)
        except Exception as e:
            self.error.emit(traceback.format_exc())


class GridWorker(QThread):
    """网格化分析（增强版）

    功能增强：
    - 添加详细的进度显示和百分比
    - 改进错误处理，提供更友好的错误信息
    - 支持取消操作
    - 添加统计指标选择和输出格式支持
    """

    # 信号
    finished = Signal(object)  # DataFrame
    error = Signal(str)
    progress = Signal(str)
    progress_percent = Signal(int)  # 进度百分比 (0-100)
    status_changed = Signal(str)  # 状态变化

    def __init__(self, ds_Sv, surface_depth_m, grid_config, density_config):
        super().__init__()
        self.ds_Sv = ds_Sv
        self.surface_depth_m = surface_depth_m
        self.grid_config = grid_config
        self.density_config = density_config
        self._cancelled = False
        self._current_step = ""
        self._total_steps = 4  # 总步骤数

    def cancel(self):
        """取消网格分析"""
        self._cancelled = True
        self.status_changed.emit("正在取消...")

    def _check_cancelled(self):
        """检查是否已取消"""
        if self._cancelled:
            raise InterruptedError("用户取消了网格分析")

    def _emit_progress(self, step_name, step_number):
        """发射进度信号"""
        self._current_step = step_name
        progress_percent = int((step_number / self._total_steps) * 100)
        self.progress.emit(step_name)
        self.progress_percent.emit(progress_percent)
        self.status_changed.emit(f"步骤 {step_number}/{self._total_steps}: {step_name}")

    def run(self):
        """执行网格分析"""
        try:
            # 导入必要的模块
            from src.core.grid import create_grid, compute_grid_density
            
            # 步骤 1: 参数验证
            self._emit_progress("验证参数...", 1)
            self._check_cancelled()
            self._validate_parameters()
            
            # 步骤 2: 创建网格
            self._emit_progress("创建网格...", 2)
            self._check_cancelled()
            
            grid_cells = create_grid(
                self.ds_Sv,
                surface_depth_m=self.surface_depth_m,
                vertical_interval_m=self.grid_config["vertical_interval_m"],
                horizontal_interval=self.grid_config["horizontal_interval"],
                method=self.grid_config["horizontal_method"],
            )
            
            # 验证网格创建结果
            if not grid_cells:
                raise ValueError("网格创建失败：未生成任何网格单元")
            
            self.progress.emit(f"创建了 {len(grid_cells)} 个网格单元")
            
            # 步骤 3: 计算网格统计
            self._emit_progress("计算网格统计...", 3)
            self._check_cancelled()
            
            # 准备配置
            config = {"density": self.density_config}
            
            # 添加选中的统计指标
            if "selected_metrics" in self.grid_config:
                config["selected_metrics"] = self.grid_config["selected_metrics"]
            
            # 添加输出格式
            if "output_format" in self.grid_config:
                config["output_format"] = self.grid_config["output_format"]
            
            # 添加元数据选项
            if "include_metadata" in self.grid_config:
                config["include_metadata"] = self.grid_config["include_metadata"]
            
            df = compute_grid_density(self.ds_Sv, grid_cells, config)
            
            # 步骤 4: 完成
            self._emit_progress("完成", 4)
            self._check_cancelled()
            
            # 验证结果
            if df is None:
                raise ValueError("网格统计计算失败：返回了空结果")
            
            if df.empty:
                logger.warning("网格统计结果为空，可能是因为数据不足或参数设置不当")
            
            self.finished.emit(df)
            
        except InterruptedError as e:
            # 用户取消
            logger.info(f"网格分析被取消: {str(e)}")
            self.error.emit(f"网格分析已取消: {str(e)}")
            
        except ImportError as e:
            # 导入错误
            error_msg = f"缺少必要的模块: {str(e)}\n请检查 echopype 和相关依赖是否正确安装"
            logger.error(error_msg)
            self.error.emit(error_msg)
            
        except KeyError as e:
            # 配置键错误
            error_msg = f"配置参数错误: 缺少必要的参数 {str(e)}\n请检查网格配置是否完整"
            logger.error(error_msg)
            self.error.emit(error_msg)
            
        except ValueError as e:
            # 值错误
            error_msg = f"参数值错误: {str(e)}\n请检查输入参数是否有效"
            logger.error(error_msg)
            self.error.emit(error_msg)
            
        except MemoryError as e:
            # 内存错误
            error_msg = "内存不足：请尝试减小网格间隔或使用更小的数据集"
            logger.error(error_msg)
            self.error.emit(error_msg)
            
        except Exception as e:
            # 其他错误
            error_msg = f"网格分析过程中发生错误: {str(e)}\n\n详细错误信息:\n{traceback.format_exc()}"
            logger.error(error_msg)
            self.error.emit(error_msg)

    def _validate_parameters(self):
        """验证参数有效性"""
        # 验证数据集
        if self.ds_Sv is None:
            raise ValueError("输入数据集为空")
        
        # 验证表面深度
        if self.surface_depth_m < 0:
            raise ValueError("表面深度不能为负数")
        
        # 验证网格配置
        if "vertical_interval_m" not in self.grid_config:
            raise KeyError("缺少垂直间隔参数 (vertical_interval_m)")
        
        if "horizontal_interval" not in self.grid_config:
            raise KeyError("缺少水平间隔参数 (horizontal_interval)")
        
        if "horizontal_method" not in self.grid_config:
            raise KeyError("缺少水平分段方法参数 (horizontal_method)")
        
        # 验证垂直间隔
        v_interval = self.grid_config["vertical_interval_m"]
        if v_interval <= 0:
            raise ValueError("垂直间隔必须大于0")
        
        # 验证水平间隔
        h_interval = self.grid_config["horizontal_interval"]
        if h_interval <= 0:
            raise ValueError("水平间隔必须大于0")
        
        # 验证水平分段方法
        h_method = self.grid_config["horizontal_method"]
        if h_method not in ["ping", "distance"]:
            raise ValueError("水平分段方法必须是 'ping' 或 'distance'")
        
        # 验证密度配置
        if "ts_default" not in self.density_config:
            raise KeyError("缺少默认目标强度参数 (ts_default)")
        
        if "avg_weight_kg" not in self.density_config:
            raise KeyError("缺少平均体重参数 (avg_weight_kg)")


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
                return path_str, None, "已取消"

            echodata = open_single_file(raw_file, self.config)

            if self._cancelled:
                return path_str, None, "已取消"

            ds_Sv = process_single_file(echodata, self.config)
            return path_str, ds_Sv, ""

        except Exception as e:
            return path_str, None, traceback.format_exc()

    def run(self):
        """并行处理所有文件"""
        total = len(self.raw_files)
        success_count = 0
        error_count = 0

        self.progress.emit(f"开始批量处理 {total} 个文件 (并行度: {self.max_workers})")

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_file = {
                executor.submit(self._process_single_file, rf): rf
                for rf in self.raw_files
            }

            for future in as_completed(future_to_file):
                if self._cancelled:
                    self.progress.emit("批量处理已取消")
                    break

                path_str, ds_Sv, error_msg = future.result()
                raw_file = future_to_file[future]

                if error_msg:
                    error_count += 1
                    self.file_error.emit(path_str, error_msg)
                    self.progress.emit(f"✗ 失败 [{success_count + error_count}/{total}]: {raw_file.name}")
                else:
                    success_count += 1
                    self.file_finished.emit(path_str, ds_Sv)
                    self.progress.emit(f"✓ 完成 [{success_count + error_count}/{total}]: {raw_file.name}")

        self.all_finished.emit(success_count, error_count)
        self.progress.emit(f"批量处理完成: 成功 {success_count}, 失败 {error_count}")


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
            from src.core.quality import check_sv_quality, check_bottom_line

            self.progress.emit("正在检查 Sv 数据质量...")
            sv_result = check_sv_quality(self.ds_Sv)

            bl_result = None
            if self.bottom is not None:
                self.progress.emit("正在检查底线质量...")
                n_samples = self.ds_Sv.sizes.get("range_sample", 0)
                bl_result = check_bottom_line(self.bottom, n_samples)

            self.finished.emit({"sv": sv_result, "bottom": bl_result})

        except Exception as e:
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
            from src.core.multifreq import get_channel_summary, compare_frequencies, list_channels

            self.progress.emit("正在分析通道信息...")
            channel_summary = get_channel_summary(self.ds_Sv)

            channels = list_channels(self.ds_Sv)
            freq_comparison = None
            if len(channels) >= 2:
                self.progress.emit("正在进行多频率对比...")
                freq_comparison = compare_frequencies(self.ds_Sv, self.config, self.channels)
            else:
                self.progress.emit("仅单通道，跳过频率对比")

            self.finished.emit({
                "channel_summary": channel_summary,
                "freq_comparison": freq_comparison,
                "channels": channels,
            })

        except Exception as e:
            self.error.emit(traceback.format_exc())


class SingleTargetWorker(QThread):
    """单体目标检测工作线程

    信号：
    - finished(object): 检测结果 DataFrame
    - error(str): 错误信息
    - progress(str): 进度信息
    """
    finished = Signal(object)
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, ds_Sv, config):
        super().__init__()
        self.ds_Sv = ds_Sv
        self.config = config

    def run(self):
        try:
            from src.core.single_target import detect_and_compute_ts

            self.progress.emit("正在检测单体目标...")
            targets_df = detect_and_compute_ts(self.ds_Sv, self.config)
            self.finished.emit(targets_df)

        except Exception as e:
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
            self.progress.emit("计算 Sv 统计...")
            result = sv_statistics_summary(self.ds_Sv)
            self.finished.emit(result)
        except Exception as e:
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
            from src.core.multifreq import split_transects, get_channel_summary
            self.progress.emit("分段中...")
            transect_ids = split_transects(self.ds_Sv, method=self.method, max_gap_s=self.max_gap_s)
            n_transects = int(transect_ids.max()) + 1 if len(transect_ids) > 0 else 0
            summary = get_channel_summary(self.ds_Sv)
            self.finished.emit({
                "transect_ids": transect_ids,
                "n_transects": n_transects,
                "channel_summary": summary,
            })
        except Exception as e:
            self.error.emit(traceback.format_exc())
    """单体目标检测工作线程

    信号：
    - finished(object): 检测结果 DataFrame
    - error(str): 错误信息
    - progress(str): 进度信息
    """
    finished = Signal(object)
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, ds_Sv, config):
        super().__init__()
        self.ds_Sv = ds_Sv
        self.config = config

    def run(self):
        try:
            from src.core.single_target import detect_and_compute_ts

            self.progress.emit("正在检测单体目标...")
            targets_df = detect_and_compute_ts(self.ds_Sv, self.config)
            self.finished.emit(targets_df)

        except Exception as e:
            self.error.emit(traceback.format_exc())

