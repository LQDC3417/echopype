# Echogram — 鱼类声学资源评估系统 用户指南

**版本**: 2.0  
**更新**: 2026-08-07

---

## 目录

1. [安装](#1-安装)
2. [快速开始](#2-快速开始)
3. [界面介绍](#3-界面介绍)
4. [操作流程](#4-操作流程)
5. [快捷键](#5-快捷键)
6. [配置文件](#6-配置文件)
7. [常见问题](#7-常见问题)

---

## 1. 安装

### 系统要求

| 项 | 要求 |
|----|------|
| Python | ≥ 3.10 |
| 操作系统 | Windows 10/11, Linux, macOS |
| 显卡 | 支持 OpenGL 3.0+ |

### 安装步骤

```bash
# 1. 克隆项目
git clone <仓库地址>
cd echopype

# 2. 创建虚拟环境
python -m venv venv
venv\Scripts\activate    # Windows
# source venv/bin/activate  # Linux/Mac

# 3. 安装依赖
pip install -r requirements.txt

# 4. 验证安装
python -c "import echopype; print(echopype.__version__)"
python -c "from PySide6.QtWidgets import QApplication; print('PySide6 OK')"
```

### 核心依赖

```
echopype>=0.8.0       # 声学数据处理
xarray>=2023.1        # 多维数据
numpy>=1.24           # 数值计算
pandas>=2.0           # 表格数据
PySide6>=6.5          # GUI 框架
PyOpenGL>=3.1         # OpenGL 渲染
matplotlib>=3.7       # 颜色映射
pyyaml>=6.0           # 配置文件
```

---

## 2. 快速开始

### 启动 GUI

```bash
python -m src.app
```

### 5 分钟快速流程

```
1. 文件 → 导入 Raw 文件 (Ctrl+I) → 选择 .raw 文件
2. 双击左侧文件树中的文件名
3. 处理 → 全部运行 (F5)
4. 查看回波图，调整参数
5. 文件 → 导出结果 (Ctrl+E)
```

---

## 3. 界面介绍

### 主窗口布局

```
┌──────────────────────────────────────────────────┐
│ Menu Bar                                          │
├──────────────────────────────────────────────────┤
│ StandardToolBar | EchogramToolBar                 │
├───────────┬──────────────────────┬───────────────┤
│ [Dock]    │                      │ [Dock]        │
│ 文件树    │    Echogram (GL)     │ 属性面板      │
│ 变量列表  │                      │ 信息/参数/结果│
├───────────┴──────────────────────┴───────────────┤
│ [Dock] 区域表格 (可折叠)                          │
├──────────────────────────────────────────────────┤
│ Status Bar                                        │
└──────────────────────────────────────────────────┘
```

### 各区域功能

| 区域 | 功能 |
|------|------|
| **文件树** (左) | 显示已导入的文件集，支持多文件切换 |
| **变量列表** (左) | 显示当前数据集的变量（Sv, Sv_corrected 等） |
| **Echogram** (中) | OpenGL 渲染的回波图，支持缩放/平移/叠加 |
| **属性面板** (右) | 文件信息、处理参数、统计结果 |
| **区域表格** (底) | 分析区域管理 |
| **状态栏** (底) | 坐标显示、Sv 值、处理进度 |

### 属性面板标签页

| 标签 | 内容 |
|------|------|
| 文件信息 | 当前文件的通道、频率、Ping 数、时间范围 |
| 处理参数 | 噪声去除、底部检测、鱼群检测、密度估算、网格分析、质量检查、多频分析 |
| 统计结果 | 鱼群统计、密度统计、网格统计 |

---

## 4. 操作流程

### 4.1 文件导入

**方式一：菜单导入**
1. 文件 → 导入 Raw 文件 (Ctrl+I)
2. 选择一个或多个 .raw 文件
3. 文件自动添加到左侧文件树

**方式二：拖拽导入**
1. 将 .raw 文件拖入文件树区域
2. 松开后自动创建文件集并加载

**支持格式**：EK80, EK60, AZFP (.raw)

### 4.2 数据处理

#### 全部运行 (F5)
一键执行完整处理流程：Sv 计算 → 噪声去除 → 底部检测

#### 分步处理

| 步骤 | 快捷键 | 说明 |
|------|--------|------|
| 计算 Sv | Ctrl+1 | 计算体积反向散射强度 |
| 噪声去除 | Ctrl+2 | 基于 SNR 阈值去除噪声 |
| 检测底部 | Ctrl+3 | 自动检测海底部线 |
| 检测鱼群 | Ctrl+4 | 检测鱼群/虾群 |
| 计算密度 | Ctrl+5 | 估算鱼类密度 |

### 4.3 底线编辑

1. 切换鼠标模式为"绘制底线"
2. **左键拖动**：自由手绘底线，密集采样形成平滑曲线
3. **分段替换**：只替换新绘制覆盖的 Ping 范围，保留其他部分
4. **Ctrl+Z**：撤销上一步编辑（最多 50 步）
5. **右键菜单**：完成绘制、清除绘制点、撤销操作

### 4.4 网格分析

1. 属性面板 → 处理参数 → 网格分析
2. 设置参数：
   - 垂直间隔：1m / 2m / 5m
   - 水平间隔：Ping 数或距离
   - 分段方式：Ping / 距离（GPS）
3. 点击"网格分析"
4. 结果自动叠加到回波图（颜色编码 mean_sv）
5. 统计对话框显示详细数据

### 4.5 质量检查

1. 属性面板 → 处理参数 → "🔍 数据质量检查"
2. 自动检查：
   - Sv 数据完整性（NaN 比例、值范围）
   - 底线有效性（跳变、连续性）
3. 弹窗显示检查结果和警告

### 4.6 多频分析

1. 属性面板 → 处理参数 → "📊 多频分析"
2. 自动分析：
   - 通道信息（频率、Ping 数）
   - 多频率 ABC 对比（需 ≥ 2 通道）
3. 弹窗显示分析结果

### 4.7 批量处理

1. 处理 → 批量处理文件 (Ctrl+B)
2. 选择多个 .raw 文件
3. 后台并行处理（默认 2 workers）
4. 状态栏显示进度：✓ 完成 [2/5]: xxx.raw
5. 完成后弹窗提示成功/失败数

### 4.8 数据导出

1. 文件 → 导出结果 (Ctrl+E)
2. 选择导出格式：
   - netCDF (.nc) — 科学数据标准格式
   - CSV (.csv) — 通用表格格式（UTF-8-BOM，Excel 兼容）
   - Excel (.xlsx) — 多 Sheet 工作簿
   - Zarr (.zarr) — 大数据格式
3. 选择导出内容：Sv / 鱼群 / 密度 / 网格

---

## 5. 快捷键

### 文件操作

| 快捷键 | 功能 |
|--------|------|
| Ctrl+I | 导入 Raw 文件 |
| Ctrl+O | 打开配置文件 |
| Ctrl+Shift+S | 保存配置 |
| Ctrl+E | 导出结果 |
| Ctrl+B | 批量处理 |
| Ctrl+Q | 退出 |

### 处理操作

| 快捷键 | 功能 |
|--------|------|
| F5 | 全部运行 |
| Ctrl+1 | 计算 Sv |
| Ctrl+2 | 噪声去除 |
| Ctrl+3 | 检测底部 |
| Ctrl+4 | 检测鱼群 |
| Ctrl+5 | 计算密度 |

### 编辑操作

| 快捷键 | 功能 |
|--------|------|
| Ctrl+Z | 撤销底线编辑 |
| Ctrl+Y | 重做 |

### 视图操作

| 快捷键 | 功能 |
|--------|------|
| Ctrl++ | 放大 |
| Ctrl+- | 缩小 |
| Ctrl+0 | 适应窗口 |
| Escape | 取消绘制 |

---

## 6. 配置文件

### 配置文件格式 (YAML)

```yaml
# 水库/调查项目信息
reservoir:
  name: "水库名称"
  region: "省份"

# 输入文件
input:
  raw_dir: "./raw_data"
  pattern: "*.raw"

# 处理参数
processing:
  sonar_model: "EK80"     # EK80/EK60/AZFP
  frequencies: [200000]   # 频率列表（Hz）
  waveform_mode: "CW"     # CW/BB
  encode_mode: "power"    # power/complex

  noise_removal:
    ping_num: 5
    range_sample_num: 10
    SNR_threshold: "3.0dB"

  bottom_detection:
    method: "echoview"     # echoview/basic
    threshold: -50.0       # dB，范围 -70 ~ -20
    offset_m: 0.5

# 鱼群检测
school_detection:
  method: "echoview"
  thr: -55.0
  mincan: [3.0, 10.0]
  maxlink: [3.0, 15.0]
  minsho: [3.0, 15.0]

# 密度估算
density:
  ts_default: -30.0
  avg_weight_kg: 0.5

# 输出
output:
  dir: "./outputs"
  formats: ["csv", "xlsx"]
```

### 配置文件操作

- **打开配置**：文件 → 打开配置文件 (Ctrl+O)
- **保存配置**：文件 → 保存配置 (Ctrl+Shift+S)
- **默认配置**：`configs/example.yaml`

---

## 7. 常见问题

### 安装问题

| 问题 | 解决方案 |
|------|---------|
| `ImportError: echopype` | `pip install echopype` |
| `ImportError: PySide6` | `pip install PySide6` |
| `ImportError: PyOpenGL` | `pip install PyOpenGL` |
| OpenGL 渲染黑屏 | 更新显卡驱动，检查 PyOpenGL 版本 |

### 数据处理问题

| 问题 | 解决方案 |
|------|---------|
| 文件加载失败 | 检查 sonar_model 是否匹配（EK80/EK60/AZFP） |
| 底部检测失败 | 调整 threshold（-70 ~ -20 dB），尝试不同 method |
| 鱼群检测无结果 | 降低 thr 值（如 -60），减小 minsho |
| 内存不足 | 减小 frequencies 数量，或分批处理 |

### 显示问题

| 问题 | 解决方案 |
|------|---------|
| 回波图全黑 | 检查 Sv 数据是否有效（质量检查） |
| 中文乱码 | CSV 使用 UTF-8-BOM 编码，Excel 可直接打开 |
| 网格叠加不显示 | 确认已运行网格分析，检查 mean_sv 列存在 |

### 性能问题

| 问题 | 解决方案 |
|------|---------|
| 渲染卡顿 | 缩小数据范围，或升级显卡驱动 |
| 批量处理慢 | 减小 max_workers（默认 2），避免内存溢出 |
| 文件加载慢 | 检查磁盘 I/O，使用 SSD |

---

## 附录

### 术语表

| 术语 | 说明 |
|------|------|
| Sv | Volume backscattering strength（体积反向散射强度），dB |
| TS | Target strength（目标强度），dB |
| ABC | Area backscattering coefficient（面积反向散射系数） |
| NASC | Nautical area scattering coefficient（海里面积散射系数） |
| Ping | 单次声纳发射-接收周期 |
| Sample | 单个 ping 的距离采样点 |
| Echoview | 商业声学分析软件（对标产品） |

### 联系方式

- 项目地址：<GitHub 仓库地址>
- 问题反馈：<Issues 页面>
