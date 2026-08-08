"""测试 echogram 颜色映射切换显示效果"""

import sys
import os

os.environ["PYTHONUTF8"] = "1"

from PySide6.QtWidgets import QApplication
from src.gui.main_window import MainWindow
from src.gui.theme import DARK_THEME
from pathlib import Path
from src.core.acoustic import open_single_file, process_single_file


RAW_FILE = r"D:\Administrator\Desktop\echopype\raw_data\20250706SCSK-D20250706-T024009.raw"

CONFIG = {
    "processing": {
        "sonar_model": "EK80",
        "noise_removal": {"ping_num": 5, "range_sample_num": 10, "SNR_threshold": "3.0dB"},
        "bottom_detection": {"method": "basic", "threshold": -50.0, "offset_m": 0.5, "bin_skip_from_surface": 200},
    },
    "school_detection": {"method": "echoview", "thr": -55.0, "mincan": [3, 10], "maxlink": [3, 15], "minsho": [3, 15]},
    "density": {"ts_default": -30.0},
}


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_THEME)
    window = MainWindow()
    window.resize(1400, 900)
    window.show()

    print("加载数据...")
    ed = open_single_file(Path(RAW_FILE), CONFIG)
    ds = process_single_file(ed, CONFIG)
    sv = ds["Sv"].values
    if sv.ndim == 3:
        sv = sv[0]
    window.echogram.set_data(sv)
    app.processEvents()

    def take_screenshot(name):
        pixmap = window.grab()
        path = f"D:\\Administrator\\Desktop\\echopype\\screenshots\\{name}.png"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        pixmap.save(path)
        print(f"截图: {path}")

    colormaps = ["jet", "viridis", "inferno", "gray"]
    for cmap in colormaps:
        print(f"切换到: {cmap}")
        window.echo_toolbar.cmap_combo.setCurrentText(cmap)
        app.processEvents()
        take_screenshot(f"echogram_{cmap}")

    print("\n截图已保存到 screenshots/ 目录，请检查颜色是否变化")


if __name__ == "__main__":
    main()
