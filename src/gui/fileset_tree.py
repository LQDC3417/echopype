"""Fileset 树形面板 + 批量导入对话框 — Echoview 风格"""

from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.gui.fileset import Fileset, FilesetStore, RawFileInfo

# ═══════════════════════════════════════════════════════════════
# Probe Worker — 后台探测 raw 文件元信息
# ═══════════════════════════════════════════════════════════════

class ProbeWorker(QThread):
    """后台探测文件元信息"""
    progress = Signal(int, int)  # current, total
    file_done = Signal(str, object)  # path_str, RawFileInfo
    all_done = Signal()

    def __init__(self, fileset: Fileset):
        super().__init__()
        self.fileset = fileset

    def run(self):
        for i, f in enumerate(self.fileset.files):
            info = RawFileInfo.probe(f, fast=False)
            self.fileset.file_infos[str(f)] = info
            self.file_done.emit(str(f), info)
            self.progress.emit(i + 1, len(self.fileset.files))
        self.all_done.emit()


# ═══════════════════════════════════════════════════════════════
# Import Dialog — 批量导入 .raw 文件
# ═══════════════════════════════════════════════════════════════

class BatchImportDialog(QDialog):
    """批量导入 .RAW 文件对话框"""

    fileset_created = Signal(object)  # Fileset

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("批量导入 Raw 文件")
        self.setMinimumSize(700, 500)
        self._files: list[Path] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # ── 顶部：选择来源 ──
        src_group = QGroupBox("文件来源")
        src_layout = QHBoxLayout()
        self.btn_folder = QPushButton("📁 选择文件夹...")
        self.btn_folder.clicked.connect(self._select_folder)
        self.btn_files = QPushButton("📄 选择文件...")
        self.btn_files.clicked.connect(self._select_files)
        src_layout.addWidget(self.btn_folder)
        src_layout.addWidget(self.btn_files)
        src_layout.addStretch()
        src_group.setLayout(src_layout)
        layout.addWidget(src_group)

        # ── 文件集名称 ──
        name_layout = QFormLayout()
        self.edit_name = QLineEdit("新建文件集")
        name_layout.addRow("文件集名称:", self.edit_name)
        layout.addLayout(name_layout)

        # ── 文件列表 ──
        self.file_list = QTreeWidget()
        self.file_list.setHeaderLabels(["文件名", "大小", "通道", "Ping 数", "时间范围", "状态"])
        self.file_list.setAlternatingRowColors(True)
        self.file_list.setRootIsDecorated(False)
        self.file_list.setSelectionMode(QTreeWidget.ExtendedSelection)
        self.file_list.header().setStretchLastSection(True)
        layout.addWidget(self.file_list, 1)

        # ── 进度 ──
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        # ── 底部按钮 ──
        btn_layout = QHBoxLayout()
        self.btn_probe = QPushButton("🔍 探测文件信息")
        self.btn_probe.clicked.connect(self._probe_files)
        self.btn_remove = QPushButton("🗑 移除选中")
        self.btn_remove.clicked.connect(self._remove_selected)
        btn_layout.addWidget(self.btn_probe)
        btn_layout.addWidget(self.btn_remove)
        btn_layout.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        btn_layout.addWidget(buttons)
        layout.addLayout(btn_layout)

    def _select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择包含 .raw 文件的文件夹")
        if folder:
            paths = sorted(Path(folder).glob("*.raw"))
            if not paths:
                QMessageBox.warning(self, "警告", f"在 {folder} 中未找到 .raw 文件")
                return
            self._files = list(paths)
            self.edit_name.setText(Path(folder).name)
            self._refresh_list()

    def _select_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择 Raw 文件", "",
            "Raw 文件 (*.raw);;所有文件 (*)"
        )
        if paths:
            self._files = [Path(p) for p in paths]
            self._refresh_list()

    def _refresh_list(self):
        self.file_list.clear()
        for f in self._files:
            item = QTreeWidgetItem([
                f.name,
                f"{f.stat().st_size / 1e6:.1f} MB",
                "--",
                "--",
                "--",
                "未探测",
            ])
            item.setData(0, Qt.UserRole, str(f))
            self.file_list.addTopLevelItem(item)

    def _probe_files(self):
        if not self._files:
            return
        self.progress.setVisible(True)
        self.btn_probe.setEnabled(False)
        self.btn_folder.setEnabled(False)
        self.btn_files.setEnabled(False)

        fileset = Fileset(name=self.edit_name.text(), files=list(self._files))
        self._worker = ProbeWorker(fileset)
        self._worker.progress.connect(self._on_probe_progress)
        self._worker.file_done.connect(self._on_probe_file)
        self._worker.all_done.connect(self._on_probe_done)
        self._worker.start()

    def _on_probe_progress(self, cur, total):
        self.progress.setRange(0, total)
        self.progress.setValue(cur)

    def _on_probe_file(self, path_str, info: RawFileInfo):
        for i in range(self.file_list.topLevelItemCount()):
            item = self.file_list.topLevelItem(i)
            if item.data(0, Qt.UserRole) == path_str:
                channels = ", ".join(info.channels) if info.channels else "--"
                pings = str(info.ping_count) if info.ping_count else "--"
                time_range = "--"
                if info.time_start:
                    time_range = info.time_start.strftime("%H:%M:%S")
                    if info.time_end:
                        time_range += f" ~ {info.time_end.strftime('%H:%M:%S')}"
                status = "✅" if info.is_valid else f"❌ {info.error_msg[:40]}"
                item.setText(1, f"{info.size_mb:.1f} MB")
                item.setText(2, channels)
                item.setText(3, pings)
                item.setText(4, time_range)
                item.setText(5, status)
                break

    def _on_probe_done(self):
        self.progress.setVisible(False)
        self.btn_probe.setEnabled(True)
        self.btn_folder.setEnabled(True)
        self.btn_files.setEnabled(True)

    def _remove_selected(self):
        for item in self.file_list.selectedItems():
            idx = self.file_list.indexOfTopLevelItem(item)
            self.file_list.takeTopLevelItem(idx)
            path_str = item.data(0, Qt.UserRole)
            self._files = [f for f in self._files if str(f) != path_str]

    def _on_accept(self):
        if not self._files:
            QMessageBox.warning(self, "没有文件", "请先添加至少一个 .raw 文件")
            return
        name = self.edit_name.text().strip() or "新建文件集"
        fileset = Fileset(name=name, files=list(self._files))
        self.fileset_created.emit(fileset)
        self.accept()

    def get_fileset(self) -> Fileset | None:
        if not self._files:
            return None
        name = self.edit_name.text().strip() or "新建文件集"
        return Fileset(name=name, files=list(self._files))


# ═══════════════════════════════════════════════════════════════
# Fileset Tree Widget — 文件集树形面板
# ═══════════════════════════════════════════════════════════════

class FilesetTreeWidget(QWidget):
    """左侧文件集面板 — Echoview Fileset 风格"""

    fileset_selected = Signal(object)      # Fileset
    file_selected = Signal(Path)            # 单个 raw 文件路径
    import_requested = Signal()             # 请求打开批量导入
    channel_selected = Signal(str)           # 频率通道名称

    def __init__(self, parent=None):
        super().__init__(parent)
        self._store = FilesetStore()
        self._filesets: dict[str, Fileset] = {}
        self._current_fileset: Fileset | None = None
        self._setup_ui()
        self._load_saved()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # ── 顶部按钮 ──
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(2)
        self.btn_import = QPushButton("📥 导入")
        self.btn_import.setToolTip("批量导入 .raw 文件到新文件集")
        self.btn_import.clicked.connect(self._on_import)
        self.btn_add = QPushButton("＋")
        self.btn_add.setToolTip("将文件添加到当前文件集")
        self.btn_add.clicked.connect(self._on_add_files)
        self.btn_del = QPushButton("🗑")
        self.btn_del.setToolTip("删除当前文件集")
        self.btn_del.clicked.connect(self._on_delete)
        btn_layout.addWidget(self.btn_import)
        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_del)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # ── 文件集树 ──
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["文件集 / 文件"])
        self.tree.setAlternatingRowColors(True)
        self.tree.setRootIsDecorated(True)
        self.tree.setIndentation(16)
        self.tree.header().setStretchLastSection(True)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.currentItemChanged.connect(self._on_item_changed)
        layout.addWidget(self.tree, 1)

        # ── 通道选择 ──
        ch_layout = QHBoxLayout()
        ch_layout.addWidget(QLabel("频率:"))
        self.ch_combo = QPushButton("全部")
        self.ch_combo.setEnabled(False)
        self.ch_combo.clicked.connect(self._on_channel_click)
        ch_layout.addWidget(self.ch_combo, 1)
        layout.addLayout(ch_layout)

        # ── 统计 ──
        self.lbl_stats = QLabel("")
        self.lbl_stats.setStyleSheet("color: #888; font-size: 10px; padding: 4px;")
        layout.addWidget(self.lbl_stats)

    # ── 按钮操作 ──

    def _on_import(self):
        dlg = BatchImportDialog(self)
        dlg.fileset_created.connect(self.add_fileset)
        dlg.exec()

    def _on_add_files(self):
        if self._current_fileset is None:
            QMessageBox.warning(self, "提示", "请先选中一个文件集")
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self, "添加 Raw 文件", "",
            "Raw 文件 (*.raw);;所有文件 (*)"
        )
        if paths:
            for p in paths:
                pp = Path(p)
                if pp not in self._current_fileset.files:
                    self._current_fileset.files.append(pp)
            self._refresh_tree()
            self._store.save(self._current_fileset)

    def _on_delete(self):
        if self._current_fileset is None:
            return
        reply = QMessageBox.question(
            self, "删除文件集",
            f"确定要删除文件集 '{self._current_fileset.name}' 吗？\n（不会删除实际文件）",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._store.delete(self._current_fileset.name)
            self._filesets.pop(self._current_fileset.name, None)
            self._current_fileset = None
            self._refresh_tree()

    def _on_channel_click(self):
        if self._current_fileset is None:
            return
        channels = self._current_fileset.channels
        if not channels:
            return
        menu = QMenu(self)
        for ch in channels:
            action = menu.addAction(ch)
            action.triggered.connect(lambda checked, c=ch: self._select_channel(c))
        menu.exec_(self.ch_combo.mapToGlobal(self.ch_combo.rect().bottomLeft()))

    def _select_channel(self, channel: str):
        self.ch_combo.setText(channel)
        self.channel_selected.emit(channel)

    # ── 树操作 ──

    def _on_item_changed(self, current, previous):
        if current is None:
            return
        # 顶层 = 文件集，子节点 = 文件
        parent = current.parent()
        if parent is None:
            # 选中文件集
            name = current.text(0)
            fs = self._filesets.get(name)
            if fs:
                self._current_fileset = fs
                self.fileset_selected.emit(fs)
                self._update_channel_combo(fs)
                self._update_stats(fs)
        else:
            # 选中文件
            path_str = current.data(0, Qt.UserRole)
            if path_str:
                self.file_selected.emit(Path(path_str))
            # 也更新父文件集
            parent_name = parent.text(0)
            fs = self._filesets.get(parent_name)
            if fs:
                self._current_fileset = fs
                self._update_channel_combo(fs)

    def _show_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if item is None:
            return
        menu = QMenu(self)
        if item.parent() is None:
            # 文件集
            menu.addAction("重命名", lambda: self._rename_fileset(item))
            menu.addAction("刷新", lambda: self._refresh_tree())
        else:
            menu.addAction("移除", lambda: self._remove_file(item))
            menu.addAction("打开所在文件夹", lambda: self._open_in_explorer(item))
        menu.exec_(self.tree.mapToGlobal(pos))

    def _rename_fileset(self, item):
        from PySide6.QtWidgets import QInputDialog
        old_name = item.text(0)
        new_name, ok = QInputDialog.getText(self, "重命名", "新名称:", text=old_name)
        if ok and new_name and new_name != old_name:
            fs = self._filesets.pop(old_name)
            fs.name = new_name
            self._filesets[new_name] = fs
            self._store.delete(old_name)
            self._store.save(fs)
            self._refresh_tree()

    def _remove_file(self, item):
        parent_item = item.parent()
        path_str = item.data(0, Qt.UserRole)
        path = Path(path_str)
        parent_name = parent_item.text(0)
        fs = self._filesets.get(parent_name)
        if fs and path in fs.files:
            fs.files.remove(path)
            fs.file_infos.pop(path_str, None)
            self._store.save(fs)
            self._refresh_tree()

    def _open_in_explorer(self, item):
        import subprocess
        path_str = item.data(0, Qt.UserRole)
        if path_str:
            folder = str(Path(path_str).parent)
            subprocess.run(["explorer", folder], shell=True, check=False)

    # ── 公共方法 ──

    def add_fileset(self, fileset: Fileset):
        """添加新文件集"""
        self._filesets[fileset.name] = fileset
        self._current_fileset = fileset
        self._store.save(fileset)
        self._refresh_tree()
        # 自动探测
        self._probe_fileset(fileset)
        # 立刻触发加载（不依赖 tree selection 信号）
        self.fileset_selected.emit(fileset)

    def get_current_fileset(self) -> Fileset | None:
        return self._current_fileset

    def refresh(self):
        self._load_saved()

    # ── 内部方法 ──

    def _load_saved(self):
        names = self._store.list()
        for name in names:
            fs = self._store.load(name)
            if fs:
                self._filesets[name] = fs
        self._refresh_tree()

    def _refresh_tree(self):
        self.tree.clear()
        for name, fs in self._filesets.items():
            fs_item = QTreeWidgetItem([name])
            fs_item.setData(0, Qt.UserRole, name)
            for f in fs.files:
                file_item = QTreeWidgetItem([f.name])
                file_item.setData(0, Qt.UserRole, str(f))
                file_item.setToolTip(0, str(f))
                # 如果有元信息，显示通道
                info = fs.file_infos.get(str(f))
                if info and info.channels:
                    file_item.setText(0, f"{f.name}  [{', '.join(info.channels)}]")
                fs_item.addChild(file_item)
            self.tree.addTopLevelItem(fs_item)
        self.tree.expandAll()

    def _probe_fileset(self, fileset: Fileset):
        """后台探测文件集"""
        self._worker = ProbeWorker(fileset)
        self._worker.all_done.connect(lambda: self._refresh_tree())
        self._worker.start()

    def _update_channel_combo(self, fileset: Fileset):
        channels = fileset.channels
        self.ch_combo.setEnabled(len(channels) > 0)
        if channels:
            self.ch_combo.setText(channels[0] if fileset.default_channel not in channels
                                  else fileset.default_channel)
        else:
            self.ch_combo.setText("--")

    def _update_stats(self, fileset: Fileset):
        total_files = fileset.file_count
        valid_files = sum(1 for info in fileset.file_infos.values() if info.is_valid)
        total_pings = fileset.total_pings
        self.lbl_stats.setText(
            f"文件: {total_files} 个 | 有效: {valid_files} | Ping: {total_pings:,}"
        )
