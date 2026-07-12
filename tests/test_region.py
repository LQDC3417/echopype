"""分析区域模块测试"""

import numpy as np
import pytest
import xarray as xr

from src.core.region import (
    depth_to_sample_index,
    bottom_depth_to_sample_indices,
    get_echo_range_1d,
    get_surface_sample,
    get_bottom_samples,
    build_analysis_mask,
    crop_sv_by_region,
)


# ── 测试数据 ──────────────────────────────────────────────

def _make_echo_range(n_samples=100, start=0.5, step=0.5):
    """创建均匀 echo_range"""
    return np.arange(start, start + n_samples * step, step)[:n_samples]


def _make_ds_sv(n_pings=50, n_samples=100, with_echo_range=True):
    """创建模拟 ds_Sv"""
    np.random.seed(42)
    Sv = np.random.uniform(-80, -40, (n_pings, n_samples))

    coords = {
        "ping_time": np.arange(n_pings),
        "range_sample": np.arange(n_samples),
    }
    data_vars = {"Sv": xr.DataArray(Sv, dims=["ping_time", "range_sample"], coords=coords)}

    if with_echo_range:
        echo_range = _make_echo_range(n_samples)
        # broadcast 到 2D
        er_2d = np.broadcast_to(echo_range, (n_pings, n_samples)).copy()
        data_vars["echo_range"] = xr.DataArray(er_2d, dims=["ping_time", "range_sample"], coords=coords)

    return xr.Dataset(data_vars)


# ── depth_to_sample_index ─────────────────────────────────

def test_depth_to_sample_index_basic():
    """基本转换"""
    echo_range = np.array([0.5, 1.0, 1.5, 2.0, 2.5])
    assert depth_to_sample_index(0.5, echo_range) == 0
    assert depth_to_sample_index(1.0, echo_range) == 1
    assert depth_to_sample_index(2.5, echo_range) == 4


def test_depth_to_sample_index_between():
    """深度在两个采样点之间"""
    echo_range = np.array([0.5, 1.0, 1.5, 2.0])
    # 1.3 在 1.0 和 1.5 之间，searchsorted 返回 2
    idx = depth_to_sample_index(1.3, echo_range)
    assert idx == 2


def test_depth_to_sample_index_clamp():
    """深度超出范围时裁剪"""
    echo_range = np.array([0.5, 1.0, 1.5])
    assert depth_to_sample_index(0.0, echo_range) == 0
    assert depth_to_sample_index(10.0, echo_range) == 2


# ── bottom_depth_to_sample_indices ────────────────────────

def test_bottom_depth_to_sample_indices_basic():
    """基本转换"""
    echo_range = np.array([0.5, 1.0, 1.5, 2.0, 2.5])
    bottom_depth = np.array([1.0, 2.0, np.nan, 0.5, 3.0])
    result = bottom_depth_to_sample_indices(bottom_depth, echo_range)

    assert result.dtype == np.float32
    assert len(result) == 5
    assert result[0] == 1  # 1.0 → index 1
    assert result[1] == 3  # 2.0 → index 3
    assert np.isnan(result[2])  # NaN 输入
    assert result[3] == 0  # 0.5 → index 0
    assert result[4] == 4  # 3.0 超出范围，裁剪到 4


def test_bottom_depth_to_sample_indices_all_nan():
    """全部 NaN"""
    echo_range = np.array([0.5, 1.0, 1.5])
    bottom_depth = np.array([np.nan, np.nan])
    result = bottom_depth_to_sample_indices(bottom_depth, echo_range)
    assert np.all(np.isnan(result))


def test_bottom_depth_to_sample_indices_negative():
    """负深度视为无效"""
    echo_range = np.array([0.5, 1.0, 1.5])
    bottom_depth = np.array([-1.0, 0.0])
    result = bottom_depth_to_sample_indices(bottom_depth, echo_range)
    assert np.isnan(result[0])  # 负值
    # 0.0 经过 searchsorted 会返回 index 0，但 bd <= 0 被跳过
    # 实际实现：valid_mask = (~np.isnan(bd)) & (bd > 0)，所以 0.0 也被排除


# ── get_echo_range_1d ─────────────────────────────────────

def test_get_echo_range_1d_with_channel():
    """有 channel 维度时取第一个"""
    echo_range = np.array([0.5, 1.0, 1.5])
    ds = xr.Dataset({
        "echo_range": xr.DataArray(
            np.broadcast_to(echo_range, (3, 2, 3)).copy(),
            dims=["ping_time", "channel", "range_sample"],
        ),
    })
    result = get_echo_range_1d(ds)
    assert result is not None
    assert result.shape == (3,)
    np.testing.assert_array_almost_equal(result, echo_range)


def test_get_echo_range_1d_2d():
    """2D echo_range 取第一个 ping"""
    echo_range = np.array([[0.5, 1.0, 1.5], [0.6, 1.1, 1.6]])
    ds = xr.Dataset({
        "echo_range": xr.DataArray(echo_range, dims=["ping_time", "range_sample"]),
    })
    result = get_echo_range_1d(ds)
    assert result is not None
    assert result.shape == (3,)


def test_get_echo_range_1d_missing():
    """无 echo_range 时返回 None"""
    ds = xr.Dataset({"Sv": xr.DataArray(np.zeros((5, 10)), dims=["ping_time", "range_sample"])})
    assert get_echo_range_1d(ds) is None


# ── build_analysis_mask ───────────────────────────────────

def test_build_analysis_mask_none():
    """两者都为 None 时返回 None"""
    assert build_analysis_mask((50, 100), None, None) is None


def test_build_analysis_mask_surface_only():
    """只有表线"""
    mask = build_analysis_mask((50, 100), surface_sample=10.0, bottom_line=None)
    assert mask.shape == (50, 100)
    assert np.all(mask[:, 10:] == True)
    assert np.all(mask[:, :10] == False)


def test_build_analysis_mask_bottom_only():
    """只有底线"""
    bottom = np.full(50, 80.0)
    mask = build_analysis_mask((50, 100), surface_sample=None, bottom_line=bottom)
    assert mask.shape == (50, 100)
    assert np.all(mask[:, :80] == True)
    assert np.all(mask[:, 81:] == False)


def test_build_analysis_mask_both():
    """表线 + 底线"""
    bottom = np.full(50, 80.0)
    mask = build_analysis_mask((50, 100), surface_sample=10.0, bottom_line=bottom)
    assert mask.shape == (50, 100)
    assert np.all(mask[:, :10] == False)  # 表线以上
    assert np.all(mask[:, 10:80] == True)  # 分析区域
    assert np.all(mask[:, 81:] == False)  # 底线以下


def test_build_analysis_mask_bottom_nan():
    """底线有 NaN 时该 ping 不排除"""
    bottom = np.full(50, 80.0)
    bottom[10] = np.nan  # 该 ping 无底线
    mask = build_analysis_mask((50, 100), surface_sample=None, bottom_line=bottom)
    assert np.all(mask[10, :] == True)  # NaN 的 ping 全部保留


# ── crop_sv_by_region ─────────────────────────────────────

def test_crop_sv_by_region_no_params():
    """无参数时返回原数据集"""
    ds = _make_ds_sv()
    result = crop_sv_by_region(ds)
    assert result is ds


def test_crop_sv_by_region_with_surface():
    """表线裁剪"""
    ds = _make_ds_sv(n_pings=10, n_samples=20)
    result = crop_sv_by_region(ds, surface_depth_m=2.0)

    # Sv 中表线以上应为 NaN
    sv = result["Sv"].values
    # echo_range 从 0.5 开始，步长 0.5，所以 2.0m 对应 index 3
    assert np.all(np.isnan(sv[:, :3]))


def test_crop_sv_by_region_masks_both_sv_and_sv_corrected():
    """同时裁剪 Sv 和 Sv_corrected"""
    ds = _make_ds_sv(n_pings=10, n_samples=20)
    # 添加 Sv_corrected
    ds["Sv_corrected"] = ds["Sv"].copy()

    result = crop_sv_by_region(ds, surface_depth_m=2.0)

    sv = result["Sv"].values
    sv_corr = result["Sv_corrected"].values
    # 两者都应被裁剪
    assert np.all(np.isnan(sv[:, :3]))
    assert np.all(np.isnan(sv_corr[:, :3]))
