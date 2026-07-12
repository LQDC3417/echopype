"""网格化分析模块：垂直分层 × 水平分段的网格统计

职责：
- 垂直方向：以表线为起点，按 1m/2m/5m 间隔划分深度层
- 水平方向：按 ping 数或 GPS 航行距离划分段
- 每个网格单元独立计算统计指标（mean_sv、ABC 等）
"""

import logging

import numpy as np
import pandas as pd
import xarray as xr

from src.core.utils import get_sv_array, get_vertical_coords, sv_to_linear

logger = logging.getLogger("fish_acoustics")


# ── 垂直分层 ──────────────────────────────────────────────

def _split_vertical(ds_Sv: xr.Dataset, surface_depth_m: float, interval_m: float) -> list[tuple[float, float]]:
    """从表线深度开始，按 interval_m 划分深度层。

    Parameters
    ----------
    ds_Sv : xr.Dataset
    surface_depth_m : float
        表线深度（米）
    interval_m : float
        垂直间隔（米）

    Returns
    -------
    list[tuple[float, float]]
        [(d_lo, d_hi), ...] 深度层列表
    """
    depth = get_vertical_coords(ds_Sv)
    d_max = float(np.nanmax(depth))

    # 从表线开始，向上取整到 interval_m 的倍数
    d_start = surface_depth_m
    bins = np.arange(d_start, d_max + interval_m, interval_m)

    layers = []
    for i in range(len(bins) - 1):
        d_lo = float(bins[i])
        d_hi = float(bins[i + 1])
        # 检查该深度层是否有数据
        if np.any((depth >= d_lo) & (depth < d_hi)):
            layers.append((d_lo, d_hi))

    logger.info(f"垂直分层完成: {len(layers)} 层, 起点={surface_depth_m}m, 间隔={interval_m}m")
    return layers


# ── 水平分段 ──────────────────────────────────────────────

def _split_by_ping(ds_Sv: xr.Dataset, pings_per_segment: int) -> list[tuple[int, int]]:
    """按固定 ping 数划分水平段。

    Parameters
    ----------
    ds_Sv : xr.Dataset
    pings_per_segment : int
        每段 ping 数

    Returns
    -------
    list[tuple[int, int]]
        [(ping_start, ping_end), ...]
    """
    n_pings = ds_Sv.sizes["ping_time"]
    segments = []
    for i in range(0, n_pings, pings_per_segment):
        end = min(i + pings_per_segment, n_pings)
        segments.append((i, end))

    logger.info(f"水平分段完成: {len(segments)} 段, 每段 {pings_per_segment} pings")
    return segments


def _split_by_distance(ds_Sv: xr.Dataset, distance_m: float) -> list[tuple[int, int]]:
    """按 GPS 航行距离划分水平段。

    Parameters
    ----------
    ds_Sv : xr.Dataset
    distance_m : float
        每段距离（米）

    Returns
    -------
    list[tuple[int, int]]
        [(ping_start, ping_end), ...]
    """
    cumulative_dist = _get_cumulative_distance(ds_Sv)
    if cumulative_dist is None:
        logger.warning("无 GPS 数据，回退到按 ping 数分段（每段 100 ping）")
        return _split_by_ping(ds_Sv, 100)

    n_pings = len(cumulative_dist)
    segments = []
    seg_start_idx = 0

    for i in range(1, n_pings):
        if cumulative_dist[i] - cumulative_dist[seg_start_idx] >= distance_m:
            segments.append((seg_start_idx, i))
            seg_start_idx = i

    # 最后一段
    if seg_start_idx < n_pings:
        segments.append((seg_start_idx, n_pings))

    total_dist = cumulative_dist[-1]
    logger.info(f"水平分段完成: {len(segments)} 段, 每段 {distance_m}m, 总距离 {total_dist:.0f}m")
    return segments


# ── GPS 距离计算 ──────────────────────────────────────────

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

    # 验证坐标有效性
    valid_count = np.sum(np.isfinite(lat) & np.isfinite(lon))
    if valid_count < 2:
        logger.warning(f"GPS 数据有效点不足: {valid_count}")
        return None

    # 向量化计算相邻点距离
    distances = np.zeros(len(lat))
    mask = np.isfinite(lat) & np.isfinite(lon)
    for i in range(1, len(lat)):
        if mask[i] and mask[i-1]:
            distances[i] = _haversine(lat[i-1], lon[i-1], lat[i], lon[i])

    return np.cumsum(distances)


def _extract_gps(ds_Sv: xr.Dataset) -> tuple[np.ndarray | None, np.ndarray | None]:
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

    # 处理多维坐标（取第一个 channel）
    if lat.ndim > 1:
        # 优先用 xarray 维度名判断；否则回退到 shape 启发式
        lat_arr = ds_Sv["latitude"] if "latitude" in ds_Sv else None
        if lat_arr is not None and "channel" in lat_arr.dims:
            ch_dim = list(lat_arr.dims).index("channel")
            idx = [0] * lat.ndim
            idx[ch_dim] = slice(None)
            # 取非 channel 维度的第一个元素
            lat = lat[tuple(slice(0, 1) if d != ch_dim else slice(None) for d in range(lat.ndim))]
            lon = lon[tuple(slice(0, 1) if d != ch_dim else slice(None) for d in range(lon.ndim))]
            lat = lat.squeeze()
            lon = lon.squeeze()
        else:
            # 启发式：较短的维度是 channel，取第一个
            if lat.ndim == 2:
                if lat.shape[1] < lat.shape[0]:
                    lat, lon = lat[:, 0], lon[:, 0]
                else:
                    lat, lon = lat[0, :], lon[0, :]

    return lat, lon


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine 公式计算两点间距离（米）。"""
    R = 6371000  # 地球半径（米）
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2) ** 2
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


# ── 网格创建 ──────────────────────────────────────────────

def create_grid(
    ds_Sv: xr.Dataset,
    surface_depth_m: float,
    vertical_interval_m: float,
    horizontal_interval: float,
    method: str = "ping",
) -> list[dict]:
    """创建网格划分。

    Parameters
    ----------
    ds_Sv : xr.Dataset
    surface_depth_m : float
        表线深度（米）
    vertical_interval_m : float
        垂直间隔（米）：1, 2, 5
    horizontal_interval : float
        水平间隔：ping 数或距离（米）
    method : str
        "ping" — 按 ping 数
        "distance" — 按 GPS 航行距离

    Returns
    -------
    list[dict]
        网格单元列表，每个包含 ping_start, ping_end, depth_lo, depth_hi
    """
    vertical_layers = _split_vertical(ds_Sv, surface_depth_m, vertical_interval_m)

    if method == "ping":
        horizontal_segments = _split_by_ping(ds_Sv, int(horizontal_interval))
    elif method == "distance":
        horizontal_segments = _split_by_distance(ds_Sv, horizontal_interval)
    else:
        raise ValueError(f"不支持的水平分段方法: {method}")

    grid_cells = []
    for h_start, h_end in horizontal_segments:
        for v_lo, v_hi in vertical_layers:
            grid_cells.append({
                "ping_start": h_start,
                "ping_end": h_end,
                "depth_lo": v_lo,
                "depth_hi": v_hi,
            })

    logger.info(f"网格创建完成: {len(horizontal_segments)} × {len(vertical_layers)} = {len(grid_cells)} 个单元")
    return grid_cells


# ── 网格统计 ──────────────────────────────────────────────

def compute_grid_stats(
    ds_Sv: xr.Dataset,
    grid_cells: list[dict],
) -> pd.DataFrame:
    """计算每个网格单元的统计指标。

    Parameters
    ----------
    ds_Sv : xr.Dataset
    grid_cells : list[dict]
        由 create_grid 返回的网格单元列表

    Returns
    -------
    pd.DataFrame
        每行一个网格单元，包含 cell_id, ping_start, ping_end, depth_lo, depth_hi,
        mean_sv, median_sv, std_sv, n_valid, abc
    """
    Sv = get_sv_array(ds_Sv)  # (n_pings, n_samples)
    depth = get_vertical_coords(ds_Sv)  # (n_samples,)
    ping_time = ds_Sv["ping_time"].values

    # 深度分辨率（与 density.py 统一使用 region.get_echo_range_1d）
    from src.core.region import get_echo_range_1d
    er = get_echo_range_1d(ds_Sv)
    if er is not None:
        dr = np.abs(np.diff(er))
        dr = np.append(dr, dr[-1])
        # broadcast 到 2D
        if Sv.ndim == 2 and dr.ndim == 1:
            dr = np.broadcast_to(dr, Sv.shape)
    else:
        dr = np.ones_like(Sv)

    records = []
    for i, cell in enumerate(grid_cells):
        p_start = cell["ping_start"]
        p_end = cell["ping_end"]
        d_lo = cell["depth_lo"]
        d_hi = cell["depth_hi"]

        # 深度掩码
        d_mask = (depth >= d_lo) & (depth < d_hi)
        if not np.any(d_mask):
            records.append(_empty_cell(i, p_start, p_end, d_lo, d_hi, ping_time))
            continue

        # 提取子数组
        sv_cell = Sv[p_start:p_end, :]
        dr_cell = dr[p_start:p_end, :]
        sv_cell = sv_cell[:, d_mask]
        dr_cell = dr_cell[:, d_mask]

        # 统计
        valid_mask = np.isfinite(sv_cell)
        if not np.any(valid_mask):
            records.append(_empty_cell(i, p_start, p_end, d_lo, d_hi, ping_time))
            continue

        sv_valid = sv_cell[valid_mask]
        # ABC = 4π × ∫ Sv_linear × dr（向量化：先线性化，再乘 dr，NaN 位置置零后求和）
        abc = float(4 * np.pi * np.nansum(sv_to_linear(sv_cell) * dr_cell))

        records.append({
            "cell_id": i,
            "ping_start": int(p_start),
            "ping_end": int(p_end),
            "ping_time_start": str(ping_time[p_start])[:19] if p_start < len(ping_time) else "",
            "ping_time_end": str(ping_time[min(p_end-1, len(ping_time)-1)])[:19] if p_end > 0 else "",
            "depth_lo": d_lo,
            "depth_hi": d_hi,
            "mean_sv": float(np.mean(sv_valid)),
            "median_sv": float(np.median(sv_valid)),
            "std_sv": float(np.std(sv_valid)),
            "n_pings": p_end - p_start,
            "n_valid": len(sv_valid),
            "abc": abc,
        })

    result = pd.DataFrame(records)
    logger.info(f"网格统计完成: {len(result)} 个单元")
    return result


def _empty_cell(cell_id, p_start, p_end, d_lo, d_hi, ping_time):
    """空网格单元的默认值。"""
    return {
        "cell_id": cell_id,
        "ping_start": int(p_start),
        "ping_end": int(p_end),
        "ping_time_start": str(ping_time[p_start])[:19] if p_start < len(ping_time) else "",
        "ping_time_end": str(ping_time[min(p_end-1, len(ping_time)-1)])[:19] if p_end > 0 else "",
        "depth_lo": d_lo,
        "depth_hi": d_hi,
        "mean_sv": np.nan,
        "median_sv": np.nan,
        "std_sv": np.nan,
        "n_pings": p_end - p_start,
        "n_valid": 0,
        "abc": np.nan,
    }


def compute_grid_density(
    ds_Sv: xr.Dataset,
    grid_cells: list[dict],
    config: dict,
) -> pd.DataFrame:
    """计算每个网格单元的密度估算。

    Parameters
    ----------
    ds_Sv : xr.Dataset
    grid_cells : list[dict]
    config : dict

    Returns
    -------
    pd.DataFrame
        每行一个网格单元，包含 density_ind_m2, density_ind_ha, biomass_kg_ha
    """
    density_cfg = config.get("density", {})
    ts_default = density_cfg.get("ts_default", -30.0)
    avg_weight_kg = density_cfg.get("avg_weight_kg", 0.5)
    sigma_bs = 10 ** (ts_default / 10)

    stats_df = compute_grid_stats(ds_Sv, grid_cells)

    records = []
    for _, row in stats_df.iterrows():
        abc = row["abc"]
        if np.isnan(abc):
            density_m2 = np.nan
            density_ha = np.nan
            biomass = np.nan
        else:
            density_m2 = abc / (4 * np.pi * sigma_bs)
            density_ha = density_m2 * 10000
            biomass = density_ha * avg_weight_kg

        records.append({
            "cell_id": row["cell_id"],
            "ping_start": row["ping_start"],
            "ping_end": row["ping_end"],
            "depth_lo": row["depth_lo"],
            "depth_hi": row["depth_hi"],
            "mean_sv": row["mean_sv"],
            "abc": abc,
            "density_ind_m2": density_m2,
            "density_ind_ha": density_ha,
            "biomass_kg_ha": biomass,
        })

    result = pd.DataFrame(records)
    logger.info(f"网格密度估算完成: {len(result)} 个单元")
    return result
