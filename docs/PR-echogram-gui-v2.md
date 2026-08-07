# PR: Echogram GUI v2.0 — 鱼类声学资源评估系统

## 概述

基于 echopype 构建的专业鱼类声学数据处理 GUI，提供 Echoview 风格的交互式回波图分析、鱼群检测、密度估算和网格化统计功能。

## 功能特性

### 核心处理流程

| 功能 | 模块 | 说明 |
|------|------|------|
| 文件加载 | `acoustic.py` | 支持 raw/ek60/ek80/AZFP 格式 |
| Sv 校准 | `acoustic.py` | 使用 echopype compute_Sv，保留原始 Sv 不覆盖 |
| 噪声去除 | `acoustic.py` | 基于 ping_num/range_sample_num/SNR 阈值 |
| 底部检测 | `acoustic.py` | 可调阈值 (-70~-20 dB)，支持 echoview/basic 方法 |
| 鱼群检测 | `school.py` | 基于 detect_shoal，输出鱼群 mask + DataFrame |
| 密度估算 | `density.py` | ABC/NASC → 鱼类密度，支持深度分层 |
| 网格分析 | `grid.py` | 垂直分层 × 水平分段的网格化统计 |
| 数据导出 | `export.py` | 支持 netCDF/Zarr/CSV/Excel 格式 |

### 新增后端模块

| 模块 | 文件 | 职责 |
|------|------|------|
| **区域管理** | `src/core/region.py` | 表线/底线管理、深度↔sample 转换、分析区域裁剪 |
| **网格分析** | `src/core/grid.py` | 垂直分层(1m/2m/5m) × 水平分段(Ping/GPS距离) |
| **质量检查** | `src/core/quality.py` | Sv 数据验证、底线有效性检查 |
| **多频分析** | `src/core/multifreq.py` | 频率选择、断面分割、频率对比 |
| **数据导出** | `src/core/export.py` | netCDF/Zarr/CSV/Excel 多格式导出 |
| **工具函数** | `src/core/utils.py` | squeeze_sv、sv_to_linear、get_sv_array 等 |

### GUI 功能

| 组件 | 说明 |
|------|------|
| **主窗口** | Echoview 专业停靠布局：文件树/变量列表/属性面板/区域表格可折叠 Dock |
| **工具栏** | StandardToolBar + EchogramToolBar（2 行紧凑布局） |
| **属性面板** | PropertyPanel：处理参数 + 网格分析 + 统计按钮 |
| **OpenGL 渲染器** | 高性能回波图渲染，支持缩放/平移/叠加层/视口裁剪 |
| **统计对话框** | 双标签页：鱼群/密度 + 网格统计 |
| **导出对话框** | 可选格式(netCDF/CSV/Excel/Zarr) + 内容(Sv/鱼群/密度/网格) |
| **蓝白色主题** | 专业清爽的 UI 配色方案 |

## 技术架构

```
┌─────────────────────────────────────────────────────────┐
│                      GUI Layer                          │
│  MainWindow ← Toolbars ← Workers ← Dialogs             │
│  (PySide6)    (信号槽)   (QThread)  (Stats/Export)      │
├─────────────────────────────────────────────────────────┤
│                    Processing Layer                     │
│  acoustic.py → school.py → density.py → grid.py        │
│       ↓            ↓           ↓           ↓           │
│  region.py     quality.py  multifreq.py  export.py      │
├─────────────────────────────────────────────────────────┤
│                     Data Layer                          │
│  echopype (compute_Sv, detect_seafloor, detect_shoal)   │
│  xarray Dataset (Sv, Sv_corrected, echo_range)          │
└─────────────────────────────────────────────────────────┘
```

## 关键设计决策

### 1. 分析区域在 GUI 层统一裁剪

**决策：** 将分析区域裁剪（表线→底线）从后端模块移至 GUI 层，后端函数接收预裁剪的 ds_Sv。

**原因：**
- 后端模块保持纯净的计算逻辑，不依赖区域参数
- 裁剪逻辑统一在 `_apply_analysis_region_to_ds()` 中，避免多处重复
- `crop_sv_by_region()` 同时裁剪 `Sv` 和 `Sv_corrected`，确保下游无论读哪个变量都受约束

### 2. Sv 数据永不覆盖

**决策：** 噪声去除结果存储在 `Sv_corrected` 中，原始 `Sv` 始终保留。

**原因：** 用户需要对比原始/去噪数据，覆盖原始数据会丢失信息。

### 3. 状态持久化

**决策：** `_save_file_state()` 缓存底线、噪声 mask、鱼群 mask、表线深度，`_switch_file()` 恢复完整状态。

**原因：** 多文件分析时切换页面需要保留所有处理结果。

### 4. 工具函数统一入口

**决策：** `squeeze_sv()`、`sv_to_linear()`、`get_sv_array()` 等放在 `utils.py`，所有模块统一调用。

**原因：** 消除跨文件的重复代码（Sv 降维 6 处、Sv 转线性 4 处）。

### 5. 底线自由手绘编辑

**决策：** 实现自由手绘底线编辑，支持分段替换和撤销。

**功能：**
- **自由手绘**：按住左键拖动连续绘制底线，密集采样形成平滑曲线
- **分段替换**：只替换新绘制覆盖的 Ping 范围，保留其他部分
- **实时预览**：绘制过程中橙色线条实时显示
- **撤销支持**：Ctrl+Z 撤销上一步编辑，最多 50 步历史
- **右键菜单**：完成绘制、清除绘制点、撤销操作
- **坐标+Sv显示**：状态栏实时显示鼠标位置和回波强度

**原因：**
- 自由手绘更直观，适合快速绘制复杂底线
- 分段替换避免意外覆盖已有底线
- 撤销功能提供容错能力

## 代码质量改进

### Bug 修复

| # | 严重度 | 问题 | 修复 |
|---|--------|------|------|
| 1 | 🔴 | `centroid_depth` 用 ping 索引而非深度索引 | 改用 `cols.mean()` |
| 2 | 🔴 | 坐标反转时未同步反转 Sv 数据 | 反转时同步反转对应维度 |
| 3 | 🔴 | `crop_sv_by_region` 只裁剪一个变量 | 循环裁剪 `Sv` 和 `Sv_corrected` |
| 4 | 🔴 | `_dragging_node` 未初始化导致运行时崩溃 | 添加初始化 |
| 5 | 🟡 | `_switch_file` 未重建分析数据集 | 添加 `_apply_analysis_region_to_ds()` 调用 |
| 6 | 🟡 | `build_analysis_mask` Python 循环性能差 | 向量化 NumPy 广播 |
| 7 | 🟡 | `bottom_depth_to_sample_indices` Python 循环 | 向量化 `np.searchsorted` |
| 8 | 🟡 | dr 计算 density.py vs grid.py 不一致 | 统一使用 `region.get_echo_range_1d` |
| 9 | 🟡 | 深度分层默认从 0 开始浪费首层 | 改为从 `d_min` 开始 |
| 10 | 🔵 | 表线/底线边界语义不对称 | 统一为边界点保留 |

### 性能优化

| 优化 | 位置 | 效果 |
|------|------|------|
| `build_analysis_mask` 向量化 | `region.py` | O(n) Python 循环 → NumPy 广播 |
| `bottom_depth_to_sample_indices` 向量化 | `region.py` | 逐 ping searchsorted → 批量 searchsorted |
| `_draw_school_boundaries` 向量化 | `opengl_renderer.py` | O(h×w) 双重循环 → NumPy 边界检测 |
| `sv_to_linear` 统一入口 | `utils.py` | 消除 4 处重复的 10^(Sv/10) 计算 |

### 代码去重

| 公共函数 | 消除重复 |
|----------|----------|
| `squeeze_sv()` | main_window.py 6处, workers.py 1处 |
| `sv_to_linear()` | density.py 3处, grid.py 1处 |
| `get_echo_range_1d()` | density.py 1处, grid.py 1处 |
| `_apply_sv_to_display()` | main_window.py 2处 |

## 文件清单

### 新增文件

| 文件 | 说明 |
|------|------|
| `src/core/region.py` | 分析区域管理模块 |
| `src/core/grid.py` | 网格化分析模块 |
| `src/core/quality.py` | 数据质量检查模块 |
| `src/core/multifreq.py` | 多频分析模块 |
| `src/core/export.py` | 数据导出模块 |
| `src/gui/stats_dialog.py` | 统计对话框 |
| `src/gui/export_dialog.py` | 导出对话框 |

### 修改文件

| 文件 | 修改内容 |
|------|----------|
| `src/gui/main_window.py` | 重构工具栏、分析区域、状态持久化、导出对话框 |
| `src/gui/toolbars.py` | 新增 ProcessingToolBar、蓝白色主题适配 |
| `src/gui/theme.py` | 全新蓝白色主题 |
| `src/gui/workers.py` | 新增 GridWorker、修复导入 |
| `src/gui/status_bar.py` | 蓝白色主题适配 |
| `src/gui/property_panel.py` | 蓝白色主题适配 |
| `src/core/density.py` | 使用 sv_to_linear、统一 dr 计算、常量提取 |
| `src/core/school.py` | 修复 centroid_depth、坐标反转、深度分辨率 |
| `src/core/utils.py` | 新增 squeeze_sv、sv_to_linear |
| `src/viz/opengl_renderer.py` | 修复 _dragging_node、白底背景、清理导入 |
| `configs/example.yaml` | 更新默认参数 |

## 测试验证

```bash
# 启动 GUI
python -m src.app

# 测试流程
1. 导入 raw 文件 → 全部运行
2. 调整底线阈值 → 检测底部
3. 设置表线深度 → 启用分析区域
4. 检测鱼群 → 查看统计
5. 设置网格参数 → 网格分析
6. 导出结果 → 选择格式和内容
```

## 后续计划

- [ ] 多频分析 UI（multifreq.py 已实现，GUI 尚未接入）
- [ ] 质量检查结果展示（quality.py 已实现，GUI 尚未接入）
- [x] 底线自由手绘编辑（分段替换 + Ctrl+Z 撤销）
- [x] 批量处理 UI（Ctrl+B，ThreadPoolExecutor 并行）
- [ ] 网格分析结果可视化（颜色编码）
- [ ] 用户文档和使用指南
