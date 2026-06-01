"""声学处理模块：raw → Sv → 噪声去除 → 底部检测"""

import logging
import os

# 修复 echopype 在 Windows 中文环境的 YAML 编码问题
os.environ["PYTHONUTF8"] = "1"

from pathlib import Path
from typing import List

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


def open_single_file(raw_file: Path, config: dict):
    """
    打开单个 raw 文件，返回 EchoData 对象。

    Returns
    -------
    echopype.EchoData
    """
    import echopype as ep

    sonar_model = config.get("processing", {}).get("sonar_model", "EK80")
    logger.info(f"读取文件: {raw_file.name} (sonar_model={sonar_model})")

    echodata = ep.open_raw(
        raw_file=str(raw_file),
        sonar_model=sonar_model,
    )
    return echodata


def _detect_waveform_mode(echodata) -> tuple:
    """
    从 EchoData 自动检测 waveform_mode 和 encode_mode。

    Returns
    -------
    (waveform_mode, encode_mode) : (str, str)
        waveform_mode: "CW" 或 "BB"
        encode_mode: "complex" 或 "power"
    """
    try:
        bg = echodata["Sonar/Beam_group1"]

        # 检测 transmit_type: "CW" → narrowband, "FM"/"BB" → broadband
        transmit_type = bg["transmit_type"].values
        if transmit_type.ndim > 1:
            transmit_type = transmit_type[0]  # 取第一个 channel
        first_type = str(transmit_type.flat[0]).upper() if transmit_type.size > 0 else "CW"

        if first_type in ("FM", "BB"):
            waveform_mode = "BB"
        else:
            waveform_mode = "CW"

        # 检测 beam_type: 1=complex, 3=power/angle
        beam_type = int(bg["beam_type"].values[0]) if "beam_type" in bg else 1
        encode_mode = "complex" if beam_type == 1 else "power"

        logger.info(f"自动检测: waveform_mode={waveform_mode}, encode_mode={encode_mode}")
        return waveform_mode, encode_mode

    except Exception as e:
        logger.warning(f"自动检测失败，使用默认值 CW/power: {e}")
        return "CW", "power"


def _add_depth(ds_Sv: xr.Dataset, echodata) -> xr.Dataset:
    """
    使用 echopype.consolidate.add_depth 计算真实水深。

    depth = echo_range + transducer_depth (从 Platform group 自动获取)
    """
    if "depth" in ds_Sv:
        return ds_Sv

    from echopype.consolidate import add_depth

    ds_Sv = add_depth(
        ds_Sv,
        echodata=echodata,
        use_platform_vertical_offsets=True,
    )
    logger.info("depth 计算完成 (使用 Platform vertical offsets)")
    return ds_Sv


def process_single_file(echodata, config: dict) -> xr.Dataset:
    """
    处理单个 EchoData 对象的完整流程：
    1. compute_Sv — 计算体积反向散射强度
    2. remove_background_noise — 噪声去除
    3. depth — 计算真实水深
    4. detect_seafloor — 底部检测

    Parameters
    ----------
    echodata : echopype.EchoData
        由 open_raw 或 open_single_file 返回的 EchoData 对象
    config : dict
        配置字典

    Returns
    -------
    xr.Dataset
        包含 Sv、depth、bottom_depth 的数据集
    """
    from echopype.calibrate import compute_Sv
    from echopype.clean import remove_background_noise
    from echopype.mask import detect_seafloor

    proc_cfg = config["processing"]

    # 1. 计算 Sv（自动检测 CW/BB 和 complex/power）
    logger.info("计算 Sv...")
    waveform_mode, encode_mode = _detect_waveform_mode(echodata)
    ds_Sv = compute_Sv(
        echodata,
        waveform_mode=waveform_mode,
        encode_mode=encode_mode,
    )

    # 2. 噪声去除
    noise_cfg = proc_cfg.get("noise_removal", {})
    logger.info("去除背景噪声...")
    ds_Sv = remove_background_noise(
        ds_Sv,
        ping_num=noise_cfg.get("ping_num", 5),
        range_sample_num=noise_cfg.get("range_sample_num", 10),
        SNR_threshold=noise_cfg.get("SNR_threshold", "3.0dB"),
    )
    # 使用校正后的 Sv 替换原始 Sv
    if "Sv_corrected" in ds_Sv:
        ds_Sv["Sv"] = ds_Sv["Sv_corrected"]
        logger.info("已使用 Sv_corrected 替换 Sv")

    # 3. 计算真实水深
    ds_Sv = _add_depth(ds_Sv, echodata)

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

    logger.info("处理完成")
    return ds_Sv


def process_all_files(config: dict) -> xr.Dataset:
    """处理所有 raw 文件并合并。

    流程：open_raw → combine_echodata → compute_Sv + noise + depth + seafloor
    """
    import echopype as ep

    raw_files = load_raw_files(config)

    # 1. 打开所有 raw 文件，得到 EchoData 列表
    echodata_list = []
    for raw_file in raw_files:
        try:
            ed = open_single_file(raw_file, config)
            echodata_list.append(ed)
        except Exception as e:
            logger.error(f"打开文件失败 {raw_file.name}: {e}")
            continue

    if not echodata_list:
        raise RuntimeError("所有文件打开失败")

    # 2. 合并 EchoData 对象（如有多个文件）
    if len(echodata_list) > 1:
        logger.info(f"合并 {len(echodata_list)} 个 EchoData 对象...")
        combined_ed = ep.combine_echodata(echodata_list=echodata_list)
    else:
        combined_ed = echodata_list[0]

    # 3. 校准 + 噪声去除 + 深度 + 底部检测
    ds_Sv = process_single_file(combined_ed, config)
    return ds_Sv
