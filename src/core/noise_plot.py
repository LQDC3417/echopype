"""噪声可视化检查模块：生成噪声去除效果的检查图

参考：Matecho 的检查图生成功能

功能：
- 原始 Sv vs 噪声估计对比图
- SNR 分布图
- 噪声随 ping 变化图
- 去噪前后对比图
"""

import logging
from pathlib import Path

import numpy as np
import xarray as xr

logger = logging.getLogger("fish_acoustics")


def plot_noise_check(
    ds_Sv: xr.Dataset,
    save_dir: str | Path | None = None,
    show: bool = False,
) -> dict[str, str]:
    """生成噪声检查图

    Parameters
    ----------
    ds_Sv : xr.Dataset
        包含噪声信息的数据集（需要先调用 apply_noise_reduction）
    save_dir : str or Path, optional
        保存目录。如果为 None，使用当前目录。
    show : bool
        是否显示图形

    Returns
    -------
    dict[str, str]
        保存的文件路径字典
    """
    try:
        import matplotlib.pyplot as plt
        
    except ImportError:
        logger.warning("matplotlib 未安装，跳过噪声检查图生成")
        return {}

    if "noise_per_ping" not in ds_Sv:
        logger.warning("数据集中无噪声信息，跳过检查图生成")
        return {}

    # 设置中文字体
    plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False

    save_dir = Path(save_dir) if save_dir else Path(".")
    save_dir.mkdir(parents=True, exist_ok=True)

    saved_files = {}

    # 1. 噪声随 ping 变化图
    fig, ax = plt.subplots(figsize=(12, 4))
    noise_per_ping = ds_Sv["noise_per_ping"].values
    ping_idx = np.arange(len(noise_per_ping))

    ax.plot(ping_idx, noise_per_ping, 'b-', linewidth=0.5, alpha=0.7)
    ax.axhline(y=np.nanmean(noise_per_ping), color='r', linestyle='--',
               label=f'均值: {np.nanmean(noise_per_ping):.1f} dB')
    ax.set_xlabel("Ping 索引")
    ax.set_ylabel("噪声估计 (dB)")
    ax.set_title("噪声随 Ping 变化")
    ax.legend()
    ax.grid(True, alpha=0.3)

    filepath = save_dir / "noise_per_ping.png"
    fig.savefig(filepath, dpi=150, bbox_inches='tight')
    saved_files["noise_per_ping"] = str(filepath)
    if not show:
        plt.close(fig)
    logger.info(f"噪声变化图已保存: {filepath}")

    # 2. SNR 分布图
    if "SNR" in ds_Sv:
        fig, ax = plt.subplots(figsize=(8, 5))
        snr = ds_Sv["SNR"].values
        snr_valid = snr[np.isfinite(snr)]

        if len(snr_valid) > 0:
            ax.hist(snr_valid, bins=100, edgecolor='none', alpha=0.7)
            ax.axvline(x=3.0, color='r', linestyle='--', label='SNR 阈值 = 3 dB')
            ax.set_xlabel("SNR (dB)")
            ax.set_ylabel("样本数")
            ax.set_title("SNR 分布")
            ax.legend()
            ax.grid(True, alpha=0.3)

            filepath = save_dir / "snr_distribution.png"
            fig.savefig(filepath, dpi=150, bbox_inches='tight')
            saved_files["snr_distribution"] = str(filepath)
            if not show:
                plt.close(fig)
            logger.info(f"SNR 分布图已保存: {filepath}")

    # 3. 去噪前后对比图（取中间 ping 的剖面）
    if "Sv" in ds_Sv and "Sv_corrected" in ds_Sv:
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))

        n_pings = ds_Sv.sizes["ping_time"]
        mid_ping = n_pings // 2

        depth = None
        if "depth" in ds_Sv:
            depth_data = ds_Sv["depth"]
            if "channel" in depth_data.dims:
                depth_data = depth_data.isel(channel=0)
            if "ping_time" in depth_data.dims:
                depth = depth_data.isel(ping_time=mid_ping).values
            else:
                depth = depth_data.values

        if depth is None:
            depth = np.arange(ds_Sv.sizes["range_sample"])

        # 获取原始和去噪后的 Sv
        sv_orig = ds_Sv["Sv"]
        sv_corr = ds_Sv["Sv_corrected"]

        if "channel" in sv_orig.dims:
            sv_orig = sv_orig.isel(channel=0)
        if "channel" in sv_corr.dims:
            sv_corr = sv_corr.isel(channel=0)

        sv_orig_ping = sv_orig.isel(ping_time=mid_ping).values
        sv_corr_ping = sv_corr.isel(ping_time=mid_ping).values

        # 左图：原始 vs 去噪
        axes[0].plot(sv_orig_ping, depth, 'b-', alpha=0.5, label='原始 Sv')
        axes[0].plot(sv_corr_ping, depth, 'r-', alpha=0.7, label='去噪后 Sv')
        axes[0].set_xlabel("Sv (dB)")
        axes[0].set_ylabel("深度 (m)")
        axes[0].set_title(f"Ping {mid_ping} 剖面")
        axes[0].legend()
        axes[0].grid(True, alpha=0.3)
        axes[0].invert_yaxis()

        # 右图：噪声剖面
        if "noise_Sv" in ds_Sv:
            noise_ping = ds_Sv["noise_Sv"].isel(ping_time=mid_ping).values
            axes[1].plot(noise_ping, depth, 'g-', linewidth=2, label='噪声估计')
            axes[1].set_xlabel("噪声 (dB)")
            axes[1].set_ylabel("深度 (m)")
            axes[1].set_title(f"Ping {mid_ping} 噪声剖面")
            axes[1].legend()
            axes[1].grid(True, alpha=0.3)
            axes[1].invert_yaxis()

        filepath = save_dir / "noise_comparison.png"
        fig.savefig(filepath, dpi=150, bbox_inches='tight')
        saved_files["noise_comparison"] = str(filepath)
        if not show:
            plt.close(fig)
        logger.info(f"去噪对比图已保存: {filepath}")

    # 4. 噪声热力图
    if "noise_Sv" in ds_Sv:
        fig, ax = plt.subplots(figsize=(12, 4))
        noise_2d = ds_Sv["noise_Sv"].values

        # 降采样显示
        step_p = max(1, noise_2d.shape[0] // 200)
        step_r = max(1, noise_2d.shape[1] // 100)
        noise_display = noise_2d[::step_p, ::step_r]

        im = ax.imshow(noise_display.T, aspect='auto', cmap='viridis',
                       origin='upper', interpolation='nearest')
        ax.set_xlabel("Ping 索引")
        ax.set_ylabel("样本索引")
        ax.set_title("噪声热力图")
        plt.colorbar(im, ax=ax, label="噪声 (dB)")

        filepath = save_dir / "noise_heatmap.png"
        fig.savefig(filepath, dpi=150, bbox_inches='tight')
        saved_files["noise_heatmap"] = str(filepath)
        if not show:
            plt.close(fig)
        logger.info(f"噪声热力图已保存: {filepath}")

    if show:
        plt.show()

    return saved_files


def print_noise_report(ds_Sv: xr.Dataset) -> None:
    """打印噪声去除报告到日志

    Parameters
    ----------
    ds_Sv : xr.Dataset
        包含噪声信息的数据集
    """
    from src.core.noise import noise_statistics

    stats = noise_statistics(ds_Sv)

    logger.info("=" * 60)
    logger.info("噪声去除报告")
    logger.info("=" * 60)

    if stats.get("status") != "ok":
        logger.info("  无噪声数据")
        return

    logger.info(f"  处理 ping 数: {stats['n_pings']}")
    logger.info(f"  噪声均值: {stats['noise_mean']:.1f} dB")
    logger.info(f"  噪声标准差: {stats['noise_std']:.1f} dB")
    logger.info(f"  噪声范围: [{stats['noise_min']:.1f}, {stats['noise_max']:.1f}] dB")
    logger.info(f"  噪声中位数: {stats['noise_median']:.1f} dB")

    if "snr_mean" in stats:
        logger.info(f"  SNR 均值: {stats['snr_mean']:.1f} dB")
        logger.info(f"  SNR 标准差: {stats['snr_std']:.1f} dB")
        logger.info(f"  SNR < 3 dB 样本数: {stats['snr_below_threshold']}")

    logger.info("=" * 60)
