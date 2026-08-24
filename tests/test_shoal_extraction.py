"""高级鱼群提取模块测试"""

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from src.core.shoal_extraction import (
    ShoalGroup,
    Segment,
    ShoalExtractionResult,
    extract_shoals_advanced,
    shoals_to_dataframe,
    extract_shoals,
)
from src.core.sed import aggregate_targets_to_grid


@pytest.fixture
def mock_ds_Sv_with_shoals():
    """创建带鱼群的模拟数据"""
    np.random.seed(42)
    n_pings, n_samples = 200, 300
    depth = np.tile(np.linspace(0, 30, n_samples), (n_pings, 1))
    Sv = np.random.uniform(-70, -40, (n_pings, n_samples))

    # 模拟鱼群（在 10-15m 深度，50-100 ping 范围）
    Sv[50:100, 100:150] = np.random.uniform(-50, -30, (50, 50))

    return xr.Dataset({
        'Sv': xr.DataArray(Sv, dims=['ping_time', 'range_sample']),
        'depth': xr.DataArray(depth, dims=['ping_time', 'range_sample']),
    }, coords={
        'ping_time': np.arange(n_pings),
        'range_sample': np.arange(n_samples),
    })


class TestSegment:
    """Segment 数据类测试"""

    def test_creation(self):
        """测试创建 Segment"""
        seg = Segment(depth_min=10.0, depth_max=15.0, ping_idx=50)
        assert seg.depth_min == 10.0
        assert seg.depth_max == 15.0
        assert seg.ping_idx == 50
        assert seg.label == -1


class TestShoalGroup:
    """ShoalGroup 数据类测试"""

    def test_properties(self):
        """测试属性计算"""
        segments = [
            Segment(10.0, 15.0, 50, 0),
            Segment(10.5, 15.5, 51, 0),
            Segment(11.0, 16.0, 52, 0),
        ]
        shoal = ShoalGroup(id=1, segments=segments)

        assert shoal.ping_start == 50
        assert shoal.ping_end == 52
        assert shoal.depth_min == 10.0
        assert shoal.depth_max == 16.0
        assert shoal.n_pings == 3
        assert shoal.height == 6.0
        assert shoal.length_pings == 3


class TestExtractShoalsAdvanced:
    """extract_shoals_advanced 函数测试"""

    def test_basic_extraction(self, mock_ds_Sv_with_shoals):
        """测试基本鱼群提取"""
        config = {
            'school_detection': {
                'method': 'advanced',
                'min_threshold': -55,
                'max_depth_distance': 1.0,
                'min_shoal_pings': 3,
            }
        }

        result = extract_shoals_advanced(mock_ds_Sv_with_shoals, config)

        assert isinstance(result, ShoalExtractionResult)
        assert len(result.shoals) > 0
        assert result.mask.shape == (200, 300)

    def test_with_bottom(self, mock_ds_Sv_with_shoals):
        """测试带底部的鱼群提取"""
        config = {
            'school_detection': {
                'method': 'advanced',
                'min_threshold': -55,
                'max_depth_distance': 1.0,
                'min_shoal_pings': 3,
            }
        }
        bottom_depth = np.full(200, 20.0)

        result = extract_shoals_advanced(
            mock_ds_Sv_with_shoals, config, bottom_depth_m=bottom_depth
        )

        assert isinstance(result, ShoalExtractionResult)
        # 底部以下应该被排除
        depth = np.linspace(0, 30, 300)
        bottom_mask = depth >= 20.0
        assert not np.any(result.mask[:, bottom_mask])

    def test_threshold_filtering(self, mock_ds_Sv_with_shoals):
        """测试阈值过滤"""
        config = {
            'school_detection': {
                'method': 'advanced',
                'min_threshold': -35,  # 高阈值
                'max_depth_distance': 1.0,
                'min_shoal_pings': 3,
            }
        }

        result = extract_shoals_advanced(mock_ds_Sv_with_shoals, config)

        # 高阈值应该检测到更少的鱼群
        assert isinstance(result, ShoalExtractionResult)


class TestShoalsToDataFrame:
    """shoals_to_dataframe 函数测试"""

    def test_conversion(self, mock_ds_Sv_with_shoals):
        """测试转换为 DataFrame"""
        config = {
            'school_detection': {
                'method': 'advanced',
                'min_threshold': -55,
                'max_depth_distance': 1.0,
                'min_shoal_pings': 3,
            }
        }

        result = extract_shoals_advanced(mock_ds_Sv_with_shoals, config)
        df = shoals_to_dataframe(result, mock_ds_Sv_with_shoals)

        assert 'shoal_id' in df.columns
        assert 'ping_start' in df.columns
        assert 'ping_end' in df.columns
        assert 'depth_min' in df.columns
        assert 'depth_max' in df.columns
        assert 'mean_sv' in df.columns
        assert 'area' in df.columns


class TestExtractShoals:
    """extract_shoals 统一接口测试"""

    def test_advanced_method(self, mock_ds_Sv_with_shoals):
        """测试 advanced 方法"""
        config = {
            'school_detection': {
                'method': 'advanced',
                'min_threshold': -55,
                'max_depth_distance': 1.0,
                'min_shoal_pings': 3,
            }
        }

        mask, df = extract_shoals(mock_ds_Sv_with_shoals, config)

        assert mask.shape == (200, 300)
        assert 'shoal_id' in df.columns


if __name__ == '__main__':
    pytest.main([__file__, '-v'])


# ── aggregate_targets_to_grid ─────────────────────────────


class TestAggregateTargetsToGrid:
    """SED 网格聚合测试"""

    @pytest.fixture
    def mock_grid_config(self):
        return {"integration": {"esu_type": "pings", "esu_size": 10, "layer_width": 5.0}}

    @pytest.fixture
    def mock_grid_ds(self):
        """带 echo_range 的简单 ds（50 pings × 20 samples）"""
        n_pings, n_samples = 50, 20
        echo_range = np.broadcast_to(
            np.arange(0.5, n_samples * 0.5 + 0.5, 0.5)[:n_samples], (n_pings, n_samples)
        ).copy()
        sv = np.random.uniform(-80, -30, (n_pings, n_samples)).astype(float)
        return xr.Dataset({
            "Sv": xr.DataArray(sv, dims=["ping_time", "range_sample"]),
            "echo_range": xr.DataArray(echo_range, dims=["ping_time", "range_sample"]),
            "ping_time": xr.DataArray(np.arange(n_pings), dims=["ping_time"]),
            "range_sample": xr.DataArray(np.arange(n_samples), dims=["range_sample"]),
        })

    def test_empty_targets(self, mock_grid_ds, mock_grid_config):
        """空 targets → 全 NaN 网格"""
        targets = pd.DataFrame(columns=["ping_idx", "range_m", "ts_db"])
        grid_df = aggregate_targets_to_grid(targets, mock_grid_ds, mock_grid_config)
        assert len(grid_df) > 0
        assert (grid_df["n_targets"] == 0).all()
        assert grid_df["ts_mean"].isna().all()

    def test_single_target(self, mock_grid_ds, mock_grid_config):
        """单个目标归入正确网格"""
        targets = pd.DataFrame({"ping_idx": [5], "range_m": [3.0], "ts_db": [-40.0]})
        grid_df = aggregate_targets_to_grid(targets, mock_grid_ds, mock_grid_config)
        with_targets = grid_df[grid_df["n_targets"] > 0]
        assert len(with_targets) == 1
        assert with_targets.iloc[0]["n_targets"] == 1
        assert with_targets.iloc[0]["ts_mean"] == pytest.approx(-40.0, abs=0.1)

    def test_multiple_targets_same_cell(self, mock_grid_ds, mock_grid_config):
        """同网格多个目标 → TS 线性域均值"""
        targets = pd.DataFrame({
            "ping_idx": [5, 6, 7],
            "range_m": [3.0, 3.5, 4.0],
            "ts_db": [-40.0, -40.0, -40.0],
        })
        grid_df = aggregate_targets_to_grid(targets, mock_grid_ds, mock_grid_config)
        with_targets = grid_df[grid_df["n_targets"] > 0]
        assert len(with_targets) == 1
        assert with_targets.iloc[0]["n_targets"] == 3
        # 同值均值 = 本身
        assert with_targets.iloc[0]["ts_mean"] == pytest.approx(-40.0, abs=0.1)

    def test_output_columns(self, mock_grid_ds, mock_grid_config):
        """输出列名完整"""
        targets = pd.DataFrame({"ping_idx": [5], "range_m": [3.0], "ts_db": [-40.0]})
        grid_df = aggregate_targets_to_grid(targets, mock_grid_ds, mock_grid_config)
        expected_cols = {
            "interval", "layer", "ping_start", "ping_end",
            "depth_start", "depth_end", "n_targets", "ts_mean",
            "ts_std", "ts_min", "ts_max", "center_lat", "center_lon",
        }
        assert expected_cols.issubset(set(grid_df.columns))
