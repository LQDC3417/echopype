"""后台处理工作线程"""

import traceback
import numpy as np
from PySide6.QtCore import QThread, Signal
from pathlib import Path


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

            bottom_depth_np = bottom_depth_m.values
            if bottom_depth_np.ndim > 1:
                bottom_depth_np = bottom_depth_np[:, 0]

            bottom_indices = bottom_depth_to_sample_indices(bottom_depth_np, er)
            self.finished.emit(bottom_indices)
        except Exception as e:
            self.error.emit(traceback.format_exc())


class DetectSchoolsWorker(QThread):
    """鱼群检测（ds_Sv 已由 MainWindow 按分析区域裁剪）"""
    finished = Signal(object, object)  # mask, DataFrame
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, ds_Sv, config: dict):
        super().__init__()
        self.ds_Sv = ds_Sv
        self.config = config

    def run(self):
        try:
            from src.core.school import detect_schools, schools_to_dataframe
            self.progress.emit("检测鱼群...")
            mask = detect_schools(self.ds_Sv, self.config)
            df = schools_to_dataframe(mask, self.ds_Sv)
            self.finished.emit(mask, df)
        except Exception as e:
            self.error.emit(traceback.format_exc())


class DensityWorker(QThread):
    """密度估算（ds_Sv 已由 MainWindow 按分析区域裁剪）"""
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
    """网格化分析"""
    finished = Signal(object)  # DataFrame
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, ds_Sv, surface_depth_m, grid_config, density_config):
        super().__init__()
        self.ds_Sv = ds_Sv
        self.surface_depth_m = surface_depth_m
        self.grid_config = grid_config
        self.density_config = density_config

    def run(self):
        try:
            from src.core.grid import create_grid, compute_grid_density
            self.progress.emit("创建网格...")
            grid_cells = create_grid(
                self.ds_Sv,
                surface_depth_m=self.surface_depth_m,
                vertical_interval_m=self.grid_config["vertical_interval_m"],
                horizontal_interval=self.grid_config["horizontal_interval"],
                method=self.grid_config["horizontal_method"],
            )
            self.progress.emit("计算网格统计...")
            config = {"density": self.density_config}
            df = compute_grid_density(self.ds_Sv, grid_cells, config)
            self.finished.emit(df)
        except Exception as e:
            self.error.emit(traceback.format_exc())
