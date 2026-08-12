"""回声积分模块单元测试"""

import tempfile
from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from src.core.integration import (
    ESUType,
    IntegrationGrid,
    IntegrationResult,
    create_integration_grid,
    integrate,
    integrate_by_grid_cells,
    integration_statistics_summary,
)


@pytest.fixture
def mock_ds_Sv():
    """创建模拟的 Sv 数据集"""
    np.random.seed(42)
    n_pings = 500
    n_samples = 300

    depth_2d = np.tile(np.linspace(0, 30, n_samples), (n_pings, 1))
    Sv = np.random.uniform(-70, -20, (n_pings, n_samples))

    return xr.Dataset({
        'Sv': xr.DataArray(Sv, dims=['ping_time', 'range_sample']),
        'depth': xr.DataArray(depth_2d, dims=['ping_time', 'range_sample']),
        'echo_range': xr.DataArray(depth_2d, dims=['ping_time', 'range_sample']),
    }, coords={
        'ping_time': np.arange(n_pings),
        'range_sample': np.arange(n_samples),
    })


class TestIntegrationResult:
    """IntegrationResult 类测试"""

    def test_creation(self):
        """测试创建 IntegrationResult"""
        result = IntegrationResult(
            mean_Sv=np.array([[1.0, 2.0], [3.0, 4.0]]),
            nasc=np.array([[10.0, 20.0], [30.0, 40.0]]),
            min_Sv=np.array([[-5.0, -4.0], [-3.0, -2.0]]),
            max_Sv=np.array([[5.0, 6.0], [7.0, 8.0]]),
            n_good=np.array([[100, 200], [300, 400]]),
            n_excluded=np.array([[10, 20], [30, 40]]),
            n_total=np.array([[110, 220], [330, 440]]),
            ping_start=np.array([0, 250]),
            ping_end=np.array([250, 500]),
            depth_start=np.array([0.0, 15.0]),
            depth_end=np.array([15.0, 30.0]),
        )

        assert result.n_intervals == 2
        assert result.n_layers == 2

    def test_to_dataframe(self):
        """测试转换为 DataFrame"""
        result = IntegrationResult(
            mean_Sv=np.array([[1.0, 2.0], [3.0, 4.0]]),
            nasc=np.array([[10.0, 20.0], [30.0, 40.0]]),
            min_Sv=np.array([[-5.0, -4.0], [-3.0, -2.0]]),
            max_Sv=np.array([[5.0, 6.0], [7.0, 8.0]]),
            n_good=np.array([[100, 200], [300, 400]]),
            n_excluded=np.array([[10, 20], [30, 40]]),
            n_total=np.array([[110, 220], [330, 440]]),
            ping_start=np.array([0, 250]),
            ping_end=np.array([250, 500]),
            depth_start=np.array([0.0, 15.0]),
            depth_end=np.array([15.0, 30.0]),
        )

        df = result.to_dataframe()
        assert df.shape == (4, 13)
        assert 'interval' in df.columns
        assert 'layer' in df.columns
        assert 'mean_Sv' in df.columns
        assert 'nasc' in df.columns


class TestCreateIntegrationGrid:
    """create_integration_grid 函数测试"""

    def test_pings_esu(self, mock_ds_Sv):
        """测试按 ping 数创建网格"""
        grid = create_integration_grid(mock_ds_Sv, esu_type=ESUType.PINGS, esu_size=100, layer_width=5.0)

        assert isinstance(grid, IntegrationGrid)
        assert grid.n_intervals == 5
        assert grid.n_layers == 6
        assert len(grid.ping_start) == 5
        assert len(grid.depth_start) == 6

    def test_seconds_esu(self, mock_ds_Sv):
        """测试按时间创建网格"""
        grid = create_integration_grid(mock_ds_Sv, esu_type=ESUType.SECONDS, esu_size=100, layer_width=10.0)

        assert isinstance(grid, IntegrationGrid)
        assert grid.n_intervals > 0
        assert grid.n_layers > 0

    def test_custom_depth_range(self, mock_ds_Sv):
        """测试自定义深度范围"""
        grid = create_integration_grid(
            mock_ds_Sv,
            esu_type=ESUType.PINGS,
            esu_size=200,
            layer_width=5.0,
            surface_depth_m=5.0,
            max_depth_m=25.0,
        )

        assert grid.depth_start[0] >= 5.0
        assert grid.depth_end[-1] <= 25.0


class TestIntegrate:
    """integrate 函数测试"""

    def test_basic_integration(self, mock_ds_Sv):
        """测试基本积分"""
        grid = create_integration_grid(mock_ds_Sv, esu_type=ESUType.PINGS, esu_size=100, layer_width=10.0)
        result = integrate(mock_ds_Sv, grid)

        assert isinstance(result, IntegrationResult)
        assert result.n_intervals == grid.n_intervals
        assert result.n_layers == grid.n_layers
        assert np.any(np.isfinite(result.mean_Sv))
        assert np.any(np.isfinite(result.nasc))

    def test_with_threshold(self, mock_ds_Sv):
        """测试带阈值的积分"""
        grid = create_integration_grid(mock_ds_Sv, esu_type=ESUType.PINGS, esu_size=100, layer_width=10.0)
        result = integrate(mock_ds_Sv, grid, min_threshold=-60, max_threshold=-10)

        # 应该有一些样本被排除
        assert np.any(result.n_excluded > 0)

    def test_with_bottom(self, mock_ds_Sv):
        """测试带底部的积分"""
        grid = create_integration_grid(mock_ds_Sv, esu_type=ESUType.PINGS, esu_size=100, layer_width=10.0)
        bottom_depth = np.full(500, 25.0)  # 底部在 25m

        result = integrate(mock_ds_Sv, grid, exclude_below_bottom=True, bottom_depth_m=bottom_depth)

        # 底部以下应该被排除
        assert np.any(result.n_excluded > 0)


class TestIntegrateByGridCells:
    """integrate_by_grid_cells 函数测试"""

    def test_with_grid_cells(self, mock_ds_Sv):
        """测试按网格单元列表积分"""
        grid_cells = [
            {"cell_id": 0, "ping_start": 0, "ping_end": 100, "depth_lo": 0.0, "depth_hi": 10.0},
            {"cell_id": 1, "ping_start": 0, "ping_end": 100, "depth_lo": 10.0, "depth_hi": 20.0},
            {"cell_id": 2, "ping_start": 100, "ping_end": 200, "depth_lo": 0.0, "depth_hi": 10.0},
            {"cell_id": 3, "ping_start": 100, "ping_end": 200, "depth_lo": 10.0, "depth_hi": 20.0},
        ]

        result = integrate_by_grid_cells(mock_ds_Sv, grid_cells)

        assert isinstance(result, IntegrationResult)
        assert result.n_intervals == 2
        assert result.n_layers == 2


class TestIntegrationStatisticsSummary:
    """integration_statistics_summary 函数测试"""

    def test_summary(self, mock_ds_Sv):
        """测试统计摘要"""
        grid = create_integration_grid(mock_ds_Sv, esu_type=ESUType.PINGS, esu_size=100, layer_width=10.0)
        result = integrate(mock_ds_Sv, grid)

        summary = integration_statistics_summary(result)

        assert 'n_intervals' in summary
        assert 'n_layers' in summary
        assert 'total_good_samples' in summary
        assert 'coverage_ratio' in summary
        assert summary['n_intervals'] == grid.n_intervals
        assert summary['n_layers'] == grid.n_layers


# 保留原有集成测试（需要真实数据）
@pytest.mark.skipif(
    not Path("D:/data/test/raw").exists(),
    reason="测试数据目录不存在"
)
def test_full_pipeline():
    """完整流水线测试（需要真实数据）"""
    from src.core.utils import validate_config

    config = {
        "reservoir": {"name": "集成测试", "region": "测试"},
        "input": {"raw_dir": "D:/data/test/raw", "pattern": "*.raw"},
        "processing": {
            "sonar_model": "EK80",
            "frequencies": [38000],
            "waveform_mode": "CW",
            "encode_mode": "power",
            "noise_removal": {"ping_num": 5, "range_sample_num": 10},
            "bottom_detection": {"method": "basic", "threshold": -50.0},
        },
        "school_detection": {
            "method": "echoview",
            "thr": -60.0,
            "mincan": [2.0, 5.0],
            "maxlink": [2.0, 10.0],
            "minsho": [2.0, 10.0],
        },
        "density": {"ts_default": -30.0},
        "output": {"dir": tempfile.mkdtemp(), "formats": ["csv"]},
    }

    validate_config(config)

    from src.core.acoustic import process_all_files
    ds_Sv = process_all_files(config)
    assert ds_Sv is not None
    assert "Sv" in ds_Sv

    from src.core.school import detect_schools, schools_to_dataframe
    mask = detect_schools(ds_Sv, config)
    schools_df = schools_to_dataframe(mask, ds_Sv)

    from src.core.density import estimate_density
    density_df = estimate_density(schools_df, ds_Sv, config)
    assert "density_ind_ha" in density_df.columns


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
