"""分析区域模块：表线/底线管理、深度-sample 转换、区域裁剪

职责：
- 表线深度(米) ↔ sample index 转换
- 底部深度(米) → sample index 转换
- 构建分析区域 mask（排除表线以上、底线以下）
- 裁剪 ds_Sv 到分析区域
"""

import logging

import numpy as np
import xarray as xr

logger = logging.getLogger("fish_acoustics")


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
    for vname in ("Sv", "Sv_corrected"):
        if vname not in ds_out:
            continue
        arr = ds_out[vname]
        if "channel" in arr.dims:
            arr = arr.isel(channel=0)
        arr_vals = arr.values.copy()
        if arr_vals.ndim == 3:
            arr_vals[0, :, :][~mask] = np.nan
            ds_out[vname].values[0, :, :] = arr_vals[0, :, :]
        else:
            arr_vals[~mask] = np.nan
            ds_out[vname].values[:] = arr_vals

    n_valid = int(mask.sum())
    n_total = mask.size
    logger.info(f"分析区域裁剪完成: {n_valid}/{n_total} 像素有效 ({100*n_valid/n_total:.1f}%)")

    return ds_out
