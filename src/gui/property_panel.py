"""右侧属性面板：文件信息 + 处理参数 + 统计结果

设计原则：
- 参数分组清晰，一屏可见
- 数值输入紧凑，标签左对齐
- 结果区域突出显示
"""

from PySide6.QtWidgets import (
    QTabWidget, QWidget, QVBoxLayout, QFormLayout,
    QLabel, QSpinBox, QDoubleSpinBox, QPushButton,
    QTableWidget, QTableWidgetItem, QGroupBox, QScrollArea,
    QHBoxLayout, QFrame, QComboBox,
)
from PySide6.QtCore import Signal, Qt


class _InfoRow(QWidget):
    """信息行：标签 + 值（紧凑布局）"""
    def __init__(self, label: str, value: str = "--"):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.lbl_label = QLabel(label)
        self.lbl_label.setStyleSheet("color: #4a5568; font-size: 11px;")
        self.lbl_label.setFixedWidth(70)

        self.lbl_value = QLabel(value)
        self.lbl_value.setStyleSheet("color: #2c3e50; font-size: 11px;")
        self.lbl_value.setTextInteractionFlags(Qt.TextSelectableByMouse)

        layout.addWidget(self.lbl_label)
        layout.addWidget(self.lbl_value, 1)

    def set_value(self, value: str):
        self.lbl_value.setText(value)


class FileInfoTab(QWidget):
    """文件信息标签页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(8, 8, 8, 8)

        self.row_sonar = _InfoRow("声呐型号")
        self.row_freq = _InfoRow("频率")
        self.row_pings = _InfoRow("Ping 数")
        self.row_samples = _InfoRow("采样点数")
        self.row_time = _InfoRow("时间范围")

        for row in [self.row_sonar, self.row_freq, self.row_pings,
                    self.row_samples, self.row_time]:
            layout.addWidget(row)

        layout.addStretch()

    def update_info(self, ds_Sv):
        """更新文件信息"""
        if ds_Sv is None:
            return
        if "channel" in ds_Sv:
            self.row_freq.set_value(str(ds_Sv["channel"].values[0]))
        if "ping_time" in ds_Sv:
            n_pings = len(ds_Sv["ping_time"])
            self.row_pings.set_value(str(n_pings))
            times = ds_Sv["ping_time"].values
            if len(times) > 1:
                self.row_time.set_value(f"{str(times[0])[:19]} ~ {str(times[-1])[:19]}")
        if "range_sample" in ds_Sv:
            n_samples = len(ds_Sv["range_sample"])
            self.row_samples.set_value(str(n_samples))


class ProcessingTab(QWidget):
    """处理参数标签页"""

    noise_params_changed = Signal(dict)
    surface_line_changed = Signal(float)
    detect_schools_clicked = Signal()
    compute_density_clicked = Signal()
    grid_clicked = Signal()
    stats_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        # ── 噪声去除参数 ──
        noise_group = QGroupBox("噪声去除")
        noise_layout = QFormLayout()
        noise_layout.setSpacing(6)
        noise_layout.setContentsMargins(8, 12, 8, 8)

        self.spin_ping_num = QSpinBox()
        self.spin_ping_num.setRange(1, 100)
        self.spin_ping_num.setValue(5)
        self.spin_range_num = QSpinBox()
        self.spin_range_num.setRange(1, 100)
        self.spin_range_num.setValue(10)
        self.spin_snr = QDoubleSpinBox()
        self.spin_snr.setRange(0, 30)
        self.spin_snr.setValue(3.0)
        self.spin_snr.setSuffix(" dB")

        noise_layout.addRow("Ping 数:", self.spin_ping_num)
        noise_layout.addRow("Range 样本:", self.spin_range_num)
        noise_layout.addRow("SNR 阈值:", self.spin_snr)
        noise_group.setLayout(noise_layout)
        layout.addWidget(noise_group)

        self.spin_ping_num.valueChanged.connect(self._emit_noise_params)
        self.spin_range_num.valueChanged.connect(self._emit_noise_params)
        self.spin_snr.valueChanged.connect(self._emit_noise_params)

        # ── 表线设置 ──
        surface_group = QGroupBox("表线设置")
        surface_layout = QFormLayout()
        surface_layout.setSpacing(6)
        surface_layout.setContentsMargins(8, 12, 8, 8)

        self.spin_surface = QDoubleSpinBox()
        self.spin_surface.setRange(0, 50)
        self.spin_surface.setValue(2.0)
        self.spin_surface.setSuffix(" m")
        self.spin_surface.setToolTip("水面以下多少米绘制表线。分析时仅在表线~底线之间计算。")
        surface_layout.addRow("表线深度:", self.spin_surface)
        surface_group.setLayout(surface_layout)
        layout.addWidget(surface_group)

        self.spin_surface.valueChanged.connect(
            lambda v: self.surface_line_changed.emit(float(v))
        )

        # ── 底部检测参数 ──
        bottom_group = QGroupBox("底部检测")
        bottom_layout = QFormLayout()
        bottom_layout.setSpacing(6)
        bottom_layout.setContentsMargins(8, 12, 8, 8)

        self.spin_bottom_thr = QDoubleSpinBox()
        self.spin_bottom_thr.setRange(-70, -20)
        self.spin_bottom_thr.setValue(-40.0)
        self.spin_bottom_thr.setSuffix(" dB")
        self.spin_bottom_thr.setToolTip("Sv 阈值：低于此值视为底部。推荐 -50 ~ -30 dB")
        bottom_layout.addRow("Sv 阈值:", self.spin_bottom_thr)
        bottom_group.setLayout(bottom_layout)
        layout.addWidget(bottom_group)

        # ── 鱼群检测参数 ──
        school_group = QGroupBox("鱼群检测")
        school_layout = QFormLayout()
        school_layout.setSpacing(6)
        school_layout.setContentsMargins(8, 12, 8, 8)

        self.spin_school_thr = QDoubleSpinBox()
        self.spin_school_thr.setRange(-100, 0)
        self.spin_school_thr.setValue(-55.0)
        self.spin_school_thr.setSuffix(" dB")
        self.btn_detect_schools = QPushButton("检测鱼群")
        self.btn_detect_schools.setProperty("cssClass", "primary")

        school_layout.addRow("Sv 阈值:", self.spin_school_thr)
        school_layout.addRow(self.btn_detect_schools)
        school_group.setLayout(school_layout)
        layout.addWidget(school_group)

        self.btn_detect_schools.clicked.connect(self.detect_schools_clicked)

        # ── 密度估算 ──
        density_group = QGroupBox("密度估算")
        density_layout = QFormLayout()
        density_layout.setSpacing(6)
        density_layout.setContentsMargins(8, 12, 8, 8)

        self.spin_ts = QDoubleSpinBox()
        self.spin_ts.setRange(-70, -20)
        self.spin_ts.setValue(-30.0)
        self.spin_ts.setSuffix(" dB")
        self.spin_avg_weight = QDoubleSpinBox()
        self.spin_avg_weight.setRange(0.001, 100.0)
        self.spin_avg_weight.setValue(0.5)
        self.spin_avg_weight.setSuffix(" kg")
        self.spin_avg_weight.setToolTip("单尾平均体重，用于计算生物量 (kg/ha)")
        self.btn_compute_density = QPushButton("计算密度")
        self.btn_compute_density.setProperty("cssClass", "primary")

        density_layout.addRow("TS 默认值:", self.spin_ts)
        density_layout.addRow("平均体重:", self.spin_avg_weight)
        density_layout.addRow(self.btn_compute_density)
        density_group.setLayout(density_layout)
        layout.addWidget(density_group)

        self.btn_compute_density.clicked.connect(self.compute_density_clicked)

        # ── 网格分析 ──
        grid_group = QGroupBox("网格分析")
        grid_layout = QFormLayout()
        grid_layout.setSpacing(6)
        grid_layout.setContentsMargins(8, 12, 8, 8)

        self.combo_grid_v = QComboBox()
        self.combo_grid_v.addItems(["1m", "2m", "5m"])
        self.combo_grid_v.setCurrentIndex(1)  # 默认 2m
        self.combo_grid_v.setToolTip("垂直间隔")

        self.spin_grid_h = QSpinBox()
        self.spin_grid_h.setRange(1, 10000)
        self.spin_grid_h.setValue(100)
        self.spin_grid_h.setToolTip("水平间隔（ping 数）")

        self.combo_grid_h_method = QComboBox()
        self.combo_grid_h_method.addItems(["Ping", "距离"])
        self.combo_grid_h_method.setToolTip("水平分段方式")

        self.btn_grid = QPushButton("网格分析")
        self.btn_grid.clicked.connect(self.grid_clicked)

        grid_layout.addRow("垂直间隔:", self.combo_grid_v)
        grid_layout.addRow("水平间隔:", self.spin_grid_h)
        grid_layout.addRow("分段方式:", self.combo_grid_h_method)
        grid_layout.addRow(self.btn_grid)
        grid_group.setLayout(grid_layout)
        layout.addWidget(grid_group)

        # ── 统计按钮 ──
        self.btn_stats = QPushButton("统计结果")
        self.btn_stats.clicked.connect(self.stats_clicked)
        layout.addWidget(self.btn_stats)

        layout.addStretch()
        scroll.setWidget(container)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    def _emit_noise_params(self):
        self.noise_params_changed.emit({
            "ping_num": self.spin_ping_num.value(),
            "range_sample_num": self.spin_range_num.value(),
            "SNR_threshold": f"{self.spin_snr.value()}dB",
        })

    def get_noise_config(self) -> dict:
        return {
            "ping_num": self.spin_ping_num.value(),
            "range_sample_num": self.spin_range_num.value(),
            "SNR_threshold": f"{self.spin_snr.value()}dB",
        }

    def get_school_config(self) -> dict:
        return {"thr": self.spin_school_thr.value()}

    def get_bottom_config(self) -> dict:
        return {"threshold": self.spin_bottom_thr.value()}

    def get_density_config(self) -> dict:
        return {
            "ts_default": self.spin_ts.value(),
            "avg_weight_kg": self.spin_avg_weight.value(),
        }

    def get_grid_config(self) -> dict:
        v_text = self.combo_grid_v.currentText()
        v_interval = float(v_text.replace("m", ""))
        h_method = "ping" if self.combo_grid_h_method.currentIndex() == 0 else "distance"
        return {
            "vertical_interval_m": v_interval,
            "horizontal_interval": float(self.spin_grid_h.value()),
            "horizontal_method": h_method,
        }

    def load_from_config(self, config: dict):
        """从配置字典加载参数"""
        proc = config.get("processing", {})
        noise = proc.get("noise_removal", {})
        if "ping_num" in noise:
            self.spin_ping_num.setValue(noise["ping_num"])
        if "range_sample_num" in noise:
            self.spin_range_num.setValue(noise["range_sample_num"])
        if "SNR_threshold" in noise:
            val = float(str(noise["SNR_threshold"]).replace("dB", "").strip())
            self.spin_snr.setValue(val)

        bottom = proc.get("bottom_detection", {})
        if "threshold" in bottom:
            self.spin_bottom_thr.setValue(bottom["threshold"])

        school = config.get("school_detection", {})
        if "thr" in school:
            self.spin_school_thr.setValue(school["thr"])

        density = config.get("density", {})
        surface = config.get("surface_line", {})
        if "depth_m" in surface:
            self.spin_surface.setValue(surface["depth_m"])
        if "ts_default" in density:
            self.spin_ts.setValue(density["ts_default"])
        if "avg_weight_kg" in density:
            self.spin_avg_weight.setValue(density["avg_weight_kg"])


class StatsTab(QWidget):
    """统计结果标签页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        # ── 密度摘要（突出显示）──
        summary_group = QGroupBox("密度摘要")
        summary_layout = QVBoxLayout()
        summary_layout.setContentsMargins(8, 12, 8, 8)

        self.lbl_abc = QLabel("ABC: --")
        self.lbl_abc.setStyleSheet("font-size: 13px; font-weight: bold; color: #2f855a;")
        self.lbl_density = QLabel("密度: --")
        self.lbl_density.setStyleSheet("font-size: 13px; font-weight: bold; color: #1a73e8;")
        self.lbl_biomass = QLabel("生物量: --")
        self.lbl_biomass.setStyleSheet("font-size: 13px; font-weight: bold; color: #c05621;")

        summary_layout.addWidget(self.lbl_abc)
        summary_layout.addWidget(self.lbl_density)
        summary_layout.addWidget(self.lbl_biomass)
        summary_group.setLayout(summary_layout)
        layout.addWidget(summary_group)

        # ── 鱼群列表 ──
        schools_group = QGroupBox("鱼群列表")
        schools_layout = QVBoxLayout()
        schools_layout.setContentsMargins(8, 12, 8, 8)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "ID", "Ping 范围", "深度范围", "面积", "平均 Sv", "中心深度"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.verticalHeader().setVisible(False)

        schools_layout.addWidget(self.table)
        schools_group.setLayout(schools_layout)
        layout.addWidget(schools_group, 1)

    def update_density(self, density_df):
        """更新密度统计"""
        if density_df is None or density_df.empty:
            return
        row = density_df.iloc[0]
        self.lbl_abc.setText(f"ABC: {row.get('abc', 0):.6f} m²/m²")
        self.lbl_density.setText(f"密度: {row.get('density_ind_ha', 0):.2f} ind/ha")
        self.lbl_biomass.setText(f"生物量: {row.get('total_biomass_kg_ha', 0):.2f} kg/ha")

    def update_schools(self, schools_df):
        """更新鱼群列表"""
        if schools_df is None or schools_df.empty:
            self.table.setRowCount(0)
            return
        self.table.setRowCount(len(schools_df))
        for i, (_, row) in enumerate(schools_df.iterrows()):
            self.table.setItem(i, 0, QTableWidgetItem(str(row.get("school_id", ""))))
            self.table.setItem(i, 1, QTableWidgetItem(
                f"{row.get('ping_start', '')} ~ {row.get('ping_end', '')}"))
            self.table.setItem(i, 2, QTableWidgetItem(
                f"{row.get('depth_start', 0):.1f} ~ {row.get('depth_end', 0):.1f} m"))
            self.table.setItem(i, 3, QTableWidgetItem(f"{row.get('area', 0):.1f}"))
            self.table.setItem(i, 4, QTableWidgetItem(f"{row.get('mean_sv', 0):.1f} dB"))
            self.table.setItem(i, 5, QTableWidgetItem(f"{row.get('centroid_depth', 0):.1f} m"))


class PropertyPanel(QTabWidget):
    """右侧属性面板"""

    noise_params_changed = Signal(dict)
    surface_line_changed = Signal(float)
    detect_schools_clicked = Signal()
    compute_density_clicked = Signal()
    grid_clicked = Signal()
    stats_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.file_info = FileInfoTab()
        self.processing = ProcessingTab()
        self.stats = StatsTab()

        self.addTab(self.file_info, "文件信息")
        self.addTab(self.processing, "处理参数")
        self.addTab(self.stats, "统计结果")

        # 转发信号
        self.processing.noise_params_changed.connect(self.noise_params_changed)
        self.processing.surface_line_changed.connect(self.surface_line_changed)
        self.processing.detect_schools_clicked.connect(self.detect_schools_clicked)
        self.processing.compute_density_clicked.connect(self.compute_density_clicked)
        self.processing.grid_clicked.connect(self.grid_clicked)
        self.processing.stats_clicked.connect(self.stats_clicked)
