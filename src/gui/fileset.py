"""Fileset Manager — Echoview 风格的文件集管理器

管理多文件调查项目：创建文件集 → 批量导入 .raw → 查看文件属性
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

logger = logging.getLogger("fish_acoustics")


@dataclass
class RawFileInfo:
    """单个 .raw 文件的元信息"""
    path: Path
    size_mb: float = 0.0
    channels: list[str] = field(default_factory=list)
    frequencies: list[float] = field(default_factory=list)
    ping_count: int = 0
    time_start: datetime | None = None
    time_end: datetime | None = None
    sonar_model: str = "EK80"
    is_valid: bool = False
    error_msg: str = ""

    @classmethod
    def probe(cls, path: Path, fast: bool = False) -> RawFileInfo:
        """探测 raw 文件元信息（快速模式只读文件头，不做全量解析）"""
        info = cls(path=path, size_mb=path.stat().st_size / 1e6 if path.exists() else 0)
        if fast:
            info.is_valid = path.exists() and path.suffix.lower() == ".raw"
            return info
        try:
            import echopype as ep
            ed = ep.open_raw(raw_file=str(path), sonar_model="EK80")
            info.sonar_model = "EK80"

            # 探测通道/频率
            if "Sonar/Beam_group1" in ed:
                bg = ed["Sonar/Beam_group1"]
                if "frequency_nominal" in bg:
                    freqs = bg["frequency_nominal"].values
                    if freqs.ndim > 0:
                        info.frequencies = [float(f) for f in freqs.flat]
                        info.channels = [f"{f/1000:.0f} kHz" for f in info.frequencies]
                    else:
                        info.frequencies = [float(freqs)]
                        info.channels = [f"{info.frequencies[0]/1000:.0f} kHz"]
                if "ping_time" in bg:
                    pts = bg["ping_time"].values
                    if pts.ndim > 0:
                        info.ping_count = len(pts.flat)
                        ts = pts.flat[:]
                        if len(ts) > 0:
                            info.time_start = _to_datetime(ts[0])
                            info.time_end = _to_datetime(ts[-1])
            info.is_valid = True
        except Exception as e:
            info.error_msg = str(e)
        return info


def _to_datetime(val) -> datetime | None:
    """numpy datetime64 → Python datetime"""
    try:
        ts = pd.Timestamp(val)
        return ts.to_pydatetime()
    except Exception:
        return None


@dataclass
class Fileset:
    """文件集 — 一个调查项目的多个 raw 文件"""
    name: str
    files: list[Path] = field(default_factory=list)
    file_infos: dict[str, RawFileInfo] = field(default_factory=dict)
    default_channel: str = ""
    created: datetime = field(default_factory=datetime.now)

    @property
    def file_count(self) -> int:
        return len(self.files)

    @property
    def total_pings(self) -> int:
        return sum(info.ping_count for info in self.file_infos.values())

    @property
    def channels(self) -> list[str]:
        """所有文件中出现的通道（去重）"""
        seen = set()
        for info in self.file_infos.values():
            for ch in info.channels:
                if ch not in seen:
                    seen.add(ch)
        return sorted(seen, key=_freq_sort_key)

    def probe_all(self, progress_callback=None) -> int:
        """探测所有文件的元信息（快速模式，不校验）"""
        count = 0
        for i, f in enumerate(self.files):
            if str(f) not in self.file_infos:
                info = RawFileInfo.probe(f, fast=False)
                self.file_infos[str(f)] = info
                if info.is_valid:
                    count += 1
            if progress_callback:
                progress_callback(i + 1, len(self.files))
        return count

    @classmethod
    def from_folder(cls, folder: Path, name: str | None = None,
                    pattern: str = "*.raw") -> Fileset:
        """从文件夹创建文件集"""
        folder = Path(folder)
        files = sorted(folder.glob(pattern))
        if not files:
            raise FileNotFoundError(f"在 {folder} 中未找到匹配 {pattern} 的文件")
        return cls(name=name or folder.name, files=list(files))

    @classmethod
    def from_paths(cls, paths: list[Path], name: str = "新建文件集") -> Fileset:
        """从文件路径列表创建文件集"""
        return cls(name=name, files=[Path(p) for p in paths])

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "files": [str(f) for f in self.files],
            "default_channel": self.default_channel,
            "created": self.created.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> Fileset:
        fs = cls(
            name=d["name"],
            files=[Path(p) for p in d.get("files", [])],
            default_channel=d.get("default_channel", ""),
        )
        if "created" in d:
            fs.created = datetime.fromisoformat(d["created"])
        return fs


def _freq_sort_key(ch: str) -> float:
    """按频率值排序：'38 kHz' → 38.0"""
    try:
        return float(ch.replace("kHz", "").strip())
    except ValueError:
        return 999.0


class FilesetStore:
    """文件集持久化存储"""

    def __init__(self, store_dir: Path | None = None):
        self.store_dir = store_dir or Path.home() / ".echogram"
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self.store_dir / "filesets.yaml"

    def list(self) -> list[str]:
        """列出所有文件集名称"""
        if not self._index_path.exists():
            return []
        with open(self._index_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return list(data.keys())

    def load(self, name: str) -> Fileset | None:
        """加载文件集"""
        if not self._index_path.exists():
            return None
        with open(self._index_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if name not in data:
            return None
        return Fileset.from_dict(data[name])

    def save(self, fileset: Fileset) -> None:
        """保存文件集"""
        data = {}
        if self._index_path.exists():
            with open(self._index_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        data[fileset.name] = fileset.to_dict()
        with open(self._index_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)

    def delete(self, name: str) -> bool:
        """删除文件集"""
        if not self._index_path.exists():
            return False
        with open(self._index_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if name not in data:
            return False
        del data[name]
        with open(self._index_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
        return True
