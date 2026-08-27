"""浅色 Echoview 风格 GUI 模板的冒烟测试。"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from templates.echoview_gui_template import EchoviewTemplateWindow


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_light_template_exposes_workbench_regions(qapp):
    window = EchoviewTemplateWindow()

    assert window.windowTitle() == "Echoview · Fish Acoustic Workbench"
    assert window.findChild(object, "echogramCanvas") is not None
    assert window.findChild(object, "filesetDock") is not None
    assert window.findChild(object, "processingDock") is not None
    assert window.findChild(object, "bottomDock") is not None

    window.close()
