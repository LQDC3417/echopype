"""配置加载测试"""

import pytest
import yaml

from src.core.utils import load_config, validate_config


def test_load_config_valid(config_file):
    """测试正常加载配置"""
    config = load_config(config_file)
    assert config["reservoir"]["name"] == "测试水库"


def test_load_config_not_found():
    """测试配置文件不存在"""
    with pytest.raises(FileNotFoundError):
        load_config("nonexistent.yaml")


def test_validate_config_missing_reservoir():
    """测试缺少 reservoir 字段"""
    config = {"input": {}, "output": {}}
    with pytest.raises(ValueError, match="reservoir"):
        validate_config(config)


def test_validate_config_missing_input():
    """测试缺少 input 字段"""
    config = {"reservoir": {}, "output": {}}
    with pytest.raises(ValueError, match="input"):
        validate_config(config)


def test_validate_config_missing_raw_dir():
    """测试缺少 raw_dir"""
    config = {
        "reservoir": {"name": "test"},
        "input": {"pattern": "*.raw"},
        "processing": {},
        "output": {"dir": "/tmp"},
    }
    with pytest.raises(ValueError, match="raw_dir"):
        validate_config(config)


def test_validate_config_valid(sample_config):
    """测试正常验证"""
    validate_config(sample_config)  # 不应抛出异常
