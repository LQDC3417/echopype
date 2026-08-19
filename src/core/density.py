"""密度估算模块：ABC / NASC → 鱼类密度（支持深度分层）"""

import logging

import numpy as np
import pandas as pd
import xarray as xr

from src.core.region import get_echo_range_1d
from src.core.utils import get_sv_array, get_vertical_coords, sv_to_linear

logger = logging.getLogger("fish_acoustics")

# 物理常数
FOUR_PI = 4 * np.pi
DEFAULT_N_DEPTH_LAYERS = 5


# ── 辅助函数 ──────────────────────────────────────────────

def _get_depth_resolution(ds_Sv: xr.Dataset) -> np.ndarray:
    """获取深度分辨率 dr，shape 与 Sv 一致 (n_pings, n_samples) 或 (n_samples,)。"""
    er = get_echo_range_1d(ds_Sv)
    if er is None:
        sv = get_sv_array(ds_Sv)
        return np.ones_like(sv)
    # 计算相邻深度差
    dr = np.abs(np.diff(er))
    dr = np.append(dr, dr[-1])
    # 如果 Sv 是 2D，广播 dr
    sv = get_sv_array(ds_Sv)
    if sv.ndim == 2 and dr.ndim == 1:
        dr = np.broadcast_to(dr, sv.shape)
    return dr


def density_from_abc(abc: float, ts_default_db: float = -30.0) -> float:
    """ABC → 鱼类密度 (ind/ha)。

    ρ = ABC / (4π·σ_bs) × 10000，σ_bs = 10^(TS/10)
    项目内密度换算的单一来源（回声积分 integration.py 与本模块共用）。
    """
    sigma_bs = 10 ** (ts_default_db / 10)
    return abc / (FOUR_PI * sigma_bs) * 10000


def _abc_to_density(abc: float, sigma_bs: float, avg_weight_kg: float) -> dict:
    """ABC → 密度指标（消除重复计算）。"""
    density_m2 = abc / (4 * np.pi * sigma_bs)
    density_ha = density_m2 * 10000
    return {
        "abc": abc,
        "density_ind_m2": density_m2,
        "density_ind_ha": density_ha,
        "total_biomass_kg_ha": density_ha * avg_weight_kg,
    }


# ── 核心计算 ──────────────────────────────────────────────

def calculate_abc(
    ds_Sv: xr.Dataset,
    config: dict,
) -> pd.DataFrame:
    """
    计算 Area Backscattering Coefficient (ABC)

    ABC = 4π × ∫ Sv_linear × dz    [m²/m²]

    Parameters
    ----------
    ds_Sv : xr.Dataset
        包含 Sv 和 echo_range 的数据集
    config : dict
        配置字典

    Returns
    -------
    pd.DataFrame
        包含 ping_idx, ping_time, abc 的 DataFrame
    """
    Sv = get_sv_array(ds_Sv)
    dr = _get_depth_resolution(ds_Sv)

    # 积分: ABC = 4π × ∫ Sv_linear × dr
    integrated = np.nansum(sv_to_linear(Sv) * dr, axis=1)
    abc = FOUR_PI * integrated

    ping_time = ds_Sv["ping_time"].values

    df = pd.DataFrame({
        "ping_idx": np.arange(len(ping_time)),
        "ping_time": ping_time,
        "abc": abc,
    })

    logger.info(f"ABC 计算完成: mean={np.nanmean(abc):.6f} m²/m²")
    return df


# ── 密度估算 ──────────────────────────────────────────────

def estimate_density(
    schools_df: pd.DataFrame,
    ds_Sv: xr.Dataset,
    config: dict,
) -> pd.DataFrame:
    """
    基于 ABC 和 TS 估算鱼类密度。

    密度公式: ρ = ABC / (4π × σ_bs)

    Parameters
    ----------
    schools_df : pd.DataFrame
        鱼群清单（school_id, ping_start, ping_end, depth_start, depth_end）
    ds_Sv : xr.Dataset
        Sv 数据集
    config : dict
        配置字典

    Returns
    -------
    pd.DataFrame
        密度估算结果
    """
    density_cfg = config.get("density", {})
    ts_default = density_cfg.get("ts_default", -30.0)
    avg_weight_kg = density_cfg.get("avg_weight_kg", 0.5)
    sigma_bs = 10 ** (ts_default / 10)

    abc_df = calculate_abc(ds_Sv, config)
    ping_time = ds_Sv["ping_time"].values

    if schools_df.empty:
        total_abc = abc_df["abc"].sum()
        row = _abc_to_density(total_abc, sigma_bs, avg_weight_kg)
        row["transect_id"] = 1
        row["depth_layer"] = "all"
        result = pd.DataFrame([row])
    else:
        records = []
        for _, school in schools_df.iterrows():
            # 用 ping_time 索引匹配（school 的 ping_start/end 是 datetime）
            mask_ping = (ping_time >= school["ping_start"]) & (ping_time <= school["ping_end"])
            school_abc = abc_df.loc[mask_ping, "abc"].sum()

            row = _abc_to_density(school_abc, sigma_bs, avg_weight_kg)
            row["transect_id"] = 1
            row["school_id"] = school["school_id"]
            row["depth_layer"] = f"{school['depth_start']:.1f}-{school['depth_end']:.1f}m"
            records.append(row)

        result = pd.DataFrame(records)

    logger.info(f"密度估算完成: {len(result)} 条记录")
    return result


def estimate_density_by_depth(
    ds_Sv: xr.Dataset,
    config: dict,
    depth_bins: list[float] | None = None,
) -> pd.DataFrame:
    """
    按深度分层估算鱼类密度（向量化，无逐 ping 循环）。

    Parameters
    ----------
    ds_Sv : xr.Dataset
    config : dict
    depth_bins : list[float], optional
        深度分层边界（米），如 [0, 5, 10, 20, 50]。
        默认按 echo_range 均分为 5 层。

    Returns
    -------
    pd.DataFrame
        每层一行，包含 depth_layer, abc, density 等
    """
    density_cfg = config.get("density", {})
    ts_default = density_cfg.get("ts_default", -30.0)
    avg_weight_kg = density_cfg.get("avg_weight_kg", 0.5)
    sigma_bs = 10 ** (ts_default / 10)

    Sv = get_sv_array(ds_Sv)  # (n_pings, n_samples)
    dr = _get_depth_resolution(ds_Sv)
    depth = get_vertical_coords(ds_Sv)  # (n_samples,)

    if depth_bins is None:
        d_min = float(np.nanmin(depth))
        d_max = float(np.nanmax(depth))
        depth_bins = np.linspace(d_min, d_max, DEFAULT_N_DEPTH_LAYERS + 1).tolist()

    # 向量化：预乘 Sv × dr
    sv_dr = sv_to_linear(Sv) * dr  # (n_pings, n_samples)

    records = []
    for i in range(len(depth_bins) - 1):
        d_lo, d_hi = depth_bins[i], depth_bins[i + 1]
        mask_d = (depth >= d_lo) & (depth < d_hi)  # (n_samples,)
        if not np.any(mask_d):
            continue

        # 向量化积分：对每 ping 求和该深度范围
        layer_abc_per_ping = np.nansum(sv_dr[:, mask_d], axis=1)  # (n_pings,)
        layer_abc = FOUR_PI * layer_abc_per_ping
        mean_abc = float(np.nanmean(layer_abc))

        row = _abc_to_density(mean_abc, sigma_bs, avg_weight_kg)
        row["depth_layer"] = f"{d_lo:.0f}-{d_hi:.0f}m"
        records.append(row)

    result = pd.DataFrame(records)
    logger.info(f"深度分层密度估算完成: {len(result)} 层")
    return result


# ── 统计摘要 ──────────────────────────────────────────────

def sv_statistics_summary(
    ds_Sv: xr.Dataset,
    transect_ids: np.ndarray | None = None,
) -> pd.DataFrame:
    """Sv 统计摘要（按 transect 分组）。

    Parameters
    ----------
    ds_Sv : xr.Dataset
    transect_ids : np.ndarray, optional
        transect ID 数组，shape=(n_pings,)。默认全部视为 1 个 transect。

    Returns
    -------
    pd.DataFrame
        每行一个 transect，包含 mean, median, std, p5, p25, p75, p95
    """
    Sv = get_sv_array(ds_Sv)  # (n_pings, n_samples)

    if transect_ids is None:
        transect_ids = np.zeros(Sv.shape[0], dtype=int)

    records = []
    for tid in np.unique(transect_ids):
        sv_t = Sv[transect_ids == tid, :]
        sv_valid = sv_t[np.isfinite(sv_t)]

        if len(sv_valid) == 0:
            continue

        records.append({
            "transect_id": int(tid),
            "n_pings": int((transect_ids == tid).sum()),
            "mean_sv": float(np.mean(sv_valid)),
            "median_sv": float(np.median(sv_valid)),
            "std_sv": float(np.std(sv_valid)),
            "p5_sv": float(np.percentile(sv_valid, 5)),
            "p25_sv": float(np.percentile(sv_valid, 25)),
            "p75_sv": float(np.percentile(sv_valid, 75)),
            "p95_sv": float(np.percentile(sv_valid, 95)),
            "min_sv": float(np.min(sv_valid)),
            "max_sv": float(np.max(sv_valid)),
            "nan_ratio": float(np.isnan(sv_t).sum() / sv_t.size),
        })

    result = pd.DataFrame(records)
    logger.info(f"Sv 统计摘要完成: {len(result)} 个 transect")
    return result
