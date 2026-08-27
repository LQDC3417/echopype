import numpy as np
import xarray as xr

from src.gui.workers import merge_region_noise_result


def test_noise_result_keeps_values_outside_analysis_region_unchanged():
    original = xr.Dataset({"Sv": (("ping_time", "range_sample"), np.full((2, 4), -60.0))})
    analysis = original.copy(deep=True)
    analysis["Sv"].values[:, [0, 3]] = np.nan
    processed = analysis.copy(deep=True)
    processed["Sv_corrected"] = analysis["Sv"].copy(deep=True)
    processed["Sv_corrected"].values[:, 1:3] = -75.0

    result = merge_region_noise_result(original, analysis, processed)

    np.testing.assert_allclose(result["Sv_corrected"].values[:, [0, 3]], -60.0)
    np.testing.assert_allclose(result["Sv_corrected"].values[:, 1:3], -75.0)
    np.testing.assert_allclose(result["Sv"].values, -60.0)
