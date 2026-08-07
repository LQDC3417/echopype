"""工具栏组件 - 基于 Echoview 设计的专业风格

设计原则：
- 简洁的文字标签，无 emoji
- 状态一目了然（选中态、禁用态）
- 参数控件紧凑排列
- 三行工具栏：标准、Echogram、处理
"""

from enum import Enum
from PySide6.QtWidgets import (
    QToolBar, QComboBox, QLabel, QSlider, QSpinBox, QDoubleSpinBox,
    QPushButton, QToolButton, QButtonGroup, QFrame,
)
from PySide6.QtGui import QAction, QIcon, QFont
from PySide6.QtCore import Signal, Qt, QSize


class MouseMode(Enum):
    NAVIGATE = 0
    SELECT_NOISE = 1
    DRAW_BOTTOM = 2
    INSPECT = 3


class StandardToolBar(QToolBar):
    """标准工具栏 - 文件操作 + 流程控制
    
    布局：[导入] [打开配置] [保存] | [运行] | [撤销] [重做] | [导出]
    """
    
    open_clicked = Signal()
    open_config_clicked = Signal()
    save_config_clicked = Signal()
    run_clicked = Signal()
    undo_clicked = Signal()
    redo_clicked = Signal()
    export_clicked = Signal()
    
    def __init__(self, parent=None):
        super().__init__("Standard", parent)
        self.setMovable(False)
        self.setObjectName("StandardToolBar")
        self.setIconSize(QSize(16, 16))
        self.setToolButtonStyle(Qt.ToolButtonTextOnly)
        
        # ─── 文件操作 ───
        self.addAction(self._act("Import Raw", self.open_clicked, "Ctrl+I"))
        self.addAction(self._act("Open Config", self.open_config_clicked, "Ctrl+O"))
        self.addAction(self._act("Save Config", self.save_config_clicked, "Ctrl+Shift+S"))
        self.addSeparator()
        
        # ─── 流程控制 ───
        self._run_act = self._act("Run All", self.run_clicked, "F5")
        self.addAction(self._run_act)
        self.addSeparator()
        
        # ─── 撤销/重做 ───
        self.addAction(self._act("Undo", self.undo_clicked, "Ctrl+Z"))
        self.addAction(self._act("Redo", self.redo_clicked, "Ctrl+Y"))
        self.addSeparator()
        
        # ─── 导出 ───
        self.addAction(self._act("Export", self.export_clicked, "Ctrl+E"))
    
    def _act(self, text, signal, shortcut=None):
        a = QAction(text, self)
        if shortcut:
            a.setShortcut(shortcut)
        a.triggered.connect(signal)
        return a


class EchogramToolBar(QToolBar):
    """Echogram 工具栏 - 交互模式 + 显示控制
    
    布局：[模式] | [视图] [翻页] | [颜色映射] [Sv 范围]
    """
    
    mode_changed = Signal(MouseMode)
    colormap_changed = Signal(str, float, float)
    reset_view_clicked = Signal()
    fit_view_clicked = Signal()
    prev_file_clicked = Signal()
    next_file_clicked = Signal()
    
    MODE_LABELS = ["Navigate", "Select Noise", "Draw Bottom", "Inspect"]
    
    def __init__(self, parent=None):
        super().__init__("Echogram", parent)
        self.setMovable(False)
        self.setObjectName("EchogramToolBar")
        self.setIconSize(QSize(16, 16))
        self.setToolButtonStyle(Qt.ToolButtonTextOnly)
        
        # ─── 鼠标模式 ───
        self.addWidget(self._label("Mode"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(self.MODE_LABELS)
        self.mode_combo.setMinimumWidth(100)
        self.mode_combo.currentIndexChanged.connect(
            lambda idx: self.mode_changed.emit(MouseMode(idx))
        )
        self.addWidget(self.mode_combo)
        
        self.addSeparator()
        
        # ─── 视图控制 ───
        self.addAction(self._act("Reset", self.reset_view_clicked))
        self.addAction(self._act("Fit", self.fit_view_clicked))
        
        self.addSeparator()
        
        # ─── 文件翻页 ───
        self.addAction(self._act("< Prev", self.prev_file_clicked))
        self.addAction(self._act("Next >", self.next_file_clicked))
        
        self.addSeparator()
        
        # ─── 颜色映射 ───
        self.addWidget(self._label("Color"))
        self.cmap_combo = QComboBox()
        self.cmap_combo.addItems(["jet", "viridis", "inferno", "gray"])
        self.cmap_combo.setMinimumWidth(80)
        self.cmap_combo.currentTextChanged.connect(self._on_cmap_changed)
        self.addWidget(self.cmap_combo)
        
        self.addSeparator()
        
        # ─── Sv 范围 ───
        self.addWidget(self._label("Sv"))
        
        self.slider_vmin = QSlider(Qt.Horizontal)
        self.slider_vmin.setRange(-100, 0)
        self.slider_vmin.setValue(-70)
        self.slider_vmin.setFixedWidth(100)
        self.addWidget(self.slider_vmin)
        
        self.lbl_vmin = QLabel("-70")
        self.lbl_vmin.setFixedWidth(30)
        self.lbl_vmin.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.addWidget(self.lbl_vmin)
        
        self.addWidget(self._label("~"))
        
        self.slider_vmax = QSlider(Qt.Horizontal)
        self.slider_vmax.setRange(-100, 0)
        self.slider_vmax.setValue(-20)
        self.slider_vmax.setFixedWidth(100)
        self.addWidget(self.slider_vmax)
        
        self.lbl_vmax = QLabel("-20")
        self.lbl_vmax.setFixedWidth(30)
        self.lbl_vmax.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.addWidget(self.lbl_vmax)
        
        self.slider_vmin.valueChanged.connect(self._on_sv_range_changed)
        self.slider_vmax.valueChanged.connect(self._on_sv_range_changed)
    
    def _act(self, text, signal, shortcut=None):
        a = QAction(text, self)
        if shortcut:
            a.setShortcut(shortcut)
        a.triggered.connect(signal)
        return a
    
    def _label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #666; font-size: 11px;")
        return lbl
    
    def _on_cmap_changed(self, cmap):
        vmin = self.slider_vmin.value()
        vmax = self.slider_vmax.value()
        self.colormap_changed.emit(cmap, vmin, vmax)
    
    def _on_sv_range_changed(self, _):
        vmin = self.slider_vmin.value()
        vmax = self.slider_vmax.value()
        self.lbl_vmin.setText(str(vmin))
        self.lbl_vmax.setText(str(vmax))
        cmap = self.cmap_combo.currentText()
        self.colormap_changed.emit(cmap, vmin, vmax)


class ProcessingToolBar(QToolBar):
    """处理工具栏 - 数据处理步骤快捷按钮
    
    布局：[Sv] [噪声] [底部] [鱼群] [密度] [网格] [导出]
    """
    
    compute_sv_clicked = Signal()
    noise_removal_clicked = Signal()
    detect_bottom_clicked = Signal()
    detect_schools_clicked = Signal()
    compute_density_clicked = Signal()
    grid_analysis_clicked = Signal()
    export_clicked = Signal()
    
    def __init__(self, parent=None):
        super().__init__("Processing", parent)
        self.setMovable(False)
        self.setObjectName("ProcessingToolBar")
        self.setIconSize(QSize(16, 16))
        self.setToolButtonStyle(Qt.ToolButtonTextOnly)
        
        # ─── 处理步骤按钮 ───
        self.addAction(self._act("1. Compute Sv", self.compute_sv_clicked, "Ctrl+1"))
        self.addAction(self._act("2. Noise Removal", self.noise_removal_clicked, "Ctrl+2"))
        self.addAction(self._act("3. Detect Bottom", self.detect_bottom_clicked, "Ctrl+3"))
        self.addAction(self._act("4. Detect Schools", self.detect_schools_clicked, "Ctrl+4"))
        self.addAction(self._act("5. Compute Density", self.compute_density_clicked, "Ctrl+5"))
        
        self.addSeparator()
        
        # ─── 分析和导出 ───
        self.addAction(self._act("Grid Analysis", self.grid_analysis_clicked))
        self.addAction(self._act("Export", self.export_clicked, "Ctrl+E"))
    
    def _act(self, text, signal, shortcut=None):
        a = QAction(text, self)
        if shortcut:
            a.setShortcut(shortcut)
        a.triggered.connect(signal)
        return a
