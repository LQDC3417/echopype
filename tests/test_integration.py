"""回声积分模块单元测试（合并网格分析后：ABC + 密度 + pings/distance EDSU）"""

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
    integration_statistics_summary,
)


@pytest.fixture
def mock_ds_Sv():
    """创建模拟的 Sv 数据集（含 GPS 坐标）"""
    np.random.seed(42)
    n_pings = 500
    n_samples = 300

    depth_2d = np.tile(np.linspace(0, 30, n_samples), (n_pings, 1))
    Sv = np.random.uniform(-70, -20, (n_pings, n_samples))

    # 模拟 GPS：每 ping 前进 ~0.5 m
    latitude = 24.83 + np.arange(n_pings) * 4.5e-6
    longitude = 117.82 + np.arange(n_pings) * 4.5e-6

    return xr.Dataset({
        'Sv': xr.DataArray(Sv, dims=['ping_time', 'range_sample']),
        'depth': xr.DataArray(depth_2d, dims=['ping_time', 'range_sample']),
        'echo_range': xr.DataArray(depth_2d, dims=['ping_time', 'range_sample']),
    }, coords={
        'ping_time': np.arange(n_pings),
        'range_sample': np.arange(n_samples),
        'latitude': ('ping_time', latitude),
        'longitude': ('ping_time', longitude),
    })


def _make_result():
    return IntegrationResult(
        mean_Sv=np.array([[1.0, 2.0], [3.0, 4.0]]),
        abc=np.array([[10.0, 20.0], [30.0, 40.0]]),
        min_Sv=np.array([[-5.0, -4.0], [-3.0, -2.0]]),
        max_Sv=np.array([[5.0, 6.0], [7.0, 8.0]]),
        density_ind_ha=np.array([[100.0, 200.0], [300.0, 400.0]]),
        n_good=np.array([[100, 200], [300, 400]]),
        n_excluded=np.array([[10, 20], [30, 40]]),
        n_total=np.array([[110, 220], [330, 440]]),
        ping_start=np.array([0, 250]),
        ping_end=np.array([250, 500]),
        depth_start=np.array([0.0, 15.0]),
        depth_end=np.array([15.0, 30.0]),
    )


class TestIntegrationResult:
    """IntegrationResult 类测试"""

    def test_creation(self):
        result = _make_result()
        assert result.n_intervals == 2
        assert result.n_layers == 2

    def test_to_dataframe(self):
        df = _make_result().to_dataframe()
        assert df.shape == (4, 12)
        assert 'interval' in df.columns
        assert 'abc' in df.columns
        assert 'density_ind_ha' in df.columns
        assert 'mean_Sv' in df.columns
        assert 'nasc' not in df.columns


class TestCreateIntegrationGrid:
    """create_integration_grid 函数测试"""

    def test_pings_esu(self, mock_ds_Sv):
        grid = create_integration_grid(mock_ds_Sv, esu_type=ESUType.PINGS, esu_size=100, layer_width=5.0)
        assert isinstance(grid, IntegrationGrid)
        assert grid.n_intervals == 5
        assert grid.n_layers == 6
        assert len(grid.ping_start) == 5
        assert len(grid.depth_start) == 6

    def test_distance_esu(self, mock_ds_Sv):
        """测试按 GPS 距离创建网格"""
        grid = create_integration_grid(mock_ds_Sv, esu_type=ESUType.DISTANCE, esu_size=50, layer_width=10.0)
        assert isinstance(grid, IntegrationGrid)
        assert grid.n_intervals > 0
        assert grid.n_layers > 0

    def test_distance_no_gps_raises(self):
        """无 GPS 时 distance 分段应报错"""
        ds = mock_ds_Sv.__wrapped__() if hasattr(mock_ds_Sv, "__wrapped__") else None
        # 构造无 GPS 的 mock（去掉坐标）
        np.random.seed(42)
        n_pings, n_samples = 500, 300
        depth_2d = np.tile(np.linspace(0, 30, n_samples), (n_pings, 1))
        ds_nogps = xr.Dataset({
            'Sv': xr.DataArray(np.random.uniform(-70, -20, (n_pings, n_samples)),
                               dims=['ping_time', 'range_sample']),
            'echo_range': xr.DataArray(depth_2d, dims=['ping_time', 'range_sample']),
        }, coords={'ping_time': np.arange(n_pings), 'range_sample': np.arange(n_samples)})
        with pytest.raises(ValueError):
            create_integration_grid(ds_nogps, esu_type=ESUType.DISTANCE, esu_size=50)

    def test_custom_depth_range(self, mock_ds_Sv):
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
        grid = create_integration_grid(mock_ds_Sv, esu_type=ESUType.PINGS, esu_size=100, layer_width=10.0)
        result = integrate(mock_ds_Sv, grid)
        assert isinstance(result, IntegrationResult)
        assert result.n_intervals == grid.n_intervals
        assert result.n_layers == grid.n_layers
        assert np.any(np.isfinite(result.mean_Sv))
        assert np.any(np.isfinite(result.abc))
        assert np.any(np.isfinite(result.density_ind_ha))

    def test_with_threshold(self, mock_ds_Sv):
        grid = create_integration_grid(mock_ds_Sv, esu_type=ESUType.PINGS, esu_size=100, layer_width=10.0)
        result = integrate(mock_ds_Sv, grid, min_threshold=-60, max_threshold=-10)
        assert np.any(result.n_excluded > 0)

    def test_with_bottom(self, mock_ds_Sv):
        grid = create_integration_grid(mock_ds_Sv, esu_type=ESUType.PINGS, esu_size=100, layer_width=10.0)
        bottom_depth = np.full(500, 25.0)
        result = integrate(mock_ds_Sv, grid, exclude_below_bottom=True, bottom_depth_m=bottom_depth)
        assert np.any(result.n_excluded > 0)

    def test_ts_default_affects_density(self, mock_ds_Sv):
        grid = create_integration_grid(mock_ds_Sv, esu_type=ESUType.PINGS, esu_size=100, layer_width=10.0)
        r1 = integrate(mock_ds_Sv, grid, ts_default_db=-30.0)
        r2 = integrate(mock_ds_Sv, grid, ts_default_db=-20.0)
        # TS 越大 → σ_bs 越大 → 密度越小
        assert np.nanmean(r2.density_ind_ha) < np.nanmean(r1.density_ind_ha)


class TestIntegrationStatisticsSummary:
    """integration_statistics_summary 函数测试"""

    def test_summary(self, mock_ds_Sv):
        grid = create_integration_grid(mock_ds_Sv, esu_type=ESUType.PINGS, esu_size=100, layer_width=10.0)
        result = integrate(mock_ds_Sv, grid)
        summary = integration_statistics_summary(result)
        assert 'n_intervals' in summary
        assert 'n_layers' in summary
        assert 'total_good_samples' in summary
        assert 'coverage_ratio' in summary
        assert 'abc_global' in summary
        assert 'density_global' in summary
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
