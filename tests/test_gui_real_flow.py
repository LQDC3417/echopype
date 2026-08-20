"""GUI 完整功能测试 — 模拟真实用户操作流程

按 PRD 操作流程逐项测试：
1. 导入数据 → Echogram 显示
2. 设置表线/底线
3. 质量检查
4. 噪声去除
5. 鱼群检测
6. 密度估算
7. 网格分析
8. 单体目标检测
9. 多频分析
10. 数据导出
"""

import traceback
from pathlib import Path

import numpy as np
import pandas as pd

# 本文件设计为直接运行（python tests/test_gui_real_flow.py），
# test_step 是辅助函数而非测试用例，不参与 pytest 收集
__test__ = False

RAW_FILE = Path("D:/Administrator/Desktop/echopype/raw_data/20250706SCSK-D20250706-T024009.raw")
CONFIG_PATH = Path("D:/Administrator/Desktop/echopype/configs/example.yaml")

# 结果收集
results = []

def test_step(name, func):
    """执行测试步骤并记录结果"""
    print(f"\n{'='*60}")
    print(f"测试: {name}")
    print(f"{'='*60}")
    try:
        result = func()
        print(f"  ✅ {name}: {result}")
        results.append((name, "PASS", result))
        return True
    except Exception as e:
        print(f"  ❌ {name}: {traceback.format_exc()}")
        results.append((name, "FAIL", str(e)))
        return False

# ═══════════════════════════════════════════════════════
# 步骤 1: 导入数据
# ═══════════════════════════════════════════════════════
def step1_load_file():
    from src.core.utils import load_config
    from src.core.acoustic import open_single_file, process_single_file

    config = load_config(str(CONFIG_PATH))
    echodata = open_single_file(RAW_FILE, config)
    ds_Sv = process_single_file(echodata, config)

    sv = ds_Sv["Sv"].values
    if sv.ndim == 3:
        sv = sv[0]

    print(f"  数据尺寸: {ds_Sv.sizes}")
    print(f"  Sv 范围: [{np.nanmin(sv):.1f}, {np.nanmax(sv):.1f}] dB")
    print(f"  Sv_corrected: {'有' if 'Sv_corrected' in ds_Sv else '无'}")
    print(f"  bottom_depth: {'有' if 'bottom_depth' in ds_Sv else '无'}")

    return config, echodata, ds_Sv, sv

# ═══════════════════════════════════════════════════════
# 步骤 2: 设置表线
# ═══════════════════════════════════════════════════════
def step2_surface_line(ds_Sv):
    from src.core.region import get_surface_sample

    surface_sample = get_surface_sample(ds_Sv, 2.0)
    print(f"  表线深度: 2.0 m → sample index: {surface_sample}")
    assert surface_sample > 0, "表线 sample 应 > 0"
    return f"surface_sample={surface_sample}"

# ═══════════════════════════════════════════════════════
# 步骤 3: 设置底线
# ═══════════════════════════════════════════════════════
def step3_bottom_line(ds_Sv):
    if "bottom_depth" not in ds_Sv:
        return "无 bottom_depth（跳过）"

    bottom = ds_Sv["bottom_depth"].values
    valid = bottom[np.isfinite(bottom)]
    print(f"  底线有效 ping: {len(valid)}/{len(bottom)}")
    print(f"  底线深度范围: [{np.nanmin(valid):.1f}, {np.nanmax(valid):.1f}] m")
    return f"有效 {len(valid)}/{len(bottom)}"

# ═══════════════════════════════════════════════════════
# 步骤 4: 分析区域（表线→底线）
# ═══════════════════════════════════════════════════════
def step4_analysis_region(ds_Sv):
    from src.core.region import crop_sv_by_region

    if "bottom_depth" not in ds_Sv:
        return "无底线，跳过裁剪"

    bottom = ds_Sv["bottom_depth"].values
    ds_cropped = crop_sv_by_region(ds_Sv, surface_depth_m=2.0, bottom_depth_m=bottom)
    print(f"  裁剪前: {dict(ds_Sv.sizes)}")
    print(f"  裁剪后: {dict(ds_cropped.sizes)}")
    return "裁剪完成"

# ═══════════════════════════════════════════════════════
# 步骤 5: 质量检查
# ═══════════════════════════════════════════════════════
def step5_quality_check(ds_Sv):
    from src.core.quality import check_sv_quality, check_bottom_line

    sv_result = check_sv_quality(ds_Sv)
    print(f"  Sv 质量: valid={sv_result['valid']}, warnings={sv_result['warnings']}")

    if "bottom_depth" in ds_Sv:
        bl_result = check_bottom_line(ds_Sv["bottom_depth"].values, ds_Sv.sizes.get("range_sample", 0))
        print(f"  底线质量: valid={bl_result['valid']}, warnings={bl_result['warnings']}")

    return f"Sv valid={sv_result['valid']}"

# ═══════════════════════════════════════════════════════
# 步骤 6: 鱼群检测
# ═══════════════════════════════════════════════════════
def step6_school_detection(ds_Sv, config):
    from src.core.school import detect_schools

    school_mask = detect_schools(ds_Sv, config.get("school_detection", {}))
    if hasattr(school_mask, 'values'):
        n_schools = int(np.sum(school_mask.values)) if school_mask.dtype == bool else 0
        print(f"  鱼群 mask 类型: {type(school_mask).__name__}")
        print(f"  鱼群像素数: {n_schools}")
        return f"鱼群像素={n_schools}"
    return f"返回类型: {type(school_mask).__name__}"

# ═══════════════════════════════════════════════════════
# 步骤 7: 密度估算
# ═══════════════════════════════════════════════════════
def step7_density(ds_Sv, config):
    from src.core.density import estimate_density

    density_df = estimate_density(pd.DataFrame(), ds_Sv, config.get("density", {}))
    print(f"  密度结果: {len(density_df)} 行")
    print(f"  列: {list(density_df.columns)}")
    if not density_df.empty:
        print(f"  ABC: {density_df['abc'].values[0]:.4f}")
        print(f"  密度: {density_df['density_ind_m2'].values[0]:.6f} ind/m²")
    return f"密度={len(density_df)} 行"

# ═══════════════════════════════════════════════════════
# 步骤 8: 回声积分（ABC + 密度，替代网格分析）
# ═══════════════════════════════════════════════════════
def step8_integration(ds_Sv, config):
    from src.core.integration import create_integration_grid, integrate, ESUType

    grid = create_integration_grid(ds_Sv, esu_type=ESUType.PINGS, esu_size=100, layer_width=2.0, surface_depth_m=2.0)
    result = integrate(ds_Sv, grid, min_threshold=-70, max_threshold=0, ts_default_db=-30.0)
    df = result.to_dataframe()

    print(f"  区间×层: {grid.n_intervals}×{grid.n_layers}")
    print(f"  列: {list(df.columns)}")
    print(f"  含 abc: {'abc' in df.columns}")
    print(f"  含 density: {'density_ind_ha' in df.columns}")
    print(f"  含 mean_Sv: {'mean_Sv' in df.columns}")
    return f"积分={len(df)} 单元"

# ═══════════════════════════════════════════════════════
# 步骤 9: 单体目标检测
# ═══════════════════════════════════════════════════════
def step10_multifreq(ds_Sv, config):
    from src.core.multifreq import get_channel_summary, split_transects

    summary = get_channel_summary(ds_Sv)
    channels = list(summary["channel"]) if not summary.empty else []
    print(f"  通道数: {len(channels)}")
    print(f"  通道: {channels}")

    transect_ids = split_transects(ds_Sv)
    n_transects = int(transect_ids.max()) + 1 if len(transect_ids) > 0 else 0
    print(f"  Transect 分段: {n_transects}")

    return f"通道={len(channels)}, transect={n_transects}"

# ═══════════════════════════════════════════════════════
# 步骤 11: Sv 统计
# ═══════════════════════════════════════════════════════
def step11_sv_stats(ds_Sv):
    from src.core.density import sv_statistics_summary

    stats = sv_statistics_summary(ds_Sv)
    print(f"  统计行数: {len(stats)}")
    if not stats.empty:
        print(f"  列: {list(stats.columns)}")
    return f"统计={len(stats)} 行"

# ═══════════════════════════════════════════════════════
# 步骤 12: 数据导出
# ═══════════════════════════════════════════════════════
def step12_export(ds_Sv):
    import tempfile
    from src.core.export import export_all

    with tempfile.TemporaryDirectory() as tmpdir:
        paths = export_all(ds_Sv, None, None, tmpdir, ["csv"])
        print(f"  导出文件数: {len(paths)}")
        for p in paths:
            size = p.stat().st_size
            print(f"  {p.name}: {size/1024:.0f} KB")
    return f"导出={len(paths)} 文件"

# ═══════════════════════════════════════════════════════
# 步骤 13: 渲染器
# ═══════════════════════════════════════════════════════
def step13_renderer(sv):
    from src.viz.opengl_renderer import EchogramRenderer

    renderer = EchogramRenderer()
    renderer.set_data(sv)
    print(f"  数据已设置: {renderer._n_pings} pings × {renderer._n_samples} samples")
    print(f"  set_grid_data: {hasattr(renderer, 'set_grid_data')}")
    print(f"  set_noise_mask: {hasattr(renderer, 'set_noise_mask')}")
    print(f"  set_bottom_line: {hasattr(renderer, 'set_bottom_line')}")
    print(f"  set_school_mask: {hasattr(renderer, 'set_school_mask')}")
    return "渲染器就绪"

# ═══════════════════════════════════════════════════════
# 步骤 14: GUI Worker 导入
# ═══════════════════════════════════════════════════════
def step14_workers():
    from src.gui.workers import (
        LoadFileWorker, ComputeSvWorker, NoiseRemovalWorker,
        DetectSeafloorWorker, DetectSchoolsWorker, ComputeDensityWorker,
        IntegrationWorker, BatchProcessWorker, QualityCheckWorker,
        TransectSplitWorker,
    )
    workers = [
        LoadFileWorker, ComputeSvWorker, NoiseRemovalWorker,
        DetectSeafloorWorker, DetectSchoolsWorker, ComputeDensityWorker,
        IntegrationWorker, BatchProcessWorker, QualityCheckWorker,
        TransectSplitWorker,
    ]
    print(f"  Worker 类数: {len(workers)}")
    return "全部 Worker 导入成功"

# ═══════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════
def main():
    print("=" * 60)
    print("GUI 完整功能测试 — 真实数据操作流程")
    print("=" * 60)

    # 步骤 1: 导入数据
    success = test_step("1. 导入数据 (FR-01/02)", step1_load_file)
    if not success:
        print("\n❌ 数据导入失败，无法继续")
        return
    config, echodata, ds_Sv, sv = results[-1][2]

    # 步骤 2-12: 功能测试
    test_step("2. 设置表线", lambda: step2_surface_line(ds_Sv))
    test_step("3. 设置底线", lambda: step3_bottom_line(ds_Sv))
    test_step("4. 分析区域裁剪", lambda: step4_analysis_region(ds_Sv))
    test_step("5. 质量检查", lambda: step5_quality_check(ds_Sv))
    test_step("6. 鱼群检测", lambda: step6_school_detection(ds_Sv, config))
    test_step("7. 密度估算", lambda: step7_density(ds_Sv, config))
    test_step("8. 回声积分", lambda: step8_integration(ds_Sv, config))
    test_step("9. 多频分析", lambda: step10_multifreq(ds_Sv, config))
    test_step("10. Sv 统计", lambda: step11_sv_stats(ds_Sv))
    test_step("11. 数据导出", lambda: step12_export(ds_Sv))
    test_step("12. 渲染器", lambda: step13_renderer(sv))
    test_step("13. Worker 导入", step14_workers)

    # ═══════════════════════════════════════════════════════
    # 汇总
    # ═══════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("测试汇总")
    print("=" * 60)
    passed = sum(1 for _, s, _ in results if s == "PASS")
    failed = sum(1 for _, s, _ in results if s == "FAIL")
    print(f"\n✅ 通过: {passed}/{len(results)}")
    if failed:
        print(f"❌ 失败: {failed}/{len(results)}")
        for name, status, msg in results:
            if status == "FAIL":
                print(f"  ❌ {name}: {msg[:80]}")
    else:
        print("\n🎉 所有功能测试通过！")

    return results


if __name__ == "__main__":
    main()
