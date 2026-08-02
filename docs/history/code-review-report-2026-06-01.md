# echopype 项目代码审查与修改报告

**日期**: 2026-06-01
**依据**: echopype 官方文档 https://echopype.readthedocs.io/en/latest/
**审查范围**: `src/` 全部模块 + `configs/` + `tests/`

---

## 一、审查方法

1. 浏览 echopype 官方文档首页、API 参考、数据处理功能页面
2. 逐项对比项目代码与官方 API 的函数签名、参数、返回值
3. 验证工作流是否符合 echopype 设计哲学（EchoData → xr.Dataset）

---

## 二、发现的问题与修改依据

### 问题 1: combine_echodata 类型错误 [严重]

**文件**: `src/acoustic.py`
**官方 API**:
```
echopype.combine_echodata(echodata_list: List[EchoData], ...) → EchoData
```
**原代码**:
```python
datasets = []
for raw_file in raw_files:
    ds = process_single_file(raw_file, config)  # 返回 xr.Dataset
    datasets.append(ds)
combined = ep.combine_echodata(datasets)  # 传入 Dataset 列表 — 类型错误
```
**问题**: `combine_echodata` 要求 `EchoData` 对象列表，原代码传入的是 `xr.Dataset` 列表（Sv 校准后的结果）。
**修改**: 分离 `open_single_file`（返回 EchoData）和 `process_single_file`（接收 EchoData），在 `process_all_files` 中先合并 EchoData 再校准。
**文档来源**: API reference — `combine_echodata(echodata_list: List[EchoData] = None, ...)`

---

### 问题 2: 噪声去除结果未被使用 [严重]

**文件**: `src/acoustic.py`
**官方 API**:
```
echopype.clean.remove_background_noise(ds_Sv, ping_num, range_sample_num, ...) → Dataset
# 返回新增 Sv_corrected 和 Sv_noise，不修改原始 Sv
```
**原代码**:
```python
ds_Sv = remove_background_noise(ds_Sv, ...)
# 后续仍使用 ds_Sv["Sv"]（原始未校正数据）
```
**问题**: 函数返回的 Dataset 中 `Sv_corrected` 是校正后的数据，但代码继续使用原始 `Sv`，噪声去除完全无效。
**修改**: 添加 `ds_Sv["Sv"] = ds_Sv["Sv_corrected"]`
**文档来源**: API reference — "Returns: The input dataset with additional variables, including the corrected Sv (Sv_corrected) and the noise estimates (Sv_noise)"

---

### 问题 3: depth 变量未正确计算 [重要]

**文件**: `src/acoustic.py`
**官方 API**:
```
echopype.consolidate.add_depth(ds, echodata=None, depth_offset=None,
    use_platform_vertical_offsets=False, ...) → Dataset
```
**原代码**:
```python
if "depth" not in ds_Sv and "echo_range" in ds_Sv:
    ds_Sv["depth"] = ds_Sv["echo_range"]  # 直接复制 echo_range，未加换能器深度
```
**问题**:
- `echo_range` 是从换能器表面到目标的距离，不是水深
- 两个 if/else 分支代码完全相同
- 未利用 Platform group 中的换能器深度信息
**修改**: 使用 `add_depth(ds_Sv, echodata=echodata, use_platform_vertical_offsets=True)`
**文档来源**: API reference — "Create a depth data variable based on data in Sv dataset, EchoData object... use_platform_vertical_offsets: If True, use Echodata Platform group vertical offset values to compute transducer depth"

---

### 问题 4: 绕过公共 API 加载内部模块 [重要]

**文件**: `src/school.py`
**官方 API**:
```
echopype.mask.detect_shoal(ds, method, params) → DataArray
```
**原代码**:
```python
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "shoal_echoview",
    _ep_root / "mask" / "shoal_detection" / "shoal_echoview.py",
)
```
**问题**: 绕过 echopype 公共 API 直接加载内部模块，路径可能随版本变化，跳过参数验证。
**修改**: 改用 `from echopype.mask import detect_shoal`
**文档来源**: API reference — "detect_shoal(ds, method, params): Detect shoals using the selected method and return a 2D boolean mask"

---

### 问题 5: encode_mode 配置不一致 [重要]

**文件**: `configs/test.yaml` vs `src/acoustic.py` vs `tests/test_integration.py`
**官方说明**:
```
EK80 narrowband (CW) mode:
  - encode_mode="complex" → 复数采样
  - encode_mode="power"   → 功率/角度采样（等同 EK60 格式）
```
**原配置**: `test.yaml` 写 `"complex"`，代码默认 `"power"`，测试用 `"power"` — 三处不一致。
**修改**: 统一为 `"power"`，并在配置中添加 `sonar_model: "EK80"`
**文档来源**: Data processing functionalities — "If the data is stored as power/angle samples... use encode_mode='power'"

---

### 问题 6: NASC → ABC [用户需求]

**文件**: `src/density.py`
**说明**:
```
NASC (s_A) = 4π × 1852² × ∫Sv_linear×dz   [m²/nmi²]  — 海里单位
ABC  (s_a) = 4π ×        ∫Sv_linear×dz    [m²/m²]     — 国际单位
```
**用户要求**: 使用 ABC 而非 NASC
**修改**: 移除 1852² 转换因子，函数重命名 `calculate_nasc` → `calculate_abc`，输出列名 `nasc` → `abc`

---

### 问题 7: 其他 minor 问题

| 问题 | 文件 | 修改 |
|------|------|------|
| 重复导入 numpy | `school.py` | 移除第 89 行重复导入 |
| sonar_model 硬编码 | `acoustic.py` + `configs/test.yaml` | 从配置读取，配置中添加字段 |
| 3D Sv 未降维 | `school.py` | 添加 `if Sv.ndim == 3: Sv = Sv[0]` |
| unused numpy import | `acoustic.py` | 移除未使用的 `import numpy` |

---

## 三、修改后的工作流

```
open_raw(sonar_model=配置值)
    → EchoData
combine_echodata(echodata_list=[...])
    → 合并的 EchoData
compute_Sv(waveform_mode, encode_mode)
    → xr.Dataset (含 Sv, echo_range)
remove_background_noise(ping_num, range_sample_num, SNR_threshold)
    → 新增 Sv_corrected, Sv_noise
    → ds_Sv["Sv"] = ds_Sv["Sv_corrected"]
add_depth(echodata=..., use_platform_vertical_offsets=True)
    → 新增 depth
detect_seafloor(method, params)
    → 新增 bottom_depth
detect_shoal(method, params)           [公共 API]
    → 2D 布尔 mask
schools_to_dataframe(mask)
    → 鱼群清单 DataFrame
calculate_abc(ds_Sv)
    → ABC [m²/m²]
estimate_density(schools_df, ds_Sv)
    → 密度 [ind/m², ind/ha]
```

---

## 四、涉及的文件清单

| 文件 | 修改类型 |
|------|----------|
| `src/acoustic.py` | 重写 — 修复问题 1, 2, 3, 7 |
| `src/school.py` | 重写 — 修复问题 4, 7 |
| `src/density.py` | 重写 — 修复问题 6 |
| `configs/test.yaml` | 修改 — 修复问题 5 |
| `tests/test_density.py` | 修改 — 适配 ABC |
| `tests/test_integration.py` | 修改 — 添加 sonar_model |
| `src/viz.py` | 无修改 |
| `src/utils.py` | 无修改 |
| `src/cli.py` | 无修改（接口兼容） |
