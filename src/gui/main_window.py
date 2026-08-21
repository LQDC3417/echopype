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

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QDockWidget,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.gui.i18n import T, set_language
from src.gui.property_panel import PropertyPanel
from src.gui.region_panel import RegionBrowserWidget
from src.gui.stats_dialog import StatsDialog
from src.gui.status_bar import MainStatusBar
from src.gui.toolbars import EchogramToolBar, MouseMode, StandardToolBar
from src.viz.opengl_renderer import EchogramRenderer

from src.gui.handlers import (
    FileMixin,
    ProcessingMixin,
    AnalysisMixin,
    InteractionMixin,
)

logger = logging.getLogger(__name__)


class _LogBridge(QObject):
    """信号桥：后台线程 → 主线程日志面板"""
    log_record = Signal(str)


class _QtLogHandler(logging.Handler):
    """线程安全的 logging Handler：通过 Qt 信号将日志从任意线程桥接到主线程"""

    def __init__(self):
        super().__init__()
        self._bridge = _LogBridge()

    @property
    def log_record(self):
        return self._bridge.log_record

    def emit(self, record):
        try:
            msg = self.format(record)
            self._bridge.log_record.emit(msg)
        except Exception:
            self.handleError(record)


class MainWindow(QMainWindow, FileMixin, ProcessingMixin, AnalysisMixin, InteractionMixin):
    """Echoview 风格主窗口 — 鱼类声学资源评估系统"""

    # 流水线进度信号
    pipeline_step = Signal(str)       # 步骤名称
    pipeline_done = Signal()          # 全部完成

    def __init__(self):
        super().__init__()
        self.setWindowTitle(T("app_title"))
        self.setMinimumSize(1400, 900)

        # ── 状态 ──
        self._config: dict | None = None
        self._echodata = None
        self._ds_Sv = None            # 完整 Sv（含水底数据）
        self._ds_Sv_analysis = None   # 分析区域裁剪后的 Sv（表线~底线）
        self._noise_mask_manual = None
        self._bottom_line = None
        self._bottom_manually_edited = False  # 底线是否被手动编辑过
        self._surface_depth_m = 2.0  # 表线深度（米）
        self._analysis_region_enabled = False  # 分析区域限定（仅控制 UI 渲染，不影响分析裁剪）
        self._schools_mask = None
        self._schools_df = None
        self._current_worker = None
        self._current_channel = ""
        self._undo_stack = []
        self._redo_stack = []
        self._current_mode = MouseMode.NAVIGATE
        self._run_all_chain = False
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
        fm = mb.addMenu(T("menu_file"))
        fm.addAction(self._act(T("import_raw_files"), self._import_raw, "Ctrl+I"))
        fm.addAction(self._act(T("open_config"), self._open_config, "Ctrl+O"))
        fm.addAction(self._act(T("save_config"), self._save_config, "Ctrl+Shift+S"))
        fm.addSeparator()
        fm.addAction(self._act(T("menu_export"), self._export, "Ctrl+E"))
        fm.addSeparator()
        fm.addAction(self._act(T("quit"), self.close, "Ctrl+Q"))

        # ── 编辑 ──
        em = mb.addMenu(T("menu_edit"))
        em.addAction(self._act(T("undo"), self._undo, "Ctrl+Z"))
        em.addAction(self._act(T("redo"), self._redo, "Ctrl+Y"))
        em.addSeparator()
        em.addAction(self._act(T("clear_noise"), self._clear_noise_regions))
        em.addAction(self._act(T("clear_schools"), self._clear_schools))

        # ── 显示 ──
        vm = mb.addMenu(T("menu_view"))
        vm.addAction(self._act(T("reset_view"), self._reset_view))
        vm.addAction(self._act(T("fit_view"), self._fit_view))
        vm.addSeparator()
        self._act_noise = self._checkable(T("show_noise_overlay"), True)
        self._act_school = self._checkable(T("show_school_overlay"), True)
        self._act_bottom = self._checkable(T("show_bottom_line"), True)
        vm.addAction(self._act_noise)
        vm.addAction(self._act_school)
        vm.addAction(self._act_bottom)
        vm.addSeparator()

        # 语言切换子菜单
        lang_menu = vm.addMenu(T("menu_language"))
        act_zh = QAction(T("lang_zh"), self)
        act_zh.triggered.connect(lambda: self._switch_language("zh"))
        lang_menu.addAction(act_zh)
        act_en = QAction(T("lang_en"), self)
        act_en.triggered.connect(lambda: self._switch_language("en"))
        lang_menu.addAction(act_en)

        # ── 处理 ──
        pm = mb.addMenu(T("menu_process"))
        pm.addAction(self._act(T("run_all"), self._run_all, "F5"))
        pm.addAction(self._act(T("batch_process"), self._batch_process_files, "Ctrl+B"))
        pm.addSeparator()
        pm.addAction(self._act(T("compute_sv"), self._compute_sv, "Ctrl+1"))
        pm.addAction(self._act(T("noise_removal"), self._apply_noise_params, "Ctrl+2"))
        pm.addAction(self._act(T("detect_bottom"), self._detect_bottom, "Ctrl+3"))
        pm.addAction(self._act(T("detect_schools"), self._detect_schools, "Ctrl+4"))

        # ── 分析 ──
        am = mb.addMenu(T("menu_analysis"))
        am.addAction(self._act(T("menu_integration"), self._run_integration))
        am.addAction(self._act(T("btn_real_sed"), self._run_real_sed))
        am.addSeparator()
        am.addAction(self._act(T("menu_export_schools"), self._export_schools))

        # ── 帮助 ──
        hm = mb.addMenu(T("menu_help"))
        hm.addAction(self._act(T("about"), self._show_about))

    def _register_dock_view_actions(self):
        """将各 Dock 的显示/隐藏切换加入视图菜单"""
        vm = None
        for a in self.menuBar().actions():
            if a.text() == T("menu_view"):
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

        # ── 中央：View Tab 容器 ──
        self.echogram = EchogramRenderer()
        self.view_tabs = QTabWidget()
        self.view_tabs.addTab(self.echogram, T("view_tab", n=1))
        self.setCentralWidget(self.view_tabs)

        # ── 左侧 Dock：变量列表面板 ──
        from src.gui.left_panel import LeftPanel
        self.left_panel = LeftPanel()
        self.variable_list = self.left_panel.variable_list

        self.dock_left = QDockWidget(T("fileset_ctrl_title"), self)
        self.dock_left.setObjectName("dockVariables")
        self.dock_left.setWidget(self.left_panel)
        self.dock_left.setFeatures(
            QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable
        )
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_left)

        # ── 右侧 Dock：属性面板 ──
        self.property_panel = PropertyPanel()
        self.dock_right = QDockWidget(T("tab_processing"), self)
        self.dock_right.setObjectName("dockProperties")
        self.dock_right.setWidget(self.property_panel)
        self.dock_right.setFeatures(
            QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable
        )
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_right)

        # ── 底部 Dock：区域浏览器 + 消息日志 tab ──
        self.region_browser = RegionBrowserWidget()
        self.region_table = self.region_browser.table  # 兼容现有引用
        self._setup_message_log()

        bottom_tabs = QTabWidget()
        bottom_tabs.addTab(self.region_browser, T("bottom_region_tab"))
        bottom_tabs.addTab(self._message_panel, T("bottom_messages_tab"))

        self.dock_bottom = QDockWidget(T("region_school"), self)
        self.dock_bottom.setObjectName("dockRegions")
        self.dock_bottom.setWidget(bottom_tabs)
        self.dock_bottom.setFeatures(
            QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable
        )
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_bottom)

        # 默认尺寸：左 260px，右 300px，底部 160px
        self.resizeDocks([self.dock_left], [260], Qt.Horizontal)
        self.resizeDocks([self.dock_right], [300], Qt.Horizontal)
        self.resizeDocks([self.dock_bottom], [160], Qt.Vertical)

    # ═══════════════════════════════════════════════════════
    # 消息日志（线程安全）
    # ═══════════════════════════════════════════════════════

    def _setup_message_log(self):
        """创建消息日志面板 + 线程安全的 logging handler"""
        self._message_panel = QWidget()
        msg_layout = QVBoxLayout(self._message_panel)
        msg_layout.setContentsMargins(0, 0, 0, 0)
        msg_layout.setSpacing(2)

        btn_clear = QPushButton(T("messages_clear"))
        btn_clear.clicked.connect(lambda: self._message_text.clear())
        msg_layout.addWidget(btn_clear)

        self._message_text = QPlainTextEdit()
        self._message_text.setReadOnly(True)
        msg_layout.addWidget(self._message_text, 1)

        # 线程安全：通过 Qt 信号桥接后台线程的日志
        handler = _QtLogHandler()
        handler.log_record.connect(self._message_text.appendPlainText)
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S"))
        fish_logger = logging.getLogger("fish_acoustics")
        fish_logger.setLevel(logging.INFO)
        fish_logger.addHandler(handler)

    # ═══════════════════════════════════════════════════════
    # 信号连接
    # ═══════════════════════════════════════════════════════

    def _connect_signals(self):
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
        self.property_panel.stats_clicked.connect(self._show_stats)
        self.property_panel.noise_params_changed.connect(self._on_noise_params_changed)
        self.property_panel.quality_check_clicked.connect(self._run_quality_check)
        self.property_panel.multifreq_clicked.connect(self._run_multifreq_analysis)
        self.property_panel.sv_stats_clicked.connect(self._run_sv_stats)
        self.property_panel.transect_split_clicked.connect(self._run_transect_split)
        self.property_panel.integration_clicked.connect(self._run_integration)
        self.property_panel.real_sed_clicked.connect(self._run_real_sed)
        self.property_panel.detect_bottom_clicked.connect(self._detect_bottom)
        self.property_panel.draw_bottom_clicked.connect(self._start_draw_bottom)
        self.property_panel.update_bottom_clicked.connect(self._on_update_bottom)
        self.property_panel.apply_all_clicked.connect(self._apply_all_params)

        # 变量列表
        self.variable_list.variable_selected.connect(self._on_variable_selected)

        # 区域面板（信号通过 RegionBrowserWidget 转发）
        self.region_browser.region_deleted.connect(self._on_region_deleted)

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
                    "method": "enhanced", "threshold": -40.0,
                    "offset_m": 0.5, "bin_skip_from_surface": 50,
                    "peak_threshold": -40.0, "discrimination_threshold": -50.0,
                    "saturation_threshold": -60.0,
                    "validation_window": 15, "validation_threshold": 3.0,
                    "smoothing_window": 11,
                    "search_min": 10.0, "window_len": 11, "backstep": 35.0,
                },
            },
            "school_detection": {
                "method": "advanced", "thr": -55.0,
                "mincan": [3, 10], "maxlink": [3, 15], "minsho": [3, 15],
                "min_threshold": -60.0, "max_depth_distance": 0.1,
                "max_ping_distance": 1, "max_time_gap": 20,
                "min_shoal_pings": 3, "min_shoal_height": 0.5,
            },
            "integration": {
                "esu_type": "pings", "esu_size": 500,
                "layer_width": 5.0, "min_threshold": -70.0,
                "max_threshold": 0.0, "ts_default": -30.0,
            },
        }

    # ═══════════════════════════════════════════════════════
    # 语言切换 & 关于
    # ═══════════════════════════════════════════════════════

    def _switch_language(self, lang: str):
        """切换语言（需要重启应用生效）"""
        set_language(lang)
        QMessageBox.information(self, T("dialog_info"), T("lang_switch_prompt"))

    def _show_about(self):
        QMessageBox.about(self, T("about_title"), T("about_html"))

    def _on_worker_error(self, msg):
        self._run_all_chain = False
        self.statusbar.hide_progress()
        self.statusbar.set_status(f"{T('dialog_error')}: {msg}")
        QMessageBox.critical(self, T("dialog_processing_error"), msg)

    # ═══════════════════════════════════════════════════════
    # 文件操作 — 批量导入
    # ═══════════════════════════════════════════════════════

    # -- Mixin methods split into handlers/ modules --
    # FileMixin:       file import, batch, cache, switch, variable list
    # ProcessingMixin:  Sv, noise, bottom, schools, integration
    # AnalysisMixin:    quality, multifreq, single target, Sv stats, transect
    # InteractionMixin: mouse, region, undo/redo, view, export
