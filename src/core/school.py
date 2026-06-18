"""鱼群识别模块：基于 Sv 阈值的鱼群检测与聚类"""

import logging

import numpy as np
import pandas as pd
import xarray as xr

from src.core.utils import build_analysis_mask

logger = logging.getLogger("fish_acoustics")


def _build_edge_coords(center_coords: np.ndarray) -> np.ndarray:
    """
    将中心坐标转换为边缘坐标（长度 n → n+1）。
    echoview 算法需要边缘坐标来计算鱼群尺寸。
    """
    if len(center_coords) < 2:
        return np.array([center_coords[0] - 0.5, center_coords[0] + 0.5])

    # 等间距情况：用相邻中点作为边缘
    edges = np.empty(len(center_coords) + 1)
    step = center_coords[1] - center_coords[0]
    edges[0] = center_coords[0] - step / 2
    edges[1:] = center_coords + step / 2
    return edges


def detect_schools(
    ds_Sv: xr.Dataset,
    config: dict,
    surface_sample: float | None = None,
    bottom_line: np.ndarray | None = None,
) -> xr.DataArray:
    """
    鱼群检测：使用 echopype 公共 API detect_shoal

    Parameters
    ----------
    ds_Sv : xr.Dataset
        包含 Sv 变量的数据集
    config : dict
        配置字典，需包含 school_detection 子项
    surface_sample : float or None
        表线 sample index，以上区域排除；None 表示不限
    bottom_line : np.ndarray or None
        底线 sample index 数组 (n_pings,)，以下区域排除；None 表示不限

    Returns
    -------
    xr.DataArray
        布尔 mask，True 表示鱼群区域
    """
    from echopype.mask import detect_shoal

    school_cfg = config.get("school_detection", {})
    method = school_cfg.get("method", "echoview")

    if method != "echoview":
        raise ValueError(f"不支持的鱼群检测方法: {method}")

    # 选择第一个 channel
    channel = str(ds_Sv["channel"].values[0]) if "channel" in ds_Sv.dims else None

    # 构建边缘坐标（echoview 方法需要 n+1 长度）
    ping_time = ds_Sv["ping_time"].values
    range_sample = ds_Sv["range_sample"].values

    # idim = 垂直坐标（depth 或 range_sample）
    if "depth" in ds_Sv:
        depth_data = ds_Sv["depth"]
        if "channel" in depth_data.dims:
            depth_data = depth_data.isel(channel=0)
        idim_center = depth_data.isel(ping_time=0).values
    elif "echo_range" in ds_Sv:
        echo_data = ds_Sv["echo_range"]
        if "channel" in echo_data.dims:
            echo_data = echo_data.isel(channel=0)
        idim_center = echo_data.isel(ping_time=0).values
    else:
        idim_center = range_sample.astype(float)

    # 填充 NaN 值
    if np.any(np.isnan(idim_center)):
        valid_mask = ~np.isnan(idim_center)
        if np.any(valid_mask):
            valid_indices = np.where(valid_mask)[0]
            idim_center = np.interp(
                np.arange(len(idim_center)),
                valid_indices,
                idim_center[valid_mask],
            )
        else:
            idim_center = range_sample.astype(float)

    # jdim = 水平坐标（ping_time）
    jdim_center = ping_time.astype(float)

    # 确保坐标单调递增
    if len(idim_center) > 1 and idim_center[0] > idim_center[-1]:
        idim_center = idim_center[::-1]
    if len(jdim_center) > 1 and jdim_center[0] > jdim_center[-1]:
        jdim_center = jdim_center[::-1]

    # 转换为边缘坐标
    idim = _build_edge_coords(idim_center)
    jdim = _build_edge_coords(jdim_center)

    # ── 分析区域 mask ──
    sv_arr = ds_Sv["Sv"].values
    if sv_arr.ndim == 3:
        sv_arr = sv_arr[0]
    n_pings, n_samples = sv_arr.shape
    analysis_mask = build_analysis_mask(
        (n_pings, n_samples), surface_sample, bottom_line
    )
    if analysis_mask is not None:
        # 直接修改 Sv 数组（in-place），避免拷贝整个 Dataset
        original_values = sv_arr.copy()
        sv_arr[~analysis_mask] = -999.0
        ds_for_detect = ds_Sv
        surf_label = f"{surface_sample:.0f}" if surface_sample is not None else "None"
        logger.info(
            f"分析区域限定: 表线={surf_label}, "
            f"有效样本={(analysis_mask.sum() / analysis_mask.size * 100):.1f}%"
        )
    else:
        ds_for_detect = ds_Sv
        original_values = None

    params = {
        "var_name": "Sv",
        "channel": channel,
        "idim": idim,
        "jdim": jdim,
        "thr": school_cfg.get("thr", -55.0),
        "mincan": tuple(school_cfg.get("mincan", [3.0, 10.0])),
        "maxlink": tuple(school_cfg.get("maxlink", [3.0, 15.0])),
        "minsho": tuple(school_cfg.get("minsho", [3.0, 15.0])),
    }

    logger.info(f"鱼群检测: method={method}, thr={params['thr']}")
    mask = detect_shoal(ds_for_detect, method=method, params=params)

    # 恢复原始 Sv 值
    if original_values is not None:
        sv_arr[:] = original_values

    n_detected = int(mask.sum().values)
    logger.info(f"检测到 {n_detected} 个鱼群像素")

    return mask


def schools_to_dataframe(
    mask: xr.DataArray,
    ds_Sv: xr.Dataset,
) -> pd.DataFrame:
    """
    将鱼群 mask 转换为 DataFrame，每个鱼群一行。

    使用 scipy.ndimage.label 进行连通区域标记。

    Parameters
    ----------
    mask : xr.DataArray
        布尔 mask，True 表示鱼群区域
    ds_Sv : xr.Dataset
        包含 Sv 变量的数据集

    Returns
    -------
    pd.DataFrame
        每行一个鱼群，包含 school_id、位置、面积、平均 Sv 等
    """
    from scipy import ndimage

    # 连通区域标记
    labeled, num_features = ndimage.label(mask.values)

    if num_features == 0:
        return pd.DataFrame(columns=[
            "school_id", "ping_start", "ping_end",
            "depth_start", "depth_end", "area",
            "mean_sv", "centroid_depth",
        ])

    # 获取坐标
    ping_time = ds_Sv["ping_time"].values
    if "depth" in ds_Sv:
        depth = ds_Sv["depth"].isel(ping_time=0).values
    elif "echo_range" in ds_Sv:
        depth = ds_Sv["echo_range"].isel(ping_time=0).values
    else:
        depth = np.arange(ds_Sv.sizes["range_sample"], dtype=float)

    Sv = ds_Sv["Sv"].values
    if Sv.ndim == 3:
        Sv = Sv[0]  # 取第一个 channel

    records = []
    for i in range(1, num_features + 1):
        region = labeled == i
        rows, cols = np.where(region)

        if len(rows) == 0:
            continue

        ping_start = ping_time[rows.min()]
        ping_end = ping_time[rows.max()]

        depth_idx_min = cols.min()
        depth_idx_max = cols.max()
        depth_start = depth[depth_idx_min] if depth_idx_min < len(depth) else float(depth_idx_min)
        depth_end = depth[depth_idx_max] if depth_idx_max < len(depth) else float(depth_idx_max)

        # 计算面积（像素数 × 分辨率）
        n_pixels = int(region.sum())
        ping_res = float(np.diff(ping_time[:2])[0]) if len(ping_time) > 1 else 1.0
        depth_res = float(np.diff(depth[:2])[0]) if len(depth) > 1 else 1.0
        area = n_pixels * abs(ping_res) * abs(depth_res)

        # 计算平均 Sv
        sv_values = Sv[region]
        sv_values = sv_values[np.isfinite(sv_values)]
        mean_sv = float(np.mean(sv_values)) if len(sv_values) > 0 else np.nan

        # 中心深度
        centroid_depth = float(depth[int(rows.mean())]) if len(rows) > 0 else np.nan

        records.append({
            "school_id": i,
            "ping_start": ping_start,
            "ping_end": ping_end,
            "depth_start": depth_start,
            "depth_end": depth_end,
            "area": area,
            "mean_sv": mean_sv,
            "centroid_depth": centroid_depth,
        })

    df = pd.DataFrame(records)
    logger.info(f"识别到 {len(df)} 个鱼群")
    return df
