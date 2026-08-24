"""E2E 测试：按 PRD 验证全部功能模块

使用真实 raw 数据验证：
- FR-01~FR-02: 文件加载 + Sv 校准
- FR-03: 噪声去除
- FR-04: 底部检测
- FR-05: 鱼群检测
- FR-07: 网格分析（回声积分，含 ABC/密度列）
- FR-08: 质量检查
- FR-09: 数据导出
- FR-10~FR-13: GUI 导入验证
"""

import numpy as np
import pandas as pd
import pytest

from src.core.acoustic import open_single_file, process_single_file
from src.core.utils import load_config, get_sv_array, squeeze_sv, sv_to_linear

RAW_FILE = "D:/Administrator/Desktop/echopype/raw_data/20250706SCSK-D20250706-T024009.raw"
CONFIG_PATH = "D:/Administrator/Desktop/echopype/configs/example.yaml"


@pytest.fixture(scope="module")
def config():
    return load_config(CONFIG_PATH)


@pytest.fixture(scope="module")
def echodata(config):
    from pathlib import Path
    return open_single_file(Path(RAW_FILE), config)


@pytest.fixture(scope="module")
def ds_Sv(echodata, config):
    return process_single_file(echodata, config)


# ═══════════════════════════════════════════════════════
# FR-01/02: 文件加载 + Sv 校准
# ═══════════════════════════════════════════════════════

class TestFR01_FileLoading:
    def test_echodata_not_none(self, echodata):
        assert echodata is not None

    def test_echodata_has_beam(self, echodata):
        assert echodata.beam is not None

    def test_load_config(self, config):
        assert "processing" in config
        assert "sonar_model" in config["processing"]

    def test_sv_computed(self, ds_Sv):
        assert "Sv" in ds_Sv
        sv = get_sv_array(ds_Sv)
        assert sv.ndim == 2
        assert sv.shape[0] > 0
        assert sv.shape[1] > 0

    def test_sv_data_valid(self, ds_Sv):
        sv = get_sv_array(ds_Sv)
        nan_ratio = np.isnan(sv).sum() / sv.size
        assert nan_ratio < 0.95


# ═══════════════════════════════════════════════════════
# FR-03: 噪声去除（process_single_file 内含）
# ═══════════════════════════════════════════════════════

class TestFR03_NoiseRemoval:
    def test_sv_corrected_exists(self, ds_Sv):
        assert "Sv_corrected" in ds_Sv

    def test_original_sv_preserved(self, ds_Sv):
        sv = get_sv_array(ds_Sv)
        assert sv.shape[0] > 0

    def test_corrected_differ_from_original(self, ds_Sv):
        sv = get_sv_array(ds_Sv)
        sv_corr = ds_Sv["Sv_corrected"].values
        if sv_corr.ndim == 3:
            sv_corr = sv_corr[0]
        # 去噪后至少部分值不同
        assert not np.array_equal(sv, sv_corr)


# ═══════════════════════════════════════════════════════
# FR-04: 底部检测（process_single_file 内含）
# ═══════════════════════════════════════════════════════

class TestFR04_BottomDetection:
    def test_bottom_depth_exists(self, ds_Sv):
        assert "bottom_depth" in ds_Sv

    def test_bottom_has_values(self, ds_Sv):
        bottom = ds_Sv["bottom_depth"].values
        assert bottom is not None
        valid = bottom[np.isfinite(bottom)]
        assert len(valid) > 0

    def test_bottom_in_range(self, ds_Sv):
        """底线深度（米）允许小负值（表线偏移）"""
        bottom = ds_Sv["bottom_depth"].values
        valid = bottom[np.isfinite(bottom)]
        if len(valid) > 0:
            assert np.all(valid >= -1.0), f"底线异常负值: {valid.min():.2f}"


# ═══════════════════════════════════════════════════════
# FR-05: 鱼群检测
# ═══════════════════════════════════════════════════════

class TestFR05_SchoolDetection:
    def test_detect_schools_returns_mask(self, ds_Sv):
        import xarray as xr
        from src.core.school import detect_schools
        mask = detect_schools(ds_Sv, {"thr": -55.0, "mincan": [3.0, 10.0], "maxlink": [3.0, 15.0], "minsho": [3.0, 15.0]})
        assert isinstance(mask, xr.DataArray)


# ═══════════════════════════════════════════════════════
# FR-07: 网格分析
# ═══════════════════════════════════════════════════════

class TestFR07_Integration:
    def test_create_integration_grid_pings(self, ds_Sv):
        from src.core.integration import create_integration_grid, ESUType
        grid = create_integration_grid(ds_Sv, esu_type=ESUType.PINGS, esu_size=100, layer_width=2.0, surface_depth_m=2.0)
        assert grid.n_intervals > 0
        assert grid.n_layers > 0
        assert len(grid.ping_start) > 0
        assert len(grid.depth_start) > 0

    def test_integrate_abc_density(self, ds_Sv):
        from src.core.integration import create_integration_grid, integrate, ESUType
        grid = create_integration_grid(ds_Sv, esu_type=ESUType.PINGS, esu_size=100, layer_width=2.0, surface_depth_m=2.0)
        result = integrate(ds_Sv, grid, ts_default_db=-30.0)
        df = result.to_dataframe()
        assert isinstance(df, pd.DataFrame)
        assert "abc" in df.columns
        assert "density_ind_ha" in df.columns

    def test_integration_distance_method(self, ds_Sv):
        from src.core.integration import create_integration_grid, ESUType
        grid = create_integration_grid(ds_Sv, esu_type=ESUType.DISTANCE, esu_size=100, layer_width=5.0, surface_depth_m=2.0)
        assert grid.n_intervals > 0


# ═══════════════════════════════════════════════════════
# FR-08: 质量检查
# ═══════════════════════════════════════════════════════

class TestFR08_QualityCheck:
    def test_check_sv_quality(self, ds_Sv):
        from src.core.quality import check_sv_quality
        result = check_sv_quality(ds_Sv)
        assert "valid" in result
        assert "sv_range" in result
        assert "nan_ratio" in result
        assert "warnings" in result

    def test_check_bottom_line(self, ds_Sv):
        from src.core.quality import check_bottom_line
        bottom = ds_Sv["bottom_depth"].values
        n_samples = ds_Sv.sizes.get("range_sample", 1000)
        result = check_bottom_line(bottom, n_samples)
        assert "valid" in result
        assert "warnings" in result

    def test_quality_report(self, ds_Sv):
        from src.core.quality import print_quality_report
        print_quality_report(ds_Sv)


# ═══════════════════════════════════════════════════════
# FR-09: 数据导出
# ═══════════════════════════════════════════════════════

class TestFR09_DataExport:
    def test_export_all(self, ds_Sv, tmp_path):
        from src.core.export import export_all
        paths = export_all(ds_Sv, None, None, tmp_path, ["csv"])
        assert len(paths) > 0
        for p in paths:
            assert p.exists()

    def test_export_csv_encoding(self, ds_Sv, tmp_path):
        from src.core.export import export_sv_to_csv
        p = export_sv_to_csv(ds_Sv, tmp_path / "sv.csv")
        assert p.exists()
        with open(p, "rb") as f:
            header = f.read(3)
        assert header == b"\xef\xbb\xbf"


# ═══════════════════════════════════════════════════════
# FR-10~FR-13: GUI 导入验证
# ═══════════════════════════════════════════════════════

class TestFR10_GUI:
    def test_import_all_workers(self):
        from src.gui.workers import (
            LoadFileWorker, ComputeSvWorker, NoiseRemovalWorker,
            DetectSeafloorWorker, DetectSchoolsWorker,
            IntegrationWorker, BatchProcessWorker, QualityCheckWorker,
            MultifreqAnalysisWorker,
        )
        assert all(w is not None for w in [
            LoadFileWorker, ComputeSvWorker, NoiseRemovalWorker,
            DetectSeafloorWorker, DetectSchoolsWorker,
            IntegrationWorker, BatchProcessWorker, QualityCheckWorker,
            MultifreqAnalysisWorker,
        ])

    def test_import_main_window(self):
        from src.gui.main_window import MainWindow
        assert MainWindow is not None

    def test_import_renderer(self):
        from src.viz.opengl_renderer import EchogramRenderer
        assert EchogramRenderer is not None

    def test_renderer_grid_methods(self):
        from src.viz.opengl_renderer import EchogramRenderer
        assert hasattr(EchogramRenderer, "set_grid_data")
        assert hasattr(EchogramRenderer, "clear_grid_overlay")
        assert hasattr(EchogramRenderer, "_draw_grid_overlay")

    def test_import_property_panel(self):
        from src.gui.property_panel import PropertyPanel
        assert hasattr(PropertyPanel, "quality_check_clicked")
        assert hasattr(PropertyPanel, "multifreq_clicked")


# ═══════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════

class TestUtils:
    def test_squeeze_sv_3d(self):
        arr = np.random.rand(3, 100, 50).astype(np.float32)
        result = squeeze_sv(arr)
        assert result.shape == (100, 50)

    def test_squeeze_sv_2d(self):
        arr = np.random.rand(100, 50).astype(np.float32)
        result = squeeze_sv(arr)
        assert result.shape == (100, 50)

    def test_sv_to_linear(self):
        assert abs(sv_to_linear(0.0) - 1.0) < 1e-6
        assert abs(sv_to_linear(-10.0) - 0.1) < 1e-6

    def test_get_memory_usage(self):
        from src.core.utils import get_memory_usage
        mem = get_memory_usage()
        assert "rss_mb" in mem
        assert mem["rss_mb"] >= 0
