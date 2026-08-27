# 会话交接文档

> 本文档用于 Codex 桌面端接手。目标：让一个全新上下文的 agent 无需回溯历史会话即可继续本项目。

## 基本信息
- 最后更新：2026-08-26 23:30
- 工作目录：`D:\Administrator\Desktop\echopype`
- 项目：**echopype Echogram** —— 基于 Python + PySide6 + echopype 的 Echoview 风格鱼类声学资源评估 GUI
- 用户：dcc，博士研究生，内陆淡水声学 / 水库鱼类资源精准评估

## 当前进度
- **深色主题视觉重做已完成并推送**（commit `b173af2`）：`theme.py` 重写为真深色主题（背景 `#1e1e22` + 青绿强调 `#00b4d8`），修正了 `DARK_THEME` 原为 `LIGHT_THEME` 别名的问题；`opengl_renderer.py` 的 `glClearColor` 改深灰；`toolbars.py` 用 Qt `StandardPixmap` 图标；`navigation_bar.py` 深色青绿系。
- **合并后噪声去除 KeyError 已修复并推送**（commit `f68656a`）：`merge_aligned()` 重建 Dataset 时保留全部标量校准变量 + per-ping 变量，修复 `KeyError: No variable named 'sound_absorption'`。
- **多文件导入稳定性第一轮已完成（代码在工作树，未提交）**：`MergeFilesWorker` 已移除 `ep.combine_echodata()` 调用，不再保留多文件 `echodata_list`，逐文件收集失败信息并继续合并成功文件；错误通过可滚动消息面板展示。
- **底线与交互已完成**：长底线绘制降采样、底线结果长度/有效点诊断、工具栏 `PAN/手爪平移` 左键拖动；保留中键拖动兼容。
- **参数自动应用已完成**：噪声、底线、鱼群、积分、SED 独立信号和防抖；下游结果标记过期；旧 Worker 完成结果不会覆盖新结果。
- 验证：非真实数据回归 `130 passed, 1 skipped`；改动文件 Ruff 通过；`git diff --check` 和 compileall 通过。真实 GUI 集成测试读取当前 1 个 raw 文件时在 184 秒超时，未完成真实场景验收。

## 待办任务
1. **现场验收 8 个以上真实 `.raw` 文件**：确认批量导入期间 GUI 可操作、失败文件被列出、消息栏可滚动、合并 Echogram 显示、底线显示或给出有效点为零的诊断。
2. **评审工作树未提交的变更**：本会话未 commit/push；需由用户确认后再决定提交。详见下方「工作树未提交变更」。
3. **v3.0 TS 模型反演规划**：Matecho 路线图中唯一尚未开始的项，需单独规划。

## 工作树未提交变更（⚠️ 需评审）
当前工作树混合了此前 WIP 与本会话实现，尚未 commit。接手方需先 `git diff` 评审再决定：

**已修改（tracked）**：
- `src/gui/workers.py` —— ①`apply_manual_mask()` 重写（新增 `Sv_corrected` 兜底、3D mask 广播）；②`MergeFilesWorker` 移除 `combine_echodata`，逐文件容错并返回 `MergeResult`；③底线 Worker 输出有效点诊断。
- `src/core/noise.py`（+167 行，改动较大）、`src/core/acoustic.py`、`src/core/ep_project.py`、`src/core/export.py`、`src/core/integration.py`、`src/gui/handlers/file_handlers.py`、`src/gui/handlers/processing_handlers.py`、`src/gui/handlers/analysis_handlers.py`、`src/gui/main_window.py`、`src/gui/property_panel.py`、`src/gui/toolbars.py`、`src/gui/i18n.py`、`src/viz/opengl_renderer.py`
- `pyproject.toml`、`requirements.txt`（新增 h5py / openpyxl 依赖）

**未跟踪（untracked）**：
- `tests/test_gui_workers.py`（含 `test_merge_worker_skips_raw_echodata_combine_for_multiple_files`，验证多文件不调用 combine_echodata）
- `tests/test_high_priority_fixes.py`、`tests/test_gui_template.py`、`tests/test_gui_error_panel.py`、`tests/test_renderer_interaction.py`、`tests/test_parameter_auto_apply.py`
- `docs/superpowers/plans/2026-08-26-gui-large-raw-stability-and-interaction.md`
- `docs/superpowers/plans/2026-08-25-*.md`、`templates/`
- 散落的 `_err.txt`、`_out.txt`（调试输出，可删除）

## 遇到的坑（经验教训）—— 只增不删

### 坑1：echopype 0.11 导入时静默禁用 INFO 日志
- **现象**：`logger.info` 全部不输出、无报错，但 `print` 正常。
- **原因**：echopype 导入时调用 `logging.disable(30/WARNING)`，全局级别覆盖。
- **解决方案**：`import echopype` 之后立即加 `logging.disable(logging.NOTSET)`。
- **预防**：调试时若 info 日志全无但 print 正常，优先怀疑第三方库劫持 logging。

### 坑2：merge_aligned 重建 Dataset 的硬性要求，缺失即 KeyError
- **现象**：合并后噪声去除报 `KeyError: No variable named 'sound_absorption'`；海底检测 `.sel` 失败。
- **原因**：`merge_aligned()` 早期只保留 Sv/echo_range/depth，丢弃了标量校准变量与 channel 维度字符串。
- **解决方案**（`f68656a`）：复制全部标量变量（`if da.ndim == 0`，如 sound_absorption/sound_speed/frequency_nominal）；per-ping 变量（gain_correction/sa_correction）先按 `sort_idx` 拼接再按 `keep` 过滤；channel 维度保留**原始字符串**（如 `'WBT 401661-15 ES200-7C_ES'`）。
- **预防**：`merge_aligned` 的 Dataset 必须同时满足 echopype 内部 `detect_seafloor` / `compute_Sv` / `remove_background_noise` 的完整变量依赖。

### 坑3：多文件合并禁止 ep.combine_echodata
- **现象**：导入多个 `.raw` 报 `AlignmentError: cannot reindex or align along dimension 'WBT_filter_n' because of conflicting dimension sizes: {23, 95}`。
- **原因**：`ep.combine_echodata()` 合并不同 EK80 文件时，滤波器系数长度不同导致维度冲突。
- **解决方案**：多文件 Sv 合并**只**用 `merge_aligned()`，不调用 `combine_echodata()`；`combine_echodata` 仅用于单文件。
- **预防**：任何跨文件合并场景，先确认是否涉及 EK80 的 `WBT_filter_n` 等长度可变的元数据维度。

### 坑4：GUI 启动方式
- **现象**：`python src/app.py` 报 `ModuleNotFoundError: No module named 'src.gui'`。
- **原因**：`sys.path[0]` 变为 `src/` 而非项目根。
- **解决方案**：必须 `python -m src.app`（从项目根目录运行）。
- **预防**：`start_gui.bat` 已用 `cd /d D:\Administrator\Desktop\echopype` + `python -m src.app`，双击即可；不要改成 `python src/app.py`。

### 坑5：DARK_THEME 曾是 LIGHT_THEME 别名
- **现象**：深色主题实际渲染为浅蓝白。
- **原因**：`theme.py` 中 `DARK_THEME` 定义为 `LIGHT_THEME` 别名。
- **解决方案**：`b173af2` 重写为真深色；`LIGHT_THEME = DARK_THEME` 仅作兼容别名保留。
- **预防**：主题常量别名要检查是否指向同一字典对象。

### 坑6：本机多 Python 环境易混淆
- **现象**：命令行 `python` 可能指向非预期解释器。
- **原因**：本机 7 个独立环境（D:\Python313、D:\Python314 默认、Anaconda base 3.13.5、cowagent、echopype_env、r_env、UV；另有 QGIS 自带 3.12.11）。
- **解决方案**：本项目用 Anaconda base `D:\Program Files\Anaconda\python.exe`（Python 3.13.5）；echopype 0.11.1。
- **预防**：涉及依赖安装/运行前先确认解释器；QGIS 包用 `cmd /c "call "D:\Program Files\QGIS\bin\o4w_env.bat" && python -m pip install 包名"`。

### 坑7：Windows git LF→CRLF 警告
- **现象**：`git add`/`git diff` 大量 `LF will be replaced by CRLF` 警告。
- **原因**：Windows 换行符自动转换。
- **解决方案**：纯外观问题，忽略即可，不影响提交内容。

## 已完成的任务（历史记录）
- GUI 大规模 raw 稳定性、底线诊断/降采样、独立参数自动应用、旧任务隔离和手爪平移 — 2026-08-26，代码已实现但未提交；8 个以上真实 raw 仍待现场验收
- 深色 Echoview 风格主题重做（视觉层 4 文件，功能逻辑未动）— 2026-08-24，commit `b173af2`（已推送 origin/master）
- `merge_aligned` 保留标量校准变量，修复合并后噪声去除 KeyError — 2026-08-24/25，commit `f68656a`（已推送 origin/master）
- 清理 BatchProcessWorker 死代码 + batch i18n 死键（净删 97 行）— commit `ced983b`
- 文件导入重构 + .ep 项目 + 导航滑块 + GUI 清理 — commit `73b2b77`
- 模块重叠去重 + echopype 0.11.1 兼容 — commit `de6f111`

## 关键文件
- `src/core/merge.py`：`merge_aligned()` 多文件 Sv 合并（时间排序 + 深度重采样 + 去重 + channel 维度保留 + 标量校准变量复制）。**多文件合并的唯一入口，勿再引入 combine_echodata。**
- `src/core/acoustic.py`：`process_single_file()` / `compute_sv()` 产出 26 个 data_vars（sound_absorption 标量、echo_range/depth、gain_correction/sa_correction per-ping、source_filenames）。
- `src/core/noise.py`：噪声去除（依赖 merge_aligned 保留的标量校准变量）。
- `src/gui/workers.py`：`MergeFilesWorker`（导入/合并线程）、`apply_manual_mask`（写 `Sv_corrected` 不覆盖原始 Sv）。
- `src/gui/theme.py`：深色主题（`#1e1e22` + `#00b4d8`）。
- `src/viz/opengl_renderer.py`：`glClearColor(0.12,0.12,0.14,1.0)` 深灰背景。
- `src/gui/toolbars.py`、`src/gui/navigation_bar.py`：深色图标/导航栏。
- `start_gui.bat`：双击启动脚本（gitignored，ASCII 无 BOM）。

## 相关资源
- echopype 版本：0.11.1（内部 API `detect_seafloor` / `compute_Sv` / `remove_background_noise` 对 Dataset 结构有硬性依赖）
- `.ep` 项目文件：HDF5 格式（~12KB），支持新建/打开，保存导入的 Sv 合并结果
- 当前验证基线：非真实数据回归 `130 passed, 1 skipped`；真实 `.raw` GUI 集成测试在 184 秒超时，需现场数据继续验收。
- 待规划路线：Matecho v3.0 TS 模型反演（唯一未开始项）
