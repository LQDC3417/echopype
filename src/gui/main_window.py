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

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QDockWidget,
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.gui.i18n import T, set_language
from src.gui.navigation_bar import EchogramNavBar
from src.gui.property_panel import PropertyPanel
from src.gui.region_panel import RegionBrowserWidget
from src.gui.stats_dialog import StatsDialog
from src.gui.status_bar import MainStatusBar
from src.gui.toolbars import EchogramToolBar, MouseMode, StandardToolBar
from src.gui.workers import MergeFilesWorker
from src.viz.opengl_renderer import EchogramRenderer
from src.core.lines import LineManager
from src.core.region import AnalysisRegion

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
        self.line_manager = LineManager()
        self.analysis_region: AnalysisRegion | None = None
        self.display_settings = {"colormap": "jet", "vmin": -90.0, "vmax": -30.0}
        self._active_line_id = LineManager.SURFACE_ID
        self._analysis_region_enabled = False  # 分析区域限定（仅控制 UI 渲染，不影响分析裁剪）
        self._schools_mask = None
        self._schools_df = None
        self._current_worker = None
        self._close_pending = False
        self._current_channel = ""
        self._undo_stack = []
        self._redo_stack = []
        self._current_mode = MouseMode.NAVIGATE
        self._run_all_chain = False
        self._stale_results: set[str] = set()
        self._parameter_timers: dict[str, QTimer] = {}
        self._parameter_callbacks = {}
        self._processing_dialogs = {}
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

    def closeEvent(self, event):
        """后台任务运行时延迟关闭，避免阻塞 UI 或销毁活跃 QThread。"""
        worker = self._current_worker
        if worker is not None and worker.isRunning():
            if hasattr(worker, "requestInterruption"):
                worker.requestInterruption()
            if not self._close_pending:
                self._close_pending = True
                worker.finished.connect(
                    lambda *_args, active=worker: self._complete_deferred_close(active)
                )
                worker.error.connect(
                    lambda *_args, active=worker: self._complete_deferred_close(active)
                )
                # 多数 Worker 为 ``finished = Signal(object)``，覆盖了 QThread
                # 原生无参 finished 信号；因此必须轮询运行状态作为关闭兜底。
                QTimer.singleShot(50, lambda active=worker: self._complete_deferred_close(active))
            event.ignore()
            self.statusbar.set_status("后台任务结束后将自动关闭")
            return
        super().closeEvent(event)

    def _complete_deferred_close(self, worker):
        if not self._close_pending or worker is not self._current_worker:
            return
        if worker.isRunning():
            QTimer.singleShot(50, lambda active=worker: self._complete_deferred_close(active))
            return
        self._current_worker = None
        self._close_pending = False
        QTimer.singleShot(0, self.close)

    # ═══════════════════════════════════════════════════════
    # 菜单栏
    # ═══════════════════════════════════════════════════════

    def _setup_menubar(self):
        mb = self.menuBar()

        # ── 文件 ──
        fm = mb.addMenu(T("menu_file"))
        fm.addAction(self._act(T("new_project"), self._new_project, "Ctrl+N"))
        fm.addAction(self._act(T("open_project"), self._open_project, "Ctrl+O"))
        fm.addAction(self._act(T("save_project"), self._save_project, "Ctrl+S"))
        fm.addSeparator()

        # 最近打开的项目
        self._recent_menu = fm.addMenu(T("recent_projects"))
        self._update_recent_menu()

        fm.addSeparator()
        fm.addAction(self._act(T("open_config"), self._open_config))
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

        lines_menu = mb.addMenu("线段设置")
        lines_menu.addAction(self._act("线段管理...", self._show_line_manager))
        lines_menu.addAction(self._act("底线检测...", self._detect_bottom))

        data_menu = mb.addMenu("数据")
        self._data_menu_actions = {
            "noise": self._act("噪声去除...", lambda: self._show_processing_dialog("noise")),
            "schools": self._act("鱼群检测...", lambda: self._show_processing_dialog("schools")),
            "integration": self._act("回声积分...", lambda: self._show_processing_dialog("integration")),
            "sed": self._act("SED 单体目标检测...", lambda: self._show_processing_dialog("sed")),
        }
        for action in self._data_menu_actions.values():
            data_menu.addAction(action)

        # ── 分析 ──
        am = mb.addMenu(T("menu_analysis"))
        am.addAction(self._act("质量检查", self._run_quality_check))
        am.addAction(self._act("多频分析", self._run_multifreq_analysis))
        am.addAction(self._act("Sv 统计", self._run_sv_stats))
        am.addAction(self._act("Transect 分段", self._run_transect_split))
        am.addSeparator()
        am.addAction(self._act(T("menu_export_schools"), self._export_schools))

        # ── 帮助 ──
        hm = mb.addMenu(T("menu_help"))
        hm.addAction(self._act(T("about"), self._show_about))

    def _update_recent_menu(self):
        from src.gui.handlers.file_handlers import _load_recent
        self._recent_menu.clear()
        recent = _load_recent()
        if not recent:
            action = self._recent_menu.addAction(T("recent_empty"))
            action.setEnabled(False)
            return
        for path in recent:
            p = Path(path)
            action = self._recent_menu.addAction(f"{p.name}  ({p.parent})")
            action.triggered.connect(lambda checked=False, pp=path: self._open_recent(pp))

    def _update_nav_bar(self, *args):
        """渲染器视图变化 → 同步导航滑块"""
        ratio = self.echogram.get_view_ratio()
        self.nav_bar.set_view_ratio(*ratio)

    def _open_recent(self, path: str):
        """打开最近列表中的项目"""
        # 当前任务仍运行时拒绝切换，不能阻塞 UI 或丢弃 QThread 引用。
        if self._current_worker is not None and self._current_worker.isRunning():
            self.statusbar.set_status("请等待当前后台任务完成后再切换项目")
            return
        self._current_worker = None
        try:
            from src.gui.handlers.file_handlers import _save_recent
            from src.core.ep_project import EpProject

            proj = EpProject.load(Path(path))
            all_ok, missing = proj.verify_raw_files()
            if not all_ok:
                missing_list = "\n".join(str(p) for p in missing[:20])
                QMessageBox.critical(
                    self, T("dialog_error"),
                    T("msg_project_raw_missing", files=missing_list)
                )
                return

            self._reset_analysis_state()
            self._current_raw_files = proj.raw_files
            self._current_project_path = Path(path)
            self._config = proj.config

            self.statusbar.show_progress(T("msg_loading_files", n=len(proj.raw_files)))
            self._current_worker = MergeFilesWorker(proj.raw_files, proj.config)
            worker = self._current_worker
            self._connect_latest_worker(
                worker, lambda ds: self._on_project_loaded(ds, proj)
            )
            worker.progress.connect(self.statusbar.set_status)
            worker.progress_num.connect(self.statusbar.set_progress_value)
            worker.start()
            _save_recent(str(path))
        except Exception as e:
            QMessageBox.critical(self, T("dialog_error"), f"{e}")

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

    def _refresh_line_toolbar(self):
        if hasattr(self, "echo_toolbar"):
            self.echo_toolbar.set_editable_lines(self.line_manager.editable_lines())

    def _select_active_line(self, line_id: str):
        if line_id:
            self._active_line_id = line_id
            if hasattr(self, "echogram"):
                self.echogram.set_active_line(line_id)

    def _start_draw_active_line(self):
        if self._active_line_id == LineManager.ZERO_ID:
            return
        self._current_mode = MouseMode.DRAW_LINE
        self.echogram.set_mouse_mode(MouseMode.DRAW_LINE.value)
        self.statusbar.set_status(f"绘制线段: {self.line_manager.get(self._active_line_id).name}")

    def _show_line_manager(self):
        """最小线段管理入口：新增引用偏移线，完整编辑仍保留现有底线工作流。"""
        name, accepted = QInputDialog.getText(self, "新增线段", "线段名称")
        if not accepted:
            return
        # 新线尚未加入模型，因此可以安全引用当前活动线（默认就是 Surface）。
        references = list(self.line_manager)
        labels = [line.name for line in references]
        reference_name, accepted = QInputDialog.getItem(self, "线段基准", "参考线", labels, 0, False)
        if not accepted:
            return
        offset, accepted = QInputDialog.getDouble(self, "线段偏移", "偏移 (m；正数向下)", 0.0, -10000, 10000, 2)
        if not accepted:
            return
        reference = next(line for line in references if line.name == reference_name)
        existing_ids = {line.id for line in self.line_manager}
        suffix = len(existing_ids)
        line_id = f"line_{suffix}"
        while line_id in existing_ids:
            suffix += 1
            line_id = f"line_{suffix}"
        try:
            self.line_manager.add_line(line_id, name, reference_id=reference.id, offset_m=offset)
        except ValueError as exc:
            QMessageBox.warning(self, "线段设置", str(exc))
            return
        self._refresh_line_toolbar()

    def _show_display_settings(self):
        from src.gui.display_settings_dialog import DisplaySettingsDialog

        dialog = DisplaySettingsDialog(
            self.display_settings["colormap"],
            self.display_settings["vmin"],
            self.display_settings["vmax"],
            self,
        )
        dialog.settings_applied.connect(self._apply_display_settings)
        dialog.show()
        self._display_settings_dialog = dialog

    def _show_analysis_region_dialog(self):
        """选择分析区域的上下边界，并使后续分析立即使用新范围。"""
        from src.gui.analysis_region_dialog import AnalysisRegionDialog

        lines = [(line.id, line.name) for line in self.line_manager if line.visible]
        if len(lines) < 2:
            QMessageBox.warning(self, T("dialog_warning"), "请先创建或检测至少两条线段。")
            return
        region = self.analysis_region
        dialog = AnalysisRegionDialog(
            lines,
            upper_line_id=(region.upper_line_id if region else LineManager.SURFACE_ID),
            lower_line_id=(region.lower_line_id if region else LineManager.BOTTOM_ID),
            parent=self,
        )
        dialog.region_applied.connect(self._apply_analysis_region)
        dialog.show()
        self._analysis_region_dialog = dialog

    def _apply_analysis_region(self, upper_line_id: str, lower_line_id: str):
        self.analysis_region = AnalysisRegion(upper_line_id, lower_line_id)
        self._analysis_region_enabled = True
        self.echogram.set_analysis_region_enabled(True)
        self._invalidate_analysis_region_cache()
        self._apply_analysis_region_to_ds()

    def _apply_display_settings(self, colormap: str, vmin: float, vmax: float):
        self.display_settings = {
            "colormap": colormap,
            "vmin": float(vmin),
            "vmax": float(vmax),
        }
        self.echogram.set_colormap(colormap, float(vmin), float(vmax))

    def _show_processing_dialog(self, kind: str):
        """显示单一功能参数窗口；只有 Apply/确定才启动对应 Worker。"""
        if self._ds_Sv is None:
            QMessageBox.warning(self, T("dialog_warning"), T("msg_load_data_first"))
            return
        if self._current_worker is not None and self._current_worker.isRunning():
            self.statusbar.set_status("请等待当前后台任务完成后再执行新的数据处理")
            return

        dialog = self._processing_dialogs.get(kind)
        if dialog is None:
            from src.gui.processing_dialogs import ProcessingParametersDialog

            processing = self.property_panel.processing
            specs = {
                "noise": (processing.noise_group, processing.get_noise_config, "噪声去除参数", self._apply_noise_params),
                "schools": (processing.school_group, processing.get_school_config, "鱼群检测参数", self._detect_schools),
                "integration": (processing.integration_group, processing.get_integration_config, "回声积分参数", self._run_integration),
                "sed": (processing.real_sed_group, processing.get_real_sed_config, "SED 单体目标检测参数", self._run_real_sed),
            }
            parameter_widget, getter, title, callback = specs[kind]
            # 旧参数页已从 Dock 移除；原有功能按钮会绕过 Apply/确定语义。
            button_name = {
                "schools": "btn_detect_schools",
                "integration": "btn_integration",
                "sed": "btn_real_sed",
            }.get(kind)
            if button_name:
                getattr(processing, button_name).hide()
            dialog = ProcessingParametersDialog(
                parameter_widget, getter, title=title, parent=self
            )
            dialog.apply_requested.connect(lambda _config, cb=callback: cb())
            self._processing_dialogs[kind] = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    # ═══════════════════════════════════════════════════════
    # UI 布局
    # ═══════════════════════════════════════════════════════

    def _setup_ui(self):
        # ── 工具栏（2 行紧凑）──
        self.std_toolbar = StandardToolBar(self)
        self.addToolBar(self.std_toolbar)
        self.echo_toolbar = EchogramToolBar(self)
        self.addToolBar(self.echo_toolbar)

        # ── 统计对话框 ──
        self.stats_dialog = StatsDialog(self)

        # ── 状态栏 ──
        self.statusbar = MainStatusBar(self)
        self.setStatusBar(self.statusbar)

        # ── 中央：Echogram + 底部导航滑块 ──
        self.echogram = EchogramRenderer()
        self.nav_bar = EchogramNavBar()
        self.view_tabs = QTabWidget()
        self.view_tabs.setDocumentMode(True)
        self.view_tabs.setUsesScrollButtons(True)
        self.view_tabs.setObjectName("documentTabs")
        central_widget = QWidget()
        central_layout = QVBoxLayout(central_widget)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(self.echogram, 1)
        central_layout.addWidget(self.nav_bar)
        self.view_tabs.addTab(central_widget, T("view_tab", n=1))
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
        self._hide_dock_title(self.dock_left)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_left)

        # ── 右侧 Dock：属性面板 ──
        self.property_panel = PropertyPanel()
        # PropertyPanel 在界面优化分支中改为折叠面板，不再是 QTabWidget。
        # 保留内部 ProcessingTab 作为各参数弹窗的数据源，但不在 Dock 中展示
        # 处理参数，避免绕过 Apply/确定的执行语义。
        self.property_panel.configure_summary_view()
        self.dock_right = QDockWidget("属性", self)
        self.dock_right.setObjectName("dockProperties")
        self.dock_right.setWidget(self.property_panel)
        self.dock_right.setFeatures(
            QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable
        )
        self._hide_dock_title(self.dock_right)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_right)

        # ── 底部 Dock：区域浏览器 + 消息日志 tab ──
        self.region_browser = RegionBrowserWidget()
        self.region_table = self.region_browser.table  # 兼容现有引用
        self._setup_message_log()

        bottom_tabs = QTabWidget()
        bottom_tabs.addTab(self.region_browser, T("bottom_region_tab"))
        bottom_tabs.addTab(self._message_panel, T("bottom_messages_tab"))
        self._bottom_tabs = bottom_tabs

        self.dock_bottom = QDockWidget(T("region_school"), self)
        self.dock_bottom.setObjectName("dockRegions")
        self.dock_bottom.setWidget(bottom_tabs)
        self.dock_bottom.setFeatures(
            QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable
        )
        self._hide_dock_title(self.dock_bottom)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_bottom)

        # 默认尺寸：左 260px，右 300px，底部 160px
        self.resizeDocks([self.dock_left], [240], Qt.Horizontal)
        self.resizeDocks([self.dock_right], [360], Qt.Horizontal)
        self.resizeDocks([self.dock_bottom], [160], Qt.Vertical)

    @staticmethod
    def _hide_dock_title(dock: QDockWidget) -> None:
        """去除传统 Dock 标题栏，保留停靠、缩放和菜单中的显示控制。"""
        title_bar = QWidget(dock)
        title_bar.setFixedHeight(0)
        dock.setTitleBarWidget(title_bar)

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
        self._message_text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._message_text.setMaximumBlockCount(5000)
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
        self.std_toolbar.open_clicked.connect(self._new_project)
        self.std_toolbar.open_config_clicked.connect(self._open_config)
        self.std_toolbar.save_config_clicked.connect(self._save_config)
        self.std_toolbar.undo_clicked.connect(self._undo)
        self.std_toolbar.redo_clicked.connect(self._redo)
        self.std_toolbar.export_clicked.connect(self._export)

        # Echogram 工具栏
        self.echo_toolbar.mode_changed.connect(self._on_mode_changed)
        self.echo_toolbar.mode_changed.connect(lambda m: self.echogram.set_mouse_mode(m.value))
        self.echo_toolbar.line_selected.connect(self._select_active_line)
        self.echo_toolbar.draw_line_requested.connect(self._start_draw_active_line)
        self.echo_toolbar.reset_view_clicked.connect(self._reset_view)
        self.echo_toolbar.fit_view_clicked.connect(self._fit_view)
        self._act_noise.toggled.connect(
            lambda visible: self.echogram.set_overlay_visible("noise", visible)
        )
        self._act_school.toggled.connect(
            lambda visible: self.echogram.set_overlay_visible("school", visible)
        )
        self._act_bottom.toggled.connect(
            lambda visible: self.echogram.set_overlay_visible("bottom", visible)
        )

        # Echogram 交互
        self.echogram.mouse_moved.connect(self.statusbar.set_coords)
        self.echogram.mouse_moved.connect(self._update_depth_at_cursor)
        self.echogram.region_selected.connect(self._on_region_selected)
        self.echogram.line_edited.connect(self._on_line_edited)
        self.echogram.sv_at_cursor.connect(self.statusbar.set_sv)
        self.echogram.zoom_changed.connect(self.statusbar.set_zoom_info)
        self.echogram.zoom_changed.connect(self._update_nav_bar)

        # 导航滑块
        self.nav_bar.view_moved.connect(self.echogram.set_view_ratio)

        # 右键菜单信号
        self.echogram.surface_line_requested.connect(self._on_surface_line_dialog)
        self.echogram.analysis_region_requested.connect(self._show_analysis_region_dialog)
        self.echogram.analysis_region_toggle.connect(self._on_analysis_region_toggle)
        self.echogram.display_settings_requested.connect(self._show_display_settings)
        self.echogram.noise_removal_requested.connect(lambda: self._show_processing_dialog("noise"))
        self.echogram.school_detection_requested.connect(lambda: self._show_processing_dialog("schools"))
        self.echogram.integration_requested.connect(lambda: self._show_processing_dialog("integration"))
        self.echogram.real_sed_requested.connect(lambda: self._show_processing_dialog("sed"))
        self.echogram.re_detect_bottom.connect(self._detect_bottom)
        self.echogram.update_bottom_requested.connect(self._on_update_bottom)

        # 属性面板（处理参数）
        # 参数控件仅作为内部配置来源，修改控件本身不再自动启动 Worker。
        self.property_panel.detect_schools_clicked.connect(self._detect_schools)
        self.property_panel.stats_clicked.connect(self._show_stats)
        self.property_panel.surface_line_changed.connect(self._on_surface_line_changed)
        self.property_panel.quality_check_clicked.connect(self._run_quality_check)
        self.property_panel.multifreq_clicked.connect(self._run_multifreq_analysis)
        self.property_panel.sv_stats_clicked.connect(self._run_sv_stats)
        self.property_panel.transect_split_clicked.connect(self._run_transect_split)
        self.property_panel.integration_clicked.connect(self._run_integration)
        self.property_panel.real_sed_clicked.connect(self._run_real_sed)
        self.property_panel.detect_bottom_clicked.connect(self._detect_bottom)
        self.property_panel.draw_bottom_clicked.connect(self._start_draw_bottom)
        self.property_panel.update_bottom_clicked.connect(self._on_update_bottom)
        self.property_panel.export_clicked.connect(self._export)
        self._refresh_line_toolbar()

        # 变量列表
        self.variable_list.variable_selected.connect(self._on_variable_selected)

        # 区域面板（信号通过 RegionBrowserWidget 转发）
        self.region_browser.region_deleted.connect(self._on_region_deleted)

        self._set_overlay_actions_enabled(False)

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
            "output": {
                "dir": "outputs",
                "formats": ["netcdf", "csv"],
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
        summary = next((line.strip() for line in reversed(msg.splitlines()) if line.strip()), msg)
        self.statusbar.set_status(f"{T('dialog_error')}: {summary[:180]}")
        self._append_error_message(msg)

    def _connect_latest_worker(self, worker, finished=None):
        """只接受当前 Worker 的结果，避免旧参数任务覆盖新结果。"""
        if finished is not None:
            worker.finished.connect(
                lambda result, w=worker: (
                    finished(result) if w is self._current_worker else None
                )
            )
        worker.error.connect(
            lambda msg, w=worker: (
                self._on_worker_error(msg) if w is self._current_worker else None
            )
        )

    def _schedule_parameter_apply(self, name: str, callback, interval_ms: int = 500) -> None:
        """防抖调度单个功能参数，避免连续拖动启动多个 Worker。"""
        timer = self._parameter_timers.get(name)
        if timer is None:
            timer = QTimer(self)
            timer.setSingleShot(True)
            self._parameter_timers[name] = timer
            timer.timeout.connect(lambda n=name: self._run_scheduled_parameter(n))
        timer.setInterval(interval_ms)
        self._parameter_callbacks[name] = callback
        timer.start()

    def _run_scheduled_parameter(self, name: str) -> None:
        callback = self._parameter_callbacks.get(name)
        if callback is not None:
            callback()

    def _mark_results_stale(self, *names: str) -> None:
        self._stale_results.update(names)
        labels = {"bottom": "底线", "schools": "鱼群", "integration": "积分", "real_sed": "SED"}
        text = "、".join(labels.get(name, name) for name in names)
        if text:
            self.statusbar.set_status(f"参数已变更：{text}结果需要重新计算")

    def _append_error_message(self, msg: str) -> None:
        """将后台错误写入可滚动消息面板，不阻塞主窗口。"""
        if not hasattr(self, "_message_text"):
            return
        self._message_text.appendPlainText(msg.rstrip())
        self._bottom_tabs.setCurrentIndex(1)
        self.dock_bottom.show()

    def _on_toolbar_colormap_changed(self, cmap: str, vmin: float, vmax: float) -> None:
        self.property_panel.display.set_values(cmap, vmin, vmax)
        self.echogram.set_colormap(cmap, vmin, vmax)

    def _on_display_params_changed(self, cmap: str, vmin: float, vmax: float) -> None:
        self.echo_toolbar.set_display_values(cmap, vmin, vmax)
        self.echogram.set_colormap(cmap, vmin, vmax)

    def _set_overlay_actions_enabled(self, enabled: bool) -> None:
        """无数据时禁用结果开关，导入成功后恢复可用。"""
        for action in (self._act_noise, self._act_school, self._act_bottom):
            action.setEnabled(enabled)

    # ═══════════════════════════════════════════════════════
    # 文件操作 — 批量导入
    # ═══════════════════════════════════════════════════════

    # -- Mixin methods split into handlers/ modules --
    # FileMixin:       file import, batch, cache, switch, variable list
    # ProcessingMixin:  Sv, noise, bottom, schools, integration
    # AnalysisMixin:    quality, multifreq, single target, Sv stats, transect
    # InteractionMixin: mouse, region, undo/redo, view, export
