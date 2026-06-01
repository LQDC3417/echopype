"""鱼群识别模块测试"""

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from src.core.school import detect_schools, schools_to_dataframe


def _make_mock_sv(n_pings=50, n_samples=100):
    """创建模拟 Sv 数据"""
    np.random.seed(42)
    Sv = np.random.uniform(-80, -40, (n_pings, n_samples))
    # 在中间区域插入鱼群信号
    Sv[10:20, 30:50] = np.random.uniform(-55, -45, (10, 20))
    Sv[35:45, 60:80] = np.random.uniform(-55, -45, (10, 20))

    return xr.Dataset(
        {
            "Sv": xr.DataArray(
                Sv,
                dims=["ping_time", "range_sample"],
                coords={
                    "ping_time": np.arange(n_pings),
                    "range_sample": np.arange(n_samples),
                },
            ),
        }
    )


def test_detect_schools_returns_mask():
    """测试鱼群检测返回布尔 mask"""
    ds = _make_mock_sv()
    config = {
        "school_detection": {
            "method": "echoview",
            "thr": -60.0,
            "mincan": [2.0, 5.0],
            "maxlink": [2.0, 10.0],
            "minsho": [2.0, 10.0],
        }
    }
    mask = detect_schools(ds, config)
    assert mask.dtype == bool
    assert mask.dims == ("ping_time", "range_sample")


def test_schools_to_dataframe():
    """测试鱼群 mask 转 DataFrame"""
    mask = xr.DataArray(
        np.array([[True, True, False], [True, True, False], [False, False, False]]),
        dims=["ping_time", "range_sample"],
        coords={"ping_time": [0, 1, 2], "range_sample": [0, 1, 2]},
    )
    ds = xr.Dataset({
        "Sv": xr.DataArray(
            np.array([[-50, -51, -80], [-52, -53, -80], [-80, -80, -80]]),
            dims=["ping_time", "range_sample"],
            coords={"ping_time": [0, 1, 2], "range_sample": [0, 1, 2]},
        ),
    })
    df = schools_to_dataframe(mask, ds)
    assert isinstance(df, pd.DataFrame)
    assert "school_id" in df.columns
    assert "mean_sv" in df.columns
    assert len(df) > 0
