"""密度估算模块：ABC → 鱼类密度"""

import logging

import numpy as np
import pandas as pd
import xarray as xr

logger = logging.getLogger("fish_acoustics")


def calculate_abc(
    ds_Sv: xr.Dataset,
    config: dict,
) -> pd.DataFrame:
    """
    计算 Area Backscattering Coefficient (ABC)

    ABC = 4π × ∫ Sv_linear × dz    [m²/m²]

    与 NASC 的区别：ABC 不含海里-米转换因子 (1852²)

    Parameters
    ----------
    ds_Sv : xr.Dataset
        包含 Sv 和 echo_range 的数据集。若已启用分析区域，应传入裁剪后的 ds_Sv。
    config : dict
        配置字典

    Returns
    -------
    pd.DataFrame
        包含 transect_id 和 abc 的 DataFrame
    """
    Sv = ds_Sv["Sv"]
    if "channel" in Sv.dims:
        Sv = Sv.isel(channel=0)
    Sv = Sv.values  # (ping_time, range_sample)

    # 获取深度分辨率
    if "echo_range" in ds_Sv:
        echo_range = ds_Sv["echo_range"]
        if "channel" in echo_range.dims:
            echo_range = echo_range.isel(channel=0)
        echo_range = echo_range.values
        if echo_range.ndim == 2:
            dr = np.diff(echo_range, axis=1)
            dr = np.column_stack([dr, dr[:, -1:]])
        else:
            dr = np.diff(echo_range)
            dr = np.append(dr, dr[-1])
    else:
        dr = np.ones_like(Sv)

    # Sv 转线性（NaN 区域自动为 0，不影响积分）
    Sv_linear = 10 ** (Sv / 10)
    Sv_linear = np.where(np.isfinite(Sv_linear), Sv_linear, 0)

    # 积分
    integrated = np.nansum(Sv_linear * np.abs(dr), axis=1)

    # ABC = 4π × integrated [m²/m²]
    abc = 4 * np.pi * integrated

    ping_time = ds_Sv["ping_time"].values
    n_pings = len(ping_time)

    # 默认整个数据为一个 transect
    transect_id = np.ones(n_pings, dtype=int)

    df = pd.DataFrame({
        "transect_id": transect_id,
        "ping_idx": np.arange(n_pings),
        "ping_time": ping_time,
        "abc": abc,
    })

    logger.info(f"ABC 计算完成: mean={np.nanmean(abc):.6f} m²/m²")
    return df


def estimate_density(
    schools_df: pd.DataFrame,
    ds_Sv: xr.Dataset,
    config: dict,
) -> pd.DataFrame:
    """
    基于 ABC 和 TS 估算鱼类密度

    密度公式: ρ = ABC / (4π × σ_bs)
    其中:
        ABC — 面积后向散射系数 [m²/m²]
        σ_bs = 10^(TS/10) — 单体鱼后向散射截面 [m²]
        ρ 单位为 ind/m²

    Parameters
    ----------
    schools_df : pd.DataFrame
        鱼群清单
    ds_Sv : xr.Dataset
        Sv 数据集。若已启用分析区域，应传入裁剪后的 ds_Sv。
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

    # 计算 ABC
    abc_df = calculate_abc(ds_Sv, config)

    # 合并鱼群信息
    if schools_df.empty:
        # 无鱼群，基于全 transect 计算
        total_abc = abc_df["abc"].sum()
        # ρ = ABC / (4π × σ_bs) [ind/m²]
        density_m2 = total_abc / (4 * np.pi * sigma_bs)
        density_ha = density_m2 * 10000  # 转换为 ind/ha

        result = pd.DataFrame({
            "transect_id": [1],
            "depth_layer": ["all"],
            "abc": [total_abc],
            "density_ind_m2": [density_m2],
            "density_ind_ha": [density_ha],
            "total_biomass_kg_ha": [density_ha * avg_weight_kg],
        })
    else:
        # 按鱼群计算
        records = []
        for _, school in schools_df.iterrows():
            school_abc = abc_df[
                (abc_df["ping_idx"] >= school["ping_start"])
                & (abc_df["ping_idx"] <= school["ping_end"])
            ]["abc"].sum()

            # ρ = ABC / (4π × σ_bs) [ind/m²]
            density_m2 = school_abc / (4 * np.pi * sigma_bs)
            density_ha = density_m2 * 10000  # 转换为 ind/ha

            depth_layer = f"{school['depth_start']:.1f}-{school['depth_end']:.1f}m"

            records.append({
                "transect_id": 1,
                "school_id": school["school_id"],
                "depth_layer": depth_layer,
                "abc": school_abc,
                "density_ind_m2": density_m2,
                "density_ind_ha": density_ha,
                "total_biomass_kg_ha": density_ha * avg_weight_kg,
            })

        result = pd.DataFrame(records)

    logger.info(f"密度估算完成: {len(result)} 条记录")
    return result
