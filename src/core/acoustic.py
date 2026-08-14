"""声学处理模块：raw → Sv → 噪声去除 → 底部检测"""

import logging
import os

# 修复 echopype 在 Windows 中文环境的 YAML 编码问题
os.environ["PYTHONUTF8"] = "1"

from pathlib import Path

import xarray as xr

logger = logging.getLogger("fish_acoustics")


def load_raw_files(config: dict) -> list[Path]:
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


def compute_sv(echodata, config: dict) -> xr.Dataset:
    """
    计算 Sv 并添加深度信息（不做噪声去除和底部检测）。

    处理流程：
    1. compute_Sv — 计算体积反向散射强度
    2. add_depth — 计算真实水深（几何量，与噪声无关）

    Parameters
    ----------
    echodata : echopype.EchoData
    config : dict

    Returns
    -------
    xr.Dataset
        包含 Sv 和 depth 的数据集
    """
    from echopype.calibrate import compute_Sv as ep_compute_Sv

    logger.info("计算 Sv...")
    waveform_mode, encode_mode = _detect_waveform_mode(echodata)
    ds_Sv = ep_compute_Sv(
        echodata,
        waveform_mode=waveform_mode,
        encode_mode=encode_mode,
    )

    # 深度是几何量，应在噪声去除前独立计算
    ds_Sv = _add_depth(ds_Sv, echodata)

    logger.info("Sv + depth 计算完成")
    return ds_Sv


def process_single_file(echodata, config: dict) -> xr.Dataset:
    """
    处理单个 EchoData 对象的完整流程（供 CLI 和批量导入使用）：
    1. compute_Sv + depth
    2. remove_background_noise — 噪声去除
    3. detect_seafloor — 底部检测

    关键原则：Sv 原始数据永不覆盖，去噪结果存入 Sv_corrected。
    下游操作（底部检测等）优先使用 Sv_corrected。

    Parameters
    ----------
    echodata : echopype.EchoData
    config : dict

    Returns
    -------
    xr.Dataset
        包含 Sv、Sv_corrected（如有）、depth、bottom_depth 的数据集
    """
    from echopype.clean import remove_background_noise

    proc_cfg = config["processing"]

    # 1. 计算 Sv + depth
    ds_Sv = compute_sv(echodata, config)

    # 2. 噪声去除（Sv 原始数据保留，去噪结果存入 Sv_corrected）
    noise_cfg = proc_cfg.get("noise_removal", {})
    logger.info("去除背景噪声...")
    ds_Sv = remove_background_noise(
        ds_Sv,
        ping_num=noise_cfg.get("ping_num", 5),
        range_sample_num=noise_cfg.get("range_sample_num", 10),
        SNR_threshold=noise_cfg.get("SNR_threshold", "3.0dB"),
    )
    if "Sv_corrected" in ds_Sv:
        logger.info("噪声去除完成，Sv_corrected 已生成（原始 Sv 保留）")

    # 3. 底部检测（优先使用去噪后的数据）
    from src.core.bottom_detection import detect_bottom

    bottom_cfg = proc_cfg.get("bottom_detection", {})
    bottom_method = bottom_cfg.get("method", "basic")
    logger.info(f"检测底部 (方法={bottom_method})...")

    # 调用统一底部检测接口
    bottom_depth = detect_bottom(
        ds_Sv,
        method=bottom_method,
        offset_m=bottom_cfg.get("offset_m", 0.5),
        # basic 方法参数
        threshold=bottom_cfg.get("threshold", -50.0),
        bin_skip_from_surface=bottom_cfg.get("bin_skip_from_surface", 200),
        # enhanced 方法参数
        peak_threshold=bottom_cfg.get("peak_threshold", -40.0),
        discrimination_threshold=bottom_cfg.get("discrimination_threshold", -50.0),
        saturation_threshold=bottom_cfg.get("saturation_threshold", -60.0),
        validation_window=bottom_cfg.get("validation_window", 15),
        validation_threshold=bottom_cfg.get("validation_threshold", 3.0),
        smoothing_window=bottom_cfg.get("smoothing_window", 11),
        # afsc 方法参数
        search_min=bottom_cfg.get("search_min", 10.0),
        window_len=bottom_cfg.get("window_len", 11),
        backstep=bottom_cfg.get("backstep", 35.0),
    )
    ds_Sv["bottom_depth"] = ("ping_time", bottom_depth)

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
