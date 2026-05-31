# EK80 淡水鱼类资源评估系统 — 设计文档

> 日期：2026-05-31
> 状态：设计确认

---

## 1. 项目目标

构建一个端到端的淡水鱼类资源评估 CLI 工具，基于 echopype 包处理 Simrad EK80 声学数据，实现从原始 .raw 文件到鱼类密度/生物量估算、鱼群识别、可视化报告的完整自动化流程。

**核心场景：** 福建省水库群（山美水库、坂头水库等）的鱼类资源调查。

---

## 2. 数据流与处理流程

```
.raw 文件
    │
    ▼
┌─────────────┐
│ 1. 声学处理  │  echopype: raw → Sv/TS → 噪声去除 → 底部检测
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ 2. 鱼群识别  │  基于 Sv 阈值的鱼群检测与聚类
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ 3. 密度估算  │  NASC → 鱼类密度 (ind/ha)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ 4. 可视化    │  echogram、密度分布图、统计报表
└──────┬──────┘
       │
       ▼
  CSV 输出 + 图表
```

---

## 3. 项目结构

```
echopype/
├── configs/                # 水库配置文件 (YAML)
│   └── example.yaml
├── src/
│   ├── __init__.py
│   ├── cli.py              # CLI 入口 (click)
│   ├── acoustic.py         # 声学处理模块
│   ├── school.py           # 鱼群识别模块
│   ├── density.py          # 密度估算模块
│   ├── viz.py              # 可视化模块
│   └── utils.py            # 通用工具（日志、路径等）
├── outputs/                # 输出目录（按水库/日期组织）
├── tests/
│   ├── test_acoustic.py
│   ├── test_school.py
│   ├── test_density.py
│   └── conftest.py
├── pyproject.toml
└── README.md
```

---

## 4. 配置文件格式

每个水库一个 YAML 配置文件，定义处理参数：

```yaml
reservoir:
  name: "山美水库"
  region: "福建泉州"

input:
  raw_dir: "D:/data/shanmei/raw"
  pattern: "*.raw"

processing:
  frequencies: [38000, 70000, 120000]   # Hz
  sv_threshold: -60                      # dB
  bottom_detection:
    method: "arima"
    offset: 0.5                          # m
  noise_removal:
    method: "estimate"
    ping_average: 5

school_detection:
  min_sv: -55                            # dB
  min_length: 3                          # ping 数
  min_height: 2                          # 采样单元数

density:
  ts_default: -30                        # 默认 TS 值 (dB)，无采样数据时使用
  ts_body_length: null                   # 体长-TS 关系（后续由拖网数据提供）

output:
  dir: "D:/data/shanmei/outputs"
  formats: ["csv", "png"]
```

---

## 5. CLI 接口

```bash
# 运行完整流水线
python -m fish_acoustics run configs/shanmei.yaml

# 只运行指定步骤
python -m fish_acoustics run configs/shanmei.yaml --step acoustic
python -m fish_acoustics run configs/shanmei.yaml --step school
python -m fish_acoustics run configs/shanmei.yaml --step density
python -m fish_acoustics run configs/shanmei.yaml --step viz

# 跳到指定步骤（前面步骤的输出已存在）
python -m fish_acoustics run configs/shanmei.yaml --skip-to density

# 查看处理状态
python -m fish_acoustics status configs/shanmei.yaml
```

**步骤说明：**
1. **acoustic** — raw → Sv 计算、噪声去除、底部检测、水域分割
2. **school** — 基于 Sv 阈值的鱼群检测与聚类
3. **density** — NASC 计算、密度估算
4. **viz** — echogram、分布图、统计报表

---

## 6. 核心模块设计

### 6.1 acoustic.py — 声学处理

基于 echopype 标准流程：

```python
def process_raw(config: dict) -> xr.Dataset:
    """
    处理流程：
    1. ep.open_raw() — 读取 .raw 文件
    2. ep.calibrate.compute_Sv() — 计算体积反向散射强度
    3. ep.clean.remove_noise() — 噪声去除
    4. ep.process.detect_bottom() — 底部检测
    """
    ...
```

**输入：** 配置中的 raw_dir 路径
**输出：** 处理后的 xarray Dataset（含 Sv、底部深度等）

### 6.2 school.py — 鱼群识别

```python
def detect_schools(sv_data: xr.Dataset, config: dict) -> pd.DataFrame:
    """
    鱼群检测流程：
    1. 二值化：Sv > min_sv 的区域标记为潜在鱼群
    2. 连通区域标记（blob detection）
    3. 过滤：最小长度/高度/面积
    4. 计算每个鱼群属性
    """
    ...
```

**输出 DataFrame 列：**
- `school_id` — 鱼群编号
- `ping_start`, `ping_end` — ping 范围
- `depth_start`, `depth_end` — 深度范围
- `area` — 面积 (m²)
- `mean_sv` — 平均 Sv (dB)
- `centroid_depth` — 中心深度

### 6.3 density.py — 密度估算

```python
def estimate_density(
    schools_df: pd.DataFrame,
    sv_data: xr.Dataset,
    config: dict
) -> pd.DataFrame:
    """
    密度估算流程：
    1. 计算每个 transect 的 NASC
    2. 基于 TS-体长关系转换为密度
    3. 按深度分层统计

    注：当前阶段无生物学采样数据，TS 参数使用配置文件中的默认值。
    后续整合拖网数据后，可基于实测体长-TS 关系替换。
    """
    ...
```

**输出 DataFrame 列：**
- `transect_id` — 断面编号
- `depth_layer` — 深度层
- `nasc` — NASC 值
- `density_ind_ha` — 密度 (ind/ha)
- `total_biomass_kg` — 生物量估算 (kg)

### 6.4 viz.py — 可视化

```python
def generate_plots(
    sv_data: xr.Dataset,
    schools_df: pd.DataFrame,
    density_df: pd.DataFrame,
    config: dict
):
    """
    生成图表：
    1. echogram — 声学图（带鱼群标记）
    2. 鱼群分布图 — 深度 vs 距离
    3. 密度剖面图
    4. 统计汇总表
    """
    ...
```

---

## 7. 错误处理

- 每个模块独立捕获异常，写入日志文件 (`outputs/<reservoir>/logs/`)
- 处理中断时支持从断点恢复：检查中间输出文件是否存在
- 常见错误的友好提示：
  - 文件不存在 / 格式错误
  - 参数越界（频率不在设备范围内）
  - 内存不足（建议分块处理）

---

## 8. 依赖

```
echopype >= 0.11.0
xarray
pandas
numpy
matplotlib
click
pyyaml
```

---

## 9. 测试策略

- **单元测试：** 每个模块的核心函数
- **集成测试：** 用 echopype 内置示例数据跑完整流程
- **真实数据测试：** 用山美水库 .raw 文件验证

---

## 10. 未来扩展

- 生物学采样数据整合（拖网/刺网 → 物种识别）
- 多水库批量处理
- Web 可视化界面
- 分布式处理支持（大规模数据）
