"""QualityDialog 单元测试"""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

# 确保 QApplication 单例
_app = QApplication.instance() or QApplication([])


@pytest.fixture
def dialog():
    """创建 QualityDialog 实例"""
    from src.gui.quality_dialog import QualityDialog
    return QualityDialog()


@pytest.fixture
def sv_result_valid():
    """Sv 检查结果：全部通过"""
    return {
        "valid": True,
        "sv_range": (-70.0, -30.0),
        "total_pings": 500,
        "total_samples": 2000,
        "nan_ratio": 0.02,
        "warnings": [],
    }


@pytest.fixture
def sv_result_with_warnings():
    """Sv 检查结果：有警告"""
    return {
        "valid": True,
        "sv_range": (-80.0, -20.0),
        "total_pings": 500,
        "total_samples": 2000,
        "nan_ratio": 0.15,
        "warnings": ["Sv 值范围偏大", "NaN 比例较高"],
    }


@pytest.fixture
def bottom_result_valid():
    """底线检查结果：正常"""
    return {
        "valid": True,
        "valid_pings": 480,
        "nan_ratio": 0.04,
        "warnings": [],
    }


def test_dialog_creation(dialog):
    """验证对话框可以创建"""
    assert dialog is not None
    assert dialog.windowTitle() == "数据质量检查"
    # 底线区域默认隐藏
    assert not dialog.bottom_group.isVisible()


def test_load_results_valid(dialog, sv_result_valid):
    """传入 valid=True 的结果，验证状态显示绿色"""
    dialog.load_results(sv_result_valid)
    dialog.show()

    # 状态文本应为通过
    assert "检查通过" in dialog.status_frame.text()

    # 验证 Sv 数据标签
    assert "[-70.0, -30.0]" in dialog.lbl_sv_range.text()
    assert "500 pings" in dialog.lbl_data_size.text()
    assert "2.0%" in dialog.lbl_nan_ratio.text()

    # 无警告时显示绿色提示
    assert dialog.lbl_no_warnings.isVisible()
    assert not dialog.warnings_list.isVisible()


def test_load_results_with_warnings(dialog, sv_result_with_warnings):
    """传入有 warnings 的结果，验证警告列表填充"""
    dialog.load_results(sv_result_with_warnings)
    dialog.show()

    # 状态应为警告
    assert "存在警告" in dialog.status_frame.text()

    # 警告列表应有 2 项
    assert dialog.warnings_list.count() == 2
    assert dialog.warnings_list.isVisible()
    assert not dialog.lbl_no_warnings.isVisible()

    # 检查警告内容
    assert "Sv 值范围偏大" in dialog.warnings_list.item(0).text()
    assert "NaN 比例较高" in dialog.warnings_list.item(1).text()


def test_load_results_with_bottom(dialog, sv_result_valid, bottom_result_valid):
    """传入底线结果，验证底线区域显示"""
    dialog.load_results(sv_result_valid, bottom_result=bottom_result_valid)
    dialog.show()

    # 底线区域应可见
    assert dialog.bottom_group.isVisible()

    # 验证底线数据
    assert "480" in dialog.lbl_valid_pings.text()
    assert "4.0%" in dialog.lbl_bottom_nan.text()

    # 整体状态应为通过
    assert "检查通过" in dialog.status_frame.text()
