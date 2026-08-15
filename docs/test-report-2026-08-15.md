# Echogram GUI 真实数据测试报告

**测试日期**: 2026-08-15  
**测试数据**: `raw_data/20250706SCSK-D20250706-T024009.raw` (170MB, SCSK 水库)  
**测试环境**: Windows 11, Python 3.13, echopype

---

## 一、测试概览

| 步骤 | 功能 | 结果 | 耗时 |
|------|------|------|------|
| 1 | 数据加载 | ✅ 通过 | 2.7s |
| 2 | Sv 计算 | ✅ 通过 | 4.0s |
| 3 | 质量检查 | ✅ 通过 | <0.1s |
| 4 | 底部检测 | ✅ 通过 | 已有数据 |
| 5 | 鱼群检测 | ⚠️ 部分通过 | 0.4s |
| 6 | 多频分析 | ✅ 通过 (仅1通道) | <0.1s |
| 7 | GUI 启动 | ✅ 通过 | 5s |

---

## 二、数据概况

| 指标 | 值 |
|------|-----|
| 声呐型号 | EK80 |
| 通道数 | 1 (WBT 401661-15 ES200-7C_ES, 200kHz) |
| Ping 数 | 225 |
| 采样点数 | 33132 |
| Sv 范围 | [-163.1, 6.7] dB |
| NaN 比例 | 91.0% |
| 底部深度 | [11.6, 21.5] 米 |
| 鱼群像素 | 124,179 个 |
| 鱼群数量 | 23 个 |

---

## 三、发现的问题

### 🔴 Bug 1: 鱼群面积计算为 0（严重）

**现象**: 所有 23 个鱼群的 `area` 字段都是 0.0

**根因**: `shoal_extraction.py` 中深度分辨率计算错误

```python
# 当前代码 (line 359)
depth_res = float(np.median(np.abs(np.diff(depth))))

# 问题: 深度数组有 26174/33132 个重复值（EK80 数据填充）
# 导致 np.median 返回 0.0
```

**修复建议**:
```python
diffs = np.abs(np.diff(depth))
non_zero_diffs = diffs[diffs > 0]
depth_res = float(np.median(non_zero_diffs)) if len(non_zero_diffs) > 0 else 0.1
```

**影响**: 网格分析、密度估算中的面积相关计算全部失效

---

### 🟡 Bug 2: 配置与代码不一致（中等）

**现象**: `configs/example.yaml` 中 `school_detection.method: "advanced"`，但 `school.py` 只支持 `"echoview"`

**根因**: 有两个鱼群检测入口：
- `school.py:detect_schools` — 只支持 "echoview"
- `shoal_extraction.py:extract_shoals` — 支持 "echoview" 和 "advanced"

**影响**: GUI 中直接调用 `detect_schools` 会报错 `ValueError: 不支持的鱼群检测方法: advanced`

**修复建议**: GUI 的 Workers 应使用 `extract_shoals` 统一接口，或在 `school.py` 中添加 "advanced" 方法路由

---

### 🟡 Bug 3: quality.py 中 Sv 范围不一致（中等）

**现象**: 
- 实际 Sv 范围: [-163.1, 6.7] dB
- 质量检查报告: [-80.2, 6.7] dB

**根因**: `check_sv_quality()` 使用 `get_sv_array(ds_Sv)` 可能返回的是 `Sv_corrected` 而非 `Sv`，导致范围不同

**影响**: 质量检查报告的 Sv 范围与实际不符，可能误导用户

---

### 🟡 Bug 4: 高 NaN 比例未触发警告（中等）

**现象**: NaN 比例 91.0%，但质量检查返回 `valid: True`，无警告

**根因**: 质量检查阈值为 98%，91% 未触发。但对于真实数据，91% 的 NaN 比例已经非常高

**影响**: 用户可能误以为数据质量良好

**建议**: 考虑添加分级警告（如 >80% 为黄色警告，>95% 为红色错误）

---

### 🔵 Issue 5: EchoData 清理错误（低）

**现象**: 程序退出时出现 `ModuleNotFoundError: import of xarray.core.formatting halted`

**根因**: echopype 的 `EchoData.__del__()` 在 Python 退出时尝试清理临时文件，但 xarray 模块已被卸载

**影响**: 不影响功能，仅影响退出时的错误输出

---

### 🔵 Issue 6: 仅 1 通道，多频分析无意义（信息）

**现象**: 测试数据只有 1 个通道 (200kHz)，多频分析无法进行频率对比

**影响**: 多频分析功能无法在此数据集上验证

**建议**: 需要多通道数据（如 38kHz + 120kHz + 200kHz）来测试多频功能

---

## 四、性能数据

| 操作 | 耗时 | 备注 |
|------|------|------|
| 文件加载 | 2.7s | 170MB raw 文件 |
| Sv 计算 | 4.0s | 含噪声去除 + 底部检测 |
| 鱼群检测 | 0.4s | advanced 方法，225 pings × 33132 samples |
| GUI 启动 | ~5s | 含 OpenGL 初始化 |

---

## 五、修复优先级

| 优先级 | 问题 | 预计工作量 |
|--------|------|-----------|
| P0 | Bug 1: 鱼群面积计算为 0 | 小（修改 1 行代码） |
| P1 | Bug 2: 配置与代码不一致 | 中（统一接口或添加路由） |
| P1 | Bug 3: Sv 范围不一致 | 小（检查 get_sv_array 逻辑） |
| P2 | Bug 4: NaN 警告阈值 | 小（调整阈值或添加分级） |
| P3 | Issue 5: 清理错误 | 无（echopype 上游问题） |

---

## 六、结论

核心数据处理流程（加载 → Sv → 底部检测）工作正常。主要问题集中在：

1. **面积计算 bug** — 导致所有面积相关功能失效，需立即修复
2. **接口不统一** — 鱼群检测有两个入口，配置和代码不同步
3. **数据质量阈值** — 需要根据真实数据特征调整

GUI 可以正常启动和显示，但因面积 bug，网格分析和密度估算的结果将不准确。
