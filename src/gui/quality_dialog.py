"""数据质量检查结果展示对话框

功能：
- 显示 Sv 数据质量检查结果（值范围、数据尺寸、NaN 比例）
- 显示底线质量检查结果（可选）
- 警告列表展示
- 整体状态指示（通过/警告/失败）
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
)


class QualityDialog(QDialog):
    """数据质量检查结果对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("数据质量检查")
        self.setMinimumSize(500, 350)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint)

        # 存储检查结果
        self._sv_result = None
        self._bottom_result = None

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(14, 14, 14, 14)

        # ── 顶部整体状态 ──
        self._setup_status_bar()
        layout.addWidget(self.status_frame)

        # ── Sv 数据质量区域 ──
        self._setup_sv_section()
        layout.addWidget(self.sv_group)

        # ── 底线质量区域（可选） ──
        self._setup_bottom_section()
        layout.addWidget(self.bottom_group)
        self.bottom_group.setVisible(False)

        # ── 警告列表 ──
        self._setup_warnings_section()
        layout.addWidget(self.warnings_group)

        # ── 底部按钮 ──
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_close = QPushButton("关闭")
        self.btn_close.setFixedWidth(80)
        self.btn_close.clicked.connect(self.close)
        btn_layout.addWidget(self.btn_close)
        layout.addLayout(btn_layout)

    def _setup_status_bar(self):
        """设置顶部状态栏"""
        self.status_frame = QLabel()
        self.status_frame.setAlignment(Qt.AlignCenter)
        self.status_frame.setFixedHeight(48)
        self.status_frame.setStyleSheet(
            "font-size: 16px; font-weight: bold; border-radius: 6px; padding: 6px;"
        )
        # 默认等待状态
        self._set_status("等待检查...", "#718096", "#EDF2F7")

    def _set_status(self, text, text_color, bg_color):
        """设置状态栏样式"""
        self.status_frame.setText(text)
        self.status_frame.setStyleSheet(
            f"font-size: 16px; font-weight: bold; color: {text_color}; "
            f"background: {bg_color}; border-radius: 6px; padding: 6px;"
        )

    def _setup_sv_section(self):
        """设置 Sv 数据质量区域"""
        self.sv_group = QGroupBox("Sv 数据质量")
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 14, 10, 10)
        layout.setSpacing(6)

        # 值范围
        row_range = QHBoxLayout()
        row_range.addWidget(QLabel("Sv 值范围:"))
        self.lbl_sv_range = QLabel("--")
        self.lbl_sv_range.setStyleSheet("font-weight: bold; color: #2b6cb0;")
        row_range.addWidget(self.lbl_sv_range)
        row_range.addStretch()
        layout.addLayout(row_range)

        # 数据尺寸
        row_size = QHBoxLayout()
        row_size.addWidget(QLabel("数据尺寸:"))
        self.lbl_data_size = QLabel("--")
        self.lbl_data_size.setStyleSheet("font-weight: bold; color: #2b6cb0;")
        row_size.addWidget(self.lbl_data_size)
        row_size.addStretch()
        layout.addLayout(row_size)

        # NaN 比例
        row_nan = QHBoxLayout()
        row_nan.addWidget(QLabel("NaN 比例:"))
        self.lbl_nan_ratio = QLabel("--")
        self.lbl_nan_ratio.setStyleSheet("font-weight: bold; color: #2b6cb0;")
        row_nan.addWidget(self.lbl_nan_ratio)
        row_nan.addStretch()
        layout.addLayout(row_nan)

        self.sv_group.setLayout(layout)

    def _setup_bottom_section(self):
        """设置底线质量区域"""
        self.bottom_group = QGroupBox("底线质量")
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 14, 10, 10)
        layout.setSpacing(6)

        # 有效 ping 数
        row_pings = QHBoxLayout()
        row_pings.addWidget(QLabel("有效 Ping 数:"))
        self.lbl_valid_pings = QLabel("--")
        self.lbl_valid_pings.setStyleSheet("font-weight: bold; color: #2b6cb0;")
        row_pings.addWidget(self.lbl_valid_pings)
        row_pings.addStretch()
        layout.addLayout(row_pings)

        # NaN 比例
        row_nan = QHBoxLayout()
        row_nan.addWidget(QLabel("NaN 比例:"))
        self.lbl_bottom_nan = QLabel("--")
        self.lbl_bottom_nan.setStyleSheet("font-weight: bold; color: #2b6cb0;")
        row_nan.addWidget(self.lbl_bottom_nan)
        row_nan.addStretch()
        layout.addLayout(row_nan)

        self.bottom_group.setLayout(layout)

    def _setup_warnings_section(self):
        """设置警告列表区域"""
        self.warnings_group = QGroupBox("警告列表")
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 14, 10, 10)

        self.warnings_list = QListWidget()
        self.warnings_list.setStyleSheet(
            "QListWidget { background: #FFF5F5; border: 1px solid #FEB2B2; "
            "border-radius: 4px; padding: 4px; }"
            "QListWidget::item { padding: 3px 0; }"
        )
        layout.addWidget(self.warnings_list)

        # 无警告时的提示
        self.lbl_no_warnings = QLabel("所有检查通过，无警告")
        self.lbl_no_warnings.setAlignment(Qt.AlignCenter)
        self.lbl_no_warnings.setStyleSheet("color: #38A169; font-style: italic;")
        self.lbl_no_warnings.setVisible(False)
        layout.addWidget(self.lbl_no_warnings)

        self.warnings_group.setLayout(layout)

    def load_results(self, sv_result, bottom_result=None):
        """加载质量检查结果并更新界面

        Parameters
        ----------
        sv_result : dict
            check_sv_quality() 返回的结果
        bottom_result : dict, optional
            check_bottom_line() 返回的结果
        """
        self._sv_result = sv_result
        self._bottom_result = bottom_result

        # 更新 Sv 数据质量
        self._update_sv_section(sv_result)

        # 更新底线质量
        if bottom_result is not None:
            self._update_bottom_section(bottom_result)
            self.bottom_group.setVisible(True)

        # 更新警告列表
        self._update_warnings(sv_result, bottom_result)

        # 更新整体状态
        self._update_overall_status(sv_result, bottom_result)

    def _update_sv_section(self, result):
        """更新 Sv 数据质量显示"""
        sv_min, sv_max = result.get("sv_range", (float("nan"), float("nan")))
        self.lbl_sv_range.setText(f"[{sv_min:.1f}, {sv_max:.1f}] dB")

        n_pings = result.get("total_pings", 0)
        n_samples = result.get("total_samples", 0)
        self.lbl_data_size.setText(f"{n_pings} pings × {n_samples} samples")

        nan_ratio = result.get("nan_ratio", 0.0)
        self.lbl_nan_ratio.setText(f"{nan_ratio:.1%}")

        # NaN 比例过高时变红警告
        if nan_ratio > 0.5:
            self.lbl_nan_ratio.setStyleSheet("font-weight: bold; color: #E53E3E;")

    def _update_bottom_section(self, result):
        """更新底线质量显示"""
        valid_pings = result.get("valid_pings", 0)
        total_pings = self._sv_result.get("total_pings", 0) if self._sv_result else 0
        self.lbl_valid_pings.setText(f"{valid_pings} / {total_pings}")

        nan_ratio = result.get("nan_ratio", 0.0)
        self.lbl_bottom_nan.setText(f"{nan_ratio:.1%}")

        if nan_ratio > 0.3:
            self.lbl_bottom_nan.setStyleSheet("font-weight: bold; color: #E53E3E;")

    def _update_warnings(self, sv_result, bottom_result):
        """更新警告列表"""
        all_warnings = []
        all_warnings.extend(sv_result.get("warnings", []))
        if bottom_result is not None:
            all_warnings.extend(bottom_result.get("warnings", []))

        self.warnings_list.clear()
        if all_warnings:
            for w in all_warnings:
                self.warnings_list.addItem(f"⚠ {w}")
            self.lbl_no_warnings.setVisible(False)
            self.warnings_list.setVisible(True)
        else:
            self.lbl_no_warnings.setVisible(True)
            self.warnings_list.setVisible(False)

    def _update_overall_status(self, sv_result, bottom_result):
        """根据检查结果更新整体状态"""
        sv_valid = sv_result.get("valid", False)
        has_sv_warnings = bool(sv_result.get("warnings", []))

        bottom_valid = True
        has_bottom_warnings = False
        if bottom_result is not None:
            bottom_valid = bottom_result.get("valid", False)
            has_bottom_warnings = bool(bottom_result.get("warnings", []))

        # 判定整体状态
        if not sv_valid or not bottom_valid:
            self._set_status("✕ 检查失败", "#9B2C2C", "#FFF5F5")
        elif has_sv_warnings or has_bottom_warnings:
            self._set_status("⚠ 存在警告", "#975A16", "#FFFFF0")
        else:
            self._set_status("✓ 检查通过", "#276749", "#F0FFF4")
