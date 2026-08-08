"""右侧属性面板：文件信息 + 处理参数 + 统计结果

设计原则：
- 参数分组清晰，一屏可见
- 数值输入紧凑，标签左对齐
- 结果区域突出显示
- 网格配置增强：统计指标选择、输出格式、输入验证
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


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
        """设置值并更新样式"""
        self.lbl_value.setText(value)
        # 如果值为空或默认值，使用灰色
        if value in ["--", "无数据", ""]:
            self.lbl_value.setStyleSheet("color: #a0aec0; font-size: 11px;")
        else:
            self.lbl_value.setStyleSheet("color: #2c3e50; font-size: 11px;")


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
    quality_check_clicked = Signal()
    multifreq_clicked = Signal()
    single_target_clicked = Signal()
    sv_stats_clicked = Signal()
    transect_split_clicked = Signal()
    # ??????
    detect_bottom_clicked = Signal()
    draw_bottom_clicked = Signal()
    update_bottom_clicked = Signal()

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
        self.spin_ping_num.setToolTip("用于计算背景噪声的 ping 数量\n推荐值: 5-20")

        self.spin_range_num = QSpinBox()
        self.spin_range_num.setRange(1, 100)
        self.spin_range_num.setValue(10)
        self.spin_range_num.setToolTip("用于计算背景噪声的 range 样本数\n推荐值: 10-50")

        self.spin_snr = QDoubleSpinBox()
        self.spin_snr.setRange(0, 30)
        self.spin_snr.setValue(3.0)
        self.spin_snr.setSuffix(" dB")
        self.spin_snr.setToolTip("信噪比阈值\n低于此阈值的信号将被去除\n推荐值: 2-5 dB")

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
        self.spin_surface.setToolTip("水面以下多少米绘制表线。分析时仅在表线~底线之间计算。\n推荐值: 1-10 米")
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
        self.spin_bottom_thr.setToolTip("Sv 阈值：低于此值视为底部\n推荐范围: -50 ~ -30 dB\n过大值可能误判，过小值可能漏检")
        bottom_layout.addRow("Sv 阈值:", self.spin_bottom_thr)
        # 底部检测按钮
        self.btn_detect_bottom = QPushButton("检测底部")
        self.btn_detect_bottom.setProperty("cssClass", "primary")
        self.btn_detect_bottom.setToolTip("点击开始底部检测\n需要先完成噪声去除")

        self.btn_draw_bottom = QPushButton("绘制底线")
        self.btn_draw_bottom.setToolTip("切换到底线绘制模式\n手动绘制或修改底线")

        self.btn_update_bottom = QPushButton("更新底线")
        self.btn_update_bottom.setToolTip("保存当前编辑的底线\n更新底线数据")

        # 按钮布局
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.btn_detect_bottom)
        btn_layout.addWidget(self.btn_draw_bottom)
        btn_layout.addWidget(self.btn_update_bottom)
        bottom_layout.addRow(btn_layout)

        self.btn_detect_bottom.clicked.connect(self.detect_bottom_clicked)
        self.btn_draw_bottom.clicked.connect(self.draw_bottom_clicked)
        self.btn_update_bottom.clicked.connect(self.update_bottom_clicked)

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
        self.spin_school_thr.setToolTip("鱼群检测的 Sv 阈值\n高于此值的区域将被视为鱼群\n推荐范围: -60 ~ -45 dB")

        self.btn_detect_schools = QPushButton("检测鱼群")
        self.btn_detect_schools.setProperty("cssClass", "primary")
        self.btn_detect_schools.setToolTip("点击开始鱼群检测\n需要先完成噪声去除和底部检测")

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
        self.spin_ts.setToolTip("目标强度 (Target Strength) 默认值\n用于将 Sv 转换为密度\n推荐值: -30 ~ -25 dB")

        self.spin_avg_weight = QDoubleSpinBox()
        self.spin_avg_weight.setRange(0.001, 100.0)
        self.spin_avg_weight.setValue(0.5)
        self.spin_avg_weight.setSuffix(" kg")
        self.spin_avg_weight.setToolTip("单尾平均体重，用于计算生物量 (kg/ha)\n推荐值: 0.1-10 kg")

        self.btn_compute_density = QPushButton("计算密度")
        self.btn_compute_density.setProperty("cssClass", "primary")
        self.btn_compute_density.setToolTip("点击开始密度计算\n需要先完成鱼群检测")

        density_layout.addRow("TS 默认值:", self.spin_ts)
        density_layout.addRow("平均体重:", self.spin_avg_weight)
        density_layout.addRow(self.btn_compute_density)
        density_group.setLayout(density_layout)
        layout.addWidget(density_group)

        self.btn_compute_density.clicked.connect(self.compute_density_clicked)

        # ── 网格分析（增强版）──
        grid_group = QGroupBox("网格分析")
        grid_layout = QVBoxLayout()
        grid_layout.setSpacing(8)
        grid_layout.setContentsMargins(8, 12, 8, 8)

        # 网格参数网格布局
        grid_params_layout = QGridLayout()
        grid_params_layout.setSpacing(6)

        # 垂直间隔
        lbl_v_interval = QLabel("垂直间隔:")
        lbl_v_interval.setToolTip("深度方向的网格划分间隔\n间隔越小，分辨率越高，但计算量越大")
        self.combo_grid_v = QComboBox()
        self.combo_grid_v.addItems(["0.5m", "1m", "2m", "5m", "10m"])
        self.combo_grid_v.setCurrentIndex(2)  # 默认 2m
        self.combo_grid_v.setToolTip("垂直间隔选项\n推荐值: 1-5m")
        grid_params_layout.addWidget(lbl_v_interval, 0, 0)
        grid_params_layout.addWidget(self.combo_grid_v, 0, 1)

        # 水平间隔
        lbl_h_interval = QLabel("水平间隔:")
        lbl_h_interval.setToolTip("水平方向的网格划分间隔\n间隔越小，分辨率越高，但计算量越大")
        self.spin_grid_h = QSpinBox()
        self.spin_grid_h.setRange(1, 10000)
        self.spin_grid_h.setValue(100)
        self.spin_grid_h.setToolTip("水平间隔（ping 数或距离）\n推荐值: 50-500")
        grid_params_layout.addWidget(lbl_h_interval, 1, 0)
        grid_params_layout.addWidget(self.spin_grid_h, 1, 1)

        # 水平分段方式
        lbl_h_method = QLabel("分段方式:")
        lbl_h_method.setToolTip("水平方向的分段方式\nPing: 按固定 ping 数分段\n距离: 按 GPS 航行距离分段")
        self.combo_grid_h_method = QComboBox()
        self.combo_grid_h_method.addItems(["Ping", "距离"])
        self.combo_grid_h_method.setToolTip("水平分段方式\nPing: 按固定 ping 数分段\n距离: 按 GPS 航行距离分段")
        grid_params_layout.addWidget(lbl_h_method, 2, 0)
        grid_params_layout.addWidget(self.combo_grid_h_method, 2, 1)

        # 距离单位（仅当选择距离方式时启用）
        lbl_distance_unit = QLabel("距离单位:")
        lbl_distance_unit.setToolTip("距离分段时的单位")
        self.combo_distance_unit = QComboBox()
        self.combo_distance_unit.addItems(["米 (m)", "公里 (km)", "海里 (nm)"])
        self.combo_distance_unit.setToolTip("距离分段时的单位\n米: 米\n公里: 千米\n海里: 海里")
        self.combo_distance_unit.setEnabled(False)
        grid_params_layout.addWidget(lbl_distance_unit, 3, 0)
        grid_params_layout.addWidget(self.combo_distance_unit, 3, 1)

        grid_layout.addLayout(grid_params_layout)

        # 统计指标选择
        stats_group = QGroupBox("统计指标")
        stats_layout = QVBoxLayout()
        stats_layout.setSpacing(4)
        stats_layout.setContentsMargins(8, 12, 8, 8)

        self.chk_mean_sv = QCheckBox("平均 Sv")
        self.chk_mean_sv.setChecked(True)
        self.chk_mean_sv.setToolTip("计算网格内的平均体积反向散射强度")

        self.chk_abc = QCheckBox("ABC (面积背散射系数)")
        self.chk_abc.setChecked(True)
        self.chk_abc.setToolTip("计算面积背散射系数")

        self.chk_density = QCheckBox("密度 (ind/ha)")
        self.chk_density.setChecked(True)
        self.chk_density.setToolTip("计算每公顷个体密度")

        self.chk_biomass = QCheckBox("生物量 (kg/ha)")
        self.chk_biomass.setChecked(True)
        self.chk_biomass.setToolTip("计算每公顷生物量")

        self.chk_valid_pixels = QCheckBox("有效像素数")
        self.chk_valid_pixels.setChecked(True)
        self.chk_valid_pixels.setToolTip("计算网格内的有效像素数量")

        stats_layout.addWidget(self.chk_mean_sv)
        stats_layout.addWidget(self.chk_abc)
        stats_layout.addWidget(self.chk_density)
        stats_layout.addWidget(self.chk_biomass)
        stats_layout.addWidget(self.chk_valid_pixels)
        stats_group.setLayout(stats_layout)
        grid_layout.addWidget(stats_group)

        # 输出格式选择
        output_group = QGroupBox("输出设置")
        output_layout = QFormLayout()
        output_layout.setSpacing(6)
        output_layout.setContentsMargins(8, 12, 8, 8)

        self.combo_output_format = QComboBox()
        self.combo_output_format.addItems(["DataFrame", "CSV", "Excel", "JSON"])
        self.combo_output_format.setToolTip("网格统计结果的输出格式\nDataFrame: 内存中的数据框\nCSV: 逗号分隔值文件\nExcel: Excel 文件\nJSON: JSON 格式")

        self.chk_include_metadata = QCheckBox("包含元数据")
        self.chk_include_metadata.setChecked(True)
        self.chk_include_metadata.setToolTip("在输出中包含网格配置信息和统计参数")

        self.chk_include_summary = QCheckBox("包含摘要统计")
        self.chk_include_summary.setChecked(True)
        self.chk_include_summary.setToolTip("在输出中包含整体摘要统计信息")

        output_layout.addRow("输出格式:", self.combo_output_format)
        output_layout.addRow(self.chk_include_metadata)
        output_layout.addRow(self.chk_include_summary)
        output_group.setLayout(output_layout)
        grid_layout.addWidget(output_group)

        # 网格分析按钮
        self.btn_grid = QPushButton("网格分析")
        self.btn_grid.setProperty("cssClass", "primary")
        self.btn_grid.setToolTip("点击开始网格分析\n需要先完成噪声去除和底部检测")
        self.btn_grid.clicked.connect(self._on_grid_clicked)

        # 统计结果按钮
        self.btn_stats = QPushButton("统计结果")
        self.btn_stats.setToolTip("查看详细的统计结果\n包括网格统计、鱼群统计等")

        # 按钮布局
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.btn_grid)
        btn_layout.addWidget(self.btn_stats)
        grid_layout.addLayout(btn_layout)

        grid_group.setLayout(grid_layout)
        layout.addWidget(grid_group)

        # 连接信号
        self.combo_grid_h_method.currentIndexChanged.connect(self._on_h_method_changed)
        self.btn_stats.clicked.connect(self.stats_clicked)

        # ── 质量检查 ──
        self.btn_quality = QPushButton("🔍 数据质量检查")
        self.btn_quality.setToolTip("检查 Sv 数据和底线的质量\n验证数据完整性和合理性")
        self.btn_quality.clicked.connect(self.quality_check_clicked)

        # ── 多频分析 ──
        self.btn_multifreq = QPushButton("📊 多频分析")
        self.btn_multifreq.setToolTip("多频率通道信息和对比分析\n需要数据包含多个通道")
        self.btn_multifreq.clicked.connect(self.multifreq_clicked)

        # ── 单体目标检测 ──
        self.btn_single_target = QPushButton("🎯 单体目标检测")
        self.btn_single_target.setToolTip("检测水体中单个鱼类目标\n估算目标强度（TS）")
        self.btn_single_target.clicked.connect(self.single_target_clicked)

        btn_layout2 = QHBoxLayout()
        btn_layout2.addWidget(self.btn_quality)
        btn_layout2.addWidget(self.btn_multifreq)
        layout.addLayout(btn_layout2)

        btn_layout3 = QHBoxLayout()
        btn_layout3.addWidget(self.btn_single_target)
        layout.addLayout(btn_layout3)

        # ── Sv 统计摘要 ──
        self.btn_sv_stats = QPushButton("📈 Sv 统计摘要")
        self.btn_sv_stats.setToolTip("按 transect 统计 Sv 均值/中位/分位数/NaN 比例")
        self.btn_sv_stats.clicked.connect(self.sv_stats_clicked)

        # ── Transect 分段 ──
        self.btn_transect = QPushButton("✂ Transect 分段")
        self.btn_transect.setToolTip("按时间间隔或固定 ping 数分割 transect")
        self.btn_transect.clicked.connect(self.transect_split_clicked)

        btn_layout4 = QHBoxLayout()
        btn_layout4.addWidget(self.btn_sv_stats)
        btn_layout4.addWidget(self.btn_transect)
        layout.addLayout(btn_layout4)

        layout.addStretch()
        scroll.setWidget(container)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    def _on_h_method_changed(self, index):
        """水平分段方式改变时更新距离单位的启用状态"""
        self.combo_distance_unit.setEnabled(index == 1)

    def _on_grid_clicked(self):
        """网格分析按钮点击时进行输入验证"""
        # 验证垂直间隔
        v_text = self.combo_grid_v.currentText()
        try:
            v_interval = float(v_text.replace("m", ""))
            if v_interval <= 0:
                QMessageBox.warning(self, "输入错误", "垂直间隔必须大于0")
                return
        except ValueError:
            QMessageBox.warning(self, "输入错误", "垂直间隔格式错误")
            return

        # 验证水平间隔
        h_interval = self.spin_grid_h.value()
        if h_interval <= 0:
            QMessageBox.warning(self, "输入错误", "水平间隔必须大于0")
            return

        # 验证统计指标至少选择一个
        if not (self.chk_mean_sv.isChecked() or self.chk_abc.isChecked() or 
                self.chk_density.isChecked() or self.chk_biomass.isChecked() or 
                self.chk_valid_pixels.isChecked()):
            QMessageBox.warning(self, "输入错误", "请至少选择一个统计指标")
            return

        # 验证通过，发射信号
        self.grid_clicked.emit()

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
        """获取网格配置（增强版）"""
        v_text = self.combo_grid_v.currentText()
        v_interval = float(v_text.replace("m", ""))
        h_method = "ping" if self.combo_grid_h_method.currentIndex() == 0 else "distance"
        
        # 获取选中的统计指标
        selected_metrics = []
        if self.chk_mean_sv.isChecked():
            selected_metrics.append("mean_sv")
        if self.chk_abc.isChecked():
            selected_metrics.append("abc")
        if self.chk_density.isChecked():
            selected_metrics.append("density")
        if self.chk_biomass.isChecked():
            selected_metrics.append("biomass")
        if self.chk_valid_pixels.isChecked():
            selected_metrics.append("valid_pixels")
        
        return {
            "vertical_interval_m": v_interval,
            "horizontal_interval": float(self.spin_grid_h.value()),
            "horizontal_method": h_method,
            "distance_unit": self.combo_distance_unit.currentText() if h_method == "distance" else None,
            "selected_metrics": selected_metrics,
            "output_format": self.combo_output_format.currentText(),
            "include_metadata": self.chk_include_metadata.isChecked(),
            "include_summary": self.chk_include_summary.isChecked(),
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
    quality_check_clicked = Signal()
    multifreq_clicked = Signal()
    single_target_clicked = Signal()
    sv_stats_clicked = Signal()
    transect_split_clicked = Signal()
    # ??????
    detect_bottom_clicked = Signal()
    draw_bottom_clicked = Signal()
    update_bottom_clicked = Signal()

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
        self.processing.detect_bottom_clicked.connect(self.detect_bottom_clicked)
        self.processing.draw_bottom_clicked.connect(self.draw_bottom_clicked)
        self.processing.update_bottom_clicked.connect(self.update_bottom_clicked)
        self.processing.quality_check_clicked.connect(self.quality_check_clicked)
        self.processing.multifreq_clicked.connect(self.multifreq_clicked)
        self.processing.single_target_clicked.connect(self.single_target_clicked)
        self.processing.sv_stats_clicked.connect(self.sv_stats_clicked)
        self.processing.transect_split_clicked.connect(self.transect_split_clicked)
