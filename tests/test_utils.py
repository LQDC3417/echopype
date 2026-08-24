"""工具函数模块测试"""

import numpy as np
import pytest
import xarray as xr

from src.core.utils import (
    depth_resolution,
    get_sv_array,
    get_vertical_coords,
    ping_resolution,
    squeeze_sv,
    sv_to_linear,
)


# ── squeeze_sv ────────────────────────────────────────────

def test_squeeze_sv_3d():
    """3D 数组降维为 2D"""
    sv = np.random.rand(1, 50, 100)
    result = squeeze_sv(sv)
    assert result.shape == (50, 100)


def test_squeeze_sv_2d():
    """2D 数组不变"""
    sv = np.random.rand(50, 100)
    result = squeeze_sv(sv)
    assert result.shape == (50, 100)
    np.testing.assert_array_equal(result, sv)


# ── sv_to_linear ──────────────────────────────────────────

def test_sv_to_linear_basic():
    """基本转换: Sv(dB) → 线性值"""
    Sv = np.array([0.0, -10.0, -20.0])
    result = sv_to_linear(Sv)
    np.testing.assert_array_almost_equal(result, [1.0, 0.1, 0.01])


def test_sv_to_linear_nan():
    """NaN 位置保留 NaN（下游 nansum 会正确处理）"""
    Sv = np.array([0.0, np.nan, -20.0])
    result = sv_to_linear(Sv)
    assert result[0] == 1.0
    assert np.isnan(result[1])
    assert result[2] == pytest.approx(0.01)


def test_sv_to_linear_inf():
    """Inf 位置返回 NaN"""
    Sv = np.array([0.0, np.inf, -np.inf])
    result = sv_to_linear(Sv)
    assert result[0] == 1.0
    assert np.isnan(result[1])
    assert np.isnan(result[2])


def test_sv_to_linear_2d():
    """2D 数组"""
    Sv = np.array([[-70.0, -60.0], [-50.0, -40.0]])
    result = sv_to_linear(Sv)
    assert result.shape == (2, 2)
    assert result[0, 0] == pytest.approx(1e-7)


# ── get_sv_array ──────────────────────────────────────────

def test_get_sv_array_prefers_sv_corrected():
    """优先使用 Sv_corrected"""
    ds = xr.Dataset({
        "Sv": xr.DataArray(np.full((10, 20), -70.0), dims=["ping_time", "range_sample"]),
        "Sv_corrected": xr.DataArray(np.full((10, 20), -50.0), dims=["ping_time", "range_sample"]),
    })
    result = get_sv_array(ds)
    assert result[0, 0] == -50.0


def test_get_sv_array_falls_back_to_sv():
    """无 Sv_corrected 时使用 Sv"""
    ds = xr.Dataset({
        "Sv": xr.DataArray(np.full((10, 20), -70.0), dims=["ping_time", "range_sample"]),
    })
    result = get_sv_array(ds)
    assert result[0, 0] == -70.0


def test_get_sv_array_squeezes_3d():
    """3D 数据自动降维"""
    ds = xr.Dataset({
        "Sv": xr.DataArray(np.full((1, 10, 20), -70.0), dims=["channel", "ping_time", "range_sample"]),
    })
    result = get_sv_array(ds)
    assert result.shape == (10, 20)


# ── get_vertical_coords ───────────────────────────────────

def test_get_vertical_coords_with_depth():
    """有 depth 变量时使用 depth"""
    ds = xr.Dataset({
        "Sv": xr.DataArray(np.zeros((5, 10)), dims=["ping_time", "range_sample"]),
        "depth": xr.DataArray(
            np.broadcast_to(np.arange(0.5, 5.5, 0.5), (5, 10)).copy(),
            dims=["ping_time", "range_sample"],
        ),
    })
    result = get_vertical_coords(ds)
    assert len(result) == 10
    assert result[0] == pytest.approx(0.5)


def test_get_vertical_coords_with_echo_range():
    """无 depth 时使用 echo_range"""
    echo_range = np.arange(0.5, 5.5, 0.5)
    ds = xr.Dataset({
        "Sv": xr.DataArray(np.zeros((5, 10)), dims=["ping_time", "range_sample"]),
        "echo_range": xr.DataArray(
            np.broadcast_to(echo_range, (5, 10)).copy(),
            dims=["ping_time", "range_sample"],
        ),
    })
    result = get_vertical_coords(ds)
    assert len(result) == 10
    assert result[0] == pytest.approx(0.5)


def test_get_vertical_coords_fallback_to_range_sample():
    """无 depth/echo_range 时 fallback 到 range_sample"""
    ds = xr.Dataset({
        "Sv": xr.DataArray(np.zeros((5, 10)), dims=["ping_time", "range_sample"]),
    })
    result = get_vertical_coords(ds)
    assert len(result) == 10
    # range_sample 是 0, 1, 2, ...
    assert result[0] == pytest.approx(0.0)


# ── depth_resolution / ping_resolution ────────────────────

def test_depth_resolution_skips_zero_diffs():
    """零差值（EK80 重复深度填充）不拉低分辨率"""
    depth = np.array([0.0, 1.0, 1.0, 1.0, 3.0])  # 重复 1.0
    result = depth_resolution(depth)
    # diff = [1, 0, 0, 2]，非零中位数 = median([1, 2]) = 1.5
    assert result == pytest.approx(1.5)


def test_depth_resolution_short_array():
    """长度 <= 1 时返回默认 0.1"""
    assert depth_resolution(np.array([1.0])) == pytest.approx(0.1)
    assert depth_resolution(np.array([])) == pytest.approx(0.1)


def test_ping_resolution_datetime64():
    """datetime64 ping_time → 秒"""
    ping_time = np.array(["2026-01-01T00:00:00", "2026-01-01T00:00:05",
                          "2026-01-01T00:00:10"], dtype="datetime64")
    assert ping_resolution(ping_time) == pytest.approx(5.0)


def test_ping_resolution_numeric():
    """数值 ping_time → 原值"""
    assert ping_resolution(np.array([0.0, 2.0, 4.0])) == pytest.approx(2.0)
    assert ping_resolution(np.array([0.0])) == pytest.approx(1.0)
