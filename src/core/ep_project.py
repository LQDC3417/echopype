"""EP 项目文件管理 — 读写 .ep (HDF5) 项目文件

.ep 文件（扩展名 .ep）是一个 HDF5 容器，包含：
- metadata: 原始 .raw 文件路径列表 + 校验和 + 处理配置 + 时间戳
- analysis:  表线深度、底部检测线、鱼群 mask
- results:   鱼群统计表、积分结果、SED 结果（JSON 序列化的 DataFrame）

设计参照 Echoview 的 .ev 文件：不存储大型 Sv 数据，
打开时重新从 .raw 文件计算；只存轻量元数据和分析结果。
"""

import hashlib
import io
import json
import os
from datetime import datetime
from pathlib import Path

import h5py
import numpy as np
import pandas as pd

from src.core.lines import LineManager
from src.core.region import AnalysisRegion
from src.core.provenance import mask_summary, snapshot_metadata
from src.core.project_tables import read_frame, write_frame

PROJECT_VERSION = "1.3"


def _md5(path: Path) -> str:
    """计算文件 MD5 校验和（分块读取，内存友好）"""
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class EpProject:
    """EP 项目文件（HDF5）"""

    def __init__(self, raw_files: list[Path] | None = None, config: dict | None = None):
        self.raw_files: list[Path] = [Path(p) for p in (raw_files or [])]
        self.raw_checksums: dict[str, str] = {}
        self.config: dict = config or {}
        self.created_at: str = _now()
        self.modified_at: str = _now()
        self.provenance: dict = {}
        self.processing_state: dict = {}
        self.selected_channel_id: str = ""
        self.channel_states: dict[str, dict] = {}

        # 分析结果
        self.surface_depth: float = 2.0
        self.bottom_line: np.ndarray | None = None
        self.line_manager = LineManager()
        self.analysis_region: AnalysisRegion | None = None
        self.analysis_region_enabled = False
        self.display_settings: dict = {"colormap": "jet", "vmin": -90.0, "vmax": -30.0}
        self.noise_mask: np.ndarray | None = None
        self.school_mask: np.ndarray | None = None

        # 统计结果
        self.schools_df: pd.DataFrame | None = None
        self.integration_df: pd.DataFrame | None = None
        # SED 的逐目标结果和网格汇总用途不同，必须分别保存。
        self.sed_df: pd.DataFrame | None = None
        self.sed_grid_df: pd.DataFrame | None = None

    # ═══════════════════════════════════════════════════════
    # 保存
    # ═══════════════════════════════════════════════════════

    def save(self, path: Path) -> Path:
        """Atomically save the project, preserving the previous file on failure."""
        path = Path(path)
        if path.suffix.lower() != ".ep":
            path = path.with_suffix(".ep")

        temp_path = path.with_name(f".{path.name}.tmp")
        try:
            provenance = self._save_to_path(temp_path)
            os.replace(temp_path, path)
            self.provenance = provenance
        except Exception:
            if temp_path.exists():
                temp_path.unlink()
            raise
        return path

    def _save_to_path(self, path: Path) -> dict:
        """保存到 .ep 文件（HDF5）"""
        self.modified_at = _now()
        self._sync_line_manager_from_legacy()
        provenance = self.build_manifest()

        with h5py.File(path, "w") as f:
            # metadata
            md = f.create_group("metadata")
            md.create_dataset("raw_files", data=[str(p) for p in self.raw_files])
            md.create_dataset("raw_checksums", data=[self.raw_checksums.get(str(p), "") for p in self.raw_files])
            md.attrs["version"] = PROJECT_VERSION
            md.attrs["created_at"] = self.created_at
            md.attrs["modified_at"] = self.modified_at
            md.create_dataset("config", data=json.dumps(self.config, ensure_ascii=False))
            md.create_dataset("provenance", data=json.dumps(provenance, ensure_ascii=False))
            md.create_dataset("processing_state", data=json.dumps(self.processing_state, ensure_ascii=False))
            md.attrs["selected_channel_id"] = self.selected_channel_id

            # analysis
            an = f.create_group("analysis")
            an.create_dataset("surface_depth", data=float(self.surface_depth))
            if self.bottom_line is not None:
                an.create_dataset("bottom_line", data=np.asarray(self.bottom_line, dtype=np.float32))
            an.create_dataset(
                "lines",
                data=json.dumps(self.line_manager.to_records(), ensure_ascii=False, default=str),
            )
            if self.analysis_region is not None:
                an.create_dataset(
                    "analysis_region",
                    data=json.dumps(
                        {
                            "upper_line_id": self.analysis_region.upper_line_id,
                            "lower_line_id": self.analysis_region.lower_line_id,
                        }
                    ),
                )
            an.create_dataset("display_settings", data=json.dumps(self.display_settings, ensure_ascii=False))
            if self.noise_mask is not None:
                an.create_dataset(
                    "noise_mask",
                    data=np.asarray(self.noise_mask, dtype=bool),
                    compression="gzip",
                )
            if self.school_mask is not None:
                an.create_dataset(
                    "school_mask",
                    data=np.asarray(self.school_mask, dtype=bool),
                    compression="gzip",
                )

            # results
            rs = f.create_group("results")
            for name in ("schools_df", "integration_df", "sed_df", "sed_grid_df"):
                write_frame(rs, name, getattr(self, name))
            channels = f.create_group("channels")
            for index, channel_id in enumerate(sorted(self.channel_states)):
                state = self.channel_states[channel_id]
                group = channels.create_group(f"channel_{index:04d}")
                group.attrs["channel_id"] = channel_id
                group.attrs["config"] = json.dumps(state.get("config", {}), ensure_ascii=False)
                group.attrs["surface_depth"] = float(state.get("surface_depth", self.surface_depth))
                group.attrs["bottom_manually_edited"] = bool(state.get("bottom_manually_edited", False))
                group.attrs["analysis_region_enabled"] = bool(state.get("analysis_region_enabled", False))
                group.attrs["noise_enabled"] = json.dumps(state.get("noise_enabled"))
                group.attrs["noise_applied"] = bool(state.get("noise_applied", False))
                group.attrs["stale_results"] = json.dumps(state.get("stale_results", []))
                group.attrs["incomplete_results"] = json.dumps(state.get("incomplete_results", []))
                group.attrs["result_provenance"] = json.dumps(
                    state.get("result_provenance", {}), ensure_ascii=False
                )
                group.attrs["analysis_region"] = json.dumps(state.get("analysis_region"), ensure_ascii=False)
                group.create_dataset("lines", data=json.dumps(state.get("lines", []), ensure_ascii=False, default=str))
                for key in ("bottom_line", "noise_mask", "school_mask"):
                    value = state.get(key)
                    if value is not None:
                        group.create_dataset(key, data=np.asarray(value), compression="gzip")
                state_results = group.create_group("results")
                for key in ("schools_df", "integration_df", "sed_df", "sed_grid_df"):
                    write_frame(state_results, key, state.get(key))
                for stack_name in ("undo_stack", "redo_stack"):
                    stack_group = group.create_group(stack_name)
                    for item_index, item in enumerate(state.get(stack_name, ())):
                        action, value = item
                        item_group = stack_group.create_group(str(item_index))
                        item_group.attrs["action"] = str(action)
                        if value is not None:
                            item_group.create_dataset("data", data=np.asarray(value), compression="gzip")
            an.create_dataset("analysis_region_enabled", data=bool(self.analysis_region_enabled))
        return provenance


    # ═══════════════════════════════════════════════════════
    # 加载
    # ═══════════════════════════════════════════════════════

    @classmethod
    def load(cls, path: Path) -> "EpProject":
        """从 .ep 文件加载"""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f".ep 文件不存在: {path}")

        proj = cls()
        with h5py.File(path, "r") as f:
            md = f["metadata"]

            def _decode(v):
                if isinstance(v, bytes):
                    return v.decode("utf-8")
                return v

            proj.raw_files = [Path(_decode(p)) for p in md["raw_files"][()].tolist()]
            checksums = [_decode(c) for c in md["raw_checksums"][()].tolist()]
            proj.raw_checksums = dict(zip([str(p) for p in proj.raw_files], checksums))
            proj.config = json.loads(_decode(md["config"][()]))
            proj.selected_channel_id = str(_decode(md.attrs.get("selected_channel_id", "")))
            if "provenance" in md:
                proj.provenance = json.loads(_decode(md["provenance"][()]))
            if "processing_state" in md:
                proj.processing_state = json.loads(_decode(md["processing_state"][()]))
            proj.created_at = _decode(md.attrs.get("created_at", ""))
            proj.modified_at = _decode(md.attrs.get("modified_at", ""))

            if "analysis" in f:
                an = f["analysis"]
                proj.surface_depth = float(an["surface_depth"][()]) if "surface_depth" in an else 2.0
                if "bottom_line" in an:
                    proj.bottom_line = an["bottom_line"][()]
                if "lines" in an:
                    proj.line_manager = LineManager.from_records(
                        json.loads(_decode(an["lines"][()]))
                    )
                else:
                    proj.line_manager.set_offset(LineManager.SURFACE_ID, proj.surface_depth)
                    if proj.bottom_line is not None:
                        proj.line_manager.set_line_data(
                            LineManager.BOTTOM_ID, proj.bottom_line, kind="detected"
                        )
                if "analysis_region" in an:
                    region = json.loads(_decode(an["analysis_region"][()]))
                    proj.analysis_region = AnalysisRegion(
                        region["upper_line_id"], region["lower_line_id"]
                    )
                proj.analysis_region_enabled = (
                    bool(an["analysis_region_enabled"][()])
                    if "analysis_region_enabled" in an
                    else proj.analysis_region is not None
                )
                if "display_settings" in an:
                    proj.display_settings = json.loads(_decode(an["display_settings"][()]))
                if "noise_mask" in an:
                    proj.noise_mask = an["noise_mask"][()]
                if "school_mask" in an:
                    proj.school_mask = an["school_mask"][()]

            if "results" in f:
                rs = f["results"]

                def _decode(v):
                    if isinstance(v, bytes):
                        return v.decode("utf-8")
                    return v

                for name in ("schools_df", "integration_df", "sed_df", "sed_grid_df"):
                    if name not in rs:
                        continue
                    table = rs[name]
                    if isinstance(table, h5py.Group):
                        setattr(proj, name, read_frame(table))
                    else:
                        # 1.0–1.2 结果以 JSON records 保存，精度限制无法从旧文件恢复。
                        setattr(proj, name, pd.read_json(io.StringIO(_decode(table[()]))))

            if "channels" in f:
                for group_name in sorted(f["channels"]):
                    group = f["channels"][group_name]
                    channel_id = str(_decode(group.attrs["channel_id"]))
                    state = {
                        "config": json.loads(_decode(group.attrs.get("config", "{}"))),
                        "surface_depth": float(group.attrs.get("surface_depth", proj.surface_depth)),
                        "bottom_manually_edited": bool(group.attrs.get("bottom_manually_edited", False)),
                        "analysis_region_enabled": bool(group.attrs.get("analysis_region_enabled", False)),
                        "noise_enabled": json.loads(_decode(group.attrs.get("noise_enabled", "false"))),
                        "noise_applied": bool(group.attrs.get("noise_applied", False)),
                        "stale_results": json.loads(_decode(group.attrs.get("stale_results", "[]"))),
                        "incomplete_results": json.loads(_decode(group.attrs.get("incomplete_results", "[]"))),
                        "result_provenance": json.loads(
                            _decode(group.attrs.get("result_provenance", "{}"))
                        ),
                        "analysis_region": json.loads(_decode(group.attrs.get("analysis_region", "null"))),
                        "lines": json.loads(_decode(group["lines"][()])) if "lines" in group else [],
                    }
                    for key in ("bottom_line", "noise_mask", "school_mask"):
                        if key in group:
                            state[key] = group[key][()]
                        else:
                            state[key] = None
                    results = group.get("results")
                    for key in ("schools_df", "integration_df", "sed_df", "sed_grid_df"):
                        if results is not None and key in results:
                            table = results[key]
                            state[key] = read_frame(table) if isinstance(table, h5py.Group) else None
                        else:
                            state[key] = None
                    for stack_name in ("undo_stack", "redo_stack"):
                        stack = []
                        if stack_name in group:
                            for item_name in sorted(group[stack_name], key=int):
                                item_group = group[stack_name][item_name]
                                action = str(_decode(item_group.attrs["action"]))
                                value = item_group["data"][()] if "data" in item_group else None
                                stack.append((action, value))
                        state[stack_name] = stack
                    proj.channel_states[channel_id] = state

        return proj

    def build_manifest(self) -> dict:
        """生成当前项目快照；旧结果是否与当前配置一致由 processing_state 表明。"""
        self._sync_line_manager_from_legacy()
        checksums = {str(p): self.raw_checksums.get(str(p), "") for p in self.raw_files}
        manifest = snapshot_metadata(self.config, checksums)
        lines = self.line_manager.to_records()
        for line in lines:
            if line["values"] is not None:
                # 无有效底线的 ping 在标准 JSON 中表示为 null。
                line["values"] = [v if np.isfinite(v) else None for v in line["values"]]
        manifest.update({
            "project_version": PROJECT_VERSION,
            "config": self.config,
            "inputs": [
                {"path": str(p), "checksum": checksums[str(p)], "algorithm": "md5"}
                for p in self.raw_files
            ],
            "input_checksums_scope": "recorded_not_reverified",
            "lines": lines,
            "analysis_region": None if self.analysis_region is None else {
                "upper_line_id": self.analysis_region.upper_line_id,
                "lower_line_id": self.analysis_region.lower_line_id,
            },
            "analysis_region_enabled": bool(self.analysis_region_enabled),
            "noise_mask": mask_summary(self.noise_mask),
            "processing_state": self.processing_state,
            "results_status": self.processing_state.get("reference_results_status", "unverified"),
        })
        # 断开可变配置引用，确保已生成的说明不会随之后的界面编辑改变。
        return json.loads(json.dumps(manifest, ensure_ascii=False, default=str))

    def export_manifest(self, path: Path) -> Path:
        """原子导出当前快照说明 JSON；完整掩码与结果仍需配套 .ep 文件。"""
        path = Path(path)
        temp_path = path.with_name(f".{path.name}.tmp")
        payload = json.dumps(self.build_manifest(), ensure_ascii=False, indent=2)
        try:
            temp_path.write_text(payload + "\n", encoding="utf-8")
            os.replace(temp_path, path)
        except Exception:
            if temp_path.exists():
                temp_path.unlink()
            raise
        return path

    def get_line_manager(self) -> LineManager:
        """返回通用线段模型，并兼容旧调用方直接写入的字段。"""
        self._sync_line_manager_from_legacy()
        return self.line_manager

    def _sync_line_manager_from_legacy(self) -> None:
        """将旧表线/底线字段与通用线模型保持双向兼容。"""
        surface = self.line_manager.get(LineManager.SURFACE_ID)
        if surface.kind == "derived":
            # 新线模型为主状态；仅当它仍为默认值时接纳旧调用方写入的 legacy 值。
            if np.isclose(surface.offset_m, 2.0) and not np.isclose(self.surface_depth, 2.0):
                surface.offset_m = float(self.surface_depth)
        bottom = self.line_manager._lines.get(LineManager.BOTTOM_ID)
        if self.bottom_line is not None and (bottom is None or bottom.values is None):
            self.line_manager.set_line_data(LineManager.BOTTOM_ID, self.bottom_line, kind="detected")
            bottom = self.line_manager.get(LineManager.BOTTOM_ID)
        self.surface_depth = float(surface.offset_m)
        if bottom is not None and bottom.values is not None:
            self.bottom_line = bottom.values.copy()

    # ═══════════════════════════════════════════════════════
    # 完整性检查
    # ═══════════════════════════════════════════════════════

    def verify_raw_files(self) -> tuple[bool, list[Path]]:
        """检查所有 .raw 文件是否存在且校验和匹配。

        Returns
        -------
        (all_ok, problem_files)
            problem_files: 不存在或校验和不匹配的文件列表
        """
        problems = []
        for p in self.raw_files:
            if not p.exists():
                problems.append(p)
            elif str(p) in self.raw_checksums and self.raw_checksums[str(p)]:
                if _md5(p) != self.raw_checksums[str(p)]:
                    problems.append(p)
        return (len(problems) == 0, problems)

    def compute_checksums(self) -> None:
        """为所有 .raw 文件计算校验和"""
        for p in self.raw_files:
            if p.exists():
                self.raw_checksums[str(p)] = _md5(p)
