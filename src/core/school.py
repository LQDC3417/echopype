"""鱼群识别模块：基于 Sv 阈值的鱼群检测与聚类"""

import logging

import numpy as np
import pandas as pd
import xarray as xr

from src.core.utils import get_sv_array, get_vertical_coords

logger = logging.getLogger("fish_acoustics")


def _build_edge_coords(center_coords: np.ndarray) -> np.ndarray:
    """将中心坐标转换为边缘坐标（长度 n → n+1）。"""
    if len(center_coords) < 2:
        return np.array([center_coords[0] - 0.5, center_coords[0] + 0.5])

    edges = np.empty(len(center_coords) + 1)
    step = center_coords[1] - center_coords[0]
    edges[0] = center_coords[0] - step / 2
    edges[1:] = center_coords + step / 2
    return edges


def detect_schools(
    ds_Sv: xr.Dataset,
    config: dict,
) -> xr.DataArray:
    """
    鱼群检测：使用 echopype 公共 API detect_shoal

    Parameters
    ----------
    ds_Sv : xr.Dataset
        包含 Sv 变量的数据集。若已启用分析区域，应传入裁剪后的 ds_Sv。
    config : dict
        配置字典，需包含 school_detection 子项

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

    channel = str(ds_Sv["channel"].values[0]) if "channel" in ds_Sv.dims else None
    ping_time = ds_Sv["ping_time"].values

    # 优先使用去噪数据
    var_name = "Sv_corrected" if "Sv_corrected" in ds_Sv else "Sv"

    # 垂直坐标
    idim_center = get_vertical_coords(ds_Sv)

    # 确保单调递增（同步反转 Sv 数据以保持对齐）
    if len(idim_center) > 1 and idim_center[0] > idim_center[-1]:
        idim_center = idim_center[::-1]
        # 同步反转 Sv 的深度维度
        sv_arr = ds_Sv[var_name].values
        if sv_arr.ndim == 3:
            ds_Sv[var_name].values[0, :, :] = sv_arr[0, :, ::-1]
        else:
            ds_Sv[var_name].values[:] = sv_arr[:, ::-1]

    jdim_center = ping_time.astype(float)
    if len(jdim_center) > 1 and jdim_center[0] > jdim_center[-1]:
        jdim_center = jdim_center[::-1]

    idim = _build_edge_coords(idim_center)
    jdim = _build_edge_coords(jdim_center)

    params = {
        "var_name": var_name,
        "channel": channel,
        "idim": idim,
        "jdim": jdim,
        "thr": school_cfg.get("thr", -55.0),
        "mincan": tuple(school_cfg.get("mincan", [3.0, 10.0])),
        "maxlink": tuple(school_cfg.get("maxlink", [3.0, 15.0])),
        "minsho": tuple(school_cfg.get("minsho", [3.0, 15.0])),
    }

    logger.info(f"鱼群检测: method={method}, var={var_name}, thr={params['thr']}")
    mask = detect_shoal(ds_Sv, method=method, params=params)

    n_detected = int(mask.sum().values)
    logger.info(f"检测到 {n_detected} 个鱼群像素")

    return mask


def schools_to_dataframe(
    mask: xr.DataArray,
    ds_Sv: xr.Dataset,
) -> pd.DataFrame:
    """
    将鱼群 mask 转换为 DataFrame，每个鱼群一行。

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

    labeled, num_features = ndimage.label(mask.values)

    if num_features == 0:
        return pd.DataFrame(columns=[
            "school_id", "ping_start", "ping_end",
            "depth_start", "depth_end", "area",
            "mean_sv", "centroid_depth",
        ])

    ping_time = ds_Sv["ping_time"].values
    depth = get_vertical_coords(ds_Sv)
    Sv = get_sv_array(ds_Sv)

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

        n_pixels = int(region.sum())
        # 避免 datetime 与 float 混算：ping_res 单位为秒
        if np.issubdtype(ping_time.dtype, np.datetime64):
            ping_res_s = float(np.diff(ping_time[:2]) / np.timedelta64(1, 's')) if len(ping_time) > 1 else 1.0
        else:
            ping_res_s = float(np.diff(ping_time[:2])[0]) if len(ping_time) > 1 else 1.0
        depth_res = float(np.median(np.abs(np.diff(depth)))) if len(depth) > 1 else 1.0
        area = n_pixels * abs(ping_res_s) * depth_res

        sv_values = Sv[region]
        sv_values = sv_values[np.isfinite(sv_values)]
        mean_sv = float(np.mean(sv_values)) if len(sv_values) > 0 else np.nan

        centroid_depth = float(depth[int(cols.mean())]) if len(cols) > 0 else np.nan

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
