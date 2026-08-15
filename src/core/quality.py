"""数据质量检查模块：验证 Sv 数据完整性与合理性。

职责：
- 处理前数据完整性检查
- Sv 值范围合理性验证
- 缺失数据比例统计
- 底部检测结果验证
"""

import logging

import numpy as np
import xarray as xr

from src.core.utils import get_sv_array, squeeze_sv

logger = logging.getLogger("fish_acoustics")


def check_sv_quality(ds_Sv: xr.Dataset) -> dict:
    """检查 Sv 数据质量。

    Parameters
    ----------
    ds_Sv : xr.Dataset

    Returns
    -------
    dict
        质量检查结果
    """
    sv = get_sv_array(ds_Sv)
    n_pings, n_samples = sv.shape
    warnings_list = []

    # 同时报告原始 Sv 和去噪 Sv 的范围
    sv_raw = squeeze_sv(ds_Sv["Sv"].values) if "Sv" in ds_Sv else sv
    sv_raw_valid = sv_raw[np.isfinite(sv_raw)]
    sv_corrected_valid = sv[np.isfinite(sv)]

    sv_raw_range = (
        (float(np.nanmin(sv_raw_valid)), float(np.nanmax(sv_raw_valid)))
        if len(sv_raw_valid) > 0
        else (float("nan"), float("nan"))
    )
    sv_corrected_range = (
        (float(np.nanmin(sv_corrected_valid)), float(np.nanmax(sv_corrected_valid)))
        if len(sv_corrected_valid) > 0
        else (float("nan"), float("nan"))
    )

    # NaN 比例
    nan_count = int(np.isnan(sv).sum())
    total = n_pings * n_samples
    nan_ratio = nan_count / total if total > 0 else 0.0

    sv_valid = sv_corrected_valid
    if len(sv_valid) == 0:
        warnings_list.append("Sv 全部为 NaN，无有效数据")
        return {
            "valid": False,
            "sv_range": (float("nan"), float("nan")),
            "sv_raw_range": sv_raw_range,
            "sv_corrected_range": sv_corrected_range,
            "nan_ratio": 1.0,
            "total_pings": n_pings,
            "total_samples": n_samples,
            "warnings": warnings_list,
        }

    sv_min = float(np.nanmin(sv_valid))
    sv_max = float(np.nanmax(sv_valid))

    if sv_min < -120:
        warnings_list.append(f"Sv 最小值 {sv_min:.1f} dB 异常偏小（<-120 dB）")
    if sv_max > 10:
        warnings_list.append(f"Sv 最大值 {sv_max:.1f} dB 异常偏大（>10 dB）")
    # 分级 NaN 警告
    if nan_ratio > 0.98:
        warnings_list.append(f"[严重] NaN 比例 {nan_ratio:.1%} 过高（>98%，数据几乎全空）")
    elif nan_ratio > 0.90:
        warnings_list.append(f"[警告] NaN 比例 {nan_ratio:.1%} 偏高（>90%，大部分数据缺失）")
    elif nan_ratio > 0.80:
        warnings_list.append(f"[提示] NaN 比例 {nan_ratio:.1%} 较高（>80%），统计结果可能不稳定")
    if n_pings < 10:
        warnings_list.append(f"Ping 数过少（{n_pings}），统计结果可能不可靠")

    valid = len(warnings_list) == 0
    if valid:
        logger.info(f"数据质量检查通过: {n_pings} pings x {n_samples} samples")
    else:
        logger.warning(f"数据质量检查发现 {len(warnings_list)} 个问题")

    return {
        "valid": valid,
        "sv_range": (sv_min, sv_max),
        "sv_raw_range": sv_raw_range,
        "sv_corrected_range": sv_corrected_range,
        "nan_ratio": nan_ratio,
        "total_pings": n_pings,
        "total_samples": n_samples,
        "warnings": warnings_list,
    }


def check_bottom_line(bottom: np.ndarray, n_samples: int) -> dict:
    """检查底线数据质量。"""
    warnings_list = []
    n_pings = len(bottom)

    nan_count = int(np.isnan(bottom).sum())
    valid_count = n_pings - nan_count

    if valid_count == 0:
        warnings_list.append("底线全部为 NaN，无法检测底部")
        return {"valid": False, "nan_ratio": 1.0, "warnings": warnings_list}

    bottom_valid = bottom[np.isfinite(bottom)]

    if np.any(bottom_valid < -1.0):
        warnings_list.append(f"底线异常负值: {bottom_valid.min():.2f}")
    if np.any(bottom_valid >= n_samples):
        warnings_list.append("底线超出采样范围")

    if valid_count > 1:
        diffs = np.abs(np.diff(bottom_valid))
        max_diff = float(np.max(diffs))
        if max_diff > n_samples * 0.3:
            warnings_list.append(f"底线跳变过大（最大 {max_diff:.0f} samples）")

    nan_ratio = nan_count / n_pings if n_pings > 0 else 0.0
    if nan_ratio > 0.3:
        warnings_list.append(f"底线 NaN 比例 {nan_ratio:.1%} 过高（>30%）")

    return {
        "valid": len(warnings_list) == 0,
        "nan_ratio": nan_ratio,
        "valid_pings": valid_count,
        "warnings": warnings_list,
    }


def print_quality_report(ds_Sv: xr.Dataset, bottom: np.ndarray | None = None) -> None:
    """打印质量检查报告到日志。"""
    logger.info("=" * 50)
    logger.info("数据质量检查报告")
    logger.info("=" * 50)

    sv_check = check_sv_quality(ds_Sv)
    logger.info(f"  Sv 原始范围: [{sv_check['sv_raw_range'][0]:.1f}, {sv_check['sv_raw_range'][1]:.1f}] dB")
    logger.info(f"  Sv 去噪范围: [{sv_check['sv_corrected_range'][0]:.1f}, {sv_check['sv_corrected_range'][1]:.1f}] dB")
    logger.info(f"  数据尺寸: {sv_check['total_pings']} pings x {sv_check['total_samples']} samples")
    logger.info(f"  NaN 比例: {sv_check['nan_ratio']:.1%}")

    for w in sv_check["warnings"]:
        logger.warning(f"  ! {w}")

    if bottom is not None:
        bl_check = check_bottom_line(bottom, sv_check["total_samples"])
        logger.info(f"  底线有效 ping: {bl_check.get('valid_pings', 0)}/{sv_check['total_pings']}")
        for w in bl_check["warnings"]:
            logger.warning(f"  ! {w}")

    logger.info("=" * 50)
