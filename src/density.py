"""密度估算模块：NASC → 鱼类密度"""

import logging

import numpy as np
import pandas as pd
import xarray as xr

logger = logging.getLogger("fish_acoustics")


def calculate_nasc(ds_Sv: xr.Dataset, config: dict) -> pd.DataFrame:
    """
    计算 Nautical Area Scattering Coefficient (NASC)

    NASC = 4π × (1852)^2 × ∫ Sv_linear dz

    Parameters
    ----------
    ds_Sv : xr.Dataset
        包含 Sv 和 echo_range 的数据集
    config : dict
        配置字典

    Returns
    -------
    pd.DataFrame
        包含 transect_id 和 nasc 的 DataFrame
    """
    Sv = ds_Sv["Sv"].values  # (ping_time, range_sample)

    # 获取深度分辨率
    if "echo_range" in ds_Sv:
        echo_range = ds_Sv["echo_range"].values
        # 计算每个采样单元的厚度
        if echo_range.ndim == 2:
            dr = np.diff(echo_range, axis=1)
            dr = np.column_stack([dr, dr[:, -1:]])
        else:
            dr = np.diff(echo_range)
            dr = np.append(dr, dr[-1])
    else:
        dr = np.ones_like(Sv)

    # Sv 转线性
    Sv_linear = 10 ** (Sv / 10)

    # 积分
    Sv_linear = np.where(np.isfinite(Sv_linear), Sv_linear, 0)
    integrated = np.nansum(Sv_linear * np.abs(dr), axis=1)

    # NASC = 4π × (1852)^2 × integrated
    nasc = 4 * np.pi * (1852 ** 2) * integrated

    ping_time = ds_Sv["ping_time"].values
    n_pings = len(ping_time)

    # 默认整个数据为一个 transect
    transect_id = np.ones(n_pings, dtype=int)

    df = pd.DataFrame({
        "transect_id": transect_id,
        "ping_idx": np.arange(n_pings),
        "ping_time": ping_time,
        "nasc": nasc,
    })

    logger.info(f"NASC 计算完成: mean={np.nanmean(nasc):.2f}")
    return df


def estimate_density(
    schools_df: pd.DataFrame,
    ds_Sv: xr.Dataset,
    config: dict,
) -> pd.DataFrame:
    """
    基于 NASC 和 TS 估算鱼类密度

    密度公式: ρ = NASC / (4π × 10^(TS/10) × 10000)
    其中 ρ 单位为 ind/ha

    Parameters
    ----------
    schools_df : pd.DataFrame
        鱼群清单
    ds_Sv : xr.Dataset
        Sv 数据集
    config : dict
        配置字典

    Returns
    -------
    pd.DataFrame
        密度估算结果
    """
    ts_default = config.get("density", {}).get("ts_default", -30.0)

    # 计算 NASC
    nasc_df = calculate_nasc(ds_Sv, config)

    # 合并鱼群信息
    if schools_df.empty:
        # 无鱼群，基于全 transect 计算
        total_nasc = nasc_df["nasc"].sum()
        sigma_bs = 10 ** (ts_default / 10)
        density = total_nasc / (4 * np.pi * sigma_bs * 10000)

        result = pd.DataFrame({
            "transect_id": [1],
            "depth_layer": ["all"],
            "nasc": [total_nasc],
            "density_ind_ha": [density],
            "total_biomass_kg": [density * 0.5],  # 假设平均体重 0.5kg
        })
    else:
        # 按鱼群计算
        records = []
        for _, school in schools_df.iterrows():
            school_nasc = nasc_df[
                (nasc_df["ping_idx"] >= school["ping_start"])
                & (nasc_df["ping_idx"] <= school["ping_end"])
            ]["nasc"].sum()

            sigma_bs = 10 ** (ts_default / 10)
            density = school_nasc / (4 * np.pi * sigma_bs * 10000)

            depth_layer = f"{school['depth_start']:.1f}-{school['depth_end']:.1f}m"

            records.append({
                "transect_id": 1,
                "school_id": school["school_id"],
                "depth_layer": depth_layer,
                "nasc": school_nasc,
                "density_ind_ha": density,
                "total_biomass_kg": density * 0.5,  # 假设平均体重 0.5kg
            })

        result = pd.DataFrame(records)

    logger.info(f"密度估算完成: {len(result)} 条记录")
    return result
