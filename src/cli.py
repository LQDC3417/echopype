"""CLI 入口 — fish-acoustics 命令行工具"""

import os

os.environ["PYTHONUTF8"] = "1"

import click

from src.core.utils import load_config, validate_config, setup_logging, get_output_dir


@click.group()
@click.version_option(version="0.1.0", prog_name="fish-acoustics")
def main():
    """EK80 淡水鱼类资源评估系统 CLI"""


@main.command()
@click.argument("config_path", type=click.Path(exists=True))
@click.option("--step", default="all", help="运行步骤: acoustic, school, density, gui, all")
def run(config_path, step):
    """运行处理流水线或启动 GUI

    \b
    示例:
        fish-acoustics run configs/shanmei.yaml
        fish-acoustics run configs/shanmei.yaml --step acoustic
        fish-acoustics run configs/shanmei.yaml --step gui
    """
    if step == "gui":
        from src.app import main as gui_main
        gui_main()
        return

    config = load_config(config_path)
    validate_config(config)

    reservoir_name = config["reservoir"]["name"]
    output_dir = get_output_dir(config)
    setup_logging(reservoir_name, str(output_dir))

    if step in ("all", "acoustic"):
        _run_acoustic(config)

    if step in ("all", "school"):
        _run_school(config)

    if step in ("all", "density"):
        _run_density(config)


def _run_acoustic(config):
    """声学处理步骤"""
    click.echo("=" * 50)
    click.echo("[1/3] 声学处理")
    click.echo("=" * 50)

    from src.core.acoustic import process_all_files

    ds_Sv = process_all_files(config)
    output_dir = get_output_dir(config)

    # 保存 Sv 数据集
    sv_path = output_dir / f"{config['reservoir']['name']}_Sv.nc"
    ds_Sv.to_netcdf(sv_path)
    click.echo(f"  Sv 数据集已保存: {sv_path}")

    # 保存为配置中的临时状态（通过全局方式）
    _run_acoustic._ds_Sv = ds_Sv


def _run_school(config):
    """鱼群识别步骤"""
    click.echo("=" * 50)
    click.echo("[2/3] 鱼群识别")
    click.echo("=" * 50)

    ds_Sv = getattr(_run_acoustic, "_ds_Sv", None)
    if ds_Sv is None:
        # 尝试从已有的 netcdf 加载
        import xarray as xr
        output_dir = get_output_dir(config)
        sv_path = output_dir / f"{config['reservoir']['name']}_Sv.nc"
        if sv_path.exists():
            ds_Sv = xr.open_dataset(sv_path)
        else:
            click.echo("错误: 请先运行声学处理 (--step acoustic)")
            return

    from src.core.school import detect_schools, schools_to_dataframe

    mask = detect_schools(ds_Sv, config)
    schools_df = schools_to_dataframe(mask, ds_Sv)

    output_dir = get_output_dir(config)
    schools_df.to_csv(
        output_dir / f"{config['reservoir']['name']}_schools.csv",
        index=False, encoding="utf-8-sig",
    )
    click.echo(f"  检测到 {len(schools_df)} 个鱼群")

    _run_acoustic._ds_Sv = ds_Sv
    _run_acoustic._schools_df = schools_df
    _run_acoustic._mask = mask


def _run_density(config):
    """密度估算步骤"""
    click.echo("=" * 50)
    click.echo("[3/3] 密度估算")
    click.echo("=" * 50)

    ds_Sv = getattr(_run_acoustic, "_ds_Sv", None)
    schools_df = getattr(_run_acoustic, "_schools_df", None)

    if ds_Sv is None:
        import xarray as xr
        output_dir = get_output_dir(config)
        sv_path = output_dir / f"{config['reservoir']['name']}_Sv.nc"
        if sv_path.exists():
            ds_Sv = xr.open_dataset(sv_path)
        else:
            click.echo("错误: 请先运行声学处理 (--step acoustic)")
            return

    if schools_df is None:
        # 没有鱼群也继续算（走全 transect 路径）
        import pandas as pd
        schools_df = pd.DataFrame()

    from src.core.density import estimate_density

    density_df = estimate_density(schools_df, ds_Sv, config)

    output_dir = get_output_dir(config)
    density_df.to_csv(
        output_dir / f"{config['reservoir']['name']}_density.csv",
        index=False, encoding="utf-8-sig",
    )

    for _, row in density_df.iterrows():
        click.echo(
            f"  深度层: {row['depth_layer']} | "
            f"ABC: {row['abc']:.6f} m²/m² | "
            f"密度: {row['density_ind_ha']:.2f} ind/ha"
        )


@main.command()
@click.argument("config_path", type=click.Path(exists=True))
def status(config_path):
    """查看处理状态"""
    config = load_config(config_path)
    output_dir = get_output_dir(config)
    reservoir_name = config["reservoir"]["name"]

    click.echo(f"水库: {reservoir_name}")
    click.echo(f"输出目录: {output_dir}")

    files = {
        "Sv 数据集": output_dir / f"{reservoir_name}_Sv.nc",
        "鱼群清单": output_dir / f"{reservoir_name}_schools.csv",
        "密度结果": output_dir / f"{reservoir_name}_density.csv",
    }

    for label, path in files.items():
        status_text = "✅ 已生成" if path.exists() else "❌ 未生成"
        click.echo(f"  {label}: {status_text}")


@main.command()
def gui():
    """启动图形界面"""
    from src.app import main as gui_main
    gui_main()
