# Canvas-first GUI visual QA

## Comparison target

- Source visual truth: `C:\Users\Administrator\.codex\generated_images\01a04875-0892-7572-bcf0-55e361f09fdf\exec-31a85648-3d54-4ca6-984b-4434f7401133.png`
- Implementation capture: Windows Computer Use `screenshot-0` (ephemeral capture; no local file was produced by the capture service)
- Source viewport: desktop mockup, approximately 1440 × 1024 CSS px.
- Implementation viewport: 1402 × 864 logical px at the system display scale.
- State: empty project, welcome overlay visible. The source uses illustrative echogram data behind the overlay; the implementation intentionally preserves the product requirement that no data is shown until the user imports a file.
- Normalization: compared the shared desktop-app content frame and the focused toolbar, navigation, property, and welcome-overlay regions rather than browser or OS chrome.

## Full-view comparison

The implementation now follows the source's dark canvas-first workbench structure: text-plus-icon project actions lead the toolbar, the left dock is organized as project / view / channel context, the center remains the primary canvas, and the right dock exposes display and bottom-detection controls. The focused welcome panel has the same two primary entry actions and compact recent-project region.

## Focused-region comparison

- Toolbar: implementation has visible `导入数据`, `打开项目`, and `导出` actions with local SVG icons. Canvas tools remain compact to preserve editing space.
- Left context: implementation adds project state, `Surface` view selection, and a channel list. No channel is fabricated before import.
- Right context: implementation exposes file, display, bottom-detection, annotation, and statistics sections; controls use real existing widgets.
- Welcome overlay: implementation uses a compact dark panel with `导入 .raw` and `打开项目`, plus the existing recent-project behavior.

## Required fidelity surfaces

- Fonts and typography: retained the application's Segoe UI / Microsoft YaHei UI stack; added a clearer welcome heading and preserved compact scientific-tool labels.
- Spacing and layout rhythm: toolbars, docks, and the welcome panel use the existing 4–8 px rhythm, with a centered 440 px entry panel and no nested-card layout.
- Colors and visual tokens: retained the established graphite base, slate borders, and cyan primary/selected state; new selectors reuse existing theme tokens.
- Image quality and assets: all visible controls retain the existing local SVG icon registry. No generated, inline, or handcrafted artwork was introduced.
- Copy and content: project actions now read `导入数据`, `打开项目`, and `导出`; empty state remains truthful rather than showing mock measurements or echo data.

## Findings

- [P3] The reference mockup's data-loaded echogram state cannot be shown truthfully in the empty-project window. This is an intentional product constraint; after a real import, the existing renderer supplies the echogram rather than a synthetic placeholder.
- [P3] The reference has a more abbreviated bottom status strip, while the implementation keeps the real region/message pane visible for existing workflows.

## Comparison history

1. Initial implementation capture showed icon-only project actions. Fixed by changing the project toolbar to text-plus-icon actions and wiring `打开项目` to the actual project-open command.
2. Final capture confirmed the updated toolbar, contextual docks, and welcome overlay at the same empty-project state.

## Implementation checklist

- [x] Implement the selected canvas-first workbench hierarchy.
- [x] Preserve real import/open interactions and data-dependent rendering.
- [x] Add regression coverage for toolbar, navigation, property context, and welcome controls.
- [x] Capture the desktop application and compare it with the selected visual.

final result: passed

## 2026-09-15：浅色工作台收尾检查

本节对应当前 `DESIGN.md` 的浅色仪器风；上文深色参考记录仅供追溯。

- 工具图标、独立色标和导航条使用主题颜色；当前鼠标工具显示选中态，空项目禁用操作使用灰色。
- 左侧采用两列快捷操作、文件名中间省略及完整路径提示；右侧五个短任务标题保留完整名称提示。
- 处理表单长行换行；恢复信息页中被隐藏容器移走的文件信息；积分预览前移并设为只读。
- 主窗口允许缩小至 1200×760，默认仍为 1400×900；实际检查了 1280×800 空项目和真实数据、1440×940 处理页，以及英文信息页。中英文 360px 属性栏均无页面横向溢出，数据表自身仍可横向滚动读取所有列。
- Windows OpenGL 实际渲染使用现有真实 RAW 的 `Sv.nc` 缓存；未改声学计算或数据色阶编码。本轮没有重跑 RAW 校准/科学对照。
- 验证：默认测试 302 通过、39 跳过，Ruff 与语法检查通过。仍有三条既有 Qt 鼠标事件弃用警告；英文模式部分既有菜单和分析摘要仍为中文，本轮没有完成全应用翻译。
- 临时截图查看后清理，不作为正式资产或持续视觉基线。
