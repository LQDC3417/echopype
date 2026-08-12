"""噪声去除模块测试"""

import numpy as np
import pytest
import xarray as xr

from src.core.noise import (
    estimate_noise_de_robertis,
    estimate_noise_passive,
    apply_noise_reduction,
    noise_statistics,
    NoiseEstimate,
)


@pytest.fixture
def mock_ds_Sv():
    """创建模拟数据"""
    np.random.seed(42)
    n_pings, n_samples = 200, 300
    depth = np.linspace(0, 30, n_samples)
    Sv = np.random.uniform(-80, -40, (n_pings, n_samples))

    return xr.Dataset({
        'Sv': xr.DataArray(Sv, dims=['ping_time', 'range_sample']),
        'depth': xr.DataArray(np.tile(depth, (n_pings, 1)), dims=['ping_time', 'range_sample']),
    }, coords={
        'ping_time': np.arange(n_pings),
        'range_sample': np.arange(n_samples),
    })


class TestEstimateNoiseDeRobertis:
    """De Robertis 噪声估算测试"""

    def test_basic(self, mock_ds_Sv):
        """测试基本功能"""
        Sv = mock_ds_Sv['Sv'].values
        depth = np.linspace(0, 30, 300)

        noise_2d, noise_per_ping = estimate_noise_de_robertis(
            Sv, depth, ping_num=20, range_sample_num=5,
        )

        assert noise_2d.shape == (200, 300)
        assert noise_per_ping.shape == (200,)

    def test_parameters(self, mock_ds_Sv):
        """测试不同参数"""
        Sv = mock_ds_Sv['Sv'].values
        depth = np.linspace(0, 30, 300)

        noise_2d, noise_per_ping = estimate_noise_de_robertis(
            Sv, depth, ping_num=40, range_sample_num=10, noise_max=-130.0,
        )

        assert noise_2d.shape == (200, 300)


class TestEstimateNoisePassive:
    """被动噪声估算测试"""

    def test_with_passive_indices(self, mock_ds_Sv):
        """测试指定被动 ping"""
        Sv = mock_ds_Sv['Sv'].values
        passive_indices = np.arange(0, 50)
        depth = np.linspace(0, 30, 300)

        noise_2d, noise_per_ping = estimate_noise_passive(
            Sv, passive_indices, depth=depth,
        )

        assert noise_2d.shape == (200, 300)
        assert noise_per_ping.shape == (200,)

    def test_without_passive_indices(self, mock_ds_Sv):
        """测试无指定被动 ping"""
        Sv = mock_ds_Sv['Sv'].values

        noise_2d, noise_per_ping = estimate_noise_passive(Sv)

        assert noise_2d.shape == (200, 300)


class TestApplyNoiseReduction:
    """完整噪声去除流程测试"""

    def test_de_robertis_mode(self, mock_ds_Sv):
        """测试 De Robertis 模式"""
        config = {
            'noise_removal': {
                'mode': 'de_robertis',
                'ping_num': 20,
                'range_sample_num': 5,
                'snr_threshold': 3.0,
            }
        }

        result = apply_noise_reduction(mock_ds_Sv, config)

        assert 'Sv_corrected' in result
        assert 'noise_Sv' in result
        assert 'noise_per_ping' in result
        assert 'SNR' in result

    def test_passive_mode(self, mock_ds_Sv):
        """测试被动模式"""
        config = {
            'noise_removal': {
                'mode': 'passive',
                'passive_ping_indices': list(range(50)),
                'snr_threshold': 3.0,
            }
        }

        result = apply_noise_reduction(mock_ds_Sv, config)

        assert 'Sv_corrected' in result
        assert 'noise_Sv' in result


class TestNoiseStatistics:
    """噪声统计测试"""

    def test_with_noise_data(self, mock_ds_Sv):
        """测试有噪声数据"""
        config = {'noise_removal': {'mode': 'de_robertis', 'ping_num': 20, 'range_sample_num': 5}}
        result = apply_noise_reduction(mock_ds_Sv, config)

        stats = noise_statistics(result)

        assert stats['status'] == 'ok'
        assert 'noise_mean' in stats
        assert 'noise_std' in stats
        assert 'snr_mean' in stats

    def test_without_noise_data(self, mock_ds_Sv):
        """测试无噪声数据"""
        stats = noise_statistics(mock_ds_Sv)
        assert stats['status'] == 'no_noise_data'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
