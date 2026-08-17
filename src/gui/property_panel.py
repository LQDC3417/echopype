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
    compute_density_clicked = Signal()
    grid_clicked = Signal()
    stats_clicked = Signal()
    quality_check_clicked = Signal()
    multifreq_clicked = Signal()
    single_target_clicked = Signal()
    sv_stats_clicked = Signal()
    transect_split_clicked = Signal()
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
        bottom_layout = QFormLayout()
        bottom_layout.setSpacing(6)
        bottom_layout.setContentsMargins(8, 12, 8, 8)

        self.combo_bottom_method = QComboBox()
        self.combo_bottom_method.addItems(["basic", "enhanced", "afsc"])
        bottom_layout.addRow(T("bottom_method"), self.combo_bottom_method)

        self.spin_bottom_thr = QDoubleSpinBox()
        self.spin_bottom_thr.setRange(-70, -20)
        self.spin_bottom_thr.setValue(-40.0)
        self.spin_bottom_thr.setSuffix(" dB")
        bottom_layout.addRow(T("bottom_sv_threshold"), self.spin_bottom_thr)

        self.spin_peak_thr = QDoubleSpinBox()
        self.spin_peak_thr.setRange(-80, -10)
        self.spin_peak_thr.setValue(-40.0)
        self.spin_peak_thr.setSuffix(" dB")
        bottom_layout.addRow(T("bottom_peak_threshold"), self.spin_peak_thr)

        self.spin_disc_thr = QDoubleSpinBox()
        self.spin_disc_thr.setRange(-80, -10)
        self.spin_disc_thr.setValue(-50.0)
        self.spin_disc_thr.setSuffix(" dB")
        bottom_layout.addRow(T("bottom_disc_threshold"), self.spin_disc_thr)

        # 底部检测按钮
        self.btn_detect_bottom = QPushButton(T("btn_detect_bottom"))
        self.btn_detect_bottom.setProperty("cssClass", "primary")

        self.btn_draw_bottom = QPushButton(T("btn_draw_bottom"))

        self.btn_update_bottom = QPushButton(T("btn_update_bottom"))

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
        school_group = QGroupBox(T("school_group"))
        school_layout = QFormLayout()
        school_layout.setSpacing(6)
        school_layout.setContentsMargins(8, 12, 8, 8)

        self.spin_school_thr = QDoubleSpinBox()
        self.spin_school_thr.setRange(-100, 0)
        self.spin_school_thr.setValue(-55.0)
        self.spin_school_thr.setSuffix(" dB")

        self.btn_detect_schools = QPushButton(T("btn_detect_schools"))
        self.btn_detect_schools.setProperty("cssClass", "primary")

        school_layout.addRow(T("school_sv_threshold"), self.spin_school_thr)
        school_layout.addRow(self.btn_detect_schools)
        school_group.setLayout(school_layout)
        layout.addWidget(school_group)

        self.btn_detect_schools.clicked.connect(self.detect_schools_clicked)

        # ── 密度估算 ──
        density_group = QGroupBox(T("density_group"))
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

        self.btn_compute_density = QPushButton(T("btn_compute_density"))
        self.btn_compute_density.setProperty("cssClass", "primary")

        density_layout.addRow(T("density_ts_default"), self.spin_ts)
        density_layout.addRow(T("density_avg_weight"), self.spin_avg_weight)
        density_layout.addRow(self.btn_compute_density)
        density_group.setLayout(density_layout)
        layout.addWidget(density_group)

        self.btn_compute_density.clicked.connect(self.compute_density_clicked)

        # ── 网格分析（增强版）──
        grid_group = QGroupBox(T("grid_group"))
        grid_layout = QVBoxLayout()
        grid_layout.setSpacing(8)
        grid_layout.setContentsMargins(8, 12, 8, 8)

        grid_params_layout = QGridLayout()
        grid_params_layout.setSpacing(6)

        # 垂直间隔
        lbl_v_interval = QLabel(T("grid_vertical_interval"))
        self.spin_grid_v = QDoubleSpinBox()
        self.spin_grid_v.setRange(0.1, 100.0)
        self.spin_grid_v.setValue(2.0)
        self.spin_grid_v.setSingleStep(0.5)
        self.spin_grid_v.setDecimals(1)
        grid_params_layout.addWidget(lbl_v_interval, 0, 0)
        grid_params_layout.addWidget(self.spin_grid_v, 0, 1)

        # 水平间隔
        lbl_h_interval = QLabel(T("grid_horizontal_interval"))
        self.spin_grid_h = QSpinBox()
        self.spin_grid_h.setRange(1, 10000)
        self.spin_grid_h.setValue(100)
        grid_params_layout.addWidget(lbl_h_interval, 1, 0)
        grid_params_layout.addWidget(self.spin_grid_h, 1, 1)

        # 水平分段方式
        lbl_h_method = QLabel(T("grid_segment_method"))
        self.combo_grid_h_method = QComboBox()
        self.combo_grid_h_method.addItems([T("grid_method_ping"), T("grid_method_distance")])
        grid_params_layout.addWidget(lbl_h_method, 2, 0)
        grid_params_layout.addWidget(self.combo_grid_h_method, 2, 1)

        # 距离单位
        lbl_distance_unit = QLabel(T("grid_distance_unit"))
        self.combo_distance_unit = QComboBox()
        self.combo_distance_unit.addItems(["m", "km", "nm"])
        self.combo_distance_unit.setEnabled(False)
        grid_params_layout.addWidget(lbl_distance_unit, 3, 0)
        grid_params_layout.addWidget(self.combo_distance_unit, 3, 1)

        grid_layout.addLayout(grid_params_layout)

        # 统计指标选择
        stats_group = QGroupBox(T("grid_stats_group"))
        stats_layout = QVBoxLayout()
        stats_layout.setSpacing(4)
        stats_layout.setContentsMargins(8, 12, 8, 8)

        self.chk_mean_sv = QCheckBox(T("grid_stat_mean_sv"))
        self.chk_mean_sv.setChecked(True)
        self.chk_abc = QCheckBox(T("grid_stat_abc"))
        self.chk_abc.setChecked(True)
        self.chk_density = QCheckBox(T("grid_stat_density"))
        self.chk_density.setChecked(True)
        self.chk_biomass = QCheckBox(T("grid_stat_biomass"))
        self.chk_biomass.setChecked(True)
        self.chk_valid_pixels = QCheckBox(T("grid_stat_valid_pixels"))
        self.chk_valid_pixels.setChecked(True)

        stats_layout.addWidget(self.chk_mean_sv)
        stats_layout.addWidget(self.chk_abc)
        stats_layout.addWidget(self.chk_density)
        stats_layout.addWidget(self.chk_biomass)
        stats_layout.addWidget(self.chk_valid_pixels)
        stats_group.setLayout(stats_layout)
        grid_layout.addWidget(stats_group)

        # 输出格式选择
        output_group = QGroupBox(T("grid_output_group"))
        output_layout = QFormLayout()
        output_layout.setSpacing(6)
        output_layout.setContentsMargins(8, 12, 8, 8)

        self.combo_output_format = QComboBox()
        self.combo_output_format.addItems(["DataFrame", "CSV", "Excel", "JSON"])

        self.chk_include_metadata = QCheckBox(T("grid_include_metadata"))
        self.chk_include_metadata.setChecked(True)
        self.chk_include_summary = QCheckBox(T("grid_include_summary"))
        self.chk_include_summary.setChecked(True)

        output_layout.addRow(T("grid_output_format"), self.combo_output_format)
        output_layout.addRow(self.chk_include_metadata)
        output_layout.addRow(self.chk_include_summary)
        output_group.setLayout(output_layout)
        grid_layout.addWidget(output_group)

        # 网格分析按钮
        self.btn_grid = QPushButton(T("btn_grid_analysis"))
        self.btn_grid.setProperty("cssClass", "primary")
        self.btn_grid.clicked.connect(self._on_grid_clicked)

        self.btn_stats = QPushButton(T("btn_statistics"))

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.btn_grid)
        btn_layout.addWidget(self.btn_stats)
        grid_layout.addLayout(btn_layout)

        grid_group.setLayout(grid_layout)
        layout.addWidget(grid_group)

        self.combo_grid_h_method.currentIndexChanged.connect(self._on_h_method_changed)
        self.btn_stats.clicked.connect(self.stats_clicked)

        # ── 质量检查 ──
        self.btn_quality = QPushButton(T("btn_quality_check"))
        self.btn_quality.clicked.connect(self.quality_check_clicked)

        # ── 多频分析 ──
        self.btn_multifreq = QPushButton(T("btn_multifreq"))
        self.btn_multifreq.clicked.connect(self.multifreq_clicked)

        # ── 单体目标检测 ──
        self.btn_single_target = QPushButton(T("btn_single_target"))
        self.btn_single_target.clicked.connect(self.single_target_clicked)

        btn_layout2 = QHBoxLayout()
        btn_layout2.addWidget(self.btn_quality)
        btn_layout2.addWidget(self.btn_multifreq)
        layout.addLayout(btn_layout2)

        btn_layout3 = QHBoxLayout()
        btn_layout3.addWidget(self.btn_single_target)
        layout.addLayout(btn_layout3)

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
                "density": preset.get("density", {}),
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

    def _on_h_method_changed(self, index):
        """水平分段方式改变时更新距离单位的启用状态"""
        self.combo_distance_unit.setEnabled(index == 1)

    def _on_grid_clicked(self):
        """网格分析按钮点击时进行输入验证"""
        v_interval = self.spin_grid_v.value()
        if v_interval <= 0:
            QMessageBox.warning(self, T("dialog_input_error"), T("grid_error_vertical"))
            return

        h_interval = self.spin_grid_h.value()
        if h_interval <= 0:
            QMessageBox.warning(self, T("dialog_input_error"), T("grid_error_horizontal"))
            return

        if not (self.chk_mean_sv.isChecked() or self.chk_abc.isChecked() or
                self.chk_density.isChecked() or self.chk_biomass.isChecked() or
                self.chk_valid_pixels.isChecked()):
            QMessageBox.warning(self, T("dialog_input_error"), T("grid_error_no_metrics"))
            return

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
        return {
            "method": self.combo_bottom_method.currentText(),
            "threshold": self.spin_bottom_thr.value(),
            "peak_threshold": self.spin_peak_thr.value(),
            "discrimination_threshold": self.spin_disc_thr.value(),
        }

    def get_density_config(self) -> dict:
        return {
            "ts_default": self.spin_ts.value(),
            "avg_weight_kg": self.spin_avg_weight.value(),
        }

    def get_grid_config(self) -> dict:
        """获取网格配置（增强版）"""
        v_interval = self.spin_grid_v.value()
        h_method = "ping" if self.combo_grid_h_method.currentIndex() == 0 else "distance"

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
        if "method" in bottom:
            idx = self.combo_bottom_method.findText(bottom["method"])
            if idx >= 0:
                self.combo_bottom_method.setCurrentIndex(idx)
        if "peak_threshold" in bottom:
            self.spin_peak_thr.setValue(bottom["peak_threshold"])
        if "discrimination_threshold" in bottom:
            self.spin_disc_thr.setValue(bottom["discrimination_threshold"])

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

    def get_all_config(self) -> dict:
        """获取所有配置参数"""
        return {
            "processing": {
                "noise_removal": self.get_noise_config(),
                "bottom_detection": self.get_bottom_config(),
            },
            "school_detection": self.get_school_config(),
            "density": self.get_density_config(),
            "surface_line": {"depth_m": self.spin_surface.value()},
        }


class StatsTab(QWidget):
    """统计结果标签页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        # ── 密度摘要（突出显示）──
        summary_group = QGroupBox(T("stats_density_summary"))
        summary_layout = QVBoxLayout()
        summary_layout.setContentsMargins(8, 12, 8, 8)

        self.lbl_abc = QLabel("ABC: --")
        self.lbl_abc.setStyleSheet("font-size: 13px; font-weight: bold; color: #2f855a;")
        self.lbl_density = QLabel(f"{T('density_group')}: --")
        self.lbl_density.setStyleSheet("font-size: 13px; font-weight: bold; color: #1a73e8;")
        self.lbl_biomass = QLabel(f"{T('density_avg_weight').rstrip(':')}: --")
        self.lbl_biomass.setStyleSheet("font-size: 13px; font-weight: bold; color: #c05621;")

        summary_layout.addWidget(self.lbl_abc)
        summary_layout.addWidget(self.lbl_density)
        summary_layout.addWidget(self.lbl_biomass)
        summary_group.setLayout(summary_layout)
        layout.addWidget(summary_group)

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

    def update_density(self, density_df):
        """更新密度统计"""
        if density_df is None or density_df.empty:
            return
        row = density_df.iloc[0]
        self.lbl_abc.setText(T("density_abc_fmt", val=row.get('abc', 0)))
        self.lbl_density.setText(T("density_val_fmt", val=row.get('density_ind_ha', 0)))
        self.lbl_biomass.setText(T("density_biomass_fmt", val=row.get('total_biomass_kg_ha', 0)))

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
    compute_density_clicked = Signal()
    grid_clicked = Signal()
    stats_clicked = Signal()
    quality_check_clicked = Signal()
    multifreq_clicked = Signal()
    single_target_clicked = Signal()
    sv_stats_clicked = Signal()
    transect_split_clicked = Signal()
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
        self.processing.apply_all_clicked.connect(self.apply_all_clicked)

    def save_settings(self):
        """保存当前配置"""
        self.processing.save_settings()

    def get_all_config(self) -> dict:
        """获取所有配置"""
        return self.processing.get_all_config()
