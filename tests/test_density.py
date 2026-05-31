"""密度估算模块测试"""

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from src.density import calculate_nasc, estimate_density


def _make_mock_data():
    """创建模拟数据"""
    np.random.seed(42)
    n_pings = 100
    n_samples = 50

    Sv = np.random.uniform(-80, -40, (n_pings, n_samples))
    Sv[20:40, 10:30] = np.random.uniform(-55, -45, (20, 20))

    ds_Sv = xr.Dataset({
        "Sv": xr.DataArray(
            Sv,
            dims=["ping_time", "range_sample"],
            coords={
                "ping_time": np.arange(n_pings),
                "range_sample": np.arange(n_samples),
            },
        ),
        "echo_range": xr.DataArray(
            np.tile(np.arange(n_samples) * 0.5, (n_pings, 1)),
            dims=["ping_time", "range_sample"],
        ),
    })

    schools_df = pd.DataFrame({
        "school_id": [1],
        "ping_start": [20],
        "ping_end": [39],
        "depth_start": [5.0],
        "depth_end": [14.5],
        "area": [200.0],
        "mean_sv": [-50.0],
        "centroid_depth": [10.0],
    })

    return ds_Sv, schools_df


def test_calculate_nasc():
    """测试 NASC 计算"""
    ds_Sv, _ = _make_mock_data()
    config = {
        "processing": {"frequencies": [38000]},
        "density": {"ts_default": -30.0},
    }
    nasc_df = calculate_nasc(ds_Sv, config)
    assert isinstance(nasc_df, pd.DataFrame)
    assert "nasc" in nasc_df.columns
    assert "transect_id" in nasc_df.columns


def test_estimate_density():
    """测试密度估算"""
    ds_Sv, schools_df = _make_mock_data()
    config = {
        "processing": {"frequencies": [38000]},
        "density": {"ts_default": -30.0},
    }
    density_df = estimate_density(schools_df, ds_Sv, config)
    assert isinstance(density_df, pd.DataFrame)
    assert "density_ind_ha" in density_df.columns
    assert "total_biomass_kg" in density_df.columns
