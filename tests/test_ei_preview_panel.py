"""ESP3 右栏：Channel 下拉与积分结果预览。"""

import os

import pandas as pd
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QTableWidget


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_channel_combo_and_integration_preview(qapp):
    from src.gui.property_panel import PropertyPanel

    panel = PropertyPanel()
    try:
        panel.set_channels(["38 kHz", "70 kHz", "120 kHz"])
        assert panel.processing.combo_channel.count() == 3
        assert panel.processing.combo_channel.itemText(0) == "38 kHz"

        df = pd.DataFrame(
            {
                "esu_id": [1, 2],
                "mean_Sv": [-55.1, -60.2],
                "abc": [12.3, 8.4],
            }
        )
        panel.update_integration_preview(df)
        assert panel.ei_result_table.rowCount() == 2
        assert panel.ei_result_table.columnCount() == 3
        assert "2" in panel.ei_result_summary.text()
        assert panel.stats.integration_table.rowCount() == 2
        assert (
            panel.ei_result_table.editTriggers()
            == panel.stats.integration_table.editTriggers()
            == QTableWidget.NoEditTriggers
        )

        panel.update_integration_preview(None)
        assert panel.ei_result_table.rowCount() == 0
    finally:
        panel.close()


def test_show_task_switches_tabs(qapp):
    from src.gui.property_panel import PropertyPanel

    panel = PropertyPanel()
    try:
        panel.show_task("noise")
        assert panel._tabs.currentIndex() == 0
        panel.show_task("integration")
        assert panel._tabs.currentIndex() == 1
        panel.show_task("bottom")
        assert panel._tabs.currentIndex() == 2
    finally:
        panel.close()


@pytest.mark.parametrize("language", ["zh", "en"])
def test_task_pages_fit_sidebar_and_file_info_stays_visible(qapp, language):
    """窄侧栏能读取参数，文件信息仍属于可见任务页。"""
    from src.gui.i18n import get_language, set_language
    from src.gui.property_panel import PropertyPanel
    from src.gui.theme import DARK_THEME

    previous_language = get_language()
    set_language(language)
    panel = PropertyPanel()
    try:
        panel.setStyleSheet(DARK_THEME)
        panel.set_channels(["WBT 204536-15 ES200-7C 200.000 kHz long channel identifier"])
        panel.resize(360, 850)
        panel.show()
        for index in range(panel._tabs.count()):
            panel._tabs.setCurrentIndex(index)
            qapp.processEvents()
            scroll = panel._tabs.widget(index)
            assert scroll.horizontalScrollBar().maximum() == 0, f"tab {index} overflows"
        panel.show_task("file_info")
        qapp.processEvents()
        assert panel.file_info.isVisible()
        assert panel._tabs.currentWidget().widget().isAncestorOf(panel.file_info)
    finally:
        panel.close()
        set_language(previous_language)
