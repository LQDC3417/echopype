# AGENTS.md

Echogram GUI：基于 echopype 0.11.x 的 EK80 淡水鱼类声学评估桌面程序（PySide6 + OpenGL）。
目录名是 `echopype`，但 **不是** 上游 [OSOceanAcoustics/echopype](https://github.com/OSOceanAcoustics/echopype) 库本体；本仓库的包名是 `fish-acoustics`，代码一律以 `src.*` 导入。

## 命令

必须在**项目根目录**运行。本机有多套 Python，项目约定解释器：

```powershell
& "D:\Program Files\Anaconda\python.exe"   # Python 3.13.5 + echopype 0.11.1
```

| 用途 | 命令 |
|------|------|
| 启动 GUI | `python -m src.app` |
| 默认测试 | `python -m pytest -q` |
| 真实数据测试 | `python -m pytest --run-real-data -q` |
| 单测/单文件 | `python -m pytest tests/test_merge.py::test_name -q` |
| Lint | `python -m ruff check src tests`（line-length 100） |
| 语法检查 | `python -m compileall -q src tests` |

提交前常用顺序：`ruff` → `compileall` → `pytest -q` → `git diff --check`。

**不要**用 `python src/app.py`：会把 `sys.path[0]` 变成 `src/`，触发 `ModuleNotFoundError: No module named 'src.gui'`。

## 架构（改动前先认清边界）

```
raw/.ep 项目
   → src/core/acoustic.py   open_raw / compute_Sv
   → src/core/merge.py      merge_aligned() 多文件时间对齐 + 深度重采样
   → 噪声 / 底线 / 鱼群 / 积分 / SED / 导出
   → src/gui/  交互与状态；长任务在 src/gui/workers.py 的 QThread 里
   → src/viz/opengl_renderer.py  声图绘制
```

- `MainWindow`（`src/gui/main_window.py`）通过 Mixin 拆分逻辑：`src/gui/handlers/` 下的 `FileMixin` / `ProcessingMixin` / `AnalysisMixin` / `InteractionMixin`。改 GUI 行为优先找对应 handler，不要在 `main_window.py` 里无脑堆代码。
- 统一去噪入口是 `src/core/processing.py::remove_noise()`（调 echopype）；`src/core/noise.py` 里还有遗留实现，GUI 主路径已不依赖它。
- UI 文案走 `src/gui/i18n.py` 的 `T("key")`，新字符串要同时补 `zh` / `en`。
- 主题当前为浅色（`LIGHT_THEME`）；`DARK_THEME` 是兼容旧导入名的别名，不要把它当作另一套深色主题。
- `.ep` 项目文件是 HDF5，存 raw 路径/校验和/配置/线与 mask；重开会校验 raw 是否仍在且校验和一致。

## 硬性不变量（违反会踩历史坑）

1. **原始 `Sv` 永不覆盖。** 去噪/手动 mask 写入 `Sv_corrected`；下游（底部、鱼群、积分、显示）优先读 `Sv_corrected`，否则回退 `Sv`。
2. **多文件合并只用 `merge_aligned()`**（`src/core/merge.py`）。禁止对多文件调用 `ep.combine_echodata()`——EK80 的 `WBT_filter_n` 等元数据维度长度不一致会 `AlignmentError`。`combine_echodata` 仅适合单文件。
3. **`merge_aligned` 重建 Dataset 时必须保留：** 标量校准变量（`sound_absorption`、`sound_speed`、`frequency_nominal` 等）、per-ping 变量（`gain_correction`/`sa_correction`）、以及 **原始字符串** 的 `channel` 维度标签。丢变量会在后续 `detect_seafloor` / `remove_background_noise` 处 `KeyError`。
4. **声学平均在 dB 域是错的**：积分/ABC/密度先转线性域再平均/求和（见 `src/core/integration.py`、`src/core/utils.py::sv_to_linear`）。
5. **分析区域裁剪**同时作用于 `Sv` 与 `Sv_corrected`（`src/core/region.py`），避免显示与计算读到不同变量。

## 测试

- `tests/conftest.py`：`--run-real-data` 选项 + `@pytest.mark.real_data` 自动 skip。默认套件**不**读本地 raw。
- GUI 测试普遍 `os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")`，并复用 `QApplication.instance() or QApplication([])` 单例；不要新建第二个 QApplication。
- 本地真实样本：`raw_data/20250706SCSK-D20250706-T024009.raw`（约 178MB）。完整 `--run-real-data` 曾到 300+ 用例 / 约 90s；大文件导入不要写进默认测试。
- 根目录的 `test_*.py` 调试脚本已 gitignore，不要把临时验证脚本丢在仓库根再提交；正式用例放 `tests/`。
- 不要硬编码「N passed」当验收标准——通过数会随 `--run-real-data` 与本地数据变化。

## 环境与编码

- GUI 入口会设 `os.environ["PYTHONUTF8"] = "1"`，避免 Windows 中文环境 YAML/日志乱码。
- 依赖以 `pyproject.toml` 为准（`requirements.txt` 是镜像清单）。新增包两者一起改。
- PyInstaller 配置在 `echopype.spec`；打包时必须带上 `src/gui/assets` 的 SVG 图标。
- echopype 导入可能压制全局 logging（`logging.disable`）。若 `logger.info` 全无而 `print` 正常，优先怀疑第三方库劫持 logging。
- Windows 上 `LF will be replaced by CRLF` 警告可忽略，不影响提交内容。

## 文档地图（按可信度）

| 文件 | 用途 |
|------|------|
| `docs/requirements-current.md` | 由代码反推的当前实现边界，改功能前先读 |
| `docs/review-2026-09-05.md` | 最近一次全项目审查：已修问题 + 仍待科学验收的缺口 |
| `docs/superpowers/plans/` | 历次改动计划（含具体验证命令） |
| `HANDOFF.md` | 会话交接；**时间戳较旧**，进度以 `git log` / 最新 review 为准 |
| `README.md` | 安装与使用；结构描述可能滞后，以 `src/` 实际布局为准 |

当前 `src/` 比 README 的目录树更新（例如 handlers 子包、`merge.py`/`processing.py`/`sed.py` 等），不要按 README 猜文件是否还存在。
