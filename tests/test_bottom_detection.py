"""增强底部检测模块测试"""

import numpy as np
import pytest
import xarray as xr

from src.core.bottom_detection import (
    BottomMethod,
    detect_bottom,
    detect_bottom_afsc,
    detect_bottom_basic,
    detect_bottom_enhanced,
    validate_bottom_line,
    _smooth_ping,
    _find_echo_envelope,
)


@pytest.fixture
def mock_ds_Sv():
    """创建模拟的 Sv 数据集（带底部回波）"""
    np.random.seed(42)
    n_pings = 200
    n_samples = 400

    depth_2d = np.tile(np.linspace(0, 40, n_samples), (n_pings, 1))

    # 模拟有底部回波的 Sv 数据（底部约在 25m 处）
    Sv = np.random.uniform(-70, -40, (n_pings, n_samples))
    for i in range(n_pings):
        bottom_idx = 250 + np.random.randint(-5, 5)  # 底部在 250 号样本附近
        Sv[i, bottom_idx:] = -5 + np.random.uniform(-3, 3, n_samples - bottom_idx)

    return xr.Dataset({
        'Sv': xr.DataArray(Sv, dims=['ping_time', 'range_sample']),
        'depth': xr.DataArray(depth_2d, dims=['ping_time', 'range_sample']),
    }, coords={
        'ping_time': np.arange(n_pings),
        'range_sample': np.arange(n_samples),
    })


@pytest.fixture
def mock_bottom():
    """创建模拟的底部深度数组"""
    np.random.seed(42)
    bottom = np.random.uniform(20, 30, 100)
    # 插入异常跳变
    bottom[50] = 80
    bottom[75] = 5
    return bottom


class TestSmoothPing:
    """_smooth_ping 函数测试"""

    def test_smoothing(self):
        """测试平滑效果"""
        ping = np.random.randn(100) * 5 - 50
        smoothed = _smooth_ping(ping, window_len=11)

        assert smoothed.shape == ping.shape
        assert np.std(smoothed) < np.std(ping)

    def test_with_nan(self):
        """测试处理 NaN"""
        ping = np.random.randn(100) * 5 - 50
        ping[50:60] = np.nan
        smoothed = _smooth_ping(ping, window_len=11)

        assert smoothed.shape == ping.shape
        assert np.any(np.isnan(smoothed))

    def test_all_nan(self):
        """测试全 NaN"""
        ping = np.full(100, np.nan)
        smoothed = _smooth_ping(ping, window_len=11)

        assert smoothed.shape == ping.shape
        assert np.all(np.isnan(smoothed))


class TestFindEchoEnvelope:
    """_find_echo_envelope 函数测试"""

    def test_simple_envelope(self):
        """测试简单 echo envelope"""
        ping = np.zeros(100)
        ping[30:50] = np.array([
            10, 20, 30, 40, 50, 45, 40, 35, 30, 25,
            20, 15, 10, 5, 0, -5, -10, -15, -20, -25
        ])

        result = _find_echo_envelope(ping, peak_idx=35, threshold=20, search_min_idx=5)
        assert result is not None
        assert 30 < result < 40

    def test_no_envelope(self):
        """测试无 envelope"""
        ping = np.zeros(100)
        result = _find_echo_envelope(ping, peak_idx=50, threshold=20, search_min_idx=10)
        assert result is None


class TestValidateBottomLine:
    """validate_bottom_line 函数测试"""

    def test_detect_anomalies(self, mock_bottom):
        """测试检测异常跳变"""
        validated, relevance = validate_bottom_line(mock_bottom, validation_window=15, validation_threshold=3.0)

        assert validated.shape == mock_bottom.shape
        assert relevance.shape == mock_bottom.shape
        assert np.sum(relevance == 0) > 0  # 应该检测到异常

    def test_no_anomalies(self):
        """测试无异常情况"""
        bottom = np.linspace(20, 30, 100)  # 平滑的底部
        validated, relevance = validate_bottom_line(bottom, validation_window=15, validation_threshold=3.0)

        assert np.sum(relevance == 0) == 0  # 不应该有异常


class TestDetectBottomEnhanced:
    """detect_bottom_enhanced 函数测试"""

    def test_basic_enhanced(self, mock_ds_Sv):
        """测试增强底部检测"""
        bottom = detect_bottom_enhanced(
            mock_ds_Sv,
            peak_threshold=-25.0,
            discrimination_threshold=-35.0,
        )

        assert bottom.shape == (200,)
        n_valid = np.sum(np.isfinite(bottom))
        assert n_valid > 0
        assert np.nanmin(bottom) > 0
        assert np.nanmax(bottom) < 40

    def test_with_validation(self, mock_ds_Sv):
        """测试带验证的检测"""
        bottom = detect_bottom_enhanced(
            mock_ds_Sv,
            peak_threshold=-25.0,
            discrimination_threshold=-35.0,
            validation_window=10,
            validation_threshold=2.0,
        )

        n_valid = np.sum(np.isfinite(bottom))
        assert n_valid > 0


class TestDetectBottomAfsc:
    """detect_bottom_afsc 函数测试"""

    def test_basic_afsc(self, mock_ds_Sv):
        """测试 AFSC 底部检测"""
        bottom = detect_bottom_afsc(
            mock_ds_Sv,
            search_min=5.0,
            window_len=11,
            backstep=25.0,
        )

        assert bottom.shape == (200,)
        n_valid = np.sum(np.isfinite(bottom))
        assert n_valid > 0

    def test_custom_params(self, mock_ds_Sv):
        """测试自定义参数"""
        bottom = detect_bottom_afsc(
            mock_ds_Sv,
            search_min=10.0,
            window_len=15,
            backstep=30.0,
        )

        n_valid = np.sum(np.isfinite(bottom))
        assert n_valid > 0


class TestDetectBottom:
    """detect_bottom 统一接口测试"""

    def test_enhanced_method(self, mock_ds_Sv):
        """测试 enhanced 方法"""
        bottom = detect_bottom(mock_ds_Sv, method='enhanced',
                              peak_threshold=-25.0, discrimination_threshold=-35.0)
        assert bottom.shape == (200,)

    def test_afsc_method(self, mock_ds_Sv):
        """测试 afsc 方法"""
        bottom = detect_bottom(mock_ds_Sv, method='afsc',
                              search_min=5.0, backstep=25.0)
        assert bottom.shape == (200,)

    def test_invalid_method(self, mock_ds_Sv):
        """测试无效方法"""
        with pytest.raises(ValueError, match="不支持的底部检测方法"):
            detect_bottom(mock_ds_Sv, method='invalid')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
