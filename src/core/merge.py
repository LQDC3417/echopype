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
        (n_pings, n_common_samples) 的 Sv 数组
    """
    sv = ds_Sv["Sv"].values
    if sv.ndim == 3:
        sv = sv[0]  # 第一个 channel
    sv = np.asarray(sv, dtype=np.float64)

    er = _echo_range_1d(ds_Sv)
    n_pings = sv.shape[0]

    # 逐 ping 沿深度插值
    out = np.full((n_pings, len(common_grid)), np.nan, dtype=np.float32)
    for i in range(n_pings):
        row = sv[i]
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
        out[i] = np.interp(common_grid, xp, fp, left=np.nan, right=np.nan)

    return out


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

    # 提取原始 channel 值（保留给下游 detect_bottom 等使用）
    channel_vals = None
    first_ds = ds_list[0]
    if "channel" in first_ds.coords:
        channel_vals = first_ds["channel"].values
    elif "channel" in first_ds.dims:
        channel_vals = first_ds["channel"].values

    # 只保留第一个 channel
    ds_list = [
        ds.isel(channel=0) if "channel" in ds.dims else ds
        for ds in ds_list
    ]

    # 公共深度网格
    common_grid = compute_common_grid(ds_list)
    if len(common_grid) == 0:
        raise ValueError("公共深度网格为空")

    # 逐文件重采样 + 收集 ping_time
    all_sv = []
    all_times = []
    for ds in ds_list:
        sv_resampled = _resample_sv(ds, common_grid)
        times = ds["ping_time"].values
        all_sv.append(sv_resampled)
        all_times.append(times)

    sv_all = np.vstack(all_sv)
    times_all = np.concatenate(all_times)

    # 按真实时间戳排序
    sort_idx = np.argsort(times_all, kind="stable")
    sv_sorted = sv_all[sort_idx]
    times_sorted = times_all[sort_idx]

    # 去重（时间戳相同的 ping 只保留第一个）
    keep = np.ones(len(sv_all), dtype=bool)
    if dedup and len(times_sorted) > 1:
        t_prev = times_sorted[0]
        for i in range(1, len(times_sorted)):
            if times_sorted[i] == t_prev:
                keep[i] = False
            else:
                t_prev = times_sorted[i]
        if not np.all(keep):
            logger.info(f"去重 {int((~keep).sum())} 个重叠 ping")
        sv_sorted = sv_sorted[keep]
        times_sorted = times_sorted[keep]

    # 组装 xr.Dataset
    if channel_vals is None:
        channel_vals = np.array([0], dtype=np.int64)
    else:
        channel_vals = np.atleast_1d(channel_vals)[:1]
    n_ch = len(channel_vals)
    sv_3d = np.broadcast_to(
        sv_sorted.astype(np.float32)[None, :, :], (n_ch, sv_sorted.shape[0], sv_sorted.shape[1])
    )
    merged = xr.Dataset(
        {
            "Sv": xr.DataArray(
                sv_3d,
                dims=["channel", "ping_time", "range_sample"],
                coords={
                    "channel": ("channel", channel_vals),
                    "ping_time": ("ping_time", times_sorted),
                    "range_sample": ("range_sample", np.arange(len(common_grid))),
                },
            ),
        }
    )
    # depth / echo_range 与原始一致：带 channel 维度（下游 detect_seafloor 依赖）
    er_2d = np.broadcast_to(
        common_grid.astype(np.float32)[None, None, :],
        (n_ch, len(times_sorted), len(common_grid)),
    )
    merged.coords["echo_range"] = (("channel", "ping_time", "range_sample"), er_2d)
    merged.coords["depth"] = (("channel", "ping_time", "range_sample"), er_2d)

    # 复制标量校准变量（声速/吸收/波束参数等，同一调查所有文件一致，取第一个文件）
    # 缺失这些变量会导致下游 remove_background_noise 等报 KeyError
    first = ds_list[0]
    for vname in first.data_vars:
        if vname == "Sv":
            continue
        da = first[vname]
        if da.ndim == 0:
            merged[vname] = da
    # per-ping 校准变量（gain/sa_correction）：取合并后各 ping 的拼接值
    for vname in ("gain_correction", "sa_correction"):
        if vname in first.data_vars:
            vals = np.concatenate([ds[vname].values for ds in ds_list])[sort_idx]
            if dedup and len(times_sorted) > 1:
                vals = vals[keep]
            merged[vname] = (("ping_time",), vals)

    logger.info(
        f"对齐拼接完成: {len(times_sorted)} pings × {len(common_grid)} samples"
    )
    return merged
