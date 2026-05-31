# EK80 淡水鱼类资源评估系统 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个端到端 CLI 工具，处理 EK80 .raw 文件，完成声学处理、鸡群识别、密度估算和可视化。

**Architecture:** 模块化 CLI + YAML 配置驱动。每个处理步骤是独立模块，click CLI 入口串联各模块。

**Tech Stack:** Python 3.11+, echopype 0.11.0, xarray, pandas, numpy, matplotlib, click, pyyaml

**关键发现：** echopype 已内置 `detect_shoal`（鱼群检测）和 `detect_seafloor`（底部检测），可直接复用。

---

## 文件结构

```
echopype/
├── configs/
│   └── example.yaml
├── src/
│   ├── __init__.py
│   ├── cli.py              # CLI 入口
│   ├── acoustic.py         # 声学处理
│   ├── school.py           # 鱼群识别
│   ├── density.py          # 密度估算
│   ├── viz.py              # 可视化
│   └── utils.py            # 通用工具
├── tests/
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_acoustic.py
│   ├── test_school.py
│   ├── test_density.py
│   └── test_viz.py
├── pyproject.toml
└── README.md
```

---

## Task 1: 项目脚手架与配置加载

**Files:**
- Create: `pyproject.toml`
- Create: `src/__init__.py`
- Create: `src/utils.py`
- Create: `configs/example.yaml`
- Create: `tests/conftest.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: 创建 pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "fish-acoustics"
version = "0.1.0"
description = "EK80 淡水鱼类资源评估系统"
requires-python = ">=3.10"
dependencies = [
    "echopype>=0.11.0",
    "xarray",
    "pandas",
    "numpy",
    "matplotlib",
    "click",
    "pyyaml",
]

[project.scripts]
fish-acoustics = "src.cli:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: 创建 src/__init__.py**

```python
"""EK80 淡水鱼类资源评估系统"""
```

- [ ] **Step 3: 创建 configs/example.yaml**

```yaml
reservoir:
  name: "示例水库"
  region: "福建"

input:
  raw_dir: "D:/data/example/raw"
  pattern: "*.raw"

processing:
  frequencies: [38000, 70000, 120000]
  waveform_mode: "CW"
  encode_mode: "power"
  noise_removal:
    ping_num: 5
    range_sample_num: 10
    SNR_threshold: "3.0dB"
  bottom_detection:
    method: "basic"
    threshold: -50.0
    offset_m: 0.5
    bin_skip_from_surface: 200

school_detection:
  method: "echoview"
  thr: -55.0
  mincan: [3.0, 10.0]
  maxlink: [3.0, 15.0]
  minsho: [3.0, 15.0]

density:
  ts_default: -30.0

output:
  dir: "D:/data/example/outputs"
  formats: ["csv", "png"]
```

- [ ] **Step 4: 创建 src/utils.py — 配置加载与日志**

```python
"""通用工具：配置加载、日志、路径管理"""

import logging
from pathlib import Path
from typing import Any

import yaml


def load_config(config_path: str) -> dict:
    """加载 YAML 配置文件"""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def validate_config(config: dict) -> None:
    """验证配置文件必要字段"""
    required = ["reservoir", "input", "processing", "output"]
    for key in required:
        if key not in config:
            raise ValueError(f"配置文件缺少必要字段: {key}")

    # 验证 input
    input_cfg = config["input"]
    if "raw_dir" not in input_cfg:
        raise ValueError("配置缺少 input.raw_dir")

    # 验证 output
    output_cfg = config["output"]
    if "dir" not in output_cfg:
        raise ValueError("配置缺少 output.dir")


def setup_logging(reservoir_name: str, output_dir: str) -> logging.Logger:
    """设置日志"""
    log_dir = Path(output_dir) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("fish_acoustics")
    logger.setLevel(logging.INFO)

    # 文件处理器
    fh = logging.FileHandler(log_dir / f"{reservoir_name}.log", encoding="utf-8")
    fh.setLevel(logging.INFO)

    # 控制台处理器
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)

    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger


def get_output_dir(config: dict) -> Path:
    """获取输出目录并创建"""
    output_dir = Path(config["output"]["dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir
```

- [ ] **Step 5: 创建 tests/conftest.py**

```python
"""测试配置"""

import tempfile
from pathlib import Path

import pytest
import yaml


@pytest.fixture
def sample_config():
    """示例配置"""
    return {
        "reservoir": {"name": "测试水库", "region": "福建"},
        "input": {"raw_dir": "D:/data/test/raw", "pattern": "*.raw"},
        "processing": {
            "frequencies": [38000, 70000],
            "waveform_mode": "CW",
            "encode_mode": "power",
            "noise_removal": {
                "ping_num": 5,
                "range_sample_num": 10,
                "SNR_threshold": "3.0dB",
            },
            "bottom_detection": {
                "method": "basic",
                "threshold": -50.0,
                "offset_m": 0.5,
                "bin_skip_from_surface": 200,
            },
        },
        "school_detection": {
            "method": "echoview",
            "thr": -55.0,
            "mincan": [3.0, 10.0],
            "maxlink": [3.0, 15.0],
            "minsho": [3.0, 15.0],
        },
        "density": {"ts_default": -30.0},
        "output": {"dir": "D:/data/test/outputs", "formats": ["csv", "png"]},
    }


@pytest.fixture
def config_file(sample_config, tmp_path):
    """创建临时配置文件"""
    config_path = tmp_path / "test_config.yaml"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(sample_config, f, allow_unicode=True)
    return str(config_path)
```

- [ ] **Step 6: 创建 tests/test_config.py**

```python
"""配置加载测试"""

import pytest
import yaml

from src.utils import load_config, validate_config


def test_load_config_valid(config_file):
    """测试正常加载配置"""
    config = load_config(config_file)
    assert config["reservoir"]["name"] == "测试水库"


def test_load_config_not_found():
    """测试配置文件不存在"""
    with pytest.raises(FileNotFoundError):
        load_config("nonexistent.yaml")


def test_validate_config_missing_reservoir():
    """测试缺少 reservoir 字段"""
    config = {"input": {}, "output": {}}
    with pytest.raises(ValueError, match="reservoir"):
        validate_config(config)


def test_validate_config_missing_input():
    """测试缺少 input 字段"""
    config = {"reservoir": {}, "output": {}}
    with pytest.raises(ValueError, match="input"):
        validate_config(config)


def test_validate_config_missing_raw_dir():
    """测试缺少 raw_dir"""
    config = {
        "reservoir": {"name": "test"},
        "input": {"pattern": "*.raw"},
        "output": {"dir": "/tmp"},
    }
    with pytest.raises(ValueError, match="raw_dir"):
        validate_config(config)


def test_validate_config_valid(sample_config):
    """测试正常验证"""
    validate_config(sample_config)  # 不应抛出异常
```

- [ ] **Step 7: 运行测试**

Run: `pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 8: 提交**

```bash
git add pyproject.toml src/__init__.py src/utils.py configs/example.yaml tests/conftest.py tests/test_config.py
git commit -m "feat: 项目脚手架与配置加载"
```

---

## Task 2: 声学处理模块 (acoustic.py)

**Files:**
- Create: `src/acoustic.py`
- Create: `tests/test_acoustic.py`

- [ ] **Step 1: 创建 tests/test_acoustic.py — 写失败测试**

```python
"""声学处理模块测试"""

import numpy as np
import pytest
import xarray as xr

from src.acoustic import load_raw_files, process_single_file


def test_load_raw_files_not_found(tmp_path):
    """测试 raw 目录不存在"""
    config = {"input": {"raw_dir": str(tmp_path / "nonexistent"), "pattern": "*.raw"}}
    with pytest.raises(FileNotFoundError):
        load_raw_files(config)


def test_load_raw_files_empty(tmp_path):
    """测试 raw 目录为空"""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    config = {"input": {"raw_dir": str(raw_dir), "pattern": "*.raw"}}
    with pytest.raises(FileNotFoundError, match="未找到"):
        load_raw_files(config)


def test_load_raw_files_found(tmp_path):
    """测试找到 raw 文件"""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "test1.raw").touch()
    (raw_dir / "test2.raw").touch()
    config = {"input": {"raw_dir": str(raw_dir), "pattern": "*.raw"}}
    files = load_raw_files(config)
    assert len(files) == 2
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/test_acoustic.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: 创建 src/acoustic.py — 实现**

```python
"""声学处理模块：raw → Sv → 噪声去除 → 底部检测"""

import logging
import os

# 修复 echopype 在 Windows 中文环境的 YAML 编码问题
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from pathlib import Path
from typing import List

import numpy as np
import xarray as xr

logger = logging.getLogger("fish_acoustics")


def load_raw_files(config: dict) -> List[Path]:
    """加载 raw 文件列表"""
    raw_dir = Path(config["input"]["raw_dir"])
    pattern = config["input"].get("pattern", "*.raw")

    if not raw_dir.exists():
        raise FileNotFoundError(f"raw 目录不存在: {raw_dir}")

    files = sorted(raw_dir.glob(pattern))
    if not files:
        raise FileNotFoundError(f"未找到匹配 {pattern} 的文件: {raw_dir}")

    logger.info(f"找到 {len(files)} 个 raw 文件")
    return files


def process_single_file(
    raw_file: Path,
    config: dict,
) -> xr.Dataset:
    """
    处理单个 raw 文件的完整流程：
    1. open_raw — 读取文件
    2. compute_Sv — 计算体积反向散射强度
    3. remove_background_noise — 噪声去除
    4. detect_seafloor — 底部检测
    """
    import echopype as ep
    from echopype.calibrate import compute_Sv
    from echopype.clean import remove_background_noise
    from echopype.mask import detect_seafloor

    proc_cfg = config["processing"]

    # 1. 读取 raw 文件
    logger.info(f"读取文件: {raw_file.name}")
    echodata = ep.open_raw(
        raw_file=str(raw_file),
        sonar_model="EK80",
    )

    # 2. 计算 Sv
    logger.info("计算 Sv...")
    waveform_mode = proc_cfg.get("waveform_mode", "CW")
    encode_mode = proc_cfg.get("encode_mode", "power")
    ds_Sv = compute_Sv(
        echodata,
        waveform_mode=waveform_mode,
        encode_mode=encode_mode,
    )

    # 3. 噪声去除
    noise_cfg = proc_cfg.get("noise_removal", {})
    logger.info("去除背景噪声...")
    ds_Sv = remove_background_noise(
        ds_Sv,
        ping_num=noise_cfg.get("ping_num", 5),
        range_sample_num=noise_cfg.get("range_sample_num", 10),
        SNR_threshold=noise_cfg.get("SNR_threshold", "3.0dB"),
    )

    # 4. 底部检测
    bottom_cfg = proc_cfg.get("bottom_detection", {})
    logger.info("检测底部...")
    channel = str(ds_Sv["channel"].values[0])
    bottom_params = {
        "var_name": "Sv",
        "channel": channel,
        "threshold": bottom_cfg.get("threshold", -50.0),
        "offset_m": bottom_cfg.get("offset_m", 0.5),
        "bin_skip_from_surface": bottom_cfg.get("bin_skip_from_surface", 200),
    }
    bottom_depth = detect_seafloor(
        ds_Sv,
        method=bottom_cfg.get("method", "basic"),
        params=bottom_params,
    )
    ds_Sv["bottom_depth"] = bottom_depth

    logger.info(f"处理完成: {raw_file.name}")
    return ds_Sv


def process_all_files(config: dict) -> xr.Dataset:
    """处理所有 raw 文件并合并"""
    raw_files = load_raw_files(config)

    datasets = []
    for raw_file in raw_files:
        try:
            ds = process_single_file(raw_file, config)
            datasets.append(ds)
        except Exception as e:
            logger.error(f"处理失败 {raw_file.name}: {e}")
            continue

    if not datasets:
        raise RuntimeError("所有文件处理失败")

    # 合并数据集
    if len(datasets) > 1:
        import echopype as ep
        combined = ep.combine_echodata(datasets)
        return combined
    return datasets[0]
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/test_acoustic.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/acoustic.py tests/test_acoustic.py
git commit -m "feat: 声学处理模块 — raw → Sv → 噪声去除 → 底部检测"
```

---

## Task 3: 鱼群识别模块 (school.py)

**Files:**
- Create: `src/school.py`
- Create: `tests/test_school.py`

- [ ] **Step 1: 创建 tests/test_school.py — 写失败测试**

```python
"""鱼群识别模块测试"""

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from src.school import detect_schools, schools_to_dataframe


def _make_mock_sv(n_pings=50, n_samples=100):
    """创建模拟 Sv 数据"""
    np.random.seed(42)
    Sv = np.random.uniform(-80, -40, (n_pings, n_samples))
    # 在中间区域插入鱼群信号
    Sv[10:20, 30:50] = np.random.uniform(-55, -45, (10, 20))
    Sv[35:45, 60:80] = np.random.uniform(-55, -45, (10, 20))

    return xr.Dataset(
        {
            "Sv": xr.DataArray(
                Sv,
                dims=["ping_time", "range_sample"],
                coords={
                    "ping_time": np.arange(n_pings),
                    "range_sample": np.arange(n_samples),
                },
            ),
        }
    )


def test_detect_schools_returns_mask():
    """测试鱼群检测返回布尔 mask"""
    ds = _make_mock_sv()
    config = {
        "school_detection": {
            "method": "echoview",
            "thr": -60.0,
            "mincan": [2.0, 5.0],
            "maxlink": [2.0, 10.0],
            "minsho": [2.0, 10.0],
        }
    }
    mask = detect_schools(ds, config)
    assert mask.dtype == bool
    assert mask.dims == ("ping_time", "range_sample")


def test_schools_to_dataframe():
    """测试鱼群 mask 转 DataFrame"""
    mask = xr.DataArray(
        np.array([[True, True, False], [True, True, False], [False, False, False]]),
        dims=["ping_time", "range_sample"],
        coords={"ping_time": [0, 1, 2], "range_sample": [0, 1, 2]},
    )
    ds = xr.Dataset({
        "Sv": xr.DataArray(
            np.array([[-50, -51, -80], [-52, -53, -80], [-80, -80, -80]]),
            dims=["ping_time", "range_sample"],
            coords={"ping_time": [0, 1, 2], "range_sample": [0, 1, 2]},
        ),
    })
    df = schools_to_dataframe(mask, ds)
    assert isinstance(df, pd.DataFrame)
    assert "school_id" in df.columns
    assert "mean_sv" in df.columns
    assert len(df) > 0
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/test_school.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: 创建 src/school.py — 实现**

```python
"""鱼群识别模块：基于 Sv 阈值的鱼群检测与聚类"""

import logging

import numpy as np
import pandas as pd
import xarray as xr

logger = logging.getLogger("fish_acoustics")


def detect_schools(ds_Sv: xr.Dataset, config: dict) -> xr.DataArray:
    """
    鱼群检测：使用 echopype 内置的 detect_shoal

    Parameters
    ----------
    ds_Sv : xr.Dataset
        包含 Sv 变量的数据集
    config : dict
        配置字典

    Returns
    -------
    xr.DataArray
        布尔 mask，True 表示鱼群区域
    """
    from echopype.mask import detect_shoal

    school_cfg = config.get("school_detection", {})
    method = school_cfg.get("method", "echoview")

    # 选择第一个 channel
    channel = str(ds_Sv["channel"].values[0]) if "channel" in ds_Sv.dims else None

    # 构建坐标数组（echoview 方法需要）
    ping_time = ds_Sv["ping_time"].values
    range_sample = ds_Sv["range_sample"].values

    # 计算深度坐标（使用 echo_range 或 depth）
    if "depth" in ds_Sv:
        idim = ds_Sv["depth"].isel(ping_time=0).values
    elif "echo_range" in ds_Sv:
        idim = ds_Sv["echo_range"].isel(ping_time=0).values
    else:
        idim = range_sample.astype(float)

    jdim = ping_time.astype(float)

    # 确保坐标是单调递增的
    if len(idim) > 1 and idim[0] > idim[-1]:
        idim = idim[::-1]
    if len(jdim) > 1 and jdim[0] > jdim[-1]:
        jdim = jdim[::-1]

    params = {
        "var_name": "Sv",
        "channel": channel,
        "idim": idim,
        "jdim": jdim,
        "thr": school_cfg.get("thr", -55.0),
        "mincan": tuple(school_cfg.get("mincan", [3.0, 10.0])),
        "maxlink": tuple(school_cfg.get("maxlink", [3.0, 15.0])),
        "minsho": tuple(school_cfg.get("minsho", [3.0, 15.0])),
    }

    logger.info(f"鸡群检测: method={method}, thr={params['thr']}")
    mask = detect_shoal(ds_Sv, method=method, params=params)

    n_detected = int(mask.sum().values)
    logger.info(f"检测到 {n_detected} 个鱼群像素")

    return mask


def schools_to_dataframe(
    mask: xr.DataArray,
    ds_Sv: xr.Dataset,
) -> pd.DataFrame:
    """
    将鱼群 mask 转换为 DataFrame，每个鱼群一行

    使用 scipy.ndimage.label 进行连通区域标记
    """
    from scipy import ndimage

    # 连通区域标记
    labeled, num_features = ndimage.label(mask.values)

    if num_features == 0:
        return pd.DataFrame(columns=[
            "school_id", "ping_start", "ping_end",
            "depth_start", "depth_end", "area",
            "mean_sv", "centroid_depth",
        ])

    # 获取坐标
    ping_time = ds_Sv["ping_time"].values
    if "depth" in ds_Sv:
        depth = ds_Sv["depth"].isel(ping_time=0).values
    elif "echo_range" in ds_Sv:
        depth = ds_Sv["echo_range"].isel(ping_time=0).values
    else:
        depth = np.arange(ds_Sv.dims["range_sample"], dtype=float)

    Sv = ds_Sv["Sv"].values

    records = []
    for i in range(1, num_features + 1):
        region = labeled == i
        rows, cols = np.where(region)

        if len(rows) == 0:
            continue

        ping_start = ping_time[rows.min()]
        ping_end = ping_time[rows.max()]

        depth_idx_min = cols.min()
        depth_idx_max = cols.max()
        depth_start = depth[depth_idx_min] if depth_idx_min < len(depth) else depth_idx_min
        depth_end = depth[depth_idx_max] if depth_idx_max < len(depth) else depth_idx_max

        # 计算面积（像素数 × 分辨率）
        n_pixels = int(region.sum())
        ping_res = float(np.diff(ping_time[:2])[0]) if len(ping_time) > 1 else 1.0
        depth_res = float(np.diff(depth[:2])[0]) if len(depth) > 1 else 1.0
        area = n_pixels * abs(ping_res) * abs(depth_res)

        # 计算平均 Sv
        sv_values = Sv[region]
        sv_values = sv_values[np.isfinite(sv_values)]
        mean_sv = float(np.mean(sv_values)) if len(sv_values) > 0 else np.nan

        # 中心深度
        centroid_depth = float(depth[rows.mean().astype(int)]) if len(rows) > 0 else np.nan

        records.append({
            "school_id": i,
            "ping_start": ping_start,
            "ping_end": ping_end,
            "depth_start": depth_start,
            "depth_end": depth_end,
            "area": area,
            "mean_sv": mean_sv,
            "centroid_depth": centroid_depth,
        })

    df = pd.DataFrame(records)
    logger.info(f"识别到 {len(df)} 个鱼群")
    return df
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/test_school.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/school.py tests/test_school.py
git commit -m "feat: 鱼群识别模块 — detect_shoal + 连通区域标记"
```

---

## Task 4: 密度估算模块 (density.py)

**Files:**
- Create: `src/density.py`
- Create: `tests/test_density.py`

- [ ] **Step 1: 创建 tests/test_density.py — 写失败测试**

```python
"""密度估算模块测试"""

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from src.density import calculate_nasc, estimate_density


def _make_mock_data():
    """创建模拟数据"""
    np.random.seed(42)
    n_pings = 100
    n_samples = 50

    Sv = np.random.uniform(-80, -40, (n_pings, n_samples))
    Sv[20:40, 10:30] = np.random.uniform(-55, -45, (20, 20))

    ds_Sv = xr.Dataset({
        "Sv": xr.DataArray(
            Sv,
            dims=["ping_time", "range_sample"],
            coords={
                "ping_time": np.arange(n_pings),
                "range_sample": np.arange(n_samples),
            },
        ),
        "echo_range": xr.DataArray(
            np.tile(np.arange(n_samples) * 0.5, (n_pings, 1)),
            dims=["ping_time", "range_sample"],
        ),
    })

    schools_df = pd.DataFrame({
        "school_id": [1],
        "ping_start": [20],
        "ping_end": [39],
        "depth_start": [5.0],
        "depth_end": [14.5],
        "area": [200.0],
        "mean_sv": [-50.0],
        "centroid_depth": [10.0],
    })

    return ds_Sv, schools_df


def test_calculate_nasc():
    """测试 NASC 计算"""
    ds_Sv, _ = _make_mock_data()
    config = {
        "processing": {"frequencies": [38000]},
        "density": {"ts_default": -30.0},
    }
    nasc_df = calculate_nasc(ds_Sv, config)
    assert isinstance(nasc_df, pd.DataFrame)
    assert "nasc" in nasc_df.columns
    assert "transect_id" in nasc_df.columns


def test_estimate_density():
    """测试密度估算"""
    ds_Sv, schools_df = _make_mock_data()
    config = {
        "processing": {"frequencies": [38000]},
        "density": {"ts_default": -30.0},
    }
    density_df = estimate_density(schools_df, ds_Sv, config)
    assert isinstance(density_df, pd.DataFrame)
    assert "density_ind_ha" in density_df.columns
    assert "total_biomass_kg" in density_df.columns
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/test_density.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: 创建 src/density.py — 实现**

```python
"""密度估算模块：NASC → 鱼类密度"""

import logging

import numpy as np
import pandas as pd
import xarray as xr

logger = logging.getLogger("fish_acoustics")


def calculate_nasc(ds_Sv: xr.Dataset, config: dict) -> pd.DataFrame:
    """
    计算 Nautical Area Scattering Coefficient (NASC)

    NASC = 4π × (1852)^2 × ∫ Sv_linear dz

    Parameters
    ----------
    ds_Sv : xr.Dataset
        包含 Sv 和 echo_range 的数据集
    config : dict
        配置字典

    Returns
    -------
    pd.DataFrame
        包含 transect_id 和 nasc 的 DataFrame
    """
    Sv = ds_Sv["Sv"].values  # (ping_time, range_sample)

    # 获取深度分辨率
    if "echo_range" in ds_Sv:
        echo_range = ds_Sv["echo_range"].values
        # 计算每个采样单元的厚度
        if echo_range.ndim == 2:
            dr = np.diff(echo_range, axis=1)
            dr = np.column_stack([dr, dr[:, -1:]])
        else:
            dr = np.diff(echo_range)
            dr = np.append(dr, dr[-1])
    else:
        dr = np.ones_like(Sv)

    # Sv 转线性
    Sv_linear = 10 ** (Sv / 10)

    # 积分
    Sv_linear = np.where(np.isfinite(Sv_linear), Sv_linear, 0)
    integrated = np.nansum(Sv_linear * np.abs(dr), axis=1)

    # NASC = 4π × (1852)^2 × integrated
    nasc = 4 * np.pi * (1852 ** 2) * integrated

    ping_time = ds_Sv["ping_time"].values
    n_pings = len(ping_time)

    # 默认整个数据为一个 transect
    transect_id = np.ones(n_pings, dtype=int)

    df = pd.DataFrame({
        "transect_id": transect_id,
        "ping_idx": np.arange(n_pings),
        "ping_time": ping_time,
        "nasc": nasc,
    })

    logger.info(f"NASC 计算完成: mean={np.nanmean(nasc):.2f}")
    return df


def estimate_density(
    schools_df: pd.DataFrame,
    ds_Sv: xr.Dataset,
    config: dict,
) -> pd.DataFrame:
    """
    基于 NASC 和 TS 估算鱼类密度

    密度公式: ρ = NASC / (4π × 10^(TS/10) × 10000)
    其中 ρ 单位为 ind/ha

    Parameters
    ----------
    schools_df : pd.DataFrame
        鱼群清单
    ds_Sv : xr.Dataset
        Sv 数据集
    config : dict
        配置字典

    Returns
    -------
    pd.DataFrame
        密度估算结果
    """
    ts_default = config.get("density", {}).get("ts_default", -30.0)

    # 计算 NASC
    nasc_df = calculate_nasc(ds_Sv, config)

    # 合并鱼群信息
    if schools_df.empty:
        # 无鱼群，基于全 transect 计算
        total_nasc = nasc_df["nasc"].sum()
        sigma_bs = 10 ** (ts_default / 10)
        density = total_nasc / (4 * np.pi * sigma_bs * 10000)

        result = pd.DataFrame({
            "transect_id": [1],
            "depth_layer": ["all"],
            "nasc": [total_nasc],
            "density_ind_ha": [density],
            "total_biomass_kg": [density * 0.5],  # 假设平均体重 0.5kg
        })
    else:
        # 按鱼群计算
        records = []
        for _, school in schools_df.iterrows():
            school_nasc = nasc_df[
                (nasc_df["ping_idx"] >= school["ping_start"])
                & (nasc_df["ping_idx"] <= school["ping_end"])
            ]["nasc"].sum()

            sigma_bs = 10 ** (ts_default / 10)
            density = school_nasc / (4 * np.pi * sigma_bs * 10000)

            depth_layer = f"{school['depth_start']:.1f}-{school['depth_end']:.1f}m"

            records.append({
                "transect_id": 1,
                "school_id": school["school_id"],
                "depth_layer": depth_layer,
                "nasc": school_nasc,
                "density_ind_ha": density,
                "total_biomass_kg": density * 0.5,  # 假设平均体重 0.5kg
            })

        result = pd.DataFrame(records)

    logger.info(f"密度估算完成: {len(result)} 条记录")
    return result
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/test_density.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/density.py tests/test_density.py
git commit -m "feat: 密度估算模块 — NASC 计算与密度转换"
```

---

## Task 5: 可视化模块 (viz.py)

**Files:**
- Create: `src/viz.py`
- Create: `tests/test_viz.py`

- [ ] **Step 1: 创建 tests/test_viz.py — 写失败测试**

```python
"""可视化模块测试"""

import matplotlib
matplotlib.use("Agg")  # 非交互后端

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from src.viz import plot_echogram, plot_density_profile, plot_school_overlay


def _make_mock_data():
    """创建模拟数据"""
    np.random.seed(42)
    Sv = np.random.uniform(-80, -40, (50, 100))
    ds_Sv = xr.Dataset({
        "Sv": xr.DataArray(
            Sv,
            dims=["ping_time", "range_sample"],
            coords={
                "ping_time": np.arange(50),
                "range_sample": np.arange(100),
            },
        ),
        "bottom_depth": xr.DataArray(
            np.linspace(40, 45, 50),
            dims=["ping_time"],
            coords={"ping_time": np.arange(50)},
        ),
    })
    return ds_Sv


def test_plot_echogram(tmp_path):
    """测试 echogram 绘制"""
    ds_Sv = _make_mock_data()
    fig = plot_echogram(ds_Sv, save_path=str(tmp_path / "echogram.png"))
    assert fig is not None
    assert (tmp_path / "echogram.png").exists()


def test_plot_density_profile(tmp_path):
    """测试密度剖面图"""
    density_df = pd.DataFrame({
        "transect_id": [1, 1, 1],
        "depth_layer": ["0-5m", "5-10m", "10-15m"],
        "density_ind_ha": [100, 200, 50],
    })
    fig = plot_density_profile(density_df, save_path=str(tmp_path / "density.png"))
    assert fig is not None
    assert (tmp_path / "density.png").exists()


def test_plot_school_overlay(tmp_path):
    """测试鱼群叠加图"""
    ds_Sv = _make_mock_data()
    mask = xr.DataArray(
        np.zeros((50, 100), dtype=bool),
        dims=["ping_time", "range_sample"],
        coords={"ping_time": np.arange(50), "range_sample": np.arange(100)},
    )
    mask.values[10:20, 30:50] = True

    fig = plot_school_overlay(ds_Sv, mask, save_path=str(tmp_path / "overlay.png"))
    assert fig is not None
    assert (tmp_path / "overlay.png").exists()
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/test_viz.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: 创建 src/viz.py — 实现**

```python
"""可视化模块：echogram、鱼群分布图、密度剖面图"""

import logging
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr

logger = logging.getLogger("fish_acoustics")

# 中文字体支持
plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def plot_echogram(
    ds_Sv: xr.Dataset,
    save_path: Optional[str] = None,
    vmin: float = -80,
    vmax: float = -40,
    title: str = "Echogram (Sv)",
) -> plt.Figure:
    """
    绘制声学图 (echogram)

    Parameters
    ----------
    ds_Sv : xr.Dataset
        包含 Sv 变量的数据集
    save_path : str, optional
        保存路径
    vmin, vmax : float
        Sv 显示范围 (dB)
    title : str
        图表标题

    Returns
    -------
    plt.Figure
    """
    Sv = ds_Sv["Sv"].values

    fig, ax = plt.subplots(figsize=(14, 6))
    im = ax.imshow(
        Sv.T,
        aspect="auto",
        origin="upper",
        cmap="jet",
        vmin=vmin,
        vmax=vmax,
        interpolation="nearest",
    )

    # 绘制底部
    if "bottom_depth" in ds_Sv:
        bottom = ds_Sv["bottom_depth"].values
        if "echo_range" in ds_Sv:
            echo_range = ds_Sv["echo_range"].values
            if echo_range.ndim == 2:
                echo_range = echo_range[:, 0]
            # 将深度转换为采样索引
            dr = np.mean(np.diff(echo_range))
            bottom_idx = bottom / dr
        else:
            bottom_idx = bottom
        ax.plot(bottom_idx, "w-", linewidth=1.5, label="底部")

    ax.set_xlabel("Ping")
    ax.set_ylabel("Range Sample")
    ax.set_title(title)

    cbar = fig.colorbar(im, ax=ax, label="Sv (dB)")

    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        logger.info(f"保存 echogram: {save_path}")

    return fig


def plot_school_overlay(
    ds_Sv: xr.Dataset,
    mask: xr.DataArray,
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    绘制 echogram + 鱼群标记叠加图
    """
    fig = plot_echogram(ds_Sv, save_path=None)

    # 叠加鱼群 mask 边界
    ax = fig.axes[0]
    mask_data = mask.values.astype(float)
    ax.contour(mask_data, levels=[0.5], colors="white", linewidths=0.8)

    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        logger.info(f"保存鱼群叠加图: {save_path}")

    return fig


def plot_density_profile(
    density_df: pd.DataFrame,
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    绘制密度剖面图
    """
    fig, ax = plt.subplots(figsize=(8, 6))

    if "density_ind_ha" in density_df.columns:
        ax.barh(
            density_df["depth_layer"],
            density_df["density_ind_ha"],
            color="steelblue",
        )
        ax.set_xlabel("密度 (ind/ha)")
        ax.set_ylabel("深度层")
        ax.set_title("鱼类密度剖面")

    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        logger.info(f"保存密度剖面图: {save_path}")

    return fig


def generate_all_plots(
    ds_Sv: xr.Dataset,
    mask: xr.DataArray,
    density_df: pd.DataFrame,
    config: dict,
) -> None:
    """生成所有图表"""
    output_dir = Path(config["output"]["dir"])
    reservoir_name = config["reservoir"]["name"]

    # echogram
    plot_echogram(
        ds_Sv,
        save_path=str(output_dir / f"{reservoir_name}_echogram.png"),
        title=f"{reservoir_name} — Echogram (Sv)",
    )
    plt.close()

    # 鱼群叠加图
    plot_school_overlay(
        ds_Sv, mask,
        save_path=str(output_dir / f"{reservoir_name}_schools.png"),
    )
    plt.close()

    # 密度剖面图
    plot_density_profile(
        density_df,
        save_path=str(output_dir / f"{reservoir_name}_density.png"),
    )
    plt.close()

    logger.info(f"所有图表已保存到: {output_dir}")
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/test_viz.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/viz.py tests/test_viz.py
git commit -m "feat: 可视化模块 — echogram、鱼群叠加、密度剖面"
```

---

## Task 6: CLI 入口 (cli.py)

**Files:**
- Create: `src/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: 创建 src/cli.py — 实现**

```python
"""CLI 入口：串联所有模块"""

import sys
from pathlib import Path

import click

from src.utils import load_config, validate_config, setup_logging, get_output_dir


@click.group()
def main():
    """EK80 淡水鱼类资源评估系统"""
    pass


@main.command()
@click.argument("config_path", type=click.Path(exists=True))
@click.option("--step", type=click.Choice(["acoustic", "school", "density", "viz", "all"]), default="all")
@click.option("--skip-to", type=click.Choice(["acoustic", "school", "density", "viz"]), default=None)
def run(config_path: str, step: str, skip_to: str):
    """运行处理流水线"""
    # 加载配置
    config = load_config(config_path)
    validate_config(config)

    reservoir_name = config["reservoir"]["name"]
    output_dir = get_output_dir(config)
    logger = setup_logging(reservoir_name, str(output_dir))

    logger.info(f"开始处理: {reservoir_name}")
    logger.info(f"步骤: {step}, 跳到: {skip_to}")

    # 确定执行步骤
    steps = ["acoustic", "school", "density", "viz"]
    if skip_to:
        start_idx = steps.index(skip_to)
        steps = steps[start_idx:]
    elif step != "all":
        steps = [step]

    # 执行流水线
    ds_Sv = None
    mask = None
    schools_df = None
    density_df = None

    for current_step in steps:
        try:
            if current_step == "acoustic":
                from src.acoustic import process_all_files
                logger.info("=== 步骤 1: 声学处理 ===")
                ds_Sv = process_all_files(config)
                # 保存中间结果
                sv_path = output_dir / "sv_data.nc"
                ds_Sv.to_netcdf(sv_path)
                logger.info(f"Sv 数据已保存: {sv_path}")

            elif current_step == "school":
                from src.school import detect_schools, schools_to_dataframe
                import xarray as xr

                if ds_Sv is None:
                    sv_path = output_dir / "sv_data.nc"
                    if sv_path.exists():
                        logger.info("加载已保存的 Sv 数据...")
                        ds_Sv = xr.open_dataset(sv_path)
                    else:
                        logger.error("未找到 Sv 数据，请先运行 acoustic 步骤")
                        sys.exit(1)

                logger.info("=== 步骤 2: 鱼群识别 ===")
                mask = detect_schools(ds_Sv, config)
                schools_df = schools_to_dataframe(mask, ds_Sv)

                # 保存
                schools_df.to_csv(output_dir / "schools.csv", index=False, encoding="utf-8-sig")
                logger.info(f"鱼群数据已保存: {output_dir / 'schools.csv'}")

            elif current_step == "density":
                from src.density import estimate_density
                import pandas as pd
                import xarray as xr

                if ds_Sv is None:
                    sv_path = output_dir / "sv_data.nc"
                    if sv_path.exists():
                        ds_Sv = xr.open_dataset(sv_path)
                    else:
                        logger.error("未找到 Sv 数据，请先运行 acoustic 步骤")
                        sys.exit(1)

                if schools_df is None:
                    schools_path = output_dir / "schools.csv"
                    if schools_path.exists():
                        schools_df = pd.read_csv(schools_path)
                    else:
                        schools_df = pd.DataFrame()

                logger.info("=== 步骤 3: 密度估算 ===")
                density_df = estimate_density(schools_df, ds_Sv, config)

                density_df.to_csv(output_dir / "density.csv", index=False, encoding="utf-8-sig")
                logger.info(f"密度数据已保存: {output_dir / 'density.csv'}")

            elif current_step == "viz":
                from src.viz import generate_all_plots
                import pandas as pd
                import xarray as xr
                import numpy as np

                if ds_Sv is None:
                    sv_path = output_dir / "sv_data.nc"
                    if sv_path.exists():
                        ds_Sv = xr.open_dataset(sv_path)
                    else:
                        logger.error("未找到 Sv 数据，请先运行 acoustic 步骤")
                        sys.exit(1)

                if mask is None:
                    # 创建空 mask
                    mask = xr.DataArray(
                        np.zeros(
                            (len(ds_Sv["ping_time"]), len(ds_Sv["range_sample"])),
                            dtype=bool,
                        ),
                        dims=["ping_time", "range_sample"],
                    )

                if density_df is None:
                    density_path = output_dir / "density.csv"
                    if density_path.exists():
                        density_df = pd.read_csv(density_path)
                    else:
                        density_df = pd.DataFrame()

                logger.info("=== 步骤 4: 可视化 ===")
                generate_all_plots(ds_Sv, mask, density_df, config)

        except Exception as e:
            logger.error(f"步骤 {current_step} 失败: {e}")
            if step == "all":
                logger.info("继续下一个步骤...")
                continue
            else:
                sys.exit(1)

    logger.info("处理完成!")


@main.command()
@click.argument("config_path", type=click.Path(exists=True))
def status(config_path: str):
    """查看处理状态"""
    config = load_config(config_path)
    output_dir = Path(config["output"]["dir"])

    print(f"水库: {config['reservoir']['name']}")
    print(f"输出目录: {output_dir}")
    print()

    # 检查各步骤的输出文件
    files = {
        "声学处理 (Sv)": output_dir / "sv_data.nc",
        "鸡群识别": output_dir / "schools.csv",
        "密度估算": output_dir / "density.csv",
        "echogram": output_dir / f"{config['reservoir']['name']}_echogram.png",
        "鱼群图": output_dir / f"{config['reservoir']['name']}_schools.png",
        "密度图": output_dir / f"{config['reservoir']['name']}_density.png",
    }

    for name, path in files.items():
        status = "✓ 已完成" if path.exists() else "✗ 未完成"
        print(f"  {name}: {status}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 创建 tests/test_cli.py**

```python
"""CLI 测试"""

import pytest
from click.testing import CliRunner

from src.cli import main


def test_cli_help():
    """测试 CLI 帮助信息"""
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "EK80" in result.output


def test_cli_run_help():
    """测试 run 子命令帮助"""
    runner = CliRunner()
    result = runner.invoke(main, ["run", "--help"])
    assert result.exit_code == 0
    assert "config_path" in result.output


def test_cli_status_config_not_found():
    """测试 status 命令配置文件不存在"""
    runner = CliRunner()
    result = runner.invoke(main, ["status", "nonexistent.yaml"])
    assert result.exit_code != 0
```

- [ ] **Step 3: 运行测试验证通过**

Run: `pytest tests/test_cli.py -v`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add src/cli.py tests/test_cli.py
git commit -m "feat: CLI 入口 — run/status 命令"
```

---

## Task 7: Windows 编码修复与集成测试

**Files:**
- Modify: `src/acoustic.py` (添加编码修复)
- Create: `tests/test_integration.py`

- [ ] **Step 1: 修复 echopype Windows 编码问题**

在 `src/acoustic.py` 顶部添加环境变量修复：

```python
"""声学处理模块：raw → Sv → 噪声去除 → 底部检测"""

import logging
import os

# 修复 echopype 在 Windows 中文环境的 YAML 编码问题
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from pathlib import Path
from typing import List

import numpy as np
import xarray as xr

logger = logging.getLogger("fish_acoustics")
```

- [ ] **Step 2: 创建 tests/test_integration.py**

```python
"""集成测试：使用 echopype 示例数据"""

import pytest
import tempfile
from pathlib import Path

from src.utils import load_config, validate_config


@pytest.mark.skipif(
    not Path("D:/data/test/raw").exists(),
    reason="测试数据目录不存在"
)
def test_full_pipeline():
    """完整流水线测试（需要真实数据）"""
    config = {
        "reservoir": {"name": "集成测试", "region": "测试"},
        "input": {"raw_dir": "D:/data/test/raw", "pattern": "*.raw"},
        "processing": {
            "frequencies": [38000],
            "waveform_mode": "CW",
            "encode_mode": "power",
            "noise_removal": {"ping_num": 5, "range_sample_num": 10},
            "bottom_detection": {"method": "basic", "threshold": -50.0},
        },
        "school_detection": {
            "method": "echoview",
            "thr": -60.0,
            "mincan": [2.0, 5.0],
            "maxlink": [2.0, 10.0],
            "minsho": [2.0, 10.0],
        },
        "density": {"ts_default": -30.0},
        "output": {"dir": tempfile.mkdtemp(), "formats": ["csv"]},
    }

    # 验证配置
    validate_config(config)

    # 声学处理
    from src.acoustic import process_all_files
    ds_Sv = process_all_files(config)
    assert ds_Sv is not None
    assert "Sv" in ds_Sv

    # 鱼群识别
    from src.school import detect_schools, schools_to_dataframe
    mask = detect_schools(ds_Sv, config)
    schools_df = schools_to_dataframe(mask, ds_Sv)

    # 密度估算
    from src.density import estimate_density
    density_df = estimate_density(schools_df, ds_Sv, config)
    assert "density_ind_ha" in density_df.columns
```

- [ ] **Step 3: 运行全部测试**

Run: `pytest tests/ -v`
Expected: PASS (跳过需要真实数据的测试)

- [ ] **Step 4: 提交**

```bash
git add src/acoustic.py tests/test_integration.py
git commit -m "fix: Windows 编码修复 + 集成测试"
```

---

## Task 8: README 与文档

**Files:**
- Create: `README.md`

- [ ] **Step 1: 创建 README.md**

```markdown
# EK80 淡水鱼类资源评估系统

基于 [echopype](https://github.com/OSOceanAcoustics/echopype) 的端到端 EK80 声学数据处理工具。

## 功能

- **声学处理**: raw → Sv 计算 → 噪声去除 → 底部检测
- **鸡群识别**: 基于 Sv 阈值的鸡群检测与聚类
- **密度估算**: NASC → 鱼类密度 (ind/ha) → 生物量估算
- **可视化**: echogram、鱼群分布图、密度剖面图

## 安装

```bash
pip install -e .
```

## 使用

```bash
# 运行完整流水线
fish-acoustics run configs/shanmei.yaml

# 只运行声学处理
fish-acoustics run configs/shanmei.yaml --step acoustic

# 查看处理状态
fish-acoustics status configs/shanmei.yaml
```

## 配置文件

参考 `configs/example.yaml`，为每个水库创建独立配置。

## 项目结构

```
src/
├── acoustic.py     # 声学处理
├── school.py       # 鸡群识别
├── density.py      # 密度估算
├── viz.py          # 可视化
├── cli.py          # CLI 入口
└── utils.py        # 通用工具
```
```

- [ ] **Step 2: 提交**

```bash
git add README.md
git commit -m "docs: README 与使用说明"
```

---

## 执行顺序

1. Task 1: 项目脚手架与配置加载
2. Task 2: 声学处理模块
3. Task 3: 鱼群识别模块
4. Task 4: 密度估算模块
5. Task 5: 可视化模块
6. Task 6: CLI 入口
7. Task 7: Windows 编码修复与集成测试
8. Task 8: README 与文档
