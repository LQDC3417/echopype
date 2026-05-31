"""声学处理模块：raw → Sv → 噪声去除 → 底部检测"""

import logging
import os

# 修复 echopype 在 Windows 中文环境的 YAML 编码问题
os.environ["PYTHONUTF8"] = "1"

from pathlib import Path
from typing import List

import numpy as np
import xarray as xr

logger = logging.getLogger("fish_acoustics")


def load_raw_files(config: dict) -> List[Path]:
    """加载 raw 文件列表"""
    raw_dir = Path(config["input"]["raw_dir"])
    pattern = config["input"].get("pattern", "*.raw")

    if not raw_dir.exists():
        raise FileNotFoundError(f"raw 目录不存在: {raw_dir}")

    files = sorted(raw_dir.glob(pattern))
    if not files:
        raise FileNotFoundError(f"未找到匹配 {pattern} 的文件: {raw_dir}")

    logger.info(f"找到 {len(files)} 个 raw 文件")
    return files


def process_single_file(
    raw_file: Path,
    config: dict,
) -> xr.Dataset:
    """
    处理单个 raw 文件的完整流程：
    1. open_raw — 读取文件
    2. compute_Sv — 计算体积反向散射强度
    3. remove_background_noise — 噪声去除
    4. detect_seafloor — 底部检测
    """
    import echopype as ep
    from echopype.calibrate import compute_Sv
    from echopype.clean import remove_background_noise
    from echopype.mask import detect_seafloor

    proc_cfg = config["processing"]

    # 1. 读取 raw 文件
    logger.info(f"读取文件: {raw_file.name}")
    echodata = ep.open_raw(
        raw_file=str(raw_file),
        sonar_model="EK80",
    )

    # 2. 计算 Sv
    logger.info("计算 Sv...")
    waveform_mode = proc_cfg.get("waveform_mode", "CW")
    encode_mode = proc_cfg.get("encode_mode", "power")
    ds_Sv = compute_Sv(
        echodata,
        waveform_mode=waveform_mode,
        encode_mode=encode_mode,
    )

    # 3. 噪声去除
    noise_cfg = proc_cfg.get("noise_removal", {})
    logger.info("去除背景噪声...")
    ds_Sv = remove_background_noise(
        ds_Sv,
        ping_num=noise_cfg.get("ping_num", 5),
        range_sample_num=noise_cfg.get("range_sample_num", 10),
        SNR_threshold=noise_cfg.get("SNR_threshold", "3.0dB"),
    )

    # 4. 底部检测
    bottom_cfg = proc_cfg.get("bottom_detection", {})
    logger.info("检测底部...")
    channel = str(ds_Sv["channel"].values[0])
    bottom_params = {
        "var_name": "Sv",
        "channel": channel,
        "threshold": bottom_cfg.get("threshold", -50.0),
        "offset_m": bottom_cfg.get("offset_m", 0.5),
        "bin_skip_from_surface": bottom_cfg.get("bin_skip_from_surface", 200),
    }
    bottom_depth = detect_seafloor(
        ds_Sv,
        method=bottom_cfg.get("method", "basic"),
        params=bottom_params,
    )
    ds_Sv["bottom_depth"] = bottom_depth

    logger.info(f"处理完成: {raw_file.name}")
    return ds_Sv


def process_all_files(config: dict) -> xr.Dataset:
    """处理所有 raw 文件并合并"""
    raw_files = load_raw_files(config)

    datasets = []
    for raw_file in raw_files:
        try:
            ds = process_single_file(raw_file, config)
            datasets.append(ds)
        except Exception as e:
            logger.error(f"处理失败 {raw_file.name}: {e}")
            continue

    if not datasets:
        raise RuntimeError("所有文件处理失败")

    # 合并数据集
    if len(datasets) > 1:
        import echopype as ep
        combined = ep.combine_echodata(datasets)
        return combined
    return datasets[0]
