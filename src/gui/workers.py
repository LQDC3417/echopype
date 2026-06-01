"""后台处理工作线程"""

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
            self.error.emit(str(e))


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
            from src.core.acoustic import process_single_file
            self.progress.emit("计算 Sv...")
            ds_Sv = process_single_file(self.echodata, self.config)
            self.finished.emit(ds_Sv)
        except Exception as e:
            self.error.emit(str(e))


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
            if "Sv_corrected" in ds:
                ds["Sv"] = ds["Sv_corrected"]
            self.finished.emit(ds)
        except Exception as e:
            self.error.emit(str(e))


class DetectSeafloorWorker(QThread):
    """底部检测"""
    finished = Signal(object)  # xr.DataArray
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, ds_Sv, config: dict):
        super().__init__()
        self.ds_Sv = ds_Sv
        self.config = config

    def run(self):
        try:
            from echopype.mask import detect_seafloor
            bottom_cfg = self.config.get("processing", {}).get("bottom_detection", {})
            channel = str(self.ds_Sv["channel"].values[0])
            self.progress.emit("检测底部...")
            params = {
                "var_name": "Sv",
                "channel": channel,
                "threshold": bottom_cfg.get("threshold", -50.0),
                "offset_m": bottom_cfg.get("offset_m", 0.5),
                "bin_skip_from_surface": bottom_cfg.get("bin_skip_from_surface", 200),
            }
            bottom = detect_seafloor(
                self.ds_Sv,
                method=bottom_cfg.get("method", "basic"),
                params=params,
            )
            self.finished.emit(bottom)
        except Exception as e:
            self.error.emit(str(e))


class DetectSchoolsWorker(QThread):
    """鱼群检测"""
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
            self.error.emit(str(e))


class DensityWorker(QThread):
    """密度估算"""
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
            self.error.emit(str(e))
