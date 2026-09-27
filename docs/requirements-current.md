# Fish Acoustics 当前实现需求文档

## 1. 文档说明

本文档根据当前代码、配置文件和测试用例反向整理，不以历史需求文档或未来计划为依据。

| 项目 | 内容 |
|---|---|
| 项目名称 | Fish Acoustics / echopype 声学数据处理系统 |
| 文档类型 | 当前实现需求文档（Reverse-engineered Requirements） |
| 依据 | `src/`、`tests/`、`README.md` |
| 当前日期 | 2026-09-26 |
| 主要入口 | PySide6 GUI |
| 核心依赖 | echopype、xarray、NumPy、PySide6、PyOpenGL、pandas |

本文档描述“代码现在应该能够做什么”，不等同于完整的产品规划。标记为“限制”的内容表示当前实现已经暴露出的边界，不代表已完成修复。

## 2. 系统目标

系统用于导入 EK80 等水声探测数据，生成并查看 Echogram，完成 Sv 计算、噪声处理、底部检测、鱼群识别、回声积分、密度估算和结果导出。

当前产品工作流是 GUI 交互式分析：用户通过项目、配置、处理菜单和 Echogram 界面完成数据分析。仓库不再提供 CLI。

## 3. 系统边界与技术架构

```text
raw / 配置文件
        │
        ▼
echopype.open_raw → EchoData
        │
        ▼
compute_Sv → xr.Dataset(Sv, depth, echo_range, GPS)
        │
        ├─ 噪声去除 → Sv_corrected
        ├─ 底部检测 → bottom_depth / bottom line
        ├─ 鱼群检测 → mask / schools DataFrame
        ├─ 回声积分 → ABC / density / grid statistics
        ├─ 多频率分析
        └─ 结果导出 → NetCDF / Zarr / CSV / Excel
```

主要模块职责：

| 模块 | 职责 |
|---|---|
| `src/core/acoustic.py` | raw 文件加载、Sv 计算、深度和 GPS 附加 |
| `src/core/merge.py` | GUI 多文件 Sv 对齐、深度重采样、时间排序和去重 |
| `src/core/noise.py` | 噪声参数和噪声相关分析 |
| `src/core/bottom_detection.py` | basic、enhanced、AFSC 底部检测 |
| `src/core/school.py` | 鱼群检测和鱼群表格提取 |
| `src/core/integration.py` | 按 ping 或 GPS 距离分组的回声积分、ABC 和密度 |
| `src/core/density.py` | ABC、Sv 统计和密度换算 |
| `src/core/region.py` | 表线、底线、分析区域和数据裁剪 |
| `src/core/quality.py` | Sv 和底线质量检查 |
| `src/core/multifreq.py` | 通道摘要、多频率比较和 transect 分段 |
| `src/core/sed.py` | 分裂波束真实单体目标检测和网格聚合 |
| `src/core/export.py` | NetCDF、Zarr、CSV、Excel 导出 |
| `src/core/ep_project.py` | `.ep` 项目文件的保存、加载和 raw 校验 |
| `src/gui/` | 主窗口、面板、菜单、对话框和后台工作线程 |
| `src/viz/` | OpenGL Echogram 渲染和图层叠加 |

## 4. 用户角色与主要场景

### 4.1 单文件分析

用户选择一个 raw 文件，系统加载 EchoData，计算 Sv，显示 Echogram，然后依次执行噪声去除、底部检测、鱼群检测和积分分析。

### 4.2 多文件调查数据合并

用户选择多个 raw 文件，系统逐个计算 Sv，再按照真实 `ping_time` 排序，并将不同深度网格重采样到公共网格后拼接。

当前 GUI 多文件合并以 `merge_aligned()` 生成的 `xr.Dataset` 为准；不会再强制调用 `echopype.combine_echodata()`，以避免不同 raw 文件的 EK80 滤波器系数维度不一致导致导入失败。

### 4.3 可复用项目

用户可以将 raw 文件路径、校验和、配置、表线深度、底线、噪声 mask、鱼群 mask 和分析结果保存为 `.ep` 项目文件。重新打开项目时，系统检查 raw 文件是否存在以及校验和是否一致，并从 raw 文件重新计算数据。

## 5. 功能需求

### FR-01 文件加载

系统应：

- 支持通过 `echopype.open_raw()` 加载 raw 文件。
- 从配置读取 `input.raw_dir` 和 `input.pattern`。
- 默认使用 `processing.sonar_model`，未配置时使用 `EK80`。
- 在文件不存在、目录不存在、格式不支持或加载失败时返回可显示的错误信息。
- GUI 支持单文件和多文件选择。
- GUI 多文件加载时逐文件发出进度和临时显示结果。

当前实现：已实现。支持的具体声纳格式取决于当前 echopype 版本和 `sonar_model` 配置。

### FR-02 GUI 多文件合并

系统应：

- 对每个 raw 文件独立计算 Sv、深度和 GPS。
- 保留第一个 channel 作为当前 Echogram 显示通道。
- 自动计算公共 `echo_range` 深度网格。
- 按真实时间戳排序 ping。
- 对重复时间戳进行去重。
- 将各文件结果拼接为一个连续 `xr.Dataset`。
- 对多个文件的不同采样深度进行重采样。

当前限制：多文件 GUI 导入后不生成合并 `EchoData` 对象。SED 对多文件逐个处理原始 EchoData，再按实际 ping 时间映射结果；项目 replay 使用保存的合并 Sv 与活动通道参数重算积分，不重放 SED。

### FR-03 Sv 计算

系统应：

- 自动检测 waveform mode：`CW` 或 `BB`。
- 自动检测 encode mode：`complex` 或 `power`。
- 调用 echopype 的 `compute_Sv()`。
- 生成 Sv 数据集。
- 使用 `add_depth()` 计算深度，并尽可能使用 Platform vertical offset。
- 从 Platform 数据插值附加 `latitude` 和 `longitude`。

主要输出变量包括：

- `Sv`
- `depth`
- `echo_range`
- `ping_time`
- `latitude` / `longitude`（存在有效 GPS 时）
- `gain_correction`
- `sa_correction`

### FR-04 噪声去除

系统应：

- 使用 `ping_num`、`range_sample_num` 和 `SNR_threshold` 配置。
- 调用 `echopype.clean.remove_background_noise()`。
- 保留原始 `Sv`。
- 将去噪结果保存为 `Sv_corrected`。
- 支持手动框选噪声区域，并将 mask 应用到 `Sv_corrected`。
- 不因手动 mask 操作覆盖原始 Sv。

### FR-05 底部检测

系统应支持：

- `basic`
- `enhanced`
- `afsc`

可配置参数包括阈值、表面跳过范围、峰值阈值、判别阈值、平滑窗口、搜索最小深度和回退参数等。

输出包括：

- 以米为单位的 `bottom_depth`。
- 用于 Echogram 显示和编辑的 bottom line sample index。

### FR-06 鱼群检测

系统应支持：

- `echoview` 方法。
- `advanced` 方法。

系统应输出：

- 鱼群二维 mask。
- 鱼群数量。
- 鱼群的 ping 范围、深度范围、面积和平均 Sv 等统计信息。
- Echogram 上的鱼群边界叠加。

### FR-07 分析区域

系统应允许用户设置：

- 表线深度。
- 自动或手动底线。
- 是否启用表线至底线的分析区域限制。

分析区域之外的数据应被设置为 NaN，而不是改变原始数组尺寸。积分、鱼群检测、质量检查和统计分析应优先使用裁剪后的分析数据。

### FR-08 回声积分与密度

系统应支持两种 EDSU 分组方式：

- `pings`：按 ping 数量分组。
- `distance`：按 GPS 累计距离分组；无有效 GPS 时回退到 ping 分组。

可配置参数包括：

- EDSU 大小。
- 垂直层宽。
- 最小和最大 Sv 阈值。
- 默认目标强度 `ts_default`。
- 表线深度和最大分析深度。

积分结果应包括：

- `mean_Sv`
- `abc`
- `min_Sv` / `max_Sv`
- 有效样本数和排除样本数。
- ping 或距离区间。
- 深度层范围。
- `density_ind_ha` 等密度指标。

### FR-09 多频率与 transect 分析

系统应支持：

- 通道列表和通道摘要。
- 频率、ping 数和 sample 数统计。
- 至少两个 channel 时进行频率 ABC 比较。
- 输出 mean、std、max ABC。
- 按时间间隔或其他配置进行 transect 分段。
- 将多频率结果导出为 CSV 或 Excel。

### FR-10 真实单体目标检测

系统应支持 EK80 分裂波束数据的真实单体目标检测，包括：

- TS 阈值筛选。
- 脉冲长度和归一化脉冲长度筛选。
- 沿船和横船方向测角。
- 角度标准差筛选。
- 波束补偿。
- 目标深度范围限制。
- 按积分网格聚合目标结果。

当前限制：该功能依赖单个 `EchoData`。GUI 多文件合并后不会伪造合并 EchoData，因此该功能当前应视为单文件功能。

### FR-11 数据质量检查

系统应检查：

- Sv 最小值和最大值。
- 原始 Sv 和校正 Sv 范围。
- NaN 比例。
- ping 数是否过少。
- 底线是否全部无效。
- 底线是否超出采样范围。
- 底线是否存在异常跳变。

检查结果应显示有效、警告或失败状态，并列出具体告警信息。

### FR-12 Echogram 交互

系统应支持：

- Sv Echogram 显示。
- 鼠标缩放和平移。
- 视图重置和适配。
- 光标位置的 ping、深度和 Sv 值显示。
- 噪声 mask、鱼群 mask、表线和底线叠加。
- 底线手动绘制。
- 底线更新、撤销和重做。
- 分析区域开关。
- 缩略图导航和文件页切换。
- 多种 colormap 和 Sv 显示范围。

### FR-13 项目文件

`.ep` v1.3 文件保存：

- raw 文件路径列表。
- raw 文件 MD5 校验和。
- 项目配置。
- 创建和修改时间。
- 表线深度。
- 底线。
- 噪声 mask。
- 鱼群 mask。
- 活动通道 ID 和各通道处理参数、线、区域、mask、结果状态及撤销信息。
- 鱼群、积分和 SED 的强类型结果表（区分未计算与已计算空表）。

`.ep` 文件不保存大体积 Sv 数组。打开项目时校验 raw 并重新计算 Sv；历史结果标记待核验，自动去噪策略与当前内存是否已生成校正数据分开保存。

### FR-14 数据导出

系统应支持：

| 格式 | 内容 |
|---|---|
| NetCDF | Sv、Sv_corrected、depth、echo_range、bottom_depth 等核心变量 |
| Zarr | 完整或较完整的 xarray 数据集 |
| CSV | Sv 长表、鱼群表、密度表 |
| Excel | 鱼群结果和密度结果，多 Sheet 输出 |

CSV 应使用 `utf-8-sig` 编码。Sv CSV 数据量过大时应提示用户优先使用 NetCDF 或 Zarr。

### FR-15 配置与预设

系统应支持：

- YAML 配置文件加载和保存。
- 配置合法性检查。
- 默认配置。
- reservoir、river、ocean、default 等预设。
- GUI 参数面板与配置字典双向同步。
- 保存最近使用的项目列表。
- 中英文界面切换。

## 6. GUI 菜单与操作需求

### 文件菜单

- 新建项目：选择一个或多个 raw 文件。
- 打开项目：打开 `.ep` 文件并校验 raw 文件。
- 保存项目。
- 打开配置。
- 保存配置。
- 导出结果。
- 最近项目。
- 退出。

### 编辑菜单

- 撤销。
- 重做。
- 清除噪声区域。
- 清除鱼群区域。

### 查看菜单

- 重置视图。
- 适配视图。
- 显示或隐藏噪声、鱼群、底线图层。
- 中文/英文切换。

### 处理菜单

- 运行完整流程。
- 计算 Sv。
- 噪声去除。
- 底部检测。
- 鱼群检测。

### 分析菜单

- 回声积分。
- 真实单体目标检测。
- 鱼群结果导出。
- 质量检查、多频率分析、Sv 统计和 transect 分段等分析入口。

## 7. 配置需求

配置至少包含以下部分：

```yaml
input:
  raw_dir: "./raw_data"
  pattern: "*.raw"

processing:
  sonar_model: "EK80"
  waveform_mode: "CW"
  encode_mode: "power"
  noise_removal: {}
  bottom_detection: {}

school_detection: {}
integration: {}
density: {}
output: {}
```

配置读取应允许缺省子项，并使用合理默认值。界面调整参数后，应同步更新当前运行配置。

## 8. 错误处理需求

系统应：

- 在 GUI 后台线程中捕获异常。
- 通过错误信号将完整 traceback 传递到界面。
- 在消息框或状态栏显示用户可理解的错误。
- 对文件不存在、raw 加载失败、格式不支持、参数无效和处理失败分别给出提示。
- 记录核心处理日志。
- 在后台任务运行期间显示进度，并允许安全关闭或等待任务结束。

已知边界：部分错误信息仍以 traceback 为主，后续可进一步转换为面向用户的诊断信息。

## 9. 非功能需求

### 性能

- 大型 raw 文件不应阻塞 GUI 主线程。
- 声学计算、噪声去除、底部检测、鱼群检测和积分应运行在后台 worker。
- 多文件导入应支持增量显示和进度反馈。
- 导出大数据时应避免无提示地生成超大 CSV。

### 数据安全

- 保存 `.ep` 项目时采用临时文件替换方式，避免直接覆盖导致项目损坏。
- 打开项目前校验 raw 文件存在性和 MD5。
- Zarr 已存在时默认拒绝覆盖，只有显式允许时才覆盖。
- 不应通过导入路径访问未授权目录以外的数据。

### 可维护性

- 后端计算逻辑与 GUI 展示逻辑分离。
- 处理参数集中在配置字典中。
- 关键处理步骤有独立 worker 和测试。
- 原始 `Sv` 与校正后的 `Sv_corrected` 分离保存。

## 10. 当前实现限制与待确认事项

以下内容是根据当前代码识别出的限制，不属于已经完成的功能需求：

1. GUI 多文件导入使用自定义 Sv 合并；多文件 SED 按各原始文件处理后映射结果，尚无 ESP3/Echoview 同数据基准输出。
2. 项目 replay 目前重算选定通道积分，不重跑底部、鱼群或 SED 检测，也不是历史操作序列回放。
3. `.ep` 不保存 Sv 缓存，打开项目需要重新读取 raw 并校准；保存的结果表和通道状态用于查看、审计及后续计算。
4. 过期、未核验或部分输入的结果不能正式导出；原始数据导出与分析结果导出有不同资格要求。
5. 具体支持哪些声纳型号，取决于 `sonar_model` 配置和当前 echopype 版本。
6. 约 1 GB 用户现场调查尚未指定并执行本轮验收；超过 30 个文件/30 GB 的分块处理也未实现或验收。
7. 需求文档没有定义正式的用户权限、远程数据源和插件机制；性能仍缺少可重复基准体系。

## 11. 验收建议

### 基础验收

- 单个有效 raw 文件能够导入并显示 Echogram。
- Sv、depth、echo_range 能够生成。
- 噪声去除能够生成 `Sv_corrected` 且不覆盖 `Sv`。
- basic/enhanced/afsc 底部检测均能返回结果。
- 鱼群检测能够生成 mask 和统计表。
- 回声积分能够生成 ABC、密度和网格结果。
- NetCDF、Zarr、CSV、Excel 导出能够生成文件。

### 多文件验收

- 两个深度网格不同的 raw 文件能够完成 GUI 合并。
- 文件顺序与真实 `ping_time` 一致。
- 重复 ping 能够去重。
- 存在 `WBT_filter_n=23` 和 `WBT_filter_n=95` 的文件时，GUI 导入不应触发 `AlignmentError`。
- 多文件导入失败时，界面应显示明确的处理阶段和文件信息。

### 项目验收

- `.ep` 能够保存和加载。
- raw 文件缺失或校验和变化时能够阻止项目继续加载。
- 项目重新打开后能够恢复表线、底线、mask 和结果表。

## 12. 当前代码覆盖的测试范围

测试目录覆盖以下领域：

- acoustic 加载和处理。
- merge 对齐合并。
- noise、bottom、school、density、integration。
- region、quality、multifreq。
- GUI 集成、渲染器、底线绘制和 worker。
- 导出和项目相关高优先级修复。

本需求文档新增的多文件导入回归测试位于：

```text
tests/test_gui_workers.py
```
