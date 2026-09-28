# Echogram GUI — 鱼类声学资源评估系统

基于 [echopype](https://github.com/OSOceanAcoustics/echopype) 构建的专业鱼类声学数据处理 GUI，提供 Echoview 风格的交互式回波图分析。

## 功能特性

### 数据处理

| 功能 | 说明 |
|------|------|
| 文件加载 | 支持 Raw/EK60/EK80/AZFP 格式 |
| Sv 校准 | 使用 echopype 计算体积散射强度，原始数据永不覆盖 |
| 噪声去除 | 基于 ping/range/SNR 阈值的自适应噪声去除 |
| 底部检测 | 可调阈值 (-70~-20 dB)，支持 echoview/basic 方法 |

### 分析功能

| 功能 | 说明 |
|------|------|
| 鱼群检测 | 基于 echopype detect_shoal 的自动鱼群识别 |
| 密度估算 | ABC/NASC → 鱼类密度，支持深度分层 |
| 网格分析 | 垂直分层 × 水平分段的网格化统计 |
| 数据导出 | 支持 netCDF/Zarr/CSV/Excel 格式 |

### GUI 特性

| 特性 | 说明 |
|------|------|
| Echoview 风格布局 | 文件树 + 回波图 + 工具栏 |
| OpenGL 渲染 | 高性能回波图渲染，支持缩放/平移 |
| 交互式底线编辑 | 自动检测 + 自由手绘 + 分段替换 + Ctrl+Z 撤销 |
| 分析区域限定 | 表线/底线裁剪，所有分析在区域内生效 |
| 蓝白色主题 | 专业清爽的 UI 配色 |

## 安装

### 环境要求

- Python 3.11–3.13（已在 3.13.5 验证）
- 支持 OpenGL 的显卡

### 安装步骤

```bash
# 克隆仓库
git clone https://github.com/LQDC3417/echopype.git
cd echopype

# 创建虚拟环境
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 安装依赖
pip install -e .
```

### 依赖

| 包 | 版本 | 用途 |
|----|------|------|
| PySide6 | >=6.6.0 | GUI 框架 |
| PyOpenGL | >=3.1.7 | OpenGL 渲染 |
| echopype | >=0.11.0,<0.12 | 声学数据处理 |
| xarray | - | 多维数据 |
| numpy | - | 数值计算 |
| pandas | - | 数据分析 |
| matplotlib | - | 颜色映射 |
| scipy | - | 鱼群聚类 |
| PyYAML | - | 配置加载 |
| h5py、h5netcdf、openpyxl、zarr | - | 项目保存与结果导出 |

## 使用

### 启动 GUI

```bash
python -m src.app
```

### 基本流程

1. **导入调查文件**：选择一个或多个 RAW 文件，确认导入清单和时间接缝。
2. **选择分析通道**：在处理面板选择要查看和分析的通道；项目按原始通道 ID 分别保存处理状态。
3. **设置分析条件**：检查自动去噪策略、表线、底线和分析区域。参数变化会标记相关结果待重算。
4. **明确运行分析**：手动运行所需的底部、鱼群、积分或 SED 分析；积分会按已选通道和当前设置执行。
5. **保存项目与导出**：`.ep` 保存配置、标注、通道状态和结果表。过期、待核验或不完整的分析结果不能正式导出。

本项目是桌面 GUI 应用，不提供 CLI。项目复现入口按保存的活动通道和处理快照重算积分；它不重放历史点击顺序，也不重跑鱼群或 SED 检测。

### 配置文件

参考 `configs/example.yaml`：

```yaml
reservoir:
  name: "示例水库"
  region: "福建"

input:
  raw_dir: "path/to/raw/files"
  pattern: "*.raw"

processing:
  frequencies: [38000, 70000]
  waveform_mode: "CW"
  encode_mode: "power"
  noise_removal:
    ping_num: 5
    range_sample_num: 10
    SNR_threshold: "3.0dB"
  bottom_detection:
    method: "basic"
    threshold: -40.0
    offset_m: 0.5
    bin_skip_from_surface: 50

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
  dir: "outputs"
  formats: ["csv", "xlsx"]
```

## 项目结构

```
echopype/
├── src/
│   ├── app.py              # 应用入口
│   ├── core/               # 后端处理模块
│   │   ├── acoustic.py     # RAW 读取与 Sv 校准
│   │   ├── merge.py        # 多文件对齐与拼接
│   │   ├── processing.py   # 去噪与人工掩膜
│   │   ├── integration.py  # 分层积分
│   │   ├── sed.py          # 单体目标检测
│   │   ├── ep_project.py   # .ep 项目保存与恢复
│   │   ├── replay.py       # 保存快照的积分重算
│   │   └── export.py       # 数据导出
│   ├── gui/                # GUI 模块
│   │   ├── main_window.py  # 主窗口
│   │   ├── handlers/       # 文件、处理、分析与交互逻辑
│   │   ├── workers.py      # 后台线程
│   │   ├── theme.py        # UI 主题
│   │   └── ...
│   └── viz/                # 可视化
│       └── opengl_renderer.py  # OpenGL 渲染器
├── configs/                # 示例配置
├── tests/                  # 自动化测试
├── docs/                   # 文档
├── pyproject.toml          # 项目配置
├── requirements.txt        # 依赖清单
├── LICENSE                 # 开源许可证
└── README.md               # 本文件
```

## 测试

```bash
python -m pytest -q
```

真实 RAW 集成测试需显式运行 `python -m pytest --run-real-data -q`；默认测试会跳过这些用例。

## 技术文档

- [PR 文档](docs/PR-echogram-gui-v2.md) — 完整的功能说明和设计决策
- [设计文档](docs/superpowers/specs/2026-06-01-echogram-gui-design.md) — 架构设计

## 致谢

- [echopype](https://github.com/OSOceanAcoustics/echopype) — 声学数据处理核心库
- [Echoview](https://www.echoview.com/) — 交互设计理念参考

## 许可证

MIT License — 详见 [LICENSE](LICENSE)
