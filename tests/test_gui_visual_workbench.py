"""Echoview 风格工作台与 SVG 图标的界面契约。"""

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_icon_registry_provides_local_svg_icons(qapp):
    """核心工作台操作应从本地 SVG 资源取得统一图标。"""
    from src.gui.icons import icon, icon_path

    for name in ("import", "save", "run", "pan_open", "pan_closed", "zoom_in"):
        assert icon_path(name).is_file()
        assert not icon(name).isNull()


def test_pyinstaller_spec_packages_gui_svg_assets():
    """冻结版应用也必须包含图标加载器使用的本地 SVG 目录。"""
    spec_path = Path(__file__).parents[1] / "echopype.spec"

    assert 'str(ROOT / "src" / "gui" / "assets")' in spec_path.read_text(encoding="utf-8")


def test_workbench_toolbars_are_icon_first(qapp):
    """顶栏应使用紧凑 SVG 图标，避免平台默认图标和 emoji。"""
    from src.gui.toolbars import EchogramToolBar, StandardToolBar

    standard = StandardToolBar()
    echogram = EchogramToolBar()
    try:
        assert standard.toolButtonStyle() == Qt.ToolButtonIconOnly
        assert echogram.toolButtonStyle() == Qt.ToolButtonIconOnly
        assert all(not action.icon().isNull() for action in standard.actions() if not action.isSeparator())
        assert not echogram.pan_button.icon().isNull()
        assert echogram.pan_button.text() == ""
    finally:
        standard.close()
        echogram.close()


def test_property_panel_exposes_reference_ordered_accordion(qapp):
    """属性区应为单一滚动的参考图顺序，且不再提供统一应用按钮。"""
    from src.gui.property_panel import PropertyPanel

    panel = PropertyPanel()
    try:
        assert panel.section_ids() == (
            "file_info",
            "display",
            "processing",
            "bottom",
            "export",
            "annotations",
            "advanced",
        )
        assert not hasattr(panel.processing, "btn_apply_all")
    finally:
        panel.close()


def test_property_panel_translates_workbench_section_titles(qapp):
    """英文界面重启后，新增工作台分区不应残留中文标题或说明。"""
    from src.gui.i18n import get_language, set_language
    from src.gui.property_panel import PropertyPanel

    previous_language = get_language()
    set_language("en")
    panel = PropertyPanel()
    try:
        headers = [section.header.text() for section in panel._sections.values()]
        labels = [label.text() for label in panel.findChildren(QLabel)]

        assert headers == [
            "File Info",
            "Display Settings",
            "Parameters",
            "Bottom Detection",
            "Export",
            "Annotations & Measurements",
            "Advanced Analysis",
        ]
        assert "Export uses the current Echogram and processed results." in labels
        assert "Selection, hand panning, and bottom drawing tools are in the toolbar above." in labels
    finally:
        panel.close()
        set_language(previous_language)


def test_pan_mode_sets_open_hand_before_drag(qapp):
    """点击手爪后，进入 Echogram 前即显示可拖动的张开手爪。"""
    from src.gui.toolbars import MouseMode
    from src.viz.opengl_renderer import EchogramRenderer

    renderer = EchogramRenderer()
    try:
        renderer.set_mouse_mode(MouseMode.PAN)
        assert renderer.cursor().shape() == Qt.OpenHandCursor
    finally:
        renderer.close()


def test_main_window_uses_document_style_workspace_chrome(qapp):
    """主窗口应具备参考图所示的文件标签和无标题 Dock 工作台边框。"""
    from src.gui.main_window import MainWindow

    window = MainWindow()
    try:
        assert window.view_tabs.documentMode()
        assert window.dock_left.titleBarWidget() is not None
        assert window.dock_right.titleBarWidget() is not None
        assert window.dock_bottom.titleBarWidget() is not None
    finally:
        window.close()
