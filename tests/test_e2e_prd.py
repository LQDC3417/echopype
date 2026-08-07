"""E2E 测试：按 PRD 验证全部功能模块

使用真实 raw 数据验证：
- FR-01~FR-02: 文件加载 + Sv 校准
- FR-03: 噪声去除
- FR-04: 底部检测
- FR-05: 鱼群检测
- FR-06: 密度估算
- FR-07: 网格分析
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
# FR-06: 密度估算
# ═══════════════════════════════════════════════════════

class TestFR06_DensityEstimation:
    def test_density_empty_schools(self, ds_Sv):
        from src.core.density import estimate_density
        result = estimate_density(pd.DataFrame(), ds_Sv, {"ts_default": -30.0})
        assert isinstance(result, pd.DataFrame)


# ═══════════════════════════════════════════════════════
# FR-07: 网格分析
# ═══════════════════════════════════════════════════════

class TestFR07_GridAnalysis:
    def test_create_grid(self, ds_Sv):
        from src.core.grid import create_grid
        cells = create_grid(ds_Sv, surface_depth_m=2.0, vertical_interval_m=2.0, horizontal_interval=100)
        assert isinstance(cells, list)
        assert len(cells) > 0
        assert "ping_start" in cells[0]
        assert "depth_lo" in cells[0]

    def test_compute_grid_density(self, ds_Sv):
        from src.core.grid import create_grid, compute_grid_density
        cells = create_grid(ds_Sv, surface_depth_m=2.0, vertical_interval_m=2.0, horizontal_interval=100)
        result = compute_grid_density(ds_Sv, cells, {"density": {"ts_default": -30.0}})
        assert isinstance(result, pd.DataFrame)
        assert "mean_sv" in result.columns

    def test_grid_ping_method(self, ds_Sv):
        from src.core.grid import create_grid
        cells = create_grid(ds_Sv, surface_depth_m=2.0, vertical_interval_m=5.0, horizontal_interval=50, method="ping")
        assert len(cells) > 0

    def test_grid_distance_method(self, ds_Sv):
        from src.core.grid import create_grid
        cells = create_grid(ds_Sv, surface_depth_m=2.0, vertical_interval_m=5.0, horizontal_interval=500, method="distance")
        assert len(cells) > 0


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
            DetectSeafloorWorker, DetectSchoolsWorker, ComputeDensityWorker,
            GridWorker, BatchProcessWorker, QualityCheckWorker,
            MultifreqAnalysisWorker,
        )
        assert all(w is not None for w in [
            LoadFileWorker, ComputeSvWorker, NoiseRemovalWorker,
            DetectSeafloorWorker, DetectSchoolsWorker, ComputeDensityWorker,
            GridWorker, BatchProcessWorker, QualityCheckWorker,
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
