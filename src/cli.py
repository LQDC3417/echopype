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
        "鱼群识别": output_dir / "schools.csv",
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
