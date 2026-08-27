"""独立于 Qt 的 Echogram 线段领域模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import numpy as np


DEFAULT_LINE_COLORS = ("#4ec9b0", "#ffcc00", "#ff6b6b", "#b388ff", "#64b5f6")


@dataclass
class LineDefinition:
    """一条深度线，深度单位为米，正方向向下。"""

    id: str
    name: str
    kind: str = "derived"
    reference_id: str | None = None
    offset_m: float = 0.0
    visible: bool = True
    color: str = DEFAULT_LINE_COLORS[0]
    values: np.ndarray | None = field(default=None, repr=False)
    ping_times: np.ndarray | None = field(default=None, repr=False)

    def copy(self) -> "LineDefinition":
        return LineDefinition(
            id=self.id,
            name=self.name,
            kind=self.kind,
            reference_id=self.reference_id,
            offset_m=self.offset_m,
            visible=self.visible,
            color=self.color,
            values=None if self.values is None else self.values.copy(),
            ping_times=None if self.ping_times is None else self.ping_times.copy(),
        )


class LineManager:
    """管理 Zero、检测线、手工线和引用偏移线。"""

    ZERO_ID = "zero"
    SURFACE_ID = "surface"
    BOTTOM_ID = "bottom"

    def __init__(self, lines: Iterable[LineDefinition] | None = None):
        self._lines: dict[str, LineDefinition] = {}
        self._revision = 0
        if lines is None:
            self._install_defaults()
        else:
            for line in lines:
                self._lines[line.id] = line.copy()
            if self.ZERO_ID not in self._lines:
                self._install_defaults()

    def _install_defaults(self) -> None:
        self._lines = {
            self.ZERO_ID: LineDefinition(self.ZERO_ID, "Zero", kind="zero", color="#ffffff"),
            self.SURFACE_ID: LineDefinition(
                self.SURFACE_ID,
                "Surface",
                reference_id=self.ZERO_ID,
                offset_m=2.0,
                color=DEFAULT_LINE_COLORS[0],
            ),
        }

    def __iter__(self):
        return iter(self._lines.values())

    @property
    def revision(self) -> int:
        """返回模型修订号，供依赖线段解析结果的缓存判定失效。"""
        return self._revision

    def _touch(self) -> None:
        self._revision += 1

    def get(self, line_id: str) -> LineDefinition:
        try:
            return self._lines[line_id]
        except KeyError as exc:
            raise ValueError(f"Unknown line: {line_id}") from exc

    def editable_lines(self) -> list[LineDefinition]:
        return [line for line in self if line.visible and line.id != self.ZERO_ID]

    def add_line(
        self,
        line_id: str,
        name: str,
        *,
        reference_id: str | None,
        offset_m: float = 0.0,
        color: str | None = None,
    ) -> LineDefinition:
        if line_id in self._lines:
            raise ValueError(f"Line already exists: {line_id}")
        self._validate_name(name)
        if reference_id is None:
            raise ValueError("Derived lines require a reference")
        self.get(reference_id)
        line = LineDefinition(
            line_id,
            name.strip(),
            reference_id=reference_id,
            offset_m=float(offset_m),
            color=color or DEFAULT_LINE_COLORS[len(self._lines) % len(DEFAULT_LINE_COLORS)],
        )
        self._lines[line_id] = line
        self._touch()
        return line

    def rename_line(self, line_id: str, name: str) -> None:
        if line_id == self.ZERO_ID:
            raise ValueError("Zero line is protected")
        self._validate_name(name, except_id=line_id)
        self.get(line_id).name = name.strip()
        self._touch()

    def delete_line(self, line_id: str, *, protected_ids: set[str] | None = None) -> None:
        if line_id == self.ZERO_ID:
            raise ValueError("Zero line is protected")
        if line_id in (protected_ids or set()):
            raise ValueError("Line is protected by the active analysis region")
        if any(line.reference_id == line_id for line in self):
            raise ValueError("Line is referenced by another line")
        self.get(line_id)
        del self._lines[line_id]
        self._touch()

    def set_reference(self, line_id: str, reference_id: str) -> None:
        line = self.get(line_id)
        if line_id == self.ZERO_ID:
            raise ValueError("Zero line is protected")
        self.get(reference_id)
        if self._would_cycle(line_id, reference_id):
            raise ValueError("Line reference would create a cycle")
        line.reference_id = reference_id
        line.kind = "derived"
        line.values = None
        line.ping_times = None
        self._touch()

    def set_offset(self, line_id: str, offset_m: float) -> None:
        line = self.get(line_id)
        if line.kind == "zero":
            raise ValueError("Zero line is protected")
        line.offset_m = float(offset_m)
        self._touch()

    def set_visible(self, line_id: str, visible: bool) -> None:
        self.get(line_id).visible = bool(visible)
        self._touch()

    def set_line_data(
        self,
        line_id: str,
        values: Iterable[float],
        ping_times: Iterable | None = None,
        *,
        kind: str = "manual",
    ) -> None:
        if line_id == self.ZERO_ID:
            raise ValueError("Zero line cannot be drawn")
        line = self._lines.get(line_id)
        if line is None:
            line = LineDefinition(line_id, "Bottom" if line_id == self.BOTTOM_ID else line_id, color="#ffcc00")
            self._lines[line_id] = line
        arr = np.asarray(values, dtype=np.float32).reshape(-1)
        times = None if ping_times is None else np.asarray(ping_times).reshape(-1)
        if times is not None and len(times) != len(arr):
            raise ValueError("ping_times must have the same length as values")
        if kind not in {"manual", "detected"}:
            raise ValueError("Line data kind must be manual or detected")
        line.kind = kind
        line.reference_id = None
        line.offset_m = 0.0
        line.values = arr
        line.ping_times = times
        self._touch()

    def resolve_for_pings(self, line_id: str, ping_times: Iterable) -> np.ndarray:
        target_times = np.asarray(ping_times).reshape(-1)
        return self._resolve(line_id, target_times, set())

    def _resolve(self, line_id: str, target_times: np.ndarray, visited: set[str]) -> np.ndarray:
        if line_id in visited:
            raise ValueError("Line reference cycle")
        line = self.get(line_id)
        if line.kind == "zero":
            return np.zeros(len(target_times), dtype=np.float32)
        if line.kind in {"manual", "detected"}:
            return self._reindex(line.values, line.ping_times, target_times)
        if line.reference_id is None:
            return np.full(len(target_times), np.nan, dtype=np.float32)
        base = self._resolve(line.reference_id, target_times, visited | {line_id})
        return (base + line.offset_m).astype(np.float32)

    @staticmethod
    def _reindex(
        values: np.ndarray | None,
        source_times: np.ndarray | None,
        target_times: np.ndarray,
    ) -> np.ndarray:
        out = np.full(len(target_times), np.nan, dtype=np.float32)
        if values is None:
            return out
        if source_times is None:
            out[: min(len(out), len(values))] = values[: len(out)]
            return out
        positions = {value: index for index, value in enumerate(source_times.tolist())}
        for index, value in enumerate(target_times.tolist()):
            source_index = positions.get(value)
            if source_index is not None:
                out[index] = values[source_index]
        return out

    def to_records(self) -> list[dict]:
        records = []
        for line in self:
            records.append(
                {
                    "id": line.id,
                    "name": line.name,
                    "kind": line.kind,
                    "reference_id": line.reference_id,
                    "offset_m": line.offset_m,
                    "visible": line.visible,
                    "color": line.color,
                    "values": None if line.values is None else line.values.tolist(),
                    "ping_times": None if line.ping_times is None else line.ping_times.tolist(),
                    "ping_times_dtype": None if line.ping_times is None else str(line.ping_times.dtype),
                }
            )
        return records

    @classmethod
    def from_records(cls, records: Iterable[dict]) -> "LineManager":
        lines = []
        for record in records:
            line = LineDefinition(
                id=record["id"],
                name=record["name"],
                kind=record.get("kind", "derived"),
                reference_id=record.get("reference_id"),
                offset_m=float(record.get("offset_m", 0.0)),
                visible=bool(record.get("visible", True)),
                color=record.get("color", DEFAULT_LINE_COLORS[0]),
                values=None if record.get("values") is None else np.asarray(record["values"], dtype=np.float32),
                ping_times=(
                    None
                    if record.get("ping_times") is None
                    else np.asarray(record["ping_times"], dtype=record.get("ping_times_dtype"))
                ),
            )
            lines.append(line)
        return cls(lines)

    def _validate_name(self, name: str, except_id: str | None = None) -> None:
        normalized = name.strip().casefold()
        if not normalized:
            raise ValueError("Line name cannot be empty")
        if any(line.id != except_id and line.name.casefold() == normalized for line in self):
            raise ValueError("Line name must be unique")

    def _would_cycle(self, line_id: str, reference_id: str) -> bool:
        current = reference_id
        while current is not None:
            if current == line_id:
                return True
            current = self.get(current).reference_id
        return False
