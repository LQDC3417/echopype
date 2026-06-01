"""右侧属性面板：文件信息 + 处理参数 + 统计结果"""

from PySide6.QtWidgets import (
    QTabWidget, QWidget, QVBoxLayout, QFormLayout,
    QLabel, QSpinBox, QDoubleSpinBox, QPushButton,
    QTableWidget, QTableWidgetItem, QGroupBox, QScrollArea,
)
from PySide6.QtCore import Signal


class FileInfoTab(QWidget):
    """文件信息标签页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QFormLayout(self)
        self.lbl_sonar = QLabel("--")
        self.lbl_freq = QLabel("--")
        self.lbl_pings = QLabel("--")
        self.lbl_samples = QLabel("--")
        self.lbl_time_range = QLabel("--")
        layout.addRow("声呐型号:", self.lbl_sonar)
        layout.addRow("频率:", self.lbl_freq)
        layout.addRow("Ping 数:", self.lbl_pings)
        layout.addRow("采样点数:", self.lbl_samples)
        layout.addRow("时间范围:", self.lbl_time_range)

    def update_info(self, ds_Sv):
        """更新文件信息"""
        if ds_Sv is None:
            return
        if "channel" in ds_Sv:
            self.lbl_freq.setText(str(ds_Sv["channel"].values[0]))
        if "ping_time" in ds_Sv:
            n_pings = len(ds_Sv["ping_time"])
            self.lbl_pings.setText(str(n_pings))
            times = ds_Sv["ping_time"].values
            if len(times) > 1:
                self.lbl_time_range.setText(f"{str(times[0])[:19]} ~ {str(times[-1])[:19]}")
        if "range_sample" in ds_Sv:
            n_samples = len(ds_Sv["range_sample"])
            self.lbl_samples.setText(str(n_samples))


class ProcessingTab(QWidget):
    """处理参数标签页"""

    noise_params_changed = Signal(dict)
    bottom_params_changed = Signal(dict)
    school_params_changed = Signal(dict)
    detect_bottom_clicked = Signal()
    detect_schools_clicked = Signal()
    compute_density_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)

        # --- 噪声去除参数 ---
        noise_group = QGroupBox("噪声去除")
        noise_layout = QFormLayout()
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
        noise_layout.addRow("Range 样本数:", self.spin_range_num)
        noise_layout.addRow("SNR 阈值:", self.spin_snr)
        noise_group.setLayout(noise_layout)
        layout.addWidget(noise_group)

        self.spin_ping_num.valueChanged.connect(self._emit_noise_params)
        self.spin_range_num.valueChanged.connect(self._emit_noise_params)
        self.spin_snr.valueChanged.connect(self._emit_noise_params)

        # --- 底部检测参数 ---
        bottom_group = QGroupBox("底部检测")
        bottom_layout = QFormLayout()
        self.spin_threshold = QDoubleSpinBox()
        self.spin_threshold.setRange(-100, 0)
        self.spin_threshold.setValue(-50.0)
        self.spin_threshold.setSuffix(" dB")
        self.spin_offset = QDoubleSpinBox()
        self.spin_offset.setRange(0, 10)
        self.spin_offset.setValue(0.5)
        self.spin_offset.setSuffix(" m")
        self.spin_bin_skip = QSpinBox()
        self.spin_bin_skip.setRange(0, 1000)
        self.spin_bin_skip.setValue(200)
        self.btn_detect_bottom = QPushButton("重新检测底部")
        bottom_layout.addRow("阈值:", self.spin_threshold)
        bottom_layout.addRow("偏移:", self.spin_offset)
        bottom_layout.addRow("跳过表面样本:", self.spin_bin_skip)
        bottom_layout.addRow(self.btn_detect_bottom)
        bottom_group.setLayout(bottom_layout)
        layout.addWidget(bottom_group)

        self.btn_detect_bottom.clicked.connect(self.detect_bottom_clicked)

        # --- 鱼群检测参数 ---
        school_group = QGroupBox("鱼群检测")
        school_layout = QFormLayout()
        self.spin_school_thr = QDoubleSpinBox()
        self.spin_school_thr.setRange(-100, 0)
        self.spin_school_thr.setValue(-55.0)
        self.spin_school_thr.setSuffix(" dB")
        self.btn_detect_schools = QPushButton("检测鱼群")
        school_layout.addRow("Sv 阈值:", self.spin_school_thr)
        school_layout.addRow(self.btn_detect_schools)
        school_group.setLayout(school_layout)
        layout.addWidget(school_group)

        self.btn_detect_schools.clicked.connect(self.detect_schools_clicked)

        # --- 密度估算 ---
        density_group = QGroupBox("密度估算")
        density_layout = QFormLayout()
        self.spin_ts = QDoubleSpinBox()
        self.spin_ts.setRange(-60, 0)
        self.spin_ts.setValue(-30.0)
        self.spin_ts.setSuffix(" dB")
        self.btn_compute_density = QPushButton("计算密度")
        density_layout.addRow("TS 默认值:", self.spin_ts)
        density_layout.addRow(self.btn_compute_density)
        density_group.setLayout(density_layout)
        layout.addWidget(density_group)

        self.btn_compute_density.clicked.connect(self.compute_density_clicked)

        layout.addStretch()
        scroll.setWidget(container)

        main_layout = QVBoxLayout(self)
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

    def get_bottom_config(self) -> dict:
        return {
            "method": "basic",
            "threshold": self.spin_threshold.value(),
            "offset_m": self.spin_offset.value(),
            "bin_skip_from_surface": self.spin_bin_skip.value(),
        }


class StatsTab(QWidget):
    """统计结果标签页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        # ABC / 密度摘要
        self.lbl_abc = QLabel("ABC: --")
        self.lbl_density = QLabel("密度: --")
        self.lbl_biomass = QLabel("生物量: --")
        layout.addWidget(self.lbl_abc)
        layout.addWidget(self.lbl_density)
        layout.addWidget(self.lbl_biomass)

        # 鱼群列表
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "ID", "Ping 范围", "深度范围", "面积", "平均 Sv", "中心深度"
        ])
        layout.addWidget(self.table)

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
    bottom_params_changed = Signal(dict)
    detect_bottom_clicked = Signal()
    detect_schools_clicked = Signal()
    compute_density_clicked = Signal()

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
        self.processing.detect_bottom_clicked.connect(self.detect_bottom_clicked)
        self.processing.detect_schools_clicked.connect(self.detect_schools_clicked)
        self.processing.compute_density_clicked.connect(self.compute_density_clicked)
