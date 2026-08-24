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

from src.gui.i18n import T


class ExportDialog(QDialog):
    """导出格式选择对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(T("export_title"))
        self.setMinimumSize(300, 250)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        # ── 格式选择 ──
        format_group = QGroupBox(T("export_format_group"))
        format_layout = QVBoxLayout()
        format_layout.setContentsMargins(8, 12, 8, 8)

        self.chk_netcdf = QCheckBox(T("export_netcdf"))
        self.chk_csv = QCheckBox(T("export_csv"))
        self.chk_excel = QCheckBox(T("export_excel"))
        self.chk_zarr = QCheckBox(T("export_zarr"))

        self.chk_csv.setChecked(True)
        self.chk_excel.setChecked(True)

        format_layout.addWidget(self.chk_netcdf)
        format_layout.addWidget(self.chk_csv)
        format_layout.addWidget(self.chk_excel)
        format_layout.addWidget(self.chk_zarr)
        format_group.setLayout(format_layout)
        layout.addWidget(format_group)

        # ── 导出内容 ──
        content_group = QGroupBox(T("export_content_group"))
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(8, 12, 8, 8)

        self.chk_sv = QCheckBox(T("export_sv_data"))
        self.chk_schools = QCheckBox(T("export_school_list"))
        self.chk_grid = QCheckBox(T("export_grid_stats"))

        self.chk_sv.setChecked(True)
        self.chk_schools.setChecked(True)

        content_layout.addWidget(self.chk_sv)
        content_layout.addWidget(self.chk_schools)
        content_layout.addWidget(self.chk_grid)
        content_group.setLayout(content_layout)
        layout.addWidget(content_group)

        # ── 按钮 ──
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_cancel = QPushButton(T("export_cancel"))
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        btn_ok = QPushButton(T("export_confirm"))
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
            "grid": self.chk_grid.isChecked(),
        }
