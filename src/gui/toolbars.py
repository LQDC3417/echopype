"""工具栏组件 — Echoview 专业风格

设计原则：
- 文字标签简洁，无 emoji
- 状态一目了然（选中态/禁用态）
- 参数控件紧凑排列
"""

from enum import Enum
from PySide6.QtWidgets import QToolBar, QComboBox, QLabel, QSlider, QSpinBox, QDoubleSpinBox, QPushButton
from PySide6.QtGui import QAction
from PySide6.QtCore import Signal, Qt


class MouseMode(Enum):
    NAVIGATE = 0
    SELECT_NOISE = 1
    DRAW_BOTTOM = 2
    INSPECT = 3


class StandardToolBar(QToolBar):
    """标准工具栏 — 文件操作 + 流程控制"""

    open_clicked = Signal()
    open_config_clicked = Signal()
    save_config_clicked = Signal()
    run_clicked = Signal()
    undo_clicked = Signal()
    redo_clicked = Signal()
    export_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__("标准", parent)
        self.setMovable(False)
        self.setObjectName("StandardToolBar")
        self.setIconSize(self.iconSize() * 0.9)

        # 文件操作
        self.addAction(self._act("导入 Raw", self.open_clicked, "Ctrl+I"))
        self.addAction(self._act("打开配置", self.open_config_clicked, "Ctrl+O"))
        self.addAction(self._act("保存配置", self.save_config_clicked, "Ctrl+Shift+S"))
        self.addSeparator()

        # 流程控制
        self._run_act = self._act("全部运行", self.run_clicked, "F5")
        self.addAction(self._run_act)
        self.addSeparator()

        # 撤销/重做
        self.addAction(self._act("撤销", self.undo_clicked, "Ctrl+Z"))
        self.addAction(self._act("重做", self.redo_clicked, "Ctrl+Y"))
        self.addSeparator()

        # 导出
        self.addAction(self._act("导出", self.export_clicked, "Ctrl+E"))

    def _act(self, text, signal, shortcut=None):
        a = QAction(text, self)
        if shortcut:
            a.setShortcut(shortcut)
        a.triggered.connect(signal)
        return a


class EchogramToolBar(QToolBar):
    """Echogram 工具栏 — 交互模式 + 显示控制

    布局：[模式] | [视图] | [文件翻页] | [颜色映射] [Sv 范围]
    """

    mode_changed = Signal(MouseMode)
    colormap_changed = Signal(str, float, float)
    reset_view_clicked = Signal()
    fit_view_clicked = Signal()
    prev_file_clicked = Signal()
    next_file_clicked = Signal()

    MODE_LABELS = ["导航", "框选噪声", "绘制底线", "检查"]

    def __init__(self, parent=None):
        super().__init__("Echogram", parent)
        self.setMovable(False)
        self.setObjectName("EchogramToolBar")
        self.setIconSize(self.iconSize() * 0.9)

        # ── 鼠标模式 ──
        self.addWidget(self._label("模式"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(self.MODE_LABELS)
        self.mode_combo.setMinimumWidth(80)
        self.mode_combo.currentIndexChanged.connect(
            lambda idx: self.mode_changed.emit(MouseMode(idx))
        )
        self.addWidget(self.mode_combo)

        self.addSeparator()

        # ── 视图控制 ──
        self.addAction(self._act("重置", self.reset_view_clicked))
        self.addAction(self._act("适应", self.fit_view_clicked))

        self.addSeparator()

        # ── 文件翻页 ──
        self.addAction(self._act("<", self.prev_file_clicked))
        self.addAction(self._act(">", self.next_file_clicked))

        self.addSeparator()

        # ── 颜色映射 ──
        self.addWidget(self._label("颜色"))
        self.cmap_combo = QComboBox()
        self.cmap_combo.addItems(["jet", "viridis", "inferno", "gray"])
        self.cmap_combo.setMinimumWidth(70)
        self.cmap_combo.currentTextChanged.connect(self._on_cmap_changed)
        self.addWidget(self.cmap_combo)

        self.addSeparator()

        # ── Sv 范围（紧凑布局）──
        self.addWidget(self._label("Sv"))

        self.slider_vmin = QSlider(Qt.Horizontal)
        self.slider_vmin.setRange(-100, 0)
        self.slider_vmin.setValue(-70)
        self.slider_vmin.setFixedWidth(100)
        self.addWidget(self.slider_vmin)

        self.lbl_vmin = QLabel("-70")
        self.lbl_vmin.setFixedWidth(28)
        self.lbl_vmin.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.addWidget(self.lbl_vmin)

        self.addWidget(self._label("~"))

        self.slider_vmax = QSlider(Qt.Horizontal)
        self.slider_vmax.setRange(-100, 0)
        self.slider_vmax.setValue(-20)
        self.slider_vmax.setFixedWidth(100)
        self.addWidget(self.slider_vmax)

        self.lbl_vmax = QLabel("-20")
        self.lbl_vmax.setFixedWidth(28)
        self.lbl_vmax.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.addWidget(self.lbl_vmax)

        self.slider_vmin.valueChanged.connect(self._on_sv_range_changed)
        self.slider_vmax.valueChanged.connect(self._on_sv_range_changed)

        self._current_cmap = "jet"

    def _label(self, text):
        """创建紧凑标签"""
        lbl = QLabel(f" {text} ")
        lbl.setStyleSheet("color: #4a5568; font-size: 11px;")
        return lbl

    def _act(self, text, signal, shortcut=None):
        a = QAction(text, self)
        if shortcut:
            a.setShortcut(shortcut)
        a.triggered.connect(signal)
        return a

    def _on_cmap_changed(self, name):
        self._current_cmap = name
        vmin, vmax = self.get_sv_range()
        self.colormap_changed.emit(self._current_cmap, vmin, vmax)

    def _on_sv_range_changed(self):
        vmin = self.slider_vmin.value()
        vmax = self.slider_vmax.value()
        if vmin >= vmax:
            vmin = vmax - 1
            self.slider_vmin.blockSignals(True)
            self.slider_vmin.setValue(vmin)
            self.slider_vmin.blockSignals(False)
        self.lbl_vmin.setText(str(vmin))
        self.lbl_vmax.setText(str(vmax))
        self.colormap_changed.emit(self._current_cmap, float(vmin), float(vmax))

    def get_sv_range(self):
        return float(self.slider_vmin.value()), float(self.slider_vmax.value())


class ProcessingToolBar(QToolBar):
    """处理参数工具栏 — 紧凑参数控件 + 操作按钮"""

    noise_params_changed = Signal(dict)
    surface_line_changed = Signal(float)
    detect_schools_clicked = Signal()
    compute_density_clicked = Signal()
    stats_clicked = Signal()
    grid_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__("处理", parent)
        self.setMovable(False)
        self.setObjectName("ProcessingToolBar")
        self.setIconSize(self.iconSize() * 0.85)

        # ── 表线 ──
        self.addWidget(self._label("表线"))
        self.spin_surface = QDoubleSpinBox()
        self.spin_surface.setRange(0, 50)
        self.spin_surface.setValue(2.0)
        self.spin_surface.setSuffix("m")
        self.spin_surface.setFixedWidth(65)
        self.spin_surface.setToolTip("表线深度（米）")
        self.addWidget(self.spin_surface)
        self.spin_surface.valueChanged.connect(
            lambda v: self.surface_line_changed.emit(float(v))
        )

        self.addSeparator()

        # ── 底部检测阈值 ──
        self.addWidget(self._label("底部"))
        self.spin_bottom_thr = QDoubleSpinBox()
        self.spin_bottom_thr.setRange(-70, -20)
        self.spin_bottom_thr.setValue(-40.0)
        self.spin_bottom_thr.setSuffix("dB")
        self.spin_bottom_thr.setFixedWidth(70)
        self.spin_bottom_thr.setToolTip("底部检测 Sv 阈值")
        self.addWidget(self.spin_bottom_thr)

        self.addSeparator()

        # ── 鱼群检测 ──
        self.addWidget(self._label("鱼群"))
        self.spin_school_thr = QDoubleSpinBox()
        self.spin_school_thr.setRange(-100, 0)
        self.spin_school_thr.setValue(-55.0)
        self.spin_school_thr.setSuffix("dB")
        self.spin_school_thr.setFixedWidth(70)
        self.addWidget(self.spin_school_thr)

        self.btn_detect_schools = QPushButton("检测鱼群")
        self.btn_detect_schools.setProperty("cssClass", "primary")
        self.addWidget(self.btn_detect_schools)
        self.btn_detect_schools.clicked.connect(self.detect_schools_clicked)

        self.addSeparator()

        # ── 密度估算 ──
        self.addWidget(self._label("TS"))
        self.spin_ts = QDoubleSpinBox()
        self.spin_ts.setRange(-70, -20)
        self.spin_ts.setValue(-30.0)
        self.spin_ts.setSuffix("dB")
        self.spin_ts.setFixedWidth(65)
        self.addWidget(self.spin_ts)

        self.btn_compute_density = QPushButton("计算密度")
        self.btn_compute_density.setProperty("cssClass", "primary")
        self.addWidget(self.btn_compute_density)
        self.btn_compute_density.clicked.connect(self.compute_density_clicked)

        self.addSeparator()

        # ── 网格分析 ──
        self.addSeparator()
        self.addWidget(self._label("网格"))
        self.combo_grid_v = QComboBox()
        self.combo_grid_v.addItems(["1m", "2m", "5m"])
        self.combo_grid_v.setCurrentIndex(1)  # 默认 2m
        self.combo_grid_v.setFixedWidth(50)
        self.combo_grid_v.setToolTip("垂直间隔")
        self.addWidget(self.combo_grid_v)

        self.spin_grid_h = QSpinBox()
        self.spin_grid_h.setRange(1, 10000)
        self.spin_grid_h.setValue(100)
        self.spin_grid_h.setFixedWidth(60)
        self.spin_grid_h.setToolTip("水平间隔（ping 数）")
        self.addWidget(self.spin_grid_h)

        self.combo_grid_h_method = QComboBox()
        self.combo_grid_h_method.addItems(["Ping", "距离"])
        self.combo_grid_h_method.setFixedWidth(55)
        self.combo_grid_h_method.setToolTip("水平分段方式")
        self.addWidget(self.combo_grid_h_method)

        self.btn_grid = QPushButton("网格分析")
        self.addWidget(self.btn_grid)
        self.btn_grid.clicked.connect(self.grid_clicked)

        # ── 统计按钮 ──
        self.addSeparator()
        self.btn_stats = QPushButton("统计")
        self.addWidget(self.btn_stats)
        self.btn_stats.clicked.connect(self.stats_clicked)

    def _label(self, text):
        lbl = QLabel(f" {text} ")
        lbl.setStyleSheet("color: #4a5568; font-size: 11px;")
        return lbl

    def get_noise_config(self) -> dict:
        return {"ping_num": 5, "range_sample_num": 10, "SNR_threshold": "3.0dB"}

    def get_school_config(self) -> dict:
        return {"thr": self.spin_school_thr.value()}

    def get_bottom_config(self) -> dict:
        return {"threshold": self.spin_bottom_thr.value()}

    def get_density_config(self) -> dict:
        return {"ts_default": self.spin_ts.value(), "avg_weight_kg": 0.5}

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
        proc = config.get("processing", {})
        bottom = proc.get("bottom_detection", {})
        if "threshold" in bottom:
            self.spin_bottom_thr.setValue(bottom["threshold"])
        school = config.get("school_detection", {})
        if "thr" in school:
            self.spin_school_thr.setValue(school["thr"])
        density = config.get("density", {})
        if "ts_default" in density:
            self.spin_ts.setValue(density["ts_default"])
        surface = config.get("surface_line", {})
        if "depth_m" in surface:
            self.spin_surface.setValue(surface["depth_m"])
