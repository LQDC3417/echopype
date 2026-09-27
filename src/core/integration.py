"""回声积分模块：按 EDSU 分组 + 垂直分层积分（合并自原网格分析）

以回声积分为主体，吸收原网格分析功能：
- EDSU 类型：pings（按 ping 数）/ distance（按 GPS 航行距离，米）
- 核心指标：mean_Sv、ABC（面积反向散射系数，m²/m²）、min/max_Sv、有效样本数
- 新增：密度估算（ind/ha，基于 ABC 与默认目标强度 ts_default）
- 支持 echogram 网格叠加显示（按 mean_Sv 着色）
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

import numpy as np
import pandas as pd
import xarray as xr

from src.core.utils import get_sv_array, get_vertical_coords, sv_to_linear

logger = logging.getLogger("fish_acoustics")


class ESUType(Enum):
    """EDSU 类型枚举"""
    PINGS = "pings"
    DISTANCE = "distance"


# ── GPS 距离计算（移植自原 grid.py）───────────────────────

def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine 公式计算两点间距离（米）。"""
    R = 6371000  # 地球半径（米）
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2) ** 2
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


def _extract_gps(ds_Sv: xr.Dataset) -> tuple:
    """从数据集提取 GPS 坐标，处理多种数据结构。"""
    lat, lon = None, None

    if "latitude" in ds_Sv and "longitude" in ds_Sv:
        lat = ds_Sv["latitude"].values
        lon = ds_Sv["longitude"].values
    elif "location" in ds_Sv:
        loc = ds_Sv["location"]
        if "latitude" in loc and "longitude" in loc:
            lat = loc["latitude"].values
            lon = loc["longitude"].values

    if lat is None or lon is None:
        return None, None

    # 按维度名选择首通道，保留全部 ping，避免轴顺序改变时截掉测线。
    coordinates = []
    for name in ("latitude", "longitude"):
        values = ds_Sv[name]
        if "channel" in values.dims:
            values = values.isel(channel=0)
        if values.dims != ("ping_time",):
            raise ValueError("GPS 坐标必须按 ping_time 对齐")
        coordinates.append(values.values)
    lat, lon = coordinates

    return lat, lon


def _get_cumulative_distance(ds_Sv: xr.Dataset) -> np.ndarray | None:
    """从 GPS 数据计算累积距离（米）。

    Returns
    -------
    np.ndarray or None
        累积距离数组 (n_pings,)；无 GPS 数据时返回 None
    """
    lat, lon = _extract_gps(ds_Sv)
    if lat is None or lon is None:
        return None

    mask = np.isfinite(lat) & np.isfinite(lon)
    valid_indices = np.where(mask)[0]
    if len(valid_indices) < 2:
        logger.warning(f"GPS 数据有效点不足: {len(valid_indices)}")
        return None

    distances = np.zeros(len(lat))
    for i in range(1, len(valid_indices)):
        idx_prev = valid_indices[i - 1]
        idx_curr = valid_indices[i]
        distances[idx_curr] = _haversine(lat[idx_prev], lon[idx_prev], lat[idx_curr], lon[idx_curr])

    return np.cumsum(distances)


@dataclass
class IntegrationResult:
    """回声积分结果

    按 (n_intervals, n_layers) 组织的积分统计结果。
    每个 interval 代表一个水平 EDSU，每个 layer 代表一个垂直深度层。

    Attributes
    ----------
    mean_Sv : np.ndarray
        平均体积散射强度 (dB)，shape=(n_intervals, n_layers)
    abc : np.ndarray
        面积反向散射系数 (m²/m²)，shape=(n_intervals, n_layers)
    min_Sv / max_Sv : np.ndarray
        最小/最大 Sv (dB)
    density_ind_ha : np.ndarray
        鱼类密度 (ind/ha)，基于 ABC 与默认目标强度
    n_good : np.ndarray
        有效样本数
    n_excluded / n_total : np.ndarray
        排除样本数 / 总样本数
    ping_start / ping_end : np.ndarray
        每个 interval 的起始/结束 ping 索引
    depth_start / depth_end : np.ndarray
        每层的起始/结束深度 (米)
    """
    mean_Sv: np.ndarray
    abc: np.ndarray
    min_Sv: np.ndarray
    max_Sv: np.ndarray
    density_ind_ha: np.ndarray
    n_good: np.ndarray
    n_excluded: np.ndarray
    n_total: np.ndarray
    ping_start: np.ndarray
    ping_end: np.ndarray
    depth_start: np.ndarray
    depth_end: np.ndarray

    @property
    def n_intervals(self) -> int:
        return self.mean_Sv.shape[0]

    @property
    def n_layers(self) -> int:
        return self.mean_Sv.shape[1]

    def to_dataframe(self) -> pd.DataFrame:
        """将积分结果转换为 DataFrame（每行一个网格单元）"""
        records = []
        for i in range(self.n_intervals):
            for j in range(self.n_layers):
                records.append({
                    "interval": i,
                    "layer": j,
                    "ping_start": int(self.ping_start[i]),
                    "ping_end": int(self.ping_end[i]),
                    "depth_start": float(self.depth_start[j]),
                    "depth_end": float(self.depth_end[j]),
                    "mean_Sv": float(self.mean_Sv[i, j]),
                    "abc": float(self.abc[i, j]),
                    "min_Sv": float(self.min_Sv[i, j]),
                    "max_Sv": float(self.max_Sv[i, j]),
                    "n_good": int(self.n_good[i, j]),
                    "density_ind_ha": float(self.density_ind_ha[i, j]),
                })
        return pd.DataFrame(records)


@dataclass
class IntegrationGrid:
    """积分网格定义

    Parameters
    ----------
    n_intervals : int
        水平区间数
    n_layers : int
        垂直层数
    ping_start / ping_end : np.ndarray
        每个水平区间的 ping 索引范围
    depth_start / depth_end : np.ndarray
        每个垂直层的深度范围 (米)
    """
    n_intervals: int
    n_layers: int
    ping_start: np.ndarray
    ping_end: np.ndarray
    depth_start: np.ndarray
    depth_end: np.ndarray


def _integration_depth(ds_Sv: xr.Dataset) -> np.ndarray:
    """保留逐 ping 的真实深度；缺失物理坐标时沿用公共坐标回退。"""
    for name in ("depth", "echo_range"):
        if name in ds_Sv:
            depth = ds_Sv[name]
            if "channel" in depth.dims:
                depth = depth.isel(channel=0)
            depth = depth.broadcast_like(ds_Sv["Sv"].isel(channel=0) if "channel" in ds_Sv["Sv"].dims else ds_Sv["Sv"])
            return depth.transpose("ping_time", "range_sample").values
    return np.broadcast_to(get_vertical_coords(ds_Sv), get_sv_array(ds_Sv).shape)


def create_integration_grid(
    ds_Sv: xr.Dataset,
    esu_type: ESUType = ESUType.PINGS,
    esu_size: float = 500,
    layer_width: float = 5.0,
    surface_depth_m: float = 0.0,
    max_depth_m: float | None = None,
) -> IntegrationGrid:
    """创建积分网格

    Parameters
    ----------
    ds_Sv : xr.Dataset
        Sv 数据集
    esu_type : ESUType
        EDSU 类型：PINGS（按 ping 数）、DISTANCE（按 GPS 航行距离，米）
    esu_size : float
        EDSU 大小：ping 数或距离（米）
    layer_width : float
        垂直层宽度 (米)
    surface_depth_m : float
        表线深度 (米)
    max_depth_m : float, optional
        最大深度限制 (米)，默认使用数据最大深度

    Returns
    -------
    IntegrationGrid
        积分网格定义

    Raises
    ------
    ValueError
        distance 模式下无 GPS 数据时抛出
    """
    if not np.isfinite(esu_size) or esu_size <= 0:
        raise ValueError("esu_size 必须为有限正数")
    if esu_type == ESUType.PINGS and (esu_size < 1 or esu_size != int(esu_size)):
        raise ValueError("ping 分段的 esu_size 必须为正整数")
    if not np.isfinite(layer_width) or layer_width <= 0:
        raise ValueError("layer_width 必须为有限正数")
    n_pings = ds_Sv.sizes["ping_time"]
    depth = _integration_depth(ds_Sv)

    # 确定深度范围
    d_min = surface_depth_m
    d_max = float(np.nanmax(depth)) if max_depth_m is None else max_depth_m

    if not np.isfinite(d_min) or not np.isfinite(d_max) or d_max <= d_min:
        raise ValueError("最大深度必须大于表线深度，且均为有限值")

    # 创建水平区间
    if esu_type == ESUType.PINGS:
        ping_starts = np.arange(0, n_pings, int(esu_size), dtype=int)
        ping_ends = np.minimum(ping_starts + int(esu_size), n_pings)
    elif esu_type == ESUType.DISTANCE:
        cum_dist = _get_cumulative_distance(ds_Sv)
        if cum_dist is None:
            raise ValueError("distance 分段需要 GPS 数据 (latitude/longitude)")
        if esu_size <= 0:
            raise ValueError(f"esu_size (距离) 必须为正数，当前值: {esu_size}")
        bin_edges = np.arange(0, cum_dist[-1] + esu_size, esu_size)
        bin_indices = np.digitize(cum_dist, bin_edges) - 1
        unique_bins = np.unique(bin_indices)
        ping_starts = np.array([np.where(bin_indices == b)[0][0] for b in unique_bins])
        ping_ends = np.array([np.where(bin_indices == b)[0][-1] + 1 for b in unique_bins])
    else:
        raise ValueError(f"不支持的 EDSU 类型: {esu_type}")

    # 创建垂直层
    depth_edges = np.arange(d_min, d_max + layer_width, layer_width)
    depth_edges[-1] = d_max
    depth_starts = depth_edges[:-1]
    depth_ends = depth_edges[1:]

    n_intervals = len(ping_starts)
    n_layers = len(depth_starts)

    logger.info(f"积分网格创建完成: {n_intervals} 个区间 × {n_layers} 层")
    logger.info(f"  EDSU 类型={esu_type.value}, 大小={esu_size}")
    logger.info(f"  深度范围: {d_min:.1f}m - {d_max:.1f}m, 层宽={layer_width}m")

    return IntegrationGrid(
        n_intervals=n_intervals,
        n_layers=n_layers,
        ping_start=ping_starts,
        ping_end=ping_ends,
        depth_start=depth_starts,
        depth_end=depth_ends,
    )


def _compute_abc_density(
    sv_layer: np.ndarray,
    dr_layer: np.ndarray,
    ts_default_db: float,
) -> tuple:
    """计算 ABC 与密度。

    Parameters
    ----------
    sv_layer : np.ndarray
        该层的 Sv 数组（可能含 NaN 掩码）
    dr_layer : np.ndarray
        深度分辨率数组
    ts_default_db : float
        默认目标强度 (dB)

    Returns
    -------
    (abc, density_ind_ha) : (float, float)
    """
    # ABC 积分与密度换算均复用 density.py 的单一来源
    from src.core.density import abc_integral, density_from_abc

    # EDSU 报告每 ping 垂直积分的均值，不随区间 ping 数增大。
    abc = float(np.mean(abc_integral(sv_to_linear(sv_layer), dr_layer, axis=1)))
    density_ha = density_from_abc(abc, ts_default_db)
    return abc, density_ha


def integrate(
    ds_Sv: xr.Dataset,
    grid: IntegrationGrid,
    min_threshold: float = -70.0,
    max_threshold: float = 0.0,
    exclude_below_bottom: bool = True,
    bottom_depth_m: np.ndarray | None = None,
    ts_default_db: float = -30.0,
    progress_callback: Callable[[int, int], None] | None = None,
) -> IntegrationResult:
    """按网格单元进行回声积分

    Parameters
    ----------
    ds_Sv : xr.Dataset
        Sv 数据集
    grid : IntegrationGrid
        积分网格定义
    min_threshold : float
        最小 Sv 阈值 (dB)，低于此值的样本被排除
    max_threshold : float
        最大 Sv 阈值 (dB)，高于此值的样本被排除
    exclude_below_bottom : bool
        是否排除底线以下的样本
    bottom_depth_m : np.ndarray, optional
        底部深度数组 (米)，shape=(n_pings,)
    ts_default_db : float
        默认目标强度 (dB)，用于密度估算
    progress_callback : callable, optional
        进度回调函数，接受 (current, total) 参数

    Returns
    -------
    IntegrationResult
        积分结果
    """
    Sv = get_sv_array(ds_Sv)  # (n_pings, n_samples)
    depth = _integration_depth(ds_Sv)
    if bottom_depth_m is not None:
        bottom_depth_m = np.asarray(bottom_depth_m)
        if bottom_depth_m.shape != (Sv.shape[0],):
            raise ValueError("底线必须为每个 ping 提供一个深度")

    # 与逐 ping ABC 共用厚度，保留各 ping 的采样间距。
    from src.core.density import _get_depth_resolution
    dr = _get_depth_resolution(ds_Sv)

    # 初始化结果数组
    shape = (grid.n_intervals, grid.n_layers)
    mean_Sv = np.full(shape, np.nan)
    abc = np.full(shape, np.nan)
    min_Sv = np.full(shape, np.nan)
    max_Sv = np.full(shape, np.nan)
    density_ind_ha = np.full(shape, np.nan)
    n_good = np.zeros(shape, dtype=int)
    n_excluded = np.zeros(shape, dtype=int)
    n_total = np.zeros(shape, dtype=int)

    # 逐 interval 逐 layer 积分
    total_cells = grid.n_intervals * grid.n_layers
    cell_count = 0

    for i in range(grid.n_intervals):
        p_start = grid.ping_start[i]
        p_end = grid.ping_end[i]

        # 提取该区间的 Sv 和 dr
        sv_interval = Sv[p_start:p_end, :]
        dr_interval = dr[p_start:p_end, :] if dr.ndim == 2 else np.broadcast_to(dr, sv_interval.shape)

        depth_interval = depth[p_start:p_end]
        valid_interval = np.isfinite(sv_interval) & (sv_interval >= min_threshold) & (sv_interval <= max_threshold)
        if exclude_below_bottom and bottom_depth_m is not None:
            bottom = bottom_depth_m[p_start:p_end, np.newaxis]
            valid_interval &= ~np.isfinite(bottom) | (depth_interval < bottom)

        for j in range(grid.n_layers):
            depth_mask = (depth_interval >= grid.depth_start[j]) & (depth_interval < grid.depth_end[j])
            valid_mask = valid_interval & depth_mask
            n_total[i, j] = int(np.sum(depth_mask))
            n_good[i, j] = int(np.sum(valid_mask))
            n_excluded[i, j] = n_total[i, j] - n_good[i, j]
            if n_good[i, j] > 0:
                sv_valid = sv_interval[valid_mask]
                mean_Sv[i, j] = float(10 * np.log10(np.mean(sv_to_linear(sv_valid))))
                min_Sv[i, j] = float(np.min(sv_valid))
                max_Sv[i, j] = float(np.max(sv_valid))
                sv_filtered = np.where(valid_mask, sv_interval, np.nan)
                abc[i, j], density_ind_ha[i, j] = _compute_abc_density(
                    sv_filtered, dr_interval, ts_default_db
                )
            cell_count += 1
            if progress_callback:
                progress_callback(cell_count, total_cells)

    logger.info(f"回声积分完成: {grid.n_intervals} 个区间 × {grid.n_layers} 层")
    logger.info(f"  有效样本比例: {np.sum(n_good) / max(np.sum(n_total), 1) * 100:.1f}%")

    return IntegrationResult(
        mean_Sv=mean_Sv,
        abc=abc,
        min_Sv=min_Sv,
        max_Sv=max_Sv,
        density_ind_ha=density_ind_ha,
        n_good=n_good,
        n_excluded=n_excluded,
        n_total=n_total,
        ping_start=grid.ping_start,
        ping_end=grid.ping_end,
        depth_start=grid.depth_start,
        depth_end=grid.depth_end,
    )


def integration_statistics_summary(result: IntegrationResult) -> dict:
    """积分结果统计摘要

    Returns
    -------
    dict
        包含全局统计信息
    """
    valid_mask = np.isfinite(result.mean_Sv) & (result.n_good > 0)
    if not np.any(valid_mask):
        return {"n_intervals": 0, "n_layers": 0, "total_good_samples": 0}

    return {
        "n_intervals": result.n_intervals,
        "n_layers": result.n_layers,
        "total_good_samples": int(np.sum(result.n_good)),
        "total_excluded_samples": int(np.sum(result.n_excluded)),
        "total_samples": int(np.sum(result.n_total)),
        "coverage_ratio": float(np.sum(result.n_good) / np.sum(result.n_total)) if np.sum(result.n_total) > 0 else 0.0,
        "mean_Sv_global": float(10 * np.log10(np.average(
            sv_to_linear(result.mean_Sv[valid_mask]), weights=result.n_good[valid_mask]
        ))),
        "abc_global": float(np.nanmean(result.abc[valid_mask])),
        "density_global": float(np.nanmean(result.density_ind_ha[valid_mask])),
    }
