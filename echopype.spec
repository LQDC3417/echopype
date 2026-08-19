# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置 — Echogram 鱼类声学资源评估系统"""

import sys
from pathlib import Path

block_cipher = None

# 项目根目录
ROOT = Path(SPECPATH)

# 需要打包的数据文件
datas = [
    (str(ROOT / "configs"), "configs"),
    (str(ROOT / "docs"), "docs"),
]

# 隐式导入（PyInstaller 可能漏掉的模块）
hiddenimports = [
    "pickle",
    "pickletools",
    "multiprocessing",
    "multiprocessing.pool",
    "multiprocessing.context",
    "multiprocessing.reduction",
    "jaraco",
    "jaraco.text",
    "jaraco.functools",
    "jaraco.context",
    "pkg_resources",
    "echopype",
    "xarray",
    "numpy",
    "pandas",
    "scipy",
    "scipy.ndimage",
    "matplotlib",
    "matplotlib.cm",
    "matplotlib.colormaps",
    "PySide6.QtWidgets",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtOpenGLWidgets",
    "PyOpenGL",
    "PyOpenGL.GL",
    "yaml",
    "src.core.acoustic",
    "src.core.density",
    "src.core.integration",
    "src.core.school",
    "src.core.region",
    "src.core.quality",
    "src.core.multifreq",
    "src.core.single_target",
    "src.core.export",
    "src.core.utils",
    "src.gui.main_window",
    "src.gui.property_panel",
    "src.gui.toolbars",
    "src.gui.workers",
    "src.gui.theme",
    "src.gui.fileset_tree",
    "src.gui.fileset",
    "src.gui.variable_list",
    "src.gui.region_panel",
    "src.gui.stats_dialog",
    "src.gui.multifreq_dialog",
    "src.gui.quality_dialog",
    "src.gui.export_dialog",
    "src.gui.status_bar",
    "src.viz.opengl_renderer",
]

a = Analysis(
    [str(ROOT / "src" / "app.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "unittest",
        "test",
        "setuptools",
        "pip",
        "IPython",
        "jupyter",
        "PyQt5",
        "PyQt6",
        "sip",
        "pkg_resources",
        "setuptools",
        # Anaconda 大包排除
        "numba",
        "llvmlite",
        "scikit-learn",
        "sklearn",
        "scikit-image",
        "cv2",
        "opencv",
        "torch",
        "torchvision",
        "tensorflow",
        "keras",
        "bokeh",
        "holoviews",
        "panel",
        "streamlit",
        "flask",
        "django",
        "fastapi",
        "uvicorn",
        "sphinx",
        "docutils",
        "notebook",
        "ipykernel",
        "ipywidgets",
        "zmq",
        "tornado",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Echogram",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # 无控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 可添加 .ico 图标
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Echogram",
)


