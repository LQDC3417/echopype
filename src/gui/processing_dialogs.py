"""可复用的处理参数弹窗。"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

ConfigGetter = Callable[[], Mapping[str, Any]]


class ProcessingParametersDialog(QDialog):
    """包装参数 QWidget，并只在用户确认应用时发出配置。"""

    apply_requested = Signal(dict)

    def __init__(
        self,
        parameter_widget: QWidget,
        config_getter: ConfigGetter,
        *,
        title: str = "处理参数",
        last_applied_config: Mapping[str, Any] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.parameter_widget = parameter_widget
        self._config_getter = config_getter
        self._last_applied_config = (
            deepcopy(dict(last_applied_config)) if last_applied_config is not None else None
        )
        self._last_applied_widget_state = self._snapshot_widget_state()

        self.setWindowTitle(title)
        layout = QVBoxLayout(self)
        layout.addWidget(parameter_widget)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Cancel
        )
        layout.addWidget(self.button_box)

        apply_button = self.button_box.button(QDialogButtonBox.StandardButton.Apply)
        apply_button.clicked.connect(self.apply_changes)
        self.button_box.accepted.connect(self._accept_with_pending_changes)
        self.button_box.rejected.connect(self._reject_without_pending_changes)

    def _snapshot_widget_state(self) -> list[tuple[QWidget, object]]:
        """保存参数控件状态，供取消时恢复尚未应用的修改。"""
        state = []
        for widget in self.parameter_widget.findChildren(QWidget):
            value = None
            if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                value = widget.value()
            elif isinstance(widget, QComboBox):
                value = widget.currentIndex()
            elif isinstance(widget, QLineEdit):
                value = widget.text()
            if value is not None:
                state.append((widget, value))
        return state

    def _restore_widget_state(self) -> None:
        for widget, value in self._last_applied_widget_state:
            signals_blocked = widget.blockSignals(True)
            try:
                if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                    widget.setValue(value)
                elif isinstance(widget, QComboBox):
                    widget.setCurrentIndex(value)
                elif isinstance(widget, QLineEdit):
                    widget.setText(value)
            finally:
                widget.blockSignals(signals_blocked)

    def current_config(self) -> dict[str, Any]:
        """读取参数控件的当前配置并返回独立副本。"""
        return deepcopy(dict(self._config_getter()))

    @property
    def last_applied_config(self) -> dict[str, Any] | None:
        """返回最近一次执行配置的副本。"""
        if self._last_applied_config is None:
            return None
        return deepcopy(self._last_applied_config)

    def apply_changes(self) -> bool:
        """仅当配置相对上次执行发生变化时发出请求。"""
        config = self.current_config()
        if config == self._last_applied_config:
            return False

        self._last_applied_config = deepcopy(config)
        self._last_applied_widget_state = self._snapshot_widget_state()
        self.apply_requested.emit(deepcopy(config))
        return True

    def _accept_with_pending_changes(self) -> None:
        self.apply_changes()
        self.accept()

    def _reject_without_pending_changes(self) -> None:
        self._restore_widget_state()
        self.reject()


def _create_processing_dialog(
    parameter_widget: QWidget,
    getter_name: str,
    title: str,
    *,
    last_applied_config: Mapping[str, Any] | None = None,
    parent: QWidget | None = None,
) -> ProcessingParametersDialog:
    getter = getattr(parameter_widget, getter_name)
    return ProcessingParametersDialog(
        parameter_widget,
        getter,
        title=title,
        last_applied_config=last_applied_config,
        parent=parent,
    )

def create_noise_dialog(
    parameter_widget: QWidget,
    *,
    last_applied_config: Mapping[str, Any] | None = None,
    parent: QWidget | None = None,
) -> ProcessingParametersDialog:
    """创建绑定 ``get_noise_config`` 的噪声参数弹窗。"""
    return _create_processing_dialog(
        parameter_widget,
        "get_noise_config",
        "噪声去除参数",
        last_applied_config=last_applied_config,
        parent=parent,
    )


def create_school_dialog(
    parameter_widget: QWidget,
    *,
    last_applied_config: Mapping[str, Any] | None = None,
    parent: QWidget | None = None,
) -> ProcessingParametersDialog:
    """创建绑定 ``get_school_config`` 的鱼群参数弹窗。"""
    return _create_processing_dialog(
        parameter_widget,
        "get_school_config",
        "鱼群检测参数",
        last_applied_config=last_applied_config,
        parent=parent,
    )


def create_integration_dialog(
    parameter_widget: QWidget,
    *,
    last_applied_config: Mapping[str, Any] | None = None,
    parent: QWidget | None = None,
) -> ProcessingParametersDialog:
    """创建绑定 ``get_integration_config`` 的积分参数弹窗。"""
    return _create_processing_dialog(
        parameter_widget,
        "get_integration_config",
        "回声积分参数",
        last_applied_config=last_applied_config,
        parent=parent,
    )


def create_sed_dialog(
    parameter_widget: QWidget,
    *,
    last_applied_config: Mapping[str, Any] | None = None,
    parent: QWidget | None = None,
) -> ProcessingParametersDialog:
    """创建绑定 ``get_real_sed_config`` 的 SED 参数弹窗。"""
    return _create_processing_dialog(
        parameter_widget,
        "get_real_sed_config",
        "SED 单体目标检测参数",
        last_applied_config=last_applied_config,
        parent=parent,
    )
