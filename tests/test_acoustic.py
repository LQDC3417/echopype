"""声学处理模块测试"""

import numpy as np
import pytest
import xarray as xr

from src.core.acoustic import _attach_gps, load_raw_files


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


def test_attach_gps_keeps_pings_outside_coverage_missing():
    """GPS 覆盖范围外的 ping 不应被端点坐标伪造。"""
    ping_time = np.array(
        [
            "2026-01-01T00:00:00",
            "2026-01-01T00:00:01",
            "2026-01-01T00:00:02",
            "2026-01-01T00:00:03",
        ],
        dtype="datetime64[ns]",
    )
    platform = xr.Dataset(
        {
            "latitude": ("time1", [10.0, 20.0]),
            "longitude": ("time1", [100.0, 110.0]),
        },
        coords={"time1": ping_time[1:-1]},
    )

    result = _attach_gps(xr.Dataset(coords={"ping_time": ping_time}), {"Platform": platform})

    assert np.isnan(result["latitude"].values[0])
    assert np.isnan(result["longitude"].values[0])
    assert np.isnan(result["latitude"].values[-1])
    assert np.isnan(result["longitude"].values[-1])
    assert result["latitude"].values[1:-1].tolist() == [10.0, 20.0]
