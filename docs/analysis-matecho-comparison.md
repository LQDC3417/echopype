# 渔业声学开源项目对比分析与改进计划

**文档版本**：v1.0
**创建日期**：2026-08-12
**分析目的**：对比国际开源声学数据处理软件，识别当前项目短板，制定改进路线

---

## 一、项目现状概述

### 1.1 当前项目功能清单

| 模块 | 文件 | 功能 | 成熟度 |
|------|------|------|--------|
| 声学处理 | `src/core/acoustic.py` | Sv 计算、噪声去除、底部检测 | ⭐⭐⭐ |
| 鱼群检测 | `src/core/school.py` | 基于阈值的鱼群识别 | ⭐⭐ |
| 密度估算 | `src/core/density.py` | ABC/NASC → 鱼类密度 | ⭐⭐⭐ |
| 网格分析 | `src/core/grid.py` | 垂直分层 × 水平分段统计 | ⭐⭐⭐ |
| 区域管理 | `src/core/region.py` | 表线/底线裁剪 | ⭐⭐⭐⭐ |
| 多频分析 | `src/core/multifreq.py` | 多通道管理、频率对比 | ⭐⭐ |
| 质量检查 | `src/core/quality.py` | Sv/底线数据验证 | ⭐⭐⭐ |
| GUI | `src/gui/` | PySide6 + OpenGL 渲染 | ⭐⭐⭐⭐ |

### 1.2 技术栈

| 组件 | 选择 | 评价 |
|------|------|------|
| 数据格式 | xarray Dataset → netCDF/Zarr | ✅ 现代化 |
| 界面框架 | PySide6 + OpenGL | ✅ 高性能 |
| 声学核心 | echopype 库 | ✅ 开源标准 |
| 代码架构 | 模块化分离 (core/gui/viz) | ✅ 可扩展 |

---

## 二、国际开源项目调研

### 2.1 项目清单

#### Python 项目

| 项目 | Stars | 机构 | 主要功能 | 链接 |
|------|-------|------|----------|------|
| **echopype** | 139 | OSU-AOS | 数据转换、标准化、基础处理 | [GitHub](https://github.com/echostack-org/echopype) |
| **pyEcholab** (NOAA) | 43 | NOAA NCEI | 数据读写、处理、可视化 | [GitHub](https://github.com/CI-CMG/pyEcholab) |
| **pyEcholab** (AFSC) | 10 | NOAA AFSC | 底部检测、积分、噪声处理 | [GitHub](https://github.com/noaa-afsc-mace/pyEcholab) |
| **oceanstream** | 7 | Pineview Labs | CLI 工具、噪声去除 | [GitHub](https://github.com/OceanStreamIO/oceanstream) |
| **echopop** | 4 | OSU-AOS | 生物量估算 | [GitHub](https://github.com/echostack-org/echopop) |

#### MATLAB 项目

| 项目 | 机构 | 主要功能 | 链接 |
|------|------|----------|------|
| **Matecho** | 法国 IRD/LEMAR | 完整处理流程（积分、鱼群、反演） | [GitLab](https://forge.ird.fr/lemar/active_acoustics/matecho) |

#### R 语言项目

| 项目 | Stars | 主要功能 | 链接 |
|------|-------|----------|------|
| **FSA** | 76 | 渔业资源评估 | [GitHub](https://github.com/fishR-Core-Team/FSA) |
| **TropFishR** | 30 | 热带渔业分析 | [GitHub](https://github.com/tokami/TropFishR) |

### 2.2 核心项目功能对比

| 功能 | echopype | pyEcholab | Matecho | 本项目 | 差距 |
|------|----------|-----------|---------|--------|------|
| 数据读取 | ✅ | ✅ | ✅ | ✅ | 无 |
| Sv 计算 | ✅ | ✅ | ✅ | ✅ | 无 |
| 噪声去除 | ✅ 基础 | ✅ 被动模式 | ✅ De Robertis 完整 | ✅ 基础 | **中** |
| 底部检测 | ✅ 基础 | ✅ AFSC 算法 | ✅ 高级相关性验证 | ✅ 基础 | **大** |
| 鱼群提取 | ✅ 基础 | ❌ | ✅ 空间聚类+迁移处理 | ✅ 基础 | **大** |
| **回声积分** | ❌ | ✅ 完整 | ✅ 完整 | ❌ | **严重** |
| 网格分析 | ❌ | ✅ 完整 | ✅ 完整 | ✅ | 小 |
| 单目标检测 | ❌ | ❌ | ✅ | ❌ | **严重** |
| 模型反演 | ❌ | ❌ | ✅ TS 模型 | ❌ | **严重** |

---

## 三、关键算法分析

### 3.1 Matecho 噪声去除算法（De Robertis 2007）

**文件**：`privat/Filtering/NoiseReductionDeRobertis.m`

**核心思想**：
1. 移除 TVG（Time Varied Gain）得到校准功率 PowCal
2. 按 ping 窗口和深度窗口进行平均
3. 按 ping 列取最小值作为噪声估计
4. 在线性域中减去噪声

**关键参数**：
```matlab
NoiseMax = -125;           % 噪声上限 (dB)
ApplyMeaning = 1;          % 是否平滑
WinPingN = 40;             % ping 方向窗口大小
WinDep = 10;               % 深度方向窗口大小 (米)
LowSv_dB = -150;           % 低 Sv 替换值
PassifMode = 0;            % 被动模式开关
```

**两种模式**：
- **De Robertis 模式**（PassifMode=0）：从回波数据的最小功率估计噪声
- **被动模式**（PassifMode=1）：使用被动 ping（关闭发射时）估算噪声

**可移植性**：⭐⭐⭐⭐（算法清晰，参数明确）

---

### 3.2 Matecho 底部检测算法

**文件**：`privat/Filtering/BottomDetectionMatecho.m`

**核心创新**：

#### 1. 双阈值检测
```matlab
Param.PeakThreshold = -40;           % 峰值阈值 (dB)
Param.DiscriminationThreshold = -50; % 判别阈值 (dB)
```
- 先找超过 PeakThreshold 的 Sv 峰值
- 再从峰值回溯找第一个低于 DiscriminationThreshold 的点

#### 2. 相关性验证（std15）
```matlab
nbStd = 15;  % 前 15 个 ping 用于评估

% 计算前 15 个 ping 底部深度的标准差
std15 = nanstd(d(idbot(kf, previous_pings)));

% 如果当前检测与前一个差异过大，标记为无效
if abs(current_bottom - previous_bottom) <= 3 * std15:
    relevance = 1;  # 有效
```

#### 3. 表面饱和去除
```matlab
Param.SaturationThreshold = -60;  % 饱和阈值
% 找到第一个低于饱和阈值的样本，之前的区域视为饱和
idsamp = find(sv <= Param.SaturationThreshold);
sv(1:idsamp(1)) = NaN;  % 移除饱和区域
```

**可移植性**：⭐⭐⭐⭐⭐（逻辑清晰，易于实现）

---

### 3.3 Matecho 鱼群提取算法

**文件**：`privat/SpatialAnalysis/EchoGroupExtraction.m`

**核心流程**：

#### 1. 逐 ping 阈值化
```matlab
Param.MinThres = -60;  % 最小阈值 (dB)
% 对每个 ping 的每个样本判断：Sv >= MinThres 且在底线以上
```

#### 2. 深度方向聚类
```matlab
Param.MaxDistDep = 0.1;  % 最大深度间隔 (米)
% 如果相邻有效样本的深度差 > MaxDistDep，分为不同 segment
```

#### 3. 跨 ping segment linking
```matlab
Param.MaxDistAlong = 0.6;  % 最大水平间隔 (ping 数)
% 前向连接：当前 ping 的 segment 与前 N 个 ping 的 segment 连接
% 后向连接：如果一个大的新 segment 覆盖多个旧 segment，合并它们
```

#### 4. 迁移区域特殊处理
```matlab
Param.Migration = 1;         % 启用迁移处理
Param.MaxDistDepTol = 7.5;   % 迁移区域容差 (米)

% 日出/日落检测
if twi(Kp) == 2 || twi(Kp) == 4:  % 日出或日落
    MaxDistDepTol = 7.5;  # 增大深度容差
    kprev = 1;            # 只看前 1 个 ping
```

**可移植性**：⭐⭐⭐⭐（逻辑复杂但可实现）

---

### 3.4 pyEcholab 回声积分模块

**文件**：`echolab2/processing/integration.py`

**核心设计**：

#### 结果类
```python
class results:
    """积分结果，按 (n_intervals, n_layers) 组织"""
    mean_Sv = np.full(grid_shape, np.nan)
    nasc = np.full(grid_shape, np.nan)
    min_Sv = np.full(grid_shape, np.nan)
    max_Sv = np.full(grid_shape, np.nan)
    n_good_samples = np.full(grid_shape, np.nan)
    n_excluded_samples = np.full(grid_shape, np.nan)
    total_samples = np.full(grid_shape, np.nan)
```

#### 网格类
```python
class grid:
    """网格定义"""
    n_intervals = ...  # 水平区间数
    n_layers = ...     # 垂直层数
    ping_start = ...   # 每个区间的起始 ping
    ping_end = ...     # 每个区间的结束 ping
    depth_start = ...  # 每层的起始深度
    depth_end = ...    # 每层的结束深度
```

#### 积分逻辑
```python
def integrate(data, grid, min_threshold=-70, max_threshold=0):
    """按网格单元进行回声积分"""
    for interval in range(grid.n_intervals):
        for layer in range(grid.n_layers):
            # 提取单元数据
            cell_data = data[interval_start:interval_end, layer_start:layer_end]
            
            # 应用阈值
            cell_data[cell_data < min_threshold] = np.nan
            cell_data[cell_data > max_threshold] = np.nan
            
            # 计算统计值
            results.mean_Sv[interval, layer] = np.nanmean(cell_data)
            results.nasc[interval, layer] = 4 * np.pi * 1852**2 * np.nansum(10**(cell_data/10) * dr)
```

**可移植性**：⭐⭐⭐⭐⭐（Python 代码，可直接参考）

---

### 3.5 pyEcholab 底部检测器

**文件**：`echolab2/processing/afsc_bot_detector.py`

**核心设计**：
```python
class afsc_bot_detector:
    search_min = 10      # 最小检测深度 (米)，避开 ringdown
    window_len = 11      # Hanning 窗口长度
    backstep = 35        # 回步值 (dB)
    
    def detect(self, p_data):
        """对每个 ping 执行底部检测"""
        for ping in p_data:
            # 1. 平滑处理
            smoothed = np.convolve(hanning_window, ping, mode='same')
            
            # 2. 找到超过最小深度的最大 Sv
            max_Sv = np.nanmax(smoothed[range > search_min])
            
            # 3. 计算阈值 = max_Sv - backstep
            threshold = max_Sv - self.backstep
            
            # 4. 回溯找 echo envelope 的近边
            bottom = get_echo_envelope(smoothed, peak_idx, threshold)
```

**可移植性**：⭐⭐⭐⭐⭐（Python 代码，可直接参考）

---

### 3.6 oceanstream 噪声去除封装

**文件**：`oceanstream/denoise/background_noise_remover.py`

**核心代码**：
```python
def apply_remove_background_noise(
    ds_Sv: xr.Dataset,
    ping_num: int = 40,
    range_sample_num: int = None,
    noise_max: float = -125,
    SNR_threshold: float = 3,
) -> xr.Dataset:
    """应用 echopype 的噪声去除，自动计算默认参数"""
    
    # 自动计算 range_sample_num（10米垂直分段）
    if range_sample_num is None:
        for ch in range(ds_Sv.sizes["channel"]):
            mean_diff = np.nanmean(np.diff(ds_Sv["echo_range"].isel(channel=ch).values[0, :]))
            range_sample_nums.append(int(10 / mean_diff))
        range_sample_num = min(range_sample_nums)
    
    # 调用 echopype
    ds_Sv_processed = ep.clean.remove_background_noise(
        ds_Sv, ping_num=ping_num, range_sample_num=range_sample_num,
        noise_max=noise_max, SNR_threshold=SNR_threshold,
    )
    return ds_Sv_processed
```

**可移植性**：⭐⭐⭐⭐⭐（直接使用）

---

## 四、短板识别与改进计划

### 4.1 短板汇总

| 编号 | 短板 | 严重程度 | 影响 | 参考项目 |
|------|------|----------|------|----------|
| **S1** | 回声积分模块缺失 | 🔴 严重 | 无法进行标准化积分分析 | pyEcholab |
| **S2** | 底部检测算法简单 | 🔴 严重 | 误检率高，复杂地形适应性差 | Matecho, pyEcholab |
| **S3** | 鱼群提取不够精细 | 🔴 严重 | 漏检小鱼群，迁移区域处理差 | Matecho |
| **S4** | 缺少单目标检测 | 🔴 严重 | 无法估算个体大小分布 | Matecho |
| **S5** | 噪声去除参数固定 | 🟡 中等 | 无法适应不同数据特点 | Matecho, pyEcholab |
| **S6** | 缺少模型反演功能 | 🟡 中等 | 密度估算依赖固定 TS 值 | Matecho |
| **S7** | 缺少噪声可视化检查 | 🟡 中等 | 无法验证噪声去除效果 | Matecho |

### 4.2 改进计划

#### P0 - 高优先级（1-2 周）

##### 任务 1：回声积分模块
**参考**：pyEcholab `integration.py`
**新增文件**：`src/core/integration.py`

**功能设计**：
```python
@dataclass
class IntegrationResult:
    """回声积分结果"""
    mean_Sv: np.ndarray      # (n_intervals, n_layers) 平均 Sv
    nasc: np.ndarray         # (n_intervals, n_layers) NASC
    min_Sv: np.ndarray       # (n_intervals, n_layers) 最小 Sv
    max_Sv: np.ndarray       # (n_intervals, n_layers) 最大 Sv
    n_good: np.ndarray       # (n_intervals, n_layers) 有效样本数
    n_excluded: np.ndarray   # (n_intervals, n_layers) 排除样本数
    n_total: np.ndarray      # (n_intervals, n_layers) 总样本数

def integrate(
    ds_Sv: xr.Dataset,
    grid_cells: list[dict],
    min_threshold: float = -70,
    max_threshold: float = 0,
    exclude_below_bottom: bool = True,
) -> IntegrationResult:
    """按网格单元进行回声积分"""
```

**ESU 类型支持**：
- 按 ping 数（pings）
- 按时间（seconds）
- 按距离（nmi）

**预计工作量**：3-5 天

---

##### 任务 2：增强底部检测
**参考**：Matecho `BottomDetectionMatecho.m`、pyEcholab `afsc_bot_detector.py`
**修改文件**：`src/core/acoustic.py`

**新增功能**：
```python
def detect_bottom_enhanced(
    ds_Sv: xr.Dataset,
    config: dict,
) -> xr.Dataset:
    """增强底部检测"""
    bottom_cfg = config.get("bottom_detection", {})
    method = bottom_cfg.get("method", "basic")
    
    if method == "basic":
        # 当前实现（保留）
        return detect_bottom_basic(ds_Sv, config)
    
    elif method == "enhanced":
        # 新增：增强检测
        # 1. 平滑处理（Hanning 窗口）
        # 2. 双阈值检测（峰值阈值 + 判别阈值）
        # 3. 相关性验证（std15）
        return detect_bottom_with_validation(ds_Sv, config)
    
    elif method == "afsc":
        # 新增：AFSC 算法
        return detect_bottom_afsc(ds_Sv, config)
```

**配置参数**：
```yaml
bottom_detection:
  method: "enhanced"  # basic / enhanced / afsc
  peak_threshold: -40.0      # 峰值阈值 (dB)
  discrimination_threshold: -50.0  # 判别阈值 (dB)
  saturation_threshold: -60.0  # 饱和阈值 (dB)
  validation_window: 15       # 相关性验证窗口
  validation_threshold: 3.0   # 相关性验证倍数
  smoothing_window: 11        # 平滑窗口长度
  backstep: 35.0              # AFSC 回步值 (dB)
```

**预计工作量**：3-4 天

---

#### P1 - 中高优先级（2-4 周）

##### 任务 3：高级鱼群提取
**参考**：Matecho `EchoGroupExtraction.m`
**新增文件**：`src/core/shoal_extraction.py`

**功能设计**：
```python
@dataclass
class ShoalSegment:
    """鱼群片段"""
    min_depth: float
    max_depth: float
    ping_index: int
    label: int

@dataclass
class Shoal:
    """完整鱼群"""
    id: int
    segments: list[ShoalSegment]
    ping_start: int
    ping_end: int
    depth_min: float
    depth_max: float
    area: float
    mean_sv: float
    # 形态特征
    length: float           # 水平长度
    height: float           # 垂直高度
    thickness: float        # 厚度
    centroid_depth: float   # 中心深度
    # 空间位置
    latitude_start: float
    longitude_start: float
    latitude_end: float
    longitude_end: float

def extract_shoals_advanced(
    ds_Sv: xr.Dataset,
    config: dict,
    time_of_day: np.ndarray | None = None,
) -> list[Shoal]:
    """高级鱼群提取"""
    # 1. 逐 ping 阈值化
    # 2. 深度方向聚类（MaxDistDep）
    # 3. 跨 ping segment linking（前向+后向）
    # 4. 迁移区域特殊处理
    # 5. 计算鱼群描述符
```

**配置参数**：
```yaml
school_detection:
  method: "advanced"  # echoview / advanced
  min_threshold: -60.0       # 最小阈值 (dB)
  max_depth_distance: 0.1    # 最大深度间隔 (米)
  max_ping_distance: 0.6     # 最大水平间隔 (ping 数)
  max_time_gap: 20.0         # 最大时间间隔 (秒)
  migration_enabled: true    # 启用迁移处理
  migration_tolerance: 7.5   # 迁移区域容差 (米)
```

**预计工作量**：5-7 天

---

##### 任务 4：单目标检测
**参考**：Matecho `TSMatecho`
**新增文件**：`src/core/single_target.py`

**功能设计**：
```python
@dataclass
class SingleTarget:
    """单个目标"""
    ping_index: int
    sample_index: int
    depth: float
    ts: float               # 目标强度 (dB)
    sv_peak: float          # 峰值 Sv (dB)
    # 形态特征
    minor_axis: float       # 短轴（垂直）
    major_axis: float       # 长轴（水平）
    # 位置
    ping_time: datetime
    latitude: float
    longitude: float

def detect_single_targets(
    ds_Sv: xr.Dataset,
    config: dict,
) -> pd.DataFrame:
    """单目标检测"""
    # 1. 峰值检测
    # 2. 目标分离（避免多个目标重叠）
    # 3. TS 统计
    # 4. 返回目标清单
```

**配置参数**：
```yaml
single_target:
  enabled: true
  min_ts: -50.0              # 最小 TS 阈值 (dB)
  max_ts: -20.0              # 最大 TS 阈值 (dB)
  min_separation: 3          # 最小分离距离 (样本)
  beam_width_correction: true  # 波束宽度校正
```

**预计工作量**：5-7 天

---

#### P2 - 中优先级（1-2 月）

##### 任务 5：增强噪声去除
**参考**：Matecho `NoiseReductionDeRobertis.m`、pyEcholab `noise.py`

**新增功能**：
```python
def remove_noise_enhanced(
    ds_Sv: xr.Dataset,
    config: dict,
) -> xr.Dataset:
    """增强噪声去除"""
    noise_cfg = config.get("noise_removal", {})
    mode = noise_cfg.get("mode", "de_robertis")
    
    if mode == "de_robertis":
        # De Robertis 模式（当前实现增强版）
        noise = estimate_noise_de_robertis(ds_Sv, ...)
    elif mode == "passive":
        # 被动模式
        noise = estimate_noise_from_passive(ds_Sv, ...)
    
    # 生成噪声检查图
    if noise_cfg.get("save_check_plot", False):
        plot_noise_check(ds_Sv, noise)
```

**配置参数**：
```yaml
noise_removal:
  mode: "de_robertis"  # de_robertis / passive
  ping_window: 40
  depth_window: 10  # 米
  noise_max: -125  # dB
  snr_threshold: 3  # dB
  low_sv_value: -150  # dB
  save_check_plot: true
```

**预计工作量**：3-4 天

---

##### 任务 6：噪声可视化检查
**参考**：Matecho 的检查图生成

**新增功能**：
```python
def plot_noise_check(
    ds_Sv: xr.Dataset,
    noise: np.ndarray,
    save_path: str | None = None,
) -> None:
    """生成噪声检查图"""
    # 1. 原始 Sv 与噪声估计对比
    # 2. SNR 分布图
    # 3. 噪声随 ping 变化图
```

**预计工作量**：1-2 天

---

#### P3 - 低优先级（3+ 月）

##### 任务 7：TS 模型反演
**参考**：Matecho `Inversion.m`

**新增文件**：`src/core/inversion.py`

**功能设计**：
```python
class TSModel:
    """TS 模型基类"""
    def calculate_ts(self, frequency: float, size: float, ...) -> float:
        pass

class FluidSphereModel(TSModel):
    """流体球模型"""
    pass

class InversionResult:
    """反演结果"""
    abundance: np.ndarray      # 丰度分布 (size_classes,)
    biovolume: np.ndarray      # 生物体积
    residual_error: float      # 残差
    size_classes: np.ndarray   # 尺寸类别 (mm)

def invert(
    ds_Sv: xr.Dataset,
    frequencies: list[float],
    model: TSModel,
    config: dict,
) -> InversionResult:
    """TS 模型反演"""
```

**预计工作量**：10-15 天

---

## 五、国内研究现状

### 5.1 主要研究机构

| 机构 | 研究方向 | 备注 |
|------|----------|------|
| 中国科学院水生生物研究所 | 淡水渔业声学评估 | 国内最早 |
| 中国水产科学研究院 | 海洋渔业声学调查 | 下属多个海区所 |
| 中科院声学研究所 | 水声学基础理论 | 偏重理论 |
| 厦门大学 | 海洋声学、鱼类行为 | 海洋科学强 |
| 大连海洋大学 | 渔业资源声学评估 | 渔业特色 |
| 上海海洋大学 | 渔业资源与声学 | 水产优势 |

### 5.2 国内开源现状

| 平台 | 搜索结果 | 说明 |
|------|----------|------|
| GitHub | 未找到 | 国内无开源渔业声学软件 |
| Gitee | 未找到 | 国内无开源渔业声学软件 |
| CNKI | 论文为主 | 代码极少公开 |

### 5.3 市场机会

| 优势 | 说明 |
|------|------|
| **国内空白** | 中国目前没有成熟的开源渔业声学软件 |
| **需求存在** | 各水产高校、研究所都有声学数据处理需求 |
| **替代进口** | 可以部分替代 Echoview（商业软件价格高） |
| **政策支持** | 国家鼓励科研软件国产化 |

---

## 六、水库鱼类资源评估特殊需求

### 6.1 淡水鱼 TS 参考值

| 鱼类 | 体长 (cm) | TS (dB) @ 38kHz | TS (dB) @ 120kHz | 来源 |
|------|-----------|-----------------|------------------|------|
| 鲢鱼 | 20-30 | -40 ~ -35 | -38 ~ -33 | 文献 |
| 鳙鱼 | 30-50 | -38 ~ -32 | -36 ~ -30 | 文献 |
| 草鱼 | 30-50 | -38 ~ -32 | -36 ~ -30 | 文献 |
| 鲤鱼 | 20-40 | -42 ~ -36 | -40 ~ -34 | 文献 |
| 鲫鱼 | 10-20 | -48 ~ -42 | -46 ~ -40 | 文献 |

**注意**：以上为参考值，实际 TS 受鱼体姿态、频率、水温等因素影响。

### 6.2 水库调查典型参数

| 参数 | 典型值 | 说明 |
|------|--------|------|
| 工作频率 | 38kHz + 120kHz | 双频配置 |
| 脉冲宽度 | 0.512ms 或 1.024ms | CW 模式 |
| 波束角度 | 7° 或 11° | 单波束 |
| 航速 | 5-8 km/h | 低速调查 |
| 垂直分层 | 1m 或 2m | 根据水深调整 |
| 水平分段 | 100-500 ping | 或 0.1-0.5 nmi |

---

## 七、参考资料

### 7.1 算法参考文献

1. De Robertis, A., & Higginbottom, I. (2007). A post-processing technique to estimate the signal-to-noise ratio and remove echosounder background noise. *ICES Journal of Marine Sciences*, 64(6), 1282-1291.

2. Perrot, Y., et al. (2018). Matecho: An open-source tool for processing fisheries acoustics data. *Acoustics Australia*, 46, 241-248.

3. Towler, R., et al. (2003). A versatile approach to calibration and analysis of multibeam echosounder data. *ICES Journal of Marine Sciences*, 60(3), 611-620.

### 7.2 开源项目链接

| 项目 | 链接 | 备注 |
|------|------|------|
| echopype | https://github.com/echostack-org/echopype | 数据标准化 |
| pyEcholab (NOAA) | https://github.com/CI-CMG/pyEcholab | 处理算法 |
| pyEcholab (AFSC) | https://github.com/noaa-afsc-mace/pyEcholab | 底部检测 |
| oceanstream | https://github.com/OceanStreamIO/oceanstream | CLI 工具 |
| Matecho | https://forge.ird.fr/lemar/active_acoustics/matecho | 完整功能 |

### 7.3 学习资源

| 资源 | 链接 | 说明 |
|------|------|------|
| echopype 文档 | https://echopype.readthedocs.io/ | 官方文档 |
| echopype 示例 | https://github.com/echostack-org/echopype-examples | Jupyter Notebooks |
| Matecho 用户手册 | https://pages.iuem.eu/ird/matecho/ | PDF 文档 |

---

## 八、进度跟踪

### 8.1 任务看板

| 任务 | 优先级 | 状态 | 开始日期 | 完成日期 | 备注 |
|------|--------|------|----------|----------|------|
| 回声积分模块 | P0 | 待开始 | - | - | 参考 pyEcholab |
| 增强底部检测 | P0 | 待开始 | - | - | 参考 Matecho |
| 高级鱼群提取 | P1 | 待开始 | - | - | 参考 Matecho |
| 单目标检测 | P1 | 待开始 | - | - | 参考 Matecho |
| 增强噪声去除 | P2 | 待开始 | - | - | 参考 Matecho |
| 噪声可视化检查 | P2 | 待开始 | - | - | 参考 Matecho |
| TS 模型反演 | P3 | 待开始 | - | - | 参考 Matecho |

### 8.2 版本规划

| 版本 | 主要功能 | 预计时间 |
|------|----------|----------|
| v2.1 | 回声积分 + 增强底部检测 | 2 周内 |
| v2.2 | 高级鱼群提取 + 单目标检测 | 1 月内 |
| v2.3 | 增强噪声去除 + 可视化检查 | 2 月内 |
| v3.0 | TS 模型反演 | 3+ 月 |

---

## 九、附录

### 9.1 文件结构变更

```
src/
├── core/
│   ├── acoustic.py        # 增强底部检测
│   ├── integration.py     # 新增：回声积分
│   ├── shoal_extraction.py # 新增：高级鱼群提取
│   ├── single_target.py   # 新增：单目标检测
│   ├── inversion.py       # 新增：TS 模型反演
│   ├── density.py         # 扩展：支持反演结果
│   ├── grid.py            # 无变更
│   ├── school.py          # 保留：基础检测
│   ├── region.py          # 无变更
│   ├── quality.py         # 扩展：积分质量检查
│   └── utils.py           # 无变更
├── gui/                   # 无变更
└── viz/                   # 无变更
```

### 9.2 配置文件扩展

```yaml
# 新增配置项
processing:
  noise_removal:
    mode: "de_robertis"  # 新增
    ping_window: 40      # 新增
    depth_window: 10     # 新增
    save_check_plot: true # 新增
  
  bottom_detection:
    method: "enhanced"   # 新增: basic / enhanced / afsc
    peak_threshold: -40.0           # 新增
    discrimination_threshold: -50.0 # 新增
    validation_window: 15           # 新增
    validation_threshold: 3.0       # 新增

school_detection:
  method: "advanced"     # 新增: echoview / advanced
  min_threshold: -60.0   # 新增
  max_depth_distance: 0.1 # 新增
  max_ping_distance: 0.6  # 新增
  migration_enabled: true # 新增

# 新增模块配置
integration:
  esu_type: "pings"      # pings / seconds / nmi
  esu_size: 500          # ESU 大小
  layer_width: 5         # 层宽度 (米)

single_target:
  enabled: false         # 默认关闭
  min_ts: -50.0
  max_ts: -20.0
```

---

**文档维护**：本文档应在每次重大改进后更新，记录实际进展和新的发现。
