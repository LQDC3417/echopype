# High-Priority Regression Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复会造成处理崩溃、声学数据丢失、导出缺失或 GUI 分析状态失真的五项高优先级缺陷。

**Architecture:** 保持现有 NumPy/xarray 核心算法和 PySide6 Mixin 边界。每项修复先添加最小真实回归测试；核心层保证数组维度与通道完整性，GUI 层将交互状态通过既有噪声处理和导出接口同步。

**Tech Stack:** Python 3.13, NumPy, xarray, pandas, PySide6, pytest.

---

### Task 1: 噪声窗口覆盖尾部 ping

**Files:**
- Modify: `tests/test_high_priority_fixes.py`
- Modify: `src/core/noise.py:82-112`

- [ ] **Step 1: Write the failing test**

```python
def test_noise_reduction_covers_partial_ping_window():
    sv = np.full((25, 8), -80.0)
    noise, per_ping = estimate_noise_de_robertis(sv, np.arange(8.0), ping_num=10, range_sample_num=4)
    assert noise.shape == sv.shape
    assert per_ping.shape == (25,)
```

- [ ] **Step 2: Verify it fails**

Run: `python -m pytest tests/test_high_priority_fixes.py::test_noise_reduction_covers_partial_ping_window -q`

Expected: 返回 `(20, 8)` 与 `(20,)`，而不是输入 ping 长度。

- [ ] **Step 3: Implement the minimum fix**

按 `range(0, n_pings, ping_num)` 分块计算 ping 均值；最后一个块可以短于窗口。对每个块重复其估计值 `len(block)` 次，因此 `noise_per_ping` 恒为 `n_pings` 长度。

- [ ] **Step 4: Verify the focused suite**

Run: `python -m pytest tests/test_high_priority_fixes.py tests/test_noise.py -q`

### Task 2: Preserve all channels while merging files

**Files:**
- Modify: `tests/test_merge.py`
- Modify: `src/core/merge.py:86-269`

- [ ] **Step 1: Write the failing test**

```python
def test_merge_aligned_preserves_each_channel():
    first = _make_two_channel_dataset(["2026-01-01T00:00:00"], [[1.0], [10.0]])
    second = _make_two_channel_dataset(["2026-01-01T00:01:00"], [[2.0], [20.0]])
    merged = merge_aligned([first, second])
    assert merged.channel.values.tolist() == [38.0, 120.0]
    assert merged.Sv.values[:, :, 0].tolist() == [[1.0, 2.0], [10.0, 20.0]]
```

- [ ] **Step 2: Verify it fails**

Run: `python -m pytest tests/test_merge.py::TestMergeAligned::test_merge_aligned_preserves_each_channel -q`

Expected: 当前实现只返回 channel 38.0。

- [ ] **Step 3: Implement the minimum fix**

把重采样函数改为对每个 channel 输出 `(channel, ping, range)`；校验输入文件有一致的 channel 坐标，逐文件在 ping 轴拼接、排序和去重。`Sv_corrected` 同样逐通道重采样。

- [ ] **Step 4: Verify the merge suite**

Run: `python -m pytest tests/test_merge.py -q`

### Task 3: Repair grid export and noise-mask history

**Files:**
- Modify: `tests/test_high_priority_fixes.py`
- Modify: `src/gui/handlers/interaction_handlers.py:59-221`

- [ ] **Step 1: Write the failing tests**

```python
def test_export_grid_uses_integration_dataframe(monkeypatch, tmp_path):
    host = _export_host_with_integration_dataframe(tmp_path)
    InteractionMixin._export(host)
    assert host.exported_path == tmp_path / "grid_stats.csv"

def test_undo_noise_mask_reapplies_noise_processing():
    host = _noise_host(mask=np.array([[True]]), undo=[("noise_mask", None)])
    InteractionMixin._undo(host)
    assert host._noise_mask_manual is None
    assert host.noise_apply_calls == 1
```

- [ ] **Step 2: Verify they fail**

Run: `python -m pytest tests/test_high_priority_fixes.py -k 'export_grid or undo_noise' -q`

Expected: 网格导出无调用；undo 不会重新应用噪声处理。

- [ ] **Step 3: Implement the minimum fix**

网格导出读取 `_integration_df` 并把其作为 Excel 的 density 参数。新增内部恢复方法：设置 mask、更新 renderer、保存状态并调用 `_apply_noise_params()`；新增噪声区域时把修改前快照压入 undo 栈，undo/redo/clear 共用该恢复路径。

- [ ] **Step 4: Verify the focused GUI tests**

Run: `python -m pytest tests/test_high_priority_fixes.py tests/test_gui_workflow.py -q`

### Task 4: Preserve the real SED distance origin

**Files:**
- Modify: `tests/test_single_target.py`
- Modify: `src/core/sed.py:225-234`

- [ ] **Step 1: Write the failing test**

```python
def test_real_sed_preserves_nonzero_echo_range_origin(monkeypatch):
    result = _run_fake_real_sed(monkeypatch, echo_range=[10.0, 11.0, 12.0])
    assert result.loc[0, "range_m"] == pytest.approx(11.0)
```

- [ ] **Step 2: Verify it fails**

Run: `python -m pytest tests/test_single_target.py::test_real_sed_preserves_nonzero_echo_range_origin -q`

Expected: 当前逻辑给出相对值 `1.0`。

- [ ] **Step 3: Implement the minimum fix**

以第一个有效 echo-range 和其原始 sample index 为锚点重建坐标：`er[first_valid] + (np.arange(len(er)) - first_valid) * dr`，不能把有效距离重置为零。

- [ ] **Step 4: Verify the SED suites**

Run: `python -m pytest tests/test_single_target.py tests/test_multi_file_sed.py -q`

### Task 5: Verify and commit

**Files:**
- Verify: `src/`, `tests/`

- [ ] **Step 1: Run full verification**

Run: `python -m ruff check src tests`; `python -m compileall -q src tests`; `D:\Program Files\Anaconda\python.exe -m pytest -q --disable-warnings --maxfail=1`; `D:\Program Files\Anaconda\python.exe -m pytest -m real_data --run-real-data -q --disable-warnings --maxfail=1`; `git diff --check`.

- [ ] **Step 2: Review scope and create the local commit**

Stage exactly `src/core/noise.py`, `src/core/merge.py`, `src/core/sed.py`, `src/gui/handlers/interaction_handlers.py`, corresponding regression tests, and this plan; commit with `fix: close high priority processing regressions`.
