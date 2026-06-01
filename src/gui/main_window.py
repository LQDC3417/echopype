"""主窗口：组装所有 GUI 组件"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QFileDialog, QMessageBox,
)
from PySide6.QtCore import Qt, QTimer

from src.viz.opengl_renderer import EchogramRenderer
from src.gui.file_tree import FileTree
from src.gui.property_panel import PropertyPanel
from src.gui.status_bar import MainStatusBar
from src.gui.toolbars import MainToolBar, MouseMode
from src.gui.workers import (
    LoadFileWorker, ComputeSvWorker, NoiseRemovalWorker,
    DetectSeafloorWorker, DetectSchoolsWorker, DensityWorker,
)


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Echogram GUI — 鱼类资源评估系统")
        self.setMinimumSize(1200, 800)

        # 状态
        self._config = None
        self._echodata = None
        self._ds_Sv = None
        self._noise_mask_manual = None
        self._bottom_line = None
        self._schools_mask = None
        self._schools_df = None
        self._density_df = None
        self._current_worker = None

        # 撤销栈
        self._undo_stack = []

        # 防抖定时器
        self._noise_timer = QTimer()
        self._noise_timer.setSingleShot(True)
        self._noise_timer.setInterval(300)
        self._noise_timer.timeout.connect(self._apply_noise_params)

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """设置界面布局"""
        # 工具栏
        self.toolbar = MainToolBar(self)
        self.addToolBar(self.toolbar)

        # 状态栏
        self.statusbar = MainStatusBar(self)
        self.setStatusBar(self.statusbar)

        # 中央区域：三栏布局
        splitter = QSplitter(Qt.Horizontal)

        # 左侧文件树 — 根目录指向项目根目录
        self.file_tree = FileTree()
        project_root = str(Path(__file__).resolve().parent.parent.parent)
        self.file_tree.set_root_path(project_root)
        splitter.addWidget(self.file_tree)

        # 中间 Echogram
        self.echogram = EchogramRenderer()
        splitter.addWidget(self.echogram)

        # 右侧属性面板
        self.property_panel = PropertyPanel()
        splitter.addWidget(self.property_panel)

        # 设置比例
        splitter.setSizes([200, 700, 300])

        self.setCentralWidget(splitter)

    def _connect_signals(self):
        """连接信号"""
        # 工具栏
        self.toolbar.open_clicked.connect(self._open_file)
        self.toolbar.run_clicked.connect(self._run_all)
        self.toolbar.undo_clicked.connect(self._undo)
        self.toolbar.export_clicked.connect(self._export)
        self.toolbar.reset_view_clicked.connect(self.echogram.reset_view)
        self.toolbar.mode_changed.connect(self._on_mode_changed)
        self.toolbar.colormap_changed.connect(self.echogram.set_colormap)

        # Echogram 交互
        self.echogram.mouse_moved.connect(self.statusbar.set_coords)
        self.echogram.region_selected.connect(self._on_region_selected)

        # 属性面板
        self.property_panel.noise_params_changed.connect(self._on_noise_params_changed)
        self.property_panel.detect_bottom_clicked.connect(self._detect_bottom)
        self.property_panel.detect_schools_clicked.connect(self._detect_schools)
        self.property_panel.compute_density_clicked.connect(self._compute_density)

        # 文件树
        self.file_tree.file_selected.connect(self._on_file_selected)

    def _open_file(self):
        """打开文件对话框"""
        # 默认打开 raw_data 目录
        project_root = Path(__file__).resolve().parent.parent.parent
        raw_dir = str(project_root / "raw_data")
        if not Path(raw_dir).exists():
            raw_dir = str(project_root)

        path, _ = QFileDialog.getOpenFileName(
            self, "打开 raw 文件", raw_dir, "Raw 文件 (*.raw);;所有文件 (*)"
        )
        if path:
            self._load_file(Path(path))

    def _on_file_selected(self, path: Path):
        """文件树双击"""
        if path.suffix == ".raw":
            self._load_file(path)

    def _load_file(self, path: Path):
        """加载 raw 文件"""
        if self._config is None:
            self._config = {
                "processing": {
                    "sonar_model": "EK80",
                    "noise_removal": {
                        "ping_num": 5,
                        "range_sample_num": 10,
                        "SNR_threshold": "3.0dB",
                    },
                    "bottom_detection": {
                        "method": "basic",
                        "threshold": -50.0,
                        "offset_m": 0.5,
                        "bin_skip_from_surface": 200,
                    },
                },
                "school_detection": {
                    "method": "echoview",
                    "thr": -55.0,
                    "mincan": [3, 10],
                    "maxlink": [3, 15],
                    "minsho": [3, 15],
                },
                "density": {"ts_default": -30.0},
            }

        self.statusbar.show_progress(f"加载: {path.name}")
        self._current_worker = LoadFileWorker(path, self._config)
        self._current_worker.finished.connect(self._on_file_loaded)
        self._current_worker.error.connect(self._on_worker_error)
        self._current_worker.progress.connect(self.statusbar.set_status)
        self._current_worker.start()

    def _on_file_loaded(self, echodata):
        """文件加载完成"""
        self._echodata = echodata
        self.statusbar.set_status("文件已加载，计算 Sv...")
        self._compute_sv()

    def _compute_sv(self):
        """计算 Sv"""
        if self._echodata is None:
            return
        self.statusbar.show_progress("计算 Sv...")
        self._current_worker = ComputeSvWorker(self._echodata, self._config)
        self._current_worker.finished.connect(self._on_sv_computed)
        self._current_worker.error.connect(self._on_worker_error)
        self._current_worker.progress.connect(self.statusbar.set_status)
        self._current_worker.start()

    def _on_sv_computed(self, ds_Sv):
        """Sv 计算完成"""
        self._ds_Sv = ds_Sv
        self.statusbar.hide_progress()
        self.statusbar.set_status("Sv 计算完成")

        sv = ds_Sv["Sv"].values
        if sv.ndim == 3:
            sv = sv[0]
        self.echogram.set_data(sv)

        self.property_panel.file_info.update_info(ds_Sv)

    def _on_noise_params_changed(self, params):
        """噪声参数变化，启动防抖"""
        self._noise_timer.start()

    def _apply_noise_params(self):
        """应用噪声参数（防抖后）"""
        if self._ds_Sv is None:
            return
        self.statusbar.show_progress("重新计算噪声...")
        self._current_worker = NoiseRemovalWorker(self._ds_Sv, self._config)
        self._current_worker.finished.connect(self._on_noise_removed)
        self._current_worker.error.connect(self._on_worker_error)
        self._current_worker.start()

    def _on_noise_removed(self, ds_Sv):
        """噪声去除完成"""
        self._ds_Sv = ds_Sv
        self.statusbar.hide_progress()

        sv = ds_Sv["Sv"].values
        if sv.ndim == 3:
            sv = sv[0]
        self.echogram.set_data(sv)

    def _on_region_selected(self, x1, y1, x2, y2):
        """框选区域"""
        if self.toolbar.mode_combo.currentIndex() == MouseMode.SELECT_NOISE.value:
            self._add_noise_region(x1, y1, x2, y2)

    def _add_noise_region(self, x1, y1, x2, y2):
        """添加手动噪声区域"""
        if self._ds_Sv is None:
            return

        sv = self._ds_Sv["Sv"].values
        if sv.ndim == 3:
            sv = sv[0]
        h, w = sv.shape

        if self._noise_mask_manual is None:
            self._noise_mask_manual = np.zeros((h, w), dtype=bool)

        px1 = max(0, int(min(x1, x2)))
        py1 = max(0, int(min(y1, y2)))
        px2 = min(w, int(max(x1, x2)))
        py2 = min(h, int(max(y1, y2)))

        self._noise_mask_manual[py1:py2, px1:px2] = True

        self._undo_stack.append(("noise_mask", self._noise_mask_manual.copy()))

        self.echogram.set_noise_mask(self._noise_mask_manual)
        self.statusbar.set_status(f"已添加噪声区域: ({px1},{py1}) - ({px2},{py2})")

    def _detect_bottom(self):
        """检测底部"""
        if self._ds_Sv is None:
            QMessageBox.warning(self, "警告", "请先加载数据")
            return
        self.statusbar.show_progress("检测底部...")
        self._current_worker = DetectSeafloorWorker(self._ds_Sv, self._config)
        self._current_worker.finished.connect(self._on_bottom_detected)
        self._current_worker.error.connect(self._on_worker_error)
        self._current_worker.start()

    def _on_bottom_detected(self, bottom):
        """底部检测完成"""
        self._bottom_line = bottom.values
        self._ds_Sv["bottom_depth"] = bottom
        self.echogram.set_bottom_line(self._bottom_line)
        self.statusbar.hide_progress()
        self.statusbar.set_status("底部检测完成")

    def _detect_schools(self):
        """检测鱼群"""
        if self._ds_Sv is None:
            QMessageBox.warning(self, "警告", "请先加载数据")
            return
        self.statusbar.show_progress("检测鱼群...")
        self._current_worker = DetectSchoolsWorker(self._ds_Sv, self._config)
        self._current_worker.finished.connect(self._on_schools_detected)
        self._current_worker.error.connect(self._on_worker_error)
        self._current_worker.start()

    def _on_schools_detected(self, mask, df):
        """鱼群检测完成"""
        self._schools_mask = mask.values
        self._schools_df = df
        self.echogram.set_school_mask(self._schools_mask)
        self.property_panel.stats.update_schools(df)
        self.statusbar.hide_progress()
        self.statusbar.set_status(f"检测到 {len(df)} 个鱼群")

    def _compute_density(self):
        """计算密度"""
        if self._ds_Sv is None:
            QMessageBox.warning(self, "警告", "请先加载数据")
            return
        schools_df = self._schools_df if self._schools_df is not None else pd.DataFrame()
        self.statusbar.show_progress("计算密度...")
        self._current_worker = DensityWorker(schools_df, self._ds_Sv, self._config)
        self._current_worker.finished.connect(self._on_density_computed)
        self._current_worker.error.connect(self._on_worker_error)
        self._current_worker.start()

    def _on_density_computed(self, df):
        """密度计算完成"""
        self._density_df = df
        self.property_panel.stats.update_density(df)
        self.statusbar.hide_progress()
        self.statusbar.set_status("密度计算完成")

    def _run_all(self):
        """运行全部处理流程"""
        if self._echodata is None:
            QMessageBox.warning(self, "警告", "请先加载文件")
            return
        self._compute_sv()

    def _undo(self):
        """撤销"""
        if not self._undo_stack:
            return
        action_type, data = self._undo_stack.pop()
        if action_type == "noise_mask":
            self._noise_mask_manual = data
            self.echogram.set_noise_mask(data)
            self.statusbar.set_status("已撤销")

    def _export(self):
        """导出结果"""
        if self._density_df is None:
            QMessageBox.warning(self, "警告", "没有可导出的数据")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出 CSV", "", "CSV 文件 (*.csv)"
        )
        if path:
            self._density_df.to_csv(path, index=False, encoding="utf-8-sig")
            self.statusbar.set_status(f"已导出: {path}")

    def _on_mode_changed(self, mode: MouseMode):
        """鼠标模式切换"""
        self.statusbar.set_status(f"模式: {mode.name}")

    def _on_worker_error(self, msg):
        """工作线程错误"""
        self.statusbar.hide_progress()
        self.statusbar.set_status(f"错误: {msg}")
        QMessageBox.critical(self, "错误", msg)
