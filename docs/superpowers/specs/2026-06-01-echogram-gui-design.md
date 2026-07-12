# Echogram GUI 可视化处理系统 — 设计文档

**日期**: 2026-06-01
**状态**: 设计阶段

---

## 一、项目概述

将现有 CLI 模式的 echopype 鱼类资源评估项目重构为专业级桌面 GUI 应用，参考 Echoview 和 Sonar 5 Pro 的交互体验。

### 核心目标
- 交互式 Echogram 可视化（OpenGL 渲染）
- 实时噪声剔除（自动 + 手动框选）
- 交互式底部线编辑（拖拽 / 绘制 / 参数化重检测）
- 鱼群检测结果叠加显示
- 密度估算与统计导出

---

## 二、技术选型

| 组件 | 选择 | 理由 |
|------|------|------|
| GUI 框架 | PySide6 | LGPL 协议，Qt 官方 Python 绑定 |
| 渲染 | OpenGL (QOpenGLWidget) | GPU 加速，大数据 echogram 流畅 |
| 处理后端 | echopype | 现有模块复用 |
| 异步 | QThread + 信号/槽 | 不阻塞 UI |
| 配置 | YAML | 复用现有格式 |

---

## 三、界面布局

```
┌──────────────────────────────────────────────────────────────┐
│  菜单栏: 文件 | 处理 | 视图 | 帮助                              │
│  工具栏: [打开] [运行] [撤销] [缩放] [颜色映射] [导出]           │
├──────────┬─────────────────────────┬─────────────────────────┤
│ 文件树    │                         │ 属性面板 (QTabWidget)    │
│          │                         │ ┌─ 文件信息 ──────────┐  │
│ ─ raw    │    Echogram 主显示区     │ │ 声呐型号/频率/时间   │  │
│ ─ zarr   │    (QOpenGLWidget)      │ └────────────────────┘  │
│ ─ csv    │                         │ ┌─ 处理参数 ──────────┐  │
│          │    [底部线] [噪声mask]   │ │ Sv 波形/编码模式     │  │
│          │    [鱼群边界叠加]        │ │ 噪声去除参数         │  │
│          │                         │ │ 底部检测参数         │  │
│          │                         │ │ 鱼群检测参数         │  │
│          │                         │ └────────────────────┘  │
│          │                         │ ┌─ 统计结果 ──────────┐  │
│          │                         │ │ ABC / 密度 / 生物量  │  │
│          │                         │ │ 鱼群列表             │  │
│          │                         │ └────────────────────┘  │
├──────────┴─────────────────────────┴─────────────────────────┤
│  [进度条] 状态信息                              日志输出        │
└──────────────────────────────────────────────────────────────┘
```

### 布局说明
- **左侧文件树** (QTreeView): 显示已加载的 raw/zarr/csv 文件
- **中间 Echogram** (QOpenGLWidget): 核心显示区域，支持缩放/平移/选择
- **右侧属性面板** (QTabWidget): 文件信息、处理参数、统计结果三个标签页
- **底部状态栏**: 进度条 + 状态信息 + 日志

---

## 四、Echogram 交互功能

### 4.1 基础交互
- **缩放**: 鼠标滚轮缩放，Ctrl+滚轮水平缩放
- **平移**: 鼠标中键拖拽平移
- **框选**: 左键拖拽选择区域
- **十字光标**: 跟随鼠标显示 ping/depth 坐标

### 4.2 噪声剔除

#### 自动噪声去除
- 右侧参数面板调整 `ping_num`, `range_sample_num`, `SNR_threshold`
- 参数变化时触发 `QTimer` 防抖（300ms），在后台线程重新计算
- 结果实时更新 echogram，被排除的噪声区域显示为半透明灰色覆盖

#### 手动框选剔除
- 工具栏切换到"噪声选择"模式
- 在 echogram 上拖拽矩形框选噪声区域
- 框选区域叠加红色半透明 mask
- 支持多区域选择，Ctrl+Z 撤销
- 手动 mask 与自动噪声 mask 取并集

### 4.3 底部线编辑

#### 拖拽调整
- 自动检测底部线后，显示为白色折线
- 鼠标悬停底部线附近时，光标变为可拖拽状态
- 拖拽节点调整位置，相邻线段自动插值
- 实时更新底部深度数据

#### 手动绘制
- 工具栏切换到"绘制底部线"模式
- 在 echogram 上依次点击绘制底部线节点
- 双击或按 Enter 结束绘制
- 自动替换原有底部线

#### 参数化重检测
- 右侧参数面板调整 `threshold`, `offset_m`, `bin_skip_from_surface`
- 点击"重新检测"按钮，后台线程执行 `detect_seafloor`
- 结果实时更新 echogram

### 4.4 鱼群显示
- 检测到的鱼群区域用彩色半透明边界叠加在 echogram 上
- 点击鱼群边界，右侧面板显示该鱼群属性（面积、深度范围、平均 Sv）
- 鱼群列表在右侧面板以表格形式展示

---

## 五、数据处理流程

```
[用户打开 .raw 文件]
       ↓
[后台线程] open_raw(sonar_model) → EchoData
       ↓ 信号: file_loaded
[后台线程] compute_Sv(waveform_mode, encode_mode) → ds_Sv
       ↓ 信号: sv_computed → 更新 echogram 显示
       ↓
[用户调整噪声参数 / 框选噪声区域]
       ↓
[后台线程] remove_background_noise + 手动 mask → ds_Sv_corrected
       ↓ 信号: noise_removed → 更新 echogram 显示
       ↓
[用户调整底部参数 / 编辑底部线]
       ↓
[后台线程] detect_seafloor + 手动编辑 → bottom_depth
       ↓ 信号: bottom_updated → 更新 echogram 显示
       ↓
[用户点击"检测鱼群"]
       ↓
[后台线程] detect_shoal → mask → schools_to_dataframe
       ↓ 信号: schools_detected → 更新 echogram 叠加 + 右侧面板
       ↓
[用户点击"计算密度"]
       ↓
[后台线程] calculate_abc + estimate_density → density_df
       ↓ 信号: density_computed → 更新右侧面板 + 导出 CSV
```

---

## 六、模块结构

```
src/
├── gui/
│   ├── __init__.py
│   ├── main_window.py        # 主窗口 (QMainWindow)
│   ├── echogram_widget.py    # Echogram OpenGL 渲染
│   ├── file_tree.py          # 左侧文件树
│   ├── property_panel.py     # 右侧属性面板
│   ├── status_bar.py         # 底部状态栏
│   ├── toolbars.py           # 工具栏
│   ├── dialogs.py            # 对话框（打开文件、导出等）
│   └── workers.py            # QThread 后台工作线程
├── core/
│   ├── __init__.py
│   ├── acoustic.py           # 声学处理（从现有重构）
│   ├── school.py             # 鱼群识别（从现有重构）
│   ├── density.py            # 密度估算（从现有重构）
│   └── utils.py              # 配置加载、日志
├── viz/
│   ├── __init__.py
│   └── opengl_renderer.py    # OpenGL echogram 渲染器
└── app.py                    # 应用入口
```

### 模块职责

| 模块 | 职责 | 依赖 |
|------|------|------|
| `gui/main_window.py` | 主窗口布局、菜单栏、工具栏、信号连接 | PySide6 |
| `gui/echogram_widget.py` | Echogram 显示、鼠标交互、mask/底部线叠加 | PySide6, OpenGL |
| `gui/file_tree.py` | 文件树管理 | PySide6 |
| `gui/property_panel.py` | 参数编辑、统计显示 | PySide6 |
| `gui/workers.py` | 后台处理线程 | QThread, core |
| `core/acoustic.py` | open_raw, compute_Sv, noise, seafloor | echopype |
| `core/school.py` | detect_shoal, schools_to_dataframe | echopype, scipy |
| `core/density.py` | calculate_abc, estimate_density | numpy, pandas |
| `viz/opengl_renderer.py` | OpenGL 纹理渲染 echogram | OpenGL |

---

## 七、OpenGL Echogram 渲染

### 渲染策略
- 将 Sv 数据转换为 RGB 纹理（使用 matplotlib colormap 或自定义颜色表）
- 纹理上传到 GPU，渲染为 2D 四边形
- 缩放/平移通过变换矩阵实现，不重新生成纹理
- 大数据分块加载（texture tiling），只渲染可见区域

### 叠加层
- **噪声 mask**: 半透明红色纹理，与 echogram 纹理叠加
- **底部线**: OpenGL 折线 (GL_LINE_STRIP)，白色
- **鱼群边界**: OpenGL 折线，彩色（每个鱼群不同颜色）
- **框选区域**: 半透明蓝色矩形

### 颜色映射
- 默认: Echoview 风格 (jet-like, -80 ~ -40 dB)
- 可选: viridis, inferno, grayscale
- 右侧面板滑块调整 vmin/vmax

---

## 八、关键交互实现

### 实时预览防抖机制
```
参数变化信号 → QTimer(300ms) → 取消上一次任务 → 启动新 QThread
                                   ↓
                           QThread 完成 → 信号 → 更新 echogram
```

### 撤销/重做
- 维护操作栈 (list of actions)
- 每次编辑（噪声框选、底部线调整）记录操作前状态
- Ctrl+Z 恢复上一状态，Ctrl+Y 重做

### 鼠标模式切换
```python
class MouseMode(Enum):
    NAVIGATE = 0      # 缩放/平移
    SELECT_NOISE = 1  # 框选噪声
    DRAW_BOTTOM = 2   # 绘制底部线
    ADJUST_BOTTOM = 3 # 拖拽底部线节点
    INSPECT = 4       # 点击查看鱼群属性
```

---

## 九、入口与启动

```python
# app.py
def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
```

启动命令: `python -m src.app` 或 `python src/app.py`

---

## 十、依赖清单

```
PySide6>=6.6.0
PyOpenGL>=3.1.7
echopype>=0.9.0
numpy
pandas
xarray
scipy
pyyaml
matplotlib  # 仅用于 colormap，不用于渲染
```

---

## 十一、与现有代码的关系

| 现有模块 | 处理方式 |
|----------|----------|
| `src/acoustic.py` | 移动到 `src/core/acoustic.py`，接口不变 |
| `src/school.py` | 移动到 `src/core/school.py`，接口不变 |
| `src/density.py` | 移动到 `src/core/density.py`，接口不变 |
| `src/utils.py` | 移动到 `src/core/utils.py`，接口不变 |
| `src/viz.py` | 删除，由 `gui/echogram_widget.py` + `viz/opengl_renderer.py` 替代 |
| `src/cli.py` | 删除，由 `gui/main_window.py` 替代 |
| `tests/` | 更新导入路径，保留所有测试 |
