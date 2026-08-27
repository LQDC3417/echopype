# Echoview 场景化 GUI 与处理流程改造计划

## 目标与边界

在现有 PySide6、OpenGL Renderer、Worker 和声学算法上作最小改造，使用本项目轻量 `.ep`，不支持 Echoview `.ev`。不处理主工作区已有历史文档删除或未跟踪 WIP；不自动 commit 或 push。

## 实施步骤

1. **建立领域模型：`LineDefinition`、`LineManager`、`AnalysisRegion`。**
   - 固定 `Zero`，默认 `Surface = Zero + 2 m`，检测生成 `Bottom`；支持稳定 ID、引用、偏移、显隐、颜色、手工数据和时间。
   - 派生线随基准更新；首次绘制转换为手工线；校验名称、循环、删除引用和 ping 时间重索引。
   - 验证：`tests/test_line_model.py`。

2. **扩展 `.ep` 到 1.1，并兼容 1.0。**
   - 保存全部线、分析区域及显示设置；保持 raw 路径引用而不嵌入 Sv。
   - 读取旧 `surface_depth` / `bottom_line` 时迁移到通用线，并保留旧字段写入。
   - 验证：`tests/test_ep_project.py`。

3. **实现区域掩膜语义。**
   - 使用任意上下边界线生成区域；缺失、交叉或越界 ping 整条排除；线或区域变动时清除缓存。
   - 验证：`tests/test_analysis_region.py`。

4. **更新 Renderer 与 GUI 交互。**
   - 同时渲染多线，支持选线、铅笔绘制、逐线撤销/重做与兼容 surface/bottom 包装。
   - 新增欢迎对话框、线段管理/底线检测、分析区域和图例显示设置对话框；删除顶部颜色范围控件；属性 Dock 仅显示文件信息与统计。
   - 验证：`tests/test_gui_workflow.py`、`tests/test_renderer_interaction.py`。

5. **重构菜单与参数执行。**
   - 顶部与右键共享“数据”菜单：噪声、鱼群、积分、SED；参数通过 Apply/OK/Cancel 弹窗执行，移除统一运行入口。
   - 四项处理均尊重区域：噪声仅替换区域内数据，其他处理消费区域数据或过滤结果。
   - 验证：`tests/test_processing_dialogs.py` 及相关后端测试。

6. **实现多文件 SED 调度。**
   - 逐 raw 处理并映射全局 ping；禁止 `combine_echodata()`；保存来源文件与本地 ping，部分失败可继续。
   - 验证：mock raw 的多文件 SED 测试。

7. **回归和验收。**
   - 执行计划规定的定向测试、全量测试、Ruff 和 `git diff --check`；逐条核对需求。

## 固定交互约定

- 一个项目只存一个当前分析区域；上边界为“所选线以下”、下边界为“所选线以上”。
- 线颜色自动分配并随项目保存，本轮不提供颜色编辑器。
- 图例支持 `jet`、`viridis`、`inferno`、`gray`，并要求 `vmin < vmax`。
- Apply 保持弹窗，OK 应用未执行改动后关闭，Cancel 仅放弃未应用改动。
