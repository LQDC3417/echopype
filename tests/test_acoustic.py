"""声学处理模块测试"""

import numpy as np
import pytest
import xarray as xr

from src.core.acoustic import load_raw_files, process_single_file


def test_load_raw_files_not_found(tmp_path):
    """测试 raw 目录不存在"""
    config = {"input": {"raw_dir": str(tmp_path / "nonexistent"), "pattern": "*.raw"}}
    with pytest.raises(FileNotFoundError):
        load_raw_files(config)


def test_load_raw_files_empty(tmp_path):
    """测试 raw 目录为空"""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    config = {"input": {"raw_dir": str(raw_dir), "pattern": "*.raw"}}
    with pytest.raises(FileNotFoundError, match="未找到"):
        load_raw_files(config)


def test_load_raw_files_found(tmp_path):
    """测试找到 raw 文件"""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "test1.raw").touch()
    (raw_dir / "test2.raw").touch()
    config = {"input": {"raw_dir": str(raw_dir), "pattern": "*.raw"}}
    files = load_raw_files(config)
    assert len(files) == 2
