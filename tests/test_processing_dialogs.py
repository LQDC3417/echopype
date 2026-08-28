"""处理参数弹窗的 Apply/OK/Cancel 行为测试。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QSpinBox, QVBoxLayout, QWidget


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class ParameterWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.value = QSpinBox()
        self.value.setValue(5)
        layout = QVBoxLayout(self)
        layout.addWidget(self.value)

    def get_config(self):
        return {"value": self.value.value(), "nested": [1, 2]}


def _button(dialog, role):
    return dialog.button_box.button(role)


def test_parameter_changes_do_not_request_processing(qapp):
    from src.gui.processing_dialogs import ProcessingParametersDialog

    widget = ParameterWidget()
    dialog = ProcessingParametersDialog(widget, widget.get_config)
    spy = QSignalSpy(dialog.apply_requested)

    widget.value.setValue(6)
    QApplication.processEvents()

    assert spy.count() == 0


def test_apply_emits_only_when_config_changed_since_last_execution(qapp):
    from src.gui.processing_dialogs import ProcessingParametersDialog

    widget = ParameterWidget()
    dialog = ProcessingParametersDialog(widget, widget.get_config)
    spy = QSignalSpy(dialog.apply_requested)
    apply_button = _button(dialog, QDialogButtonBox.StandardButton.Apply)

    apply_button.click()
    assert spy.count() == 1
    assert spy.at(0)[0] == {"value": 5, "nested": [1, 2]}
    assert dialog.result() == 0

    apply_button.click()
    assert spy.count() == 1

    widget.value.setValue(8)
    apply_button.click()
    assert spy.count() == 2
    assert spy.at(1)[0]["value"] == 8


def test_ok_applies_pending_change_once_and_accepts(qapp):
    from src.gui.processing_dialogs import ProcessingParametersDialog

    widget = ParameterWidget()
    dialog = ProcessingParametersDialog(
        widget,
        widget.get_config,
        last_applied_config=widget.get_config(),
    )
    spy = QSignalSpy(dialog.apply_requested)
    widget.value.setValue(9)

    _button(dialog, QDialogButtonBox.StandardButton.Ok).click()

    assert spy.count() == 1
    assert spy.at(0)[0]["value"] == 9
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_ok_without_pending_change_does_not_emit(qapp):
    from src.gui.processing_dialogs import ProcessingParametersDialog

    widget = ParameterWidget()
    current = widget.get_config()
    dialog = ProcessingParametersDialog(widget, widget.get_config, last_applied_config=current)
    spy = QSignalSpy(dialog.apply_requested)

    _button(dialog, QDialogButtonBox.StandardButton.Ok).click()

    assert spy.count() == 0
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_cancel_discards_pending_change_but_not_prior_apply(qapp):
    from src.gui.processing_dialogs import ProcessingParametersDialog

    widget = ParameterWidget()
    dialog = ProcessingParametersDialog(widget, widget.get_config)
    spy = QSignalSpy(dialog.apply_requested)

    _button(dialog, QDialogButtonBox.StandardButton.Apply).click()
    widget.value.setValue(12)
    _button(dialog, QDialogButtonBox.StandardButton.Cancel).click()

    assert spy.count() == 1
    assert spy.at(0)[0]["value"] == 5
    assert dialog.result() == QDialog.DialogCode.Rejected


def test_cancel_restores_widget_values_to_last_applied_config(qapp):
    from src.gui.processing_dialogs import ProcessingParametersDialog

    widget = ParameterWidget()
    dialog = ProcessingParametersDialog(
        widget,
        widget.get_config,
        last_applied_config=widget.get_config(),
    )

    widget.value.setValue(12)
    _button(dialog, QDialogButtonBox.StandardButton.Cancel).click()

    assert widget.value.value() == 5


def test_applied_config_is_snapshotted(qapp):
    from src.gui.processing_dialogs import ProcessingParametersDialog

    config = {"nested": [1]}
    widget = QWidget()
    dialog = ProcessingParametersDialog(widget, lambda: config)
    spy = QSignalSpy(dialog.apply_requested)

    dialog.apply_changes()
    config["nested"].append(2)
    dialog.apply_changes()

    assert spy.count() == 2


@pytest.mark.parametrize(
    ("factory_name", "getter_name"),
    [
        ("create_noise_dialog", "get_noise_config"),
        ("create_school_dialog", "get_school_config"),
        ("create_integration_dialog", "get_integration_config"),
        ("create_sed_dialog", "get_real_sed_config"),
    ],
)
def test_processing_factories_bind_existing_widget_getters(qapp, factory_name, getter_name):
    import src.gui.processing_dialogs as dialogs

    class ExistingParameters(QWidget):
        pass

    widget = ExistingParameters()
    setattr(widget, getter_name, lambda: {"kind": getter_name})
    dialog = getattr(dialogs, factory_name)(widget)
    spy = QSignalSpy(dialog.apply_requested)

    dialog.apply_changes()

    assert spy.count() == 1
    assert spy.at(0)[0] == {"kind": getter_name}
