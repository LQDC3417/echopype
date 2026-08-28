# High-Priority Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复代码审查中会造成结果错误、流程阻断或数据覆盖风险的高优先级问题。

**Architecture:** 保持现有模块边界。核心计算继续使用 NumPy/xarray，GUI 只修正状态来源、任务生命周期和导出路由；文件写入改为显式覆盖控制或临时文件替换。每项修复配套最小回归测试。

**Tech Stack:** Python 3.13, NumPy, xarray, pandas, PySide6, h5py, pytest, ruff。

**实施状态（2026-08-28）：** 本计划中的核心回归测试、计算修复、GUI 状态与导出修复、文件安全与依赖修复均已完成；完整回归结果为 `254 passed, 1 skipped`，Ruff 和 `git diff --check` 通过。

---

### Task 1: 核心回归测试

**Files:**
- Create: `tests/test_high_priority_fixes.py`
- Test: `src/core/integration.py`, `src/core/noise.py`, `src/core/merge.py`, `src/gui/workers.py`

- [x] 添加阈值积分、多通道噪声、短数据窗口、降序深度插值、手动 mask 保留原始 Sv 的最小测试。
- [x] 运行 `python -m pytest tests/test_high_priority_fixes.py -q`，确认现状失败且失败原因对应已知缺陷。

### Task 2: 修复核心计算

**Files:**
- Modify: `src/core/integration.py`
- Modify: `src/core/noise.py`
- Modify: `src/core/merge.py`
- Modify: `src/core/utils.py`

- [x] 让 ABC/density 只对阈值、NaN 和底部 mask 后的有效样本积分。
- [x] 让噪声窗口适配实际数据尺寸，并逐通道处理多通道数据。
- [x] 让合并插值处理升序/降序网格，并保留可安全对齐的核心变量。
- [x] 让手动 mask 不覆盖原始 `Sv`。

### Task 3: 修复 GUI 状态和导出

**Files:**
- Modify: `src/gui/handlers/file_handlers.py`
- Modify: `src/gui/handlers/processing_handlers.py`
- Modify: `src/gui/handlers/interaction_handlers.py`
- Modify: `src/gui/main_window.py`
- Modify: `src/gui/stats_dialog.py`
- Modify: `src/gui/i18n.py`

- [x] 导入/切换数据集时统一清理旧分析状态，并让分析区域开关真正控制数据源。
- [x] 修正批量导入后的运行状态和导出选项路由。
- [x] 修正真实 SED 导出分支和 overlay 开关连接。
- [x] 补齐缺失翻译键。

### Task 4: 修复文件安全、依赖和批量错误

**Files:**
- Modify: `src/core/export.py`
- Modify: `src/core/ep_project.py`
- Modify: `src/core/acoustic.py`
- Modify: `pyproject.toml`
- Modify: `requirements.txt`

- [x] 为 Zarr 和 EP 项目保存增加安全覆盖策略。
- [x] 遇到批量 raw 文件失败时显式报告，不静默继续。
- [x] 声明 `h5py` 和 `openpyxl` 运行依赖。

### Task 5: 验证

**Files:**
- Test: `tests/test_high_priority_fixes.py`
- Test: `tests/`

- [x] 运行回归测试。
- [x] 运行 `python -m pytest -q`。
- [x] 运行 `python -m ruff check src tests`，记录剩余既有问题。
- [x] 检查 `git diff --check` 和工作区变更范围。
