"""单体目标检测模块测试"""

import numpy as np
import pytest
import xarray as xr

from src.core.single_target import (
    detect_single_targets,
    compute_target_ts,
    detect_and_compute_ts,
    get_target_summary,
    _empty_targets_df,
)


@pytest.fixture
def mock_ds_Sv_with_targets():
    """创建带单体目标的模拟数据"""
    np.random.seed(42)
    n_pings, n_samples = 200, 300
    depth = np.tile(np.linspace(0, 30, n_samples), (n_pings, 1))
    Sv = np.random.uniform(-70, -40, (n_pings, n_samples))

    # 模拟单体目标（强回波点）
    for i in range(10):
        ping_idx = np.random.randint(50, 150)
        depth_idx = np.random.randint(100, 200)
        Sv[ping_idx, depth_idx] = -20 + np.random.uniform(-5, 5)

    return xr.Dataset({
        'Sv': xr.DataArray(Sv, dims=['ping_time', 'range_sample']),
        'depth': xr.DataArray(depth, dims=['ping_time', 'range_sample']),
    }, coords={
        'ping_time': np.arange(n_pings),
        'range_sample': np.arange(n_samples),
    })


class TestDetectSingleTargets:
    """detect_single_targets 函数测试"""

    def test_basic_detection(self, mock_ds_Sv_with_targets):
        """测试基本检测"""
        config = {
            'single_target': {
                'sv_threshold_db': -30,
                'min_area': 1,
                'max_area': 10,
            }
        }

        df = detect_single_targets(mock_ds_Sv_with_targets, config)

        assert not df.empty
        assert 'target_id' in df.columns
        assert 'depth_center' in df.columns
        assert 'sv_max' in df.columns
        assert len(df) == 10  # 10 个模拟目标

    def test_threshold_filtering(self, mock_ds_Sv_with_targets):
        """测试阈值过滤"""
        config = {
            'single_target': {
                'sv_threshold_db': -15,  # 高阈值
                'min_area': 1,
                'max_area': 10,
            }
        }

        df = detect_single_targets(mock_ds_Sv_with_targets, config)

        # 高阈值应该检测到更少的目标
        assert len(df) <= 10

    def test_area_filtering(self, mock_ds_Sv_with_targets):
        """测试面积过滤"""
        config = {
            'single_target': {
                'sv_threshold_db': -30,
                'min_area': 5,  # 最小面积 5
                'max_area': 10,
            }
        }

        df = detect_single_targets(mock_ds_Sv_with_targets, config)

        # 面积过滤应该排除单像素目标
        if not df.empty:
            assert all(df['area'] >= 5)

    def test_no_targets(self):
        """测试无目标情况"""
        n_pings, n_samples = 100, 200
        Sv = np.full((n_pings, n_samples), -80.0)  # 全部低值
        depth = np.tile(np.linspace(0, 30, n_samples), (n_pings, 1))

        ds_Sv = xr.Dataset({
            'Sv': xr.DataArray(Sv, dims=['ping_time', 'range_sample']),
            'depth': xr.DataArray(depth, dims=['ping_time', 'range_sample']),
        }, coords={
            'ping_time': np.arange(n_pings),
            'range_sample': np.arange(n_samples),
        })

        config = {'single_target': {'sv_threshold_db': -30, 'min_area': 1, 'max_area': 10}}
        df = detect_single_targets(ds_Sv, config)

        assert df.empty


class TestComputeTargetTs:
    """compute_target_ts 函数测试"""

    def test_ts_computation(self, mock_ds_Sv_with_targets):
        """测试 TS 计算"""
        config = {
            'single_target': {
                'sv_threshold_db': -30,
                'min_area': 1,
                'max_area': 10,
            }
        }

        targets_df = detect_single_targets(mock_ds_Sv_with_targets, config)
        targets_with_ts = compute_target_ts(targets_df, mock_ds_Sv_with_targets)

        assert 'ts_db' in targets_with_ts.columns
        assert len(targets_with_ts) == len(targets_df)

    def test_empty_df(self, mock_ds_Sv_with_targets):
        """测试空 DataFrame"""
        empty_df = _empty_targets_df()
        result = compute_target_ts(empty_df, mock_ds_Sv_with_targets)

        assert result.empty
        assert 'ts_db' in result.columns


class TestDetectAndComputeTs:
    """detect_and_compute_ts 函数测试"""

    def test_one_step(self, mock_ds_Sv_with_targets):
        """测试一步完成检测和 TS 计算"""
        config = {
            'single_target': {
                'sv_threshold_db': -30,
                'min_area': 1,
                'max_area': 10,
            }
        }

        df = detect_and_compute_ts(mock_ds_Sv_with_targets, config)

        assert not df.empty
        assert 'ts_db' in df.columns


class TestGetTargetSummary:
    """get_target_summary 函数测试"""

    def test_summary_with_ts(self, mock_ds_Sv_with_targets):
        """测试带 TS 的统计摘要"""
        config = {
            'single_target': {
                'sv_threshold_db': -30,
                'min_area': 1,
                'max_area': 10,
            }
        }

        df = detect_and_compute_ts(mock_ds_Sv_with_targets, config)
        summary = get_target_summary(df)

        assert 'count' in summary
        assert 'area_mean' in summary
        assert 'depth_mean' in summary
        assert 'ts_mean' in summary
        assert summary['count'] == 10

    def test_summary_empty(self):
        """测试空 DataFrame 的摘要"""
        empty_df = _empty_targets_df()
        summary = get_target_summary(empty_df)

        assert summary['count'] == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
