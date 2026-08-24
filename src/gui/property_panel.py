"""右侧属性面板：文件信息 + 处理参数 + 统计结果

设计原则：
- 中文为默认语言，可切换英文
- 参数分组清晰，一屏可见
- 数值输入紧凑，标签左对齐
- 结果区域突出显示
- 网格配置增强：统计指标选择、输出格式、输入验证
- 支持预设配置加载
- 参照 Echoview 右侧 Properties 面板
"""

from pathlib import Path

import yaml
from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
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

from src.gui.i18n import T

# 预设配置文件路径
PRESETS_FILE = Path(__file__).parent.parent.parent / "configs" / "presets.yaml"


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
        no_data_values = ["--", T("info_no_data"), ""]
        if value in no_data_values:
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

        self.row_sonar = _InfoRow(T("info_sonar_model"))
        self.row_freq = _InfoRow(T("info_frequency"))
        self.row_pings = _InfoRow(T("info_pings"))
        self.row_samples = _InfoRow(T("info_samples"))
        self.row_time = _InfoRow(T("info_time_range"))

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
    stats_clicked = Signal()
    quality_check_clicked = Signal()
    multifreq_clicked = Signal()
    sv_stats_clicked = Signal()
    transect_split_clicked = Signal()
    integration_clicked = Signal()
    real_sed_clicked = Signal()
    detect_bottom_clicked = Signal()
    draw_bottom_clicked = Signal()
    update_bottom_clicked = Signal()
    apply_all_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._presets = self._load_presets()
        self._settings = QSettings("Echopype", "FishAcoustics")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        # ── 预设配置 ──
        preset_group = QGroupBox(T("preset_group"))
        preset_layout = QHBoxLayout()
        preset_layout.setSpacing(6)
        preset_layout.setContentsMargins(8, 12, 8, 8)

        self.combo_preset = QComboBox()
        for key, preset in self._presets.items():
            self.combo_preset.addItem(preset["name"], key)

        self.btn_load_preset = QPushButton(T("preset_load"))
        self.btn_load_preset.clicked.connect(self._on_load_preset)

        self.btn_save_preset = QPushButton(T("preset_save"))
        self.btn_save_preset.clicked.connect(self._on_save_preset)

        preset_layout.addWidget(self.combo_preset, 1)
        preset_layout.addWidget(self.btn_load_preset)
        preset_layout.addWidget(self.btn_save_preset)
        preset_group.setLayout(preset_layout)
        layout.addWidget(preset_group)

        # ── 噪声去除参数 ──
        noise_group = QGroupBox(T("noise_group"))
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

        noise_layout.addRow(T("noise_ping_num"), self.spin_ping_num)
        noise_layout.addRow(T("noise_range_num"), self.spin_range_num)
        noise_layout.addRow(T("noise_snr_threshold"), self.spin_snr)
        noise_group.setLayout(noise_layout)
        layout.addWidget(noise_group)

        self.spin_ping_num.valueChanged.connect(self._emit_noise_params)
        self.spin_range_num.valueChanged.connect(self._emit_noise_params)
        self.spin_snr.valueChanged.connect(self._emit_noise_params)

        # ── 表线设置 ──
        surface_group = QGroupBox(T("surface_group"))
        surface_layout = QFormLayout()
        surface_layout.setSpacing(6)
        surface_layout.setContentsMargins(8, 12, 8, 8)

        self.spin_surface = QDoubleSpinBox()
        self.spin_surface.setRange(0, 50)
        self.spin_surface.setValue(2.0)
        self.spin_surface.setSuffix(" m")
        surface_layout.addRow(T("surface_depth"), self.spin_surface)
        surface_group.setLayout(surface_layout)
        layout.addWidget(surface_group)

        self.spin_surface.valueChanged.connect(
            lambda v: self.surface_line_changed.emit(float(v))
        )

        # ── 底部检测参数 ──
        bottom_group = QGroupBox(T("bottom_group"))
        self.bottom_layout = QFormLayout()
        self.bottom_layout.setSpacing(6)
        self.bottom_layout.setContentsMargins(8, 12, 8, 8)

        self.combo_bottom_method = QComboBox()
        self.combo_bottom_method.addItems(["basic", "enhanced", "afsc"])
        self.combo_bottom_method.currentTextChanged.connect(self._on_bottom_method_changed)
        self.bottom_layout.addRow(T("bottom_method"), self.combo_bottom_method)

        # basic 方法参数
        self.spin_bottom_thr = QDoubleSpinBox()
        self.spin_bottom_thr.setRange(-70, -20)
        self.spin_bottom_thr.setValue(-40.0)
        self.spin_bottom_thr.setSuffix(" dB")
        self.bottom_layout.addRow(T("bottom_sv_threshold"), self.spin_bottom_thr)

        # enhanced 方法参数
        self.spin_peak_thr = QDoubleSpinBox()
        self.spin_peak_thr.setRange(-80, -10)
        self.spin_peak_thr.setValue(-40.0)
        self.spin_peak_thr.setSuffix(" dB")
        self.bottom_layout.addRow(T("bottom_peak_threshold"), self.spin_peak_thr)

        self.spin_disc_thr = QDoubleSpinBox()
        self.spin_disc_thr.setRange(-80, -10)
        self.spin_disc_thr.setValue(-50.0)
        self.spin_disc_thr.setSuffix(" dB")
        self.bottom_layout.addRow(T("bottom_disc_threshold"), self.spin_disc_thr)

        self.spin_sat_thr = QDoubleSpinBox()
        self.spin_sat_thr.setRange(-80, -10)
        self.spin_sat_thr.setValue(-60.0)
        self.spin_sat_thr.setSuffix(" dB")
        self.bottom_layout.addRow(T("bottom_sat_threshold"), self.spin_sat_thr)

        self.spin_val_window = QSpinBox()
        self.spin_val_window.setRange(1, 100)
        self.spin_val_window.setValue(15)
        self.bottom_layout.addRow(T("bottom_validation_window"), self.spin_val_window)

        self.spin_val_thr = QDoubleSpinBox()
        self.spin_val_thr.setRange(1.0, 20.0)
        self.spin_val_thr.setValue(3.0)
        self.bottom_layout.addRow(T("bottom_validation_threshold"), self.spin_val_thr)

        self.spin_smooth_window = QSpinBox()
        self.spin_smooth_window.setRange(1, 50)
        self.spin_smooth_window.setValue(11)
        self.bottom_layout.addRow(T("bottom_smoothing_window"), self.spin_smooth_window)

        # afsc 方法参数
        self.spin_search_min = QDoubleSpinBox()
        self.spin_search_min.setRange(0.0, 500.0)
        self.spin_search_min.setValue(10.0)
        self.spin_search_min.setSuffix(" m")
        self.bottom_layout.addRow(T("bottom_search_min"), self.spin_search_min)

        self.spin_window_len = QSpinBox()
        self.spin_window_len.setRange(1, 50)
        self.spin_window_len.setValue(11)
        self.bottom_layout.addRow(T("bottom_window_len"), self.spin_window_len)

        self.spin_backstep = QDoubleSpinBox()
        self.spin_backstep.setRange(0.0, 100.0)
        self.spin_backstep.setValue(35.0)
        self.spin_backstep.setSuffix(" dB")
        self.bottom_layout.addRow(T("bottom_backstep"), self.spin_backstep)

        # 底部检测按钮
        self.btn_detect_bottom = QPushButton(T("btn_detect_bottom"))
        self.btn_detect_bottom.setProperty("cssClass", "primary")

        self.btn_draw_bottom = QPushButton(T("btn_draw_bottom"))

        self.btn_update_bottom = QPushButton(T("btn_update_bottom"))

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.btn_detect_bottom)
        btn_layout.addWidget(self.btn_draw_bottom)
        btn_layout.addWidget(self.btn_update_bottom)
        self.bottom_layout.addRow(btn_layout)

        self.btn_detect_bottom.clicked.connect(self.detect_bottom_clicked)
        self.btn_draw_bottom.clicked.connect(self.draw_bottom_clicked)
        self.btn_update_bottom.clicked.connect(self.update_bottom_clicked)

        bottom_group.setLayout(self.bottom_layout)
        layout.addWidget(bottom_group)

        # 初始按默认方法（basic）显示对应参数
        self._on_bottom_method_changed(self.combo_bottom_method.currentText())

        # ── 鱼群检测参数 ──
        school_group = QGroupBox(T("school_group"))
        self.school_layout = QFormLayout()
        self.school_layout.setSpacing(6)
        self.school_layout.setContentsMargins(8, 12, 8, 8)

        def _pair_row(defaults, depth_key, ping_key):
            """创建 [depth, ping] 双 spin 行，返回 (行控件, depth spin, ping spin)"""
            row = QWidget()
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(4)
            s_depth = QDoubleSpinBox()
            s_depth.setRange(0.1, 100)
            s_depth.setValue(defaults[0])
            s_depth.setDecimals(1)
            s_depth.setSuffix(" m")
            s_depth.setToolTip(T(depth_key))
            s_ping = QDoubleSpinBox()
            s_ping.setRange(0.1, 100)
            s_ping.setValue(defaults[1])
            s_ping.setDecimals(1)
            s_ping.setToolTip(T(ping_key))
            h.addWidget(s_depth, 1)
            h.addWidget(s_ping, 1)
            return row, s_depth, s_ping

        # 检测方法选择
        self.combo_school_method = QComboBox()
        self.combo_school_method.addItems(["echoview", "advanced"])
        self.combo_school_method.currentTextChanged.connect(self._on_school_method_changed)
        self.school_layout.addRow(T("school_method"), self.combo_school_method)

        # echoview 方法参数
        self.spin_school_thr = QDoubleSpinBox()
        self.spin_school_thr.setRange(-100, 0)
        self.spin_school_thr.setValue(-55.0)
        self.spin_school_thr.setSuffix(" dB")
        self.school_layout.addRow(T("school_sv_threshold"), self.spin_school_thr)

        pair_row, self.spin_mincan_depth, self.spin_mincan_ping = _pair_row(
            (3.0, 10.0), "school_mincan_depth", "school_mincan_ping")
        self.school_layout.addRow(T("school_mincan"), pair_row)

        pair_row, self.spin_maxlink_depth, self.spin_maxlink_ping = _pair_row(
            (3.0, 15.0), "school_maxlink_depth", "school_maxlink_ping")
        self.school_layout.addRow(T("school_maxlink"), pair_row)

        pair_row, self.spin_minsho_depth, self.spin_minsho_ping = _pair_row(
            (3.0, 15.0), "school_minsho_depth", "school_minsho_ping")
        self.school_layout.addRow(T("school_minsho"), pair_row)

        # advanced 方法参数
        self.spin_min_threshold = QDoubleSpinBox()
        self.spin_min_threshold.setRange(-100, 0)
        self.spin_min_threshold.setValue(-60.0)
        self.spin_min_threshold.setSuffix(" dB")
        self.school_layout.addRow(T("school_min_threshold"), self.spin_min_threshold)

        self.spin_max_depth_dist = QDoubleSpinBox()
        self.spin_max_depth_dist.setRange(0.01, 10)
        self.spin_max_depth_dist.setValue(0.1)
        self.spin_max_depth_dist.setDecimals(2)
        self.spin_max_depth_dist.setSuffix(" m")
        self.school_layout.addRow(T("school_max_depth_dist"), self.spin_max_depth_dist)

        self.spin_max_ping_dist = QSpinBox()
        self.spin_max_ping_dist.setRange(1, 100)
        self.spin_max_ping_dist.setValue(1)
        self.school_layout.addRow(T("school_max_ping_dist"), self.spin_max_ping_dist)

        self.spin_max_time_gap = QSpinBox()
        self.spin_max_time_gap.setRange(1, 200)
        self.spin_max_time_gap.setValue(20)
        self.school_layout.addRow(T("school_max_time_gap"), self.spin_max_time_gap)

        self.spin_min_shoal_pings = QSpinBox()
        self.spin_min_shoal_pings.setRange(1, 100)
        self.spin_min_shoal_pings.setValue(3)
        self.school_layout.addRow(T("school_min_shoal_pings"), self.spin_min_shoal_pings)

        self.spin_min_shoal_height = QDoubleSpinBox()
        self.spin_min_shoal_height.setRange(0.01, 10)
        self.spin_min_shoal_height.setValue(0.5)
        self.spin_min_shoal_height.setDecimals(2)
        self.spin_min_shoal_height.setSuffix(" m")
        self.school_layout.addRow(T("school_min_shoal_height"), self.spin_min_shoal_height)

        # 检测按钮（始终可见）
        self.btn_detect_schools = QPushButton(T("btn_detect_schools"))
        self.btn_detect_schools.setProperty("cssClass", "primary")
        self.school_layout.addRow(self.btn_detect_schools)

        school_group.setLayout(self.school_layout)
        layout.addWidget(school_group)

        self.btn_detect_schools.clicked.connect(self.detect_schools_clicked)

        # 初始按默认方法（echoview）显示对应参数
        self._on_school_method_changed(self.combo_school_method.currentText())

        # ── 回声积分 ──
        integration_group = QGroupBox(T("integration_group"))
        integration_layout = QFormLayout()
        integration_layout.setSpacing(6)
        integration_layout.setContentsMargins(8, 12, 8, 8)

        self.combo_integration_esu = QComboBox()
        self.combo_integration_esu.addItems([
            T("integration_esu_pings"),
            T("integration_esu_distance"),
        ])
        self.combo_integration_esu.currentIndexChanged.connect(self._on_esu_type_changed)
        integration_layout.addRow(T("integration_esu_type"), self.combo_integration_esu)

        self.spin_integration_esu_size = QDoubleSpinBox()
        self.spin_integration_esu_size.setRange(1.0, 1000000.0)
        self.spin_integration_esu_size.setValue(500.0)
        self.spin_integration_esu_size.setDecimals(0)
        integration_layout.addRow(T("integration_esu_size"), self.spin_integration_esu_size)

        self.spin_integration_ts_default = QDoubleSpinBox()
        self.spin_integration_ts_default.setRange(-80.0, 0.0)
        self.spin_integration_ts_default.setValue(-30.0)
        self.spin_integration_ts_default.setSuffix(" dB")
        integration_layout.addRow(T("integration_ts_default"), self.spin_integration_ts_default)

        self.spin_integration_layer_width = QDoubleSpinBox()
        self.spin_integration_layer_width.setRange(0.5, 100.0)
        self.spin_integration_layer_width.setValue(5.0)
        self.spin_integration_layer_width.setSingleStep(0.5)
        self.spin_integration_layer_width.setSuffix(" m")
        integration_layout.addRow(T("integration_layer_width"), self.spin_integration_layer_width)

        self.spin_integration_min_thr = QDoubleSpinBox()
        self.spin_integration_min_thr.setRange(-150.0, 0.0)
        self.spin_integration_min_thr.setValue(-70.0)
        self.spin_integration_min_thr.setSuffix(" dB")
        integration_layout.addRow(T("integration_min_threshold"), self.spin_integration_min_thr)

        self.spin_integration_max_thr = QDoubleSpinBox()
        self.spin_integration_max_thr.setRange(-150.0, 0.0)
        self.spin_integration_max_thr.setValue(0.0)
        self.spin_integration_max_thr.setSuffix(" dB")
        integration_layout.addRow(T("integration_max_threshold"), self.spin_integration_max_thr)

        self.btn_integration = QPushButton(T("btn_integration"))
        self.btn_integration.setProperty("cssClass", "primary")
        self.btn_integration.clicked.connect(self.integration_clicked)
        integration_layout.addRow(self.btn_integration)

        integration_group.setLayout(integration_layout)
        layout.addWidget(integration_group)

        # ── 质量检查 ──
        self.btn_quality = QPushButton(T("btn_quality_check"))
        self.btn_quality.clicked.connect(self.quality_check_clicked)

        # ── 多频分析 ──
        self.btn_multifreq = QPushButton(T("btn_multifreq"))
        self.btn_multifreq.clicked.connect(self.multifreq_clicked)

        btn_layout2 = QHBoxLayout()
        btn_layout2.addWidget(self.btn_quality)
        btn_layout2.addWidget(self.btn_multifreq)
        layout.addLayout(btn_layout2)

        # ── 真实 SED（分裂波束）──
        real_sed_group = QGroupBox(T("single_target_real_group"))
        real_sed_layout = QFormLayout()
        real_sed_layout.setSpacing(6)
        real_sed_layout.setContentsMargins(8, 12, 8, 8)

        self.spin_rs_threshold = QDoubleSpinBox()
        self.spin_rs_threshold.setRange(-150.0, 0.0)
        self.spin_rs_threshold.setValue(-50.0)
        self.spin_rs_threshold.setDecimals(1)
        self.spin_rs_threshold.setSuffix(" dB")
        real_sed_layout.addRow(T("st_real_ts_threshold"), self.spin_rs_threshold)

        self.spin_rs_pldl = QDoubleSpinBox()
        self.spin_rs_pldl.setRange(1.0, 30.0)
        self.spin_rs_pldl.setValue(6.0)
        self.spin_rs_pldl.setSuffix(" dB")
        real_sed_layout.addRow(T("st_real_pldl"), self.spin_rs_pldl)

        self.spin_rs_min_pulse = QDoubleSpinBox()
        self.spin_rs_min_pulse.setRange(0.1, 5.0)
        self.spin_rs_min_pulse.setValue(0.8)
        self.spin_rs_min_pulse.setDecimals(2)
        real_sed_layout.addRow(T("st_real_min_norm_pulse"), self.spin_rs_min_pulse)

        self.spin_rs_max_pulse = QDoubleSpinBox()
        self.spin_rs_max_pulse.setRange(0.1, 10.0)
        self.spin_rs_max_pulse.setValue(1.5)
        self.spin_rs_max_pulse.setDecimals(2)
        real_sed_layout.addRow(T("st_real_max_norm_pulse"), self.spin_rs_max_pulse)

        self.spin_rs_angle_std = QDoubleSpinBox()
        self.spin_rs_angle_std.setRange(0.1, 5.0)
        self.spin_rs_angle_std.setValue(0.6)
        self.spin_rs_angle_std.setSuffix(" deg")
        real_sed_layout.addRow(T("st_real_max_angle_std"), self.spin_rs_angle_std)

        self.spin_rs_beam_comp = QDoubleSpinBox()
        self.spin_rs_beam_comp.setRange(0.0, 12.0)
        self.spin_rs_beam_comp.setValue(3.0)
        self.spin_rs_beam_comp.setSuffix(" dB")
        real_sed_layout.addRow(T("st_real_max_beam_comp"), self.spin_rs_beam_comp)

        self.spin_rs_min_depth = QDoubleSpinBox()
        self.spin_rs_min_depth.setRange(0.0, 2000.0)
        self.spin_rs_min_depth.setValue(0.0)
        self.spin_rs_min_depth.setSuffix(" m")
        real_sed_layout.addRow(T("st_real_min_depth"), self.spin_rs_min_depth)

        self.spin_rs_max_depth = QDoubleSpinBox()
        self.spin_rs_max_depth.setRange(0.0, 5000.0)
        self.spin_rs_max_depth.setValue(200.0)
        self.spin_rs_max_depth.setSuffix(" m")
        real_sed_layout.addRow(T("st_real_max_depth"), self.spin_rs_max_depth)

        self.btn_real_sed = QPushButton(T("btn_real_sed"))
        self.btn_real_sed.setProperty("cssClass", "primary")
        self.btn_real_sed.clicked.connect(self.real_sed_clicked)
        real_sed_layout.addRow(self.btn_real_sed)

        real_sed_group.setLayout(real_sed_layout)
        layout.addWidget(real_sed_group)

        # ── Sv 统计摘要 ──
        self.btn_sv_stats = QPushButton(T("btn_sv_stats"))
        self.btn_sv_stats.clicked.connect(self.sv_stats_clicked)

        # ── Transect 分段 ──
        self.btn_transect = QPushButton(T("btn_transect_split"))
        self.btn_transect.clicked.connect(self.transect_split_clicked)

        btn_layout4 = QHBoxLayout()
        btn_layout4.addWidget(self.btn_sv_stats)
        btn_layout4.addWidget(self.btn_transect)
        layout.addLayout(btn_layout4)

        # ── 应用全部参数按钮 ──
        self.btn_apply_all = QPushButton(T("btn_apply_all"))
        self.btn_apply_all.setProperty("cssClass", "primary")
        self.btn_apply_all.clicked.connect(self.apply_all_clicked)
        layout.addWidget(self.btn_apply_all)

        layout.addStretch()
        scroll.setWidget(container)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

        # 恢复上次配置
        self._restore_settings()

    def _load_presets(self) -> dict:
        """加载预设配置文件"""
        try:
            if PRESETS_FILE.exists():
                with open(PRESETS_FILE, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    return data.get("presets", {})
        except Exception:
            pass
        return {"default": {"name": T("fileset_default_name"), "description": ""}}

    def _on_load_preset(self):
        """加载选中的预设配置"""
        preset_key = self.combo_preset.currentData()
        if preset_key and preset_key in self._presets:
            preset = self._presets[preset_key]
            config = {
                "processing": preset.get("processing", {}),
                "school_detection": preset.get("school_detection", {}),
            }
            self.load_from_config(config)
            QMessageBox.information(self, T("preset_loaded"),
                                    T("preset_loaded_msg", name=preset['name']))

    def _on_save_preset(self):
        """保存当前配置为自定义预设"""
        config = self.get_all_config()
        custom_presets = self._settings.value("custom_presets", {})
        if not isinstance(custom_presets, dict):
            custom_presets = {}
        custom_presets["custom"] = {
            "name": T("fileset_default_name"),
            "description": "",
            **config,
        }
        self._settings.setValue("custom_presets", custom_presets)
        QMessageBox.information(self, T("preset_saved"), T("preset_saved_msg"))

    def _restore_settings(self):
        """恢复上次保存的配置"""
        try:
            config = self._settings.value("last_config")
            if config and isinstance(config, dict):
                self.load_from_config(config)
        except Exception:
            pass

    def save_settings(self):
        """保存当前配置到QSettings"""
        config = self.get_all_config()
        self._settings.setValue("last_config", config)

    def _on_esu_type_changed(self, index):
        """EDSU 类型切换时更新大小单位（pings 无单位 / distance 米）"""
        if index == 1:  # distance
            self.spin_integration_esu_size.setSuffix(" m")
            self.spin_integration_esu_size.setDecimals(1)
        else:
            self.spin_integration_esu_size.setSuffix("")
            self.spin_integration_esu_size.setDecimals(0)

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
        return {
            "method": self.combo_school_method.currentText(),
            "thr": self.spin_school_thr.value(),
            "mincan": [self.spin_mincan_depth.value(), self.spin_mincan_ping.value()],
            "maxlink": [self.spin_maxlink_depth.value(), self.spin_maxlink_ping.value()],
            "minsho": [self.spin_minsho_depth.value(), self.spin_minsho_ping.value()],
            "min_threshold": self.spin_min_threshold.value(),
            "max_depth_distance": self.spin_max_depth_dist.value(),
            "max_ping_distance": self.spin_max_ping_dist.value(),
            "max_time_gap": self.spin_max_time_gap.value(),
            "min_shoal_pings": self.spin_min_shoal_pings.value(),
            "min_shoal_height": self.spin_min_shoal_height.value(),
        }

    def _on_school_method_changed(self, method: str):
        """鱼群检测方法切换：只显示当前方法的参数（QFormLayout 行级显隐）"""
        # 行索引：0=方法, 1-4=echoview 参数, 5-10=advanced 参数, 11=按钮
        echoview_visible = method == "echoview"
        for row in range(1, 5):
            self.school_layout.setRowVisible(row, echoview_visible)
        advanced_visible = method == "advanced"
        for row in range(5, 11):
            self.school_layout.setRowVisible(row, advanced_visible)

    def _on_bottom_method_changed(self, method: str):
        """底部检测方法切换：只显示当前方法的参数（QFormLayout 行级显隐）"""
        # 行索引：0=方法, 1=Sv 阈值(basic), 2-7=enhanced 参数, 8-10=afsc 参数, 11=按钮
        self.bottom_layout.setRowVisible(1, method == "basic")
        enhanced_visible = method == "enhanced"
        for row in range(2, 8):
            self.bottom_layout.setRowVisible(row, enhanced_visible)
        afsc_visible = method == "afsc"
        for row in range(8, 11):
            self.bottom_layout.setRowVisible(row, afsc_visible)

    def get_bottom_config(self) -> dict:
        return {
            "method": self.combo_bottom_method.currentText(),
            "threshold": self.spin_bottom_thr.value(),
            "peak_threshold": self.spin_peak_thr.value(),
            "discrimination_threshold": self.spin_disc_thr.value(),
            "saturation_threshold": self.spin_sat_thr.value(),
            "validation_window": self.spin_val_window.value(),
            "validation_threshold": self.spin_val_thr.value(),
            "smoothing_window": self.spin_smooth_window.value(),
            "search_min": self.spin_search_min.value(),
            "window_len": self.spin_window_len.value(),
            "backstep": self.spin_backstep.value(),
        }

    def get_integration_config(self) -> dict:
        """获取回声积分配置"""
        esu_map = {0: "pings", 1: "distance"}
        return {
            "esu_type": esu_map.get(self.combo_integration_esu.currentIndex(), "pings"),
            "esu_size": self.spin_integration_esu_size.value(),
            "layer_width": self.spin_integration_layer_width.value(),
            "min_threshold": self.spin_integration_min_thr.value(),
            "max_threshold": self.spin_integration_max_thr.value(),
            "ts_default": self.spin_integration_ts_default.value(),
        }

    def get_real_sed_config(self) -> dict:
        """获取真实 SED 配置"""
        return {
            "ts_threshold_db": self.spin_rs_threshold.value(),
            "pldl_db": self.spin_rs_pldl.value(),
            "min_norm_pulse": self.spin_rs_min_pulse.value(),
            "max_norm_pulse": self.spin_rs_max_pulse.value(),
            "max_angle_std_deg": self.spin_rs_angle_std.value(),
            "max_beam_comp_db": self.spin_rs_beam_comp.value(),
            "min_depth_m": self.spin_rs_min_depth.value(),
            "max_depth_m": self.spin_rs_max_depth.value(),
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
        if "method" in bottom:
            idx = self.combo_bottom_method.findText(bottom["method"])
            if idx >= 0:
                self.combo_bottom_method.setCurrentIndex(idx)
        if "peak_threshold" in bottom:
            self.spin_peak_thr.setValue(bottom["peak_threshold"])
        if "discrimination_threshold" in bottom:
            self.spin_disc_thr.setValue(bottom["discrimination_threshold"])
        if "saturation_threshold" in bottom:
            self.spin_sat_thr.setValue(bottom["saturation_threshold"])
        if "validation_window" in bottom:
            self.spin_val_window.setValue(int(bottom["validation_window"]))
        if "validation_threshold" in bottom:
            self.spin_val_thr.setValue(bottom["validation_threshold"])
        if "smoothing_window" in bottom:
            self.spin_smooth_window.setValue(int(bottom["smoothing_window"]))
        if "search_min" in bottom:
            self.spin_search_min.setValue(bottom["search_min"])
        if "window_len" in bottom:
            self.spin_window_len.setValue(int(bottom["window_len"]))
        if "backstep" in bottom:
            self.spin_backstep.setValue(bottom["backstep"])

        school = config.get("school_detection", {})
        if "method" in school:
            idx = self.combo_school_method.findText(school["method"])
            if idx >= 0:
                self.combo_school_method.setCurrentIndex(idx)
        if "thr" in school:
            self.spin_school_thr.setValue(school["thr"])
        for key, spins in (
            ("mincan", (self.spin_mincan_depth, self.spin_mincan_ping)),
            ("maxlink", (self.spin_maxlink_depth, self.spin_maxlink_ping)),
            ("minsho", (self.spin_minsho_depth, self.spin_minsho_ping)),
        ):
            if key in school:
                pair = school[key]
                spins[0].setValue(float(pair[0]))
                spins[1].setValue(float(pair[1]))
        if "min_threshold" in school:
            self.spin_min_threshold.setValue(school["min_threshold"])
        if "max_depth_distance" in school:
            self.spin_max_depth_dist.setValue(school["max_depth_distance"])
        if "max_ping_distance" in school:
            self.spin_max_ping_dist.setValue(int(school["max_ping_distance"]))
        if "max_time_gap" in school:
            self.spin_max_time_gap.setValue(int(school["max_time_gap"]))
        if "min_shoal_pings" in school:
            self.spin_min_shoal_pings.setValue(int(school["min_shoal_pings"]))
        if "min_shoal_height" in school:
            self.spin_min_shoal_height.setValue(school["min_shoal_height"])

        surface = config.get("surface_line", {})
        if "depth_m" in surface:
            self.spin_surface.setValue(surface["depth_m"])

        integ = config.get("integration", {})
        if "esu_type" in integ:
            esu_map = {"pings": 0, "distance": 1}
            self.combo_integration_esu.setCurrentIndex(esu_map.get(integ["esu_type"], 0))
        if "esu_size" in integ:
            self.spin_integration_esu_size.setValue(float(integ["esu_size"]))
        if "layer_width" in integ:
            self.spin_integration_layer_width.setValue(float(integ["layer_width"]))
        if "min_threshold" in integ:
            self.spin_integration_min_thr.setValue(float(integ["min_threshold"]))
        if "max_threshold" in integ:
            self.spin_integration_max_thr.setValue(float(integ["max_threshold"]))
        if "ts_default" in integ:
            self.spin_integration_ts_default.setValue(float(integ["ts_default"]))

        rs = config.get("single_target_real", {})
        if "ts_threshold_db" in rs:
            self.spin_rs_threshold.setValue(float(rs["ts_threshold_db"]))
        if "pldl_db" in rs:
            self.spin_rs_pldl.setValue(float(rs["pldl_db"]))
        if "min_norm_pulse" in rs:
            self.spin_rs_min_pulse.setValue(float(rs["min_norm_pulse"]))
        if "max_norm_pulse" in rs:
            self.spin_rs_max_pulse.setValue(float(rs["max_norm_pulse"]))
        if "max_angle_std_deg" in rs:
            self.spin_rs_angle_std.setValue(float(rs["max_angle_std_deg"]))
        if "max_beam_comp_db" in rs:
            self.spin_rs_beam_comp.setValue(float(rs["max_beam_comp_db"]))
        if "min_depth_m" in rs:
            self.spin_rs_min_depth.setValue(float(rs["min_depth_m"]))
        if "max_depth_m" in rs:
            self.spin_rs_max_depth.setValue(float(rs["max_depth_m"]))

    def get_all_config(self) -> dict:
        """获取所有配置参数"""
        return {
            "processing": {
                "noise_removal": self.get_noise_config(),
                "bottom_detection": self.get_bottom_config(),
            },
            "school_detection": self.get_school_config(),
            "integration": self.get_integration_config(),
            "single_target_real": self.get_real_sed_config(),
            "surface_line": {"depth_m": self.spin_surface.value()},
        }


class StatsTab(QWidget):
    """统计结果标签页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        # ── 鱼群列表 ──
        schools_group = QGroupBox(T("stats_school_list"))
        schools_layout = QVBoxLayout()
        schools_layout.setContentsMargins(8, 12, 8, 8)

        self.table = QTableWidget()
        headers = T("school_headers")
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.verticalHeader().setVisible(False)

        schools_layout.addWidget(self.table)
        schools_group.setLayout(schools_layout)
        layout.addWidget(schools_group, 1)

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
    """右侧属性面板 — 参照 Echoview Properties 面板"""

    noise_params_changed = Signal(dict)
    surface_line_changed = Signal(float)
    detect_schools_clicked = Signal()
    stats_clicked = Signal()
    quality_check_clicked = Signal()
    multifreq_clicked = Signal()
    sv_stats_clicked = Signal()
    transect_split_clicked = Signal()
    integration_clicked = Signal()
    real_sed_clicked = Signal()
    detect_bottom_clicked = Signal()
    draw_bottom_clicked = Signal()
    update_bottom_clicked = Signal()
    apply_all_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.file_info = FileInfoTab()
        self.processing = ProcessingTab()
        self.stats = StatsTab()

        self.addTab(self.file_info, T("tab_file_info"))
        self.addTab(self.processing, T("tab_processing"))
        self.addTab(self.stats, T("tab_statistics"))

        # 转发信号
        self.processing.noise_params_changed.connect(self.noise_params_changed)
        self.processing.surface_line_changed.connect(self.surface_line_changed)
        self.processing.detect_schools_clicked.connect(self.detect_schools_clicked)
        self.processing.stats_clicked.connect(self.stats_clicked)
        self.processing.detect_bottom_clicked.connect(self.detect_bottom_clicked)
        self.processing.draw_bottom_clicked.connect(self.draw_bottom_clicked)
        self.processing.update_bottom_clicked.connect(self.update_bottom_clicked)
        self.processing.quality_check_clicked.connect(self.quality_check_clicked)
        self.processing.multifreq_clicked.connect(self.multifreq_clicked)
        self.processing.sv_stats_clicked.connect(self.sv_stats_clicked)
        self.processing.transect_split_clicked.connect(self.transect_split_clicked)
        self.processing.integration_clicked.connect(self.integration_clicked)
        self.processing.real_sed_clicked.connect(self.real_sed_clicked)
        self.processing.apply_all_clicked.connect(self.apply_all_clicked)

    def save_settings(self):
        """保存当前配置"""
        self.processing.save_settings()

    def get_all_config(self) -> dict:
        """获取所有配置"""
        return self.processing.get_all_config()
