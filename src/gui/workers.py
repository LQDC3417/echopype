"""后台处理工作线程"""

import traceback
from PySide6.QtCore import QThread, Signal
from pathlib import Path


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
            import numpy as np
            from echopype.clean import remove_background_noise
            noise_cfg = self.config.get("processing", {}).get("noise_removal", {})
            self.progress.emit("去除背景噪声...")
            ds = remove_background_noise(
                self.ds_Sv,
                ping_num=noise_cfg.get("ping_num", 5),
                range_sample_num=noise_cfg.get("range_sample_num", 10),
                SNR_threshold=noise_cfg.get("SNR_threshold", "3.0dB"),
            )
            # 应用手动框选的噪声 mask（写入 Sv_corrected，不覆盖原始 Sv）
            if self.manual_mask is not None:
                target = ds["Sv_corrected"] if "Sv_corrected" in ds else ds["Sv"]
                sv_arr = target.values.copy()
                if sv_arr.ndim == 3:
                    sv_arr = sv_arr[0]
                if self.manual_mask.shape == sv_arr.shape:
                    sv_arr[self.manual_mask] = np.nan
                    if target.ndim == 3:
                        target.values[0, :, :] = sv_arr
                    else:
                        target.values[:] = sv_arr
                    if "Sv_corrected" not in ds:
                        ds["Sv_corrected"] = target

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
            import numpy as np
            from echopype.mask import detect_seafloor

            bottom_cfg = self.config.get("processing", {}).get("bottom_detection", {})
            threshold = bottom_cfg.get("threshold", -50.0)
            offset_m = bottom_cfg.get("offset_m", 0.5)
            bin_skip = bottom_cfg.get("bin_skip_from_surface", 200)
            method = bottom_cfg.get("method", "basic")

            ds = self.ds_Sv
            # 优先使用去噪后的数据
            var_name = "Sv_corrected" if "Sv_corrected" in ds else "Sv"
            sv_arr = ds[var_name].values
            if sv_arr.ndim == 3:
                sv_arr = sv_arr[0]
            n_pings, n_samples = sv_arr.shape

            channel = str(ds["channel"].values[0]) if "channel" in ds else None

            # ── 调用 echopype API 获取真实水深(m) ──
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

            # ── 将水深(m)转为 sample index ──
            if "echo_range" in ds:
                echo_range = ds["echo_range"]
                if "channel" in echo_range.dims:
                    echo_range = echo_range.isel(channel=0)
                er = echo_range.values
                if er.ndim == 2:
                    er = er[0] if er.shape[0] == 1 else er[:, 0]
            else:
                er = np.arange(n_samples, dtype=float)

            bottom_depth_np = bottom_depth_m.values
            bottom_indices = np.full(n_pings, np.nan, dtype=np.float32)
            for i in range(n_pings):
                bd = bottom_depth_np[i] if bottom_depth_np.ndim == 1 else bottom_depth_np[i, 0]
                if np.isnan(bd) or bd <= 0:
                    continue
                idx = np.searchsorted(er, bd)
                idx = max(0, min(n_samples - 1, idx))
                bottom_indices[i] = float(idx)

            self.finished.emit(bottom_indices)
        except Exception as e:
            self.error.emit(traceback.format_exc())


class DetectSchoolsWorker(QThread):
    """鱼群检测"""
    finished = Signal(object, object)  # mask, DataFrame
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, ds_Sv, config: dict,
                 surface_sample: float | None = None,
                 bottom_line=None):
        super().__init__()
        self.ds_Sv = ds_Sv
        self.config = config
        self.surface_sample = surface_sample
        self.bottom_line = bottom_line

    def run(self):
        try:
            from src.core.school import detect_schools, schools_to_dataframe
            self.progress.emit("检测鱼群...")
            mask = detect_schools(
                self.ds_Sv, self.config,
                surface_sample=self.surface_sample,
                bottom_line=self.bottom_line,
            )
            df = schools_to_dataframe(mask, self.ds_Sv)
            self.finished.emit(mask, df)
        except Exception as e:
            self.error.emit(traceback.format_exc())


class DensityWorker(QThread):
    """密度估算"""
    finished = Signal(object)  # DataFrame
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, schools_df, ds_Sv, config: dict,
                 surface_sample: float | None = None,
                 bottom_line=None):
        super().__init__()
        self.schools_df = schools_df
        self.ds_Sv = ds_Sv
        self.config = config
        self.surface_sample = surface_sample
        self.bottom_line = bottom_line

    def run(self):
        try:
            from src.core.density import estimate_density
            self.progress.emit("计算密度...")
            df = estimate_density(
                self.schools_df, self.ds_Sv, self.config,
                surface_sample=self.surface_sample,
                bottom_line=self.bottom_line,
            )
            self.finished.emit(df)
        except Exception as e:
            self.error.emit(traceback.format_exc())
