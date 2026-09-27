"""GUI 与项目重算共用的 echopype 去噪流程。"""

import numpy as np
from src.core.region import crop_sv_by_line_region


def remove_noise(ds, config, manual_mask=None, analysis_ds=None):
    """统一调用 echopype，并保留原始 Sv 与区域外数据。"""
    from echopype.clean import remove_background_noise
    source = analysis_ds if analysis_ds is not None else ds
    # echopype replaces/adds result variables; a shallow Dataset copy isolates its mapping.
    source = source.copy(deep=False)
    source.attrs.setdefault("input_processing_level", "L2A")
    cfg = config.get("processing", {}).get("noise_removal", {})
    result = remove_background_noise(
        source, ping_num=cfg.get("ping_num", 5),
        range_sample_num=cfg.get("range_sample_num", 10),
        SNR_threshold=cfg.get("SNR_threshold", "3.0dB"),
    )
    result = apply_manual_mask(result, manual_mask)
    return merge_region_noise_result(ds, source, result) if analysis_ds is not None else result


def prepare_analysis_dataset(
    ds, config, noise_enabled, manual_mask=None, line_manager=None,
    analysis_region=None, region_enabled=False,
):
    """按已保存策略生成修正数据与分析区域，供界面和快照重算共用。"""
    if noise_enabled is None:
        raise ValueError("自动去噪策略尚未确认")
    region_ds = None
    if region_enabled and analysis_region is not None:
        region_ds, _ = crop_sv_by_line_region(ds, line_manager, analysis_region)
    processed = (
        remove_noise(ds, config, manual_mask, region_ds)
        if noise_enabled
        else apply_manual_mask(ds.drop_vars("Sv_corrected") if "Sv_corrected" in ds else ds, manual_mask)
    )
    if region_enabled and analysis_region is not None:
        analysis_ds, _ = crop_sv_by_line_region(processed, line_manager, analysis_region)
    else:
        analysis_ds = processed
    return processed, analysis_ds


def apply_manual_mask(ds, manual_mask):
    """将手动框选的噪声 mask 应用到数据集（写入 Sv_corrected，不覆盖原始 Sv）。"""
    if manual_mask is None:
        return ds
    result = ds.copy(deep=False)
    source = ds["Sv_corrected"] if "Sv_corrected" in ds else ds["Sv"]
    result["Sv_corrected"] = source.copy(deep=True)
    target = result["Sv_corrected"]
    sv_arr = target.values
    if sv_arr.ndim == 3:
        if manual_mask.shape == sv_arr.shape[1:]:
            sv_arr[:, manual_mask] = np.nan
        else:
            return ds
    elif manual_mask.shape == sv_arr.shape:
        sv_arr[manual_mask] = np.nan
    else:
        return ds
    target.data = sv_arr
    return result


def merge_region_noise_result(original_ds, analysis_ds, processed_ds):
    """将区域内去噪结果写回完整数据，区域外保持原始 Sv。"""
    import xarray as xr

    result = original_ds.copy(deep=False)
    corrected = processed_ds.get("Sv_corrected", analysis_ds["Sv"])
    region_mask = analysis_ds["Sv"].notnull()
    result["Sv_corrected"] = xr.where(region_mask, corrected, original_ds["Sv"])
    return result
