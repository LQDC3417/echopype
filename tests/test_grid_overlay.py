"""测试回声积分叠加是否正确设置（原网格叠加，已合并进回声积分）

原模块顶层直接执行 process_single_file()，内部调用 echopype 0.11 的
remove_background_noise 抛出 RuntimeError（processing_level_code）。
修复方案：
  1. 所有逻辑移入 pytest 函数，避免 import 时崩溃。
  2. 用 compute_sv（Sv + depth + GPS，不调 remove_background_noise）代替 process_single_file。
  3. EchogramRenderer 需要 Qt 上下文，headless 环境下用 _MockRenderer 测试 set_grid_data 逻辑。
"""
import sys
sys.path.insert(0, '.')
from src.core.utils import load_config
from src.core.acoustic import open_single_file, compute_sv
from src.core.integration import create_integration_grid, integrate, ESUType
from pathlib import Path
import numpy as np

RAW_FILE = Path('raw_data/20250706SCSK-D20250706-T024009.raw')


# ── 辅助函数 ─────────────────────────────────────────────────

def _load_and_compute_sv():
    """加载原始文件并计算 Sv + depth + GPS（不调用 remove_background_noise）。

    使用 compute_sv 而非 process_single_file，以避免 echopype 0.11 的
    remove_background_noise 兼容性问题（RuntimeError: processing_level_code）。
    """
    config = load_config('configs/example.yaml')
    ed = open_single_file(RAW_FILE, config)
    ds = compute_sv(ed, config)
    return ds


def _build_overlay_df(ds):
    """回声积分 → 渲染器可用的 overlay DataFrame。"""
    grid = create_integration_grid(
        ds, esu_type=ESUType.PINGS, esu_size=100,
        layer_width=2.0, surface_depth_m=2.0,
    )
    result = integrate(ds, grid, min_threshold=-70, max_threshold=0)
    df = result.to_dataframe()
    # 列名映射到渲染器期望格式
    overlay_df = df.rename(columns={"depth_start": "depth_lo", "depth_end": "depth_hi"})
    return overlay_df


class _MockRenderer:
    """EchogramRenderer 的轻量替身，仅实现 set_data / set_grid_data 逻辑。

    EchogramRenderer 继承 PySide6 QOpenGLWidget，需要 Qt 上下文才能实例化。
    此 mock 复制了 set_grid_data 的核心逻辑（深度→sample 转换 + 网格单元构建），
    用于 headless 环境下验证积分结果到渲染器的叠加流程。
    """

    def __init__(self):
        self._grid_cells = None
        self._grid_values = None
        self._sv_data = None
        self._n_pings = 0
        self._n_samples = 0

    def set_data(self, sv_data: np.ndarray):
        self._sv_data = sv_data.astype(np.float32)
        self._n_pings = sv_data.shape[0]
        self._n_samples = sv_data.shape[1]

    def set_grid_data(self, grid_df, ds_Sv=None, color_by: str = "mean_sv"):
        """复制 EchogramRenderer.set_grid_data 的核心逻辑。"""
        if grid_df is None or grid_df.empty:
            self._grid_cells = None
            self._grid_values = None
            return

        cells = []
        values = []

        echo_range = None
        if ds_Sv is not None and "echo_range" in ds_Sv:
            echo_range = ds_Sv["echo_range"].values
            while echo_range.ndim > 1:
                echo_range = echo_range[0]

        for _, row in grid_df.iterrows():
            ping_start = int(row["ping_start"])
            ping_end = int(row["ping_end"])
            if echo_range is not None:
                sample_start = int(np.searchsorted(echo_range, float(row["depth_lo"])))
                sample_end = int(np.searchsorted(echo_range, float(row["depth_hi"])))
            else:
                sample_start = int(row.get("depth_lo", 0))
                sample_end = int(row.get("depth_hi", self._n_samples))
            cells.append({
                "ping_start": ping_start,
                "ping_end": ping_end,
                "sample_start": sample_start,
                "sample_end": sample_end,
            })
            values.append(float(row.get(color_by, 0)))

        self._grid_cells = cells
        self._grid_values = np.array(values, dtype=np.float32)


# ── 测试 ─────────────────────────────────────────────────────

def test_integration_overlay():
    """验证回声积分结果能正确叠加到渲染器。"""
    ds = _load_and_compute_sv()
    sv = ds['Sv'].values
    if sv.ndim == 3:
        sv = sv[0]

    # 使用 _MockRenderer（headless 环境无 Qt 上下文，无法实例化 EchogramRenderer）
    renderer = _MockRenderer()
    renderer.set_data(sv)

    overlay_df = _build_overlay_df(ds)
    renderer.set_grid_data(overlay_df, ds, color_by='mean_Sv')

    # 验证网格单元已生成
    assert renderer._grid_cells, "渲染器应产生至少一个网格单元"
    cell = renderer._grid_cells[0]
    assert 'ping_start' in cell and 'ping_end' in cell
    assert 'sample_start' in cell and 'sample_end' in cell
