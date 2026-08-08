"""网格化分析模块：垂直分层 × 水平分段的网格统计

职责：
- 垂直方向：以表线为起点，按 1m/2m/5m 间隔划分深度层
- 水平方向：按 ping 数或 GPS 航行距离划分段
- 每个网格单元独立计算统计指标（mean_sv、ABC 等）
"""

import logging
from typing import Callable, Optional, Union

import numpy as np
import pandas as pd
import xarray as xr

from src.core.utils import get_sv_array, get_vertical_coords, sv_to_linear

logger = logging.getLogger("fish_acoustics")


# ── 垂直分层 ──────────────────────────────────────────────

def _split_vertical(
    ds_Sv: xr.Dataset,
    surface_depth_m: float,
    interval_m: float,
    mode: str = "linear",
    depth_bins: Optional[list[float]] = None,
    max_depth: Optional[float] = None,
) -> list[tuple[float, float]]:
    """从表线深度开始，按指定模式划分深度层。

    Parameters
    ----------
    ds_Sv : xr.Dataset
    surface_depth_m : float
        表线深度（米）
    interval_m : float
        垂直间隔（米）
    mode : str, optional
        分层模式: "linear"（等间隔）、"logarithmic"（对数间隔）、"custom"（自定义边界）
        默认为 "linear"
    depth_bins : list[float], optional
        自定义深度边界列表，当 mode="custom" 时使用
    max_depth : float, optional
        最大深度限制，超过此深度的数据将被忽略

    Returns
    -------
    list[tuple[float, float]]
        [(d_lo, d_hi), ...] 深度层列表
    """
    # 参数验证
    if interval_m <= 0:
        raise ValueError(f"interval_m 必须为正数，当前值: {interval_m}")
    
    depth = get_vertical_coords(ds_Sv)
    d_max = float(np.nanmax(depth))
    
    # 应用最大深度限制
    if max_depth is not None and max_depth > 0:
        d_max = min(d_max, max_depth)
    
    # 根据模式生成深度边界
    if mode == "custom":
        if depth_bins is None or len(depth_bins) < 2:
            raise ValueError("自定义模式需要至少提供2个深度边界")
        bins = np.array(depth_bins)
        # 确保边界有序
        bins = np.sort(bins)
        # 确保包含最大深度
        if bins[-1] < d_max:
            bins = np.append(bins, d_max)
    elif mode == "logarithmic":
        # 对数间隔：从表线开始，按对数尺度分层
        # 确保起始深度大于0
        if surface_depth_m <= 0:
            surface_depth_m = 0.1
        # 使用对数间隔，从 log10(surface_depth_m) 到 log10(d_max)
        log_start = np.log10(surface_depth_m)
        log_end = np.log10(d_max)
        # 每层在对数尺度上间隔相等
        n_layers = max(1, int((log_end - log_start) / np.log10(interval_m + 1)))
        bins = np.logspace(log_start, log_end, n_layers + 1)
    else:  # linear
        # 线性间隔（原有逻辑）
        d_start = surface_depth_m
        bins = np.arange(d_start, d_max + interval_m, interval_m)
    
    # 生成深度层
    layers = []
    for i in range(len(bins) - 1):
        d_lo = float(bins[i])
        d_hi = float(bins[i + 1])
        
        # 确保深度层有效（d_hi > d_lo）
        if d_hi <= d_lo:
            continue
        
        # 检查该深度层是否有数据
        if np.any((depth >= d_lo) & (depth < d_hi)):
            layers.append((d_lo, d_hi))
    
    # 如果没有任何层，添加一个默认层
    if not layers:
        layers.append((surface_depth_m, d_max))
        logger.warning(f"未找到有效深度层，添加默认层: {surface_depth_m}m - {d_max}m")
    
    logger.info(f"垂直分层完成: {len(layers)} 层, 起点={surface_depth_m}m, 间隔={interval_m}m, 模式={mode}")
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
    # 参数验证
    if pings_per_segment <= 0:
        raise ValueError(f"pings_per_segment 必须为正整数，当前值: {pings_per_segment}")
    
    n_pings = ds_Sv.sizes["ping_time"]
    
    # 使用列表推导式优化性能
    segments = [
        (i, min(i + pings_per_segment, n_pings))
        for i in range(0, n_pings, pings_per_segment)
    ]
    
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
    # 参数验证
    if distance_m <= 0:
        raise ValueError(f"distance_m 必须为正数，当前值: {distance_m}")
    
    cumulative_dist = _get_cumulative_distance(ds_Sv)
    if cumulative_dist is None:
        logger.warning("无 GPS 数据，回退到按 ping 数分段（每段 100 ping）")
        return _split_by_ping(ds_Sv, 100)

    n_pings = len(cumulative_dist)
    
    # 使用向量化操作优化性能
    # 计算每个点到起始点的距离
    dist_from_start = cumulative_dist - cumulative_dist[0]
    
    # 计算每个点应该属于哪个分段
    segment_indices = np.floor(dist_from_start / distance_m).astype(int)
    
    # 获取唯一分段索引
    unique_segments = np.unique(segment_indices)
    
    segments = []
    for seg_idx in unique_segments:
        # 找到该分段的所有 ping 索引
        ping_indices = np.where(segment_indices == seg_idx)[0]
        if len(ping_indices) > 0:
            start_idx = ping_indices[0]
            end_idx = ping_indices[-1] + 1  # 包含最后一个 ping
            segments.append((start_idx, end_idx))
    
    # 确保最后一个分段覆盖到末尾
    if segments and segments[-1][1] < n_pings:
        segments.append((segments[-1][1], n_pings))
    
    total_dist = cumulative_dist[-1] - cumulative_dist[0]
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
    # 创建掩码，只对有效点计算距离
    mask = np.isfinite(lat) & np.isfinite(lon)
    
    # 初始化距离数组
    distances = np.zeros(len(lat))
    
    # 向量化计算相邻点距离
    # 找到有效点的索引
    valid_indices = np.where(mask)[0]
    
    if len(valid_indices) < 2:
        return None
    
    # 计算有效点之间的距离
    for i in range(1, len(valid_indices)):
        idx_prev = valid_indices[i-1]
        idx_curr = valid_indices[i]
        distances[idx_curr] = _haversine(lat[idx_prev], lon[idx_prev], lat[idx_curr], lon[idx_curr])
    
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
    vertical_mode: str = "linear",
    depth_bins: Optional[list[float]] = None,
    max_depth: Optional[float] = None,
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
    vertical_mode : str, optional
        垂直分层模式: "linear"、"logarithmic"、"custom"
    depth_bins : list[float], optional
        自定义深度边界列表，当 vertical_mode="custom" 时使用
    max_depth : float, optional
        最大深度限制

    Returns
    -------
    list[dict]
        网格单元列表，每个包含 ping_start, ping_end, depth_lo, depth_hi
    """
    vertical_layers = _split_vertical(
        ds_Sv, surface_depth_m, vertical_interval_m,
        mode=vertical_mode, depth_bins=depth_bins, max_depth=max_depth
    )

    if method == "ping":
        horizontal_segments = _split_by_ping(ds_Sv, int(horizontal_interval))
    elif method == "distance":
        horizontal_segments = _split_by_distance(ds_Sv, horizontal_interval)
    else:
        raise ValueError(f"不支持的水平分段方法: {method}")

    # 提取 GPS 坐标，用于计算每段的中心经纬度
    lat_arr, lon_arr = _extract_gps(ds_Sv)

    grid_cells = []
    cell_id = 0
    for h_start, h_end in horizontal_segments:
        # 计算该水平段的中心经纬度
        center_lat, center_lon = _segment_center_gps(lat_arr, lon_arr, h_start, h_end)

        for v_lo, v_hi in vertical_layers:
            grid_cells.append({
                "cell_id": cell_id,
                "ping_start": h_start,
                "ping_end": h_end,
                "depth_lo": v_lo,
                "depth_hi": v_hi,
                "latitude": center_lat,
                "longitude": center_lon,
            })
            cell_id += 1

    logger.info(f"网格创建完成: {len(horizontal_segments)} × {len(vertical_layers)} = {len(grid_cells)} 个单元")
    return grid_cells


def _segment_center_gps(
    lat: np.ndarray | None,
    lon: np.ndarray | None,
    ping_start: int,
    ping_end: int,
) -> tuple[float | None, float | None]:
    """计算水平段内有效 GPS 坐标的中心点。

    Parameters
    ----------
    lat, lon : np.ndarray or None
        全量 GPS 坐标数组
    ping_start, ping_end : int
        该水平段的 ping 索引范围 [start, end)

    Returns
    -------
    tuple[float or None, float or None]
        (latitude, longitude) 中心点；无有效数据时返回 (None, None)
    """
    if lat is None or lon is None:
        return None, None

    # 安全截取，防止越界
    s = max(0, ping_start)
    e = min(len(lat), ping_end)
    if s >= e:
        return None, None

    seg_lat = lat[s:e]
    seg_lon = lon[s:e]

    # 只取有限值的坐标求均值
    valid = np.isfinite(seg_lat) & np.isfinite(seg_lon)
    if not np.any(valid):
        return None, None

    return float(np.mean(seg_lat[valid])), float(np.mean(seg_lon[valid]))


# ── 网格统计 ──────────────────────────────────────────────

def compute_grid_stats(
    ds_Sv: xr.Dataset,
    grid_cells: list[dict],
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> pd.DataFrame:
    """计算每个网格单元的统计指标。

    Parameters
    ----------
    ds_Sv : xr.Dataset
    grid_cells : list[dict]
        由 create_grid 返回的网格单元列表
    progress_callback : callable, optional
        进度回调函数，接受 (current, total) 参数

    Returns
    -------
    pd.DataFrame
        每行一个网格单元，包含 cell_id, ping_start, ping_end, depth_lo, depth_hi,
        latitude, longitude, mean_sv, median_sv, std_sv, n_valid, abc, 以及额外的统计指标
    """
    if not grid_cells:
        logger.warning("没有网格单元需要处理")
        return pd.DataFrame()
    
    Sv = get_sv_array(ds_Sv)  # (n_pings, n_samples)
    depth = get_vertical_coords(ds_Sv)  # (n_samples,)
    ping_time = ds_Sv["ping_time"].values

    # 提取 GPS 坐标，用于每段中心经纬度
    lat_arr, lon_arr = _extract_gps(ds_Sv)

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
    total_cells = len(grid_cells)
    
    for i, cell in enumerate(grid_cells):
        p_start = cell["ping_start"]
        p_end = cell["ping_end"]
        d_lo = cell["depth_lo"]
        d_hi = cell["depth_hi"]

        # 优先使用 grid_cells 中预计算的 GPS 坐标，否则实时计算
        if "latitude" in cell:
            center_lat = cell.get("latitude")
            center_lon = cell.get("longitude")
        else:
            center_lat, center_lon = _segment_center_gps(lat_arr, lon_arr, p_start, p_end)

        # 深度掩码
        d_mask = (depth >= d_lo) & (depth < d_hi)
        if not np.any(d_mask):
            records.append(_empty_cell(i, p_start, p_end, d_lo, d_hi, ping_time,
                                       latitude=center_lat, longitude=center_lon))
            _update_progress(progress_callback, i + 1, total_cells)
            continue

        # 提取子数组
        sv_cell = Sv[p_start:p_end, :]
        dr_cell = dr[p_start:p_end, :]
        sv_cell = sv_cell[:, d_mask]
        dr_cell = dr_cell[:, d_mask]

        # 统计
        valid_mask = np.isfinite(sv_cell)
        if not np.any(valid_mask):
            records.append(_empty_cell(i, p_start, p_end, d_lo, d_hi, ping_time,
                                       latitude=center_lat, longitude=center_lon))
            _update_progress(progress_callback, i + 1, total_cells)
            continue

        sv_valid = sv_cell[valid_mask]

        # 向量化计算统计指标
        # 计算线性值用于 ABC
        # 优化内存使用：直接计算线性值，避免临时数组
        sv_linear = np.nan_to_num(sv_cell, nan=0.0, posinf=0.0, neginf=0.0)
        sv_linear = np.power(10, sv_linear / 10, out=sv_linear)
        abc = float(4 * np.pi * np.nansum(sv_linear * dr_cell))

        # 计算更多统计指标
        mean_sv = float(np.mean(sv_valid))
        median_sv = float(np.median(sv_valid))
        std_sv = float(np.std(sv_valid))

        # 计算百分位数（25%，75%）
        p25 = float(np.percentile(sv_valid, 25))
        p75 = float(np.percentile(sv_valid, 75))

        # 计算变异系数（标准差/均值）
        cv = std_sv / abs(mean_sv) if mean_sv != 0 and np.isfinite(mean_sv) else np.nan

        # 计算数据覆盖率
        total_cells_in_grid = sv_cell.size
        coverage = len(sv_valid) / total_cells_in_grid if total_cells_in_grid > 0 else 0.0

        records.append({
            "cell_id": i,
            "ping_start": int(p_start),
            "ping_end": int(p_end),
            "ping_time_start": str(ping_time[p_start])[:19] if p_start < len(ping_time) else "",
            "ping_time_end": str(ping_time[min(p_end-1, len(ping_time)-1)])[:19] if p_end > 0 else "",
            "depth_lo": d_lo,
            "depth_hi": d_hi,
            "latitude": center_lat,
            "longitude": center_lon,
            "mean_sv": mean_sv,
            "median_sv": median_sv,
            "std_sv": std_sv,
            "p25_sv": p25,
            "p75_sv": p75,
            "cv_sv": cv,
            "n_pings": p_end - p_start,
            "n_valid": len(sv_valid),
            "coverage": coverage,
            "abc": abc,
        })
        
        _update_progress(progress_callback, i + 1, total_cells)

    result = pd.DataFrame(records)
    
    # 添加元数据
    result.attrs["grid_cells_count"] = len(grid_cells)
    result.attrs["total_pings"] = ds_Sv.sizes["ping_time"]
    result.attrs["total_samples"] = len(depth)
    result.attrs["depth_range"] = (float(np.nanmin(depth)), float(np.nanmax(depth)))
    
    logger.info(f"网格统计完成: {len(result)} 个单元")
    return result


def _update_progress(callback: Optional[Callable[[int, int], None]], current: int, total: int):
    """更新进度回调。"""
    if callback is not None:
        try:
            callback(current, total)
        except Exception as e:
            logger.warning(f"进度回调执行失败: {e}")


def _empty_cell(cell_id, p_start, p_end, d_lo, d_hi, ping_time,
                latitude=None, longitude=None):
    """空网格单元的默认值。"""
    return {
        "cell_id": cell_id,
        "ping_start": int(p_start),
        "ping_end": int(p_end),
        "ping_time_start": str(ping_time[p_start])[:19] if p_start < len(ping_time) else "",
        "ping_time_end": str(ping_time[min(p_end-1, len(ping_time)-1)])[:19] if p_end > 0 else "",
        "depth_lo": d_lo,
        "depth_hi": d_hi,
        "latitude": latitude,
        "longitude": longitude,
        "mean_sv": np.nan,
        "median_sv": np.nan,
        "std_sv": np.nan,
        "p25_sv": np.nan,
        "p75_sv": np.nan,
        "cv_sv": np.nan,
        "n_pings": p_end - p_start,
        "n_valid": 0,
        "coverage": 0.0,
        "abc": np.nan,
    }


def compute_grid_density(
    ds_Sv: xr.Dataset,
    grid_cells: list[dict],
    config: dict,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> pd.DataFrame:
    """计算每个网格单元的密度估算。

    Parameters
    ----------
    ds_Sv : xr.Dataset
    grid_cells : list[dict]
    config : dict
    progress_callback : callable, optional
        进度回调函数

    Returns
    -------
    pd.DataFrame
        每行一个网格单元，包含 cell_id, ping_start, ping_end, depth_lo, depth_hi,
        latitude, longitude, mean_sv, abc, density_ind_m2, density_ind_ha, biomass_kg_ha
    """
    density_cfg = config.get("density", {})
    ts_default = density_cfg.get("ts_default", -30.0)
    avg_weight_kg = density_cfg.get("avg_weight_kg", 0.5)
    sigma_bs = 10 ** (ts_default / 10)

    stats_df = compute_grid_stats(ds_Sv, grid_cells, progress_callback)

    # 使用向量化操作计算密度
    abc_values = stats_df["abc"].values
    valid_mask = ~np.isnan(abc_values)
    
    # 初始化结果数组
    density_m2 = np.full(len(stats_df), np.nan)
    density_ha = np.full(len(stats_df), np.nan)
    biomass = np.full(len(stats_df), np.nan)
    
    # 向量化计算
    if np.any(valid_mask):
        density_m2[valid_mask] = abc_values[valid_mask] / (4 * np.pi * sigma_bs)
        density_ha[valid_mask] = density_m2[valid_mask] * 10000
        biomass[valid_mask] = density_ha[valid_mask] * avg_weight_kg

    # 创建结果 DataFrame（包含经纬度）
    export_cols = ["cell_id", "ping_start", "ping_end", "depth_lo", "depth_hi",
                   "latitude", "longitude", "mean_sv", "abc"]
    result = stats_df[export_cols].copy()
    result["density_ind_m2"] = density_m2
    result["density_ind_ha"] = density_ha
    result["biomass_kg_ha"] = biomass
    
    logger.info(f"网格密度估算完成: {len(result)} 个单元")
    return result

