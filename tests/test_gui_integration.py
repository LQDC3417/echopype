"""用真实 .raw 文件测试 GUI 集成流程

测试链：config → open_raw → compute_sv → noise_removal → bottom_detection
         → school_detection → opengl_renderer

依赖：需要真实 .raw 文件，无文件时自动跳过。
"""

import sys
from pathlib import Path

import numpy as np
import pytest

RAW_FILE = Path(r"D:\Administrator\Desktop\echopype\raw_data\20250706SCSK-D20250706-T024009.raw")

# ──────────────────────────────────────────────
# 模块级条件跳过
# ──────────────────────────────────────────────


@pytest.fixture(scope="module")
def _raw_available():
    """检查 raw 文件是否存在，不存在则跳过整个模块"""
    if not RAW_FILE.exists():
        pytest.skip(f"Raw 文件不存在: {RAW_FILE}", allow_module_level=True)
    return True


# ──────────────────────────────────────────────
# Fixture 依赖链（module scope — 整个模块只计算一次）
# ──────────────────────────────────────────────


@pytest.fixture(scope="module")
def int_config(_raw_available):
    """集成测试配置"""
    return {
        "processing": {
            "sonar_model": "EK80",
            "noise_removal": {
                "ping_num": 5,
                "range_sample_num": 10,
                "SNR_threshold": "3.0dB",
            },
            "bottom_detection": {
                "method": "basic",
                "threshold": -50.0,
                "offset_m": 0.5,
                "bin_skip_from_surface": 200,
            },
        },
        "school_detection": {
            "method": "echoview",
            "thr": -55.0,
            "mincan": [3, 10],
            "maxlink": [3, 15],
            "minsho": [3, 15],
        },
    }


@pytest.fixture(scope="module")
def int_echodata(int_config):
    """加载 raw 文件 → EchoData 对象"""
    from src.core.acoustic import open_single_file
    return open_single_file(RAW_FILE, int_config)


@pytest.fixture(scope="module")
def int_ds_sv(int_echodata, int_config):
    """计算 Sv → xr.Dataset"""
    from src.core.acoustic import compute_sv
    return compute_sv(int_echodata, int_config)


@pytest.fixture(scope="module")
def int_sv(int_ds_sv):
    """提取 Sv numpy 数组 (n_pings, n_samples)"""
    sv = int_ds_sv["Sv"].values
    if sv.ndim == 3:
        sv = sv[0]
    return sv


@pytest.fixture(scope="module")
def int_ds_clean(int_ds_sv, int_config):
    """噪声去除 → ds_Sv with Sv_corrected"""
    from echopype.clean import remove_background_noise
    noise_cfg = int_config["processing"]["noise_removal"]
    # echopype 0.11.1: remove_background_noise 要求输入带 input_processing_level
    if "input_processing_level" not in int_ds_sv.attrs:
        int_ds_sv.attrs["input_processing_level"] = "L2A"
    ds = remove_background_noise(
        int_ds_sv,
        ping_num=noise_cfg["ping_num"],
        range_sample_num=noise_cfg["range_sample_num"],
        SNR_threshold=noise_cfg["SNR_threshold"],
    )
    # 统一：下游优先用 Sv_corrected
    if "Sv_corrected" in ds:
        ds["Sv"] = ds["Sv_corrected"]
    return ds


@pytest.fixture(scope="module")
def int_bottom(int_sv):
    """底部检测 — 每 ping 找第一个超过阈值的采样点"""
    threshold = -50.0
    bin_skip = 200
    n_pings, n_samples = int_sv.shape
    bottom = np.full(n_pings, np.nan, dtype=np.float32)
    for i in range(n_pings):
        col = int_sv[i, :]
        search_start = min(bin_skip, n_samples)
        segment = col[search_start:]
        if len(segment) == 0 or np.all(np.isnan(segment)):
            continue
        above = np.where(segment >= threshold)[0]
        if len(above) > 0:
            bottom[i] = search_start + above[0]
    return bottom


@pytest.fixture(scope="module")
def int_schools_mask(int_ds_sv, int_config):
    """鱼群检测 → boolean mask DataArray"""
    from src.core.school import detect_schools
    return detect_schools(int_ds_sv, int_config)


@pytest.fixture(scope="module")
def int_schools_df(int_schools_mask, int_ds_sv):
    """鱼群 mask → DataFrame"""
    from src.core.school import schools_to_dataframe
    return schools_to_dataframe(int_schools_mask, int_ds_sv)


# ──────────────────────────────────────────────
# 测试函数 — 每个验证一个步骤
# ──────────────────────────────────────────────


def test_config(int_config):
    """验证配置完整性"""
    assert "processing" in int_config
    assert "school_detection" in int_config
    print(f"[OK] 配置加载 — {len(int_config)} 个顶层 section")


def test_open_raw(int_echodata):
    """验证 raw 文件加载"""
    from echopype.echodata import EchoData
    assert isinstance(int_echodata, EchoData), f"期望 EchoData，实际 {type(int_echodata)}"
    print(f"[OK] 文件加载: {type(int_echodata).__name__}")


def test_compute_sv(int_ds_sv, int_sv):
    """验证 Sv 计算"""
    import xarray as xr
    assert isinstance(int_ds_sv, xr.Dataset)
    assert int_sv.ndim == 2, f"期望 2D，实际 {int_sv.ndim}D"
    assert int_sv.size > 0, "Sv 数组为空"
    sv_range = f"[{np.nanmin(int_sv):.1f}, {np.nanmax(int_sv):.1f}] dB"
    print(f"[OK] Sv 计算: shape={int_sv.shape}, range={sv_range}")


def test_noise_removal(int_ds_clean, int_sv):
    """验证噪声去除"""
    sv_c = int_ds_clean["Sv"].values
    if sv_c.ndim == 3:
        sv_c = sv_c[0]
    assert sv_c.shape == int_sv.shape, f"形状变化: {int_sv.shape} → {sv_c.shape}"
    print(f"[OK] 噪声去除: shape={sv_c.shape}")


def test_bottom_detection(int_bottom, int_sv):
    """验证底部检测"""
    n_pings = int_sv.shape[0]
    valid = int(np.sum(~np.isnan(int_bottom)))
    assert valid > 0, f"底部检测失败：0/{n_pings} ping 检测到底线"
    print(f"[OK] 底部检测: {valid}/{n_pings} ping 有底线")


def test_school_detection(int_schools_mask, int_schools_df):
    """验证鱼群检测"""
    import xarray as xr
    assert isinstance(int_schools_mask, xr.DataArray)
    n_pixels = int(int_schools_mask.sum().values)
    n_schools = len(int_schools_df)
    print(f"[OK] 鱼群检测: {n_pixels} 像素, {n_schools} 个鱼群")


def test_opengl_renderer(int_sv):
    """验证 OpenGL 渲染器创建 + 数据绑定"""
    from PySide6.QtWidgets import QApplication
    from src.viz.opengl_renderer import EchogramRenderer

    app = QApplication.instance() or QApplication(sys.argv)
    renderer = EchogramRenderer()
    renderer.resize(800, 600)
    renderer.show()
    renderer.set_data(int_sv)
    app.processEvents()

    assert renderer._sv_data is not None, "纹理数据未设置"
    assert renderer._sv_data.shape == int_sv.shape, "数据形状不匹配"
    print(f"[OK] OpenGL 渲染器: 数据已设置, shape={int_sv.shape}")
    renderer.close()


# ──────────────────────────────────────────────
# 手动运行入口（`python tests/test_gui_integration.py` 仍可用）
# ──────────────────────────────────────────────

def main():
    """顺序管道 — 手动调试时直接运行"""
    print("=" * 60)
    print("Echogram GUI 集成测试 (顺序管道)")
    print("=" * 60)

    config = int_config(None)  # _raw_available 只检查文件; None 绕过 pytest fixture
    echodata = int_echodata(config)
    ds_sv = int_ds_sv(echodata, config)
    sv = int_sv(ds_sv)
    int_ds_clean(ds_sv, config)
    bottom = int_bottom(sv)
    mask = int_schools_mask(ds_sv, config)
    schools_df = int_schools_df(mask, ds_sv)

    print(f"[OK] 底部检测: {int(np.sum(~np.isnan(bottom)))}/{sv.shape[0]} ping 有底线")
    print(f"[OK] 鱼群检测: {int(mask.sum().values)} 像素, {len(schools_df)} 个鱼群")

    print("=" * 60)
    print("所有管道步骤通过!")
    print("=" * 60)


if __name__ == "__main__":
    main()
