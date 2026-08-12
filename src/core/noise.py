"""增强噪声去除模块：De Robertis 算法 + 被动模式 + 可视化检查

参考：
- Matecho NoiseReductionDeRobertis.m：完整的 De Robertis 算法
- pyEcholab noise.py：被动噪声估算

功能：
- De Robertis 模式：从回波数据估计噪声（默认）
- 被动模式：从被动 ping（关闭发射时）估算噪声
- 噪声可视化检查图生成
"""

import logging
from dataclasses import dataclass
from typing import Callable

import numpy as np
import xarray as xr

from src.core.utils import get_sv_array, get_vertical_coords

logger = logging.getLogger("fish_acoustics")


@dataclass
class NoiseEstimate:
    """噪声估计结果"""
    noise_Sv: np.ndarray  # 噪声估计 (dB), shape=(n_pings, n_samples)
    noise_per_ping: np.ndarray  # 每 ping 的噪声估计 (dB), shape=(n_pings,)
    SNR: np.ndarray  # 信噪比 (dB), shape=(n_pings, n_samples)
    Sv_corrected: np.ndarray  # 去噪后的 Sv (dB), shape=(n_pings, n_samples)
    params: dict  # 使用的参数


def estimate_noise_de_robertis(
    Sv: np.ndarray,
    depth: np.ndarray,
    ping_num: int = 40,
    range_sample_num: int = 10,
    noise_max: float = -125.0,
    low_Sv_dB: float = -150.0,
) -> tuple[np.ndarray, np.ndarray]:
    """De Robertis 噪声估计算法

    参考：De Robertis & Higginbottom (2007)
    "A post-processing technique to estimate the signal-to-noise ratio
    and remove echosounder background noise."

    Parameters
    ----------
    Sv : np.ndarray
        Sv 数据 (dB), shape=(n_pings, n_samples)
    depth : np.ndarray
        深度数组 (米), shape=(n_samples,)
    ping_num : int
        ping 方向平均窗口大小
    range_sample_num : int
        深度方向平均窗口大小
    noise_max : float
        噪声上限 (dB)
    low_Sv_dB : float
        低 Sv 替换值 (dB)

    Returns
    -------
    tuple[np.ndarray, np.ndarray]
        (noise_2d, noise_per_ping)
        - noise_2d: 2D 噪声矩阵 (dB), shape=(n_pings, n_samples)
        - noise_per_ping: 每 ping 的噪声估计 (dB), shape=(n_pings,)
    """
    n_pings, n_samples = Sv.shape

    # 1. 转换为线性域（功率）
    Sv_linear = 10 ** (Sv / 10)
    Sv_linear = np.nan_to_num(Sv_linear, nan=0.0, posinf=0.0, neginf=0.0)

    # 2. 计算分块数
    n_ping_bins = max(1, n_pings // ping_num)
    n_range_bins = max(1, n_samples // range_sample_num)

    # 3. 按窗口平均
    # 截取到可整除的大小
    ping_cut = n_ping_bins * ping_num
    range_cut = n_range_bins * range_sample_num

    Sv_cut = Sv_linear[:ping_cut, :range_cut]

    # reshape 为 (n_ping_bins, ping_num, n_range_bins, range_sample_num)
    Sv_reshaped = Sv_cut.reshape(n_ping_bins, ping_num, n_range_bins, range_sample_num)

    # 按深度方向平均
    Sv_depth_mean = np.nanmean(Sv_reshaped, axis=3)  # (n_ping_bins, ping_num, n_range_bins)

    # 按 ping 方向平均
    Sv_ping_mean = np.nanmean(Sv_depth_mean, axis=1)  # (n_ping_bins, n_range_bins)

    # 4. 按 ping 列取最小值作为噪声估计
    noise_per_bin = np.nanmin(Sv_ping_mean, axis=1)  # (n_ping_bins,)

    # 5. 应用噪声上限
    noise_max_linear = 10 ** (noise_max / 10)
    noise_per_bin = np.minimum(noise_per_bin, noise_max_linear)

    # 6. 扩展到完整 ping 数
    noise_per_ping = np.repeat(noise_per_bin, ping_num)[:n_pings]

    # 7. 构建 2D 噪声矩阵
    noise_2d = np.tile(noise_per_ping[:, np.newaxis], (1, n_samples))

    return noise_2d, noise_per_ping


def estimate_noise_passive(
    Sv: np.ndarray,
    passive_ping_indices: np.ndarray | None = None,
    min_range: float = 5.0,
    depth: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """被动模式噪声估算

    使用被动 ping（关闭发射时）估算噪声。

    Parameters
    ----------
    Sv : np.ndarray
        Sv 数据 (dB), shape=(n_pings, n_samples)
    passive_ping_indices : np.ndarray, optional
        被动 ping 的索引数组。如果为 None，使用所有 ping 的最小值。
    min_range : float
        最小距离 (米)，用于排除 ringdown
    depth : np.ndarray, optional
        深度数组 (米), shape=(n_samples,)

    Returns
    -------
    tuple[np.ndarray, np.ndarray]
        (noise_2d, noise_per_ping)
    """
    n_pings, n_samples = Sv.shape

    # 排除 ringdown 区域
    if depth is not None:
        valid_range = depth >= min_range
    else:
        valid_range = np.ones(n_samples, dtype=bool)

    # 转换为线性域
    Sv_linear = 10 ** (Sv / 10)
    Sv_linear = np.nan_to_num(Sv_linear, nan=0.0)

    # 排除 ringdown
    Sv_linear[:, ~valid_range] = 0.0

    if passive_ping_indices is not None and len(passive_ping_indices) > 0:
        # 使用指定的被动 ping 估算噪声（取均值作为全局噪声估计）
        passive_data = Sv_linear[passive_ping_indices, :]
        # 对所有被动 ping 取平均，得到单一噪声剖面
        noise_profile_linear = np.nanmean(passive_data, axis=0)  # (n_samples,)
        # 对每个 ping 应用相同的噪声剖面
        noise_2d_linear = np.tile(noise_profile_linear, (n_pings, 1))
        noise_per_ping_linear = np.nanmean(noise_2d_linear, axis=1)  # (n_pings,)
    else:
        # 使用每个 ping 的最小值（排除 ringdown）
        noise_per_ping_linear = np.nanmin(Sv_linear, axis=1)
        noise_2d_linear = np.tile(noise_per_ping_linear[:, np.newaxis], (1, n_samples))

    # 转换回 dB 域
    noise_per_ping = 10 * np.log10(noise_per_ping_linear + 1e-20)
    noise_2d = 10 * np.log10(noise_2d_linear + 1e-20)

    return noise_2d, noise_per_ping


def apply_noise_reduction(
    ds_Sv: xr.Dataset,
    config: dict,
) -> xr.Dataset:
    """应用噪声去除（增强版）

    Parameters
    ----------
    ds_Sv : xr.Dataset
        Sv 数据集
    config : dict
        配置字典

    Returns
    -------
    xr.Dataset
        添加了 Sv_corrected 和 noise 相关变量的数据集
    """
    noise_cfg = config.get("noise_removal", {})
    mode = noise_cfg.get("mode", "de_robertis")

    # 获取数据
    Sv = get_sv_array(ds_Sv)  # (n_pings, n_samples)
    depth = get_vertical_coords(ds_Sv)  # (n_samples,)

    logger.info(f"噪声去除: mode={mode}")

    if mode == "passive":
        # 被动模式
        passive_indices = noise_cfg.get("passive_ping_indices", None)
        min_range = noise_cfg.get("min_range", 5.0)

        noise_2d, noise_per_ping = estimate_noise_passive(
            Sv, passive_indices, min_range, depth,
        )
    else:
        # De Robertis 模式（默认）
        ping_num = noise_cfg.get("ping_num", 40)
        range_sample_num = noise_cfg.get("range_sample_num", 10)
        noise_max = noise_cfg.get("noise_max", -125.0)
        low_Sv_dB = noise_cfg.get("low_Sv_dB", -150.0)

        noise_2d, noise_per_ping = estimate_noise_de_robertis(
            Sv, depth, ping_num, range_sample_num, noise_max, low_Sv_dB,
        )

    # 计算 SNR
    SNR = Sv - noise_2d

    # 应用 SNR 阈值
    snr_threshold = noise_cfg.get("snr_threshold", 3.0)
    Sv_corrected = Sv.copy()
    Sv_corrected[SNR < snr_threshold] = np.nan

    # 低 Sv 替换
    low_Sv_dB = noise_cfg.get("low_Sv_dB", -150.0)
    Sv_corrected[Sv_corrected < low_Sv_dB] = low_Sv_dB

    # 保存结果到数据集
    ds_Sv["Sv_corrected"] = ds_Sv["Sv"].copy()
    ds_Sv["Sv_corrected"].values[:] = Sv_corrected
    ds_Sv["noise_Sv"] = xr.DataArray(noise_2d, dims=["ping_time", "range_sample"])
    ds_Sv["noise_per_ping"] = xr.DataArray(noise_per_ping, dims=["ping_time"])
    ds_Sv["SNR"] = xr.DataArray(SNR, dims=["ping_time", "range_sample"])

    # 记录统计
    n_masked = int(np.sum(SNR < snr_threshold))
    total = SNR.size
    logger.info(f"噪声去除完成: {n_masked}/{total} 个样本被掩码 ({100*n_masked/total:.1f}%)")
    logger.info(f"  噪声范围: [{np.nanmin(noise_per_ping):.1f}, {np.nanmax(noise_per_ping):.1f}] dB")

    return ds_Sv


def noise_statistics(ds_Sv: xr.Dataset) -> dict:
    """计算噪声统计信息

    Parameters
    ----------
    ds_Sv : xr.Dataset
        包含噪声信息的数据集

    Returns
    -------
    dict
        统计信息
    """
    if "noise_per_ping" not in ds_Sv:
        return {"status": "no_noise_data"}

    noise_per_ping = ds_Sv["noise_per_ping"].values
    noise_valid = noise_per_ping[np.isfinite(noise_per_ping)]

    if len(noise_valid) == 0:
        return {"status": "no_valid_data"}

    stats = {
        "status": "ok",
        "n_pings": len(noise_per_ping),
        "noise_mean": float(np.mean(noise_valid)),
        "noise_std": float(np.std(noise_valid)),
        "noise_min": float(np.min(noise_valid)),
        "noise_max": float(np.max(noise_valid)),
        "noise_median": float(np.median(noise_valid)),
    }

    if "SNR" in ds_Sv:
        snr = ds_Sv["SNR"].values
        snr_valid = snr[np.isfinite(snr)]
        if len(snr_valid) > 0:
            stats.update({
                "snr_mean": float(np.mean(snr_valid)),
                "snr_std": float(np.std(snr_valid)),
                "snr_below_threshold": int(np.sum(snr < 3.0)),
            })

    return stats
