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
