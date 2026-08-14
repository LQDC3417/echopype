"""MultifreqDialog 单元测试"""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pandas as pd
import pytest
from unittest.mock import patch, MagicMock
from PySide6.QtWidgets import QApplication

# 确保 QApplication 单例
_app = QApplication.instance() or QApplication([])


@pytest.fixture
def dialog():
    """创建 MultifreqDialog 实例"""
    from src.gui.multifreq_dialog import MultifreqDialog
    return MultifreqDialog()


@pytest.fixture
def mock_summary_df():
    """模拟通道摘要 DataFrame"""
    return pd.DataFrame({
        "channel": ["channel_1", "channel_2"],
        "frequency_Hz": [38000, 70000],
        "n_pings": [500, 500],
        "n_samples": [2000, 2000],
    })


@pytest.fixture
def mock_compare_df():
    """模拟频率对比 DataFrame"""
    return pd.DataFrame({
        "channel": ["channel_1", "channel_2"],
        "frequency_Hz": [38000, 70000],
        "mean_abc": [-65.3, -58.1],
        "std_abc": [4.2, 3.8],
        "max_abc": [-45.0, -40.5],
    })


@pytest.fixture
def mock_single_channel_df():
    """单通道摘要 DataFrame"""
    return pd.DataFrame({
        "channel": ["channel_1"],
        "frequency_Hz": [38000],
        "n_pings": [500],
        "n_samples": [2000],
    })


def test_dialog_creation(dialog):
    """验证对话框可以创建"""
    assert dialog is not None
    assert dialog.windowTitle() == "多频率分析"
    assert dialog.summary_table.columnCount() == 4
    assert dialog.compare_table.columnCount() == 5


@patch("src.gui.multifreq_dialog.compare_frequencies")
@patch("src.gui.multifreq_dialog.get_channel_summary")
def test_load_data_with_summary(mock_get_summary, mock_compare, dialog,
                                 mock_summary_df, mock_compare_df):
    """传入 mock ds_Sv，验证通道摘要表格填充"""
    mock_get_summary.return_value = mock_summary_df
    mock_compare.return_value = mock_compare_df

    mock_ds = MagicMock()
    config = {"processing": {"frequencies": [38000, 70000]}}
    dialog.load_data(mock_ds, config)

    # 验证摘要表格行数
    assert dialog.summary_table.rowCount() == 2

    # 验证第一行数据
    assert dialog.summary_table.item(0, 0).text() == "channel_1"
    assert dialog.summary_table.item(0, 1).text() == "38,000.00"
    assert dialog.summary_table.item(0, 2).text() == "500"

    # 验证对比表格行数
    assert dialog.compare_table.rowCount() == 2
    assert dialog.compare_table.item(1, 0).text() == "channel_2"

    # 验证 DataFrame 缓存
    assert dialog._summary_df is not None
    assert dialog._compare_df is not None


@patch("src.gui.multifreq_dialog.compare_frequencies")
@patch("src.gui.multifreq_dialog.get_channel_summary")
def test_load_data_single_channel(mock_get_summary, mock_compare, dialog,
                                   mock_single_channel_df):
    """只有 1 个通道时，频率对比标签页显示提示"""
    mock_get_summary.return_value = mock_single_channel_df
    # compare_frequencies 少于 2 通道时返回空 DataFrame
    mock_compare.return_value = pd.DataFrame()

    mock_ds = MagicMock()
    config = {"processing": {"frequencies": [38000]}}
    dialog.load_data(mock_ds, config)

    # 验证摘要表格有 1 行
    assert dialog.summary_table.rowCount() == 1

    # 验证对比提示标签已设为可见（show 后 isVisible 才生效）
    dialog.show()
    dialog.tabs.setCurrentIndex(1)
    assert dialog.lbl_compare_hint.isVisible()
    # 对比表格应为空
    assert dialog.compare_table.rowCount() == 0
