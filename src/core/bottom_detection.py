"""增强底部检测模块：多种算法支持

参考：
- Matecho BottomDetectionMatecho.m：双阈值检测 + 相关性验证
- pyEcholab afsc_bot_detector.py：平滑处理 + echo envelope 检测

功能：
- basic：基础阈值检测（保留原有实现）
- enhanced：增强检测（平滑 + 双阈值 + 相关性验证）
- afsc：AFSC 算法（Hanning 平滑 + echo envelope）
"""

import logging
from collections.abc import Callable
from enum import Enum

import numpy as np
import xarray as xr
from scipy.signal import windows

from src.core.utils import get_sv_array, get_vertical_coords

logger = logging.getLogger("fish_acoustics")


class BottomMethod(Enum):
    """底部检测方法枚举"""
    BASIC = "basic"
    ENHANCED = "enhanced"
    AFSC = "afsc"


def _smooth_ping(ping: np.ndarray, window_len: int = 11, window_type: str = "hanning") -> np.ndarray:
    """平滑单个 ping 数据

    Parameters
    ----------
    ping : np.ndarray
        1D 数组，单个 ping 的 Sv 数据
    window_len : int
        窗口长度（奇数）
    window_type : str
        窗口类型："hanning" 或 "hamming"

    Returns
    -------
    np.ndarray
        平滑后的数据
    """
    if window_len < 3:
        return ping.copy()

    # 确保窗口长度为奇数
    if window_len % 2 == 0:
        window_len += 1

    # 创建窗口
    if window_type == "hanning":
        win = windows.hann(window_len)
    elif window_type == "hamming":
        win = windows.hamming(window_len)
    else:
        win = windows.hann(window_len)

    # 归一化
    win = win / win.sum()

    # 处理 NaN
    ping_filled = np.copy(ping)
    nan_mask = np.isnan(ping_filled)
    if np.all(nan_mask):
        return ping.copy()
    ping_filled[nan_mask] = np.nanmean(ping)

    # 卷积平滑
    smoothed = np.convolve(win, ping_filled, mode='same')

    # 恢复 NaN
    smoothed[nan_mask] = np.nan

    return smoothed


def _find_echo_envelope(
    ping: np.ndarray,
    peak_idx: int,
    threshold: float,
    search_min_idx: int,
    contiguous: bool = True,
) -> float | None:
    """找 echo envelope 的近边（底部位置）

    Parameters
    ----------
    ping : np.ndarray
        平滑后的 ping 数据
    peak_idx : int
        峰值位置索引
    threshold : float
        阈值 = peak_value - backstep
    search_min_idx : int
        最小搜索索引（避开 ringdown）
    contiguous : bool
        是否要求连续

    Returns
    -------
    float or None
        底部位置（插值后的索引），未找到返回 None
    """
    try:
        if peak_idx <= search_min_idx:
            return None

        # 从峰值向近场搜索
        near_envelope_samples = []
        for idx in range(peak_idx, search_min_idx - 1, -1):
            if ping[idx] > threshold:
                near_envelope_samples.append(idx)
            elif contiguous and near_envelope_samples:
                break

        if not near_envelope_samples:
            return None

        # 找到第一个低于阈值的点（近边）
        near_idx = near_envelope_samples[-1]

        # 插值提高精度
        if near_idx > 0 and near_idx < len(ping) - 1:
            # 找到阈值穿越点
            if ping[near_idx - 1] < threshold:
                # 线性插值
                frac = (threshold - ping[near_idx - 1]) / (ping[near_idx] - ping[near_idx - 1])
                return near_idx - 1 + frac

        return float(near_idx)

    except Exception:
        return None


def detect_bottom_basic(
    ds_Sv: xr.Dataset,
    threshold: float = -40.0,
    offset_m: float = 0.5,
    bin_skip_from_surface: int = 200,
) -> np.ndarray:
    """基础底部检测（当前实现）

    Parameters
    ----------
    ds_Sv : xr.Dataset
        Sv 数据集
    threshold : float
        阈值 (dB)
    offset_m : float
        底部偏移 (米)
    bin_skip_from_surface : int
        跳过表面样本数

    Returns
    -------
    np.ndarray
        底部深度数组 (米)，shape=(n_pings,)
    """
    from echopype.mask import detect_seafloor

    var_name = "Sv_corrected" if "Sv_corrected" in ds_Sv else "Sv"
    channel = str(ds_Sv["channel"].values[0])

    bottom_params = {
        "var_name": var_name,
        "channel": channel,
        "threshold": threshold,
        "offset_m": offset_m,
        "bin_skip_from_surface": bin_skip_from_surface,
    }

    bottom_depth = detect_seafloor(
        ds_Sv,
        method="basic",
        params=bottom_params,
    )

    return bottom_depth.values


def detect_bottom_enhanced(
    ds_Sv: xr.Dataset,
    peak_threshold: float = -40.0,
    discrimination_threshold: float = -50.0,
    saturation_threshold: float = -60.0,
    validation_window: int = 15,
    validation_threshold: float = 3.0,
    smoothing_window: int = 11,
    offset_m: float = 0.5,
    progress_callback: Callable[[int, int], None] | None = None,
) -> np.ndarray:
    """增强底部检测（参考 Matecho）

    算法流程：
    1. 平滑处理（Hanning 窗口）
    2. 表面饱和去除
    3. 找超过峰值阈值的 Sv 极大值
    4. 从极大值回溯找判别阈值穿越点
    5. 相关性验证（std15）

    Parameters
    ----------
    ds_Sv : xr.Dataset
        Sv 数据集
    peak_threshold : float
        峰值阈值 (dB)，默认 -40
    discrimination_threshold : float
        判别阈值 (dB)，默认 -50
    saturation_threshold : float
        饱和阈值 (dB)，默认 -60
    validation_window : int
        相关性验证窗口大小（前 N 个 ping），默认 15
    validation_threshold : float
        相关性验证倍数，默认 3.0
    smoothing_window : int
        平滑窗口长度，默认 11
    offset_m : float
        底部偏移 (米)
    progress_callback : callable, optional
        进度回调函数

    Returns
    -------
    np.ndarray
        底部深度数组 (米)，shape=(n_pings,)
    """
    Sv = get_sv_array(ds_Sv)  # (n_pings, n_samples)
    depth = get_vertical_coords(ds_Sv)  # (n_samples,)
    n_pings, _n_samples = Sv.shape

    # 计算深度分辨率
    if len(depth) > 1:
        depth_res = float(np.median(np.abs(np.diff(depth))))
    else:
        depth_res = 0.1

    # 初始化底部深度数组
    bottom_depth = np.full(n_pings, np.nan)
    relevance = np.zeros(n_pings, dtype=int)  # 0=无效, 1=有效

    for ping_idx in range(n_pings):
        sv_ping = Sv[ping_idx, :]

        # 跳过全 NaN 的 ping
        if np.all(np.isnan(sv_ping)):
            continue

        # 1. 平滑处理
        sv_smoothed = _smooth_ping(sv_ping, window_len=smoothing_window)

        # 2. 表面饱和去除
        sat_mask = sv_smoothed <= saturation_threshold
        if np.any(sat_mask):
            first_sat = np.where(sat_mask)[0][0]
            sv_smoothed[:first_sat] = np.nan

        # 3. 找超过峰值阈值的极大值
        # 简化：找第一个超过峰值阈值的点
        above_peak = np.where(sv_smoothed >= peak_threshold)[0]

        if len(above_peak) == 0:
            # 没有超过峰值阈值的点
            continue

        # 取最深的超过阈值的点（通常是底部）
        peak_idx = above_peak[-1]

        # 4. 从峰值回溯找判别阈值穿越点
        bottom_idx = None
        for idx in range(peak_idx, -1, -1):
            if np.isnan(sv_smoothed[idx]):
                continue
            if sv_smoothed[idx] <= discrimination_threshold:
                # 找到了判别阈值穿越点
                # 继续向前找连续低于阈值的区域
                contiguous_count = 0
                for check_idx in range(idx, max(idx - 3, -1), -1):
                    if np.isnan(sv_smoothed[check_idx]) or sv_smoothed[check_idx] <= discrimination_threshold:
                        contiguous_count += 1
                    else:
                        break
                if contiguous_count >= 1:
                    bottom_idx = idx
                    break

        if bottom_idx is None:
            # 没找到判别阈值，使用峰值位置
            bottom_idx = peak_idx

        # 记录底部深度
        bottom_depth[ping_idx] = depth[bottom_idx] + offset_m

        # 5. 相关性验证（std15）
        if ping_idx > 0:
            # 计算前 validation_window 个 ping 的底部深度标准差
            start_idx = max(0, ping_idx - validation_window)
            prev_bottoms = bottom_depth[start_idx:ping_idx]
            valid_prev = prev_bottoms[np.isfinite(prev_bottoms)]

            if len(valid_prev) > 1:
                std_prev = np.std(valid_prev)
                # 确保标准差不小于 2 倍深度分辨率
                std_prev = max(std_prev, 2 * depth_res)

                # 验证当前底部与前一个的差异
                prev_bottom = bottom_depth[ping_idx - 1]
                if np.isfinite(prev_bottom):
                    diff = abs(bottom_depth[ping_idx] - prev_bottom)
                    if diff <= validation_threshold * std_prev:
                        relevance[ping_idx] = 1  # 有效
                    else:
                        # 差异过大，标记为无效
                        relevance[ping_idx] = 0
                        # 可选：使用前一个有效值
                        # bottom_depth[ping_idx] = prev_bottom
                else:
                    relevance[ping_idx] = 1  # 前一个无效，保留当前
            else:
                relevance[ping_idx] = 1  # 数据不足，保留
        else:
            relevance[ping_idx] = 1  # 第一个 ping

        if progress_callback:
            progress_callback(ping_idx + 1, n_pings)

    # 统计
    n_valid = int(np.sum(relevance))
    n_total = n_pings
    logger.info(f"增强底部检测完成: {n_valid}/{n_total} 个 ping 有效 ({100*n_valid/n_total:.1f}%)")
    logger.info(f"  参数: peak={peak_threshold}dB, disc={discrimination_threshold}dB, "
                f"sat={saturation_threshold}dB, window={validation_window}")

    return bottom_depth


def detect_bottom_afsc(
    ds_Sv: xr.Dataset,
    search_min: float = 10.0,
    window_len: int = 11,
    backstep: float = 35.0,
    offset_m: float = 0.5,
    progress_callback: Callable[[int, int], None] | None = None,
) -> np.ndarray:
    """AFSC 底部检测算法（参考 pyEcholab）

    算法流程：
    1. 平滑处理（Hanning 窗口）
    2. 找到超过最小检测深度的最大 Sv
    3. 计算阈值 = max_Sv - backstep
    4. 回溯找 echo envelope 的近边

    Parameters
    ----------
    ds_Sv : xr.Dataset
        Sv 数据集
    search_min : float
        最小检测深度 (米)，避开 ringdown
    window_len : int
        Hanning 窗口长度
    backstep : float
        回步值 (dB)
    offset_m : float
        底部偏移 (米)
    progress_callback : callable, optional
        进度回调函数

    Returns
    -------
    np.ndarray
        底部深度数组 (米)，shape=(n_pings,)
    """
    Sv = get_sv_array(ds_Sv)  # (n_pings, n_samples)
    depth = get_vertical_coords(ds_Sv)  # (n_samples,)
    n_pings, n_samples = Sv.shape

    # 初始化底部深度数组
    bottom_depth = np.full(n_pings, np.nan)

    # 找到最小检测深度对应的索引
    search_min_idx = np.searchsorted(depth, search_min)

    for ping_idx in range(n_pings):
        sv_ping = Sv[ping_idx, :]

        # 跳过全 NaN 的 ping
        if np.all(np.isnan(sv_ping)):
            continue

        # 检查是否有数据超过最小深度
        if search_min_idx >= n_samples:
            continue

        # 1. 平滑处理
        sv_smoothed = _smooth_ping(sv_ping, window_len=window_len)

        # 2. 找到超过最小深度的最大 Sv
        sv_beyond_min = sv_smoothed[search_min_idx:]
        valid_beyond = sv_beyond_min[np.isfinite(sv_beyond_min)]

        if len(valid_beyond) == 0:
            continue

        max_Sv = np.max(valid_beyond)
        max_idx_local = np.nanargmax(sv_beyond_min)
        max_idx = max_idx_local + search_min_idx

        # 3. 计算阈值
        threshold = max_Sv - backstep

        # 4. 回溯找 echo envelope 的近边
        bottom_idx = _find_echo_envelope(
            sv_smoothed,
            peak_idx=max_idx,
            threshold=threshold,
            search_min_idx=search_min_idx,
            contiguous=True,
        )

        if bottom_idx is not None:
            # 插值获取精确深度
            idx_floor = int(np.floor(bottom_idx))
            idx_ceil = int(np.ceil(bottom_idx))
            if idx_floor == idx_ceil:
                bottom_depth[ping_idx] = depth[idx_floor] + offset_m
            else:
                # 线性插值
                frac = bottom_idx - idx_floor
                d_floor = depth[idx_floor] if idx_floor < n_samples else depth[-1]
                d_ceil = depth[idx_ceil] if idx_ceil < n_samples else depth[-1]
                bottom_depth[ping_idx] = d_floor + frac * (d_ceil - d_floor) + offset_m

        if progress_callback:
            progress_callback(ping_idx + 1, n_pings)

    # 统计
    n_valid = int(np.sum(np.isfinite(bottom_depth)))
    logger.info(f"AFSC 底部检测完成: {n_valid}/{n_pings} 个 ping 有效 ({100*n_valid/n_pings:.1f}%)")
    logger.info(f"  参数: search_min={search_min}m, window={window_len}, backstep={backstep}dB")

    return bottom_depth


def validate_bottom_line(
    bottom_depth: np.ndarray,
    validation_window: int = 15,
    validation_threshold: float = 3.0,
    min_std: float | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """底部线相关性验证（可单独调用）

    Parameters
    ----------
    bottom_depth : np.ndarray
        底部深度数组 (米)，shape=(n_pings,)
    validation_window : int
        验证窗口大小
    validation_threshold : float
        验证倍数
    min_std : float, optional
        最小标准差（米），默认 2 倍中位深度分辨率

    Returns
    -------
    tuple[np.ndarray, np.ndarray]
        (validated_bottom, relevance)
        - validated_bottom: 验证后的底部深度（无效位置为 NaN）
        - relevance: 有效性标记（0=无效, 1=有效）
    """
    n_pings = len(bottom_depth)
    validated = bottom_depth.copy()
    relevance = np.ones(n_pings, dtype=int)

    # 计算最小标准差
    if min_std is None:
        valid_diffs = np.abs(np.diff(bottom_depth[np.isfinite(bottom_depth)]))
        if len(valid_diffs) > 0:
            min_std = 2 * np.median(valid_diffs)
        else:
            min_std = 0.5  # 默认 0.5 米

    for i in range(1, n_pings):
        if not np.isfinite(bottom_depth[i]):
            relevance[i] = 0
            continue

        # 计算前 validation_window 个 ping 的标准差
        start_idx = max(0, i - validation_window)
        prev_bottoms = validated[start_idx:i]
        valid_prev = prev_bottoms[np.isfinite(prev_bottoms)]

        if len(valid_prev) > 1:
            std_prev = np.std(valid_prev)
            std_prev = max(std_prev, min_std)

            # 验证与前一个的差异
            prev_bottom = validated[i - 1]
            if np.isfinite(prev_bottom):
                diff = abs(bottom_depth[i] - prev_bottom)
                if diff > validation_threshold * std_prev:
                    relevance[i] = 0
                    validated[i] = np.nan  # 标记为无效

    n_valid = int(np.sum(relevance))
    logger.info(f"底部验证完成: {n_valid}/{n_pings} 个 ping 有效")

    return validated, relevance


def detect_bottom(
    ds_Sv: xr.Dataset,
    method: str = "basic",
    offset_m: float = 0.5,
    progress_callback: Callable[[int, int], None] | None = None,
    **kwargs,
) -> np.ndarray:
    """统一底部检测接口

    Parameters
    ----------
    ds_Sv : xr.Dataset
        Sv 数据集
    method : str
        检测方法："basic", "enhanced", "afsc"
    offset_m : float
        底部偏移 (米)
    progress_callback : callable, optional
        进度回调函数
    **kwargs
        传递给具体检测方法的参数

    Returns
    -------
    np.ndarray
        底部深度数组 (米)，shape=(n_pings,)
    """
    if method == "basic":
        return detect_bottom_basic(
            ds_Sv,
            threshold=kwargs.get("threshold", -40.0),
            offset_m=offset_m,
            bin_skip_from_surface=kwargs.get("bin_skip_from_surface", 200),
        )
    elif method == "enhanced":
        return detect_bottom_enhanced(
            ds_Sv,
            peak_threshold=kwargs.get("peak_threshold", -40.0),
            discrimination_threshold=kwargs.get("discrimination_threshold", -50.0),
            saturation_threshold=kwargs.get("saturation_threshold", -60.0),
            validation_window=kwargs.get("validation_window", 15),
            validation_threshold=kwargs.get("validation_threshold", 3.0),
            smoothing_window=kwargs.get("smoothing_window", 11),
            offset_m=offset_m,
            progress_callback=progress_callback,
        )
    elif method == "afsc":
        return detect_bottom_afsc(
            ds_Sv,
            search_min=kwargs.get("search_min", 10.0),
            window_len=kwargs.get("window_len", 11),
            backstep=kwargs.get("backstep", 35.0),
            offset_m=offset_m,
            progress_callback=progress_callback,
        )
    else:
        raise ValueError(f"不支持的底部检测方法: {method}")