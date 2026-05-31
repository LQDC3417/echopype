"""可视化模块测试"""

import matplotlib
matplotlib.use("Agg")  # 非交互后端

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from src.viz import plot_echogram, plot_density_profile, plot_school_overlay


def _make_mock_data():
    """创建模拟数据"""
    np.random.seed(42)
    Sv = np.random.uniform(-80, -40, (50, 100))
    ds_Sv = xr.Dataset({
        "Sv": xr.DataArray(
            Sv,
            dims=["ping_time", "range_sample"],
            coords={
                "ping_time": np.arange(50),
                "range_sample": np.arange(100),
            },
        ),
        "bottom_depth": xr.DataArray(
            np.linspace(40, 45, 50),
            dims=["ping_time"],
            coords={"ping_time": np.arange(50)},
        ),
    })
    return ds_Sv


def test_plot_echogram(tmp_path):
    """测试 echogram 绘制"""
    ds_Sv = _make_mock_data()
    fig = plot_echogram(ds_Sv, save_path=str(tmp_path / "echogram.png"))
    assert fig is not None
    assert (tmp_path / "echogram.png").exists()


def test_plot_density_profile(tmp_path):
    """测试密度剖面图"""
    density_df = pd.DataFrame({
        "transect_id": [1, 1, 1],
        "depth_layer": ["0-5m", "5-10m", "10-15m"],
        "density_ind_ha": [100, 200, 50],
    })
    fig = plot_density_profile(density_df, save_path=str(tmp_path / "density.png"))
    assert fig is not None
    assert (tmp_path / "density.png").exists()


def test_plot_school_overlay(tmp_path):
    """测试鱼群叠加图"""
    ds_Sv = _make_mock_data()
    mask = xr.DataArray(
        np.zeros((50, 100), dtype=bool),
        dims=["ping_time", "range_sample"],
        coords={"ping_time": np.arange(50), "range_sample": np.arange(100)},
    )
    mask.values[10:20, 30:50] = True

    fig = plot_school_overlay(ds_Sv, mask, save_path=str(tmp_path / "overlay.png"))
    assert fig is not None
    assert (tmp_path / "overlay.png").exists()
