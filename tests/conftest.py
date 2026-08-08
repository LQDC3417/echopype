"""测试配置"""


import pytest
import yaml


@pytest.fixture
def sample_config():
    """示例配置"""
    return {
        "reservoir": {"name": "测试水库", "region": "福建"},
        "input": {"raw_dir": "D:/data/test/raw", "pattern": "*.raw"},
        "processing": {
            "frequencies": [38000, 70000],
            "waveform_mode": "CW",
            "encode_mode": "power",
            "noise_removal": {
                "ping_num": 5,
                "range_sample_num": 10,
                "SNR_threshold": "3.0dB",
            },
            "bottom_detection": {
                "method": "basic",
                "threshold": -50.0,
                "offset_m": 0.5,
                "bin_skip_from_surface": 200,
            },
        },
        "school_detection": {
            "method": "echoview",
            "thr": -55.0,
            "mincan": [3.0, 10.0],
            "maxlink": [3.0, 15.0],
            "minsho": [3.0, 15.0],
        },
        "density": {"ts_default": -30.0},
        "output": {"dir": "D:/data/test/outputs", "formats": ["csv", "png"]},
    }


@pytest.fixture
def config_file(sample_config, tmp_path):
    """创建临时配置文件"""
    config_path = tmp_path / "test_config.yaml"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(sample_config, f, allow_unicode=True)
    return str(config_path)
