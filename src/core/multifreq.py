"""多频率分析模块：多通道管理、频率对比、transect 分段

职责：
- 列出数据集中的可用频率/通道
- 按频率提取子集
- 多频率联合分析（频率响应、目标分类辅助）
- Transect 分段（按时间间隔或 ping 数量）
"""

import logging

import numpy as np
import pandas as pd
import xarray as xr

logger = logging.getLogger("fish_acoustics")


# ── 通道/频率管理 ──────────────────────────────────────────

def list_channels(ds_Sv: xr.Dataset) -> list[str]:
    """列出数据集中的所有通道名称。

    Returns
    -------
    list[str]
        通道名称列表
    """
    if "channel" not in ds_Sv.dims:
        return []
    return [str(c) for c in ds_Sv["channel"].values]


def get_frequency(ds_Sv: xr.Dataset, channel: str) -> float | None:
    """获取指定通道的标称频率 (Hz)。

    Returns
    -------
    float or None
        频率 (Hz)，未找到时返回 None
    """
    if "frequency_nominal" in ds_Sv:
        freq_var = ds_Sv["frequency_nominal"]
        if "channel" in freq_var.dims:
            idx = list(ds_Sv["channel"].values).index(channel)
            return float(freq_var.values[idx])
    return None


def select_channel(ds_Sv: xr.Dataset, channel: str) -> xr.Dataset:
    """选择指定通道的数据子集。

    Parameters
    ----------
    ds_Sv : xr.Dataset
    channel : str
        通道名称

    Returns
    -------
    xr.Dataset
        只包含指定通道的数据集（channel 维度被移除）
    """
    if "channel" not in ds_Sv.dims:
        return ds_Sv
    return ds_Sv.sel(channel=channel)


def get_channel_summary(ds_Sv: xr.Dataset) -> pd.DataFrame:
    """获取所有通道的摘要信息。

    Returns
    -------
    pd.DataFrame
        每行一个通道，包含 channel, frequency, n_pings, n_samples
    """
    channels = list_channels(ds_Sv)
    if not channels:
        return pd.DataFrame(columns=["channel", "frequency_Hz", "n_pings", "n_samples"])

    records = []
    for ch in channels:
        freq = get_frequency(ds_Sv, ch)
        n_pings = ds_Sv.sizes.get("ping_time", 0)
        n_samples = ds_Sv.sizes.get("range_sample", 0)
        records.append({
            "channel": ch,
            "frequency_Hz": freq,
            "n_pings": n_pings,
            "n_samples": n_samples,
        })

    return pd.DataFrame(records)


# ── Transect 分段 ──────────────────────────────────────────

def split_transects(
    ds_Sv: xr.Dataset,
    method: str = "time_gap",
    max_gap_s: float = 60.0,
    pings_per_transect: int | None = None,
) -> np.ndarray:
    """将数据按 transect 分段。

    Parameters
    ----------
    ds_Sv : xr.Dataset
    method : str
        分段方法：
        - "time_gap": 按时间间隔分段（间隔 > max_gap_s 视为新 transect）
        - "fixed_length": 按固定 ping 数分段
    max_gap_s : float
        时间间隔阈值（秒），仅 method="time_gap" 时有效
    pings_per_transect : int, optional
        每个 transect 的 ping 数，仅 method="fixed_length" 时有效

    Returns
    -------
    np.ndarray
        transect_id 数组，shape=(n_pings,)
    """
    ping_time = ds_Sv["ping_time"].values
    n_pings = len(ping_time)

    if n_pings == 0:
        return np.array([], dtype=int)

    if method == "time_gap":
        return _split_by_time_gap(ping_time, max_gap_s)
    elif method == "fixed_length":
        if pings_per_transect is None:
            pings_per_transect = 1000
        return _split_by_fixed_length(n_pings, pings_per_transect)
    else:
        raise ValueError(f"不支持的分段方法: {method}")


def _split_by_time_gap(ping_time: np.ndarray, max_gap_s: float) -> np.ndarray:
    """按时间间隔分段。"""
    n_pings = len(ping_time)
    transect_ids = np.zeros(n_pings, dtype=int)

    if n_pings <= 1:
        return transect_ids

    current_id = 0
    for i in range(1, n_pings):
        if np.issubdtype(ping_time.dtype, np.datetime64):
            gap = (ping_time[i] - ping_time[i - 1]) / np.timedelta64(1, 's')
        else:
            gap = float(ping_time[i] - ping_time[i - 1])

        if gap > max_gap_s:
            current_id += 1
        transect_ids[i] = current_id

    n_transects = current_id + 1
    logger.info(f"Transect 分段完成: {n_transects} 个 transect (方法=time_gap, 阈值={max_gap_s}s)")
    return transect_ids


def _split_by_fixed_length(n_pings: int, pings_per_transect: int) -> np.ndarray:
    """按固定 ping 数分段。"""
    transect_ids = np.arange(n_pings) // pings_per_transect
    n_transects = transect_ids[-1] + 1 if n_pings > 0 else 0
    logger.info(f"Transect 分段完成: {n_transects} 个 transect (方法=fixed_length, 每段={pings_per_transect} pings)")
    return transect_ids


# ── 多频率对比 ──────────────────────────────────────────

def compare_frequencies(
    ds_Sv: xr.Dataset,
    config: dict,
    channels: list[str] | None = None,
) -> pd.DataFrame:
    """多频率 ABC 对比分析。

    Parameters
    ----------
    ds_Sv : xr.Dataset
    config : dict
    channels : list[str], optional
        要对比的通道列表，默认使用所有通道

    Returns
    -------
    pd.DataFrame
        每行一个通道，包含 channel, frequency, mean_abc 等
    """
    from src.core.density import calculate_abc

    if channels is None:
        channels = list_channels(ds_Sv)

    if len(channels) < 2:
        logger.warning("少于 2 个通道，无法进行频率对比")
        return pd.DataFrame()

    records = []
    for ch in channels:
        ds_ch = select_channel(ds_Sv, ch)
        freq = get_frequency(ds_Sv, ch)

        abc_df = calculate_abc(ds_ch, config)
        mean_abc = float(abc_df["abc"].mean())

        records.append({
            "channel": ch,
            "frequency_Hz": freq,
            "mean_abc": mean_abc,
            "std_abc": float(abc_df["abc"].std()),
            "max_abc": float(abc_df["abc"].max()),
        })

    result = pd.DataFrame(records)
    logger.info(f"多频率对比完成: {len(result)} 个通道")
    return result


def compute_sv_per_channel(
    ds_Sv: xr.Dataset,
    echodata,
    config: dict,
) -> dict[str, xr.Dataset]:
    """为每个通道分别计算 Sv（用于多频率独立处理）。

    Parameters
    ----------
    ds_Sv : xr.Dataset
        含所有通道的 Sv 数据集
    echodata : echopype.EchoData
    config : dict

    Returns
    -------
    dict[str, xr.Dataset]
        {channel_name: single_channel_ds_Sv}
    """

    channels = list_channels(ds_Sv)
    result = {}

    for ch in channels:
        ds_ch = select_channel(ds_Sv, ch)
        # 深度信息需要从 echodata 重新计算
        from src.core.acoustic import _add_depth
        ds_ch = _add_depth(ds_ch, echodata)
        result[ch] = ds_ch
        logger.info(f"通道 {ch} Sv 计算完成")

    return result
