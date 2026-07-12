# Echogram GUI 可视化处理系统 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 echopype CLI 项目重构为 PySide6 桌面 GUI 应用，实现交互式 Echogram 可视化、噪声剔除、底部线编辑、鱼群显示和密度统计。

**Architecture:** PySide6 主窗口 + QOpenGLWidget echogram 渲染 + QThread 后台处理。核心处理逻辑从 `src/` 移动到 `src/core/`，GUI 模块在 `src/gui/`，OpenGL 渲染在 `src/viz/`。

**Tech Stack:** PySide6, PyOpenGL, echopype, numpy, pandas, xarray, scipy, matplotlib (colormap only)

---

## 文件结构

```
src/
├── app.py                    # 应用入口
├── gui/
│   ├── __init__.py
│   ├── main_window.py        # 主窗口 (QMainWindow)
│   ├── echogram_widget.py    # Echogram OpenGL 渲染 + 交互
│   ├── file_tree.py          # 左侧文件树
│   ├── property_panel.py     # 右侧属性面板 (参数 + 统计)
│   ├── status_bar.py         # 底部状态栏
│   ├── toolbars.py           # 工具栏
│   ├── dialogs.py            # 对话框
│   └── workers.py            # QThread 后台工作线程
├── core/
│   ├── __init__.py
│   ├── acoustic.py           # 从 src/acoustic.py 移入
│   ├── school.py             # 从 src/school.py 移入
│   ├── density.py            # 从 src/density.py 移入
│   └── utils.py              # 从 src/utils.py 移入
└── viz/
    ├── __init__.py
    └── opengl_renderer.py    # OpenGL echogram 渲染器
```

---

## Task 1: 项目重构 — 移动核心模块到 `src/core/`

**Files:**
- Move: `src/acoustic.py` → `src/core/acoustic.py`
- Move: `src/school.py` → `src/core/school.py`
- Move: `src/density.py` → `src/core/density.py`
- Move: `src/utils.py` → `src/core/utils.py`
- Create: `src/core/__init__.py`
- Modify: `tests/test_acoustic.py` (更新导入路径)
- Modify: `tests/test_school.py` (更新导入路径)
- Modify: `tests/test_density.py` (更新导入路径)
- Modify: `tests/test_config.py` (更新导入路径)
- Modify: `tests/test_integration.py` (更新导入路径)

- [ ] **Step 1: 创建目录并移动文件**

```bash
mkdir -p src/core src/gui src/viz
mv src/acoustic.py src/core/acoustic.py
mv src/school.py src/core/school.py
mv src/density.py src/core/density.py
mv src/utils.py src/core/utils.py
```

- [ ] **Step 2: 创建 `src/core/__init__.py`**

```python
"""核心处理模块"""
```

- [ ] **Step 3: 创建 `src/gui/__init__.py` 和 `src/viz/__init__.py`**

```python
# src/gui/__init__.py
"""GUI 模块"""
```

```python
# src/viz/__init__.py
"""可视化渲染模块"""
```

- [ ] **Step 4: 更新所有测试文件的导入路径**

`tests/test_acoustic.py`:
```python
from src.core.acoustic import load_raw_files, process_single_file
```

`tests/test_school.py`:
```python
from src.core.school import detect_schools, schools_to_dataframe
```

`tests/test_density.py`:
```python
from src.core.density import calculate_abc, estimate_density
```

`tests/test_config.py`:
```python
from src.core.utils import load_config, validate_config
```

`tests/test_integration.py`:
```python
from src.core.utils import load_config, validate_config
from src.core.acoustic import process_all_files
from src.core.school import detect_schools, schools_to_dataframe
from src.core.density import estimate_density
```

- [ ] **Step 5: 运行测试验证**

```bash
cd D:/Administrator/Desktop/echopype && python -m pytest tests/ -v
```

Expected: 19 passed, 1 skipped (same as before)

- [ ] **Step 6: Commit**

```bash
git add src/core/ src/gui/ src/viz/ tests/
git commit -m "refactor: move core modules to src/core/, prepare gui/viz directories"
```

---

## Task 2: 安装依赖

**Files:**
- Create: `requirements.txt`

- [ ] **Step 1: 安装 PySide6 和 PyOpenGL**

```bash
pip install PySide6>=6.6.0 PyOpenGL>=3.1.7
```

- [ ] **Step 2: 验证安装**

```bash
python -c "import PySide6; print(PySide6.__version__)"
python -c "import OpenGL; print(OpenGL.__version__)"
```

- [ ] **Step 3: 创建 `requirements.txt`**

```
PySide6>=6.6.0
PyOpenGL>=3.1.7
echopype>=0.9.0
numpy
pandas
xarray
scipy
pyyaml
matplotlib
```

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "deps: add PySide6 and PyOpenGL dependencies"
```

---

## Task 3: OpenGL Echogram 渲染器基础

**Files:**
- Create: `src/viz/opengl_renderer.py`

- [ ] **Step 1: 编写 OpenGL 渲染器**

`src/viz/opengl_renderer.py`:
```python
"""OpenGL Echogram 渲染器"""

import numpy as np
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent, QWheelEvent
from OpenGL.GL import *
import matplotlib.cm as cm


class EchogramRenderer(QOpenGLWidget):
    """OpenGL Echogram 渲染控件"""

    mouse_moved = Signal(float, float)
    region_selected = Signal(float, float, float, float)
    bottom_line_edited = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 300)

        self._sv_data = None
        self._texture_id = None
        self._texture_width = 0
        self._texture_height = 0
        self._data_width = 0
        self._data_height = 0

        self._zoom = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0

        self._vmin = -80.0
        self._vmax = -40.0
        self._colormap_name = "jet"

        self._noise_mask = None
        self._bottom_line = None
        self._school_mask = None
        self._selection_rect = None

        self._dragging = False
        self._drag_start = None
        self._panning = False
        self._pan_start = None

    def set_data(self, sv_data: np.ndarray):
        self._sv_data = sv_data
        self._texture_id = None
        self.update()

    def set_noise_mask(self, mask: np.ndarray):
        self._noise_mask = mask
        self.update()

    def set_bottom_line(self, bottom: np.ndarray):
        self._bottom_line = bottom
        self.update()

    def set_school_mask(self, mask: np.ndarray):
        self._school_mask = mask
        self.update()

    def set_colormap(self, name: str, vmin: float = -80, vmax: float = -40):
        self._colormap_name = name
        self._vmin = vmin
        self._vmax = vmax
        self._texture_id = None
        self.update()

    def initializeGL(self):
        glClearColor(0.0, 0.0, 0.0, 1.0)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glEnable(GL_TEXTURE_2D)

    def resizeGL(self, w, h):
        glViewport(0, 0, w, h)

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT)
        if self._sv_data is None:
            return

        w = self.width()
        h = self.height()

        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0, w, 0, h, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        glPushMatrix()
        glTranslatef(self._pan_x, self._pan_y, 0)
        glScalef(self._zoom, self._zoom, 1.0)

        self._render_echogram()
        if self._noise_mask is not None:
            self._render_noise_overlay()
        if self._bottom_line is not None:
            self._render_bottom_line()
        if self._school_mask is not None:
            self._render_school_overlay()
        if self._selection_rect is not None:
            self._render_selection_rect()

        glPopMatrix()

    def _sv_to_rgb(self, sv: np.ndarray) -> np.ndarray:
        normalized = np.clip((sv - self._vmin) / (self._vmax - self._vmin), 0, 1)
        colormap = cm.get_cmap(self._colormap_name)
        rgba = colormap(normalized)
        rgb = (rgba[:, :, :3] * 255).astype(np.uint8)
        return rgb

    def _ensure_texture(self):
        if self._texture_id is not None:
            return
        if self._sv_data is None:
            return

        rgb = self._sv_to_rgb(self._sv_data)
        h, w, _ = rgb.shape

        self._texture_width = 1
        while self._texture_width < w:
            self._texture_width *= 2
        self._texture_height = 1
        while self._texture_height < h:
            self._texture_height *= 2

        padded = np.zeros((self._texture_height, self._texture_width, 3), dtype=np.uint8)
        padded[:h, :w, :] = rgb

        if self._texture_id is None:
            self._texture_id = glGenTextures(1)

        glBindTexture(GL_TEXTURE_2D, self._texture_id)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, self._texture_width, self._texture_height,
                     0, GL_RGB, GL_UNSIGNED_BYTE, padded)

        self._data_width = w
        self._data_height = h

    def _render_echogram(self):
        self._ensure_texture()
        if self._texture_id is None:
            return

        glBindTexture(GL_TEXTURE_2D, self._texture_id)
        glColor3f(1, 1, 1)

        w = self._data_width
        h = self._data_height

        glBegin(GL_QUADS)
        glTexCoord2f(0, 0); glVertex2f(0, 0)
        glTexCoord2f(w / self._texture_width, 0); glVertex2f(w, 0)
        glTexCoord2f(w / self._texture_width, h / self._texture_height); glVertex2f(w, h)
        glTexCoord2f(0, h / self._texture_height); glVertex2f(0, h)
        glEnd()

    def _render_noise_overlay(self):
        mask = self._noise_mask
        if mask is None:
            return
        h, w = mask.shape
        glColor4f(0.5, 0.5, 0.5, 0.4)
        glDisable(GL_TEXTURE_2D)
        for y in range(h):
            for x in range(w):
                if mask[y, x]:
                    glBegin(GL_QUADS)
                    glVertex2f(x, y); glVertex2f(x + 1, y)
                    glVertex2f(x + 1, y + 1); glVertex2f(x, y + 1)
                    glEnd()
        glEnable(GL_TEXTURE_2D)

    def _render_bottom_line(self):
        if self._bottom_line is None:
            return
        glDisable(GL_TEXTURE_2D)
        glColor3f(1, 1, 1)
        glLineWidth(2.0)
        glBegin(GL_LINE_STRIP)
        for i, depth in enumerate(self._bottom_line):
            if np.isfinite(depth):
                glVertex2f(i, depth)
        glEnd()
        glEnable(GL_TEXTURE_2D)

    def _render_school_overlay(self):
        mask = self._school_mask
        if mask is None:
            return
        glDisable(GL_TEXTURE_2D)
        glColor4f(0, 1, 0, 0.6)
        glLineWidth(1.5)
        h, w = mask.shape
        for y in range(h - 1):
            for x in range(w - 1):
                if mask[y, x]:
                    if x + 1 < w and not mask[y, x + 1]:
                        glBegin(GL_LINES)
                        glVertex2f(x + 1, y); glVertex2f(x + 1, y + 1)
                        glEnd()
                    if y + 1 < h and not mask[y + 1, x]:
                        glBegin(GL_LINES)
                        glVertex2f(x, y + 1); glVertex2f(x + 1, y + 1)
                        glEnd()
                    if x > 0 and not mask[y, x - 1]:
                        glBegin(GL_LINES)
                        glVertex2f(x, y); glVertex2f(x, y + 1)
                        glEnd()
                    if y > 0 and not mask[y - 1, x]:
                        glBegin(GL_LINES)
                        glVertex2f(x, y); glVertex2f(x + 1, y)
                        glEnd()
        glEnable(GL_TEXTURE_2D)

    def _render_selection_rect(self):
        if self._selection_rect is None:
            return
        x1, y1, x2, y2 = self._selection_rect
        glDisable(GL_TEXTURE_2D)
        glColor4f(0, 0.5, 1, 0.3)
        glBegin(GL_QUADS)
        glVertex2f(x1, y1); glVertex2f(x2, y1)
        glVertex2f(x2, y2); glVertex2f(x1, y2)
        glEnd()
        glColor4f(0, 0.5, 1, 0.8)
        glLineWidth(1.0)
        glBegin(GL_LINE_LOOP)
        glVertex2f(x1, y1); glVertex2f(x2, y1)
        glVertex2f(x2, y2); glVertex2f(x1, y2)
        glEnd()
        glEnable(GL_TEXTURE_2D)

    def _screen_to_data(self, sx, sy):
        gl_y = self.height() - sy
        dx = (sx - self._pan_x) / self._zoom
        dy = (gl_y - self._pan_y) / self._zoom
        return dx, dy

    def wheelEvent(self, event: QWheelEvent):
        delta = event.angleDelta().y()
        factor = 1.1 if delta > 0 else 0.9
        self._zoom = max(0.1, min(50.0, self._zoom * factor))
        self.update()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MiddleButton:
            self._panning = True
            self._pan_start = (event.x(), event.y())
        elif event.button() == Qt.LeftButton:
            dx, dy = self._screen_to_data(event.x(), event.y())
            self._dragging = True
            self._drag_start = (dx, dy)
            self._selection_rect = None

    def mouseMoveEvent(self, event: QMouseEvent):
        dx, dy = self._screen_to_data(event.x(), event.y())
        self.mouse_moved.emit(dx, dy)
        if self._panning and self._pan_start:
            dx_pan = event.x() - self._pan_start[0]
            dy_pan = event.y() - self._pan_start[1]
            self._pan_x += dx_pan
            self._pan_y -= dy_pan
            self._pan_start = (event.x(), event.y())
            self.update()
        if self._dragging and self._drag_start:
            x1, y1 = self._drag_start
            self._selection_rect = (x1, y1, dx, dy)
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MiddleButton:
            self._panning = False
            self._pan_start = None
        elif event.button() == Qt.LeftButton:
            if self._dragging and self._selection_rect:
                x1, y1, x2, y2 = self._selection_rect
                self.region_selected.emit(
                    min(x1, x2), min(y1, y2),
                    max(x1, x2), max(y1, y2)
                )
            self._dragging = False
            self._drag_start = None

    def reset_view(self):
        self._zoom = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self._selection_rect = None
        self.update()
```

- [ ] **Step 2: 验证导入**

```bash
cd D:/Administrator/Desktop/echopype && python -c "from src.viz.opengl_renderer import EchogramRenderer; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add src/viz/opengl_renderer.py
git commit -m "feat: OpenGL echogram renderer with zoom, pan, overlays"
```

---

## Task 4: 后台工作线程

**Files:**
- Create: `src/gui/workers.py`

- [ ] **Step 1: 编写工作线程**

`src/gui/workers.py`:
```python
"""后台处理工作线程"""

from PySide6.QtCore import QThread, Signal
from pathlib import Path


class LoadFileWorker(QThread):
    finished = Signal(object)
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, raw_file: Path, config: dict):
        super().__init__()
        self.raw_file = raw_file
        self.config = config

    def run(self):
        try:
            from src.core.acoustic import open_single_file
            self.progress.emit(f"加载文件: {self.raw_file.name}")
            echodata = open_single_file(self.raw_file, self.config)
            self.finished.emit(echodata)
        except Exception as e:
            self.error.emit(str(e))


class ComputeSvWorker(QThread):
    finished = Signal(object)
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, echodata, config: dict):
        super().__init__()
        self.echodata = echodata
        self.config = config

    def run(self):
        try:
            from src.core.acoustic import process_single_file
            self.progress.emit("计算 Sv...")
            ds_Sv = process_single_file(self.echodata, self.config)
            self.finished.emit(ds_Sv)
        except Exception as e:
            self.error.emit(str(e))


class NoiseRemovalWorker(QThread):
    finished = Signal(object)
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, ds_Sv, config: dict, manual_mask=None):
        super().__init__()
        self.ds_Sv = ds_Sv
        self.config = config
        self.manual_mask = manual_mask

    def run(self):
        try:
            from echopype.clean import remove_background_noise
            noise_cfg = self.config.get("processing", {}).get("noise_removal", {})
            self.progress.emit("去除背景噪声...")
            ds = remove_background_noise(
                self.ds_Sv,
                ping_num=noise_cfg.get("ping_num", 5),
                range_sample_num=noise_cfg.get("range_sample_num", 10),
                SNR_threshold=noise_cfg.get("SNR_threshold", "3.0dB"),
            )
            if "Sv_corrected" in ds:
                ds["Sv"] = ds["Sv_corrected"]
            self.finished.emit(ds)
        except Exception as e:
            self.error.emit(str(e))


class DetectSeafloorWorker(QThread):
    finished = Signal(object)
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, ds_Sv, config: dict):
        super().__init__()
        self.ds_Sv = ds_Sv
        self.config = config

    def run(self):
        try:
            from echopype.mask import detect_seafloor
            bottom_cfg = self.config.get("processing", {}).get("bottom_detection", {})
            channel = str(self.ds_Sv["channel"].values[0])
            self.progress.emit("检测底部...")
            params = {
                "var_name": "Sv",
                "channel": channel,
                "threshold": bottom_cfg.get("threshold", -50.0),
                "offset_m": bottom_cfg.get("offset_m", 0.5),
                "bin_skip_from_surface": bottom_cfg.get("bin_skip_from_surface", 200),
            }
            bottom = detect_seafloor(
                self.ds_Sv,
                method=bottom_cfg.get("method", "basic"),
                params=params,
            )
            self.finished.emit(bottom)
        except Exception as e:
            self.error.emit(str(e))


class DetectSchoolsWorker(QThread):
    finished = Signal(object, object)
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, ds_Sv, config: dict):
        super().__init__()
        self.ds_Sv = ds_Sv
        self.config = config

    def run(self):
        try:
            from src.core.school import detect_schools, schools_to_dataframe
            self.progress.emit("检测鱼群...")
            mask = detect_schools(self.ds_Sv, self.config)
            df = schools_to_dataframe(mask, self.ds_Sv)
            self.finished.emit(mask, df)
        except Exception as e:
            self.error.emit(str(e))


class DensityWorker(QThread):
    finished = Signal(object)
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, schools_df, ds_Sv, config: dict):
        super().__init__()
        self.schools_df = schools_df
        self.ds_Sv = ds_Sv
        self.config = config

    def run(self):
        try:
            from src.core.density import estimate_density
            self.progress.emit("计算密度...")
            df = estimate_density(self.schools_df, self.ds_Sv, self.config)
            self.finished.emit(df)
        except Exception as e:
            self.error.emit(str(e))
```

- [ ] **Step 2: Commit**

```bash
git add src/gui/workers.py
git commit -m "feat: QThread background workers for data processing"
```

---

## Task 5: 文件树组件

**Files:**
- Create: `src/gui/file_tree.py`

- [ ] **Step 1: 编写文件树**

`src/gui/file_tree.py`:
```python
"""左侧文件树组件"""

from pathlib import Path
from PySide6.QtWidgets import QTreeView, QFileSystemModel
from PySide6.QtCore import QDir, Signal


class FileTree(QTreeView):
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
        self._model.setRootPath(path)
        self.setRootIndex(self._model.index(path))

    def _on_double_click(self, index):
        file_path = Path(self._model.filePath(index))
        if file_path.is_file():
            self.file_selected.emit(file_path)
```

- [ ] **Step 2: Commit**

```bash
git add src/gui/file_tree.py
git commit -m "feat: file tree component"
```

---

## Task 6: 属性面板组件

**Files:**
- Create: `src/gui/property_panel.py`

- [ ] **Step 1: 编写属性面板**

`src/gui/property_panel.py`:
```python
"""右侧属性面板"""

from PySide6.QtWidgets import (
    QTabWidget, QWidget, QVBoxLayout, QFormLayout,
    QLabel, QSpinBox, QDoubleSpinBox, QPushButton,
    QTableWidget, QTableWidgetItem, QGroupBox, QScrollArea,
)
from PySide6.QtCore import Signal


class FileInfoTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QFormLayout(self)
        self.lbl_sonar = QLabel("--")
        self.lbl_freq = QLabel("--")
        self.lbl_pings = QLabel("--")
        self.lbl_samples = QLabel("--")
        layout.addRow("声呐型号:", self.lbl_sonar)
        layout.addRow("频率:", self.lbl_freq)
        layout.addRow("Ping 数:", self.lbl_pings)
        layout.addRow("采样点数:", self.lbl_samples)

    def update_info(self, ds_Sv):
        if ds_Sv is None:
            return
        if "channel" in ds_Sv:
            self.lbl_freq.setText(str(ds_Sv["channel"].values[0]))
        if "ping_time" in ds_Sv:
            self.lbl_pings.setText(str(len(ds_Sv["ping_time"])))
        if "range_sample" in ds_Sv:
            self.lbl_samples.setText(str(len(ds_Sv["range_sample"])))


class ProcessingTab(QWidget):
    noise_params_changed = Signal(dict)
    detect_bottom_clicked = Signal()
    detect_schools_clicked = Signal()
    compute_density_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)

        # 噪声去除
        noise_group = QGroupBox("噪声去除")
        noise_layout = QFormLayout()
        self.spin_ping_num = QSpinBox(); self.spin_ping_num.setRange(1, 100); self.spin_ping_num.setValue(5)
        self.spin_range_num = QSpinBox(); self.spin_range_num.setRange(1, 100); self.spin_range_num.setValue(10)
        self.spin_snr = QDoubleSpinBox(); self.spin_snr.setRange(0, 30); self.spin_snr.setValue(3.0); self.spin_snr.setSuffix(" dB")
        noise_layout.addRow("Ping 数:", self.spin_ping_num)
        noise_layout.addRow("Range 样本数:", self.spin_range_num)
        noise_layout.addRow("SNR 阈值:", self.spin_snr)
        noise_group.setLayout(noise_layout)
        layout.addWidget(noise_group)
        self.spin_ping_num.valueChanged.connect(self._emit_noise)
        self.spin_range_num.valueChanged.connect(self._emit_noise)
        self.spin_snr.valueChanged.connect(self._emit_noise)

        # 底部检测
        bottom_group = QGroupBox("底部检测")
        bottom_layout = QFormLayout()
        self.spin_threshold = QDoubleSpinBox(); self.spin_threshold.setRange(-100, 0); self.spin_threshold.setValue(-50.0); self.spin_threshold.setSuffix(" dB")
        self.spin_offset = QDoubleSpinBox(); self.spin_offset.setRange(0, 10); self.spin_offset.setValue(0.5); self.spin_offset.setSuffix(" m")
        self.spin_bin_skip = QSpinBox(); self.spin_bin_skip.setRange(0, 1000); self.spin_bin_skip.setValue(200)
        self.btn_detect_bottom = QPushButton("重新检测底部")
        bottom_layout.addRow("阈值:", self.spin_threshold)
        bottom_layout.addRow("偏移:", self.spin_offset)
        bottom_layout.addRow("跳过表面样本:", self.spin_bin_skip)
        bottom_layout.addRow(self.btn_detect_bottom)
        bottom_group.setLayout(bottom_layout)
        layout.addWidget(bottom_group)
        self.btn_detect_bottom.clicked.connect(self.detect_bottom_clicked)

        # 鱼群检测
        school_group = QGroupBox("鱼群检测")
        school_layout = QFormLayout()
        self.spin_school_thr = QDoubleSpinBox(); self.spin_school_thr.setRange(-100, 0); self.spin_school_thr.setValue(-55.0); self.spin_school_thr.setSuffix(" dB")
        self.btn_detect_schools = QPushButton("检测鱼群")
        school_layout.addRow("Sv 阈值:", self.spin_school_thr)
        school_layout.addRow(self.btn_detect_schools)
        school_group.setLayout(school_layout)
        layout.addWidget(school_group)
        self.btn_detect_schools.clicked.connect(self.detect_schools_clicked)

        # 密度估算
        density_group = QGroupBox("密度估算")
        density_layout = QFormLayout()
        self.spin_ts = QDoubleSpinBox(); self.spin_ts.setRange(-60, 0); self.spin_ts.setValue(-30.0); self.spin_ts.setSuffix(" dB")
        self.btn_compute_density = QPushButton("计算密度")
        density_layout.addRow("TS 默认值:", self.spin_ts)
        density_layout.addRow(self.btn_compute_density)
        density_group.setLayout(density_layout)
        layout.addWidget(density_group)
        self.btn_compute_density.clicked.connect(self.compute_density_clicked)

        layout.addStretch()
        scroll.setWidget(container)
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(scroll)

    def _emit_noise(self):
        self.noise_params_changed.emit({
            "ping_num": self.spin_ping_num.value(),
            "range_sample_num": self.spin_range_num.value(),
            "SNR_threshold": f"{self.spin_snr.value()}dB",
        })


class StatsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.lbl_abc = QLabel("ABC: --")
        self.lbl_density = QLabel("密度: --")
        self.lbl_biomass = QLabel("生物量: --")
        layout.addWidget(self.lbl_abc)
        layout.addWidget(self.lbl_density)
        layout.addWidget(self.lbl_biomass)
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["ID", "Ping 范围", "深度范围", "面积", "平均 Sv", "中心深度"])
        layout.addWidget(self.table)

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
            self.table.setItem(i, 1, QTableWidgetItem(f"{row.get('ping_start', '')} ~ {row.get('ping_end', '')}"))
            self.table.setItem(i, 2, QTableWidgetItem(f"{row.get('depth_start', 0):.1f} ~ {row.get('depth_end', 0):.1f} m"))
            self.table.setItem(i, 3, QTableWidgetItem(f"{row.get('area', 0):.1f}"))
            self.table.setItem(i, 4, QTableWidgetItem(f"{row.get('mean_sv', 0):.1f} dB"))
            self.table.setItem(i, 5, QTableWidgetItem(f"{row.get('centroid_depth', 0):.1f} m"))


class PropertyPanel(QTabWidget):
    noise_params_changed = Signal(dict)
    detect_bottom_clicked = Signal()
    detect_schools_clicked = Signal()
    compute_density_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.file_info = FileInfoTab()
        self.processing = ProcessingTab()
        self.stats = StatsTab()
        self.addTab(self.file_info, "文件信息")
        self.addTab(self.processing, "处理参数")
        self.addTab(self.stats, "统计结果")
        self.processing.noise_params_changed.connect(self.noise_params_changed)
        self.processing.detect_bottom_clicked.connect(self.detect_bottom_clicked)
        self.processing.detect_schools_clicked.connect(self.detect_schools_clicked)
        self.processing.compute_density_clicked.connect(self.compute_density_clicked)
```

- [ ] **Step 2: Commit**

```bash
git add src/gui/property_panel.py
git commit -m "feat: property panel with file info, processing params, stats"
```

---

## Task 7: 工具栏和状态栏

**Files:**
- Create: `src/gui/toolbars.py`
- Create: `src/gui/status_bar.py`

- [ ] **Step 1: 编写工具栏**

`src/gui/toolbars.py`:
```python
"""工具栏"""

from enum import Enum
from PySide6.QtWidgets import QToolBar, QComboBox
from PySide6.QtGui import QAction
from PySide6.QtCore import Signal


class MouseMode(Enum):
    NAVIGATE = 0
    SELECT_NOISE = 1
    DRAW_BOTTOM = 2
    ADJUST_BOTTOM = 3
    INSPECT = 4


class MainToolBar(QToolBar):
    open_clicked = Signal()
    run_clicked = Signal()
    undo_clicked = Signal()
    export_clicked = Signal()
    reset_view_clicked = Signal()
    mode_changed = Signal(MouseMode)
    colormap_changed = Signal(str, float, float)

    def __init__(self, parent=None):
        super().__init__("主工具栏", parent)
        self.setMovable(False)

        self.act_open = QAction("打开", self)
        self.act_open.triggered.connect(self.open_clicked)
        self.addAction(self.act_open)

        self.act_run = QAction("运行全部", self)
        self.act_run.triggered.connect(self.run_clicked)
        self.addAction(self.act_run)

        self.addSeparator()

        self.act_undo = QAction("撤销", self)
        self.act_undo.setShortcut("Ctrl+Z")
        self.act_undo.triggered.connect(self.undo_clicked)
        self.addAction(self.act_undo)

        self.act_reset = QAction("重置视图", self)
        self.act_reset.triggered.connect(self.reset_view_clicked)
        self.addAction(self.act_reset)

        self.addSeparator()

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["导航", "框选噪声", "绘制底部线", "调整底部线", "查看鱼群"])
        self.mode_combo.currentIndexChanged.connect(lambda idx: self.mode_changed.emit(MouseMode(idx)))
        self.addWidget(self.mode_combo)

        self.addSeparator()

        self.cmap_combo = QComboBox()
        self.cmap_combo.addItems(["jet", "viridis", "inferno", "grayscale"])
        self.cmap_combo.currentTextChanged.connect(self._on_cmap)
        self.addWidget(self.cmap_combo)

        self.addSeparator()

        self.act_export = QAction("导出", self)
        self.act_export.triggered.connect(self.export_clicked)
        self.addAction(self.act_export)

    def _on_cmap(self, name):
        if name == "grayscale":
            name = "gray"
        self.colormap_changed.emit(name, -80, -40)
```

- [ ] **Step 2: 编写状态栏**

`src/gui/status_bar.py`:
```python
"""底部状态栏"""

from PySide6.QtWidgets import QStatusBar, QProgressBar, QLabel


class MainStatusBar(QStatusBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lbl_status = QLabel("就绪")
        self.addWidget(self.lbl_status, 1)
        self.lbl_coords = QLabel("Ping: -- | Depth: --")
        self.addPermanentWidget(self.lbl_coords)
        self.progress = QProgressBar()
        self.progress.setMaximumWidth(200)
        self.progress.setVisible(False)
        self.addPermanentWidget(self.progress)

    def set_status(self, text: str):
        self.lbl_status.setText(text)

    def set_coords(self, ping: float, depth: float):
        self.lbl_coords.setText(f"Ping: {ping:.1f} | Depth: {depth:.1f} m")

    def show_progress(self, text: str = ""):
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        if text:
            self.lbl_status.setText(text)

    def hide_progress(self):
        self.progress.setVisible(False)
```

- [ ] **Step 3: Commit**

```bash
git add src/gui/toolbars.py src/gui/status_bar.py
git commit -m "feat: toolbar and status bar components"
```

---

## Task 8: 主窗口

**Files:**
- Create: `src/gui/main_window.py`

- [ ] **Step 1: 编写主窗口**

`src/gui/main_window.py`:
```python
"""主窗口"""

from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QFileDialog, QMessageBox,
)
from PySide6.QtCore import Qt, QTimer

from src.gui.echogram_widget import EchogramRenderer
from src.gui.file_tree import FileTree
from src.gui.property_panel import PropertyPanel
from src.gui.status_bar import MainStatusBar
from src.gui.toolbars import MainToolBar, MouseMode
from src.gui.workers import (
    LoadFileWorker, ComputeSvWorker, NoiseRemovalWorker,
    DetectSeafloorWorker, DetectSchoolsWorker, DensityWorker,
)
import numpy as np
import pandas as pd


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Echogram GUI — 鱼类资源评估系统")
        self.setMinimumSize(1200, 800)

        self._config = None
        self._echodata = None
        self._ds_Sv = None
        self._noise_mask_manual = None
        self._bottom_line = None
        self._schools_mask = None
        self._schools_df = None
        self._density_df = None
        self._current_worker = None
        self._undo_stack = []

        self._noise_timer = QTimer()
        self._noise_timer.setSingleShot(True)
        self._noise_timer.setInterval(300)
        self._noise_timer.timeout.connect(self._apply_noise_params)

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        self.toolbar = MainToolBar(self)
        self.addToolBar(self.toolbar)
        self.statusbar = MainStatusBar(self)
        self.setStatusBar(self.statusbar)

        splitter = QSplitter(Qt.Horizontal)
        self.file_tree = FileTree()
        splitter.addWidget(self.file_tree)
        self.echogram = EchogramRenderer()
        splitter.addWidget(self.echogram)
        self.property_panel = PropertyPanel()
        splitter.addWidget(self.property_panel)
        splitter.setSizes([200, 700, 300])
        self.setCentralWidget(splitter)

    def _connect_signals(self):
        self.toolbar.open_clicked.connect(self._open_file)
        self.toolbar.run_clicked.connect(self._run_all)
        self.toolbar.undo_clicked.connect(self._undo)
        self.toolbar.export_clicked.connect(self._export)
        self.toolbar.reset_view_clicked.connect(self.echogram.reset_view)
        self.toolbar.mode_changed.connect(self._on_mode_changed)
        self.toolbar.colormap_changed.connect(self.echogram.set_colormap)
        self.echogram.mouse_moved.connect(self.statusbar.set_coords)
        self.echogram.region_selected.connect(self._on_region_selected)
        self.property_panel.noise_params_changed.connect(self._on_noise_params_changed)
        self.property_panel.detect_bottom_clicked.connect(self._detect_bottom)
        self.property_panel.detect_schools_clicked.connect(self._detect_schools)
        self.property_panel.compute_density_clicked.connect(self._compute_density)
        self.file_tree.file_selected.connect(self._on_file_selected)

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "打开 raw 文件", "", "Raw 文件 (*.raw);;所有文件 (*)")
        if path:
            self._load_file(Path(path))

    def _on_file_selected(self, path: Path):
        if path.suffix == ".raw":
            self._load_file(path)

    def _load_file(self, path: Path):
        if self._config is None:
            self._config = {
                "processing": {
                    "sonar_model": "EK80", "waveform_mode": "CW", "encode_mode": "power",
                    "noise_removal": {"ping_num": 5, "range_sample_num": 10, "SNR_threshold": "3.0dB"},
                    "bottom_detection": {"method": "basic", "threshold": -50.0, "offset_m": 0.5, "bin_skip_from_surface": 200},
                },
                "school_detection": {"method": "echoview", "thr": -55.0, "mincan": [3, 10], "maxlink": [3, 15], "minsho": [3, 15]},
                "density": {"ts_default": -30.0},
            }
        self.statusbar.show_progress(f"加载: {path.name}")
        self._current_worker = LoadFileWorker(path, self._config)
        self._current_worker.finished.connect(self._on_file_loaded)
        self._current_worker.error.connect(self._on_worker_error)
        self._current_worker.progress.connect(self.statusbar.set_status)
        self._current_worker.start()

    def _on_file_loaded(self, echodata):
        self._echodata = echodata
        self._compute_sv()

    def _compute_sv(self):
        if self._echodata is None:
            return
        self.statusbar.show_progress("计算 Sv...")
        self._current_worker = ComputeSvWorker(self._echodata, self._config)
        self._current_worker.finished.connect(self._on_sv_computed)
        self._current_worker.error.connect(self._on_worker_error)
        self._current_worker.start()

    def _on_sv_computed(self, ds_Sv):
        self._ds_Sv = ds_Sv
        self.statusbar.hide_progress()
        sv = ds_Sv["Sv"].values
        if sv.ndim == 3:
            sv = sv[0]
        self.echogram.set_data(sv)
        self.property_panel.file_info.update_info(ds_Sv)

    def _on_noise_params_changed(self, params):
        self._noise_timer.start()

    def _apply_noise_params(self):
        if self._ds_Sv is None:
            return
        self.statusbar.show_progress("重新计算噪声...")
        self._current_worker = NoiseRemovalWorker(self._ds_Sv, self._config)
        self._current_worker.finished.connect(self._on_noise_removed)
        self._current_worker.error.connect(self._on_worker_error)
        self._current_worker.start()

    def _on_noise_removed(self, ds_Sv):
        self._ds_Sv = ds_Sv
        self.statusbar.hide_progress()
        sv = ds_Sv["Sv"].values
        if sv.ndim == 3:
            sv = sv[0]
        self.echogram.set_data(sv)

    def _on_region_selected(self, x1, y1, x2, y2):
        if self.toolbar.mode_combo.currentIndex() == MouseMode.SELECT_NOISE.value:
            self._add_noise_region(x1, y1, x2, y2)

    def _add_noise_region(self, x1, y1, x2, y2):
        if self._ds_Sv is None:
            return
        sv = self._ds_Sv["Sv"].values
        if sv.ndim == 3:
            sv = sv[0]
        h, w = sv.shape
        if self._noise_mask_manual is None:
            self._noise_mask_manual = np.zeros((h, w), dtype=bool)
        px1, py1 = max(0, int(min(x1, x2))), max(0, int(min(y1, y2)))
        px2, py2 = min(w, int(max(x1, x2))), min(h, int(max(y1, y2)))
        self._noise_mask_manual[py1:py2, px1:px2] = True
        self._undo_stack.append(("noise_mask", self._noise_mask_manual.copy()))
        self.echogram.set_noise_mask(self._noise_mask_manual)

    def _detect_bottom(self):
        if self._ds_Sv is None:
            QMessageBox.warning(self, "警告", "请先加载数据")
            return
        self.statusbar.show_progress("检测底部...")
        self._current_worker = DetectSeafloorWorker(self._ds_Sv, self._config)
        self._current_worker.finished.connect(self._on_bottom_detected)
        self._current_worker.error.connect(self._on_worker_error)
        self._current_worker.start()

    def _on_bottom_detected(self, bottom):
        self._bottom_line = bottom.values
        self._ds_Sv["bottom_depth"] = bottom
        self.echogram.set_bottom_line(self._bottom_line)
        self.statusbar.hide_progress()

    def _detect_schools(self):
        if self._ds_Sv is None:
            QMessageBox.warning(self, "警告", "请先加载数据")
            return
        self.statusbar.show_progress("检测鱼群...")
        self._current_worker = DetectSchoolsWorker(self._ds_Sv, self._config)
        self._current_worker.finished.connect(self._on_schools_detected)
        self._current_worker.error.connect(self._on_worker_error)
        self._current_worker.start()

    def _on_schools_detected(self, mask, df):
        self._schools_mask = mask.values
        self._schools_df = df
        self.echogram.set_school_mask(self._schools_mask)
        self.property_panel.stats.update_schools(df)
        self.statusbar.hide_progress()

    def _compute_density(self):
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
        self._density_df = df
        self.property_panel.stats.update_density(df)
        self.statusbar.hide_progress()

    def _run_all(self):
        if self._echodata is None:
            QMessageBox.warning(self, "警告", "请先加载文件")
            return
        self._compute_sv()

    def _undo(self):
        if not self._undo_stack:
            return
        action_type, data = self._undo_stack.pop()
        if action_type == "noise_mask":
            self._noise_mask_manual = data
            self.echogram.set_noise_mask(data)

    def _export(self):
        if self._density_df is None:
            QMessageBox.warning(self, "警告", "没有可导出的数据")
            return
        path, _ = QFileDialog.getSaveFileName(self, "导出 CSV", "", "CSV 文件 (*.csv)")
        if path:
            self._density_df.to_csv(path, index=False, encoding="utf-8-sig")

    def _on_mode_changed(self, mode: MouseMode):
        self.statusbar.set_status(f"模式: {mode.name}")

    def _on_worker_error(self, msg):
        self.statusbar.hide_progress()
        QMessageBox.critical(self, "错误", msg)
```

- [ ] **Step 2: Commit**

```bash
git add src/gui/main_window.py
git commit -m "feat: main window assembling all GUI components"
```

---

## Task 9: 应用入口

**Files:**
- Create: `src/app.py`

- [ ] **Step 1: 编写入口**

`src/app.py`:
```python
"""Echogram GUI 应用入口"""

import sys
import os
os.environ["PYTHONUTF8"] = "1"

from PySide6.QtWidgets import QApplication
from src.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Echogram GUI")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 验证启动**

```bash
cd D:/Administrator/Desktop/echopype && python src/app.py
```

Expected: 窗口打开，显示三栏布局

- [ ] **Step 3: Commit**

```bash
git add src/app.py
git commit -m "feat: application entry point"
```

---

## Task 10: 清理旧模块

**Files:**
- Delete: `src/cli.py`
- Delete: `src/viz.py`
- Delete: `tests/test_cli.py`
- Delete: `tests/test_viz.py`

- [ ] **Step 1: 删除旧文件**

```bash
rm src/cli.py src/viz.py tests/test_cli.py tests/test_viz.py
```

- [ ] **Step 2: 运行剩余测试**

```bash
cd D:/Administrator/Desktop/echopype && python -m pytest tests/ -v
```

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "refactor: remove old CLI and viz modules"
```

---

## Task 11: 集成验证

- [ ] **Step 1: 启动 GUI**

```bash
cd D:/Administrator/Desktop/echopype && python src/app.py
```

- [ ] **Step 2: 验证界面**
- 左侧文件树显示
- 中间 Echogram 区域
- 右侧属性面板三个标签页
- 工具栏按钮可用
- 状态栏显示

- [ ] **Step 3: Final Commit**

```bash
git add -A
git commit -m "feat: echopype GUI v1.0 — echogram visualization system"
```
