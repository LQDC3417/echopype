"""集成测试：使用 echopype 示例数据"""

import pytest
import tempfile
from pathlib import Path

from src.core.utils import load_config, validate_config


@pytest.mark.skipif(
    not Path("D:/data/test/raw").exists(),
    reason="测试数据目录不存在"
)
def test_full_pipeline():
    """完整流水线测试（需要真实数据）"""
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

    # 验证配置
    validate_config(config)

    # 声学处理
    from src.core.acoustic import process_all_files
    ds_Sv = process_all_files(config)
    assert ds_Sv is not None
    assert "Sv" in ds_Sv

    # 鱼群识别
    from src.core.school import detect_schools, schools_to_dataframe
    mask = detect_schools(ds_Sv, config)
    schools_df = schools_to_dataframe(mask, ds_Sv)

    # 密度估算
    from src.core.density import estimate_density
    density_df = estimate_density(schools_df, ds_Sv, config)
    assert "density_ind_ha" in density_df.columns
