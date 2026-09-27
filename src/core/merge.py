"""多文件对齐拼接 — 按真实时间戳排序 + 重采样到公共深度网格

解决多 .raw 文件拼接时的对准问题：
1. 水平对齐：读每个文件真实 ping_time，全局按时间戳排序
2. 垂直对齐：所有文件的 Sv 重采样到公共距离网格（echo_range 并集）
3. 去重：时间戳相同且 Sv 一致的 ping 只保留第一个，冲突明确报错
4. 返回合并后的 xr.Dataset

参考 Echoview 的 Fileset 行为：多文件按时间连续拼接成一条测线。
"""

import json
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
    """覆盖所有文件、所有 ping 的有效 echo_range，输入顺序不影响网格。

    使用各文件正相邻距离差中位数的最小值，避免以文件顺序决定分辨率。

    Returns
    -------
    np.ndarray
        公共深度网格 (n_samples,)，单位米
    """
    if not ds_list:
        return np.array([], dtype=np.float64)

    starts, ends, spacings = [], [], []
    reference = None
    identical = True
    for ds in ds_list:
        if "echo_range" in ds:
            er = ds["echo_range"]
            grid = np.asarray(er.transpose(..., "range_sample").values, dtype=float)
        else:
            raise ValueError("多文件对齐需要以米为单位的 echo_range，不能用采样索引代替距离")
        valid = grid[np.isfinite(grid)]
        if not valid.size:
            raise ValueError("文件 echo_range 无有效距离，无法完整对齐")
        starts.append(float(valid.min()))
        ends.append(float(valid.max()))
        rows = grid.reshape(-1, grid.shape[-1])
        # 同一文件的各 ping 可有不同有效长度：按采样列补齐距离，再核对所有有限值。
        column_grid = np.max(rows, axis=0, where=np.isfinite(rows), initial=-np.inf)
        column_grid[~np.isfinite(column_grid)] = np.nan
        if reference is None:
            reference = column_grid
        compatible = len(column_grid) == len(reference)
        if compatible:
            compatible = np.all((column_grid == reference) | np.isnan(column_grid) | np.isnan(reference))
            reference = np.fmax(reference, column_grid)
        identical = identical and compatible and np.all((rows == column_grid) | ~np.isfinite(rows))
        differences = np.abs(np.diff(grid, axis=-1))
        positive = differences[np.isfinite(differences) & (differences > 0)]
        if positive.size:
            spacings.append(float(np.median(positive)))
    # 兼容且递增的网格不重建，避免浮点间距误差改变原采样位置。
    valid_reference = reference[np.isfinite(reference)]
    if identical and np.all(np.diff(valid_reference) > 0):
        return valid_reference.copy()
    start, end = min(starts), max(ends)
    if start == end:
        return np.array([start])
    dr = min(spacings) if spacings else end - start
    intervals = (end - start) / dr
    nearest = round(intervals)
    if abs(intervals - nearest) <= 1e-10 * max(intervals, 1):
        intervals = nearest
    n = max(int(np.ceil(intervals)) + 1, 2)
    common = np.linspace(start, end, n)
    logger.info(
        f"公共深度网格: {start:.3f} ~ {end:.3f} m, {n} samples (dr={dr:.4f} m)"
    )
    return common


def _resample_sv(ds_Sv: xr.Dataset, common_grid: np.ndarray, *, logarithmic: bool = True) -> np.ndarray:
    """把单个文件的 Sv 重采样到公共深度网格。

    Returns
    -------
    np.ndarray
        无 channel 输入返回 (n_pings, n_common_samples)，有 channel 输入返回
        (n_channels, n_pings, n_common_samples)。
    """
    dims = (["channel"] if "channel" in ds_Sv["Sv"].dims else []) + ["ping_time", "range_sample"]
    sv = np.asarray(ds_Sv["Sv"].transpose(*dims).values, dtype=np.float64)
    has_channel = sv.ndim == 3
    if sv.ndim == 2:
        sv = sv[np.newaxis, ...]
    elif not has_channel:
        raise ValueError("Sv must have ping_time and range_sample dimensions")

    if "echo_range" in ds_Sv:
        er = ds_Sv["echo_range"].broadcast_like(ds_Sv["Sv"]).transpose(*dims).values
        if not has_channel:
            er = er[np.newaxis, ...]
    else:
        er = np.broadcast_to(_echo_range_1d(ds_Sv), sv.shape)
    n_channels, n_pings, _ = sv.shape

    # Sv 在线性域插值后还原 dB；depth 等几何量直接插值。
    # ponytail: 点插值不保证积分守恒，定量跨网格守恒需按单元重叠面积重采样。
    if logarithmic:
        sv = 10.0 ** (sv / 10.0)
    # 逐 channel、逐 ping 沿深度插值。
    out = np.full((n_channels, n_pings, len(common_grid)), np.nan, dtype=np.float64)
    for channel_idx in range(n_channels):
        for ping_idx in range(n_pings):
            row = sv[channel_idx, ping_idx]
            row_range = er[channel_idx, ping_idx]
            valid = np.isfinite(row_range)
            if not np.any(valid):
                continue
            xp = row_range[valid]
            fp = row[valid]
            order = np.argsort(xp, kind="stable")
            xp = xp[order]
            fp = fp[order]
            xp, unique_idx = np.unique(xp, return_index=True)
            fp = fp[unique_idx]
            out[channel_idx, ping_idx] = np.interp(
                common_grid, xp, fp, left=np.nan, right=np.nan
            )

    if logarithmic:
        with np.errstate(divide="ignore", invalid="ignore"):
            out = 10.0 * np.log10(out)
    # 距离保留双精度，厘米以下采样间距不应因量化产生积分厚度抖动。
    if logarithmic:
        out = out.astype(np.float32)
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
    extra_dims = [dim for dim in echo_range.dims if dim not in ("channel", "ping_time", "range_sample")]
    for dim in extra_dims:
        echo_range = echo_range.isel({dim: 0})
    grids = np.asarray(echo_range.transpose("channel", ...).values)
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
    # 静态校准量必须一致；逐 ping 校准量在后面随时间拼接。
    static_names = {
        name for ds in ds_list for name, da in ds.data_vars.items()
        if set(da.dims) <= {"channel"}
    }
    for name in static_names:
        if any(name not in ds for ds in ds_list):
            raise ValueError(f"多文件校准参数不兼容或缺失：{name}")
        if any(not ds[name].equals(first_ds[name]) for ds in ds_list[1:]):
            raise ValueError(f"多文件校准参数不兼容或缺失：{name}")
    ping_names = {
        name for ds in ds_list for name, da in ds.data_vars.items()
        if "ping_time" in da.dims and "range_sample" not in da.dims and name != "bottom_depth"
    }
    for name in ping_names:
        if any(name not in ds for ds in ds_list):
            raise ValueError(f"多文件逐 ping 参数缺失：{name}")
        if any(ds[name].dims != first_ds[name].dims for ds in ds_list[1:]):
            raise ValueError(f"多文件逐 ping 参数维度不兼容：{name}")
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
    if np.isnat(times_all).any():
        raise ValueError("ping_time 含无效时间，无法可靠拼接")

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
                if not np.array_equal(sv_sorted[:, i], sv_sorted[:, i - 1], equal_nan=True):
                    raise ValueError(f"相同时间戳的 Sv 数据冲突：{times_sorted[i]}，请检查重叠文件")
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
    merged.attrs["merge_duplicate_count"] = int(len(times_all) - len(np.unique(times_all)))
    intervals = np.diff(times_sorted) / np.timedelta64(1, "s")
    positive_intervals = intervals[intervals > 0]
    # ponytail: 断档按典型 ping 间隔的 5 倍提示；不自动填补或改变声学数据。
    typical_interval = float(np.median(positive_intervals)) if positive_intervals.size else 0.0
    gaps = np.flatnonzero(intervals > 5 * typical_interval) + 1 if typical_interval else np.array([], dtype=int)
    merged.attrs["merge_gap_ping_indices"] = json.dumps(gaps.tolist())
    merged.attrs["merge_gap_threshold_seconds"] = 5 * typical_interval
    merged.attrs["merge_resampling"] = "linear_power_point_interpolation_not_integral_conservative"
    if gaps.size:
        logger.warning("拼接发现 %d 处时间断档（超过典型间隔的 5 倍）", gaps.size)
    # depth / echo_range 与原始一致：带 channel 维度（下游 detect_seafloor 依赖）
    er_2d = np.broadcast_to(
        common_grid[None, None, :],
        (n_ch, len(times_sorted), len(common_grid)),
    )
    merged.coords["echo_range"] = (("channel", "ping_time", "range_sample"), er_2d)
    merged.coords["depth"] = (("channel", "ping_time", "range_sample"), er_2d)

    # 复制已验证一致的标量校准变量。
    # 缺失这些变量会导致下游 remove_background_noise 等报 KeyError
    for vname in first.data_vars:
        if vname == "Sv":
            continue
        da = first[vname]
        if set(da.dims) <= {"channel"}:
            merged[vname] = da
    # 按 ping 变化的校准变量保持其 channel 维度（含声速与吸收系数）。
    for vname in first.data_vars:
        if not all(vname in ds.data_vars for ds in ds_list):
            continue
        da = first[vname]
        if "range_sample" in da.dims or "ping_time" not in da.dims or any(ds[vname].dims != da.dims for ds in ds_list):
            continue
        ping_axis = da.get_axis_num("ping_time")
        vals = np.concatenate([ds[vname].values for ds in ds_list], axis=ping_axis)
        vals = np.take(vals, sort_idx, axis=ping_axis)
        if dedup:
            vals = np.take(vals, np.flatnonzero(keep), axis=ping_axis)
        merged[vname] = (da.dims, vals)

    # depth 含换能器偏移，不能用 echo_range 覆盖；与 Sv 使用同一重采样映射。
    if all("depth" in ds for ds in ds_list):
        depth_parts = []
        for ds in ds_list:
            depth_values = ds["depth"].broadcast_like(ds["Sv"])
            part = _resample_sv(ds.assign(Sv=depth_values), common_grid, logarithmic=False)
            depth_parts.append(part if part.ndim == 3 else part[np.newaxis, ...])
        depths = np.concatenate(depth_parts, axis=1)[:, sort_idx, :]
        if dedup:
            depths = depths[:, keep, :]
        merged.coords["depth"] = (("channel", "ping_time", "range_sample"), depths)

    # 保留逐文件处理阶段生成的校正 Sv 和底线，避免 CLI 合并后丢失结果。
    if all("Sv_corrected" in ds for ds in ds_list):
        corrected_parts = []
        for ds in ds_list:
            corrected_part = _resample_sv(ds.assign(Sv=ds["Sv_corrected"]), common_grid)
            if corrected_part.ndim == 2:
                corrected_part = corrected_part[np.newaxis, ...]
            corrected_parts.append(corrected_part)
        corrected = np.concatenate(corrected_parts, axis=1)[:, sort_idx, :]
        if dedup:
            corrected = corrected[:, keep, :]
        merged["Sv_corrected"] = (
            ("channel", "ping_time", "range_sample"), corrected
        )

    if all("bottom_depth" in ds for ds in ds_list):
        bottom_depth = np.concatenate(
            [np.asarray(ds["bottom_depth"].values).reshape(-1) for ds in ds_list]
        )[sort_idx]
        if dedup:
            bottom_depth = bottom_depth[keep]
        merged["bottom_depth"] = (("ping_time",), bottom_depth)

    for coord_name in ("latitude", "longitude", "source_file"):
        if all(coord_name in ds for ds in ds_list):
            values = np.concatenate(
                [np.asarray(ds[coord_name].values).reshape(-1) for ds in ds_list]
            )[sort_idx]
            if dedup:
                values = values[keep]
            merged = merged.assign_coords({coord_name: (("ping_time",), values)})

    logger.info(
        f"对齐拼接完成: {len(times_sorted)} pings × {len(common_grid)} samples"
    )
    return merged
