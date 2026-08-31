"""多文件对齐拼接 — 按真实时间戳排序 + 重采样到公共深度网格

解决多 .raw 文件拼接时的对准问题：
1. 水平对齐：读每个文件真实 ping_time，全局按时间戳排序
2. 垂直对齐：所有文件的 Sv 重采样到公共深度网格（echo_range 交集）
3. 去重：时间戳相同的 ping 只保留第一个
4. 返回合并后的 xr.Dataset

参考 Echoview 的 Fileset 行为：多文件按时间连续拼接成一条测线。
"""

import logging

import numpy as np
import xarray as xr

logger = logging.getLogger("fish_acoustics")


def _echo_range_1d(ds_Sv: xr.Dataset) -> np.ndarray:
    """从 ds_Sv 提取 1D echo_range（第一个 channel 的第一 ping）。"""
    from src.core.region import get_echo_range_1d
    er = get_echo_range_1d(ds_Sv)
    if er is None:
        # fallback：range_sample index
        er = np.arange(ds_Sv.sizes["range_sample"], dtype=np.float64)
    return er


def compute_common_grid(ds_list: list[xr.Dataset]) -> np.ndarray:
    """计算公共深度网格（所有文件 echo_range 的交集）。

    取各文件 echo_range 起点最大值、终点最小值，等间距重采样。
    若交集无效则退回第一个文件的网格。

    Returns
    -------
    np.ndarray
        公共深度网格 (n_samples,)，单位米
    """
    if not ds_list:
        return np.array([], dtype=np.float64)

    grids = [_echo_range_1d(ds) for ds in ds_list]

    # 若所有文件网格完全一致，直接返回
    first = grids[0]
    if all(len(g) == len(first) and np.allclose(g, first) for g in grids[1:]):
        return first

    # 计算交集范围（跳过 NaN — echo_range 前后段可能无效）
    def _valid_extent(g):
        """返回有效（非 NaN）子区间的起点/终点"""
        v = g[np.isfinite(g)]
        if len(v) == 0:
            return None, None
        return float(np.min(v)), float(np.max(v))

    valid_grids = [_valid_extent(g) for g in grids]
    starts = [s for s, e in valid_grids if s is not None]
    ends = [e for s, e in valid_grids if e is not None]
    if not starts or not ends:
        logger.warning("所有文件 echo_range 均无有效值，退回第一个文件网格")
        return first

    start = max(starts)
    end = min(ends)

    if end <= start:
        logger.warning("文件间 echo_range 无交集，退回第一个文件网格")
        return first

    # 用第一个文件的有效相邻差值中位数作为公共网格间距
    diff_first = np.abs(np.diff(np.sort(first[np.isfinite(first)])))
    dr = float(np.median(diff_first)) if len(diff_first) > 0 else 1.0
    if not np.isfinite(dr) or dr <= 0:
        dr = 1.0
    n = max(int(np.ceil((end - start) / dr)) + 1, 2)
    common = np.linspace(start, end, n)
    logger.info(
        f"公共深度网格: {start:.3f} ~ {end:.3f} m, {n} samples (dr={dr:.4f} m)"
    )
    return common


def _resample_sv(ds_Sv: xr.Dataset, common_grid: np.ndarray) -> np.ndarray:
    """把单个文件的 Sv 重采样到公共深度网格。

    Returns
    -------
    np.ndarray
        无 channel 输入返回 (n_pings, n_common_samples)，有 channel 输入返回
        (n_channels, n_pings, n_common_samples)。
    """
    sv = np.asarray(ds_Sv["Sv"].values, dtype=np.float64)
    has_channel = sv.ndim == 3
    if sv.ndim == 2:
        sv = sv[np.newaxis, ...]
    elif not has_channel:
        raise ValueError("Sv must have ping_time and range_sample dimensions")

    er = _echo_range_1d(ds_Sv)
    n_channels, n_pings, _ = sv.shape

    # 逐 channel、逐 ping 沿深度插值。
    out = np.full((n_channels, n_pings, len(common_grid)), np.nan, dtype=np.float32)
    for channel_idx in range(n_channels):
        for ping_idx in range(n_pings):
            row = sv[channel_idx, ping_idx]
            valid = np.isfinite(row) & np.isfinite(er)
            if np.count_nonzero(valid) < 2:
                continue
            xp = er[valid]
            fp = row[valid]
            order = np.argsort(xp, kind="stable")
            xp = xp[order]
            fp = fp[order]
            xp, unique_idx = np.unique(xp, return_index=True)
            fp = fp[unique_idx]
            out[channel_idx, ping_idx] = np.interp(
                common_grid, xp, fp, left=np.nan, right=np.nan
            )

    return out if has_channel else out[0]


def _channel_values(ds_Sv: xr.Dataset) -> np.ndarray:
    """返回数据集的 channel 坐标；无 channel 数据按单通道处理。"""
    if "channel" not in ds_Sv.dims:
        return np.array([0], dtype=np.int64)
    if "channel" in ds_Sv.coords:
        return np.atleast_1d(ds_Sv["channel"].values)
    return np.arange(ds_Sv.sizes["channel"], dtype=np.int64)


def _validate_shared_channel_grid(ds_Sv: xr.Dataset) -> None:
    """拒绝 channel 间不一致的深度网格，避免把 Sv 标注到错误深度。"""
    channel_vals = _channel_values(ds_Sv)
    if len(channel_vals) <= 1:
        return

    if "echo_range" not in ds_Sv:
        return
    echo_range = ds_Sv["echo_range"]
    if "channel" not in echo_range.dims:
        return
    if "ping_time" in echo_range.dims:
        echo_range = echo_range.isel(ping_time=0)
    extra_dims = [dim for dim in echo_range.dims if dim not in ("channel", "range_sample")]
    for dim in extra_dims:
        echo_range = echo_range.isel({dim: 0})
    grids = np.asarray(echo_range.transpose("channel", "range_sample").values)
    reference = grids[0]
    if any(
        len(grid) != len(reference) or not np.allclose(grid, reference, equal_nan=True)
        for grid in grids[1:]
    ):
        raise ValueError("多通道合并要求 channel 共享相同的 echo_range 网格")


def merge_aligned(ds_list: list[xr.Dataset], dedup: bool = True) -> xr.Dataset:
    """将多个文件的 Sv 对齐拼接为一个连续 echogram。

    Parameters
    ----------
    ds_list : list[xr.Dataset]
        每个文件的 compute_sv 输出（含 Sv + echo_range + ping_time）
    dedup : bool
        是否去重时间戳相同的 ping（默认 True）

    Returns
    -------
    xr.Dataset
        合并后的数据集（Sv: ping_time × range_sample，echo_range 为公共网格）
    """
    if not ds_list:
        raise ValueError("没有可合并的文件")

    first_ds = ds_list[0]
    channel_vals = _channel_values(first_ds)
    for ds in ds_list:
        _validate_shared_channel_grid(ds)
    for ds in ds_list[1:]:
        if not np.array_equal(_channel_values(ds), channel_vals):
            raise ValueError("多文件合并要求所有文件具有相同的 channel 坐标")
    first = first_ds

    # 公共深度网格
    common_grid = compute_common_grid(ds_list)
    if len(common_grid) == 0:
        raise ValueError("公共深度网格为空")

    # 逐文件重采样 + 收集 ping_time
    all_sv = []
    all_times = []
    for ds in ds_list:
        sv_resampled = _resample_sv(ds, common_grid)
        if sv_resampled.ndim == 2:
            sv_resampled = sv_resampled[np.newaxis, ...]
        times = ds["ping_time"].values
        all_sv.append(sv_resampled)
        all_times.append(times)

    sv_all = np.concatenate(all_sv, axis=1)
    times_all = np.concatenate(all_times)

    # 按真实时间戳排序
    sort_idx = np.argsort(times_all, kind="stable")
    sv_sorted = sv_all[:, sort_idx, :]
    times_sorted = times_all[sort_idx]

    # 去重（时间戳相同的 ping 只保留第一个）
    keep = np.ones(sv_all.shape[1], dtype=bool)
    if dedup and len(times_sorted) > 1:
        t_prev = times_sorted[0]
        for i in range(1, len(times_sorted)):
            if times_sorted[i] == t_prev:
                keep[i] = False
            else:
                t_prev = times_sorted[i]
        if not np.all(keep):
            logger.info(f"去重 {int((~keep).sum())} 个重叠 ping")
        sv_sorted = sv_sorted[:, keep, :]
        times_sorted = times_sorted[keep]

    # 组装 xr.Dataset
    n_ch = len(channel_vals)
    merged = xr.Dataset(
        {
            "Sv": xr.DataArray(
                sv_sorted.astype(np.float32),
                dims=["channel", "ping_time", "range_sample"],
                coords={
                    "channel": ("channel", channel_vals),
                    "ping_time": ("ping_time", times_sorted),
                    "range_sample": ("range_sample", np.arange(len(common_grid))),
                },
            ),
        }
    )
    merged.attrs.update(first.attrs)
    # depth / echo_range 与原始一致：带 channel 维度（下游 detect_seafloor 依赖）
    er_2d = np.broadcast_to(
        common_grid.astype(np.float32)[None, None, :],
        (n_ch, len(times_sorted), len(common_grid)),
    )
    merged.coords["echo_range"] = (("channel", "ping_time", "range_sample"), er_2d)
    merged.coords["depth"] = (("channel", "ping_time", "range_sample"), er_2d)

    # 复制标量校准变量（声速/吸收/波束参数等，同一调查所有文件一致，取第一个文件）
    # 缺失这些变量会导致下游 remove_background_noise 等报 KeyError
    for vname in first.data_vars:
        if vname == "Sv":
            continue
        da = first[vname]
        if da.ndim == 0:
            merged[vname] = da
    # 按 ping 变化的校准变量（gain/sa_correction）保持其 channel 维度。
    for vname in ("gain_correction", "sa_correction"):
        if not all(vname in ds.data_vars for ds in ds_list):
            continue
        da = first[vname]
        if "ping_time" not in da.dims or any(ds[vname].dims != da.dims for ds in ds_list):
            continue
        ping_axis = da.get_axis_num("ping_time")
        vals = np.concatenate([ds[vname].values for ds in ds_list], axis=ping_axis)
        vals = np.take(vals, sort_idx, axis=ping_axis)
        if dedup and len(times_sorted) > 1:
            vals = np.take(vals, np.flatnonzero(keep), axis=ping_axis)
        merged[vname] = (da.dims, vals)

    # 保留逐文件处理阶段生成的校正 Sv 和底线，避免 CLI 合并后丢失结果。
    if all("Sv_corrected" in ds for ds in ds_list):
        corrected_parts = []
        for ds in ds_list:
            corrected_part = _resample_sv(ds.assign(Sv=ds["Sv_corrected"]), common_grid)
            if corrected_part.ndim == 2:
                corrected_part = corrected_part[np.newaxis, ...]
            corrected_parts.append(corrected_part)
        corrected = np.concatenate(corrected_parts, axis=1)[:, sort_idx, :]
        if dedup and len(times_sorted) > 1:
            corrected = corrected[:, keep, :]
        merged["Sv_corrected"] = (
            ("channel", "ping_time", "range_sample"), corrected
        )

    if all("bottom_depth" in ds for ds in ds_list):
        bottom_depth = np.concatenate(
            [np.asarray(ds["bottom_depth"].values).reshape(-1) for ds in ds_list]
        )[sort_idx]
        if dedup and len(times_sorted) > 1:
            bottom_depth = bottom_depth[keep]
        merged["bottom_depth"] = (("ping_time",), bottom_depth)

    for coord_name in ("latitude", "longitude"):
        if all(coord_name in ds for ds in ds_list):
            values = np.concatenate(
                [np.asarray(ds[coord_name].values).reshape(-1) for ds in ds_list]
            )[sort_idx]
            if dedup and len(times_sorted) > 1:
                values = values[keep]
            merged = merged.assign_coords({coord_name: (("ping_time",), values)})

    logger.info(
        f"对齐拼接完成: {len(times_sorted)} pings × {len(common_grid)} samples"
    )
    return merged
