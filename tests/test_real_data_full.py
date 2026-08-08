"""真实数据全模块测试

逐模块测试所有功能，记录遇到的问题。
使用真实 EK80 raw 文件: raw_data/20250706SCSK-D20250706-T024009.raw
"""

import sys
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

RAW_FILE = Path("D:/Administrator/Desktop/echopype/raw_data/20250706SCSK-D20250706-T024009.raw")
CONFIG_PATH = Path("D:/Administrator/Desktop/echopype/configs/example.yaml")

# 问题收集器
issues = []

def report(module, status, msg=""):
    icon = "✅" if status == "OK" else "❌" if status == "FAIL" else "⚠️"
    print(f"  {icon} {module}: {msg}")
    if status == "FAIL":
        issues.append((module, msg))

def run_all_tests():
    print("=" * 60)
    print("真实数据全模块测试")
    print("=" * 60)

    # ═══════════════════════════════════════════════════════
    # 1. 配置加载
    # ═══════════════════════════════════════════════════════
    print("\n[1] 配置加载")
    try:
        from src.core.utils import load_config, validate_config
        config = load_config(str(CONFIG_PATH))
        try:
            validate_config(config)
            report("load_config", "OK", "加载成功，验证通过")
        except ValueError as e:
            report("load_config", "WARN", f"验证问题: {e}")
    except Exception as e:
        report("load_config", "FAIL", str(e))
        return

    # ═══════════════════════════════════════════════════════
    # 2. 文件加载 (FR-01)
    # ═══════════════════════════════════════════════════════
    print("\n[2] 文件加载 (FR-01)")
    try:
        from src.core.acoustic import open_single_file
        echodata = open_single_file(RAW_FILE, config)
        report("open_single_file", "OK", f"类型: {type(echodata).__name__}")
    except Exception as e:
        report("open_single_file", "FAIL", str(e))
        return

    # ═══════════════════════════════════════════════════════
    # 3. Sv 校准 + 噪声去除 + 底部检测 (FR-02~04)
    # ═══════════════════════════════════════════════════════
    print("\n[3] Sv 校准 + 噪声去除 + 底部检测 (FR-02~04)")
    try:
        from src.core.acoustic import process_single_file
        ds_Sv = process_single_file(echodata, config)
        sv_vars = [v for v in ds_Sv.data_vars if "Sv" in v]
        report("process_single_file", "OK", f"变量: {sv_vars}, 尺寸: {dict(ds_Sv.dims)}")

        # 检查 Sv_corrected
        if "Sv_corrected" in ds_Sv:
            sv_orig = ds_Sv["Sv"].values
            sv_corr = ds_Sv["Sv_corrected"].values
            if sv_orig.shape == sv_corr.shape:
                report("Sv_corrected", "OK", f"形状一致: {sv_orig.shape}")
            else:
                report("Sv_corrected", "FAIL", f"形状不一致: {sv_orig.shape} vs {sv_corr.shape}")
        else:
            report("Sv_corrected", "WARN", "未生成 Sv_corrected")

        # 检查 bottom_depth
        if "bottom_depth" in ds_Sv:
            bottom = ds_Sv["bottom_depth"].values
            valid = bottom[np.isfinite(bottom)]
            report("bottom_depth", "OK", f"有效值: {len(valid)}/{len(bottom)}")
        else:
            report("bottom_depth", "FAIL", "bottom_depth 不存在")
    except Exception:
        report("process_single_file", "FAIL", traceback.format_exc())
        return

    # ═══════════════════════════════════════════════════════
    # 4. 质量检查 (FR-08)
    # ═══════════════════════════════════════════════════════
    print("\n[4] 质量检查 (FR-08)")
    try:
        from src.core.quality import check_sv_quality, check_bottom_line
        sv_check = check_sv_quality(ds_Sv)
        report("check_sv_quality", "OK" if sv_check["valid"] else "WARN",
               f"valid={sv_check['valid']}, warnings={sv_check['warnings']}")

        if "bottom_depth" in ds_Sv:
            bl_check = check_bottom_line(ds_Sv["bottom_depth"].values, ds_Sv.sizes.get("range_sample", 0))
            report("check_bottom_line", "OK" if bl_check["valid"] else "WARN",
                   f"valid={bl_check['valid']}, warnings={bl_check['warnings']}")
    except Exception:
        report("quality_check", "FAIL", traceback.format_exc())

    # ═══════════════════════════════════════════════════════
    # 5. 区域裁剪 (分析区域)
    # ═══════════════════════════════════════════════════════
    print("\n[5] 区域裁剪")
    try:
        from src.core.region import crop_sv_by_region, get_surface_sample
        surface_sample = get_surface_sample(ds_Sv, 2.0)
        report("get_surface_sample", "OK", f"surface_sample={surface_sample}")

        # 裁剪：表线到底线
        if "bottom_depth" in ds_Sv:
            bottom = ds_Sv["bottom_depth"].values
            valid_bottom = bottom[np.isfinite(bottom)]
            if len(valid_bottom) > 0:
                # crop_sv_by_region 需要底线数组（每个 ping 的深度），不能传 float
                ds_cropped = crop_sv_by_region(ds_Sv, surface_depth_m=2.0, bottom_depth_m=bottom)
                report("crop_sv_by_region", "OK", f"裁剪后尺寸: {dict(ds_cropped.sizes)}")
            else:
                report("crop_sv_by_region", "WARN", "无有效底线，跳过裁剪")
    except Exception:
        report("region_crop", "FAIL", traceback.format_exc())

    # ═══════════════════════════════════════════════════════
    # 6. 鱼群检测 (FR-05)
    # ═══════════════════════════════════════════════════════
    print("\n[6] 鱼群检测 (FR-05)")
    try:
        from src.core.school import detect_schools
        school_mask = detect_schools(ds_Sv, config.get("school_detection", {}))
        if hasattr(school_mask, 'values'):
            n_schools = int(np.sum(school_mask.values)) if school_mask.dtype == bool else 0
            report("detect_schools", "OK", f"类型: {type(school_mask).__name__}, 鱼群像素: {n_schools}")
        else:
            report("detect_schools", "OK", f"返回类型: {type(school_mask).__name__}")
    except Exception:
        report("detect_schools", "FAIL", traceback.format_exc())

    # ═══════════════════════════════════════════════════════
    # 7. 密度估算 (FR-06)
    # ═══════════════════════════════════════════════════════
    print("\n[7] 密度估算 (FR-06)")
    try:
        from src.core.density import estimate_density
        density_df = estimate_density(pd.DataFrame(), ds_Sv, config.get("density", {}))
        report("estimate_density", "OK", f"结果: {len(density_df)} 行, 列: {list(density_df.columns)[:5]}")
    except Exception:
        report("estimate_density", "FAIL", traceback.format_exc())

    # ═══════════════════════════════════════════════════════
    # 8. 网格分析 (FR-07)
    # ═══════════════════════════════════════════════════════
    print("\n[8] 网格分析 (FR-07)")
    try:
        from src.core.grid import create_grid, compute_grid_density
        cells = create_grid(ds_Sv, surface_depth_m=2.0, vertical_interval_m=2.0, horizontal_interval=100)
        report("create_grid", "OK", f"网格数: {len(cells)}")

        grid_df = compute_grid_density(ds_Sv, cells, config)
        cols = list(grid_df.columns)
        has_lat = "latitude" in cols
        has_lon = "longitude" in cols
        has_abc = "abc" in cols
        has_cell_id = "cell_id" in cols
        report("compute_grid_density", "OK",
               f"cell_id={has_cell_id}, lat={has_lat}, lon={has_lon}, abc={has_abc}, 行数={len(grid_df)}")
    except Exception:
        report("grid_analysis", "FAIL", traceback.format_exc())

    # ═══════════════════════════════════════════════════════
    # 9. 单体目标检测
    # ═══════════════════════════════════════════════════════
    print("\n[9] 单体目标检测")
    try:
        from src.core.single_target import detect_and_compute_ts
        targets = detect_and_compute_ts(ds_Sv, config)
        if not targets.empty:
            report("single_target", "OK",
                   f"目标数: {len(targets)}, 列: {list(targets.columns)[:8]}")
        else:
            report("single_target", "WARN", "未检测到目标")
    except Exception:
        report("single_target", "FAIL", traceback.format_exc())

    # ═══════════════════════════════════════════════════════
    # 10. 多频分析
    # ═══════════════════════════════════════════════════════
    print("\n[10] 多频分析")
    try:
        from src.core.multifreq import get_channel_summary, compare_frequencies, split_transects
        summary = get_channel_summary(ds_Sv)
        report("get_channel_summary", "OK", f"通道数: {len(summary)}")

        channels = list(summary["channel"]) if not summary.empty else []
        if len(channels) >= 2:
            comp = compare_frequencies(ds_Sv, config)
            report("compare_frequencies", "OK", f"对比 {len(comp)} 个通道")
        else:
            report("compare_frequencies", "WARN", f"仅 {len(channels)} 个通道，跳过对比")

        transect_ids = split_transects(ds_Sv)
        n_transects = int(transect_ids.max()) + 1 if len(transect_ids) > 0 else 0
        report("split_transects", "OK", f"分段数: {n_transects}")
    except Exception:
        report("multifreq", "FAIL", traceback.format_exc())

    # ═══════════════════════════════════════════════════════
    # 11. Sv 统计摘要
    # ═══════════════════════════════════════════════════════
    print("\n[11] Sv 统计摘要")
    try:
        from src.core.density import sv_statistics_summary
        stats = sv_statistics_summary(ds_Sv)
        report("sv_statistics_summary", "OK", f"统计行数: {len(stats)}")
    except Exception:
        report("sv_statistics_summary", "FAIL", traceback.format_exc())

    # ═══════════════════════════════════════════════════════
    # 12. 数据导出 (FR-09)
    # ═══════════════════════════════════════════════════════
    print("\n[12] 数据导出 (FR-09)")
    try:
        import tempfile
        from src.core.export import export_all
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = export_all(ds_Sv, None, None, tmpdir, ["csv"])
            report("export_all", "OK", f"导出 {len(paths)} 个文件")
            for p in paths:
                size = p.stat().st_size
                report(f"  {p.name}", "OK", f"{size/1024:.0f} KB")
    except Exception:
        report("export", "FAIL", traceback.format_exc())

    # ═══════════════════════════════════════════════════════
    # 13. GUI 模块导入
    # ═══════════════════════════════════════════════════════
    print("\n[13] GUI 模块导入")
    gui_modules = [
        ("main_window", "from src.gui.main_window import MainWindow"),
        ("workers", "from src.gui.workers import LoadFileWorker, ComputeSvWorker, NoiseRemovalWorker, DetectSeafloorWorker, DetectSchoolsWorker, ComputeDensityWorker, GridWorker, BatchProcessWorker, QualityCheckWorker, MultifreqAnalysisWorker, SingleTargetWorker, SvStatsWorker, TransectSplitWorker"),
        ("property_panel", "from src.gui.property_panel import PropertyPanel"),
        ("opengl_renderer", "from src.viz.opengl_renderer import EchogramRenderer"),
        ("theme", "from src.gui.theme import DARK_THEME"),
    ]
    for name, import_stmt in gui_modules:
        try:
            exec(import_stmt)
            report(name, "OK")
        except Exception as e:
            report(name, "FAIL", str(e))

    # ═══════════════════════════════════════════════════════
    # 14. 内存监控
    # ═══════════════════════════════════════════════════════
    print("\n[14] 内存监控")
    try:
        from src.core.utils import get_memory_usage, optimize_array_dtype
        mem = get_memory_usage()
        report("get_memory_usage", "OK", f"RSS: {mem['rss_mb']:.0f} MB")

        test_arr = np.random.rand(100, 100).astype(np.float64)
        opt_arr = optimize_array_dtype(test_arr)
        report("optimize_array_dtype", "OK", f"{test_arr.dtype} → {opt_arr.dtype}")
    except Exception as e:
        report("memory", "FAIL", str(e))

    # ═══════════════════════════════════════════════════════
    # 汇总
    # ═══════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("测试汇总")
    print("=" * 60)
    if issues:
        print(f"\n发现 {len(issues)} 个问题:")
        for module, msg in issues:
            print(f"  ❌ {module}: {msg[:100]}")
    else:
        print("\n✅ 所有模块测试通过！")

    return issues


if __name__ == "__main__":
    result = run_all_tests()
    sys.exit(1 if result else 0)
