"""项目快照说明；只记录当前状态，不推断历史计算环境。"""

import hashlib
import json
import platform
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import numpy as np


def config_input_fingerprint(config: dict, checksums: dict) -> str:
    """规范化配置和输入校验和，字典插入顺序不影响指纹。"""
    payload = json.dumps(
        {"config": config, "checksums": checksums},
        sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def snapshot_metadata(config: dict, checksums: dict) -> dict:
    """记录保存/导出当下的软件环境，不宣称结果由该环境计算。"""
    versions = {"python": platform.python_version()}
    for package in ("echopype", "numpy", "xarray"):
        try:
            versions[package] = version(package)
        except PackageNotFoundError:
            versions[package] = None
    return {
        "schema_version": "1.0",
        "kind": "project_snapshot",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "versions": versions,
        "config_input_fingerprint": config_input_fingerprint(config, checksums),
        "environment_scope": "snapshot_only_not_historical_computation",
    }


def mask_summary(mask) -> dict | None:
    """记录布尔掩码形状、计数和摘要，掩码数据仍保存在 .ep 内。"""
    if mask is None:
        return None
    values = np.asarray(mask, dtype=bool)
    return {
        "shape": list(values.shape),
        "true_count": int(np.count_nonzero(values)),
        "sha256": hashlib.sha256(values.tobytes(order="C")).hexdigest(),
    }


def execution_metadata(
    config: dict, *, channel_id: str, raw_paths=(), noise_enabled=None,
    manual_mask=None, line_manager=None, analysis_region=None, region_enabled=False,
    surface_depth_m=0.0, max_depth_m=None, integration_settings=None,
) -> dict:
    """记录一次成功计算实际使用的输入、设置和实现版本。"""
    raw_files = []
    for raw_path in raw_paths:
        path = Path(raw_path)
        try:
            before = path.stat()
            digest = hashlib.sha256()
            with path.open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
            after = path.stat()
            raw_files.append({
                "path": str(path),
                "size_bytes": after.st_size,
                "sha256": digest.hexdigest(),
                "stable_during_hash": (
                    before.st_size == after.st_size and before.st_mtime_ns == after.st_mtime_ns
                ),
            })
        except OSError as exc:
            raw_files.append({"path": str(path), "sha256": None, "error": str(exc)})

    line_records = line_manager.to_records() if line_manager is not None else []
    line_payload = json.dumps(
        line_records, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        default=str, allow_nan=True,
    )
    implementation = hashlib.sha256()
    for source_path in (
        Path(__file__).with_name("processing.py"),
        Path(__file__).with_name("integration.py"),
        Path(__file__).with_name("region.py"),
        Path(__file__).parents[1] / "gui" / "workers.py",
    ):
        implementation.update(source_path.name.encode("utf-8"))
        implementation.update(source_path.read_bytes())

    versions = {"python": platform.python_version()}
    for package in ("echopype", "numpy", "xarray"):
        try:
            versions[package] = version(package)
        except PackageNotFoundError:
            versions[package] = None
    return {
        "schema_version": "1.0",
        "kind": "integration_run",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "channel_id": str(channel_id),
        "config": config,
        "effective_settings": {
            "integration": integration_settings or {},
            "noise_enabled": noise_enabled,
            "surface_depth_m": float(surface_depth_m),
            "max_depth_m": max_depth_m,
            "analysis_region_enabled": bool(region_enabled),
            "analysis_region": None if analysis_region is None else {
                "upper_line_id": analysis_region.upper_line_id,
                "lower_line_id": analysis_region.lower_line_id,
            },
            "lines_sha256": hashlib.sha256(line_payload.encode("utf-8")).hexdigest(),
            "line_count": len(line_records),
            "manual_mask": mask_summary(manual_mask),
        },
        "inputs": raw_files,
        "input_checksum_algorithm": "sha256",
        "input_checksum_scope": "raw_file_content_when_result_recorded",
        "versions": versions,
        "implementation_sha256": implementation.hexdigest(),
    }
