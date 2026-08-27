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

PROJECT_VERSION = "1.1"


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

        # 分析结果
        self.surface_depth: float = 2.0
        self.bottom_line: np.ndarray | None = None
        self.line_manager = LineManager()
        self.analysis_region: AnalysisRegion | None = None
        self.display_settings: dict = {"colormap": "jet", "vmin": -90.0, "vmax": -30.0}
        self.noise_mask: np.ndarray | None = None
        self.school_mask: np.ndarray | None = None

        # 统计结果
        self.schools_df: pd.DataFrame | None = None
        self.integration_df: pd.DataFrame | None = None
        self.sed_df: pd.DataFrame | None = None

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
            self._save_to_path(temp_path)
            os.replace(temp_path, path)
        except Exception:
            if temp_path.exists():
                temp_path.unlink()
            raise
        return path

    def _save_to_path(self, path: Path) -> None:
        """保存到 .ep 文件（HDF5）"""
        self.modified_at = _now()
        self._sync_line_manager_from_legacy()

        with h5py.File(path, "w") as f:
            # metadata
            md = f.create_group("metadata")
            md.create_dataset("raw_files", data=[str(p) for p in self.raw_files])
            md.create_dataset("raw_checksums", data=[self.raw_checksums.get(str(p), "") for p in self.raw_files])
            md.attrs["version"] = PROJECT_VERSION
            md.attrs["created_at"] = self.created_at
            md.attrs["modified_at"] = self.modified_at
            md.create_dataset("config", data=json.dumps(self.config, ensure_ascii=False))

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
            if self.schools_df is not None and not self.schools_df.empty:
                rs.create_dataset("schools_df", data=self.schools_df.to_json(orient="records"))
            if self.integration_df is not None and not self.integration_df.empty:
                rs.create_dataset("integration_df", data=self.integration_df.to_json(orient="records"))
            if self.sed_df is not None and not self.sed_df.empty:
                rs.create_dataset("sed_df", data=self.sed_df.to_json(orient="records"))


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
            proj.created_at = _decode(md.attrs.get("created_at", ""))
            proj.modified_at = _decode(md.attrs.get("modified_at", ""))

            if "analysis" in f:
                an = f["analysis"]
                proj.surface_depth = float(an.get("surface_depth", 2.0)[()])
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

                if "schools_df" in rs:
                    proj.schools_df = pd.read_json(io.StringIO(_decode(rs["schools_df"][()])))
                if "integration_df" in rs:
                    proj.integration_df = pd.read_json(io.StringIO(_decode(rs["integration_df"][()])))
                if "sed_df" in rs:
                    proj.sed_df = pd.read_json(io.StringIO(_decode(rs["sed_df"][()])))

        return proj

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
