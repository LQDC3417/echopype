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
