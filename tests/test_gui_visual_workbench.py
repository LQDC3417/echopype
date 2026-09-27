"""Echoview 风格工作台与 SVG 图标的界面契约。"""

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QGroupBox


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


def test_workbench_toolbar_labels_project_actions(qapp):
    """项目操作应使用图标加文字，画布工具仍保持紧凑图标形式。"""
    from src.gui.toolbars import EchogramToolBar, StandardToolBar

    standard = StandardToolBar()
    echogram = EchogramToolBar()
    try:
        assert standard.toolButtonStyle() == Qt.ToolButtonTextBesideIcon
        assert echogram.toolButtonStyle() == Qt.ToolButtonIconOnly
        assert [action.text() for action in standard.actions() if not action.isSeparator()] == [
            "导入数据",
            "打开项目",
            "导出",
        ]
        assert all(not action.icon().isNull() for action in standard.actions() if not action.isSeparator())
        assert not echogram.pan_button.icon().isNull()
        assert echogram.pan_button.text() == ""
    finally:
        standard.close()
        echogram.close()


def test_property_panel_exposes_reference_ordered_accordion(qapp):
    """属性区应为 ESP3 任务页顺序，Processing 页提供 Apply 到 Layer。"""
    from src.gui.property_panel import PropertyPanel

    panel = PropertyPanel()
    try:
        assert panel.section_ids() == (
            "processing",
            "echo_integration",
            "lines",
            "display",
            "file_info",
        )
        assert panel.btn_apply_current.property("cssClass") == "primary"
        assert hasattr(panel, "apply_current_clicked")
        assert hasattr(panel, "apply_all_clicked")
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
        labels = [label.text() for label in panel.findChildren(QLabel)]
        tab_titles = [panel._tabs.tabText(i) for i in range(panel._tabs.count())]

        assert tab_titles == [
            "Processing",
            "Integration",
            "Lines",
            "Display",
            "Info",
        ]
        assert panel.btn_apply_current.text() == "Apply current"
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


def test_main_window_right_dock_shows_only_file_and_statistics(qapp):
    """右栏 ESP3 任务页全部可达，默认停在 Processing。"""
    from src.gui.main_window import MainWindow

    window = MainWindow()
    try:
        window.show()
        qapp.processEvents()
        assert window.property_panel.section_ids() == (
            "processing",
            "echo_integration",
            "lines",
            "display",
            "file_info",
        )
        assert window.property_panel._tabs.currentIndex() == 0
    finally:
        window.close()


def test_left_panel_groups_project_view_and_channel_context(qapp):
    """ESP3 风格左栏：Layers + Channels + 快捷操作。"""
    from src.gui.left_panel import LeftPanel

    panel = LeftPanel()
    try:
        group_titles = [group.title() for group in panel.findChildren(QGroupBox)]
        assert group_titles == ["调查文件", "数据图层", "快捷操作"]
        assert panel.project_summary.text() == "当前无项目"
        assert hasattr(panel, "variable_list")
        assert hasattr(panel, "workflow_buttons")
    finally:
        panel.close()


def test_display_settings_stay_in_sync_after_edit_and_reset(qapp):
    """侧栏、图例与项目快照应使用同一组色阶。"""
    from src.gui.main_window import MainWindow

    window = MainWindow()
    try:
        window._on_display_params_changed("viridis", -85.0, -35.0)
        assert window.display_settings == {"colormap": "viridis", "vmin": -85.0, "vmax": -35.0}
        assert window.echogram._vmin == window.property_panel.display.spin_vmin.value() == -85.0
        window._apply_display_settings("jet", -90.0, -30.0)
        assert window.property_panel.display.spin_vmin.value() == window.echogram._vmin == -90.0
    finally:
        window.close()


def test_file_info_uses_frequency_and_sections_toggle(qapp):
    """长声道标识不冒充频率；折叠后仍可恢复内容。"""
    import xarray as xr
    from src.gui.property_panel import PropertyPanel

    panel = PropertyPanel()
    try:
        panel.file_info.update_info(xr.Dataset(
            {"frequency_nominal": ("channel", [200000.0])},
            coords={"channel": ["long-channel-identifier"]},
        ))
        assert panel.file_info.row_freq.lbl_value.text() == "200 kHz"
        assert panel.file_info.row_freq.lbl_value.text() == "200 kHz"
        panel.show_task("file_info")
        assert panel._tabs.currentIndex() == 4
    finally:
        panel.close()
