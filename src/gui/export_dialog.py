"""导出格式选择对话框"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
)


class ExportDialog(QDialog):
    """导出格式选择对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("导出设置")
        self.setMinimumSize(300, 250)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        # ── 格式选择 ──
        format_group = QGroupBox("导出格式")
        format_layout = QVBoxLayout()
        format_layout.setContentsMargins(8, 12, 8, 8)

        self.chk_netcdf = QCheckBox("netCDF (.nc) — 推荐大数据集")
        self.chk_csv = QCheckBox("CSV (.csv) — 通用格式")
        self.chk_excel = QCheckBox("Excel (.xlsx) — 多 sheet")
        self.chk_zarr = QCheckBox("Zarr (.zarr) — 云优化")

        self.chk_csv.setChecked(True)
        self.chk_excel.setChecked(True)

        format_layout.addWidget(self.chk_netcdf)
        format_layout.addWidget(self.chk_csv)
        format_layout.addWidget(self.chk_excel)
        format_layout.addWidget(self.chk_zarr)
        format_group.setLayout(format_layout)
        layout.addWidget(format_group)

        # ── 导出内容 ──
        content_group = QGroupBox("导出内容")
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(8, 12, 8, 8)

        self.chk_sv = QCheckBox("Sv 数据")
        self.chk_schools = QCheckBox("鱼群清单")
        self.chk_density = QCheckBox("密度估算")
        self.chk_grid = QCheckBox("网格统计")

        self.chk_sv.setChecked(True)
        self.chk_schools.setChecked(True)
        self.chk_density.setChecked(True)

        content_layout.addWidget(self.chk_sv)
        content_layout.addWidget(self.chk_schools)
        content_layout.addWidget(self.chk_density)
        content_layout.addWidget(self.chk_grid)
        content_group.setLayout(content_layout)
        layout.addWidget(content_group)

        # ── 按钮 ──
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        btn_ok = QPushButton("导出")
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self.accept)
        btn_layout.addWidget(btn_ok)
        layout.addLayout(btn_layout)

    def get_formats(self) -> list[str]:
        """获取选中的导出格式"""
        formats = []
        if self.chk_netcdf.isChecked():
            formats.append("netcdf")
        if self.chk_csv.isChecked():
            formats.append("csv")
        if self.chk_excel.isChecked():
            formats.append("excel")
        if self.chk_zarr.isChecked():
            formats.append("zarr")
        return formats

    def get_content(self) -> dict:
        """获取选中的导出内容"""
        return {
            "sv": self.chk_sv.isChecked(),
            "schools": self.chk_schools.isChecked(),
            "density": self.chk_density.isChecked(),
            "grid": self.chk_grid.isChecked(),
        }
