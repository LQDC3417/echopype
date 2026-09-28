"""分析区域模块：表线/底线管理、深度-sample 转换、区域裁剪

职责：
- 表线深度(米) ↔ sample index 转换
- 底部深度(米) → sample index 转换
- 构建分析区域 mask（排除表线以上、底线以下）
- 裁剪 ds_Sv 到分析区域
"""

import logging
from dataclasses import dataclass

import numpy as np
import xarray as xr

from src.core.lines import LineManager

logger = logging.getLogger("fish_acoustics")


@dataclass(frozen=True)
class AnalysisRegion:
    """活动分析区域引用的上下边界线。"""

    upper_line_id: str
    lower_line_id: str

    def validate(self, available_line_ids: set[str]) -> None:
        if self.upper_line_id == self.lower_line_id:
            raise ValueError("Analysis region boundaries must be different")
        missing = {self.upper_line_id, self.lower_line_id} - available_line_ids
        if missing:
            raise ValueError(f"Analysis region references missing lines: {sorted(missing)}")


def build_line_region_mask(
    echo_range_m: np.ndarray,
    upper_depth_m: np.ndarray,
    lower_depth_m: np.ndarray,
) -> tuple[np.ndarray, int]:
    """构建任意两条深度线之间的 mask，并整条排除无效 ping。"""
    depths = np.asarray(echo_range_m, dtype=np.float32)
    upper = np.asarray(upper_depth_m, dtype=np.float32).reshape(-1)
    lower = np.asarray(lower_depth_m, dtype=np.float32).reshape(-1)
    if len(upper) != len(lower):
        raise ValueError("Region boundaries must have equal ping counts")
    if depths.ndim == 1:
        depths = np.broadcast_to(depths, (len(upper), depths.size))
    elif depths.ndim != 2 or depths.shape[0] != len(upper):
        raise ValueError("echo_range must have one row per ping")
    if depths.shape[1] == 0:
        return np.zeros((len(upper), 0), dtype=bool), len(upper)

    finite_depth = np.isfinite(depths)
    row_has_depth = finite_depth.any(axis=1)
    depth_min = np.min(np.where(finite_depth, depths, np.inf), axis=1)
    depth_max = np.max(np.where(finite_depth, depths, -np.inf), axis=1)
    valid = (
        np.isfinite(upper)
        & np.isfinite(lower)
        & (upper < lower)
        & row_has_depth
        & (upper >= depth_min)
        & (lower <= depth_max)
    )
    mask = finite_depth & (depths >= upper[:, np.newaxis]) & (depths <= lower[:, np.newaxis])
    mask[~valid, :] = False
    return mask, int((~valid).sum())


def _echo_range_2d(ds_Sv: xr.Dataset, n_pings: int) -> np.ndarray:
    """提取以米为单位的 ``ping × sample`` 深度坐标。"""
    if "echo_range" not in ds_Sv:
        raise ValueError("Dataset has no echo_range in metres")
    echo_range = ds_Sv["echo_range"]
    if "channel" in echo_range.dims:
        echo_range = echo_range.isel(channel=0)
    if "ping_time" in echo_range.dims:
        echo_range = echo_range.transpose("ping_time", "range_sample")
    values = np.asarray(echo_range.values, dtype=np.float64)
    values = np.squeeze(values)
    if values.ndim == 1:
        return np.broadcast_to(values, (n_pings, values.size))
    if values.ndim != 2 or values.shape[0] != n_pings:
        raise ValueError("echo_range ping count does not match Sv")
    return values


def depths_to_sample_indices(echo_range_m: np.ndarray, depths_m: np.ndarray) -> np.ndarray:
    """逐 ping 将米深转换为 sample index；无效或越界深度返回 NaN。"""
    depths = np.asarray(depths_m, dtype=np.float64).reshape(-1)
    ranges = np.asarray(echo_range_m, dtype=np.float64)
    if ranges.ndim == 1:
        ranges = np.broadcast_to(ranges, (len(depths), ranges.size))
    if ranges.ndim != 2 or ranges.shape[0] != len(depths):
        raise ValueError("echo_range ping count does not match depth ping count")
    result = np.full(len(depths), np.nan, dtype=np.float32)
    for ping, depth in enumerate(depths):
        row = ranges[ping]
        finite = np.isfinite(row)
        if not np.isfinite(depth) or not finite.any():
            continue
        valid_row = row[finite]
        if depth < valid_row.min() or depth > valid_row.max():
            continue
        finite_indices = np.flatnonzero(finite)
        if valid_row[0] <= valid_row[-1]:
            pos = int(np.searchsorted(valid_row, depth))
        else:
            pos = int(np.searchsorted(-valid_row, -depth))
        pos = min(pos, len(valid_row) - 1)
        result[ping] = finite_indices[pos]
    return result


def sample_indices_to_depths(echo_range_m: np.ndarray, sample_indices: np.ndarray) -> np.ndarray:
    """逐 ping 将 Renderer 的 sample index 转换为米深，支持小数 index 插值。"""
    samples = np.asarray(sample_indices, dtype=np.float64).reshape(-1)
    ranges = np.asarray(echo_range_m, dtype=np.float64)
    if ranges.ndim == 1:
        ranges = np.broadcast_to(ranges, (len(samples), ranges.size))
    if ranges.ndim != 2 or ranges.shape[0] != len(samples):
        raise ValueError("echo_range ping count does not match sample ping count")
    result = np.full(len(samples), np.nan, dtype=np.float32)
    for ping, sample in enumerate(samples):
        row = ranges[ping]
        if not np.isfinite(sample) or sample < 0 or sample > len(row) - 1:
            continue
        left = int(np.floor(sample))
        right = int(np.ceil(sample))
        if not np.isfinite(row[left]) or not np.isfinite(row[right]):
            continue
        fraction = sample - left
        result[ping] = row[left] + fraction * (row[right] - row[left])
    return result


def crop_sv_by_line_region(
    ds_Sv: xr.Dataset,
    line_manager: LineManager,
    region: AnalysisRegion,
) -> tuple[xr.Dataset, int]:
    """按 ping_time 解析任意上下边界线，并以米深构建分析区域。"""
    line_ids = {line.id for line in line_manager}
    region.validate(line_ids)
    ping_times = np.asarray(ds_Sv["ping_time"].values)
    upper = line_manager.resolve_for_pings(region.upper_line_id, ping_times)
    lower = line_manager.resolve_for_pings(region.lower_line_id, ping_times)
    echo_range = _echo_range_2d(ds_Sv, len(ping_times))
    mask, excluded = build_line_region_mask(echo_range, upper, lower)

    ds_out = ds_Sv.copy(deep=False)
    mask_da = xr.DataArray(
        mask,
        dims=("ping_time", "range_sample"),
        coords={"ping_time": ds_Sv["ping_time"], "range_sample": ds_Sv["range_sample"]},
    )
    for variable in ("Sv", "Sv_corrected"):
        if variable in ds_out:
            ds_out[variable] = ds_out[variable].where(mask_da)
    return ds_out, excluded


# ── 坐标转换 ──────────────────────────────────────────────

def depth_to_sample_index(
    depth_m: float,
    echo_range: np.ndarray,
) -> int:
    """将深度(米)转换为 sample index。

    Parameters
    ----------
    depth_m : float
        目标深度（米）
    echo_range : np.ndarray
        1D 深度数组（米），shape=(n_samples,)

    Returns
    -------
    int
        最近的 sample index
    """
    idx = int(np.searchsorted(echo_range, depth_m))
    return max(0, min(idx, len(echo_range) - 1))


def bottom_depth_to_sample_indices(
    bottom_depth_m: np.ndarray,
    echo_range: np.ndarray,
) -> np.ndarray:
    """将底部深度数组(米)转换为 sample index 数组（向量化实现）。

    Parameters
    ----------
    bottom_depth_m : np.ndarray
        底部深度（米），shape=(n_pings,)
    echo_range : np.ndarray
        1D 深度数组（米），shape=(n_samples,)

    Returns
    -------
    np.ndarray
        sample index 数组，shape=(n_pings,), dtype=float32, NaN 表示无效
    """
    n_pings = len(bottom_depth_m)
    bottom_indices = np.full(n_pings, np.nan, dtype=np.float32)

    # 向量化：只对有效深度执行 searchsorted
    valid_mask = (~np.isnan(bottom_depth_m)) & (bottom_depth_m > 0)
    if np.any(valid_mask):
        valid_depths = bottom_depth_m[valid_mask]
        indices = np.searchsorted(echo_range, valid_depths)
        indices = np.clip(indices, 0, len(echo_range) - 1).astype(np.float32)
        bottom_indices[valid_mask] = indices

    return bottom_indices


# ── 取回坐标 ──────────────────────────────────────────────

def get_echo_range_1d(ds_Sv: xr.Dataset) -> np.ndarray | None:
    """从 ds_Sv 提取 1D echo_range 数组（第一个 channel）。

    Returns
    -------
    np.ndarray or None
        1D 深度数组（米），shape=(n_samples,)；无数据时返回 None
    """
    if "echo_range" not in ds_Sv:
        return None
    er = ds_Sv["echo_range"]
    if "channel" in er.dims:
        er = er.isel(channel=0)
    er_vals = er.values
    if er.ndim == 2:
        # 取第一个 ping 的深度剖面 (n_samples,)
        er_vals = er_vals[0]
    return er_vals.astype(np.float64)


def get_surface_sample(ds_Sv: xr.Dataset, surface_depth_m: float) -> float | None:
    """将表线深度(米)转为 sample index。

    Parameters
    ----------
    ds_Sv : xr.Dataset
    surface_depth_m : float
        表线离水面深度（米）

    Returns
    -------
    float or None
        sample index；无法转换时返回 None
    """
    er = get_echo_range_1d(ds_Sv)
    if er is None:
        return None
    return float(depth_to_sample_index(surface_depth_m, er))


def get_bottom_samples(ds_Sv: xr.Dataset, bottom_depth_m: np.ndarray) -> np.ndarray | None:
    """将底部深度数组(米)转为 sample index 数组。

    Parameters
    ----------
    ds_Sv : xr.Dataset
    bottom_depth_m : np.ndarray
        底部深度（米），shape=(n_pings,)

    Returns
    -------
    np.ndarray or None
        sample index 数组；无法转换时返回 None
    """
    er = get_echo_range_1d(ds_Sv)
    if er is None:
        return None
    return bottom_depth_to_sample_indices(bottom_depth_m, er)


# ── mask 构建 ──────────────────────────────────────────────

def build_analysis_mask(
    sv_shape: tuple,
    surface_sample: float | None,
    bottom_line: np.ndarray | None,
) -> np.ndarray | None:
    """构建分析区域 mask（True = 在分析区域内）。

    Parameters
    ----------
    sv_shape : (n_pings, n_samples)
    surface_sample : float or None
        表线 sample index，以上部分排除
    bottom_line : np.ndarray or None
        底线 sample index 数组 (n_pings,)，以下部分排除

    Returns
    -------
    np.ndarray or None
        bool mask，shape=sv_shape；两者都为 None 时返回 None
    """
    if surface_sample is None and bottom_line is None:
        return None

    n_pings, n_samples = sv_shape
    mask = np.ones(sv_shape, dtype=bool)

    # 排除表线以上
    if surface_sample is not None and not np.isnan(surface_sample):
        surf_idx = round(surface_sample)
        if surf_idx > 0:
            mask[:, :surf_idx] = False

    # 排除底线以下（向量化实现，避免 Python 循环）
    if bottom_line is not None:
        bl = np.asarray(bottom_line, dtype=np.float32)
        if bl.ndim == 0:
            return mask
        bl_clipped = np.clip(bl, 0, n_samples)
        # 处理长度不匹配
        if len(bl_clipped) < n_pings:
            bl_clipped = np.pad(bl_clipped, (0, n_pings - len(bl_clipped)), constant_values=np.nan)
        elif len(bl_clipped) > n_pings:
            bl_clipped = bl_clipped[:n_pings]
        # 向量化：sample_indices > bottom → False（边界点本身保留，与表线语义一致）
        sample_indices = np.arange(n_samples)[np.newaxis, :]  # (1, n_samples)
        bottom_expanded = bl_clipped[:, np.newaxis]  # (n_pings, 1)
        # NaN 的行保持 True（不排除）
        nan_mask = np.isnan(bl_clipped)
        below_bottom = sample_indices > bottom_expanded
        below_bottom[nan_mask, :] = False  # NaN 的行不排除
        mask[below_bottom] = False

    return mask


# ── 数据裁剪 ──────────────────────────────────────────────

def crop_sv_by_region(
    ds_Sv: xr.Dataset,
    surface_depth_m: float | None = None,
    bottom_depth_m: np.ndarray | None = None,
    bottom_sample_indices: np.ndarray | None = None,
) -> xr.Dataset:
    """根据表线和底线裁剪 Sv 数据集。

    裁剪方式：将分析区域外的 Sv 值设为 NaN（不改变数组维度）。

    Parameters
    ----------
    ds_Sv : xr.Dataset
        包含 Sv 的数据集
    surface_depth_m : float, optional
        表线深度（米）
    bottom_depth_m : np.ndarray, optional
        底部深度数组（米），shape=(n_pings,)
    bottom_sample_indices : np.ndarray, optional
        底部 sample index 数组（优先于 bottom_depth_m）

    Returns
    -------
    xr.Dataset
        裁剪后的数据集（副本）
    """
    # 获取 sample index
    surface_sample = None
    if surface_depth_m is not None:
        surface_sample = get_surface_sample(ds_Sv, surface_depth_m)

    bottom_line = None
    if bottom_sample_indices is not None:
        bottom_line = bottom_sample_indices
    elif bottom_depth_m is not None:
        bottom_line = get_bottom_samples(ds_Sv, bottom_depth_m)

    if surface_sample is None and bottom_line is None:
        return ds_Sv

    # 获取 Sv 数组（用于确定 shape 和构建 mask）
    var = "Sv_corrected" if "Sv_corrected" in ds_Sv else "Sv"
    sv = ds_Sv[var]
    if "channel" in sv.dims:
        sv = sv.isel(channel=0)
    sv_arr = sv.values
    if sv_arr.ndim == 3:
        sv_arr = sv_arr[0]

    mask = build_analysis_mask(sv_arr.shape, surface_sample, bottom_line)
    if mask is None:
        return ds_Sv

    # 裁剪：区域外设为 NaN（deep copy 避免污染原始数据）
    # 同时裁剪 Sv 和 Sv_corrected（如果存在），确保下游无论读哪个变量都受分析区域约束
    ds_out = ds_Sv.copy(deep=True)
    region_mask = xr.DataArray(mask, dims=("ping_time", "range_sample"))
    for vname in ("Sv", "Sv_corrected"):
        if vname not in ds_out:
            continue
        ds_out[vname] = ds_out[vname].where(region_mask)

    n_valid = int(mask.sum())
    n_total = mask.size
    logger.info(f"分析区域裁剪完成: {n_valid}/{n_total} 像素有效 ({100*n_valid/n_total:.1f}%)")

    return ds_out
