"""密度模块测试（保留：ABC 积分、Sv 统计摘要）"""

import numpy as np
import pandas as pd
import xarray as xr

from src.core.density import (
    calculate_abc, sv_statistics_summary,
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


# ── sv_statistics_summary ─────────────────────────────────

def test_sv_statistics_summary_basic():
    """基本统计"""
    ds = _make_ds_sv()
    df = sv_statistics_summary(ds)

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1
    for col in ["mean_sv", "median_sv", "std_sv", "p5_sv", "p95_sv"]:
        assert col in df.columns
