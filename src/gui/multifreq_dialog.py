"""多频率分析结果展示对话框

功能：
- 显示通道摘要表格（channel, frequency_Hz, n_pings, n_samples）
- 显示多频率 ABC 对比表格（channel, frequency_Hz, mean_abc, std_abc, max_abc）
- 少于2个通道时 ABC 对比区域显示提示信息
- 支持导出为 CSV
"""

import math

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.core.multifreq import (
    compare_frequencies,
    get_channel_summary,
)


class MultifreqDialog(QDialog):
    """多频率分析结果展示对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("多频率分析")
        self.setMinimumSize(600, 400)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint)

        # 存储原始数据，用于导出
        self._summary_df: pd.DataFrame | None = None
        self._compare_df: pd.DataFrame | None = None

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        # ── 标签页 ──
        self.tabs = QTabWidget()

        # 标签页 1: 通道摘要
        self.summary_tab = QWidget()
        self._setup_summary_tab()
        self.tabs.addTab(self.summary_tab, "通道摘要")

        # 标签页 2: 频率对比
        self.compare_tab = QWidget()
        self._setup_compare_tab()
        self.tabs.addTab(self.compare_tab, "频率对比")

        layout.addWidget(self.tabs, 1)

        # ── 底部按钮 ──
        btn_layout = QHBoxLayout()
        self.btn_export_csv = QPushButton("导出 CSV")
        self.btn_export_csv.setToolTip("导出当前标签页数据为 CSV 文件")
        self.btn_export_csv.clicked.connect(self._on_export_csv)

        self.btn_export_all = QPushButton("导出全部")
        self.btn_export_all.setToolTip("导出所有标签页数据到一个 Excel 文件")
        self.btn_export_all.clicked.connect(self._on_export_all)

        self.btn_copy = QPushButton("复制到剪贴板")
        self.btn_copy.setToolTip("复制当前表格数据到系统剪贴板")
        self.btn_copy.clicked.connect(self._on_copy)

        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_copy)
        btn_layout.addWidget(self.btn_export_csv)
        btn_layout.addWidget(self.btn_export_all)
        layout.addLayout(btn_layout)

    # ── 标签页构建 ──────────────────────────────────────────

    def _setup_summary_tab(self):
        """构建通道摘要标签页"""
        layout = QVBoxLayout(self.summary_tab)
        layout.setSpacing(8)
        layout.setContentsMargins(0, 8, 0, 0)

        group = QGroupBox("通道摘要")
        g_layout = QVBoxLayout()
        g_layout.setContentsMargins(8, 12, 8, 8)

        self.summary_table = QTableWidget()
        self.summary_table.setColumnCount(4)
        self.summary_table.setHorizontalHeaderLabels(
            ["通道", "频率 (Hz)", "Ping 数", "采样点数"]
        )
        self.summary_table.setAlternatingRowColors(True)
        self.summary_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.summary_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.summary_table.horizontalHeader().setStretchLastSection(True)
        self.summary_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

        g_layout.addWidget(self.summary_table)
        group.setLayout(g_layout)
        layout.addWidget(group)

    def _setup_compare_tab(self):
        """构建频率对比标签页"""
        layout = QVBoxLayout(self.compare_tab)
        layout.setSpacing(8)
        layout.setContentsMargins(0, 8, 0, 0)

        group = QGroupBox("多频率 ABC 对比")
        g_layout = QVBoxLayout()
        g_layout.setContentsMargins(8, 12, 8, 8)

        # 提示标签：少于 2 个通道时显示
        self.lbl_compare_hint = QLabel("需要至少 2 个通道才能进行频率对比")
        self.lbl_compare_hint.setAlignment(Qt.AlignCenter)
        self.lbl_compare_hint.setStyleSheet(
            "font-size: 13px; color: #999; padding: 20px;"
        )
        self.lbl_compare_hint.setVisible(False)
        g_layout.addWidget(self.lbl_compare_hint)

        self.compare_table = QTableWidget()
        self.compare_table.setColumnCount(5)
        self.compare_table.setHorizontalHeaderLabels(
            ["通道", "频率 (Hz)", "平均 ABC", "标准差 ABC", "最大 ABC"]
        )
        self.compare_table.setAlternatingRowColors(True)
        self.compare_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.compare_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.compare_table.horizontalHeader().setStretchLastSection(True)
        self.compare_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

        g_layout.addWidget(self.compare_table)
        group.setLayout(g_layout)
        layout.addWidget(group)

    # ── 数据加载 ──────────────────────────────────────────

    def load_data(self, ds_Sv, config):
        """加载数据并填充表格。

        Parameters
        ----------
        ds_Sv : xr.Dataset
            包含 Sv 数据的数据集
        config : dict
            分析配置参数
        """
        # 通道摘要
        self._summary_df = get_channel_summary(ds_Sv)
        self._populate_summary_table(self._summary_df)

        # 频率对比（需要至少 2 个通道）
        n_channels = len(self._summary_df)
        if n_channels >= 2:
            self._compare_df = compare_frequencies(ds_Sv, config)
            self._populate_compare_table(self._compare_df)
            self.lbl_compare_hint.setVisible(False)
            self.compare_table.setVisible(True)
        else:
            self._compare_df = pd.DataFrame()
            self.compare_table.setRowCount(0)
            self.lbl_compare_hint.setVisible(True)
            self.compare_table.setVisible(False)

    def _populate_summary_table(self, df: pd.DataFrame):
        """填充通道摘要表格"""
        self.summary_table.setRowCount(len(df))
        for row_idx, row in df.iterrows():
            self._set_item(self.summary_table, row_idx, 0, str(row["channel"]))
            self._set_item(self.summary_table, row_idx, 1, self._fmt_number(row["frequency_Hz"]))
            self._set_item(self.summary_table, row_idx, 2, str(int(row["n_pings"])))
            self._set_item(self.summary_table, row_idx, 3, str(int(row["n_samples"])))

    def _populate_compare_table(self, df: pd.DataFrame):
        """填充频率对比表格"""
        self.compare_table.setRowCount(len(df))
        for row_idx, row in df.iterrows():
            self._set_item(self.compare_table, row_idx, 0, str(row["channel"]))
            self._set_item(self.compare_table, row_idx, 1, self._fmt_number(row["frequency_Hz"]))
            self._set_item(self.compare_table, row_idx, 2, self._fmt_number(row["mean_abc"]))
            self._set_item(self.compare_table, row_idx, 3, self._fmt_number(row["std_abc"]))
            self._set_item(self.compare_table, row_idx, 4, self._fmt_number(row["max_abc"]))

    # ── 导出功能 ──────────────────────────────────────────

    def _on_export_csv(self):
        """导出当前标签页数据为 CSV"""
        current_tab = self.tabs.currentIndex()
        if current_tab == 0:
            df = self._summary_df
            name = "通道摘要"
        else:
            df = self._compare_df
            name = "频率对比"

        if df is None or df.empty:
            QMessageBox.warning(self, "警告", f"没有 {name} 数据可导出")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, f"导出 {name}", f"{name}.csv",
            "CSV 文件 (*.csv)"
        )
        if not file_path:
            return

        try:
            df.to_csv(file_path, index=False, encoding="utf-8-sig")
            QMessageBox.information(self, "导出成功", f"数据已导出到: {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出数据时出错: {e!s}")

    def _on_export_all(self):
        """导出所有数据到 Excel"""
        has_summary = self._summary_df is not None and not self._summary_df.empty
        has_compare = self._compare_df is not None and not self._compare_df.empty

        if not has_summary and not has_compare:
            QMessageBox.warning(self, "警告", "没有数据可导出")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出所有数据", "多频率分析.xlsx",
            "Excel 文件 (*.xlsx)"
        )
        if not file_path:
            return

        try:
            with pd.ExcelWriter(file_path) as writer:
                if has_summary:
                    self._summary_df.to_excel(writer, sheet_name="通道摘要", index=False)
                if has_compare:
                    self._compare_df.to_excel(writer, sheet_name="频率对比", index=False)
            QMessageBox.information(self, "导出成功", f"数据已导出到: {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出数据时出错: {e!s}")

    def _on_copy(self):
        """复制当前表格到剪贴板"""
        current_tab = self.tabs.currentIndex()
        table = self.summary_table if current_tab == 0 else self.compare_table

        rows = []
        # 表头
        headers = []
        for col in range(table.columnCount()):
            header = table.horizontalHeaderItem(col)
            headers.append(header.text() if header else "")
        rows.append("\t".join(headers))

        # 数据行
        for r in range(table.rowCount()):
            cells = []
            for c in range(table.columnCount()):
                item = table.item(r, c)
                cells.append(item.text() if item else "")
            rows.append("\t".join(cells))

        QApplication.clipboard().setText("\n".join(rows))
        QMessageBox.information(self, "复制成功", "数据已复制到剪贴板")

    # ── 工具方法 ──────────────────────────────────────────

    @staticmethod
    def _set_item(table: QTableWidget, row: int, col: int, text: str):
        """设置表格单元格内容"""
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignCenter)
        table.setItem(row, col, item)

    @staticmethod
    def _fmt_number(val) -> str:
        """格式化数值，NaN 显示为 '--'"""
        try:
            if val is None or (isinstance(val, float) and math.isnan(val)):
                return "--"
            return f"{val:,.2f}"
        except (TypeError, ValueError):
            return str(val)
