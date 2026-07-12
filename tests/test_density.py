"""密度估算模块测试"""

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from src.core.density import (
    calculate_abc, calculate_nasc, estimate_density,
    estimate_density_by_depth, sv_statistics_summary,
)


# ── 测试数据 ──────────────────────────────────────────────

def _make_ds_sv(n_pings=50, n_samples=100):
    """创建带 echo_range 的模拟 ds_Sv"""
    np.random.seed(42)
    Sv = np.random.uniform(-80, -40, (n_pings, n_samples))
    echo_range = np.arange(0.5, 0.5 + n_samples * 0.5, 0.5)[:n_samples]
    er_2d = np.broadcast_to(echo_range, (n_pings, n_samples)).copy()

    return xr.Dataset({
        "Sv": xr.DataArray(Sv, dims=["ping_time", "range_sample"],
                           coords={"ping_time": np.arange(n_pings), "range_sample": np.arange(n_samples)}),
        "echo_range": xr.DataArray(er_2d, dims=["ping_time", "range_sample"]),
        "ping_time": xr.DataArray(np.arange(n_pings), dims=["ping_time"]),
    })


# ── calculate_abc ─────────────────────────────────────────

def test_calculate_abc_returns_dataframe():
    """返回 DataFrame"""
    ds = _make_ds_sv()
    df = calculate_abc(ds, {})
    assert isinstance(df, pd.DataFrame)
    assert "abc" in df.columns
    assert len(df) == 50


def test_calculate_abc_positive():
    """ABC 应为正值"""
    ds = _make_ds_sv()
    df = calculate_abc(ds, {})
    assert (df["abc"] >= 0).all()


def test_calculate_abc_matches_nasc():
    """ABC 和 NASC 的关系: NASC = ABC * 1852^2"""
    ds = _make_ds_sv()
    abc_df = calculate_abc(ds, {})
    nasc_df = calculate_nasc(ds, {})

    ratio = nasc_df["nasc"].values / abc_df["abc"].values
    np.testing.assert_array_almost_equal(ratio, 1852 ** 2, decimal=0)


# ── estimate_density ──────────────────────────────────────

def test_estimate_density_no_schools():
    """无鱼群时计算全断面密度"""
    ds = _make_ds_sv()
    config = {"density": {"ts_default": -30.0, "avg_weight_kg": 0.5}}
    schools_df = pd.DataFrame(columns=["school_id", "ping_start", "ping_end", "depth_start", "depth_end"])

    df = estimate_density(schools_df, ds, config)
    assert len(df) == 1
    assert "density_ind_m2" in df.columns
    assert "density_ind_ha" in df.columns


# ── estimate_density_by_depth ─────────────────────────────

def test_estimate_density_by_depth_default_bins():
    """默认分层"""
    ds = _make_ds_sv()
    config = {"density": {"ts_default": -30.0, "avg_weight_kg": 0.5}}
    df = estimate_density_by_depth(ds, config)

    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0
    assert "depth_layer" in df.columns
    assert "density_ind_m2" in df.columns


def test_estimate_density_by_depth_custom_bins():
    """自定义分层"""
    ds = _make_ds_sv()
    config = {"density": {"ts_default": -30.0, "avg_weight_kg": 0.5}}
    df = estimate_density_by_depth(ds, config, depth_bins=[0, 10, 20, 30])

    assert len(df) == 3
    assert df.iloc[0]["depth_layer"] == "0-10m"


# ── sv_statistics_summary ─────────────────────────────────

def test_sv_statistics_summary_basic():
    """基本统计"""
    ds = _make_ds_sv()
    df = sv_statistics_summary(ds)

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1
    for col in ["mean_sv", "median_sv", "std_sv", "p5_sv", "p95_sv"]:
        assert col in df.columns
