"""统计结果弹出对话框 — 支持鱼群、密度、网格结果（增强版）

功能增强：
- 改进网格统计结果展示
- 添加数据可视化（表格增强）
- 支持数据导出（CSV、Excel、JSON）
- 添加数据过滤和排序功能
"""

import csv
import json
import math

import pandas as pd
from src.gui.i18n import T
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class StatsDialog(QDialog):
    """统计结果弹出对话框（增强版）"""

    export_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(T("stats_title"))
        self.setMinimumSize(800, 600)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint)

        # 存储原始数据
        self._schools_df = None
        self._integration_df = None
        self._real_sed_df = None

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        # ── 标签页 ──
        self.tabs = QTabWidget()

        # 标签页 1: 鱼群
        self.summary_tab = QWidget()
        self._setup_summary_tab()
        self.tabs.addTab(self.summary_tab, T("stats_tab_summary"))


        # 标签页 3: 回声积分
        self.integration_tab = QWidget()
        self._setup_integration_tab()
        self.tabs.addTab(self.integration_tab, T("stats_tab_integration"))

        # 标签页 3: 真实 SED
        self.real_sed_tab = QWidget()
        self._setup_real_sed_tab()
        self.tabs.addTab(self.real_sed_tab, T("stats_tab_real_sed"))

        layout.addWidget(self.tabs, 1)

        # ── 底部按钮 ──
        btn_layout = QHBoxLayout()

        # 导出按钮
        self.btn_export = QPushButton(T("stats_btn_export"))
        self.btn_export.setToolTip(T("stats_btn_export"))
        self.btn_export.clicked.connect(self._on_export_clicked)

        # 导出全部按钮
        self.btn_export_all = QPushButton(T("stats_btn_export_all"))
        self.btn_export_all.setToolTip(T("stats_btn_export_all"))
        self.btn_export_all.clicked.connect(self._on_export_all_clicked)

        # 复制按钮
        self.btn_copy = QPushButton(T("stats_btn_copy"))
        self.btn_copy.setToolTip(T("stats_btn_copy"))
        self.btn_copy.clicked.connect(self._on_copy_clicked)

        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_copy)
        btn_layout.addWidget(self.btn_export)
        btn_layout.addWidget(self.btn_export_all)
        layout.addLayout(btn_layout)

    def _setup_summary_tab(self):
        """设置摘要标签页"""
        layout = QVBoxLayout(self.summary_tab)
        layout.setSpacing(8)
        layout.setContentsMargins(0, 8, 0, 0)

        # 鱼群列表
        schools_group = QGroupBox(T("stats_school_list"))
        schools_layout = QVBoxLayout()
        schools_layout.setContentsMargins(8, 12, 8, 8)

        # 鱼群过滤
        filter_layout = QHBoxLayout()
        self.combo_school_filter = QComboBox()
        self.combo_school_filter.addItems(["--", "ID", "Ping", "Depth", "Area", "Sv", "Depth"])
        self.combo_school_filter.setToolTip(T("stats_filter"))

        self.edit_school_filter = QLineEdit()
        self.edit_school_filter.setPlaceholderText(T("stats_filter_placeholder"))
        self.edit_school_filter.setToolTip(T("stats_filter_placeholder"))
        self.edit_school_filter.textChanged.connect(self._on_school_filter_changed)

        filter_layout.addWidget(QLabel(T("stats_filter")))
        filter_layout.addWidget(self.combo_school_filter)
        filter_layout.addWidget(self.edit_school_filter)
        schools_layout.addLayout(filter_layout)

        self.school_table = QTableWidget()
        self.school_table.setColumnCount(6)
        self.school_table.setHorizontalHeaderLabels(T("school_headers"))
        self.school_table.horizontalHeader().setStretchLastSection(True)
        self.school_table.setAlternatingRowColors(True)
        self.school_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.school_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.school_table.verticalHeader().setVisible(False)
        self.school_table.setSortingEnabled(True)
        self.school_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.school_table.customContextMenuRequested.connect(self._on_school_context_menu)

        schools_layout.addWidget(self.school_table)
        schools_group.setLayout(schools_layout)
        layout.addWidget(schools_group, 1)
    def _setup_integration_tab(self):
        """设置回声积分标签页"""
        layout = QVBoxLayout(self.integration_tab)
        layout.setSpacing(8)
        layout.setContentsMargins(0, 8, 0, 0)

        summary_layout = QHBoxLayout()
        self.lbl_integration_info = QLabel(T("integration_info"))
        self.lbl_integration_info.setStyleSheet("font-size: 13px; font-weight: bold; color: #4a5568;")
        self.lbl_integration_stats = QLabel("--")
        self.lbl_integration_stats.setStyleSheet("font-size: 12px; color: #718096;")
        summary_layout.addWidget(self.lbl_integration_info)
        summary_layout.addStretch()
        summary_layout.addWidget(self.lbl_integration_stats)
        layout.addLayout(summary_layout)

        self.integration_table = QTableWidget()
        self.integration_table.setColumnCount(8)
        self.integration_table.setHorizontalHeaderLabels(T("integration_headers"))
        self.integration_table.horizontalHeader().setStretchLastSection(True)
        self.integration_table.setAlternatingRowColors(True)
        self.integration_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.integration_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.integration_table.verticalHeader().setVisible(False)
        self.integration_table.setSortingEnabled(True)
        self.integration_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.integration_table.customContextMenuRequested.connect(self._on_integration_context_menu)

        header = self.integration_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        for col in range(3, 7):
            header.setSectionResizeMode(col, QHeaderView.Stretch)
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)

        layout.addWidget(self.integration_table, 1)

    def _setup_real_sed_tab(self):
        """设置 SED 网格聚合标签页（复用回声积分网格）"""
        layout = QVBoxLayout(self.real_sed_tab)
        layout.setSpacing(8)
        layout.setContentsMargins(0, 8, 0, 0)

        summary_layout = QHBoxLayout()
        self.lbl_real_sed_info = QLabel(T("real_sed_info"))
        self.lbl_real_sed_info.setStyleSheet("font-size: 13px; font-weight: bold; color: #4a5568;")
        self.lbl_real_sed_stats = QLabel("--")
        self.lbl_real_sed_stats.setStyleSheet("font-size: 12px; color: #718096;")
        summary_layout.addWidget(self.lbl_real_sed_info)
        summary_layout.addStretch()
        summary_layout.addWidget(self.lbl_real_sed_stats)
        layout.addLayout(summary_layout)

        self.real_sed_table = QTableWidget()
        self.real_sed_table.setColumnCount(10)
        self.real_sed_table.setHorizontalHeaderLabels(T("real_sed_headers"))
        self.real_sed_table.horizontalHeader().setStretchLastSection(True)
        self.real_sed_table.setAlternatingRowColors(True)
        self.real_sed_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.real_sed_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.real_sed_table.verticalHeader().setVisible(False)
        self.real_sed_table.setSortingEnabled(True)
        self.real_sed_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.real_sed_table.customContextMenuRequested.connect(self._on_real_sed_context_menu)

        header = self.real_sed_table.horizontalHeader()
        for col in range(10):
            header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # Ping 范围
        header.setSectionResizeMode(2, QHeaderView.Stretch)  # 深度范围

        layout.addWidget(self.real_sed_table, 1)

    def _on_real_sed_context_menu(self, position):
        """真实 SED 表格右键菜单"""
        menu = QMenu(self)

        copy_action = QAction(T("stats_copy_selected"), self)
        copy_action.triggered.connect(lambda: self._copy_selected_rows(self.real_sed_table))
        menu.addAction(copy_action)

        copy_all_action = QAction(T("stats_copy_all"), self)
        copy_all_action.triggered.connect(lambda: self._copy_all_rows(self.real_sed_table))
        menu.addAction(copy_all_action)

        menu.addSeparator()

        export_action = QAction(T("stats_export_selected"), self)
        export_action.triggered.connect(lambda: self._export_selected_rows(self.real_sed_table))
        menu.addAction(export_action)

        menu.exec_(self.real_sed_table.viewport().mapToGlobal(position))

    def _on_integration_context_menu(self, position):
        """回声积分表格右键菜单"""
        menu = QMenu(self)

        copy_action = QAction(T("stats_copy_selected"), self)
        copy_action.triggered.connect(lambda: self._copy_selected_rows(self.integration_table))
        menu.addAction(copy_action)

        copy_all_action = QAction(T("stats_copy_all"), self)
        copy_all_action.triggered.connect(lambda: self._copy_all_rows(self.integration_table))
        menu.addAction(copy_all_action)

        menu.addSeparator()

        export_action = QAction(T("stats_export_selected"), self)
        export_action.triggered.connect(lambda: self._export_selected_rows(self.integration_table))
        menu.addAction(export_action)

        menu.exec_(self.integration_table.viewport().mapToGlobal(position))

    # ── 更新方法 ──

    def update_schools(self, schools_df):
        """更新鱼群列表"""
        if schools_df is None or schools_df.empty:
            self.school_table.setRowCount(0)
            return

        self._schools_df = schools_df
        self._populate_school_table(schools_df)

    def _populate_school_table(self, df):
        """填充鱼群表格"""
        self.school_table.setSortingEnabled(False)
        self.school_table.setRowCount(len(df))

        for i, (_, row) in enumerate(df.iterrows()):
            # ID
            item_id = QTableWidgetItem(str(row.get("school_id", "")))
            item_id.setTextAlignment(Qt.AlignCenter)
            self.school_table.setItem(i, 0, item_id)

            # Ping 范围
            ping_start = row.get('ping_start', '')
            ping_end = row.get('ping_end', '')
            item_ping = QTableWidgetItem(f"{ping_start} ~ {ping_end}")
            self.school_table.setItem(i, 1, item_ping)

            # 深度范围
            depth_start = row.get('depth_start', 0)
            depth_end = row.get('depth_end', 0)
            item_depth = QTableWidgetItem(f"{depth_start:.1f} ~ {depth_end:.1f} m")
            self.school_table.setItem(i, 2, item_depth)

            # 面积
            area_val = row.get('area', 0)
            item_area = QTableWidgetItem(f"{area_val:.1f}")
            item_area.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.school_table.setItem(i, 3, item_area)

            # 平均 Sv
            mean_sv = row.get('mean_sv', 0)
            item_sv = QTableWidgetItem(f"{mean_sv:.1f} dB")
            item_sv.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            # 根据 Sv 值设置颜色
            if mean_sv > -40:
                item_sv.setBackground(QBrush(QColor("#e6fffa")))
            elif mean_sv < -60:
                item_sv.setBackground(QBrush(QColor("#fed7d7")))
            self.school_table.setItem(i, 4, item_sv)

            # 中心深度
            centroid_depth = row.get('centroid_depth', 0)
            item_centroid = QTableWidgetItem(f"{centroid_depth:.1f} m")
            item_centroid.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.school_table.setItem(i, 5, item_centroid)

        self.school_table.setSortingEnabled(True)
    def update_integration(self, df):
        """更新回声积分结果"""
        if df is None or df.empty:
            self.lbl_integration_info.setText(T("integration_info"))
            self.lbl_integration_stats.setText("--")
            self.integration_table.setRowCount(0)
            return

        self._integration_df = df
        self.lbl_integration_info.setText(T("integration_info_fmt", n=len(df)))

        parts = []
        if "abc" in df.columns:
            abc = df["abc"].dropna()
            if len(abc):
                parts.append(f"ABC: {abc.mean():.2e} m²/m²")
        if "mean_Sv" in df.columns:
            sv = df["mean_Sv"].dropna()
            if len(sv):
                parts.append(f"Sv: {sv.mean():.1f} dB")
        if "density_ind_ha" in df.columns:
            den = df["density_ind_ha"].dropna()
            if len(den):
                parts.append(f"Density: {den.mean():.0f} ind/ha")
        self.lbl_integration_stats.setText(" | ".join(parts) if parts else "--")

        self._populate_integration_table(df)
        self.tabs.setCurrentIndex(1)

    def _populate_integration_table(self, df):
        """填充回声积分表格"""
        self.integration_table.setSortingEnabled(False)
        self.integration_table.setRowCount(len(df))

        for i, (_, row) in enumerate(df.iterrows()):
            item_esu = QTableWidgetItem(str(row.get("interval", "")))
            item_esu.setTextAlignment(Qt.AlignCenter)
            self.integration_table.setItem(i, 0, item_esu)

            self.integration_table.setItem(i, 1, QTableWidgetItem(
                f"{row.get('ping_start', '')} ~ {row.get('ping_end', '')}"))
            self.integration_table.setItem(i, 2, QTableWidgetItem(
                f"{row.get('depth_start', 0):.1f} ~ {row.get('depth_end', 0):.1f} m"))

            mean_sv = row.get("mean_Sv")
            if mean_sv is not None and not _isnan(mean_sv):
                item = QTableWidgetItem(f"{mean_sv:.1f}")
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if mean_sv > -40:
                    item.setBackground(QBrush(QColor("#e6fffa")))
                elif mean_sv < -60:
                    item.setBackground(QBrush(QColor("#fed7d7")))
                self.integration_table.setItem(i, 3, item)
            else:
                self.integration_table.setItem(i, 3, self._dash_item())

            abc = row.get("abc")
            if abc is not None and not _isnan(abc):
                item = QTableWidgetItem(f"{abc:.4e}")
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.integration_table.setItem(i, 4, item)
            else:
                self.integration_table.setItem(i, 4, self._dash_item())

            for col, key in ((5, "min_Sv"), (6, "max_Sv")):
                val = row.get(key)
                if val is not None and not _isnan(val):
                    item = QTableWidgetItem(f"{val:.1f}")
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    self.integration_table.setItem(i, col, item)
                else:
                    self.integration_table.setItem(i, col, self._dash_item())

            n_good = row.get("n_good", 0)
            item_n = QTableWidgetItem(str(int(n_good)))
            item_n.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.integration_table.setItem(i, 7, item_n)

            density = row.get("density_ind_ha")
            if density is not None and not _isnan(density):
                item_d = QTableWidgetItem(f"{density:.0f}")
                item_d.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if density > 1000:
                    item_d.setBackground(QBrush(QColor("#fed7d7")))
                elif density > 100:
                    item_d.setBackground(QBrush(QColor("#fefcbf")))
                self.integration_table.setItem(i, 8, item_d)
            else:
                self.integration_table.setItem(i, 8, self._dash_item())

        self.integration_table.setSortingEnabled(True)

    def _dash_item(self):
        item = QTableWidgetItem("--")
        item.setTextAlignment(Qt.AlignCenter)
        return item

    def update_real_sed(self, df):
        """更新 SED 网格聚合结果"""
        if df is None or df.empty:
            self.lbl_real_sed_info.setText(T("real_sed_info"))
            self.lbl_real_sed_stats.setText("--")
            self.real_sed_table.setRowCount(0)
            return

        self._real_sed_df = df
        cells_with_targets = int((df["n_targets"] > 0).sum())
        total_targets = int(df["n_targets"].sum())
        self.lbl_real_sed_info.setText(T("real_sed_info_fmt", n=cells_with_targets))

        parts = []
        if "ts_mean" in df.columns:
            ts_valid = df["ts_mean"].dropna()
            if len(ts_valid):
                parts.append(f"TS mean: {ts_valid.mean():.1f} dB")
        parts.append(f"Targets: {total_targets}")
        parts.append(f"Cells: {len(df)}")
        self.lbl_real_sed_stats.setText(" | ".join(parts))

        self._populate_real_sed_table(df)
        self.tabs.setCurrentIndex(2)

    def _populate_real_sed_table(self, df):
        """填充 SED 网格聚合表格（10 列）"""
        self.real_sed_table.setSortingEnabled(False)
        self.real_sed_table.setRowCount(len(df))

        for i, (_, row) in enumerate(df.iterrows()):
            # 0 ESU
            item = QTableWidgetItem(str(int(row.get("interval", 0))))
            item.setTextAlignment(Qt.AlignCenter)
            self.real_sed_table.setItem(i, 0, item)

            # 1 Ping 范围
            p0 = int(row.get("ping_start", 0))
            p1 = int(row.get("ping_end", 0))
            item = QTableWidgetItem(f"{p0} ~ {p1}")
            item.setTextAlignment(Qt.AlignCenter)
            self.real_sed_table.setItem(i, 1, item)

            # 2 深度范围
            d0 = row.get("depth_start", 0)
            d1 = row.get("depth_end", 0)
            item = QTableWidgetItem(f"{d0:.1f} ~ {d1:.1f} m")
            item.setTextAlignment(Qt.AlignCenter)
            self.real_sed_table.setItem(i, 2, item)

            # 3 目标数
            nt = int(row.get("n_targets", 0))
            item = QTableWidgetItem(str(nt))
            item.setTextAlignment(Qt.AlignCenter)
            if nt > 0:
                item.setBackground(QBrush(QColor("#e6fffa")))
            self.real_sed_table.setItem(i, 3, item)

            # 4-7 TS 统计
            for col_idx, key in [(4, "ts_mean"), (5, "ts_std"), (6, "ts_min"), (7, "ts_max")]:
                val = row.get(key)
                if val is not None and not _isnan(val):
                    item = QTableWidgetItem(f"{val:.1f}")
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    if col_idx == 4 and val > -40:
                        item.setBackground(QBrush(QColor("#e6fffa")))
                else:
                    item = self._dash_item()
                self.real_sed_table.setItem(i, col_idx, item)

            # 8-9 GPS 中心
            for col_idx, key in [(8, "center_lon"), (9, "center_lat")]:
                val = row.get(key)
                if val is not None and not _isnan(val):
                    item = QTableWidgetItem(f"{val:.6f}")
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    item = self._dash_item()
                self.real_sed_table.setItem(i, col_idx, item)

        self.real_sed_table.setSortingEnabled(True)

    # ── 过滤功能 ──

    def _on_school_filter_changed(self, text):
        """鱼群过滤文本改变"""
        filter_column = self.combo_school_filter.currentIndex() - 1  # -1 表示全部列
        self._filter_table(self.school_table, self._schools_df, filter_column, text)
    def _filter_table(self, table, df, column_index, filter_text):
        """过滤表格数据"""
        if df is None or df.empty:
            return

        if not filter_text:
            # 无过滤，显示所有行
            for row in range(table.rowCount()):
                table.setRowHidden(row, False)
            return

        filter_text_lower = filter_text.lower()

        for row in range(table.rowCount()):
            show_row = False

            if column_index == -1:
                # 搜索所有列
                for col in range(table.columnCount()):
                    item = table.item(row, col)
                    if item and filter_text_lower in item.text().lower():
                        show_row = True
                        break
            else:
                # 搜索指定列
                if column_index < table.columnCount():
                    item = table.item(row, column_index)
                    if item and filter_text_lower in item.text().lower():
                        show_row = True

            table.setRowHidden(row, not show_row)

    # ── 右键菜单 ──

    def _on_school_context_menu(self, position):
        """鱼群表格右键菜单"""
        menu = QMenu(self)

        copy_action = QAction(T("stats_copy_selected"), self)
        copy_action.triggered.connect(lambda: self._copy_selected_rows(self.school_table))
        menu.addAction(copy_action)

        copy_all_action = QAction(T("stats_copy_all"), self)
        copy_all_action.triggered.connect(lambda: self._copy_all_rows(self.school_table))
        menu.addAction(copy_all_action)

        menu.exec_(self.school_table.viewport().mapToGlobal(position))
    def _copy_selected_rows(self, table):
        """复制选中的行到剪贴板"""
        selected_rows = set()
        for item in table.selectedItems():
            selected_rows.add(item.row())

        if not selected_rows:
            return

        self._copy_rows_to_clipboard(table, sorted(selected_rows))

    def _copy_all_rows(self, table):
        """复制所有行到剪贴板"""
        all_rows = list(range(table.rowCount()))
        self._copy_rows_to_clipboard(table, all_rows)

    def _copy_rows_to_clipboard(self, table, rows):
        """将指定行复制到剪贴板"""
        if not rows:
            return

        # 获取表头
        headers = []
        for col in range(table.columnCount()):
            header_item = table.horizontalHeaderItem(col)
            headers.append(header_item.text() if header_item else "")

        # 获取数据
        data_lines = ["\t".join(headers)]
        for row in rows:
            row_data = []
            for col in range(table.columnCount()):
                item = table.item(row, col)
                row_data.append(item.text() if item else "")
            data_lines.append("\t".join(row_data))

        # 复制到剪贴板
        clipboard_text = "\n".join(data_lines)
        QApplication.clipboard().setText(clipboard_text)

        QMessageBox.information(self, T("stats_copy_success"), T("stats_copy_msg", n=len(rows)))

    def _export_selected_rows(self, table):
        """导出选中的行"""
        selected_rows = set()
        for item in table.selectedItems():
            selected_rows.add(item.row())

        if not selected_rows:
            QMessageBox.warning(self, T("dialog_warning"), T("stats_select_rows_warn"))
            return

        self._export_rows(table, sorted(selected_rows))

    def _export_rows(self, table, rows):
        """导出指定行到文件"""
        if not rows:
            return

        file_path, _selected_filter = QFileDialog.getSaveFileName(
            self, T("stats_btn_export"), "",
            "CSV (*.csv);;Excel (*.xlsx);;JSON (*.json)"
        )

        if not file_path:
            return

        try:
            # 获取表头
            headers = []
            for col in range(table.columnCount()):
                header_item = table.horizontalHeaderItem(col)
                headers.append(header_item.text() if header_item else f"col_{col}")

            # 获取数据
            data = []
            for row in rows:
                row_data = {}
                for col in range(table.columnCount()):
                    item = table.item(row, col)
                    row_data[headers[col]] = item.text() if item else ""
                data.append(row_data)

            # 根据文件类型导出
            if file_path.endswith('.csv'):
                with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.DictWriter(f, fieldnames=headers)
                    writer.writeheader()
                    writer.writerows(data)
            elif file_path.endswith('.xlsx'):
                df = pd.DataFrame(data)
                df.to_excel(file_path, index=False)
            elif file_path.endswith('.json'):
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

            QMessageBox.information(self, T("stats_export_success"), f"{file_path}")
        except Exception as e:
            QMessageBox.critical(self, T("stats_export_failed"), f"{e!s}")

    # ── 底部按钮功能 ──

    def _on_export_clicked(self):
        """导出当前标签页数据"""
        current_tab = self.tabs.currentIndex()

        if current_tab == 0:
            # 导出鱼群数据
            if self._schools_df is not None and not self._schools_df.empty:
                self._export_dataframe(self._schools_df, T("stats_school_list"))
            else:
                QMessageBox.warning(self, T("dialog_warning"), T("stats_no_school_data"))
        elif current_tab == 1:
            # 导出回声积分数据
            if self._integration_df is not None and not self._integration_df.empty:
                self._export_dataframe(self._integration_df, T("stats_tab_integration"))
            else:
                QMessageBox.warning(self, T("dialog_warning"), T("stats_no_integration_data"))
        elif current_tab == 2:
            # 导出单体目标数据（已删除）
            pass
            # 导出单体目标数据
        elif current_tab == 3:
            # 导出真实 SED 数据
            if self._real_sed_df is not None and not self._real_sed_df.empty:
                self._export_dataframe(self._real_sed_df, T("stats_tab_real_sed"))
            else:
                QMessageBox.warning(self, T("dialog_warning"), T("stats_no_real_sed_data"))

    def _on_export_all_clicked(self):
        """导出所有数据"""
        file_path, _selected_filter = QFileDialog.getSaveFileName(
            self, T("stats_btn_export_all"), "",
            "Excel (*.xlsx);;JSON (*.json)"
        )

        if not file_path:
            return

        try:
            if file_path.endswith('.xlsx'):
                with pd.ExcelWriter(file_path) as writer:
                    if self._schools_df is not None and not self._schools_df.empty:
                        self._schools_df.to_excel(writer, sheet_name=T("stats_school_list"), index=False)
                    if self._integration_df is not None and not self._integration_df.empty:
                        self._integration_df.to_excel(writer, sheet_name=T("stats_tab_integration"), index=False)
                    if self._real_sed_df is not None and not self._real_sed_df.empty:
                        self._real_sed_df.to_excel(writer, sheet_name=T("stats_tab_real_sed"), index=False)
            elif file_path.endswith('.json'):
                all_data = {}
                if self._schools_df is not None and not self._schools_df.empty:
                    all_data["schools"] = self._schools_df.to_dict(orient='records')
                if self._integration_df is not None and not self._integration_df.empty:
                    all_data["integration"] = self._integration_df.to_dict(orient='records')
                if self._real_sed_df is not None and not self._real_sed_df.empty:
                    all_data["real_sed"] = self._real_sed_df.to_dict(orient='records')

                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(all_data, f, ensure_ascii=False, indent=2)

            QMessageBox.information(self, T("stats_export_success"), f"{file_path}")
        except Exception as e:
            QMessageBox.critical(self, T("stats_export_failed"), f"{e!s}")

    def _on_copy_clicked(self):
        """复制当前表格到剪贴板"""
        current_tab = self.tabs.currentIndex()

        if current_tab == 0:
            self._copy_all_rows(self.school_table)
        elif current_tab == 1:
            self._copy_all_rows(self.integration_table)
        elif current_tab == 2:
            self._copy_all_rows(self.real_sed_table)

    def _export_dataframe(self, df, default_name):
        """导出 DataFrame 到文件"""
        file_path, _selected_filter = QFileDialog.getSaveFileName(
            self, f"{default_name}", default_name,
            "CSV (*.csv);;Excel (*.xlsx);;JSON (*.json)"
        )

        if not file_path:
            return

        try:
            if file_path.endswith('.csv'):
                df.to_csv(file_path, index=False, encoding='utf-8-sig')
            elif file_path.endswith('.xlsx'):
                df.to_excel(file_path, index=False)
            elif file_path.endswith('.json'):
                df.to_json(file_path, orient='records', force_ascii=False, indent=2)

            QMessageBox.information(self, T("stats_export_success"), f"{default_name}: {file_path}")
        except Exception as e:
            QMessageBox.critical(self, T("stats_export_failed"), f"{e!s}")


def _isnan(val):
    """安全检查 NaN"""
    try:
        return val is None or (isinstance(val, float) and math.isnan(val))
    except (TypeError, ValueError):
        return True
