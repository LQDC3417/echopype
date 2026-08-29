"""测试配置"""


import pytest
import yaml

SCHOOL_TEST_MAX_PINGS = 64
SCHOOL_TEST_MAX_SAMPLES = 4096
SCHOOL_TEST_MAX_SECONDS = 30.0


def subset_for_school_detection(ds_sv):
    """Return a fixed-size real-data slice for the fish-school acceptance test."""
    return ds_sv.isel(
        ping_time=slice(0, SCHOOL_TEST_MAX_PINGS),
        range_sample=slice(0, SCHOOL_TEST_MAX_SAMPLES),
    )


def pytest_addoption(parser):
    group = parser.getgroup("real-data")
    group.addoption("--run-real-data", action="store_true", default=False)


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-real-data"):
        return

    skip_real_data = pytest.mark.skip(
        reason="requires local raw data; rerun with --run-real-data"
    )
    for item in items:
        if item.get_closest_marker("real_data"):
            item.add_marker(skip_real_data)


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
        "output": {"dir": "D:/data/test/outputs", "formats": ["csv", "png"]},
    }


@pytest.fixture
def config_file(sample_config, tmp_path):
    """创建临时配置文件"""
    config_path = tmp_path / "test_config.yaml"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(sample_config, f, allow_unicode=True)
    return str(config_path)
