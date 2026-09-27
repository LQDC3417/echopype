# DESIGN.md — Echogram（fish-acoustics 桌面工作台）

Brand-side 规范：约束本产品后续任何 GUI 改动、对话框、工具栏与文档配图。实现栈是 **PySide6 + OpenGL**，不是 Web。

## 1. Objective

让人一眼感觉这是一台**可信的科研仪器**（ESP3 / MATLAB 工作台气质）：浅色中性面板、信息密度高、声图是主角、控件像实验台旋钮而不是营销按钮。质量线是「现场长时间分析也不烦」——状态清晰、层级可扫读、操作有反馈；不是「截图好看」。**实现栈仍是 PySide6 + OpenGL；本规范只约束视觉与信息架构，不换前端框架。**

## 2. Product Context

- **产品一句话：** 读 EK80 等 raw，算 Sv，做底线/鱼群/积分/密度，导出可复核结果。
- **主用户：** 内陆淡水 / 水库声学评估的研究生与科研人员；在 Windows 上长时间盯声图，习惯 Echoview 心智，中文界面为主。
- **相邻感：** NIWA **ESP3**（Layer 树 + 左/右密集参数 + Apply to layer）、MATLAB 科学桌面、Echoview 信息密度。
- **疏远感：** 企业 SaaS 营销站、Notion 式卡片墙、深色「极客皮肤」若与声图抢对比。
- **文化语域：** technical / serious。可冷静，不可俏皮。
- **信息架构（已选定）：** ESP3 范式 —— 左 Layer 树 · 中声图常驻 · 右任务页签（Processing / Echo Integration / Lines / Display）· **Apply to current / all layers**。不要 1–5 向导按钮墙。

## 3. Visual Foundations

### 3a. Color（以 `src/gui/theme.py` 为唯一真源；**浅色仪器风 v2**）

| Token | 值 | 用途 |
|-------|-----|------|
| `--bg-app` | `#E8EAED` | 主窗口底（MATLAB 灰） |
| `--bg-panel` | `#F5F6F7` | Dock / 工具栏 / 菜单面板 |
| `--bg-field` | `#FFFFFF` | 输入框、表格、列表底 |
| `--bg-plot` | `#FFFFFF` | 声图画布底（与 chrome 区分） |
| `--bg-raised` | `#DDE2E7` | hover / 选中行 / 按下 |
| `--border` | `#C5CAD0` | 常规描边、分隔 |
| `--border-strong` | `#9AA3AD` | 强调分隔、Dock 边界 |
| `--text-primary` | `#1F2933` | 正文 |
| `--text-secondary` | `#5C6773` | 次级标签、轴注 |
| `--text-disabled` | `#9AA3AD` | 禁用 |
| `--accent` | `#0B6E99` | 选中、焦点、当前工具、主按钮（科学蓝，非消费青） |
| `--accent-soft` | `#E3F2F8` | 选中行浅底、focus 背景 |
| `--error` | `#B42318` | 失败 / 危险 |
| `--warning` | `#B54708` | 过期 / 可恢复警告 |
| `--ok` | `#067647` | 成功（少用） |

**用色规则：**

- **声图是唯一高饱和区**（Sv 色标）；chrome 全部中性浅色，避免和数据抢眼。
- `--accent` 编码状态（当前层、当前工具、焦点、Apply）；**不做大面积品牌底**。
- 一屏内实心 Primary ≤1（通常 = Apply to current layer / 导入）。
- 表格用细线分隔 + 白底，不用卡片阴影墙。
- OpenGL `glClearColor` 与 `--bg-plot` 一致（白或近白），轴与色标用 `--text-secondary`。

### 3b. Typography

- **UI：** `"Microsoft YaHei UI", "Microsoft YaHei", "Noto Sans CJK SC", "Segoe UI", sans-serif`
- **数据/坐标：** 等宽或 YaHei 紧凑字号；声图轴标签、dB、m、时间戳优先 tabular 对齐感。
- **字号刻度：** `10 / 11 / 12 / 13 / 14 / 16`（Qt px）。默认正文 **12**；面板标题 13–14；状态栏 11。
- **字重：** 仅 Regular / Bold。禁止同一面板内连续三级 Bold。
- **不引入** 外部 Web 字体（离线科研机）。

### 3c. Spacing & rhythm

- **基单位 4px。** 常用：`2 / 4 / 8 / 12 / 16 / 24`。
- **密度默认：Comfortable Compact** —— 比消费 App 紧，比 Echoview 2000s 皮肤松。
  - 工具按钮触达区 ≥ 28×28
  - 属性表行高 ≥ 28
  - Dock 内边距 8；组间距 12
- **「留白」在此产品 = 视觉噪声低**，不是大片空场。声图四周只留够坐标与图例。

### 3d. Component seeds

- **Button：** 三档 — Tool（图标方钮，toggle 表示模式）、Ghost（次要操作）、Primary（实心 accent，每屏 ≤1）。
- **容器 / Dock：** 直角或 2–4px 圆角；**无投影卡片**；1px 中性边框；面板底 `--bg-panel`，内容区可白底。
- **图标：** 单色线性或 Qt StandardPixmap（深灰）；必须有 tooltip。
- **空状态：** Layer 树写「导入 .raw / 打开 .ep」；声图区可留白 + 状态栏提示。
- **Apply：** 右栏任务页唯一 Primary =「应用到当前 Layer」；「应用到全部」用 Ghost。

## 4. Accessibility

- 正文对 chrome 对比 ≥ 4.5:1（`#1F2933` on `#F5F6F7`）；关键 UI ≥ 3:1。
- 焦点：2px `--accent` 描边或 `--accent-soft` 底 + 边框，键盘可见。
- 动效：仅状态切换 100–150ms；无循环装饰动画。
- 图标钮必有 tooltip；危险操作需确认文案写清后果。
- 色盲：UI 状态不能只靠红绿；需同时有文案/图标。

## 5. Voice & Tone

- **语域：** 技术、克制、中文优先；英文仅作单位/算法名（Sv、NASC、EDSU）。
- **句式：** 短句。按钮用动词短语（「检测底部」「计算密度」）。
- **使用词：** 计算、校准、检测、导出、分析区域、过期、已合并。
- **禁用词：** 一键搞定、智能赋能、魔法、极速体验、探索无限、（无意义的）卓越/流畅/无缝。
- **称呼：** 对用户用「你」或省略主语；不写「尊敬的用户」。
- **错误文案：** 发生了什么 + 可能原因 + 下一步（可滚动消息面板已存在，文案需可读）。

## 6. Implementation Practices

- **Token 真源：** `src/gui/theme.py` 的 Qt StyleSheet。浅色仪器 token 见 §3a；**禁止**在 handler/对话框散落 hex。
- **兼容别名：** `LIGHT_THEME` 应指向当前真源；禁止再把 `DARK_THEME` 当别名反用。
- **布局（ESP3 IA）：** 左 = Layer 树（调查/文件/声道/线）；中 = OpenGL 声图；右 = 任务页签（Processing / Echo Integration / Lines / Display）+ 密集表单 + Apply；底 = 区域/消息。声图始终可见。
- **i18n：** 可见文案走 `T()`，zh/en 成对。
- **图标：** `src/gui/assets/icons/*.svg`。
- **数据色标：** Sv colormap 可配；chrome 不随色标漂移；绘图区 `glClearColor` 用白/近白。
- **栈：** Widgets + QSS，不引入 Web/QML。

## 7. Anti-Patterns

- **No 营销卡片墙 / 1–5 向导按钮墙。** 流程入口 = Layer 树 + 右栏任务页。
- **No 全员 Primary。** 每屏 ≤1 实心按钮。
- **No 深色「极客皮肤」残留。** 浅色仪器风选定后，禁止混用旧 `#00b4d8` 深色块作大面积 chrome。
- **No 散落第二套中性色。** 不用 slate `#4a5568`/`#94a3b8` 等绕过 token。
- **No 覆盖原始 Sv 的「美化」操作。**
- **No 无 tooltip 纯图标。**
- **No 空状态只写「暂无数据」。** 必须指回导入/打开。

## 8. Decision-Making（冲突时优先级）

1. **科学可信与数据不被 UI 语义污染**（原始 Sv、单位、坐标系）。
2. **当前状态可读**（加载中 / 过期 / 失败 / 空）——90% 时间的状态优先于「完成态截图」。
3. **高频路径一步可达**（导入 → Sv → 底线 → 鱼群 → 积分）。
4. **与 Echoview/Matecho 操作直觉兼容**（底线手绘、缩放平移、区域裁剪）。
5. **视觉克制与主题一致**（改 chrome 不改数据编码）。
6. **实现成本**（QSS 可达；不为美观引入重架构）。

## 9. Workflow（改 UI 时）

1. 读本文件 + `AGENTS.md` 不变量（Sv_corrected、merge 等）。
2. 定位真源：主题 `theme.py`，布局 `main_window.py`，逻辑 `gui/handlers/*`，线程 `workers.py`。
3. 先改状态与信息层级，再改像素；默认测试 `python -m pytest -q`。
4. GUI 改动补/跑 offscreen 测试；涉及视觉基线时更新对应 test 或截图说明局限（OpenGL 离屏无法验收）。
5. 文案进 i18n；图标进 assets；不新增第二套色。
6. 跑 ruff + pytest；记录与本 DESIGN 的偏离及理由（Decision Trace）。
7. 大改布局/交互先更新本文件 Structure 段，再实现。
