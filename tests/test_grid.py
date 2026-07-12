"""网格化分析模块测试"""

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from src.core.grid import create_grid, compute_grid_stats, compute_grid_density


# ── 测试数据 ──────────────────────────────────────────────

def _make_ds_sv(n_pings=100, n_samples=50):
    """创建带 echo_range 的模拟 ds_Sv"""
    np.random.seed(42)
    Sv = np.random.uniform(-80, -40, (n_pings, n_samples))
    echo_range = np.arange(0.5, 0.5 + n_samples * 0.5, 0.5)[:n_samples]
    er_2d = np.broadcast_to(echo_range, (n_pings, n_samples)).copy()

    return xr.Dataset({
        "Sv": xr.DataArray(Sv, dims=["ping_time", "range_sample"],
                           coords={"ping_time": np.arange(n_pings), "range_sample": np.arange(n_samples)}),
        "echo_range": xr.DataArray(er_2d, dims=["ping_time", "range_sample"]),
    })


# ── create_grid ───────────────────────────────────────────

def test_create_grid_ping():
    """按 ping 数创建网格"""
    ds = _make_ds_sv(n_pings=100, n_samples=50)
    cells = create_grid(ds, surface_depth_m=1.0, vertical_interval_m=5.0,
                        horizontal_interval=50, method="ping")
    assert len(cells) > 0
    for cell in cells:
        assert "ping_start" in cell
        assert "ping_end" in cell
        assert "depth_lo" in cell
        assert "depth_hi" in cell


def test_create_grid_distance():
    """按距离创建网格（无 GPS 时回退到 ping）"""
    ds = _make_ds_sv(n_pings=100, n_samples=50)
    cells = create_grid(ds, surface_depth_m=1.0, vertical_interval_m=5.0,
                        horizontal_interval=500, method="distance")
    assert len(cells) > 0


def test_create_grid_invalid_method():
    """无效方法抛出异常"""
    ds = _make_ds_sv()
    with pytest.raises(ValueError, match="不支持"):
        create_grid(ds, 1.0, 5.0, 100, method="invalid")


# ── compute_grid_stats ────────────────────────────────────

def test_compute_grid_stats_returns_dataframe():
    """返回 DataFrame 并包含必要列"""
    ds = _make_ds_sv()
    cells = create_grid(ds, 1.0, 10.0, 50)
    df = compute_grid_stats(ds, cells)

    assert isinstance(df, pd.DataFrame)
    assert len(df) == len(cells)
    for col in ["cell_id", "mean_sv", "abc", "n_valid"]:
        assert col in df.columns


def test_compute_grid_stats_empty_cell():
    """无数据的网格单元返回 NaN"""
    ds = _make_ds_sv(n_pings=10, n_samples=10)
    # 创建一个超出数据范围的网格
    cells = [{"ping_start": 0, "ping_end": 10, "depth_lo": 100.0, "depth_hi": 200.0}]
    df = compute_grid_stats(ds, cells)
    assert pd.isna(df.iloc[0]["mean_sv"])
    assert df.iloc[0]["n_valid"] == 0


# ── compute_grid_density ──────────────────────────────────

def test_compute_grid_density_returns_dataframe():
    """返回 DataFrame 并包含密度列"""
    ds = _make_ds_sv()
    cells = create_grid(ds, 1.0, 10.0, 50)
    config = {"density": {"ts_default": -30.0, "avg_weight_kg": 0.5}}
    df = compute_grid_density(ds, cells, config)

    assert isinstance(df, pd.DataFrame)
    for col in ["density_ind_m2", "density_ind_ha", "biomass_kg_ha"]:
        assert col in df.columns
