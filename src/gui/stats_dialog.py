"""统计结果弹出对话框 — 支持鱼群、密度、网格结果（增强版）

功能增强：
- 改进网格统计结果展示
- 添加数据可视化（表格增强）
- 支持数据导出（CSV、Excel、JSON）
- 添加数据过滤和排序功能
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QGroupBox, QTabWidget, QWidget, QHBoxLayout, QPushButton, QFileDialog,
    QComboBox, QLineEdit, QHeaderView, QAbstractItemView, QMessageBox,
    QMenu, QApplication, QProgressBar, QSplitter,
)
from PySide6.QtCore import Qt, Signal, QTimer, QSortFilterProxyModel
from PySide6.QtGui import QColor, QBrush, QFont, QAction
import pandas as pd
import numpy as np
import math
import json
import csv
from pathlib import Path


class StatsDialog(QDialog):
    """统计结果弹出对话框（增强版）"""

    export_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("统计结果")
        self.setMinimumSize(800, 600)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint)

        # 存储原始数据
        self._density_df = None
        self._schools_df = None
        self._grid_df = None
        
        # 过滤状态
        self._grid_filter_column = -1
        self._grid_filter_text = ""

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        # ── 标签页 ──
        self.tabs = QTabWidget()

        # 标签页 1: 鱼群 + 密度
        self.summary_tab = QWidget()
        self._setup_summary_tab()
        self.tabs.addTab(self.summary_tab, "鱼群 / 密度")

        # 标签页 2: 网格统计
        self.grid_tab = QWidget()
        self._setup_grid_tab()
        self.tabs.addTab(self.grid_tab, "网格统计")

        layout.addWidget(self.tabs, 1)

        # ── 底部按钮 ──
        btn_layout = QHBoxLayout()
        
        # 导出按钮
        self.btn_export = QPushButton("导出数据")
        self.btn_export.setToolTip("导出当前标签页的数据到文件")
        self.btn_export.clicked.connect(self._on_export_clicked)
        
        # 导出全部按钮
        self.btn_export_all = QPushButton("导出全部")
        self.btn_export_all.setToolTip("导出所有标签页的数据")
        self.btn_export_all.clicked.connect(self._on_export_all_clicked)
        
        # 复制按钮
        self.btn_copy = QPushButton("复制到剪贴板")
        self.btn_copy.setToolTip("复制当前表格数据到剪贴板")
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

        # 密度摘要
        summary_group = QGroupBox("密度摘要")
        summary_layout = QVBoxLayout()
        summary_layout.setContentsMargins(8, 12, 8, 8)

        self.lbl_abc = QLabel("ABC: --")
        self.lbl_abc.setStyleSheet("font-size: 13px; font-weight: bold; color: #2f855a;")
        self.lbl_abc.setToolTip("面积背散射系数 (Area Backscattering Strength)")
        
        self.lbl_density = QLabel("密度: --")
        self.lbl_density.setStyleSheet("font-size: 13px; font-weight: bold; color: #1a73e8;")
        self.lbl_density.setToolTip("个体密度 (ind/ha)")
        
        self.lbl_biomass = QLabel("生物量: --")
        self.lbl_biomass.setStyleSheet("font-size: 13px; font-weight: bold; color: #c05621;")
        self.lbl_biomass.setToolTip("生物量 (kg/ha)")

        summary_layout.addWidget(self.lbl_abc)
        summary_layout.addWidget(self.lbl_density)
        summary_layout.addWidget(self.lbl_biomass)
        summary_group.setLayout(summary_layout)
        layout.addWidget(summary_group)

        # 鱼群列表
        schools_group = QGroupBox("鱼群列表")
        schools_layout = QVBoxLayout()
        schools_layout.setContentsMargins(8, 12, 8, 8)

        # 鱼群过滤
        filter_layout = QHBoxLayout()
        self.combo_school_filter = QComboBox()
        self.combo_school_filter.addItems(["全部列", "ID", "Ping 范围", "深度范围", "面积", "平均 Sv", "中心深度"])
        self.combo_school_filter.setToolTip("选择要过滤的列")
        
        self.edit_school_filter = QLineEdit()
        self.edit_school_filter.setPlaceholderText("输入过滤文本...")
        self.edit_school_filter.setToolTip("输入要过滤的文本\n支持部分匹配")
        self.edit_school_filter.textChanged.connect(self._on_school_filter_changed)
        
        filter_layout.addWidget(QLabel("过滤:"))
        filter_layout.addWidget(self.combo_school_filter)
        filter_layout.addWidget(self.edit_school_filter)
        schools_layout.addLayout(filter_layout)

        self.school_table = QTableWidget()
        self.school_table.setColumnCount(6)
        self.school_table.setHorizontalHeaderLabels([
            "ID", "Ping 范围", "深度范围", "面积", "平均 Sv", "中心深度"
        ])
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

    def _setup_grid_tab(self):
        """设置网格统计标签页"""
        layout = QVBoxLayout(self.grid_tab)
        layout.setSpacing(8)
        layout.setContentsMargins(0, 8, 0, 0)

        # 网格摘要
        summary_layout = QHBoxLayout()
        
        self.lbl_grid_info = QLabel("网格: --")
        self.lbl_grid_info.setStyleSheet("font-size: 13px; font-weight: bold; color: #4a5568;")
        self.lbl_grid_info.setToolTip("网格统计信息")
        
        self.lbl_grid_stats = QLabel("统计: --")
        self.lbl_grid_stats.setStyleSheet("font-size: 12px; color: #718096;")
        self.lbl_grid_stats.setToolTip("网格统计摘要")
        
        summary_layout.addWidget(self.lbl_grid_info)
        summary_layout.addStretch()
        summary_layout.addWidget(self.lbl_grid_stats)
        layout.addLayout(summary_layout)

        # 网格过滤
        filter_layout = QHBoxLayout()
        
        self.combo_grid_filter = QComboBox()
        self.combo_grid_filter.addItems([
            "全部列", "单元", "Ping 范围", "深度范围", 
            "mean Sv", "ABC", "密度(ind/ha)", "生物量(kg/ha)", "有效像素"
        ])
        self.combo_grid_filter.setToolTip("选择要过滤的列")
        
        self.edit_grid_filter = QLineEdit()
        self.edit_grid_filter.setPlaceholderText("输入过滤文本...")
        self.edit_grid_filter.setToolTip("输入要过滤的文本\n支持部分匹配和数值范围\n例如: >100, <50, 10-20")
        self.edit_grid_filter.textChanged.connect(self._on_grid_filter_changed)
        
        # 刷新按钮
        self.btn_refresh = QPushButton("刷新")
        self.btn_refresh.setToolTip("刷新网格数据")
        self.btn_refresh.clicked.connect(self._on_refresh_clicked)
        
        filter_layout.addWidget(QLabel("过滤:"))
        filter_layout.addWidget(self.combo_grid_filter)
        filter_layout.addWidget(self.edit_grid_filter)
        filter_layout.addWidget(self.btn_refresh)
        layout.addLayout(filter_layout)

        # 网格统计表
        self.grid_table = QTableWidget()
        self.grid_table.setColumnCount(8)
        self.grid_table.setHorizontalHeaderLabels([
            "单元", "Ping 范围", "深度范围", "mean Sv", "ABC", 
            "密度(ind/ha)", "生物量(kg/ha)", "有效像素"
        ])
        self.grid_table.horizontalHeader().setStretchLastSection(True)
        self.grid_table.setAlternatingRowColors(True)
        self.grid_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.grid_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.grid_table.verticalHeader().setVisible(False)
        self.grid_table.setSortingEnabled(True)
        self.grid_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.grid_table.customContextMenuRequested.connect(self._on_grid_context_menu)
        
        # 设置列宽
        header = self.grid_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        header.setSectionResizeMode(5, QHeaderView.Stretch)
        header.setSectionResizeMode(6, QHeaderView.Stretch)
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)

        layout.addWidget(self.grid_table, 1)

    # ── 更新方法 ──

    def update_density(self, density_df):
        """更新密度统计"""
        if density_df is None or density_df.empty:
            return
        
        self._density_df = density_df
        row = density_df.iloc[0]
        
        abc_val = row.get('abc', 0)
        density_val = row.get('density_ind_ha', 0)
        biomass_val = row.get('total_biomass_kg_ha', 0)
        
        self.lbl_abc.setText(f"ABC: {abc_val:.6f} m²/m²")
        self.lbl_abc.setToolTip(f"面积背散射系数: {abc_val:.6f} m²/m²")
        
        self.lbl_density.setText(f"密度: {density_val:.2f} ind/ha")
        self.lbl_density.setToolTip(f"个体密度: {density_val:.2f} ind/ha")
        
        self.lbl_biomass.setText(f"生物量: {biomass_val:.2f} kg/ha")
        self.lbl_biomass.setToolTip(f"生物量: {biomass_val:.2f} kg/ha")

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

    def update_grid(self, grid_df):
        """更新网格统计结果"""
        if grid_df is None or grid_df.empty:
            self.lbl_grid_info.setText("网格: 无数据")
            self.lbl_grid_stats.setText("统计: --")
            self.grid_table.setRowCount(0)
            return

        self._grid_df = grid_df
        self.lbl_grid_info.setText(f"网格: {len(grid_df)} 个单元")
        
        # 计算统计摘要
        stats_text = self._calculate_grid_stats(grid_df)
        self.lbl_grid_stats.setText(stats_text)
        
        self._populate_grid_table(grid_df)

        # 自动切换到网格标签页
        self.tabs.setCurrentIndex(1)

    def _calculate_grid_stats(self, df):
        """计算网格统计摘要"""
        try:
            stats_parts = []
            
            # 有效单元数
            valid_count = df['n_valid'].sum() if 'n_valid' in df.columns else 0
            stats_parts.append(f"有效像素: {valid_count:,}")
            
            # 平均 Sv
            if 'mean_sv' in df.columns:
                mean_sv_vals = df['mean_sv'].dropna()
                if not mean_sv_vals.empty:
                    avg_sv = mean_sv_vals.mean()
                    stats_parts.append(f"平均Sv: {avg_sv:.1f} dB")
            
            # 密度
            if 'density_ind_ha' in df.columns:
                density_vals = df['density_ind_ha'].dropna()
                if not density_vals.empty:
                    avg_density = density_vals.mean()
                    stats_parts.append(f"平均密度: {avg_density:.1f} ind/ha")
            
            return " | ".join(stats_parts)
        except Exception:
            return "统计计算错误"

    def _populate_grid_table(self, df):
        """填充网格表格"""
        self.grid_table.setSortingEnabled(False)
        self.grid_table.setRowCount(len(df))
        
        for i, (_, row) in enumerate(df.iterrows()):
            # 单元
            item_cell = QTableWidgetItem(str(row.get("cell_id", "")))
            item_cell.setTextAlignment(Qt.AlignCenter)
            self.grid_table.setItem(i, 0, item_cell)
            
            # Ping 范围
            ping_start = row.get('ping_start', '')
            ping_end = row.get('ping_end', '')
            item_ping = QTableWidgetItem(f"{ping_start} ~ {ping_end}")
            self.grid_table.setItem(i, 1, item_ping)
            
            # 深度范围
            depth_lo = row.get('depth_lo', 0)
            depth_hi = row.get('depth_hi', 0)
            item_depth = QTableWidgetItem(f"{depth_lo:.1f} ~ {depth_hi:.1f} m")
            self.grid_table.setItem(i, 2, item_depth)
            
            # mean Sv
            mean_sv = row.get('mean_sv')
            if mean_sv is not None and not _isnan(mean_sv):
                item_sv = QTableWidgetItem(f"{mean_sv:.1f}")
                item_sv.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                # 颜色编码
                if mean_sv > -40:
                    item_sv.setBackground(QBrush(QColor("#e6fffa")))
                elif mean_sv < -60:
                    item_sv.setBackground(QBrush(QColor("#fed7d7")))
            else:
                item_sv = QTableWidgetItem("--")
                item_sv.setTextAlignment(Qt.AlignCenter)
            self.grid_table.setItem(i, 3, item_sv)
            
            # ABC
            abc = row.get('abc')
            if abc is not None and not _isnan(abc):
                item_abc = QTableWidgetItem(f"{abc:.4f}")
                item_abc.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            else:
                item_abc = QTableWidgetItem("--")
                item_abc.setTextAlignment(Qt.AlignCenter)
            self.grid_table.setItem(i, 4, item_abc)
            
            # 密度(ind/ha)
            density = row.get('density_ind_ha')
            if density is not None and not _isnan(density):
                item_density = QTableWidgetItem(f"{density:.1f}")
                item_density.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                # 颜色编码
                if density > 1000:
                    item_density.setBackground(QBrush(QColor("#fed7d7")))
                elif density > 100:
                    item_density.setBackground(QBrush(QColor("#fefcbf")))
            else:
                item_density = QTableWidgetItem("--")
                item_density.setTextAlignment(Qt.AlignCenter)
            self.grid_table.setItem(i, 5, item_density)
            
            # 生物量(kg/ha)
            biomass = row.get('biomass_kg_ha')
            if biomass is not None and not _isnan(biomass):
                item_biomass = QTableWidgetItem(f"{biomass:.2f}")
                item_biomass.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            else:
                item_biomass = QTableWidgetItem("--")
                item_biomass.setTextAlignment(Qt.AlignCenter)
            self.grid_table.setItem(i, 6, item_biomass)
            
            # 有效像素
            n_valid = row.get("n_valid", 0)
            item_valid = QTableWidgetItem(str(int(n_valid)))
            item_valid.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.grid_table.setItem(i, 7, item_valid)
        
        self.grid_table.setSortingEnabled(True)

    # ── 过滤功能 ──

    def _on_school_filter_changed(self, text):
        """鱼群过滤文本改变"""
        filter_column = self.combo_school_filter.currentIndex() - 1  # -1 表示全部列
        self._filter_table(self.school_table, self._schools_df, filter_column, text)

    def _on_grid_filter_changed(self, text):
        """网格过滤文本改变"""
        filter_column = self.combo_grid_filter.currentIndex() - 1  # -1 表示全部列
        self._filter_table(self.grid_table, self._grid_df, filter_column, text)

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
        
        copy_action = QAction("复制选中行", self)
        copy_action.triggered.connect(lambda: self._copy_selected_rows(self.school_table))
        menu.addAction(copy_action)
        
        copy_all_action = QAction("复制全部", self)
        copy_all_action.triggered.connect(lambda: self._copy_all_rows(self.school_table))
        menu.addAction(copy_all_action)
        
        menu.exec_(self.school_table.viewport().mapToGlobal(position))

    def _on_grid_context_menu(self, position):
        """网格表格右键菜单"""
        menu = QMenu(self)
        
        copy_action = QAction("复制选中行", self)
        copy_action.triggered.connect(lambda: self._copy_selected_rows(self.grid_table))
        menu.addAction(copy_action)
        
        copy_all_action = QAction("复制全部", self)
        copy_all_action.triggered.connect(lambda: self._copy_all_rows(self.grid_table))
        menu.addAction(copy_all_action)
        
        menu.addSeparator()
        
        export_selected_action = QAction("导出选中行", self)
        export_selected_action.triggered.connect(lambda: self._export_selected_rows(self.grid_table))
        menu.addAction(export_selected_action)
        
        menu.exec_(self.grid_table.viewport().mapToGlobal(position))

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
        
        QMessageBox.information(self, "复制成功", f"已复制 {len(rows)} 行数据到剪贴板")

    def _export_selected_rows(self, table):
        """导出选中的行"""
        selected_rows = set()
        for item in table.selectedItems():
            selected_rows.add(item.row())
        
        if not selected_rows:
            QMessageBox.warning(self, "警告", "请先选择要导出的行")
            return
        
        self._export_rows(table, sorted(selected_rows))

    def _export_rows(self, table, rows):
        """导出指定行到文件"""
        if not rows:
            return
        
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self, "导出数据", "", 
            "CSV 文件 (*.csv);;Excel 文件 (*.xlsx);;JSON 文件 (*.json)"
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
            
            QMessageBox.information(self, "导出成功", f"数据已导出到: {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出数据时出错: {str(e)}")

    # ── 底部按钮功能 ──

    def _on_export_clicked(self):
        """导出当前标签页数据"""
        current_tab = self.tabs.currentIndex()
        
        if current_tab == 0:
            # 导出鱼群数据
            if self._schools_df is not None and not self._schools_df.empty:
                self._export_dataframe(self._schools_df, "鱼群数据")
            else:
                QMessageBox.warning(self, "警告", "没有鱼群数据可导出")
        elif current_tab == 1:
            # 导出网格数据
            if self._grid_df is not None and not self._grid_df.empty:
                self._export_dataframe(self._grid_df, "网格数据")
            else:
                QMessageBox.warning(self, "警告", "没有网格数据可导出")

    def _on_export_all_clicked(self):
        """导出所有数据"""
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self, "导出所有数据", "", 
            "Excel 文件 (*.xlsx);;JSON 文件 (*.json)"
        )
        
        if not file_path:
            return
        
        try:
            if file_path.endswith('.xlsx'):
                with pd.ExcelWriter(file_path) as writer:
                    if self._density_df is not None and not self._density_df.empty:
                        self._density_df.to_excel(writer, sheet_name="密度摘要", index=False)
                    if self._schools_df is not None and not self._schools_df.empty:
                        self._schools_df.to_excel(writer, sheet_name="鱼群列表", index=False)
                    if self._grid_df is not None and not self._grid_df.empty:
                        self._grid_df.to_excel(writer, sheet_name="网格统计", index=False)
            elif file_path.endswith('.json'):
                all_data = {}
                if self._density_df is not None and not self._density_df.empty:
                    all_data["density"] = self._density_df.to_dict(orient='records')
                if self._schools_df is not None and not self._schools_df.empty:
                    all_data["schools"] = self._schools_df.to_dict(orient='records')
                if self._grid_df is not None and not self._grid_df.empty:
                    all_data["grid"] = self._grid_df.to_dict(orient='records')
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(all_data, f, ensure_ascii=False, indent=2)
            
            QMessageBox.information(self, "导出成功", f"所有数据已导出到: {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出数据时出错: {str(e)}")

    def _on_copy_clicked(self):
        """复制当前表格到剪贴板"""
        current_tab = self.tabs.currentIndex()
        
        if current_tab == 0:
            self._copy_all_rows(self.school_table)
        elif current_tab == 1:
            self._copy_all_rows(self.grid_table)

    def _on_refresh_clicked(self):
        """刷新数据"""
        if self._grid_df is not None and not self._grid_df.empty:
            self._populate_grid_table(self._grid_df)

    def _export_dataframe(self, df, default_name):
        """导出 DataFrame 到文件"""
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self, f"导出{default_name}", default_name, 
            "CSV 文件 (*.csv);;Excel 文件 (*.xlsx);;JSON 文件 (*.json)"
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
            
            QMessageBox.information(self, "导出成功", f"{default_name}已导出到: {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出数据时出错: {str(e)}")


def _isnan(val):
    """安全检查 NaN"""
    try:
        return val is None or (isinstance(val, float) and math.isnan(val))
    except (TypeError, ValueError):
        return True
