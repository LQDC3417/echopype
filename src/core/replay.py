"""按保存的项目快照重算积分；独立输出，不覆盖项目和旧结果。"""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import numpy as np

from src.core.ep_project import EpProject
from src.core.integration import ESUType, create_integration_grid, integrate
from src.core.lines import LineManager
from src.core.processing import prepare_analysis_dataset
from src.core.region import AnalysisRegion


def replay_project(project_path, output_dir, progress=None):
    """重算当前快照定义的流程，不宣称复原未记录的历史操作顺序。"""
    from src.core.acoustic import compute_sv, open_single_file
    from src.core.export import export_to_netcdf
    from src.core.merge import merge_aligned

    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError(f"重算输出目录已存在：{output_dir}")
    project = EpProject.load(Path(project_path))
    if not project.raw_files or any(not project.raw_checksums.get(str(p)) for p in project.raw_files):
        raise ValueError("项目缺少输入校验和，请重新保存项目后重算")
    valid, problems = project.verify_raw_files()
    if not valid:
        raise ValueError(f"RAW 校验失败：{problems}")
    channel_id = project.selected_channel_id or ""

    datasets = []
    for index, path in enumerate(project.raw_files):
        if progress:
            progress(f"重新校准 {index + 1}/{len(project.raw_files)}：{path.name}")
        ed = open_single_file(path, project.config)
        try:
            ds = compute_sv(ed, project.config).load()
            datasets.append(ds.assign_coords(source_file=("ping_time", [str(path.resolve())] * ds.sizes["ping_time"])))
        finally:
            del ed
    ds = datasets[0] if len(datasets) == 1 else merge_aligned(datasets)
    if "channel" in ds["Sv"].dims:
        available = [value.decode("utf-8") if isinstance(value, bytes) else str(value) for value in ds.channel.values]
        if not channel_id:
            if len(available) > 1:
                channel_id = available[0]
                channel_binding = "legacy_first_channel_inferred"
            else:
                channel_id = available[0]
                channel_binding = "single_channel"
        else:
            channel_binding = "saved_channel_id"
        if channel_id not in available:
            raise ValueError(f"项目所选通道 {channel_id} 不存在于输入 RAW：{available}")
        ds = ds.sel(channel=[channel_id])
    else:
        channel_id = channel_id or "single"
        channel_binding = "single_channel"

    state = project.channel_states.get(channel_id, {})
    run_config = deepcopy(project.config)

    def merge_config(target, patch):
        for key, value in patch.items():
            if isinstance(value, dict) and isinstance(target.get(key), dict):
                merge_config(target[key], value)
            else:
                target[key] = deepcopy(value)

    merge_config(run_config, state.get("config", {}))
    line_manager = (
        LineManager.from_records(state["lines"])
        if state.get("lines")
        else project.line_manager
    )
    bounds = state.get("analysis_region")
    analysis_region = AnalysisRegion(*bounds) if bounds else project.analysis_region
    region_enabled = bool(state.get("analysis_region_enabled", project.analysis_region_enabled))
    noise_enabled = state.get("noise_enabled", project.processing_state.get("noise_enabled"))
    if noise_enabled is None:
        raise ValueError("项目未记录自动去噪策略，请在工作台明确选择并保存后重算")
    mask = state.get("noise_mask", project.noise_mask)
    if mask is not None and mask.shape != (ds.sizes["ping_time"], ds.sizes["range_sample"]):
        raise ValueError("保存的噪声 mask 与重建数据维度不一致")
    ds, analysis = prepare_analysis_dataset(
        ds, run_config, noise_enabled, mask, line_manager, analysis_region, region_enabled,
    )
    cfg = run_config.get("integration", {})
    maximum = None
    if "bottom_depth" in analysis:
        bottom = np.asarray(analysis.bottom_depth)
        valid_bottom = bottom[np.isfinite(bottom)]
        if valid_bottom.size:
            maximum = float(valid_bottom.max())
    grid = create_integration_grid(
        analysis, esu_type=ESUType(cfg.get("esu_type", "pings")),
        esu_size=float(cfg.get("esu_size", 500)), layer_width=float(cfg.get("layer_width", 5)),
        surface_depth_m=float(state.get("surface_depth", project.surface_depth)), max_depth_m=maximum,
    )
    if progress:
        progress("按保存的分析区域状态与参数重新积分")
    result = integrate(analysis, grid, min_threshold=float(cfg.get("min_threshold", -70)),
                       max_threshold=float(cfg.get("max_threshold", 0)),
                       ts_default_db=float(cfg.get("ts_default", -30)), exclude_below_bottom=False)
    output_dir.mkdir(parents=True, exist_ok=False)
    export_to_netcdf(ds, output_dir / "Sv.nc")
    result.to_dataframe().to_csv(output_dir / "integration.csv", index=False, encoding="utf-8-sig")
    manifest = project.build_manifest()
    implementation = hashlib.sha256()
    for source in sorted(Path(__file__).parent.glob("*.py")):
        implementation.update(source.name.encode())
        implementation.update(source.read_bytes())
    manifest.update(kind="snapshot_integration_run", project_file=str(Path(project_path).resolve()),
                    selected_channel_id=channel_id, channel_binding=channel_binding,
                    config=run_config,
                    steps=[
                        "calibration",
                        "saved_noise_policy",
                        *(["saved_region"] if region_enabled else []),
                        "integration",
                    ],
                    outputs=["Sv.nc", "integration.csv"],
                    historical_result_equivalence="not_asserted",
                    input_checksums_scope="verified_before_run", environment_scope="current_run",
                    processing_implementation_sha256=implementation.hexdigest())
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_dir
