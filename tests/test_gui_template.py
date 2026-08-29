"""浅色 Echoview 风格 GUI 模板的冒烟测试。"""

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QScrollArea, QTabWidget

from src.gui.property_panel import PropertyPanel

_TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "templates" / "echoview_gui_template.py"
if _TEMPLATE_PATH.is_file():
    from templates.echoview_gui_template import EchoviewTemplateWindow
else:
    EchoviewTemplateWindow = None


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_light_template_exposes_workbench_regions(qapp):
    if EchoviewTemplateWindow is None:
        pytest.skip("optional local GUI template is unavailable")

    window = EchoviewTemplateWindow()

    assert window.windowTitle() == "Echoview · Fish Acoustic Workbench"
    assert window.findChild(object, "echogramCanvas") is not None
    assert window.findChild(object, "filesetDock") is not None
    assert window.findChild(object, "processingDock") is not None
    assert window.findChild(object, "bottomDock") is not None

    window.close()
def test_live_property_panel_is_single_scrollable_page(qapp):
    """实际主窗口属性区应使用单页滚动布局，而不是多页签切换。"""
    panel = PropertyPanel()
    try:
        assert not isinstance(panel, QTabWidget)
        scroll = panel.findChild(QScrollArea, "propertyScroll")
        assert scroll is not None
        assert panel.file_info is not None
        assert panel.display is not None
        assert panel.processing is not None
        assert panel.stats is not None
    finally:
        panel.close()


def test_overlay_actions_are_disabled_until_data_is_loaded(qapp):
    """无数据时不能操作处理结果开关。"""
    from src.gui.main_window import MainWindow

    window = MainWindow()
    try:
        assert not window._act_noise.isEnabled()
        assert not window._act_school.isEnabled()
        assert not window._act_bottom.isEnabled()
    finally:
        window.close()


def test_echogram_toolbar_exposes_clickable_pan_tool(qapp):
    """工具栏应提供模板式的直接手爪按钮。"""
    from src.gui.toolbars import EchogramToolBar, MouseMode

    toolbar = EchogramToolBar()
    try:
        assert toolbar.pan_button is not None
        toolbar.pan_button.click()
        assert toolbar.mode_combo.currentIndex() == MouseMode.PAN.value
        toolbar.pan_button.click()
        assert toolbar.pan_button.isChecked()
    finally:
        toolbar.close()
