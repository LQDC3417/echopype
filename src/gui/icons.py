"""本地 SVG 图标加载器，统一 Echogram 工作台的图标状态。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer


_ICON_DIR = Path(__file__).with_name("assets") / "icons"
_ICON_FILES = {
    "import": "import.svg",
    "open": "folder-open.svg",
    "save": "save.svg",
    "run": "run.svg",
    "undo": "undo.svg",
    "redo": "redo.svg",
    "export": "export.svg",
    "pan_open": "pan-open.svg",
    "pan_closed": "pan-closed.svg",
    "pointer": "pointer.svg",
    "noise": "noise.svg",
    "bottom": "bottom.svg",
    "inspect": "inspect.svg",
    "reset": "reset.svg",
    "fit": "fit.svg",
    "prev": "previous.svg",
    "next": "next.svg",
    "palette": "palette.svg",
    "zoom_in": "zoom-in.svg",
    "zoom_out": "zoom-out.svg",
    "settings": "settings.svg",
    "file_info": "file-info.svg",
    "display": "display.svg",
    "processing": "processing.svg",
    "ruler": "ruler.svg",
    "advanced": "advanced.svg",
}


def icon_path(name: str) -> Path:
    """返回图标的本地资源路径，未知名称应尽早失败。"""
    try:
        return _ICON_DIR / _ICON_FILES[name]
    except KeyError as exc:
        raise KeyError(f"Unknown workbench icon: {name}") from exc


def _render_svg(svg: str, color: str, size: int) -> QPixmap:
    renderer = QSvgRenderer(QByteArray(svg.replace("currentColor", color).encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap


@lru_cache(maxsize=None)
def icon(name: str, size: int = 22) -> QIcon:
    """构建包含默认、悬停、选中和禁用状态的 QIcon。"""
    svg = icon_path(name).read_text(encoding="utf-8")
    result = QIcon()
    result.addPixmap(_render_svg(svg, "#d7e1e8", size), QIcon.Mode.Normal, QIcon.State.Off)
    result.addPixmap(_render_svg(svg, "#00cbea", size), QIcon.Mode.Active, QIcon.State.Off)
    result.addPixmap(_render_svg(svg, "#00cbea", size), QIcon.Mode.Normal, QIcon.State.On)
    result.addPixmap(_render_svg(svg, "#65717c", size), QIcon.Mode.Disabled, QIcon.State.Off)
    return result
