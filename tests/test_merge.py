"""多文件对齐拼接测试"""

import numpy as np
import pytest
import xarray as xr

from src.core.merge import compute_common_grid, merge_aligned


def _make_ds(ping_times, echo_range, sv_rows=None):
    """构造带 Sv + echo_range + ping_time 的数据集"""
    n_pings = len(ping_times)
    n_samples = len(echo_range)
    if sv_rows is None:
        sv_rows = np.random.uniform(-70, -30, (n_pings, n_samples))
    return xr.Dataset(
        {
            "Sv": xr.DataArray(sv_rows.astype(np.float32), dims=["ping_time", "range_sample"]),
        },
        coords={
            "ping_time": ("ping_time", np.array(ping_times, dtype="datetime64[ns]")),
            "echo_range": ("range_sample", np.asarray(echo_range, dtype=np.float32)),
        },
    )


class TestComputeCommonGrid:
    def test_identical_grids(self):
        """网格一致时直接返回"""
        g1 = np.arange(0, 100, 0.5)
        g2 = np.arange(0, 100, 0.5)
        common = compute_common_grid([_make_ds([0], g1), _make_ds([1], g2)])
        np.testing.assert_allclose(common, g1)

    def test_offset_grids_intersection(self):
        """起点偏移的网格 → 取交集"""
        g1 = np.arange(0, 100, 1.0)
        g2 = np.arange(10, 110, 1.0)
        common = compute_common_grid([_make_ds([0], g1), _make_ds([1], g2)])
        assert common[0] >= 10.0
        assert common[-1] <= 100.0
        assert len(common) > 10


class TestMergeAligned:
    def test_time_sorting(self):
        """文件乱序时按真实时间戳排序"""
        # 文件 A 时间在后，文件 B 时间在前
        ds_a = _make_ds(
            ["2026-01-01T00:01:00", "2026-01-01T00:01:10"], np.arange(0, 10, 1.0),
            sv_rows=np.array([[1.0] * 10, [2.0] * 10]),
        )
        ds_b = _make_ds(
            ["2026-01-01T00:00:00", "2026-01-01T00:00:10"], np.arange(0, 10, 1.0),
            sv_rows=np.array([[3.0] * 10, [4.0] * 10]),
        )
        merged = merge_aligned([ds_a, ds_b])
        times = merged["ping_time"].values
        assert times[0] == np.datetime64("2026-01-01T00:00:00")
        assert times[-1] == np.datetime64("2026-01-01T00:01:10")
        # 排序后 Sv 顺序也应正确（Sv 为 3D: channel × ping × sample）
        assert merged["Sv"].values[0, 0, 0] == pytest.approx(3.0)
        assert merged["Sv"].values[0, -1, 0] == pytest.approx(2.0)

    def test_dedup_overlap(self):
        """重叠时间戳去重"""
        ds_a = _make_ds(
            ["2026-01-01T00:00:00", "2026-01-01T00:00:10"], np.arange(0, 10, 1.0)
        )
        ds_b = _make_ds(
            ["2026-01-01T00:00:10", "2026-01-01T00:00:20"], np.arange(0, 10, 1.0)
        )
        merged = merge_aligned([ds_a, ds_b], dedup=True)
        assert len(merged["ping_time"]) == 3  # 4 ping - 1 重叠

    def test_depth_resample(self):
        """不同深度网格重采样到公共网格"""
        # 文件 A: 0-9m，文件 B: 5-14m（起点偏移）
        ds_a = _make_ds(
            ["2026-01-01T00:00:00", "2026-01-01T00:00:10"], np.arange(0, 10, 1.0),
            sv_rows=np.array([[1.0] * 10, [2.0] * 10]),
        )
        ds_b = _make_ds(
            ["2026-01-01T00:00:20", "2026-01-01T00:00:30"], np.arange(5, 15, 1.0),
            sv_rows=np.array([[3.0] * 10, [4.0] * 10]),
        )
        merged = merge_aligned([ds_a, ds_b])
        # 公共网格应在交集 [5, 9] 附近（echo_range 为 3D: channel × ping × sample）
        er = merged["echo_range"].values[0, 0]  # 第一 channel 第一 ping
        assert er[0] >= 5.0
        assert er[-1] <= 9.0
        # 所有文件重采样后 sample 方向长度一致（Sv: channel × ping × sample）
        assert merged["Sv"].shape[2] == len(er)
