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
| 交互式底线编辑 | 自动检测 + 手动绘制 + 右键更新 |
| 分析区域限定 | 表线/底线裁剪，所有分析在区域内生效 |
| 蓝白色主题 | 专业清爽的 UI 配色 |

## 安装

### 环境要求

- Python 3.10+
- 支持 OpenGL 的显卡

### 安装步骤

```bash
# 克隆仓库
git clone https://github.com/YOUR_USERNAME/echopype-gui.git
cd echopype-gui

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
| echopype | >=0.11.0 | 声学数据处理 |
| xarray | - | 多维数据 |
| numpy | - | 数值计算 |
| pandas | - | 数据分析 |
| matplotlib | - | 颜色映射 |
| scipy | - | 鱼群聚类 |
| PyYAML | - | 配置加载 |

## 使用

### 启动 GUI

```bash
python -m src.app
```

### 命令行模式

```bash
# 运行完整流水线
fish-acoustics run configs/example.yaml

# 只运行声学处理
fish-acoustics run configs/example.yaml --step acoustic

# 查看处理状态
fish-acoustics status configs/example.yaml
```

### 基本流程

1. **导入文件**：点击"导入"按钮选择 Raw 文件目录
2. **计算 Sv**：点击"全部运行"或手动执行各步骤
3. **检测底部**：调整阈值后点击"检测底部"
4. **设置表线**：输入表线深度（离水面距离）
5. **检测鱼群**：点击"检测鱼群"
6. **计算密度**：点击"计算密度"
7. **网格分析**：设置垂直/水平间隔后点击"网格分析"
8. **导出结果**：点击"导出"选择格式和内容

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
echopype-gui/
├── src/
│   ├── app.py              # 应用入口
│   ├── cli.py              # CLI 入口
│   ├── core/               # 后端处理模块
│   │   ├── acoustic.py     # 声学处理（Sv、噪声、底部）
│   │   ├── density.py      # 密度估算（ABC/NASC）
│   │   ├── school.py       # 鱼群检测
│   │   ├── grid.py         # 网格化分析
│   │   ├── region.py       # 分析区域管理
│   │   ├── export.py       # 数据导出
│   │   ├── quality.py      # 数据质量检查
│   │   ├── multifreq.py    # 多频分析
│   │   └── utils.py        # 通用工具函数
│   ├── gui/                # GUI 模块
│   │   ├── main_window.py  # 主窗口
│   │   ├── toolbars.py     # 工具栏
│   │   ├── workers.py      # 后台线程
│   │   ├── stats_dialog.py # 统计对话框
│   │   ├── export_dialog.py# 导出对话框
│   │   ├── theme.py        # UI 主题
│   │   └── ...
│   └── viz/                # 可视化
│       └── opengl_renderer.py  # OpenGL 渲染器
├── configs/                # 配置文件
├── tests/                  # 单元测试 (62 个)
├── docs/                   # 文档
├── pyproject.toml          # 项目配置
├── requirements.txt        # 依赖清单
├── LICENSE                 # 开源许可证
└── README.md               # 本文件
```

## 测试

```bash
python -m pytest tests/ -v
```

测试覆盖：region、utils、density、grid、school、acoustic、config、GUI 集成。

## 技术文档

- [PR 文档](docs/PR-echogram-gui-v2.md) — 完整的功能说明和设计决策
- [设计文档](docs/superpowers/specs/2026-06-01-echogram-gui-design.md) — 架构设计

## 致谢

- [echopype](https://github.com/OSOceanAcoustics/echopype) — 声学数据处理核心库
- [Echoview](https://www.echoview.com/) — 交互设计理念参考

## 许可证

MIT License — 详见 [LICENSE](LICENSE)
