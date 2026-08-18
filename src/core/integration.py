"""回声积分模块：按网格单元进行标准化积分分析

参考：pyEcholab integration.py
功能：
- 按 ESU（Elementary Sampling Unit）分组
- 按深度层逐层积分
- 计算每层的 mean_Sv、NASC、min/max_Sv、有效样本数等
- 支持多种 ESU 类型（pings、seconds、nmi）
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

import numpy as np
import pandas as pd
import xarray as xr

from src.core.region import get_echo_range_1d
from src.core.utils import get_sv_array, get_vertical_coords, sv_to_linear

logger = logging.getLogger("fish_acoustics")

# 物理常数
FOUR_PI = 4 * np.pi
NMI_TO_M = 1852  # 1 海里 = 1852 米


class ESUType(Enum):
    """ESU 类型枚举"""
    PINGS = "pings"
    SECONDS = "seconds"
    NMI = "nmi"


@dataclass
class IntegrationResult:
    """回声积分结果

    按 (n_intervals, n_layers) 组织的积分统计结果。
    每个 interval 代表一个水平 ESU，每个 layer 代表一个垂直深度层。

    Attributes
    ----------
    mean_Sv : np.ndarray
        平均体积散射强度 (dB)，shape=(n_intervals, n_layers)
    nasc : np.ndarray
        海里面积散射系数 (m²/nmi²)，shape=(n_intervals, n_layers)
    min_Sv : np.ndarray
        最小 Sv (dB)，shape=(n_intervals, n_layers)
    max_Sv : np.ndarray
        最大 Sv (dB)，shape=(n_intervals, n_layers)
    n_good : np.ndarray
        有效样本数，shape=(n_intervals, n_layers)
    n_excluded : np.ndarray
        排除样本数（低于阈值或 NaN），shape=(n_intervals, n_layers)
    n_total : np.ndarray
        总样本数，shape=(n_intervals, n_layers)
    ping_start : np.ndarray
        每个 interval 的起始 ping 索引
    ping_end : np.ndarray
        每个 interval 的结束 ping 索引
    depth_start : np.ndarray
        每层的起始深度 (米)
    depth_end : np.ndarray
        每层的结束深度 (米)
    """
    mean_Sv: np.ndarray
    nasc: np.ndarray
    min_Sv: np.ndarray
    max_Sv: np.ndarray
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
                    "nasc": float(self.nasc[i, j]),
                    "min_Sv": float(self.min_Sv[i, j]),
                    "max_Sv": float(self.max_Sv[i, j]),
                    "n_good": int(self.n_good[i, j]),
                    "n_excluded": int(self.n_excluded[i, j]),
                    "n_total": int(self.n_total[i, j]),
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
    ping_start : np.ndarray
        每个 interval 的起始 ping 索引
    ping_end : np.ndarray
        每个 interval 的结束 ping 索引
    depth_start : np.ndarray
        每层的起始深度 (米)
    depth_end : np.ndarray
        每层的结束深度 (米)
    """
    n_intervals: int
    n_layers: int
    ping_start: np.ndarray
    ping_end: np.ndarray
    depth_start: np.ndarray
    depth_end: np.ndarray


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
        ESU 类型：PINGS（按 ping 数）、SECONDS（按时间）、NMI（按海里）
    esu_size : float
        ESU 大小：ping 数、秒数或海里数
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
    """
    n_pings = ds_Sv.sizes["ping_time"]
    depth = get_vertical_coords(ds_Sv)

    # 确定深度范围
    d_min = surface_depth_m
    d_max = float(np.nanmax(depth)) if max_depth_m is None else max_depth_m

    # 创建水平区间
    if esu_type == ESUType.PINGS:
        ping_starts = np.arange(0, n_pings, int(esu_size), dtype=int)
        ping_ends = np.minimum(ping_starts + int(esu_size), n_pings)
    elif esu_type == ESUType.SECONDS:
        ping_time = ds_Sv["ping_time"].values
        if np.issubdtype(ping_time.dtype, np.datetime64):
            time_s = (ping_time - ping_time[0]) / np.timedelta64(1, 's')
        else:
            time_s = ping_time.astype(float)
        # 按时间间隔划分
        bin_edges = np.arange(0, time_s[-1] + esu_size, esu_size)
        bin_indices = np.digitize(time_s, bin_edges) - 1
        unique_bins = np.unique(bin_indices)
        ping_starts = np.array([np.where(bin_indices == b)[0][0] for b in unique_bins])
        ping_ends = np.array([np.where(bin_indices == b)[0][-1] + 1 for b in unique_bins])
    elif esu_type == ESUType.NMI:
        # 需要 GPS 数据计算距离
        from src.core.grid import _get_cumulative_distance
        cum_dist = _get_cumulative_distance(ds_Sv)
        if cum_dist is None:
            logger.warning("无 GPS 数据，回退到按 ping 数分段（每段 500 ping）")
            return create_integration_grid(ds_Sv, ESUType.PINGS, 500, layer_width, surface_depth_m, max_depth_m)
        dist_nmi = cum_dist / NMI_TO_M
        bin_edges = np.arange(0, dist_nmi[-1] + esu_size, esu_size)
        bin_indices = np.digitize(dist_nmi, bin_edges) - 1
        unique_bins = np.unique(bin_indices)
        ping_starts = np.array([np.where(bin_indices == b)[0][0] for b in unique_bins])
        ping_ends = np.array([np.where(bin_indices == b)[0][-1] + 1 for b in unique_bins])
    else:
        raise ValueError(f"不支持的 ESU 类型: {esu_type}")

    # 创建垂直层
    depth_edges = np.arange(d_min, d_max + layer_width, layer_width)
    depth_starts = depth_edges[:-1]
    depth_ends = depth_edges[1:]

    n_intervals = len(ping_starts)
    n_layers = len(depth_starts)

    logger.info(f"积分网格创建完成: {n_intervals} 个区间 × {n_layers} 层")
    logger.info(f"  ESU 类型={esu_type.value}, 大小={esu_size}")
    logger.info(f"  深度范围: {d_min:.1f}m - {d_max:.1f}m, 层宽={layer_width}m")

    return IntegrationGrid(
        n_intervals=n_intervals,
        n_layers=n_layers,
        ping_start=ping_starts,
        ping_end=ping_ends,
        depth_start=depth_starts,
        depth_end=depth_ends,
    )


def integrate(
    ds_Sv: xr.Dataset,
    grid: IntegrationGrid,
    min_threshold: float = -70.0,
    max_threshold: float = 0.0,
    exclude_below_bottom: bool = True,
    bottom_depth_m: np.ndarray | None = None,
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
    progress_callback : callable, optional
        进度回调函数，接受 (current, total) 参数

    Returns
    -------
    IntegrationResult
        积分结果
    """
    # 复制数组，避免后续底部掩码原地改写 Sv 视图时污染原始 ds_Sv
    Sv = get_sv_array(ds_Sv).copy()  # (n_pings, n_samples)
    depth = get_vertical_coords(ds_Sv)  # (n_samples,)
    _n_pings, n_samples = Sv.shape

    # 计算深度分辨率
    er = get_echo_range_1d(ds_Sv)
    if er is not None:
        dr = np.abs(np.diff(er))
        dr = np.append(dr, dr[-1])
    else:
        dr = np.ones(n_samples)

    # 初始化结果数组
    shape = (grid.n_intervals, grid.n_layers)
    mean_Sv = np.full(shape, np.nan)
    nasc = np.full(shape, np.nan)
    min_Sv = np.full(shape, np.nan)
    max_Sv = np.full(shape, np.nan)
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

        # 底部掩码（如果提供）
        if exclude_below_bottom and bottom_depth_m is not None:
            bot_interval = bottom_depth_m[p_start:p_end]
            # 为每个 ping 创建底部掩码
            for j in range(grid.n_layers):
                d_lo = grid.depth_start[j]
                d_hi = grid.depth_end[j]

                # 深度掩码
                depth_mask = (depth >= d_lo) & (depth < d_hi)
                if not np.any(depth_mask):
                    n_total[i, j] = (p_end - p_start) * int(np.sum(depth_mask))
                    continue

                # 提取该层的子数组
                sv_layer = sv_interval[:, depth_mask]
                dr_layer = dr_interval[:, depth_mask]

                # 底部掩码
                if bot_interval is not None:
                    for ping_idx in range(sv_layer.shape[0]):
                        bot_depth = bot_interval[ping_idx]
                        if np.isfinite(bot_depth):
                            below_bot = depth[depth_mask] >= bot_depth
                            sv_layer[ping_idx, below_bot] = np.nan

                # 阈值掩码
                threshold_mask = (sv_layer >= min_threshold) & (sv_layer <= max_threshold)
                valid_mask = np.isfinite(sv_layer) & threshold_mask

                # 统计
                n_total[i, j] = sv_layer.size
                n_good[i, j] = int(np.sum(valid_mask))
                n_excluded[i, j] = n_total[i, j] - n_good[i, j]

                if n_good[i, j] > 0:
                    sv_valid = sv_layer[valid_mask]
                    mean_Sv[i, j] = float(np.mean(sv_valid))
                    min_Sv[i, j] = float(np.min(sv_valid))
                    max_Sv[i, j] = float(np.max(sv_valid))

                    # NASC = 4π × 1852² × ∫ Sv_linear × dr
                    sv_linear = sv_to_linear(sv_layer)
                    nasc[i, j] = FOUR_PI * (NMI_TO_M ** 2) * float(np.nansum(sv_linear * dr_layer))

                cell_count += 1
                if progress_callback:
                    progress_callback(cell_count, total_cells)
        else:
            # 无底部掩码的情况
            for j in range(grid.n_layers):
                d_lo = grid.depth_start[j]
                d_hi = grid.depth_end[j]

                depth_mask = (depth >= d_lo) & (depth < d_hi)
                if not np.any(depth_mask):
                    n_total[i, j] = 0
                    cell_count += 1
                    continue

                sv_layer = sv_interval[:, depth_mask]
                dr_layer = dr_interval[:, depth_mask] if dr_interval.ndim == 2 else dr_interval[depth_mask]

                # 阈值掩码
                threshold_mask = (sv_layer >= min_threshold) & (sv_layer <= max_threshold)
                valid_mask = np.isfinite(sv_layer) & threshold_mask

                n_total[i, j] = sv_layer.size
                n_good[i, j] = int(np.sum(valid_mask))
                n_excluded[i, j] = n_total[i, j] - n_good[i, j]

                if n_good[i, j] > 0:
                    sv_valid = sv_layer[valid_mask]
                    mean_Sv[i, j] = float(np.mean(sv_valid))
                    min_Sv[i, j] = float(np.min(sv_valid))
                    max_Sv[i, j] = float(np.max(sv_valid))

                    sv_linear = sv_to_linear(sv_layer)
                    nasc[i, j] = FOUR_PI * (NMI_TO_M ** 2) * float(np.nansum(sv_linear * dr_layer))

                cell_count += 1
                if progress_callback:
                    progress_callback(cell_count, total_cells)

    logger.info(f"回声积分完成: {grid.n_intervals} 个区间 × {grid.n_layers} 层")
    logger.info(f"  有效样本比例: {np.sum(n_good) / np.sum(n_total) * 100:.1f}%")

    return IntegrationResult(
        mean_Sv=mean_Sv,
        nasc=nasc,
        min_Sv=min_Sv,
        max_Sv=max_Sv,
        n_good=n_good,
        n_excluded=n_excluded,
        n_total=n_total,
        ping_start=grid.ping_start,
        ping_end=grid.ping_end,
        depth_start=grid.depth_start,
        depth_end=grid.depth_end,
    )


def integrate_by_grid_cells(
    ds_Sv: xr.Dataset,
    grid_cells: list[dict],
    min_threshold: float = -70.0,
    max_threshold: float = 0.0,
    bottom_depth_m: np.ndarray | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> IntegrationResult:
    """按现有网格单元列表进行积分（兼容 grid.py 的 create_grid 输出）

    Parameters
    ----------
    ds_Sv : xr.Dataset
        Sv 数据集
    grid_cells : list[dict]
        网格单元列表，每个包含 ping_start, ping_end, depth_lo, depth_hi
    min_threshold : float
        最小 Sv 阈值 (dB)
    max_threshold : float
        最大 Sv 阈值 (dB)
    bottom_depth_m : np.ndarray, optional
        底部深度数组 (米)
    progress_callback : callable, optional
        进度回调函数

    Returns
    -------
    IntegrationResult
        积分结果
    """
    if not grid_cells:
        logger.warning("没有网格单元需要处理")
        return IntegrationResult(
            mean_Sv=np.array([]), nasc=np.array([]),
            min_Sv=np.array([]), max_Sv=np.array([]),
            n_good=np.array([]), n_excluded=np.array([]), n_total=np.array([]),
            ping_start=np.array([]), ping_end=np.array([]),
            depth_start=np.array([]), depth_end=np.array([]),
        )

    Sv = get_sv_array(ds_Sv).copy()
    depth = get_vertical_coords(ds_Sv)
    _n_pings, n_samples = Sv.shape

    # 计算深度分辨率
    er = get_echo_range_1d(ds_Sv)
    if er is not None:
        dr = np.abs(np.diff(er))
        dr = np.append(dr, dr[-1])
    else:
        dr = np.ones(n_samples)

    # 提取唯一的 interval 和 layer
    unique_pings = []
    unique_depths = []
    for cell in grid_cells:
        p_key = (cell["ping_start"], cell["ping_end"])
        d_key = (cell["depth_lo"], cell["depth_hi"])
        if p_key not in unique_pings:
            unique_pings.append(p_key)
        if d_key not in unique_depths:
            unique_depths.append(d_key)

    n_intervals = len(unique_pings)
    n_layers = len(unique_depths)

    # 初始化结果
    shape = (n_intervals, n_layers)
    mean_Sv = np.full(shape, np.nan)
    nasc = np.full(shape, np.nan)
    min_Sv = np.full(shape, np.nan)
    max_Sv = np.full(shape, np.nan)
    n_good = np.zeros(shape, dtype=int)
    n_excluded = np.zeros(shape, dtype=int)
    n_total = np.zeros(shape, dtype=int)

    ping_starts = np.array([p[0] for p in unique_pings])
    ping_ends = np.array([p[1] for p in unique_pings])
    depth_starts = np.array([d[0] for d in unique_depths])
    depth_ends = np.array([d[1] for d in unique_depths])

    # 创建 cell 到 (i, j) 的映射
    cell_map = {}
    for cell in grid_cells:
        p_key = (cell["ping_start"], cell["ping_end"])
        d_key = (cell["depth_lo"], cell["depth_hi"])
        i = unique_pings.index(p_key)
        j = unique_depths.index(d_key)
        cell_map[(i, j)] = cell.get("cell_id", len(cell_map))

    total_cells = n_intervals * n_layers
    cell_count = 0

    for i, (p_start, p_end) in enumerate(unique_pings):
        sv_interval = Sv[p_start:p_end, :]
        dr_interval = dr[p_start:p_end, :] if dr.ndim == 2 else np.broadcast_to(dr, sv_interval.shape)

        for j, (d_lo, d_hi) in enumerate(unique_depths):
            depth_mask = (depth >= d_lo) & (depth < d_hi)
            if not np.any(depth_mask):
                n_total[i, j] = 0
                cell_count += 1
                continue

            sv_layer = sv_interval[:, depth_mask]
            dr_layer = dr_interval[:, depth_mask] if dr_interval.ndim == 2 else dr_interval[depth_mask]

            # 底部掩码
            if bottom_depth_m is not None:
                bot_interval = bottom_depth_m[p_start:p_end]
                for ping_idx in range(sv_layer.shape[0]):
                    bot_depth = bot_interval[ping_idx]
                    if np.isfinite(bot_depth):
                        below_bot = depth[depth_mask] >= bot_depth
                        sv_layer[ping_idx, below_bot] = np.nan

            # 阈值掩码
            threshold_mask = (sv_layer >= min_threshold) & (sv_layer <= max_threshold)
            valid_mask = np.isfinite(sv_layer) & threshold_mask

            n_total[i, j] = sv_layer.size
            n_good[i, j] = int(np.sum(valid_mask))
            n_excluded[i, j] = n_total[i, j] - n_good[i, j]

            if n_good[i, j] > 0:
                sv_valid = sv_layer[valid_mask]
                mean_Sv[i, j] = float(np.mean(sv_valid))
                min_Sv[i, j] = float(np.min(sv_valid))
                max_Sv[i, j] = float(np.max(sv_valid))

                sv_linear = sv_to_linear(sv_layer)
                nasc[i, j] = FOUR_PI * (NMI_TO_M ** 2) * float(np.nansum(sv_linear * dr_layer))

            cell_count += 1
            if progress_callback:
                progress_callback(cell_count, total_cells)

    logger.info(f"回声积分完成: {n_intervals} 个区间 × {n_layers} 层")

    return IntegrationResult(
        mean_Sv=mean_Sv, nasc=nasc,
        min_Sv=min_Sv, max_Sv=max_Sv,
        n_good=n_good, n_excluded=n_excluded, n_total=n_total,
        ping_start=ping_starts, ping_end=ping_ends,
        depth_start=depth_starts, depth_end=depth_ends,
    )


def integration_statistics_summary(result: IntegrationResult) -> dict:
    """积分结果统计摘要

    Returns
    -------
    dict
        包含全局统计信息
    """
    valid_mask = np.isfinite(result.mean_Sv)
    if not np.any(valid_mask):
        return {"n_intervals": 0, "n_layers": 0, "total_good_samples": 0}

    return {
        "n_intervals": result.n_intervals,
        "n_layers": result.n_layers,
        "total_good_samples": int(np.sum(result.n_good)),
        "total_excluded_samples": int(np.sum(result.n_excluded)),
        "total_samples": int(np.sum(result.n_total)),
        "coverage_ratio": float(np.sum(result.n_good) / np.sum(result.n_total)) if np.sum(result.n_total) > 0 else 0.0,
        "mean_Sv_global": float(np.nanmean(result.mean_Sv[valid_mask])),
        "nasc_global": float(np.nanmean(result.nasc[valid_mask])),
    }