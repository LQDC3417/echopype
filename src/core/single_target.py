"""单体目标检测模块：基于阈值和连通域分析检测水体中的单个鱼类目标

职责：
- 基于 Sv 阈值筛选强回波区域
- 使用连通域分析识别单体目标
- 计算每个目标的目标强度(TS)、深度、面积等属性
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd
import xarray as xr

from src.core.utils import get_sv_array, get_vertical_coords, sv_to_linear

logger = logging.getLogger("fish_acoustics")


# ── 单体目标检测 ──────────────────────────────────────────

def detect_single_targets(
    ds_Sv: xr.Dataset,
    config: dict,
) -> pd.DataFrame:
    """基于阈值和连通域分析检测单体目标

    Parameters
    ----------
    ds_Sv : xr.Dataset
        包含 Sv 变量的数据集。若已启用分析区域，应传入裁剪后的 ds_Sv。
    config : dict
        配置字典，需包含 single_target 子项：
        - sv_threshold_db: float, Sv 阈值（dB），默认 -50.0
        - min_area: int, 最小面积（像素），默认 3
        - max_area: int, 最大面积（像素），默认 500

    Returns
    -------
    pd.DataFrame
        包含每个目标的属性：target_id, ping_idx, depth_idx, ping_center,
        depth_center, area, sv_max, sv_mean
    """
    from scipy import ndimage

    # 获取配置参数
    st_config = config.get("single_target", {})
    sv_threshold_db = st_config.get("sv_threshold_db", -50.0)
    min_area = st_config.get("min_area", 3)
    max_area = st_config.get("max_area", 500)

    logger.info(
        f"单体目标检测: threshold={sv_threshold_db} dB, "
        f"area=[{min_area}, {max_area}]"
    )

    # 获取 Sv 数组（优先使用去噪数据）
    Sv = get_sv_array(ds_Sv)
    ping_time = ds_Sv["ping_time"].values
    depth = get_vertical_coords(ds_Sv)

    # 阈值筛选：Sv > threshold 表示强回波
    mask = Sv > sv_threshold_db

    # 连通域分析
    labeled, num_features = ndimage.label(mask)
    logger.info(f"连通域数量: {num_features}")

    if num_features == 0:
        return _empty_targets_df()

    # 提取每个连通域的属性
    records = []
    for target_id in range(1, num_features + 1):
        region = labeled == target_id
        rows, cols = np.where(region)

        if len(rows) == 0:
            continue

        area = len(rows)

        # 面积过滤
        if area < min_area or area > max_area:
            continue

        # 计算中心位置（ping 维度和 depth 维度）
        ping_idx_center = int(np.mean(rows))
        depth_idx_center = int(np.mean(cols))

        # 获取实际 ping 时间和深度
        ping_center = ping_time[ping_idx_center] if ping_idx_center < len(ping_time) else ping_idx_center
        depth_center = float(depth[depth_idx_center]) if depth_idx_center < len(depth) else depth_idx_center

        # 计算该区域的 Sv 统计
        region_sv = Sv[region]
        sv_max = float(np.nanmax(region_sv))
        sv_mean = float(np.nanmean(region_sv))

        # 计算空间范围
        ping_start_idx = int(rows.min())
        ping_end_idx = int(rows.max())
        depth_start_idx = int(cols.min())
        depth_end_idx = int(cols.max())

        records.append({
            "target_id": target_id,
            "ping_idx_center": ping_idx_center,
            "depth_idx_center": depth_idx_center,
            "ping_start_idx": ping_start_idx,
            "ping_end_idx": ping_end_idx,
            "depth_start_idx": depth_start_idx,
            "depth_end_idx": depth_end_idx,
            "ping_center": ping_center,
            "depth_center": depth_center,
            "area": area,
            "sv_max": sv_max,
            "sv_mean": sv_mean,
        })

    df = pd.DataFrame(records)
    logger.info(f"检测到 {len(df)} 个单体目标")
    return df


# ── 目标强度计算 ──────────────────────────────────────────

def compute_target_ts(
    targets_df: pd.DataFrame,
    ds_Sv: xr.Dataset,
) -> pd.DataFrame:
    """计算每个目标的目标强度 (Target Strength, TS)

    TS 估算基于积分法：
    TS = 10 * log10( sum(10^(Sv/10)) ) + 10 * log10(Δr)
    其中 Δr 是采样间距（米）

    Parameters
    ----------
    targets_df : pd.DataFrame
        detect_single_targets 返回的目标 DataFrame
    ds_Sv : xr.Dataset
        包含 Sv 变量的数据集

    Returns
    -------
    pd.DataFrame
        原 DataFrame 添加 ts_db 列
    """
    if targets_df.empty:
        targets_df = targets_df.copy()
        targets_df["ts_db"] = []
        return targets_df

    # 获取 Sv 数组
    Sv = get_sv_array(ds_Sv)
    depth = get_vertical_coords(ds_Sv)

    # 计算采样间距（米）
    if len(depth) >= 2:
        # 取平均间距，注意可能是递减的
        diff = np.abs(np.diff(depth))
        dr = float(np.mean(diff))
    else:
        dr = 1.0  # fallback

    logger.info(f"采样间距: {dr:.4f} m")

    # 计算每个目标的 TS
    ts_list = []
    for _, row in targets_df.iterrows():
        # 提取目标区域
        ping_slice = slice(int(row["ping_start_idx"]), int(row["ping_end_idx"]) + 1)
        depth_slice = slice(int(row["depth_start_idx"]), int(row["depth_end_idx"]) + 1)

        target_sv = Sv[ping_slice, depth_slice]

        # 积分法计算 TS
        # TS = 10 * log10( sum(10^(Sv/10)) ) + 10 * log10(dr)
        sv_linear_sum = np.nansum(sv_to_linear(target_sv))
        if sv_linear_sum > 0:
            ts_db = 10 * np.log10(sv_linear_sum) + 10 * np.log10(dr)
        else:
            ts_db = -999.0  # 无效值

        ts_list.append(ts_db)

    targets_df = targets_df.copy()
    targets_df["ts_db"] = ts_list

    logger.info(f"TS 计算完成，范围: [{np.nanmin(ts_list):.1f}, {np.nanmax(ts_list):.1f}] dB")
    return targets_df


# ── 统计摘要 ──────────────────────────────────────────────

def get_target_summary(
    targets_df: pd.DataFrame,
) -> dict:
    """获取目标统计摘要

    Parameters
    ----------
    targets_df : pd.DataFrame
        detect_single_targets 或 compute_target_ts 返回的目标 DataFrame

    Returns
    -------
    dict
        包含以下统计信息：
        - count: 目标数量
        - area_mean, area_std, area_min, area_max: 面积统计
        - depth_mean, depth_std: 深度统计
        - sv_max_mean, sv_max_std: 最大 Sv 统计
        - ts_mean, ts_std, ts_min, ts_max: TS 统计（如有）
    """
    if targets_df.empty:
        return {
            "count": 0,
            "area_mean": 0, "area_std": 0, "area_min": 0, "area_max": 0,
            "depth_mean": 0, "depth_std": 0,
            "sv_max_mean": 0, "sv_max_std": 0,
            "ts_mean": 0, "ts_std": 0, "ts_min": 0, "ts_max": 0,
        }

    summary = {
        "count": len(targets_df),
        "area_mean": float(targets_df["area"].mean()),
        "area_std": float(targets_df["area"].std()) if len(targets_df) > 1 else 0,
        "area_min": float(targets_df["area"].min()),
        "area_max": float(targets_df["area"].max()),
        "depth_mean": float(targets_df["depth_center"].mean()),
        "depth_std": float(targets_df["depth_center"].std()) if len(targets_df) > 1 else 0,
        "sv_max_mean": float(targets_df["sv_max"].mean()),
        "sv_max_std": float(targets_df["sv_max"].std()) if len(targets_df) > 1 else 0,
    }

    # 如果有 TS 列，添加 TS 统计
    if "ts_db" in targets_df.columns:
        ts_values = targets_df["ts_db"]
        # 排除无效值
        valid_ts = ts_values[ts_values > -900]
        if len(valid_ts) > 0:
            summary.update({
                "ts_mean": float(valid_ts.mean()),
                "ts_std": float(valid_ts.std()) if len(valid_ts) > 1 else 0,
                "ts_min": float(valid_ts.min()),
                "ts_max": float(valid_ts.max()),
            })
        else:
            summary.update({
                "ts_mean": 0, "ts_std": 0, "ts_min": 0, "ts_max": 0,
            })
    else:
        summary.update({
            "ts_mean": 0, "ts_std": 0, "ts_min": 0, "ts_max": 0,
        })

    logger.info(f"目标统计: count={summary['count']}, "
                f"area=[{summary['area_min']:.0f}, {summary['area_max']:.0f}], "
                f"depth_mean={summary['depth_mean']:.1f} m")
    return summary


# ── 内部辅助函数 ──────────────────────────────────────────

def _empty_targets_df() -> pd.DataFrame:
    """返回空的目标 DataFrame，保持列结构一致"""
    return pd.DataFrame(columns=[
        "target_id", "ping_idx_center", "depth_idx_center",
        "ping_start_idx", "ping_end_idx",
        "depth_start_idx", "depth_end_idx",
        "ping_center", "depth_center",
        "area", "sv_max", "sv_mean",
    ])


# ── 便捷接口 ──────────────────────────────────────────────

def detect_and_compute_ts(
    ds_Sv: xr.Dataset,
    config: dict,
) -> pd.DataFrame:
    """一键检测单体目标并计算 TS

    Parameters
    ----------
    ds_Sv : xr.Dataset
        包含 Sv 变量的数据集
    config : dict
        配置字典

    Returns
    -------
    pd.DataFrame
        包含目标属性和 TS 的 DataFrame
    """
    targets_df = detect_single_targets(ds_Sv, config)
    if not targets_df.empty:
        targets_df = compute_target_ts(targets_df, ds_Sv)
    return targets_df
