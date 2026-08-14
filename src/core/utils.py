"""通用工具：配置加载、日志、路径管理、内存监控

注意：build_analysis_mask 已移至 src.core.region 模块，保留此处的兼容导入。
"""

import logging
import os
from pathlib import Path

import numpy as np
import xarray as xr
import yaml

# 兼容导入：旧代码可能从 utils 导入 build_analysis_mask

# 核心模块统一使用 "fish_acoustics" logger（见项目约定）
logger = logging.getLogger("fish_acoustics")


def squeeze_sv(sv: np.ndarray) -> np.ndarray:
    """将 3D Sv 数组降维为 2D（取第一个 channel）。"""
    if sv.ndim == 3:
        return sv[0]
    return sv


def sv_to_linear(Sv: np.ndarray) -> np.ndarray:
    """将 Sv(dB) 转换为线性值，NaN 位置置零。"""
    linear = 10 ** (Sv / 10)
    return np.where(np.isfinite(linear), linear, 0.0)


def get_sv_array(ds_Sv: xr.Dataset) -> np.ndarray:
    """获取 Sv 2D 数组，优先使用去噪后的 Sv_corrected。

    Returns
    -------
    np.ndarray
        shape=(n_pings, n_samples)
    """
    var = "Sv_corrected" if "Sv_corrected" in ds_Sv else "Sv"
    return squeeze_sv(ds_Sv[var].values)


def get_vertical_coords(ds_Sv: xr.Dataset) -> np.ndarray:
    """获取垂直坐标（depth 优先，fallback 到 echo_range → range_sample）。

    Returns
    -------
    np.ndarray
        1D 垂直坐标数组，shape=(n_samples,)
    """
    range_sample = ds_Sv["range_sample"].values

    if "depth" in ds_Sv:
        depth_data = ds_Sv["depth"]
        if "channel" in depth_data.dims:
            depth_data = depth_data.isel(channel=0)
        coords = depth_data.isel(ping_time=0).values
    elif "echo_range" in ds_Sv:
        echo_data = ds_Sv["echo_range"]
        if "channel" in echo_data.dims:
            echo_data = echo_data.isel(channel=0)
        coords = echo_data.isel(ping_time=0).values
    else:
        logger.warning("数据集中无 depth/echo_range，使用 range_sample 作为 fallback（单位为 sample index，非米）")
        coords = range_sample.astype(float)

    if np.any(np.isnan(coords)):
        valid_mask = ~np.isnan(coords)
        if np.any(valid_mask):
            valid_indices = np.where(valid_mask)[0]
            coords = np.interp(
                np.arange(len(coords)),
                valid_indices,
                coords[valid_mask],
            )
        else:
            coords = range_sample.astype(float)

    return coords


def load_config(config_path: str) -> dict:
    """加载 YAML 配置文件"""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def validate_config(config: dict) -> None:
    """验证配置文件必要字段"""
    required = ["reservoir", "input", "processing", "output"]
    for key in required:
        if key not in config:
            raise ValueError(f"配置文件缺少必要字段: {key}")

    # 验证 input
    input_cfg = config["input"]
    if "raw_dir" not in input_cfg:
        raise ValueError("配置缺少 input.raw_dir")

    # 验证 output
    output_cfg = config["output"]
    if "dir" not in output_cfg:
        raise ValueError("配置缺少 output.dir")


def setup_logging(reservoir_name: str, output_dir: str) -> logging.Logger:
    """设置日志"""
    log_dir = Path(output_dir) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("fish_acoustics")

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    # 文件处理器
    fh = logging.FileHandler(log_dir / f"{reservoir_name}.log", encoding="utf-8")
    fh.setLevel(logging.INFO)

    # 控制台处理器
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)

    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger


def get_output_dir(config: dict) -> Path:
    """获取输出目录并创建"""
    output_dir = Path(config["output"]["dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


# ── 内存监控 ──────────────────────────────────────────────

def get_memory_usage() -> dict:
    """获取当前进程内存使用情况。

    Returns
    -------
    dict
        - rss_mb: 物理内存使用 (MB)
        - vms_mb: 虚拟内存使用 (MB)
        - percent: 内存使用百分比
    """
    try:
        import psutil
        process = psutil.Process(os.getpid())
        mem = process.memory_info()
        return {
            "rss_mb": mem.rss / 1024 / 1024,
            "vms_mb": mem.vms / 1024 / 1024,
            "percent": process.memory_percent(),
        }
    except ImportError:
        # psutil 不可用时返回 0（无数据，不伪造）
        return {
            "rss_mb": 0.0,
            "vms_mb": 0.0,
            "percent": 0.0,
        }


def log_memory_usage(label: str = "") -> None:
    """记录内存使用情况到日志。"""
    mem = get_memory_usage()
    logger.info(
        f"[内存{f' {label}' if label else ''}] "
        f"RSS: {mem['rss_mb']:.1f} MB, "
        f"VMS: {mem['vms_mb']:.1f} MB, "
        f"占比: {mem['percent']:.1f}%"
    )


def optimize_array_dtype(arr: np.ndarray, target_dtype=np.float32) -> np.ndarray:
    """优化数组数据类型以减少内存占用。

    Parameters
    ----------
    arr : np.ndarray
        输入数组
    target_dtype : np.dtype
        目标数据类型，默认 float32

    Returns
    -------
    np.ndarray
        转换后的数组
    """
    if arr.dtype == target_dtype:
        return arr
    if np.issubdtype(arr.dtype, np.floating):
        return arr.astype(target_dtype)
    return arr
