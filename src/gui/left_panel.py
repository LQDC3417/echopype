"""左侧面板 — ESP3 风格 Layer 树（调查 / 文件 / 声道 / 快捷操作）

信息架构：Layer 树常驻；1–5 向导按钮墙降级为底部 Ghost 快捷钮（保留 workflow_requested 信号）。
"""

import logging
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGroupBox,
    QGridLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.gui.i18n import T

logger = logging.getLogger(__name__)


class VariableListWidget(QListWidget):
    """变量列表组件"""

    variable_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._variables = {}
        self.currentTextChanged.connect(self._on_selection)

    def add_variable(self, name: str, data, label: str | None = None):
        """添加变量"""
        self._variables[name] = data
        display = label or name
        items = self.findItems(display, Qt.MatchExactly)
        if not items:
            self.addItem(display)
        if self.count() == 1:
            self.setCurrentRow(0)

    def get_variable(self, name: str):
        return self._variables.get(name)

    def clear_variables(self):
        self._variables.clear()
        self.clear()

    def _on_selection(self, text: str):
        if text:
            self.variable_selected.emit(text)

    def get_current_data(self):
        """获取当前选中变量的数据"""
        item = self.currentItem()
        if item:
            return self._variables.get(item.text())
        return None


class LeftPanel(QWidget):
    """左侧导航 — Layer 树（文件/声道）+ 快捷操作。"""

    variable_selected = Signal(str)
    workflow_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(6)
        layout.setContentsMargins(6, 6, 6, 6)

        # ── Layer 树：调查摘要 + 源文件 ──
        layer_group = QGroupBox(T("nav_files"))
        layer_layout = QVBoxLayout(layer_group)
        layer_layout.setContentsMargins(8, 12, 8, 8)
        layer_layout.setSpacing(4)

        self.project_summary = QLabel(T("nav_no_project"))
        self.project_summary.setObjectName("projectSummary")
        self.project_summary.setWordWrap(True)
        layer_layout.addWidget(self.project_summary)

        self.survey_status = QLabel(T("nav_empty_hint"))
        self.survey_status.setObjectName("surveyStatus")
        self.survey_status.setWordWrap(True)
        layer_layout.addWidget(self.survey_status)

        self.file_list = QListWidget()
        self.file_list.setObjectName("surveyFiles")
        self.file_list.setMaximumHeight(140)
        self.file_list.setToolTip(T("nav_files_hint"))
        self.file_list.setTextElideMode(Qt.ElideMiddle)
        self.file_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        layer_layout.addWidget(self.file_list)

        layout.addWidget(layer_group)

        # ── 声道（当前 Layer 的通道）──
        var_group = QGroupBox(T("nav_variables"))
        var_layout = QVBoxLayout()
        var_layout.setSpacing(4)
        var_layout.setContentsMargins(8, 12, 8, 8)
        self.variable_list = VariableListWidget()
        self.variable_list.setObjectName("layerTree")
        self.variable_list.setMinimumHeight(72)
        self.variable_list.variable_selected.connect(self.variable_selected)
        var_layout.addWidget(self.variable_list)
        var_group.setLayout(var_layout)
        layout.addWidget(var_group, 1)

        # ── 快捷操作（Ghost，非向导墙）──
        ops = QGroupBox(T("nav_actions"))
        ops_layout = QGridLayout(ops)
        ops_layout.setContentsMargins(8, 12, 8, 8)
        ops_layout.setSpacing(4)

        self.workflow_buttons = {}
        for index, key in enumerate(("survey", "import", "quality", "region", "integration", "save")):
            button = QPushButton(T(f"nav_action_{key}"))
            button.setObjectName(f"survey_{key}" if key != "survey" else "survey_metadata")
            button.clicked.connect(
                lambda checked=False, action=key: self.workflow_requested.emit(action)
            )
            self.workflow_buttons[key] = button
            ops_layout.addWidget(button, index // 2, index % 2)
        layout.addWidget(ops)

        scroll.setWidget(container)
        main_layout.addWidget(scroll)
        self.update_survey()

    def update_survey(
        self, raw_files=(), config=None, has_data=False, busy=False,
        project_path=None, has_results=False, stale_results=(), status_text="",
    ):
        """刷新 Layer 树与状态；busy 时禁用除导入外的快捷操作。"""
        config = config or {}
        reservoir = config.get("reservoir") or {}
        name = reservoir.get("name") or T("nav_survey")
        self.project_summary.setText(name if has_data else T("nav_no_project"))
        self.project_summary.setToolTip(str(project_path or T("nav_unsaved")))
        self.file_list.clear()
        for index, raw_file in enumerate(raw_files or (), 1):
            path = str(raw_file)
            item = QListWidgetItem(f"{index:02d}  {Path(path).name}")
            item.setToolTip(path)
            item.setData(Qt.ItemDataRole.UserRole, path)
            self.file_list.addItem(item)
        count = self.file_list.count()
        self.file_list.setFixedHeight(min(140, max(32, count * 28 + 4)))
        if busy:
            status = T("nav_busy")
        elif has_data:
            result_status = T("nav_results_ready") if has_results else T("nav_pending")
            if stale_results:
                result_status = T("nav_stale", items="、".join(stale_results))
            status = T("nav_loaded", count=count, status=result_status)
        else:
            status = T("nav_empty_hint")
        self.survey_status.setText(f"{status}\n{status_text}" if status_text else status)
        for key, button in self.workflow_buttons.items():
            button.setEnabled(not busy and (key == "import" or has_data))

    def add_variable(self, name: str, data, label: str | None = None):
        self.variable_list.add_variable(name, data, label)

    def clear_variables(self):
        self.variable_list.clear_variables()

    def get_current_data(self):
        return self.variable_list.get_current_data()
