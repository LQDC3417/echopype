"""主窗口 — Echoview 专业风格停靠布局

┌──────────────────────────────────────────────────┐
│ Menu Bar                                          │
├──────────────────────────────────────────────────┤
│ StandardToolBar | EchogramToolBar                 │
├───────────┬──────────────────────┬───────────────┤
│ [Dock]    │                      │ [Dock]        │
│ 文件树    │    Echogram (GL)     │ 属性面板      │
│ 变量列表  │                      │ 信息/参数/结果│
├───────────┴──────────────────────┴───────────────┤
│ [Dock] 区域表格 (可折叠)                          │
├──────────────────────────────────────────────────┤
│ Status Bar                                        │
└──────────────────────────────────────────────────┘
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QSplitter,
)

from src.core.utils import load_config
from src.gui.export_dialog import ExportDialog
from src.gui.fileset import Fileset
from src.gui.fileset_tree import BatchImportDialog, FilesetTreeWidget
from src.gui.property_panel import PropertyPanel
from src.gui.region_panel import RegionTableWidget
from src.gui.stats_dialog import StatsDialog
from src.gui.status_bar import MainStatusBar
from src.gui.toolbars import EchogramToolBar, MouseMode, StandardToolBar
from src.gui.variable_list import VariableListWidget
from src.gui.workers import (
    BatchProcessWorker,
    ComputeSvWorker,
    DetectSchoolsWorker,
    DetectSeafloorWorker,
    GridWorker,
    LoadFileWorker,
    MultifreqAnalysisWorker,
    NoiseRemovalWorker,
    QualityCheckWorker,
    SingleTargetWorker,
    SvStatsWorker,
    TransectSplitWorker,
)
from src.gui.workers import (
    ComputeDensityWorker as DensityWorker,
)
from src.viz.opengl_renderer import EchogramRenderer

logger = logging.getLogger(__name__)


def squeeze_sv(sv: np.ndarray) -> np.ndarray:
    """将 3D Sv 数组降维为 2D（取第一个 channel）。"""
    if sv.ndim == 3:
        return sv[0]
    return sv


class MainWindow(QMainWindow):
    """Echoview 风格主窗口 — 鱼类声学资源评估系统"""

    # 流水线进度信号
    pipeline_step = Signal(str)       # 步骤名称
    pipeline_done = Signal()          # 全部完成

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Echogram — 鱼类声学资源评估系统")
        self.setMinimumSize(1400, 900)

        # ── 状态 ──
        self._config: dict | None = None
        self._echodata = None
        self._ds_Sv = None            # 完整 Sv（含水底数据）
        self._ds_Sv_analysis = None   # 分析区域裁剪后的 Sv（表线~底线）
        self._noise_mask_manual = None
        self._bottom_line = None
        self._surface_depth_m = 2.0  # 表线深度（米）
        self._analysis_region_enabled = False  # 分析区域限定
        self._schools_mask = None
        self._schools_df = None
        self._density_df = None
        self._current_worker = None
        self._batch_worker = None            # 批量处理工作线程
        self._batch_results: dict[str, object] = {}  # {path_str: ds_Sv}
        self._current_fileset: Fileset = None
        self._current_channel = ""
        self._undo_stack = []
        self._redo_stack = []
        self._current_mode = MouseMode.NAVIGATE
        self._run_all_chain = False
        self._raw_file_queue: list[Path] = []
        self._raw_queue_index = 0
        self._file_cache: dict[str, dict] = {}  # {path_str: {"sv": array, "ds": Dataset, "bottom": array}}

        # 变量缓存
        self._variable_cache = {}
        self._display_to_key = {}  # 显示名 → 缓存 key 的反向映射

        # 防抖
        self._noise_timer = QTimer()
        self._noise_timer.setSingleShot(True)
        self._noise_timer.setInterval(400)
        self._noise_timer.timeout.connect(self._apply_noise_params)

        self._setup_menubar()
        self._setup_ui()
        self._register_dock_view_actions()
        self._connect_signals()
        self._apply_default_config()

        # 流水线信号
        self.pipeline_step.connect(self.statusbar.set_step)

    # ═══════════════════════════════════════════════════════
    # 菜单栏
    # ═══════════════════════════════════════════════════════

    def _setup_menubar(self):
        mb = self.menuBar()

        # ── 文件 ──
        fm = mb.addMenu("文件(&F)")
        fm.addAction(self._act("导入 Raw 文件...", self._import_raw, "Ctrl+I"))
        fm.addAction(self._act("打开配置文件...", self._open_config, "Ctrl+O"))
        fm.addAction(self._act("保存配置...", self._save_config, "Ctrl+Shift+S"))
        fm.addSeparator()
        fm.addAction(self._act("导出结果 CSV...", self._export, "Ctrl+E"))
        fm.addSeparator()
        fm.addAction(self._act("退出", self.close, "Ctrl+Q"))

        # ── 编辑 ──
        em = mb.addMenu("编辑(&E)")
        em.addAction(self._act("撤销", self._undo, "Ctrl+Z"))
        em.addAction(self._act("重做", self._redo, "Ctrl+Y"))
        em.addSeparator()
        em.addAction(self._act("清除噪声区域", self._clear_noise_regions))
        em.addAction(self._act("清除鱼群显示", self._clear_schools))

        # ── 视图 ──
        vm = mb.addMenu("显示(&V)")
        vm.addAction(self._act("重置视图", self._reset_view))
        vm.addAction(self._act("适应窗口", self._fit_view))
        vm.addSeparator()
        self._act_noise = self._checkable("显示噪声叠加", True)
        self._act_school = self._checkable("显示鱼群叠加", True)
        self._act_bottom = self._checkable("显示底线", True)
        vm.addAction(self._act_noise)
        vm.addAction(self._act_school)
        vm.addAction(self._act_bottom)
        vm.addSeparator()
        # Dock 面板切换（_setup_ui 后由 _register_dock_view_actions 填充）

        # ── 处理 ──
        pm = mb.addMenu("处理(&P)")
        pm.addAction(self._act("▶  全部运行", self._run_all, "F5"))
        pm.addAction(self._act("⚡ 批量处理文件...", self._batch_process_files, "Ctrl+B"))
        pm.addSeparator()
        pm.addAction(self._act("计算 Sv", self._compute_sv, "Ctrl+1"))
        pm.addAction(self._act("噪声去除", self._apply_noise_params, "Ctrl+2"))
        pm.addAction(self._act("检测底部", self._detect_bottom, "Ctrl+3"))
        pm.addAction(self._act("检测鱼群", self._detect_schools, "Ctrl+4"))
        pm.addAction(self._act("计算密度", self._compute_density, "Ctrl+5"))

        # ── 分析 ──
        am = mb.addMenu("分析(&A)")
        am.addAction(self._act("导出密度报告", self._export))
        am.addAction(self._act("导出鱼群清单", self._export_schools))

        # ── 帮助 ──
        hm = mb.addMenu("帮助(&H)")
        hm.addAction(self._act("关于", self._show_about))

    def _register_dock_view_actions(self):
        """将各 Dock 的显示/隐藏切换加入视图菜单"""
        vm = None
        for a in self.menuBar().actions():
            if a.text() == "显示(&V)":
                vm = a.menu()
                break
        if vm is None:
            return
        for dock in (self.dock_left, self.dock_right, self.dock_bottom):
            vm.addAction(dock.toggleViewAction())

    def _act(self, text, slot, shortcut=None):
        a = QAction(text, self)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        a.triggered.connect(slot)
        return a

    def _checkable(self, text, default=True):
        a = QAction(text, self)
        a.setCheckable(True)
        a.setChecked(default)
        return a

    # ═══════════════════════════════════════════════════════
    # UI 布局
    # ═══════════════════════════════════════════════════════

    def _setup_ui(self):
        # ── 工具栏（2 行紧凑）──
        self.std_toolbar = StandardToolBar(self)
        self.addToolBar(self.std_toolbar)
        self.echo_toolbar = EchogramToolBar(self)
        self.addToolBarBreak()
        self.addToolBar(self.echo_toolbar)

        # ── 统计对话框 ──
        self.stats_dialog = StatsDialog(self)

        # ── 状态栏 ──
        self.statusbar = MainStatusBar(self)
        self.setStatusBar(self.statusbar)

        # ── 中央：仅 Echogram ──
        self.echogram = EchogramRenderer()
        self.setCentralWidget(self.echogram)

        # ── 左侧 Dock：文件树 + 变量列表 ──
        left_split = QSplitter(Qt.Vertical)
        self.fileset_tree = FilesetTreeWidget()
        self.variable_list = VariableListWidget()
        left_split.addWidget(self.fileset_tree)
        left_split.addWidget(self.variable_list)
        left_split.setSizes([350, 150])

        self.dock_left = QDockWidget("文件集", self)
        self.dock_left.setObjectName("dockFileset")
        self.dock_left.setWidget(left_split)
        self.dock_left.setFeatures(
            QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable
        )
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_left)

        # ── 右侧 Dock：属性面板 ──
        self.property_panel = PropertyPanel()
        self.dock_right = QDockWidget("属性", self)
        self.dock_right.setObjectName("dockProperties")
        self.dock_right.setWidget(self.property_panel)
        self.dock_right.setFeatures(
            QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable
        )
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_right)

        # ── 底部 Dock：区域表格 ──
        self.region_table = RegionTableWidget()
        self.region_table.setMaximumHeight(180)
        self.dock_bottom = QDockWidget("区域", self)
        self.dock_bottom.setObjectName("dockRegions")
        self.dock_bottom.setWidget(self.region_table)
        self.dock_bottom.setFeatures(
            QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable
        )
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_bottom)

        # 默认尺寸：左 260px，右 300px，底部 160px
        self.resizeDocks([self.dock_left], [260], Qt.Horizontal)
        self.resizeDocks([self.dock_right], [300], Qt.Horizontal)
        self.resizeDocks([self.dock_bottom], [160], Qt.Vertical)

    # ═══════════════════════════════════════════════════════
    # 信号连接
    # ═══════════════════════════════════════════════════════

    def _connect_signals(self):
        # 文件集面板
        self.fileset_tree.fileset_selected.connect(self._on_fileset_selected)
        self.fileset_tree.file_selected.connect(self._load_file)
        self.fileset_tree.channel_selected.connect(self._on_channel_selected)

        # 标准工具栏
        self.std_toolbar.open_clicked.connect(self._import_raw)
        self.std_toolbar.open_config_clicked.connect(self._open_config)
        self.std_toolbar.save_config_clicked.connect(self._save_config)
        self.std_toolbar.run_clicked.connect(self._run_all)
        self.std_toolbar.undo_clicked.connect(self._undo)
        self.std_toolbar.redo_clicked.connect(self._redo)
        self.std_toolbar.export_clicked.connect(self._export)

        # Echogram 工具栏
        self.echo_toolbar.mode_changed.connect(self._on_mode_changed)
        self.echo_toolbar.mode_changed.connect(lambda m: self.echogram.set_mouse_mode(m.value))
        self.echo_toolbar.colormap_changed.connect(self.echogram.set_colormap)
        self.echo_toolbar.reset_view_clicked.connect(self._reset_view)
        self.echo_toolbar.fit_view_clicked.connect(self._fit_view)

        # 工具栏翻页按钮
        self.echo_toolbar.prev_file_clicked.connect(lambda: self._switch_file(-1))
        self.echo_toolbar.next_file_clicked.connect(lambda: self._switch_file(1))

        # Echogram 交互
        self.echogram.mouse_moved.connect(self.statusbar.set_coords)
        self.echogram.mouse_moved.connect(self._update_depth_at_cursor)
        self.echogram.region_selected.connect(self._on_region_selected)
        self.echogram.bottom_line_edited.connect(self._on_bottom_line_edited)
        self.echogram.sv_at_cursor.connect(self.statusbar.set_sv)
        self.echogram.zoom_changed.connect(self.statusbar.set_zoom_info)

        # 右键菜单信号
        self.echogram.surface_line_requested.connect(self._on_surface_line_dialog)
        self.echogram.analysis_region_toggle.connect(self._on_analysis_region_toggle)
        self.echogram.re_detect_bottom.connect(self._detect_bottom)
        self.echogram.update_bottom_requested.connect(self._on_update_bottom)

        # echogram 翻页信号
        self.echogram.file_page_requested.connect(self._switch_file)

        # 属性面板（处理参数）
        self.property_panel.surface_line_changed.connect(self._on_surface_line_changed)
        self.property_panel.detect_schools_clicked.connect(self._detect_schools)
        self.property_panel.compute_density_clicked.connect(self._compute_density)
        self.property_panel.stats_clicked.connect(self._show_stats)
        self.property_panel.grid_clicked.connect(self._run_grid_analysis)
        self.property_panel.noise_params_changed.connect(self._on_noise_params_changed)
        self.property_panel.quality_check_clicked.connect(self._run_quality_check)
        self.property_panel.multifreq_clicked.connect(self._run_multifreq_analysis)
        self.property_panel.single_target_clicked.connect(self._run_single_target_detection)
        self.property_panel.sv_stats_clicked.connect(self._run_sv_stats)
        self.property_panel.transect_split_clicked.connect(self._run_transect_split)
        self.property_panel.detect_bottom_clicked.connect(self._detect_bottom)
        self.property_panel.draw_bottom_clicked.connect(self._start_draw_bottom)
        self.property_panel.update_bottom_clicked.connect(self._on_update_bottom)

        # 变量列表
        self.variable_list.variable_selected.connect(self._on_variable_selected)

        # 区域面板
        self.region_table.region_deleted.connect(self._on_region_deleted)

    # ═══════════════════════════════════════════════════════
    # 配置
    # ═══════════════════════════════════════════════════════

    def _apply_default_config(self):
        self._config = {
            "processing": {
                "sonar_model": "EK80",
                "noise_removal": {
                    "ping_num": 5, "range_sample_num": 10,
                    "SNR_threshold": "3.0dB",
                },
                "bottom_detection": {
                    "method": "basic", "threshold": -50.0,
                    "offset_m": 0.5, "bin_skip_from_surface": 200,
                },
            },
            "school_detection": {
                "method": "echoview", "thr": -55.0,
                "mincan": [3, 10], "maxlink": [3, 15], "minsho": [3, 15],
            },
            "density": {"ts_default": -30.0},
        }

    # ═══════════════════════════════════════════════════════
    # 文件操作 — 批量导入
    # ═══════════════════════════════════════════════════════

    def _import_raw(self):
        """打开批量导入对话框"""
        dlg = BatchImportDialog(self)
        dlg.fileset_created.connect(self.fileset_tree.add_fileset)
        dlg.exec()

    def _open_config(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "打开配置文件", "", "YAML (*.yaml *.yml);;全部 (*)"
        )
        if path:
            try:
                self._config = load_config(path)
                # 配置验证
                from src.core.utils import validate_config
                errors = validate_config(self._config)
                if errors:
                    QMessageBox.warning(self, "配置警告", "\n".join(errors))
                self.statusbar.set_status(f"配置已加载: {path}")
                self.property_panel.processing.load_from_config(self._config)
            except Exception as e:
                QMessageBox.critical(self, "错误", f"加载失败: {e}")

    def _save_config(self):
        if self._config is None:
            QMessageBox.warning(self, "警告", "无配置可保存")
            return
        path, _ = QFileDialog.getSaveFileName(self, "保存配置", "", "YAML (*.yaml)")
        if path:
            import yaml
            with open(path, "w", encoding="utf-8") as f:
                yaml.dump(self._config, f, allow_unicode=True, default_flow_style=False)
            self.statusbar.set_status(f"配置已保存: {path}")

    # ═══════════════════════════════════════════════════════
    # 批量处理（并行）
    # ═══════════════════════════════════════════════════════

    def _batch_process_files(self):
        """批量处理多个 raw 文件（后台并行）"""
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择要批量处理的 Raw 文件", str(Path.cwd()), "Raw 文件 (*.raw);;所有文件 (*)"
        )
        if not paths:
            return
        if self._batch_worker is not None and self._batch_worker.isRunning():
            QMessageBox.information(self, "提示", "批量处理正在进行中")
            return
        if self._config is None:
            self._apply_default_config()
        assert self._config is not None

        raw_files = [Path(p) for p in paths]
        self.statusbar.show_progress(f"批量处理 {len(raw_files)} 个文件...")
        self._batch_results = {}

        worker = BatchProcessWorker(raw_files, self._config, max_workers=2)
        worker.progress.connect(self.statusbar.set_status)
        worker.file_finished.connect(self._on_batch_file_finished)
        worker.file_error.connect(self._on_batch_file_error)
        worker.all_finished.connect(self._on_batch_all_finished)
        self._batch_worker = worker
        worker.start()

    def _on_batch_file_finished(self, path_str: str, ds_Sv):
        """单个文件处理完成 → 缓存结果"""
        try:
            sv = squeeze_sv(ds_Sv["Sv"].values)
            self._file_cache[path_str] = {
                "sv": sv.astype(np.float32),
                "ds": ds_Sv,
                "bottom": None,
                "noise_mask": None,
                "school_mask": None,
                "surface_depth_m": self._surface_depth_m,
            }
            self._batch_results[path_str] = ds_Sv
        except Exception:
            logger.exception("批量处理结果缓存失败: %s", path_str)

    def _on_batch_file_error(self, path_str: str, error_msg: str):
        """单个文件处理失败"""
        logger.error("批量处理失败 %s:\n%s", path_str, error_msg)

    def _on_batch_all_finished(self, success: int, error: int):
        """批量处理全部完成 → 更新队列并显示第一个成功文件"""
        new_paths = [Path(p) for p in self._batch_results]
        if new_paths:
            # 当前队列为空 → 设为新队列并显示第一个；否则追加到队尾
            if not self._raw_file_queue:
                self._raw_file_queue = list(new_paths)
                self._raw_queue_index = 0
                first = self._file_cache[str(self._raw_file_queue[0])]
                self._apply_sv_to_display(first["ds"], first["sv"])
            else:
                for p in new_paths:
                    if p not in self._raw_file_queue:
                        self._raw_file_queue.append(p)

        self.statusbar.hide_progress()
        self._batch_worker = None
        self._batch_results = {}
        self.statusbar.set_status(f"批量处理完成: 成功 {success}, 失败 {error}")
        QMessageBox.information(
            self, "批量处理完成", f"成功 {success} 个文件，失败 {error} 个文件"
        )

    def _on_fileset_selected(self, fileset: Fileset):
        """选中文件集后自动逐个加载全部 raw 文件，缓存 Sv 数据"""
        self._current_fileset = fileset
        self._file_cache.clear()
        self._raw_file_queue = list(fileset.files)
        self._raw_queue_index = 0

        if fileset.files:
            self.statusbar.set_status(
                f"文件集: {fileset.name} ({fileset.file_count} 个文件) — 自动加载中..."
            )
            self._load_file_and_cache(fileset.files[0])
        else:
            self.statusbar.set_status(
                f"文件集: {fileset.name} (空)"
            )

    def _load_file_and_cache(self, path: Path):
        """加载 raw → Sv，缓存结果，然后自动处理队列中下一个"""
        if not path.exists():
            logger.debug("File not found: %s, skipping", path)
            self._on_cache_load_error(f"文件不存在: {path.name}", path)
            return

        self.statusbar.show_progress(f"加载 [{self._raw_queue_index + 1}/{len(self._raw_file_queue)}]: {path.name}")

        if self._config is None:
            self._apply_default_config()
        assert self._config is not None
        if "sonar_model" not in self._config.get("processing", {}):
            self._config["processing"]["sonar_model"] = "EK80"

        logger.debug("Starting LoadFileWorker for %s", path.name)
        self._current_worker = LoadFileWorker(path, self._config)
        self._current_worker.finished.connect(lambda ed, p=path: self._on_cached_file_loaded(ed, p))
        self._current_worker.error.connect(lambda msg, p=path: self._on_cache_load_error(msg, p))
        self._current_worker.progress.connect(self.statusbar.set_status)
        self._current_worker.start()

    def _on_cached_file_loaded(self, echodata, path: Path):
        """文件加载完成 → 计算 Sv → 缓存"""
        self._echodata = echodata
        self.statusbar.show_progress(f"计算 Sv [{self._raw_queue_index + 1}/{len(self._raw_file_queue)}]: {path.name}")

        assert self._config is not None
        self._current_worker = ComputeSvWorker(echodata, self._config)
        self._current_worker.finished.connect(lambda ds, p=path: self._on_cached_sv_computed(ds, p))
        self._current_worker.error.connect(lambda msg, p=path: self._on_cache_load_error(msg, p))
        self._current_worker.progress.connect(self.statusbar.set_status)
        self._current_worker.start()

    def _apply_sv_to_display(self, ds_Sv, sv):
        """将 Sv 数据应用到显示：优化内存 + 更新渲染器"""
        from src.core.utils import log_memory_usage, optimize_array_dtype
        # 内存优化：float64 → float32
        sv = optimize_array_dtype(sv)
        self._ds_Sv = ds_Sv
        self._update_variable_list(ds_Sv, sv)
        self.echogram.set_data(sv)
        self._update_file_info(ds_Sv)
        self._update_surface_line_render()
        log_memory_usage("数据加载")

    def _on_cached_sv_computed(self, ds_Sv, path: Path):
        """Sv 计算完成 → 缓存 → 显示 → 自动加载下一个"""
        sv = squeeze_sv(ds_Sv["Sv"].values)

        # 缓存（只存 Sv+depth，噪声和底部由用户手动触发）
        self._file_cache[str(path)] = {
            "sv": sv.astype(np.float32),
            "ds": ds_Sv,
            "bottom": None,
            "noise_mask": None,
            "school_mask": None,
            "surface_depth_m": self._surface_depth_m,
        }

        is_first = (self._raw_queue_index == 0)
        if is_first:
            # 第一个文件：显示 + 更新变量列表
            self._apply_sv_to_display(ds_Sv, sv)
            self.statusbar.hide_progress()
            self.statusbar.set_status(
                f"文件 {1}/{len(self._raw_file_queue)}: {path.name} — Sv 计算完成"
            )

        # 加载下一个
        self._raw_queue_index += 1
        if self._raw_queue_index < len(self._raw_file_queue):
            next_path = self._raw_file_queue[self._raw_queue_index]
            self._load_file_and_cache(next_path)
        else:
            # 全部加载完成
            total = len(self._raw_file_queue)
            self.statusbar.hide_progress()
            self.statusbar.set_status(
                f"全部 {total} 个文件已缓存 — 右键 Echogram 翻页切换"
            )
            self._raw_queue_index = 0  # 重置

    def _on_cache_load_error(self, msg, path: Path):
        """某个文件加载失败，跳过继续"""
        self.statusbar.set_status(f"⚠ {path.name}: {msg}")
        self._raw_queue_index += 1
        if self._raw_queue_index < len(self._raw_file_queue):
            self._load_file_and_cache(self._raw_file_queue[self._raw_queue_index])

    def _switch_file(self, delta: int):
        """右键翻页 — 切换到上一个/下一个已缓存文件，恢复完整状态"""
        n_queue = len(self._raw_file_queue)
        n_cache = len(self._file_cache)
        logger.debug("_switch_file(delta=%d), queue=%d, cache=%d, idx=%d", delta, n_queue, n_cache, self._raw_queue_index)

        # 如果队列为空但有当前文件集，自动初始化
        if n_queue == 0 and self._current_fileset is not None:
            self._on_fileset_selected(self._current_fileset)
            n_queue = len(self._raw_file_queue)
            n_cache = len(self._file_cache)

        if n_queue == 0:
            self.statusbar.set_status("⚠ 没有已加载的文件，请先导入")
            return

        new_idx = self._raw_queue_index + delta
        if new_idx < 0 or new_idx >= n_queue:
            self.statusbar.set_status(f"已到边界 (文件 {self._raw_queue_index + 1}/{n_queue})")
            return
        self._raw_queue_index = new_idx
        path = self._raw_file_queue[new_idx]
        key = str(path)
        cached = self._file_cache.get(key)
        if cached is None:
            self.statusbar.set_status(f"⚠ {path.name} 尚未加载 (缓存: {n_cache}/{n_queue})，请等待")
            return

        self._ds_Sv = cached["ds"]
        sv = cached["sv"]
        logger.debug("Switching to %s, sv.shape=%s", path.name, sv.shape)

        # 恢复变量列表
        self._update_variable_list(cached["ds"], sv)

        # 显示当前选中的变量数据
        current_var = self.variable_list.currentItem()
        if current_var:
            key_name = self._display_to_key.get(current_var.text(), "Sv")
            display_data = self._variable_cache.get(key_name, sv)
            self.echogram.set_data(display_data)
        else:
            self.echogram.set_data(sv)

        # 恢复底线
        bottom = cached.get("bottom")
        if bottom is not None:
            self._bottom_line = bottom
            self.echogram.set_bottom_line(bottom)
        else:
            self._bottom_line = None
            self.echogram.set_bottom_line(None)

        # 恢复表线深度
        self._surface_depth_m = cached.get("surface_depth_m", 2.0)
        spin_surface = self.property_panel.processing.spin_surface
        spin_surface.blockSignals(True)
        spin_surface.setValue(self._surface_depth_m)
        spin_surface.blockSignals(False)
        self._update_surface_line_render()

        # 恢复噪声 mask
        self._noise_mask_manual = cached.get("noise_mask")
        self.echogram.set_noise_mask(self._noise_mask_manual)

        # 恢复鱼群 mask
        self._schools_mask = cached.get("school_mask")
        self.echogram.set_school_mask(self._schools_mask)

        # 重建分析区域（确保 _ds_Sv_analysis 与当前底线/表线一致）
        self._apply_analysis_region_to_ds()

        self.statusbar.set_status(
            f"文件 {new_idx + 1}/{n_queue}: {path.name}"
        )
        self.statusbar.set_file_info(f"[{new_idx + 1}/{n_queue}] {path.name}")

    def _on_channel_selected(self, channel: str):
        self._current_channel = channel
        self.statusbar.set_status(f"频率: {channel}")

    def _load_file(self, path: Path):
        """双击文件树中的文件 → 在已有队列中定位，不破坏缓存"""
        if not path.exists():
            QMessageBox.warning(self, "错误", f"文件不存在:\n{path}")
            return
        # 尝试在当前队列中定位
        key = str(path)
        for i, q in enumerate(self._raw_file_queue):
            if str(q) == key:
                self._raw_queue_index = i
                self._switch_file(0)
                return
        # 不在队列中 → 追加
        self._raw_file_queue.append(path)
        self._raw_queue_index = len(self._raw_file_queue) - 1
        self._load_file_and_cache(path)

    # ═══════════════════════════════════════════════════════
    # 变量列表统一管理
    # ═══════════════════════════════════════════════════════

    def _update_variable_list(self, ds_Sv, sv_raw=None):
        """统一更新变量列表和缓存映射。

        Parameters
        ----------
        ds_Sv : xr.Dataset
            数据集（可能包含 Sv 和 Sv_corrected）
        sv_raw : np.ndarray, optional
            原始 Sv 2D 数组。若为 None 则从 ds_Sv 提取。
        """
        self.variable_list.clear_variables()
        self._variable_cache.clear()
        self._display_to_key.clear()

        # 原始 Sv
        if sv_raw is None:
            sv_raw = ds_Sv["Sv"].values
            if sv_raw.ndim == 3:
                sv_raw = sv_raw[0]
        self._variable_cache["Sv"] = sv_raw
        self._display_to_key["Sv (原始)"] = "Sv"
        self.variable_list.add_variable("Sv", sv_raw, "Sv (原始)")

        # 去噪后 Sv_corrected
        if "Sv_corrected" in ds_Sv:
            sv_c = ds_Sv["Sv_corrected"].values
            if sv_c.ndim == 3:
                sv_c = sv_c[0]
            self._variable_cache["Sv_corrected"] = sv_c
            self._display_to_key["Sv (去噪)"] = "Sv_corrected"
            self.variable_list.add_variable("Sv_corrected", sv_c, "Sv (去噪)")

    def _save_file_state(self):
        """将当前文件的状态（底线、噪声、鱼群、表线）保存到缓存"""
        if not self._raw_file_queue or self._raw_queue_index >= len(self._raw_file_queue):
            return
        key = str(self._raw_file_queue[self._raw_queue_index])
        if key not in self._file_cache:
            return
        cache = self._file_cache[key]
        cache["bottom"] = self._bottom_line
        cache["noise_mask"] = self._noise_mask_manual
        cache["school_mask"] = self._schools_mask
        cache["surface_depth_m"] = self._surface_depth_m

    # ═══════════════════════════════════════════════════════
    # 处理流水线
    # ═══════════════════════════════════════════════════════

    def _compute_sv(self):
        if self._echodata is None or self._config is None:
            return
        self.pipeline_step.emit("计算 Sv")
        self.statusbar.show_progress("计算 Sv...")
        self._current_worker = ComputeSvWorker(self._echodata, self._config)
        self._current_worker.finished.connect(self._on_sv_computed)
        self._current_worker.error.connect(self._on_worker_error)
        self._current_worker.progress.connect(self.statusbar.set_status)
        self._current_worker.start()

    def _on_sv_computed(self, ds_Sv):
        self._ds_Sv = ds_Sv
        self.statusbar.hide_progress()
        self.statusbar.set_status("Sv 计算完成")

        sv = squeeze_sv(ds_Sv["Sv"].values)

        self._apply_sv_to_display(ds_Sv, sv)

        # 链式处理
        if getattr(self, "_run_all_chain", False):
            QTimer.singleShot(200, self._apply_noise_params)

    def _on_noise_params_changed(self, params):
        self._noise_timer.start()

    def _apply_noise_params(self):
        if self._ds_Sv is None or self._config is None:
            return
        # 从 UI 同步噪声参数到 config
        self._config.setdefault("processing", {})["noise_removal"] = (
            self.property_panel.processing.get_noise_config()
        )
        self.pipeline_step.emit("噪声去除")
        self.statusbar.show_progress("去除噪声...")
        self._current_worker = NoiseRemovalWorker(
            self._ds_Sv, self._config, self._noise_mask_manual
        )
        self._current_worker.finished.connect(self._on_noise_removed)
        self._current_worker.error.connect(self._on_worker_error)
        self._current_worker.start()

    def _on_noise_removed(self, ds_Sv):
        self._ds_Sv = ds_Sv
        self.statusbar.hide_progress()

        # 更新变量列表（保留原始 Sv，新增 Sv_corrected）
        sv_raw = ds_Sv["Sv"].values
        if sv_raw.ndim == 3:
            sv_raw = sv_raw[0]
        self._update_variable_list(ds_Sv, sv_raw)

        # 显示去噪后的数据
        if "Sv_corrected" in ds_Sv:
            sv_display = ds_Sv["Sv_corrected"].values
            if sv_display.ndim == 3:
                sv_display = sv_display[0]
            self.echogram.set_data(sv_display)
            self.statusbar.set_status("噪声去除完成（显示去噪数据，原始 Sv 已保留）")
        else:
            self.echogram.set_data(sv_raw)
            self.statusbar.set_status("噪声去除完成")

        # 同步更新缓存中当前文件的 ds
        if self._raw_file_queue and self._raw_queue_index < len(self._raw_file_queue):
            key = str(self._raw_file_queue[self._raw_queue_index])
            if key in self._file_cache:
                self._file_cache[key]["ds"] = ds_Sv

        if getattr(self, "_run_all_chain", False):
            QTimer.singleShot(200, self._detect_bottom)

    def _detect_bottom(self):
        if self._ds_Sv is None or self._config is None:
            QMessageBox.warning(self, "警告", "请先加载数据")
            return
        # 同步 UI 参数到 config
        self._config.setdefault("processing", {})["bottom_detection"] = {
            **self._config.get("processing", {}).get("bottom_detection", {}),
            **self.property_panel.processing.get_bottom_config(),
        }
        self.pipeline_step.emit("底部检测")
        self.statusbar.show_progress("检测底部...")
        self._current_worker = DetectSeafloorWorker(self._ds_Sv, self._config)
        self._current_worker.finished.connect(self._on_bottom_detected)
        self._current_worker.error.connect(self._on_worker_error)
        self._current_worker.progress.connect(self.statusbar.set_status)
        self._current_worker.start()

    def _on_bottom_detected(self, bottom):
        self._bottom_line = np.asarray(bottom, dtype=np.float32)
        self.echogram.set_bottom_line(self._bottom_line)
        self.statusbar.hide_progress()

        # 缓存底线到当前文件
        self._save_file_state()

        # 自动启用分析区域（表线~底线）
        self._analysis_region_enabled = True
        self.echogram.set_analysis_region_enabled(True)
        self._apply_analysis_region_to_ds()

        self.statusbar.set_status("底部检测完成 — 分析区域已启用，已进入绘制底线模式")

        # 自动切换到绘制底线模式（blockSignals 避免干扰链式处理）
        if not getattr(self, "_run_all_chain", False):
            self.echo_toolbar.mode_combo.blockSignals(True)
            self.echo_toolbar.mode_combo.setCurrentIndex(2)  # DRAW_BOTTOM
            self.echo_toolbar.mode_combo.blockSignals(False)
            self.echogram.set_mouse_mode(MouseMode.DRAW_BOTTOM.value)

        if getattr(self, "_run_all_chain", False):
            QTimer.singleShot(200, self._detect_schools)

    def _on_bottom_line_edited(self, bottom):
        self._bottom_line = bottom
        self.echogram.set_bottom_line(bottom)
        self._save_file_state()
        self._apply_analysis_region_to_ds()
        self.statusbar.set_status("底线已手动更新")

    def _start_draw_bottom(self):
        """切换到绘制底线模式"""
        self.echo_toolbar.mode_combo.blockSignals(True)
        self.echo_toolbar.mode_combo.setCurrentIndex(2)  # DRAW_BOTTOM
        self.echo_toolbar.mode_combo.blockSignals(False)
        self.echogram.set_mouse_mode(MouseMode.DRAW_BOTTOM.value)
        self.statusbar.set_status("绘制底线模式：左键拖动绘制，右键完成")

    def _on_update_bottom(self):
        """右键 → 更新底线：显式保存当前底线状态"""
        bottom = self.echogram.get_bottom_line()
        if bottom is not None:
            self._bottom_line = bottom
            self._save_file_state()
            self._apply_analysis_region_to_ds()
            self.statusbar.set_status("底线已更新并保存")

    def _on_surface_line_changed(self, depth_m: float):
        """表线深度变更"""
        self._surface_depth_m = depth_m
        self._update_surface_line_render()
        self._save_file_state()
        self._apply_analysis_region_to_ds()

    def _surface_depth_to_sample(self) -> float | None:
        """将表线深度(m)转为 sample index，用于后端分析区域限定。"""
        if self._ds_Sv is None:
            return None
        from src.core.region import get_surface_sample
        return get_surface_sample(self._ds_Sv, self._surface_depth_m)

    def _apply_analysis_region_to_ds(self):
        """根据分析区域（表线~底线）裁剪 ds_Sv，生成 _ds_Sv_analysis。"""
        if not self._analysis_region_enabled or self._ds_Sv is None:
            self._ds_Sv_analysis = None
            return

        from src.core.region import crop_sv_by_region
        self._ds_Sv_analysis = crop_sv_by_region(
            self._ds_Sv,
            surface_depth_m=self._surface_depth_m if self._surface_depth_m > 0 else None,
            bottom_sample_indices=self._bottom_line,
        )

    def _get_analysis_ds(self):
        """返回当前应使用的 ds_Sv：分析区域开启时返回裁剪版本，否则返回完整版本。"""
        if self._analysis_region_enabled and self._ds_Sv_analysis is not None:
            return self._ds_Sv_analysis
        return self._ds_Sv

    def _update_surface_line_render(self):
        """将表线深度(m)转为 sample index 并传给渲染器"""
        idx = self._surface_depth_to_sample()
        if idx is not None:
            self.echogram.set_surface_line(float(idx))

    def _on_surface_line_dialog(self):
        """右键 → 弹出设置表线深度对话框"""
        val, ok = QInputDialog.getDouble(
            self, "设置表线深度",
            "表线深度（离水面多少米）：",
            self._surface_depth_m, 0, 50, 1
        )
        if ok:
            self._surface_depth_m = val
            self.property_panel.processing.spin_surface.setValue(val)
            self._update_surface_line_render()
            self._apply_analysis_region_to_ds()
            self.statusbar.set_status(f"表线深度: {val:.1f} m")

    def _on_analysis_region_toggle(self, enabled: bool):
        """切换分析区域限定：开启时裁剪 ds_Sv，关闭时恢复完整数据"""
        self._analysis_region_enabled = enabled
        self.echogram.set_analysis_region_enabled(enabled)
        self._apply_analysis_region_to_ds()
        if enabled:
            if self._ds_Sv_analysis is not None:
                n_pings = len(self._ds_Sv_analysis["ping_time"])
                n_samples = len(self._ds_Sv_analysis["range_sample"])
                self.statusbar.set_status(
                    f"分析区域限定已开启: {n_pings}×{n_samples} 样本"
                )
            else:
                self.statusbar.set_status("分析区域限定已开启（需要底线）")
        else:
            self.statusbar.set_status("分析区域限定已关闭")

    def _detect_schools(self):
        if self._ds_Sv is None or self._config is None:
            QMessageBox.warning(self, "警告", "请先加载数据")
            return
        # 同步 UI 参数到 config
        self._config.setdefault("school_detection", {}).update(
            self.property_panel.processing.get_school_config()
        )
        self.pipeline_step.emit("鱼群检测")
        self.statusbar.show_progress("检测鱼群...")
        ds_for_detect = self._get_analysis_ds()
        self._current_worker = DetectSchoolsWorker(ds_for_detect, self._config)
        self._current_worker.finished.connect(self._on_schools_detected)
        self._current_worker.error.connect(self._on_worker_error)
        self._current_worker.start()

    def _on_schools_detected(self, mask, df):
        self._schools_mask = mask.values
        self._schools_df = df
        self.echogram.set_school_mask(self._schools_mask)
        self.stats_dialog.update_schools(df)
        self.property_panel.stats.update_schools(df)
        self.statusbar.hide_progress()
        self.statusbar.set_status(f"检测到 {len(df)} 个鱼群")

        # 缓存鱼群状态
        self._save_file_state()

        for _, row in df.iterrows():
            self.region_table.add_region(
                name=f"鱼群 {int(row.get('school_id', 0))}",
                region_type="鱼群",
                ping_range=f"{row.get('ping_start', 0)}-{row.get('ping_end', 0)}",
                depth_range=f"{row.get('depth_start', 0):.1f}-{row.get('depth_end', 0):.1f} m",
                area=row.get("area", 0),
                mean_sv=row.get("mean_sv", 0),
            )

        if getattr(self, "_run_all_chain", False):
            QTimer.singleShot(200, self._compute_density)

    def _compute_density(self):
        if self._ds_Sv is None or self._config is None:
            QMessageBox.warning(self, "警告", "请先加载数据")
            return
        # 同步 UI 参数到 config
        density_ui = self.property_panel.processing.get_density_config()
        self._config.setdefault("density", {}).update(density_ui)
        self.pipeline_step.emit("密度估算")
        schools_df = self._schools_df if self._schools_df is not None else pd.DataFrame()
        self.statusbar.show_progress("计算密度...")
        ds_for_density = self._get_analysis_ds()
        self._current_worker = DensityWorker(schools_df, ds_for_density, self._config)
        self._current_worker.finished.connect(self._on_density_computed)
        self._current_worker.error.connect(self._on_worker_error)
        self._current_worker.start()

    def _on_density_computed(self, df):
        self._density_df = df
        self.stats_dialog.update_density(df)
        self.property_panel.stats.update_density(df)
        self.statusbar.hide_progress()
        self.statusbar.set_status("密度计算完成")
        self._run_all_chain = False
        self.pipeline_done.emit()

    def _run_all(self):
        if self._echodata is None or self._run_all_chain:
            QMessageBox.warning(self, "警告", "请先加载文件")
            return
        self._run_all_chain = True
        self._compute_sv()

    def _show_stats(self):
        """显示统计对话框"""
        self.stats_dialog.show()
        self.stats_dialog.raise_()
        self.stats_dialog.activateWindow()

    def _run_grid_analysis(self):
        if self._ds_Sv is None or self._config is None:
            QMessageBox.warning(self, "警告", "请先加载数据")
            return
        grid_cfg = self.property_panel.processing.get_grid_config()
        density_cfg = self.property_panel.processing.get_density_config()
        self.statusbar.show_progress("网格分析...")
        self._current_worker = GridWorker(
            self._get_analysis_ds(), self._surface_depth_m, grid_cfg, density_cfg
        )
        self._current_worker.finished.connect(self._on_grid_done)
        self._current_worker.error.connect(self._on_worker_error)
        self._current_worker.progress.connect(self.statusbar.set_status)
        self._current_worker.start()

    def _on_grid_done(self, df):
        self._grid_df = df
        self.stats_dialog.update_grid(df)
        self.statusbar.hide_progress()
        self.statusbar.set_status(f"网格分析完成: {len(df)} 个单元")
        # 网格颜色叠加到回波图
        self.echogram.set_grid_data(df, self._ds_Sv, color_by="mean_sv")
        # 显示统计对话框
        self._show_stats()

    # ═══════════════════════════════════════════════════════
    # 质量检查
    # ═══════════════════════════════════════════════════════

    def _run_quality_check(self):
        """运行数据质量检查"""
        if self._ds_Sv is None:
            QMessageBox.warning(self, "警告", "请先加载数据")
            return
        self.statusbar.show_progress("正在检查数据质量...")
        self._current_worker = QualityCheckWorker(
            self._get_analysis_ds(), self._bottom_line
        )
        self._current_worker.finished.connect(self._on_quality_done)
        self._current_worker.error.connect(self._on_worker_error)
        self._current_worker.progress.connect(self.statusbar.set_status)
        self._current_worker.start()

    def _on_quality_done(self, result):
        """质量检查完成 → 弹窗显示结果"""
        self.statusbar.hide_progress()
        sv_check = result.get("sv", {})
        bl_check = result.get("bottom")

        lines = ["═══ 数据质量检查报告 ═══\n"]

        # Sv 检查
        valid_icon = "✅" if sv_check.get("valid") else "⚠️"
        lines.append(f"{valid_icon} Sv 数据: {sv_check.get('total_pings', 0)} pings × {sv_check.get('total_samples', 0)} samples")
        sv_range = sv_check.get("sv_range", (0, 0))
        lines.append(f"   Sv 范围: [{sv_range[0]:.1f}, {sv_range[1]:.1f}] dB")
        lines.append(f"   NaN 比例: {sv_check.get('nan_ratio', 0):.1%}")
        for w in sv_check.get("warnings", []):
            lines.append(f"   ⚠ {w}")

        # 底线检查
        if bl_check:
            lines.append("")
            bl_icon = "✅" if bl_check.get("valid") else "⚠️"
            lines.append(f"{bl_icon} 底线: {bl_check.get('valid_pings', 0)} 个有效 ping")
            lines.append(f"   NaN 比例: {bl_check.get('nan_ratio', 0):.1%}")
            for w in bl_check.get("warnings", []):
                lines.append(f"   ⚠ {w}")

        all_valid = sv_check.get("valid", False) and (bl_check is None or bl_check.get("valid", False))
        title = "质量检查通过 ✅" if all_valid else "质量检查发现问题 ⚠️"
        QMessageBox.information(self, title, "\n".join(lines))

    # ═══════════════════════════════════════════════════════
    # 多频分析
    # ═══════════════════════════════════════════════════════

    def _run_multifreq_analysis(self):
        """运行多频率分析"""
        if self._ds_Sv is None or self._config is None:
            QMessageBox.warning(self, "警告", "请先加载数据")
            return
        self.statusbar.show_progress("正在分析多频率通道...")
        self._current_worker = MultifreqAnalysisWorker(
            self._ds_Sv, self._config
        )
        self._current_worker.finished.connect(self._on_multifreq_done)
        self._current_worker.error.connect(self._on_worker_error)
        self._current_worker.progress.connect(self.statusbar.set_status)
        self._current_worker.start()

    def _on_multifreq_done(self, result):
        """多频分析完成 → 弹窗显示结果"""
        self.statusbar.hide_progress()
        channel_summary = result.get("channel_summary")
        freq_comparison = result.get("freq_comparison")
        channels = result.get("channels", [])

        lines = ["═══ 多频率分析报告 ═══\n"]
        lines.append(f"通道数: {len(channels)}\n")

        # 通道摘要
        if channel_summary is not None and not channel_summary.empty:
            lines.append("── 通道信息 ──")
            for _, row in channel_summary.iterrows():
                freq_mhz = row.get("frequency_Hz", 0) / 1e6 if row.get("frequency_Hz") else 0
                lines.append(f"  {row['channel']}: {freq_mhz:.1f} MHz, {row.get('n_pings', 0)} pings")

        # 频率对比
        if freq_comparison is not None and not freq_comparison.empty:
            lines.append("\n── 频率对比（ABC）──")
            for _, row in freq_comparison.iterrows():
                freq_mhz = row.get("frequency_Hz", 0) / 1e6 if row.get("frequency_Hz") else 0
                lines.append(f"  {row['channel']}: mean_abc={row.get('mean_abc', 0):.4f}")

        QMessageBox.information(self, "多频率分析", "\n".join(lines))

    # ═══════════════════════════════════════════════════════
    # 单体目标检测
    # ═══════════════════════════════════════════════════════

    def _run_single_target_detection(self):
        """运行单体目标检测"""
        if self._ds_Sv is None or self._config is None:
            QMessageBox.warning(self, "警告", "请先加载数据")
            return
        self.statusbar.show_progress("正在检测单体目标...")
        self._current_worker = SingleTargetWorker(
            self._get_analysis_ds(), self._config
        )
        self._current_worker.finished.connect(self._on_single_target_done)
        self._current_worker.error.connect(self._on_worker_error)
        self._current_worker.progress.connect(self.statusbar.set_status)
        self._current_worker.start()

    def _on_single_target_done(self, targets_df):
        """单体目标检测完成"""
        self.statusbar.hide_progress()
        n = len(targets_df) if targets_df is not None and not targets_df.empty else 0
        if n == 0:
            QMessageBox.information(self, "单体目标检测", "未检测到单体目标\n尝试降低 sv_threshold_db 参数")
            return
        lines = ["═══ 单体目标检测结果 ═══\n", f"检测到 {n} 个目标\n"]
        if not targets_df.empty:
            ts_col = "ts_db" if "ts_db" in targets_df.columns else None
            if ts_col:
                ts_valid = targets_df[ts_col].dropna()
                if len(ts_valid) > 0:
                    lines.append("TS 统计:")
                    lines.append(f"  均值: {ts_valid.mean():.1f} dB")
                    lines.append(f"  中位: {ts_valid.median():.1f} dB")
                    lines.append(f"  范围: [{ts_valid.min():.1f}, {ts_valid.max():.1f}] dB")
            lines.append(f"\n目标列: {', '.join(targets_df.columns[:8])}")
        QMessageBox.information(self, "单体目标检测", "\n".join(lines))

    # ═══════════════════════════════════════════════════════
    # Sv 统计摘要
    # ═══════════════════════════════════════════════════════

    def _run_sv_stats(self):
        """Sv 统计摘要"""
        if self._ds_Sv is None:
            QMessageBox.warning(self, "警告", "请先加载数据")
            return
        self.statusbar.show_progress("计算 Sv 统计...")
        self._current_worker = SvStatsWorker(self._get_analysis_ds())
        self._current_worker.finished.connect(self._on_sv_stats_done)
        self._current_worker.error.connect(self._on_worker_error)
        self._current_worker.progress.connect(self.statusbar.set_status)
        self._current_worker.start()

    def _on_sv_stats_done(self, result):
        self.statusbar.hide_progress()
        if result is None or result.empty:
            QMessageBox.information(self, "Sv 统计", "无统计结果")
            return
        lines = ["═══ Sv 统计摘要 ═══\n"]
        for _, row in result.iterrows():
            lines.append(f"Transect {row.get('transect_id', '?')}: {row.get('n_pings', 0)} pings")
            lines.append(f"  均值: {row.get('mean_sv', 0):.1f} dB, 中位: {row.get('median_sv', 0):.1f} dB")
            lines.append(f"  P5~P95: [{row.get('p5_sv', 0):.1f}, {row.get('p95_sv', 0):.1f}] dB")
            lines.append(f"  NaN: {row.get('nan_ratio', 0):.1%}")
        QMessageBox.information(self, "Sv 统计", "\n".join(lines))

    # ═══════════════════════════════════════════════════════
    # Transect 分段
    # ═══════════════════════════════════════════════════════

    def _run_transect_split(self):
        """Transect 分段"""
        if self._ds_Sv is None:
            QMessageBox.warning(self, "警告", "请先加载数据")
            return
        self.statusbar.show_progress("分段中...")
        self._current_worker = TransectSplitWorker(self._get_analysis_ds())
        self._current_worker.finished.connect(self._on_transect_split_done)
        self._current_worker.error.connect(self._on_worker_error)
        self._current_worker.progress.connect(self.statusbar.set_status)
        self._current_worker.start()

    def _on_transect_split_done(self, result):
        self.statusbar.hide_progress()
        n = result.get("n_transects", 0)
        QMessageBox.information(self, "Transect 分段", f"分段完成：共 {n} 个 transect")

    def _update_file_info(self, ds_Sv):
        """更新状态栏文件信息"""
        if ds_Sv is None:
            return
        info_parts = []
        if "channel" in ds_Sv:
            info_parts.append(str(ds_Sv["channel"].values[0]))
        if "ping_time" in ds_Sv:
            n_pings = len(ds_Sv["ping_time"])
            info_parts.append(f"{n_pings} pings")
        if "range_sample" in ds_Sv:
            n_samples = len(ds_Sv["range_sample"])
            info_parts.append(f"{n_samples} samples")
        self.statusbar.set_status(" | ".join(info_parts))
        # 同步属性面板文件信息
        self.property_panel.file_info.update_info(ds_Sv)

    # ═══════════════════════════════════════════════════════
    # 交互
    # ═══════════════════════════════════════════════════════

    def _on_mode_changed(self, mode: MouseMode):
        self._current_mode = mode
        self.statusbar.set_status(f"模式: {mode.name}")

    def _update_depth_at_cursor(self, ping: float, sample: float):
        """将 sample index 转为实际深度(m)并更新状态栏"""
        if self._ds_Sv is None:
            return
        if "echo_range" in self._ds_Sv:
            er = self._ds_Sv["echo_range"]
            if "channel" in er.dims:
                er = er.isel(channel=0)
            er_vals = er.values
            if er_vals.ndim == 2:
                er_vals = er_vals[:, 0]
            idx = int(round(sample))
            if 0 <= idx < len(er_vals):
                self.statusbar.set_depth_info(float(er_vals[idx]))
            else:
                self.statusbar.set_depth_info(float('nan'))
        else:
            self.statusbar.set_depth_info(float('nan'))

    def _on_region_selected(self, x1, y1, x2, y2):
        if self._current_mode == MouseMode.SELECT_NOISE:
            self._add_noise_region(x1, y1, x2, y2)
        elif self._current_mode == MouseMode.INSPECT:
            self._inspect_region(x1, y1, x2, y2)

    def _add_noise_region(self, x1, y1, x2, y2):
        if self._ds_Sv is None:
            return
        sv = squeeze_sv(self._ds_Sv["Sv"].values)
        h, w = sv.shape

        if self._noise_mask_manual is None:
            self._noise_mask_manual = np.zeros((h, w), dtype=bool)

        px1 = max(0, int(min(x1, x2)))
        py1 = max(0, int(min(y1, y2)))
        px2 = min(h, int(max(x1, x2)))
        py2 = min(w, int(max(y1, y2)))

        self._noise_mask_manual[px1:px2, py1:py2] = True
        self._undo_stack.append(("noise_mask", self._noise_mask_manual.copy()))
        self._redo_stack.clear()

        self.echogram.set_noise_mask(self._noise_mask_manual)
        self.region_table.add_region(
            name="噪声区域", region_type="噪声",
            ping_range=f"{px1}-{px2}", depth_range=f"{py1}-{py2}",
            area=(px2 - px1) * (py2 - py1), mean_sv=0.0,
        )
        self._save_file_state()
        self._apply_noise_params()

    def _inspect_region(self, x1, y1, x2, y2):
        if self._ds_Sv is None:
            return
        sv = squeeze_sv(self._ds_Sv["Sv"].values)

        px1, px2 = int(min(x1, x2)), int(max(x1, x2))
        py1, py2 = int(min(y1, y2)), int(max(y1, y2))
        px1, py1 = max(0, px1), max(0, py1)
        px2 = min(sv.shape[0], px2)
        py2 = min(sv.shape[1], py2)

        if px2 <= px1 or py2 <= py1:
            return

        region_data = sv[px1:px2, py1:py2]
        valid = region_data[~np.isnan(region_data)]
        if len(valid) == 0:
            return

        mean_sv = float(np.mean(valid))
        self.region_table.add_region(
            name="检查区域", region_type="检查",
            ping_range=f"{px1}-{px2}", depth_range=f"{py1}-{py2}",
            area=(px2 - px1) * (py2 - py1), mean_sv=mean_sv,
        )
        self.statusbar.set_status(f"区域 Sv 平均值: {mean_sv:.1f} dB")

    def _on_region_deleted(self, region_id: int):
        self.region_table.remove_region(region_id)

    def _on_variable_selected(self, display_name: str):
        # 变量列表显示 "Sv (原始)"，缓存 key 是 "Sv"
        key = self._display_to_key.get(display_name, display_name)
        data = self._variable_cache.get(key)
        if data is not None:
            self.echogram.set_data(data)

    # ═══════════════════════════════════════════════════════
    # 撤销/重做
    # ═══════════════════════════════════════════════════════

    def _undo(self):
        if not self._undo_stack:
            return
        action_type, data = self._undo_stack.pop()
        if action_type == "noise_mask":
            current = self._noise_mask_manual.copy() if self._noise_mask_manual is not None else None
            self._redo_stack.append(("noise_mask", current))
            self._noise_mask_manual = data
            self.echogram.set_noise_mask(data)
            self.statusbar.set_status("已撤销")

    def _redo(self):
        if not self._redo_stack:
            return
        action_type, data = self._redo_stack.pop()
        if action_type == "noise_mask":
            current = self._noise_mask_manual.copy() if self._noise_mask_manual is not None else None
            self._undo_stack.append(("noise_mask", current))
            self._noise_mask_manual = data
            self.echogram.set_noise_mask(data)
            self.statusbar.set_status("已重做")

    # ═══════════════════════════════════════════════════════
    # 视图
    # ═══════════════════════════════════════════════════════

    def _reset_view(self):
        self.echogram.reset_view()

    def _fit_view(self):
        self.echogram.reset_view()

    def _clear_noise_regions(self):
        self._noise_mask_manual = None
        self.echogram.set_noise_mask(None)
        self._save_file_state()
        self.statusbar.set_status("已清除噪声区域")

    def _clear_schools(self):
        self._schools_mask = None
        self._schools_df = None
        self.echogram.set_school_mask(None)
        self._save_file_state()
        self.statusbar.set_status("已清除鱼群显示")

    # ═══════════════════════════════════════════════════════
    # 导出
    # ═══════════════════════════════════════════════════════

    def _export(self):
        dlg = ExportDialog(self)
        if dlg.exec() != ExportDialog.Accepted:
            return

        from src.core.export import (
            export_density_to_csv,
            export_schools_to_csv,
        )
        from src.core.utils import get_output_dir

        formats = dlg.get_formats()
        content = dlg.get_content()
        if not formats:
            QMessageBox.warning(self, "警告", "请至少选择一种导出格式")
            return

        output_dir = get_output_dir(self._config)
        exported = []

        # 按内容导出
        if content.get("sv") and self._ds_Sv is not None:
            from src.core.export import (
                export_sv_to_csv,
                export_to_excel,
                export_to_netcdf,
            )
            if "netcdf" in formats:
                exported.append(export_to_netcdf(self._get_analysis_ds(), output_dir / "sv_data.nc"))
            if "csv" in formats:
                exported.append(export_sv_to_csv(self._get_analysis_ds(), output_dir / "sv_data.csv"))

        if content.get("schools") and self._schools_df is not None and not self._schools_df.empty:
            if "csv" in formats:
                exported.append(export_schools_to_csv(self._schools_df, output_dir / "schools.csv"))

        if content.get("density") and self._density_df is not None and not self._density_df.empty:
            if "csv" in formats:
                exported.append(export_density_to_csv(self._density_df, output_dir / "density.csv"))

        if content.get("grid") and hasattr(self, '_grid_df') and self._grid_df is not None:
            if "csv" in formats:
                exported.append(export_density_to_csv(self._grid_df, output_dir / "grid_stats.csv"))

        if "excel" in formats:
            schools = self._schools_df if content.get("schools") else None
            density = self._density_df if content.get("density") else None
            from src.core.export import export_to_excel
            exported.append(export_to_excel(schools, density, output_dir / "results.xlsx"))

        self.statusbar.set_status(f"导出完成: {len(exported)} 个文件 → {output_dir}")

    def _export_schools(self):
        if self._schools_df is None or self._schools_df.empty:
            QMessageBox.warning(self, "警告", "请先检测鱼群")
            return
        path, _ = QFileDialog.getSaveFileName(self, "导出鱼群 CSV", "", "CSV (*.csv)")
        if path:
            self._schools_df.to_csv(path, index=False, encoding="utf-8-sig")
            self.statusbar.set_status(f"鱼群清单导出: {path}")

    # ═══════════════════════════════════════════════════════
    # 其他
    # ═══════════════════════════════════════════════════════

    def _show_about(self):
        QMessageBox.about(self, "关于 Echogram",
            "<h3>Echogram</h3>"
            "<p>鱼类声学资源评估系统 v2.0</p>"
            "<p>基于 echopype + PySide6 + OpenGL</p>"
            "<p>参照 Echoview 界面设计</p>"
            "<hr>"
            "<p><b>功能:</b></p>"
            "<ul>"
            "<li>EK80 多频段 raw 数据批量导入</li>"
            "<li>Sv 校准 + 噪声去除 + 底部检测</li>"
            "<li>鱼群自动识别 (Echoview 算法)</li>"
            "<li>密度/生物量估算</li>"
            "<li>高性能 OpenGL echogram 渲染</li>"
            "</ul>"
        )

    def _on_worker_error(self, msg):
        self._run_all_chain = False
        self.statusbar.hide_progress()
        self.statusbar.set_status(f"错误: {msg}")
        QMessageBox.critical(self, "处理错误", msg)
