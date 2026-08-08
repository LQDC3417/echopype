"""左侧文件树组件"""

from pathlib import Path

from PySide6.QtCore import QDir, Signal
from PySide6.QtWidgets import QFileSystemModel, QTreeView


class FileTree(QTreeView):
    """文件系统树，显示 raw/zarr/csv 文件"""

    file_selected = Signal(Path)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._model = QFileSystemModel()
        self._model.setRootPath(QDir.currentPath())
        self._model.setNameFilters(["*.raw", "*.zarr", "*.csv", "*.yaml", "*.yml"])
        self._model.setNameFilterDisables(False)

        self.setModel(self._model)
        self.setRootIndex(self._model.index(QDir.currentPath()))
        self.setColumnHidden(1, True)
        self.setColumnHidden(2, True)
        self.setColumnHidden(3, True)
        self.setHeaderHidden(True)

        self.doubleClicked.connect(self._on_double_click)

    def set_root_path(self, path: str):
        """设置根目录"""
        self._model.setRootPath(path)
        self.setRootIndex(self._model.index(path))

    def _on_double_click(self, index):
        """双击文件"""
        file_path = Path(self._model.filePath(index))
        if file_path.is_file():
            self.file_selected.emit(file_path)
