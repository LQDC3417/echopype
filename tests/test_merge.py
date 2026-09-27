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


def _make_two_channel_ds(ping_times, values):
    values = np.asarray(values, dtype=np.float32)
    return xr.Dataset(
        {"Sv": (("channel", "ping_time", "range_sample"), values)},
        coords={
            "channel": [38.0, 120.0],
            "ping_time": ("ping_time", np.array(ping_times, dtype="datetime64[ns]")),
            "range_sample": [0, 1],
            "echo_range": ("range_sample", [1.0, 2.0]),
        },
    )


class TestComputeCommonGrid:
    def test_identical_grids(self):
        """网格一致时直接返回"""
        g1 = np.arange(0, 100, 0.5)
        g2 = np.arange(0, 100, 0.5)
        common = compute_common_grid([_make_ds([0], g1), _make_ds([1], g2)])
        np.testing.assert_allclose(common, g1)

    def test_offset_grids_union(self):
        """起点偏移的网格完整保留两端。"""
        g1 = np.arange(0, 100, 1.0)
        g2 = np.arange(10, 110, 1.0)
        common = compute_common_grid([_make_ds([0], g1), _make_ds([1], g2)])
        assert common[0] == 0.0
        assert common[-1] == 109.0
        assert len(common) > 10


class TestMergeAligned:
    def test_preserves_each_channel(self):
        first = _make_two_channel_ds(
            ["2026-01-01T00:00:00"],
            [[[1.0, 1.0]], [[10.0, 10.0]]],
        )
        second = _make_two_channel_ds(
            ["2026-01-01T00:01:00"],
            [[[2.0, 2.0]], [[20.0, 20.0]]],
        )

        merged = merge_aligned([first, second])

        assert merged["channel"].values.tolist() == [38.0, 120.0]
        assert merged["Sv"].values[:, :, 0].tolist() == [[1.0, 2.0], [10.0, 20.0]]

    def test_rejects_channel_specific_depth_grids(self):
        source = _make_two_channel_ds(
            ["2026-01-01T00:00:00"],
            [[[1.0, 1.0]], [[10.0, 10.0]]],
        ).assign_coords(
            echo_range=(
                ("channel", "ping_time", "range_sample"),
                [[[1.0, 2.0]], [[10.0, 20.0]]],
            )
        )

        with pytest.raises(ValueError, match="共享相同的 echo_range"):
            merge_aligned([source, source])

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
        ds_b["Sv"].values[0] = ds_a["Sv"].values[1]
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
        # 公共网格覆盖并集 [0, 14]，未采集范围不外推。
        er = merged["echo_range"].values[0, 0]  # 第一 channel 第一 ping
        assert er[0] == 0.0
        assert er[-1] == 14.0
        assert np.isnan(merged.Sv.values[0, :2, 10:]).all()
        assert np.isnan(merged.Sv.values[0, 2:, :5]).all()
        # 所有文件重采样后 sample 方向长度一致（Sv: channel × ping × sample）
        assert merged["Sv"].shape[2] == len(er)



def test_merge_preserves_masked_samples():
    ds = _make_ds([0], [1., 2., 3.], np.array([[-40., -40., -40.]]))
    ds["Sv_corrected"] = (("ping_time", "range_sample"), [[-40., np.nan, -40.]])
    merged = merge_aligned([ds])
    assert np.isnan(merged.Sv_corrected.values[0, 0, 1])


def test_merge_duplicate_only_ping_aligns_auxiliary_data():
    ds = _make_ds([0], [1., 2.], np.array([[-40., -40.]]))
    ds["Sv_corrected"] = ds.Sv.copy()
    ds["bottom_depth"] = (("ping_time",), [2.])
    ds["gain_correction"] = (("ping_time",), [25.])
    ds = ds.assign_coords(latitude=("ping_time", [30.]), longitude=("ping_time", [120.]))
    merged = merge_aligned([ds, ds])
    assert merged.sizes["ping_time"] == 1
    assert merged.bottom_depth.item() == 2.
    assert merged.latitude.item() == 30.


def test_merge_transposed_dimensions():
    ds = _make_ds([0, 1], [1., 2., 3.], np.array([[-40.] * 3, [-50.] * 3]))
    merged = merge_aligned([ds.transpose("range_sample", "ping_time")])
    np.testing.assert_allclose(merged.Sv.values[0], ds.Sv.values)


def test_merge_preserves_transducer_depth_offset():
    ds = _make_ds([0], [1., 2., 3.], np.array([[-40.] * 3]))
    ds["depth"] = ds.echo_range + 5.
    merged = merge_aligned([ds])
    np.testing.assert_allclose(merged.depth.values[0, 0], [6., 7., 8.])


def test_merge_uses_each_ping_range_grid():
    ds = _make_ds([0, 1], [1., 2., 3.], np.array([[-40., -50., -60.]] * 2))
    ds = ds.assign_coords(echo_range=(("ping_time", "range_sample"), [[1., 2., 3.], [2., 3., 4.]]))
    merged = merge_aligned([ds])
    assert np.isnan(merged.Sv.values[0, 1, 0])
    assert merged.Sv.values[0, 1, 1] == -40.
    assert merged.echo_range.values[0, 0, -1] == 4.
    assert merged.Sv.values[0, 1, -1] == -60.


def test_merge_keeps_channel_and_ping_calibration():
    ds = _make_two_channel_ds([0], [[[-40., -40.]], [[-50., -50.]]])
    ds["frequency_nominal"] = (("channel",), [38000., 120000.])
    ds["sound_absorption"] = (("channel", "ping_time"), [[.01], [.02]])
    merged = merge_aligned([ds, ds])
    np.testing.assert_array_equal(merged.frequency_nominal.values, [38000., 120000.])
    np.testing.assert_array_equal(merged.sound_absorption.values, [[.01], [.02]])


def test_resample_averages_linear_power_but_keeps_depth_geometric():
    from src.core.merge import _resample_sv
    ds = _make_ds([0], [1., 3.], np.array([[-40., -60.]]))
    value = _resample_sv(ds, np.array([2.]))[0, 0]
    np.testing.assert_allclose(value, 10 * np.log10((1e-4 + 1e-6) / 2), rtol=1e-6)
    depth = _resample_sv(ds.assign(Sv=(ds.echo_range + 5).broadcast_like(ds.Sv)), np.array([2.]), logarithmic=False)
    np.testing.assert_allclose(depth, [[7.]])


def test_merge_union_resolution_and_sources_are_order_independent():
    a = _make_ds([0, 1], [0., 2., 4.], np.full((2, 3), -40.))
    b = _make_ds([2, 3], [5., 6., 7.], np.full((2, 3), -50.))
    a = a.assign_coords(source_file=("ping_time", ["a.raw", "a.raw"]))
    b = b.assign_coords(source_file=("ping_time", ["b.raw", "b.raw"]))
    merged = merge_aligned([b, a])
    xr.testing.assert_equal(merged, merge_aligned([a, b]))
    np.testing.assert_array_equal(merged.echo_range.values[0, 0], np.arange(8.))
    assert merged.source_file.values.tolist() == ["a.raw", "a.raw", "b.raw", "b.raw"]
    assert np.isnan(merged.Sv.values[0, 0, 5:]).all()
    assert np.isnan(merged.Sv.values[0, 3, :5]).all()


def test_merge_duplicate_conflict_calibration_and_invalid_range():
    a = _make_ds([0], [1., 2.], np.full((1, 2), -40.))
    b = _make_ds([0], [1., 2.], np.full((1, 2), -50.))
    with pytest.raises(ValueError, match="Sv 数据冲突"):
        merge_aligned([a, b])
    a["frequency_nominal"] = 38000.
    b["frequency_nominal"] = 120000.
    with pytest.raises(ValueError, match="校准参数"):
        merge_aligned([a, b])
    with pytest.raises(ValueError, match="无有效距离"):
        merge_aligned([a.assign_coords(echo_range=("range_sample", [np.nan, np.nan]))])


def test_merge_records_duplicate_and_gap_indices():
    ds = _make_ds([0, 1, 2, 100, 101], [1., 2.], np.full((5, 2), -40.))
    ds = ds.assign_coords(source_file=("ping_time", ["a.raw"] * 5))
    merged = merge_aligned([ds, ds])
    assert merged.attrs["merge_duplicate_count"] == 5
    assert merged.attrs["merge_gap_ping_indices"] == "[3]"
    assert merged.source_file.values.tolist() == ["a.raw"] * 5


def test_common_grid_preserves_identical_fractional_positions():
    ranges = np.linspace(.001, 17.134, 1000, dtype=np.float32)
    ds = _make_ds([0, 1], ranges)
    np.testing.assert_array_equal(compute_common_grid([ds, ds]), ranges)


def test_merge_variable_valid_lengths_preserves_original_sampling():
    ranges = np.arange(33132) * .00301825477
    per_ping = np.tile(ranges, (3, 1))
    per_ping[0, 6958:] = np.nan
    per_ping[2, 12000:] = np.nan
    values = np.where(np.isfinite(per_ping), -40., np.nan)
    ds = _make_ds([0, 1, 2], ranges, values)
    ds = ds.assign_coords(echo_range=(("ping_time", "range_sample"), per_ping))
    parts = [ds.isel(ping_time=slice(None, 1)), ds.isel(ping_time=slice(1, None))]
    np.testing.assert_array_equal(compute_common_grid(parts), ranges)
    np.testing.assert_array_equal(compute_common_grid(parts[::-1]), ranges)
    merged = merge_aligned(parts)
    assert merged.sizes["range_sample"] == ds.sizes["range_sample"]
    np.testing.assert_array_equal(merged.Sv.values[0], ds.Sv.values)


def test_merge_checks_later_ping_channel_grid_and_missing_calibration():
    ds = _make_two_channel_ds([0, 1], np.full((2, 2, 2), -40.))
    ds = ds.assign_coords(echo_range=(("channel", "ping_time", "range_sample"), [
        [[1., 2.], [1., 2.]], [[1., 2.], [3., 4.]],
    ]))
    with pytest.raises(ValueError, match="共享相同的 echo_range"):
        merge_aligned([ds])
    a = _make_ds([0], [1., 2.])
    b = _make_ds([1], [1., 2.])
    a["sound_absorption"] = ("ping_time", [.01])
    with pytest.raises(ValueError, match="逐 ping 参数缺失"):
        merge_aligned([a, b])


@pytest.mark.real_data
def test_real_raw_split_join_preserves_samples_and_integration():
    from pathlib import Path
    import yaml
    from src.core.acoustic import compute_sv, open_single_file
    from src.core.integration import create_integration_grid, integrate

    root = Path(__file__).parents[1]
    raw = root / "raw_data/20250706SCSK-D20250706-T024009.raw"
    if not raw.exists():
        pytest.skip("本地验证 RAW 不存在")
    config = yaml.safe_load((root / "configs/example.yaml").read_text(encoding="utf-8"))
    ed = open_single_file(raw, config)
    original = compute_sv(ed, config).load()
    del ed
    split = original.sizes["ping_time"] // 2
    first = original.isel(ping_time=slice(None, split)).assign_coords(
        source_file=("ping_time", ["first"] * split))
    second = original.isel(ping_time=slice(split, None)).assign_coords(
        source_file=("ping_time", ["second"] * (original.sizes["ping_time"] - split)))
    merged = merge_aligned([second, first])
    assert merged.Sv.shape == original.Sv.shape
    np.testing.assert_array_equal(merged.Sv.values, original.Sv.values.astype(np.float32))
    assert merged.source_file.values.tolist() == ["first"] * split + ["second"] * (original.sizes["ping_time"] - split)
    grid = create_integration_grid(original, esu_size=50, layer_width=5, surface_depth_m=2, max_depth_m=100)
    before = integrate(original, grid, exclude_below_bottom=False)
    after = integrate(merged, grid, exclude_below_bottom=False)
    np.testing.assert_array_equal(before.n_good, after.n_good)
    np.testing.assert_array_equal(before.n_total, after.n_total)
    np.testing.assert_allclose(before.mean_Sv, after.mean_Sv, atol=1e-5, rtol=0, equal_nan=True)
    np.testing.assert_allclose(before.abc, after.abc, rtol=1e-5, atol=1e-12, equal_nan=True)
    print("真实 RAW 拼回：Sv、样本计数保持一致；ABC 最大绝对差", np.nanmax(np.abs(before.abc - after.abc)))
