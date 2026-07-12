"""统计结果弹出对话框 — 支持鱼群、密度、网格结果"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QGroupBox, QTabWidget, QWidget, QHBoxLayout, QPushButton, QFileDialog
)
from PySide6.QtCore import Qt, Signal


class StatsDialog(QDialog):
    """统计结果弹出对话框"""

    export_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("统计结果")
        self.setMinimumSize(600, 450)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint)

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
        btn_layout.addStretch()
        self.btn_export = QPushButton("导出")
        self.btn_export.clicked.connect(self.export_clicked)
        btn_layout.addWidget(self.btn_export)
        layout.addLayout(btn_layout)

    def _setup_summary_tab(self):
        layout = QVBoxLayout(self.summary_tab)
        layout.setSpacing(8)
        layout.setContentsMargins(0, 8, 0, 0)

        # 密度摘要
        summary_group = QGroupBox("密度摘要")
        summary_layout = QVBoxLayout()
        summary_layout.setContentsMargins(8, 12, 8, 8)

        self.lbl_abc = QLabel("ABC: --")
        self.lbl_abc.setStyleSheet("font-size: 13px; font-weight: bold; color: #2f855a;")
        self.lbl_density = QLabel("密度: --")
        self.lbl_density.setStyleSheet("font-size: 13px; font-weight: bold; color: #1a73e8;")
        self.lbl_biomass = QLabel("生物量: --")
        self.lbl_biomass.setStyleSheet("font-size: 13px; font-weight: bold; color: #c05621;")

        summary_layout.addWidget(self.lbl_abc)
        summary_layout.addWidget(self.lbl_density)
        summary_layout.addWidget(self.lbl_biomass)
        summary_group.setLayout(summary_layout)
        layout.addWidget(summary_group)

        # 鱼群列表
        schools_group = QGroupBox("鱼群列表")
        schools_layout = QVBoxLayout()
        schools_layout.setContentsMargins(8, 12, 8, 8)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "ID", "Ping 范围", "深度范围", "面积", "平均 Sv", "中心深度"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.verticalHeader().setVisible(False)

        schools_layout.addWidget(self.table)
        schools_group.setLayout(schools_layout)
        layout.addWidget(schools_group, 1)

    def _setup_grid_tab(self):
        layout = QVBoxLayout(self.grid_tab)
        layout.setSpacing(8)
        layout.setContentsMargins(0, 8, 0, 0)

        # 网格摘要
        self.lbl_grid_info = QLabel("网格: --")
        self.lbl_grid_info.setStyleSheet("font-size: 13px; font-weight: bold; color: #4a5568;")
        layout.addWidget(self.lbl_grid_info)

        # 网格统计表
        self.grid_table = QTableWidget()
        self.grid_table.setColumnCount(8)
        self.grid_table.setHorizontalHeaderLabels([
            "单元", "Ping 范围", "深度范围", "mean Sv", "ABC", "密度(ind/ha)", "生物量(kg/ha)", "有效像素"
        ])
        self.grid_table.horizontalHeader().setStretchLastSection(True)
        self.grid_table.setAlternatingRowColors(True)
        self.grid_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.grid_table.verticalHeader().setVisible(False)
        layout.addWidget(self.grid_table, 1)

    # ── 更新方法 ──

    def update_density(self, density_df):
        if density_df is None or density_df.empty:
            return
        row = density_df.iloc[0]
        self.lbl_abc.setText(f"ABC: {row.get('abc', 0):.6f} m²/m²")
        self.lbl_density.setText(f"密度: {row.get('density_ind_ha', 0):.2f} ind/ha")
        self.lbl_biomass.setText(f"生物量: {row.get('total_biomass_kg_ha', 0):.2f} kg/ha")

    def update_schools(self, schools_df):
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

    def update_grid(self, grid_df):
        """更新网格统计结果"""
        if grid_df is None or grid_df.empty:
            self.lbl_grid_info.setText("网格: 无数据")
            self.grid_table.setRowCount(0)
            return

        self.lbl_grid_info.setText(f"网格: {len(grid_df)} 个单元")
        self.grid_table.setRowCount(len(grid_df))

        for i, (_, row) in enumerate(grid_df.iterrows()):
            self.grid_table.setItem(i, 0, QTableWidgetItem(str(row.get("cell_id", ""))))
            self.grid_table.setItem(i, 1, QTableWidgetItem(
                f"{row.get('ping_start', '')} ~ {row.get('ping_end', '')}"))
            self.grid_table.setItem(i, 2, QTableWidgetItem(
                f"{row.get('depth_lo', 0):.1f} ~ {row.get('depth_hi', 0):.1f} m"))
            self.grid_table.setItem(i, 3, QTableWidgetItem(
                f"{row.get('mean_sv', 0):.1f}" if not _isnan(row.get('mean_sv')) else "--"))
            self.grid_table.setItem(i, 4, QTableWidgetItem(
                f"{row.get('abc', 0):.4f}" if not _isnan(row.get('abc')) else "--"))
            self.grid_table.setItem(i, 5, QTableWidgetItem(
                f"{row.get('density_ind_ha', 0):.1f}" if not _isnan(row.get('density_ind_ha')) else "--"))
            self.grid_table.setItem(i, 6, QTableWidgetItem(
                f"{row.get('biomass_kg_ha', 0):.2f}" if not _isnan(row.get('biomass_kg_ha')) else "--"))
            self.grid_table.setItem(i, 7, QTableWidgetItem(str(row.get("n_valid", 0))))

        # 自动切换到网格标签页
        self.tabs.setCurrentIndex(1)


def _isnan(val):
    """安全检查 NaN"""
    try:
        import math
        return val is None or math.isnan(float(val))
    except (TypeError, ValueError):
        return True
