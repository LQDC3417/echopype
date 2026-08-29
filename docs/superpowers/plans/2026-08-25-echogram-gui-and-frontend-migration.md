# Echogram GUI and Frontend Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在保持当前 Python 科学计算能力的前提下，先完成 PySide6 GUI 的现代化，再通过可验证的原型决定是否迁移到其他前端语言或桌面技术栈。

**Architecture:** 短期继续使用 PySide6，保留 echopype、xarray、NumPy、pandas 和现有 OpenGL Echogram 渲染器。中期先把 Qt 事件、Worker 和业务计算之间的耦合拆开，形成稳定的 Python application service 边界；只有在该边界稳定且性能测试通过后，才评估 QML/Qt Quick、TypeScript/Tauri 或 C#/WinUI/Avalonia 作为新前端。

**Tech Stack:** Python 3.13+, PySide6/Qt 6, Qt Widgets, optional QML/Qt Quick, QOpenGLWidget/Qt RHI, echopype, xarray, NumPy, pandas, pytest, ruff.

---

## 1. 当前结论与技术选择

### 1.1 当前阶段继续使用 PySide6

当前项目的 GUI 与可视化代码约 8,091 行，其中 `src/viz/opengl_renderer.py` 约 1,364 行，核心依赖包括 `QOpenGLWidget`、Qt Signal、QThread、QDockWidget、xarray 和 echopype。现在更换语言会同时重写窗口系统、渲染器、后台任务、数据传输和打包流程，因此不能把迁移当作单纯的 UI 换肤。

第一阶段只做以下工作：

- 继续使用 PySide6/Qt Widgets。
- 重构主题、间距、Dock 面板、工具栏、表格和状态栏。
- 保留现有 Echogram OpenGL 渲染器及其交互协议。
- 将业务计算从 GUI Handler/Worker 中逐步抽离。
- 不在这一阶段引入 Electron、Flutter 或 C++ 全量重写。

### 1.2 后续候选方案

| 方案 | 前端语言/技术 | 适合场景 | 本项目主要风险 | 优先级 |
|---|---|---|---|---|
| QML + Python | QML/JavaScript + PySide6 | 保留 Python 后端并实现现代声明式 UI | 复杂 Dock 工作台和现有 OpenGL 嵌入需要适配 | 最高 |
| React + TypeScript + Tauri | TypeScript/HTML/CSS + Rust 壳 + Python 服务 | 现代桌面 UI，未来可能扩展 Web | Python IPC、大型数组传输、WebGL 重写和打包 | 第二 |
| C# + WinUI 3 | C#/XAML | Windows 原生商业软件 | Python 服务边界、渲染器和全部 Qt 控件重写 | 第三 |
| C# + Avalonia | C#/AXAML | Windows/macOS/Linux 跨平台 | 生态和数据服务迁移成本 | 第四 |
| Electron | TypeScript/HTML/CSS + Chromium/Node | Web 团队快速桌面化 | 运行时体积、内存、科学数据传输 | 暂不采用 |
| Flutter | Dart | 同时覆盖桌面和移动端 | 专业桌面 Dock、科学绘图和 Python 集成 | 暂不采用 |
| C++ + Qt | C++/Qt | 极致性能和原生控制 | 最高重写成本，重复实现现有 Python 后端 | 暂不采用 |

### 1.3 Echoview 参考边界

Echoview 官方公开资料说明其早期版本使用 C++ 构建；当前版本支持 64 位 Windows，并使用 OpenGL 场景、DirectX 4D 窗口和 COM Automation。官方没有公开当前 GUI 具体采用 MFC、Qt、WinUI 还是其他控件框架，因此不能把某一种框架当作 Echoview 当前实现的确定事实。

参考资料：

- https://echoview.com/about-us/30-years-in-2025/
- https://support.echoview.com/WebHelp/_Introduction/Computer_requirements.htm
- https://support.echoview.com/WebHelp/How_To/Run_Echoview_Using_Scripts/Automation_Using_COM_Objects/Scripting_with_COM_objects.htm

## 2. 文件边界

### 2.1 当前 PySide6 GUI 层

- `src/gui/main_window.py`：主窗口、菜单、Dock 和全局 UI 连接。
- `src/gui/theme.py`：主题 token、控件样式和浅色/深色模式。
- `src/gui/toolbars.py`：标准工具栏与 Echogram 工具栏。
- `src/gui/property_panel.py`：处理参数和分析操作面板。
- `src/gui/left_panel.py`、`src/gui/region_panel.py`：变量、Fileset 和区域浏览器。
- `src/gui/status_bar.py`、`src/gui/stats_dialog.py`：状态、日志、统计和导出视图。
- `src/viz/opengl_renderer.py`：Echogram 主渲染器，第一阶段保持 API 稳定。

### 2.2 中期新增的应用服务层

- Create: `src/application/models.py`：定义数据集摘要、当前变量、分析区域和任务状态的数据模型。
- Create: `src/application/services.py`：提供加载、Sv 计算、噪声处理、底线检测、鱼群检测、积分和导出的服务接口。
- Create: `src/application/events.py`：定义进度、数据就绪、错误和结果完成事件。
- Create: `src/gui/application_bridge.py`：将 application service 事件适配为 PySide6 Signal；后续 QML 或其他前端只依赖这一层。
- Test: `tests/test_application_services.py`、`tests/test_application_bridge.py`。

### 2.3 设计模板

- Keep: `templates/echoview_gui_template.py` 作为浅色视觉参考，不接入正式业务逻辑。
- Keep: `outputs/echoview_gui_template.png` 作为本地审阅产物；默认不加入 Git 提交。
- Create later: `docs/superpowers/plans/` 下的迁移记录和性能基准报告。

## 3. 分阶段实施任务

### Task 1: 冻结现有 GUI 行为基线

**Files:**
- Test: `tests/test_gui_baseline.py`
- Inspect: `src/gui/main_window.py`
- Inspect: `src/viz/opengl_renderer.py`

- [ ] **Step 1: 建立 GUI 冒烟测试**

测试必须在 `QT_QPA_PLATFORM=offscreen` 下创建主窗口或最小化窗口，验证菜单、中央 Echogram、左右 Dock、底部区域面板和状态栏存在。

- [ ] **Step 2: 固定渲染器交互契约**

记录并测试以下 Signal/方法不变：

```text
mouse_moved
region_selected
bottom_line_edited
sv_at_cursor
analysis_region_toggle
set_data()
set_bottom_line()
set_noise_mask()
set_school_mask()
```

- [ ] **Step 3: 运行基线验证**

```powershell
python -m pytest tests/test_gui_baseline.py -q
```

Expected: GUI 冒烟测试通过，且不要求读取真实 `.raw` 文件。

### Task 2: 完成 PySide6 浅色 GUI 现代化

**Files:**
- Modify: `src/gui/theme.py`
- Modify: `src/gui/main_window.py`
- Modify: `src/gui/toolbars.py`
- Modify: `src/gui/property_panel.py`
- Modify: `src/gui/left_panel.py`
- Modify: `src/gui/region_panel.py`
- Modify: `src/gui/status_bar.py`
- Test: `tests/test_gui_theme.py`

- [ ] **Step 1: 建立主题 token**

统一定义窗口背景、Dock 背景、边框、主文字、次文字、选中态、警告态、成功态和 Echogram 辅助线颜色。所有新样式必须引用 token，不能在各控件中散落颜色字面量。

- [ ] **Step 2: 统一布局密度**

默认窗口以 1440×900 和 1920×1080 为目标：左 Dock 240–280px，右 Dock 300–340px，底部 Dock 160–220px，中央 Echogram 占用剩余空间。保留用户可拖拽、关闭和恢复 Dock 的能力。

- [ ] **Step 3: 改造工具栏与属性面板**

工具栏按“文件/视图/分析”分组，主操作保留文字或 tooltip；属性面板使用统一标题、字段间距、输入控件高度和错误提示。

- [ ] **Step 4: 验证浅色主题**

```powershell
python -m pytest tests/test_gui_theme.py tests/test_gui_template.py -q
python -m ruff check src/gui/theme.py src/gui/main_window.py src/gui/toolbars.py
```

Expected: 主题测试和 GUI 冒烟测试通过，Echogram 交互 Signal 不改变。

### Task 3: 抽离 Qt 无关的 Python application service

**Files:**
- Create: `src/application/models.py`
- Create: `src/application/events.py`
- Create: `src/application/services.py`
- Create: `src/gui/application_bridge.py`
- Modify: `src/gui/workers.py`
- Modify: `src/gui/handlers/processing_handlers.py`
- Test: `tests/test_application_services.py`
- Test: `tests/test_application_bridge.py`

- [ ] **Step 1: 定义数据模型**

至少定义以下不可变或明确可变的数据对象：

```python
AnalysisRegion(surface_depth_m: float | None, bottom_sample_indices: object | None)
TaskProgress(name: str, completed: int, total: int, message: str)
DatasetSummary(n_pings: int, n_samples: int, channels: tuple[str, ...])
```

- [ ] **Step 2: 抽离服务接口**

服务接口必须接收 Python 数据对象或 `xarray.Dataset`，不能导入 PySide6：

```python
class AcousticApplicationService:
    def load_files(self, paths, config): ...
    def compute_sv(self, echodata, config): ...
    def remove_noise(self, ds_sv, config, manual_mask=None): ...
    def detect_bottom(self, ds_sv, config): ...
    def detect_schools(self, ds_sv, config): ...
    def integrate(self, ds_sv, config, region): ...
    def export(self, ds_sv, results, config): ...
```

- [ ] **Step 3: 让 PySide6 Worker 只负责线程适配**

Worker 保留 `finished`, `error`, `progress` 等 Signal，但将计算调用转发给 service；service 本身不创建 Qt 对象、不发 Qt Signal。

- [ ] **Step 4: 运行 service 测试**

```powershell
python -m pytest tests/test_application_services.py tests/test_application_bridge.py -q
```

Expected: 不启动 GUI 也能测试主要分析流程。

### Task 4: 评估 QML/Qt Quick 前端

**Files:**
- Create: `qml/MainWindow.qml`
- Create: `qml/components/TopToolbar.qml`
- Create: `qml/components/PropertyPanel.qml`
- Create: `qml/components/RegionPanel.qml`
- Create: `src/gui/qml_bridge.py`
- Test: `tests/test_qml_smoke.py`

- [ ] **Step 1: 只迁移一个垂直切片**

先实现“打开已处理 Dataset → 显示 Echogram → 修改表线/底线 → 显示任务进度”这一条流程，不迁移所有对话框。

- [ ] **Step 2: 定义 QML/Python 边界**

QML 只消费 `QObject` bridge 暴露的模型和命令；不得直接访问 `xarray.Dataset`、NumPy 数组或 echopype 对象。大数组只通过纹理、缩略图或受控的二进制缓冲区传递。

- [ ] **Step 3: 处理 Dock 与 OpenGL 兼容性**

第一版保留 Qt Widgets 外壳或明确实现可拖拽面板；不要在没有基准测试的情况下直接替换 `EchogramRenderer`。若 QML 嵌入导致帧率、焦点或鼠标事件异常，保留混合模式：Widgets 承载 Dock 和 OpenGL，QML 只承载现代化面板。

- [ ] **Step 4: 性能验收**

使用同一份数据比较 PySide6 Widgets 与 QML 原型：启动时间、首次绘制时间、平移/缩放帧率、内存峰值、底线编辑延迟。最低接受标准为：核心 Echogram 操作无明显回退，任务进度和错误状态可见。

### Task 5: 仅在 QML 不满足目标时评估跨栈前端

**Files:**
- Create later: `frontend/`（仅在原型决策通过后）
- Create later: `frontend/src/` React/TypeScript UI
- Create later: `frontend/src-tauri/` Tauri/Rust 壳
- Modify later: `src/application/services.py`
- Test later: `tests/test_ipc_contract.py`

- [ ] **Step 1: 固定 IPC 协议**

协议至少覆盖：数据集摘要、变量选择、视口范围、颜色范围、区域选择、底线编辑、任务进度、错误和导出结果。禁止通过 JSON 传递完整大尺寸 Echogram 数组。

- [ ] **Step 2: 使用本地 Python 服务**

Python 继续负责 echopype 和科学计算；Tauri 前端通过本地 IPC、WebSocket 或 localhost RPC 调用服务。必须定义启动、停止、异常退出和版本兼容行为。

- [ ] **Step 3: 使用 WebGL/WebGPU 原型替换中心画布**

先支持固定数据集的平移、缩放、颜色表和底线显示，再接入真实任务流。未通过性能验收前，不迁移完整 GUI。

- [ ] **Step 4: 迁移决策门槛**

只有同时满足以下条件才允许全面迁移：

- 主要 Echogram 操作性能不低于现有实现的可接受范围。
- Python 后端可独立测试和启动。
- 前后端 IPC 有版本化契约测试。
- Windows 打包、升级、日志和崩溃恢复路径明确。
- 现有 core 测试和 GUI 回归测试全部通过。

### Task 6: 发布与回滚策略

**Files:**
- Modify: `pyproject.toml` 或未来前端对应的构建配置
- Create: `docs/gui-migration-benchmark.md`
- Test: `tests/` 全量测试

- [ ] **Step 1: 保留 PySide6 参考实现**

迁移期间保持旧 GUI 可运行，至少直到新前端完成打开数据、Echogram 交互、分析任务、导出和异常处理验收。

- [ ] **Step 2: 记录性能基准**

基准文件记录数据规模、启动时间、渲染帧率、内存峰值、任务延迟、系统版本和 GPU 信息。

- [ ] **Step 3: 运行完整验证**

```powershell
python -m pytest -q
python -m ruff check src tests
git diff --check
```

- [ ] **Step 4: 只在用户确认后提交或推送**

GUI 迁移阶段产生的模板、实验前端和基准文件默认不自动 commit 或 push；每个阶段单独确认提交范围。

## 4. 验收标准

### 当前 PySide6 阶段

- 主窗口、Dock、工具栏、属性面板和状态栏视觉统一。
- Echogram 缩放、平移、选区、底线和颜色表行为不回归。
- 真实数据处理仍由 Python/e​chopype/xarray 完成。
- 浅色主题在 1440×900 和 1920×1080 下无控件重叠或文字截断。
- `python -m pytest -q` 通过，已有警告单独记录。

### 后续前端迁移阶段

- 前端不直接依赖科学计算对象。
- 后端服务可以脱离 GUI 单独测试。
- 大型 Echogram 数据不通过低效 JSON 全量复制。
- 新旧前端可以在同一数据集上得到一致的分析和导出结果。
- Windows 安装、日志、异常和回滚路径可验证。

## 5. 默认决策

- 当前实现继续使用 PySide6，不立即更换底层语言。
- GUI 美化优先采用 Qt Widgets 主题和组件重构。
- QML/Qt Quick 是第一候选迁移方向。
- TypeScript + Tauri 只作为跨栈备选，不提前创建前端工程。
- C# WinUI/Avalonia 只在明确 Windows 原生或跨平台产品需求后评估。
- 不使用 Electron 或 Flutter 作为当前项目的第一迁移方案。
- 本计划文档和浅色模板暂不提交、暂不推送。
