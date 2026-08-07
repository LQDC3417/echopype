# PR: echopype 声学数据处理系统 — 产品需求文档

**版本**: 1.0  
**创建**: 2026-08-07  
**状态**: 初稿（待细化）

---

## 1. 系统概述

### 1.1 产品定位

基于 echopype 的专业鱼类声学数据处理系统，提供：
- **后端处理流水线**：文件加载 → Sv 校准 → 噪声去除 → 底部检测 → 鱼群检测 → 密度估算
- **GUI 可视化分析**：Echoview 风格交互式回波图、参数调整、结果导出

### 1.2 用户角色

| 角色 | 使用场景 | 关键需求 |
|------|----------|----------|
| 科研人员 | 海洋/淡水鱼类资源评估 | 完整处理流程、参数可调、结果可导出 |
| 数据分析师 | 批量数据处理、统计分析 | 高效批处理、网格化统计、多格式导出 |
| 研究生 | 学习声学数据处理 | 界面友好、文档完整、可复现 |

### 1.3 系统边界

```
┌─────────────────────────────────────────────────────────────┐
│                      系统边界                               │
├─────────────────┬───────────────────┬───────────────────────┤
│   输入层        │    处理层         │      输出层           │
│                 │                   │                       │
│ • .raw 文件     │ • echopype 核心   │ • netCDF/Zarr         │
│ • 配置文件      │ • 后处理模块      │ • CSV/Excel           │
│                 │ • GUI 交互        │ • PNG/SVG 图表        │
└─────────────────┴───────────────────┴───────────────────────┘
                         ↓
              外部依赖：echopype, xarray, PySide6, PyOpenGL
```

---

## 2. 功能需求

### 2.1 核心处理流水线

#### FR-01: 文件加载
- **优先级**: P0（必须）
- **输入**: EK80/EK60/AZFP 格式 .raw 文件
- **处理**: 调用 `echopype.open_raw()` 加载
- **输出**: `xr.Dataset` (EchoData)
- **验收标准**:
  - [ ] 支持单文件加载 < 30 秒（100MB 文件）
  - [ ] 支持多文件批量加载（队列模式）
  - [ ] 文件格式自动识别

#### FR-02: Sv 校准
- **优先级**: P0
- **输入**: EchoData
- **处理**: 调用 `echopype.compute_Sv()`
- **输出**: `xr.Dataset` (Sv 变量)
- **验收标准**:
  - [ ] 保留原始 `Sv`，新变量存入 `Sv_corrected`
  - [ ] 支持脉冲压缩/宽带模式

#### FR-03: 噪声去除
- **优先级**: P0
- **输入**: ds_Sv, 参数 (ping_num, range_sample_num, SNR)
- **处理**: 基于噪声阈值裁剪
- **输出**: `Sv_corrected` 更新
- **验收标准**:
  - [ ] 参数可调（GUI 实时预览）
  - [ ] 原始 Sv 保留不变

#### FR-04: 底部检测
- **优先级**: P0
- **输入**: ds_Sv, 参数 (method, threshold, offset_m)
- **处理**: 调用 `echopype.detect_seafloor()`
- **输出**: 底线数组 (ping × sample)
- **验收标准**:
  - [ ] 支持 echoview/basic 两种算法
  - [ ] 阈值范围 -70 ~ -20 dB

#### FR-05: 鱼群检测
- **优先级**: P1（重要）
- **输入**: ds_Sv, 参数 (threshold, mincan, maxlink, minsho)
- **处理**: 调用 `echopype.detect_shoal()`
- **输出**: 鱼群 mask + DataFrame (鱼群统计)
- **验收标准**:
  - [ ] 输出鱼群面积、深度、TS 等指标
  - [ ] GUI 叠加显示鱼群边界

#### FR-06: 密度估算
- **优先级**: P1
- **输入**: `ds_Sv: xr.Dataset`, `schools_df: pd.DataFrame`（school_id, ping_start/end, depth_start/end）, `config: dict`（ts_default, avg_weight_kg）
- **处理**: ABC/NASC → 密度转换
- **输出**: `pd.DataFrame` — 列: `transect_id, depth_layer, abc, density_ind_m2, density_ind_ha, total_biomass_kg_ha`
- **子函数**:
  - `estimate_density(schools_df, ds_Sv, config)` — 按鱼群估算密度
  - `estimate_density_by_depth(ds_Sv, config, depth_bins)` — 按深度层全局统计（默认 5 层）
  - `sv_statistics_summary(ds_Sv, transect_ids)` — Sv 统计摘要（均值/中位/分位数/NaN 比例）
- **验收标准**:
  - [ ] 支持深度分层统计（默认 5 层，可自定义 `depth_bins`）
  - [ ] 支持手动设置 TS 值（`config["density"]["ts_default"]`，默认 -30 dB）
  - [ ] `schools_df.empty` 时自动切换全局汇总分支
  - [ ] 输出包含 ind/m²、ind/ha、kg/ha 三种单位

#### FR-07: 网格分析
- **优先级**: P2（可选）
- **输入**: `ds_Sv: xr.Dataset`, 参数（垂直间隔, 水平分段方式, 分段值）
- **处理**: 垂直分层 × 水平分段 → 逐格统计
- **输出**: `pd.DataFrame` — 列: `cell_id, ping_start/end, depth_lo/hi, mean_sv, abc, density_ind_m2/ha, biomass_kg_ha`
- **子函数**:
  - `create_grid(ds_Sv, surface_depth_m, vertical_interval_m, horizontal_interval, method)` — 创建网格单元列表
  - `compute_grid_density(ds_Sv, grid_cells, config, progress_callback)` — 逐格计算密度
  - `compute_grid_stats(ds_Sv, grid_cells, progress_callback)` — 逐格统计（Sv 均值/中位/标准差/变异系数/覆盖率）
- **验收标准**:
  - [ ] 垂直间隔: 1m/2m/5m（可自定义 `depth_bins`）
  - [ ] 水平分段: Ping 数/距离（GPS haversine，无 GPS 时回退到 ping）
  - [ ] `method` 参数: `"ping"` / `"distance"`（默认 `"ping"`）
  - [ ] 逐格输出 ABC、密度、生物量、覆盖率、变异系数
  - [ ] `progress_callback(ping_idx, total)` 支持进度显示
  - [ ] GPS 不足时自动回退到 ping 分段并 logger.warning

#### FR-08: 质量检查
- **优先级**: P2（可选）
- **输入**: `ds_Sv: xr.Dataset`, `bottom: np.ndarray | None`
- **处理**: 数据完整性验证
- **输出**: `dict` — `valid`, `warnings`, `nan_ratio`, 统计信息
- **子函数**:
  - `check_sv_quality(ds_Sv)` — Sv 数据验证（范围、NaN 比例、维度）
  - `check_bottom_line(bottom, n_samples)` — 底线有效性检查
  - `print_quality_report(ds_Sv, bottom)` — 日志输出质量报告
- **验收标准**:
  - [ ] 全 NaN 时提前返回 `valid=False`
  - [ ] 超出合理范围时 `warnings` 列表包含具体提示
  - [ ] `print_quality_report` 输出结构化日志

#### FR-09: 数据导出
- **优先级**: P1
- **输入**: `ds_Sv`, `schools_df`, `density_df`, `output_dir`, `formats`
- **处理**: 多格式导出
- **输出**: `list[Path]` — 所有导出文件路径
- **子函数**:
  - `export_all(ds_Sv, schools_df, density_df, output_dir, formats)` — 批量导出
  - `export_to_netcdf(ds_Sv, output_path)` — 导出 .nc
  - `export_to_zarr(ds_Sv, output_path)` — 导出 .zarr（已有目录先删后写）
  - `export_to_excel(schools_df, density_df, output_path)` — 导出 .xlsx
  - `export_schools_to_csv(schools_df, output_path)` — utf-8-sig 编码
  - `export_density_to_csv(density_df, output_path)` — utf-8-sig 编码
  - `export_sv_to_csv(ds_Sv, output_path)` — 长格式；预估 > 100MB 时 `warnings.warn`
- **验收标准**:
  - [ ] 支持 netCDF/Zarr/CSV/Excel 四种格式
  - [ ] CSV 使用 `utf-8-sig` 编码（Excel 直接打开不乱码）
  - [ ] 空 DataFrame 自动跳过对应导出
  - [ ] 大数据量 CSV 导出前发出警告

### 2.2 GUI 功能

#### FR-10: 主窗口布局
- **优先级**: P0
- **验收标准**:
  - [ ] Dock 布局：左侧文件树、右侧属性面板、底部区域表格
  - [ ] 中央 Echogram 渲染器
  - [ ] 菜单栏：文件、编辑、显示、处理、分析、帮助

#### FR-11: 交互式回波图
- **优先级**: P0
- **验收标准**:
  - [ ] 鼠标缩放/平移
  - [ ] 状态栏显示坐标 + Sv 值
  - [ ] 底线/鱼群/噪声叠加层可切换

#### FR-12: 底线自由手绘
- **优先级**: P1
- **验收标准**:
  - [ ] 左键拖动连续绘制
  - [ ] 分段替换（不破坏其他部分）
  - [ ] Ctrl+Z 撤销（50 步历史）
  - [ ] 右键菜单：完成/清除/撤销

#### FR-13: 批量处理
- **优先级**: P1
- **验收标准**:
  - [ ] 菜单入口：处理 → 批量处理（Ctrl+B）
  - [ ] 多选 .raw 文件
  - [ ] 后台 ThreadPoolExecutor 并行（默认 2 workers）
  - [ ] 进度显示：成功/失败计数

---

## 3. API 接口规范

### 3.1 后端模块接口

#### `src/core/acoustic.py`

```python
def open_single_file(raw_path: Path, config: dict) -> EchoData:
    """
    加载单个 raw 文件
    
    Args:
        raw_path: raw 文件路径
        config: 处理配置字典
        
    Returns:
        EchoData: echopype 对象
        
    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 不支持的文件格式
    """
    pass

def process_single_file(echodata: EchoData, config: dict) -> xr.Dataset:
    """
    处理单个文件：Sv 校准 + 噪声去除 + 底部检测
    
    Args:
        echodata: 加载后的 EchoData
        config: 处理配置
        
    Returns:
        xr.Dataset: 包含 Sv, Sv_corrected, bottom 等变量
    """
    pass
```

#### `src/core/density.py`

```python
def compute_density(
    ds_Sv: xr.Dataset,
    schools_df: pd.DataFrame,
    config: dict,
    surface_depth_m: float = 2.0,
) -> pd.DataFrame:
    """
    计算鱼类密度
    
    Args:
        ds_Sv: Sv 数据集（已裁剪分析区域）
        schools_df: 鱼群统计 DataFrame
        config: 密度配置 {"ts_default": -30.0, "avg_weight_kg": 0.5}
        surface_depth_m: 表线深度（米）
        
    Returns:
        pd.DataFrame: 密度结果，列 = [ping_idx, depth_range, density_fish_per_1000m3]
    """
    pass
```

### 3.2 GUI 信号槽接口

#### `EchogramRenderer` 信号

```python
class EchogramRenderer(QOpenGLWidget):
    # 鼠标交互
    sv_at_cursor = Signal(float, float, float)   # (ping, sample, Sv_dB)
    zoom_changed = Signal(float, float)          # (zoom_x, zoom_y)
    
    # 底线编辑
    bottom_line_edited = Signal(np.ndarray)      # 编辑后的底线数组
    update_bottom_requested = Signal()           # 请求从后端更新底线
```

#### `BatchProcessWorker` 信号

```python
class BatchProcessWorker(QThread):
    file_started = Signal(str)                   # 文件路径
    file_finished = Signal(str, object)          # (路径, ds_Sv)
    file_error = Signal(str, str)                # (路径, 错误信息)
    all_finished = Signal(int, int)              # (成功数, 失败数)
    progress = Signal(str)                       # 进度文本
```

### 3.3 错误处理规范

#### 错误码定义

| 错误码 | 类型 | 说明 | 处理建议 |
|--------|------|------|---------|
| `E001` | FileNotFoundError | 文件不存在 | 检查路径 |
| `E002` | ValueError | 不支持的文件格式 | 检查 sonar_model |
| `E003` | ValueError | 配置参数缺失 | 填写必填字段 |
| `E004` | RuntimeError | echopype 处理失败 | 检查原始数据 |
| `E005` | MemoryError | 内存不足 | 减小数据量或增加内存 |
| `E006` | TimeoutError | 处理超时 | 增加超时时间或简化处理 |

#### 错误处理流程

```python
# 标准错误处理模式
try:
    result = process_single_file(echodata, config)
except FileNotFoundError as e:
    logger.error(f"[E001] 文件不存在: {e}")
    raise
except ValueError as e:
    logger.error(f"[E003] 配置错误: {e}")
    raise
except MemoryError as e:
    logger.error(f"[E005] 内存不足: {e}")
    raise
except Exception as e:
    logger.error(f"[E004] 处理失败: {e}")
    raise
```

#### 输入验证

```python
def validate_config(config: dict) -> list[str]:
    """
    验证配置字典完整性
    
    Returns:
        错误信息列表，空列表表示验证通过
    """
    errors = []
    
    # 必填字段检查
    required_fields = ["processing.sonar_model", "processing.frequencies"]
    for field in required_fields:
        section, key = field.split(".")
        if section not in config or key not in config.get(section, {}):
            errors.append(f"缺少必填字段: {field}")
    
    # 数值范围检查
    proc = config.get("processing", {})
    threshold = proc.get("bottom_detection", {}).get("threshold", -50)
    if not (-70 <= threshold <= -20):
        errors.append(f"底部阈值超出范围: {threshold} (应为 -70 ~ -20)")
    
    return errors
```

### 3.3 配置文件格式

```yaml
# configs/example.yaml
reservoir:
  name: "水库名称"
  region: "省份"

input:
  raw_dir: "./raw_data"
  pattern: "*.raw"

processing:
  sonar_model: "EK80"
  frequencies: [200000]
  waveform_mode: "CW"
  encode_mode: "power"
  
  noise_removal:
    ping_num: 5
    range_sample_num: 10
    SNR_threshold: "3.0dB"
    
  bottom_detection:
    method: "echoview"
    threshold: -50.0
    offset_m: 0.5

school_detection:
  method: "echoview"
  thr: -55.0
  mincan: [3.0, 10.0]
  maxlink: [3.0, 15.0]
  minsho: [3.0, 15.0]

density:
  ts_default: -30.0
  avg_weight_kg: 0.5

output:
  dir: "./outputs"
  formats: ["csv", "xlsx", "png"]
```

---

## 4. 测试覆盖标准

### 4.1 测试金字塔

```
        /\
       /  \  E2E 测试（5%）
      /    \  真实 raw 文件完整流程
     /------\
    /        \  集成测试（25%）
   /          \  模块间交互、信号槽
  /------------\
 /              \  单元测试（70%）
/                \  单个函数、边界条件
```

### 4.2 覆盖率目标（严格标准）

| 模块 | 目标覆盖率 | 最低测试数 | 当前状态 |
|------|-----------|-----------|---------|
| `src/core/*.py` | ≥ 90% | 50+ | 测试文件: test_acoustic, test_density, test_grid, test_region, test_school, test_utils |
| `src/gui/*.py` | ≥ 70% | 20+ | 测试文件: test_gui_integration |
| `src/viz/*.py` | ≥ 60% | 15+ | 测试文件: test_bottom_drawing, test_colormap_display |
| **总计** | ≥ 80% | 100+ | 当前: 67 passed, 1 skipped |

#### 覆盖率缺口分析

| 模块 | 缺口 | 需补充测试 |
|------|------|-----------|
| `core/acoustic.py` | 文件加载异常路径 | test_open_raw_file_not_found, test_open_raw_invalid_format |
| `core/density.py` | 边界条件 | test_density_empty_schools, test_density_negative_ts |
| `core/region.py` | 深度转换 | test_depth_to_sample_out_of_range |
| `gui/workers.py` | 线程生命周期 | test_worker_cancel, test_worker_timeout |
| `viz/opengl_renderer.py` | 交互状态 | test_mouse_zoom, test_mouse_pan |

### 4.3 测试类型

#### 单元测试（`tests/test_*.py`）
- **命名**: `test_<module>_<function>_<scenario>`
- **示例**: `test_density_compute_density_single_school`
- **运行**: `pytest tests/test_density.py -v`

#### 集成测试（`tests/test_gui_integration.py`）
- 测试 MainWindow 信号槽连接
- 测试 EchogramRenderer 交互
- 测试 Worker 线程生命周期

#### E2E 测试（待补充）
- 真实 .raw 文件完整处理流程
- 导出文件完整性验证

### 4.4 当前测试状态

```
tests/
├── test_acoustic.py         # 声学处理
├── test_bottom_drawing.py   # 底线绘制（6 项）
├── test_colormap_display.py # 颜色映射
├── test_config.py           # 配置加载
├── test_density.py          # 密度估算
├── test_grid.py             # 网格分析
├── test_gui_integration.py  # GUI 集成（8 项）
├── test_integration.py      # 流水线集成
├── test_region.py           # 区域管理
├── test_school.py           # 鱼群检测
└── test_utils.py            # 工具函数

结果: 67 passed, 1 skipped
```

---

## 5. 性能指标

### 5.1 关键性能指标（KPI）

| 指标 | 目标值 | 测量方法 |
|------|--------|---------|
| **文件加载时间** | < 30s (100MB) | `time open_single_file()` |
| **Sv 计算时间** | < 10s | `time compute_Sv()` |
| **渲染帧率** | ≥ 30 FPS | OpenGL FPS 计数器 |
| **内存峰值** | < 2GB (500MB 文件) | `psutil.Process().memory_info().rss` |
| **批量处理吞吐量** | ≥ 10 文件/分钟 | ThreadPoolExecutor 并行 |

### 5.2 当前性能基线

| 场景 | 测量值 | 备注 |
|------|--------|------|
| 单文件加载 | ~15s | 50MB EK80 文件 |
| Sv 计算 | ~3s | 单频率 CW 模式 |
| 渲染帧率 | ~45 FPS | 1000×500 数据矩阵 |
| 内存占用 | ~100MB | 空闲状态 |

### 5.3 性能优化清单

| 优化项 | 位置 | 效果 |
|--------|------|------|
| `_sv_to_rgba` 视口裁剪 | `opengl_renderer.py` | 只渲染可见区域，减少 GPU 负载 |
| `optimize_array_dtype` | `utils.py` | float64 → float32，节省 50% 内存 |
| `BatchProcessWorker` | `workers.py` | ThreadPoolExecutor 并行处理 |
| `build_analysis_mask` 向量化 | `region.py` | O(n) 循环 → NumPy 广播 |

---

## 6. 用户体验规范

### 6.1 操作流程

#### 完整分析流程（10 步）
```
1. 启动 GUI                    → python -m src.app
2. 导入 Raw 文件               → Ctrl+I → 选择文件
3. 加载数据                    → 双击文件树节点
4. 计算 Sv                     → 处理菜单 → 计算 Sv（Ctrl+1）
5. 噪声去除                    → 调整参数 → Ctrl+2
6. 底部检测                    → 调整阈值 → Ctrl+3
7. 底线编辑（可选）             → 鼠标模式 → 自由手绘 → Ctrl+Z 撤销
8. 鱼群检测                    → 调整参数 → Ctrl+4
9. 密度估算                    → 设置 TS → Ctrl+5
10. 导出结果                   → Ctrl+E → 选择格式
```

#### 快捷键一览

| 快捷键 | 功能 | 位置 |
|--------|------|------|
| `Ctrl+I` | 导入 Raw 文件 | 文件菜单 |
| `Ctrl+O` | 打开配置文件 | 文件菜单 |
| `Ctrl+S` | 保存配置 | 文件菜单 |
| `Ctrl+E` | 导出结果 | 文件菜单 |
| `Ctrl+B` | 批量处理 | 处理菜单 |
| `F5` | 全部运行 | 处理菜单 |
| `Ctrl+1~5` | 各处理步骤 | 处理菜单 |
| `Ctrl+Z` | 撤销底线编辑 | 编辑菜单 |
| `Ctrl+Y` | 重做 | 编辑菜单 |
| `Ctrl++/-` | 缩放 | Echogram |
| `Ctrl+0` | 适应窗口 | Echogram |
| `Escape` | 取消绘制 | Echogram |

### 6.2 交互细节

#### 拖拽导入
- **触发**: 将 .raw 文件拖入文件树区域
- **反馈**: 光标变为"+"，松开后自动创建文件集并加载
- **限制**: 单次最多 50 个文件

#### 参数预设
- **功能**: 保存/加载常用参数组合
- **入口**: 属性面板 → "保存预设" / "加载预设"
- **存储**: `~/.echogram/presets/` 目录

#### 一键重置
- **功能**: 恢复当前文件的默认参数
- **入口**: 处理菜单 → "重置当前参数"
- **范围**: 噪声参数、底部阈值、鱼群参数、TS 值

#### 帮助文档入口
- **入口**: 帮助菜单 → "用户指南" (F1)
- **内容**: 本地 HTML 或 Markdown 文档
- **索引**: 按功能模块组织，支持搜索

### 6.3 UI 状态反馈

| 场景 | 反馈方式 |
|------|---------|
| 文件加载中 | 状态栏: "加载 [1/3]: xxx.raw" |
| 处理计算中 | 进度条 + 状态文本 |
| 批量处理 | "✓ 完成 [2/5]: xxx.raw" |
| 错误发生 | QMessageBox 弹窗 + 状态栏红色提示 |
| 操作完成 | 状态栏绿色提示（3 秒后消失） |
| 拖拽文件 | 光标"+"，松开后文件树高亮 |
| 参数修改 | 属性面板标题加"*"表示未保存 |

### 6.4 错误处理规范

| 错误类型 | 处理方式 |
|----------|---------|
| 文件不存在 | 弹窗提示 + 状态栏 |
| 格式不支持 | 弹窗提示支持格式列表 |
| 处理失败 | 弹窗显示详细错误 + 日志记录 |
| 内存不足 | 警告提示 + 建议减小数据量 |
| 参数无效 | 属性面板红色边框 + 错误提示 |

---

## 7. 非功能需求

### 7.1 兼容性

| 项 | 要求 |
|----|------|
| Python | ≥ 3.10 |
| echopype | ≥ 0.8.0 |
| PySide6 | ≥ 6.5 |
| 操作系统 | Windows 10/11（主要）, Linux, macOS |

### 7.2 可维护性

- **日志规范**: 核心模块 `fish_acoustics`，GUI 模块 `__name__`
- **配置读取**: `config.get("section", {}).get("key", default)` 链式调用
- **代码注释**: 中文注释，英文变量名/函数名

### 7.3 可扩展性

- **插件架构**: 支持自定义处理模块（未来）
- **配置热重载**: 修改配置后重新加载（未来）
- **多频扩展**: multifreq.py 已预留接口

---

## 8. 验收标准（Definition of Done）

### 8.1 功能验收

- [ ] 所有 P0 功能可正常使用（FR-01~FR-04）
- [ ] P1 功能 100% 可用（FR-05, FR-06, FR-09, FR-12, FR-13）
- [ ] P2 功能 80% 可用（FR-07, FR-08, FR-14）
- [ ] 单元测试覆盖率 ≥ 80%（总计 100+ 测试）
- [ ] 集成测试通过（GUI 信号槽、Worker 线程）

### 8.2 性能验收

- [ ] 文件加载 < 30s (100MB)
- [ ] Sv 计算 < 10s
- [ ] 渲染帧率 ≥ 30 FPS
- [ ] 内存峰值 < 2GB
- [ ] 批量处理 ≥ 10 文件/分钟

### 8.3 安全性验收

- [ ] 文件路径验证（防止目录遍历）
- [ ] 输出文件自动创建目录（`mkdir(parents=True, exist_ok=True)`）
- [ ] 配置文件 YAML 安全加载（`yaml.safe_load`）
- [ ] 超大数据量警告（CSV > 100MB 时 `warnings.warn`）

### 8.4 文档验收

- [ ] README 更新（安装、使用、配置）
- [ ] API 文档（docstring 完整，含 Args/Returns/Raises）
- [ ] 用户指南（操作流程、快捷键、FAQ）
- [ ] 配置参考（YAML 格式说明）

---

## 9. 附录

### 9.1 文件清单

| 模块 | 文件 | 说明 |
|------|------|------|
| 后端核心 | `src/core/acoustic.py` | 声学处理 |
| | `src/core/density.py` | 密度估算 |
| | `src/core/grid.py` | 网格分析 |
| | `src/core/region.py` | 区域管理 |
| | `src/core/school.py` | 鱼群检测 |
| | `src/core/quality.py` | 质量检查 |
| | `src/core/multifreq.py` | 多频分析 |
| | `src/core/export.py` | 数据导出 |
| | `src/core/utils.py` | 工具函数 |
| GUI | `src/gui/main_window.py` | 主窗口 |
| | `src/gui/toolbars.py` | 工具栏 |
| | `src/gui/property_panel.py` | 属性面板 |
| | `src/gui/workers.py` | 工作线程 |
| | `src/gui/stats_dialog.py` | 统计对话框 |
| | `src/gui/export_dialog.py` | 导出对话框 |
| | `src/gui/theme.py` | 蓝白主题 |
| 可视化 | `src/viz/opengl_renderer.py` | OpenGL 渲染 |
| 测试 | `tests/test_*.py` | 11 个测试模块 |

### 9.2 配置参考

#### 完整配置结构（configs/example.yaml）

```yaml
# 水库/调查项目信息
reservoir:
  name: "水库名称"        # 必填
  region: "省份"          # 可选

# 输入文件
input:
  raw_dir: "./raw_data"   # raw 文件目录
  pattern: "*.raw"         # 文件匹配模式

# 处理参数
processing:
  sonar_model: "EK80"     # EK80/EK60/AZFP
  frequencies: [200000]   # 频率列表（Hz）
  waveform_mode: "CW"     # CW（连续波）/ BB（宽带）
  encode_mode: "power"    # power/complex

  noise_removal:
    ping_num: 5            # 噪声估计 ping 数
    range_sample_num: 10   # 噪声估计采样数
    SNR_threshold: "3.0dB" # SNR 阈值（字符串格式）

  bottom_detection:
    method: "echoview"     # echoview/basic
    threshold: -50.0       # 底部阈值（dB），范围 -70 ~ -20
    offset_m: 0.5          # 底部偏移（米）
    bin_skip_from_surface: 200  # 跳过水面采样数

# 鱼群检测
school_detection:
  method: "echoview"       # echoview
  thr: -55.0               # 鱼群阈值（dB）
  mincan: [3.0, 10.0]     # 最小候选尺寸 [ping, sample]
  maxlink: [3.0, 15.0]    # 最大连接距离
  minsho: [3.0, 15.0]     # 最小鱼群尺寸

# 密度估算
density:
  ts_default: -30.0        # 默认 TS 值（dB）
  avg_weight_kg: 0.5       # 平均个体重量（kg）

# 输出
output:
  dir: "./outputs"         # 输出目录
  formats: ["csv", "xlsx"] # 导出格式：netcdf/zarr/csv/xlsx
```

#### 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `sonar_model` | str | "EK80" | 声纳型号，决定 echopype 解析方式 |
| `frequencies` | list[int] | [200000] | 处理频率（Hz），支持多频 |
| `SNR_threshold` | str | "3.0dB" | 信噪比阈值，必须带单位字符串 |
| `method` | str | "echoview" | 底部检测算法 |
| `threshold` | float | -50.0 | 底部强度阈值（dB） |
| `ts_default` | float | -30.0 | 默认目标强度（dB），用于密度转换 |

### 9.3 环境搭建

#### 依赖安装

```bash
# 1. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 2. 安装依赖
pip install -r requirements.txt

# 3. 验证安装
python -c "import echopype; print(echopype.__version__)"
python -c "from PySide6.QtWidgets import QApplication; print('PySide6 OK')"
```

#### requirements.txt 核心依赖

```
echopype>=0.8.0
xarray>=2023.1
numpy>=1.24
pandas>=2.0
PySide6>=6.5
PyOpenGL>=3.1
matplotlib>=3.7
pyyaml>=6.0
```

#### 启动 GUI

```bash
python -m src.app
```

### 9.4 故障排除（FAQ）

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| `ImportError: echopype` | 未安装 echopype | `pip install echopype` |
| `ImportError: PySide6` | 未安装 PySide6 | `pip install PySide6` |
| `ValueError: sonar_model` | 不支持的声纳型号 | 检查 `processing.sonar_model` 是否为 EK80/EK60/AZFP |
| `FileNotFoundError` | raw 文件路径错误 | 检查 `input.raw_dir` 和 `pattern` |
| `MemoryError` | 数据量过大 | 减小 `frequencies` 数量或分批处理 |
| 渲染黑屏 | OpenGL 驱动问题 | 更新显卡驱动，检查 `PyOpenGL` 版本 |
| 中文乱码 | CSV 编码问题 | 系统使用 `utf-8-sig` 编码，Excel 可直接打开 |
| 底部检测失败 | 阈值设置不当 | 调整 `bottom_detection.threshold`（-70 ~ -20 dB） |
| 批量处理卡死 | 线程冲突 | 减小 `max_workers`（默认 2） |

### 9.5 术语表

| 术语 | 说明 |
|------|------|
| Sv | Volume backscattering strength（体积反向散射强度），dB |
| NASC | Nautical area scattering coefficient（海里面积散射系数），m²/nm² |
| TS | Target strength（目标强度），dB |
| ABC | Area backscattering coefficient（面积反向散射系数） |
| Ping | 单次声纳发射-接收周期 |
| Sample | 单个 ping 的距离采样点 |
| Echoview | 商业声学分析软件（对标产品） |

---

## 变更记录

| 日期 | 版本 | 变更内容 |
|------|------|---------|
| 2026-08-07 | 1.0 | 初始版本，包含功能需求、API 规范、测试标准、性能指标、UX 规范 |
