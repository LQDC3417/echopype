"""真实单体目标检测（Split-beam SED）模块

参照 Echoview 的 Single Target Detection 算法，基于分裂波束原始复采样实现：
1. 阈值触发 → 回波候选（逐 ping 沿 range 扫描）
2. 峰值 + 脉冲长度判据（PLDL + 归一化脉冲长度）
3. 分裂波束测角（沿船/横向电相位 → 机械角）
4. 角度标准差过滤（单目标回波角度稳定，多目标相位抖动）
5. 波束方向图补偿 + 最大补偿过滤

数据要求：EK80 分裂波束复采样（backscatter_r/i，4 象限）+ compute_TS 输出。
"""

import logging

import numpy as np
import pandas as pd
import xarray as xr

logger = logging.getLogger("fish_acoustics")


def compute_split_beam_angles(
    complex_samples: np.ndarray,
    angle_sensitivity_along: float,
    angle_sensitivity_athw: float,
    angle_offset_along: float = 0.0,
    angle_offset_athw: float = 0.0,
) -> tuple:
    """逐样本计算沿船/横向机械角（度）。

    Parameters
    ----------
    complex_samples : np.ndarray
        shape=(n_samples, 4) 复数数组（4 象限复采样）
    angle_sensitivity_along : float
        沿船角度灵敏度（电角度度/机械角度，EK80 通常约 23）
    angle_sensitivity_athw : float
        横向角度灵敏度
    angle_offset_along / angle_offset_athw : float
        机械角偏移（度）

    Returns
    -------
    (angles_alongship, angles_athwartship) : (np.ndarray, np.ndarray)
        机械角（度），shape=(n_samples,)
    """
    q1, q2, q3, q4 = (
        complex_samples[:, 0],
        complex_samples[:, 1],
        complex_samples[:, 2],
        complex_samples[:, 3],
    )
    # 象限配对（beam 顺序: [fore-port, fore-star, aft-port, aft-star]）
    # 沿船（前后）：前半个 (Q1+Q2) vs 后半个 (Q3+Q4)
    # 横向（左右）：右舷 (Q2+Q4) vs 左舷 (Q1+Q3)
    fore = q1 + q2
    aft = q3 + q4
    star = q2 + q4
    port = q1 + q3

    # 电相位（弧度）
    phi_along = np.angle(fore * np.conj(aft))
    phi_athw = np.angle(star * np.conj(port))

    # 电角度（度）→ 机械角（度），再补偿偏移
    along = np.degrees(phi_along) / angle_sensitivity_along + angle_offset_along
    athw = np.degrees(phi_athw) / angle_sensitivity_athw + angle_offset_athw
    return along, athw


def beam_compensation(angle_deg: np.ndarray, beamwidth_deg: float) -> np.ndarray:
    """波束方向图补偿（dB），Gaussian 近似：comp = 6.0206 * (2θ/θ3dB)^2。

    离轴目标回波被波束压低，补偿量为正 dB 加到峰值 TS 上。
    """
    theta = np.abs(angle_deg)
    return 6.0206 * (2.0 * theta / beamwidth_deg) ** 2


def _detect_ping_candidates(
    ts_ping: np.ndarray,
    threshold_db: float,
    pldl_db: float,
    pulse_len_samples: float,
    min_norm_pulse: float,
    max_norm_pulse: float,
) -> list:
    """检测单个 ping 的回波候选（阈值 + 脉冲长度判据）。

    Parameters
    ----------
    ts_ping : np.ndarray
        该 ping 的未补偿 TS（dB），shape=(n_samples,)
    threshold_db : float
        TS 阈值（dB）
    pldl_db : float
        脉冲长度判定电平（dB，相对峰值）
    pulse_len_samples : float
        发射脉冲长度（samples）
    min_norm_pulse / max_norm_pulse : float
        归一化脉冲长度范围

    Returns
    -------
    list of dict
        每个候选：{peak_idx, peak_ts, pulse_len, norm_pulse, left, right}
    """
    above = ts_ping > threshold_db
    candidates = []
    n = len(above)
    i = 0
    while i < n:
        if above[i]:
            start = i
            while i < n and above[i]:
                i += 1
            end = i - 1
            seg = ts_ping[start:end + 1]
            peak_rel = int(np.argmax(seg))
            peak_idx = start + peak_rel
            peak_ts = float(seg[peak_rel])

            # 在 PLDL 电平处测量脉冲长度（从峰值向两边扩展）
            level = peak_ts - pldl_db
            left = peak_idx
            while left > start and ts_ping[left - 1] >= level:
                left -= 1
            right = peak_idx
            while right < end and ts_ping[right + 1] >= level:
                right += 1
            pulse_len = right - left + 1
            norm_pulse = pulse_len / pulse_len_samples

            if min_norm_pulse <= norm_pulse <= max_norm_pulse:
                candidates.append({
                    "peak_idx": peak_idx,
                    "peak_ts": peak_ts,
                    "pulse_len": pulse_len,
                    "norm_pulse": norm_pulse,
                    "left": left,
                    "right": right,
                })
        else:
            i += 1
    return candidates


def detect_single_targets_real(
    echodata,
    ds_TS,
    config: dict,
    channel_id: str | None = None,
) -> pd.DataFrame:
    """真实单体目标检测主函数。

    Parameters
    ----------
    echodata : EchoData
        原始数据（含 4 象限复采样 + 校准参数）
    ds_TS : xr.Dataset
        compute_TS 输出（未补偿 TS）
    config : dict
        需含 single_target_real 子项：
        - ts_threshold_db: float, 默认 -50.0
        - pldl_db: float, 默认 6.0
        - min_norm_pulse: float, 默认 0.8
        - max_norm_pulse: float, 默认 1.5
        - max_angle_std_deg: float, 默认 0.6
        - max_beam_comp_db: float, 默认 3.0
        - min_depth_m / max_depth_m: 可选检测深度范围

    Returns
    -------
    pd.DataFrame
        target_id, ping_idx, sample_idx, range_m, ts_db（补偿后）,
        ts_uncompensated_db, alongship_deg, athwartship_deg,
        pulse_len, norm_pulse, beam_comp_db, angle_std_deg
    """
    cfg = config.get("single_target_real", {})
    ts_threshold = float(cfg.get("ts_threshold_db", -50.0))
    pldl = float(cfg.get("pldl_db", 6.0))
    min_norm = float(cfg.get("min_norm_pulse", 0.8))
    max_norm = float(cfg.get("max_norm_pulse", 1.5))
    max_angle_std = float(cfg.get("max_angle_std_deg", 0.6))
    max_beam_comp = float(cfg.get("max_beam_comp_db", 3.0))
    min_depth_m = cfg.get("min_depth_m")
    max_depth_m = cfg.get("max_depth_m")

    # 1. 提取数据
    bg = echodata["Sonar/Beam_group1"]
    ts_data = ds_TS["TS"]
    def select_channel(data, label):
        values = list(data["channel"].values if isinstance(data, xr.Dataset) else data.channel.values)
        lookup = {
            value.decode("utf-8") if isinstance(value, bytes) else str(value): value
            for value in values
        }
        if label is None:
            if len(values) != 1:
                raise ValueError("多通道 SED 必须指定 channel_id")
            label = next(iter(lookup))
        if str(label) not in lookup:
            raise ValueError(f"SED 输入中不存在所选通道：{label}")
        return data.sel(channel=lookup[str(label)]), str(label)

    if "channel" in ts_data.dims:
        ts_data, channel_id = select_channel(ts_data, channel_id)
    if "channel" in bg.dims:
        bg, channel_id = select_channel(bg, channel_id)
    ts = ts_data.transpose("ping_time", "range_sample").values
    n_pings, n_samples = ts.shape

    # 复采样 (n_pings, n_samples, 4)
    complex_data = None
    if "backscatter_r" in bg and "backscatter_i" in bg:
        real = bg["backscatter_r"].values
        imag = bg["backscatter_i"].values
        if real.ndim == 4:
            real = real[0]
            imag = imag[0]
        complex_data = real + 1j * imag

    # 校准参数
    angle_sens_along = float(bg["angle_sensitivity_alongship"].values.flat[0]) if "angle_sensitivity_alongship" in bg else 23.0
    angle_sens_athw = float(bg["angle_sensitivity_athwartship"].values.flat[0]) if "angle_sensitivity_athwartship" in bg else 23.0
    angle_off_along = float(bg["angle_offset_alongship"].values.flat[0]) if "angle_offset_alongship" in bg else 0.0
    angle_off_athw = float(bg["angle_offset_athwartship"].values.flat[0]) if "angle_offset_athwartship" in bg else 0.0
    beamwidth = float(bg["beamwidth_twoway_alongship"].values.flat[0]) if "beamwidth_twoway_alongship" in bg else 7.0

    # 脉冲长度（samples）
    if "transmit_duration_nominal" in bg and "sample_interval" in bg:
        tau = float(bg["transmit_duration_nominal"].values.flat[0])
        sample_int = float(bg["sample_interval"].values.flat[0])
        pulse_len_samples = tau / sample_int if sample_int > 0 else 32.0
    else:
        pulse_len_samples = 32.0

    # echo_range（用于深度）
    # 注意：部分 EK80 数据 compute_TS 的 echo_range 坐标仅覆盖前段，
    # 之后为 NaN。从有效段推导采样间距 Δr，重建完整 range。
    if "echo_range" not in ds_TS:
        raise ValueError("SED 需要 echo_range 米制坐标，不能用采样索引代替距离")
    er_data = ds_TS["echo_range"]
    if "channel" in er_data.dims:
        if channel_id is None:
            raise ValueError("SED 距离坐标存在多通道但未指定 channel_id")
        er_data, _ = select_channel(er_data, channel_id)
    ranges = er_data.broadcast_like(ts_data).transpose("ping_time", "range_sample").values.copy()
    for er in ranges:
        valid = np.isfinite(er)
        if np.count_nonzero(valid) >= 2:
            vidx = np.where(valid)[0]
            dr = float((er[vidx[1]] - er[vidx[0]]) / (vidx[1] - vidx[0]))
            first_valid = int(vidx[0])
            er[~valid] = (er[first_valid] + (np.arange(len(er)) - first_valid) * dr)[~valid]
    depths = ranges
    if "depth" in ds_TS:
        depth_data = ds_TS["depth"]
        if "channel" in depth_data.dims:
            if channel_id is None:
                raise ValueError("SED 深度坐标存在多通道但未指定 channel_id")
            depth_data, _ = select_channel(depth_data, channel_id)
        depths = depth_data.broadcast_like(ts_data).transpose("ping_time", "range_sample").values

    logger.info(
        f"SED 参数: threshold={ts_threshold} dB, PLDL={pldl} dB, "
        f"norm_pulse=[{min_norm},{max_norm}], pulse={pulse_len_samples:.1f} samples, "
        f"angle_sens={angle_sens_along:.1f}, beamwidth={beamwidth:.1f} deg"
    )

    # 2. 逐 ping 检测
    records = []
    for ping in range(n_pings):
        candidates = _detect_ping_candidates(
            ts[ping], ts_threshold, pldl, pulse_len_samples, min_norm, max_norm
        )
        for cand in candidates:
            peak_idx = cand["peak_idx"]
            left, right = cand["left"], cand["right"]

            # 深度范围过滤
            range_m = float(ranges[ping, peak_idx])
            depth_m = float(depths[ping, peak_idx])
            if not np.isfinite(range_m) or not np.isfinite(depth_m):
                continue
            if min_depth_m is not None and depth_m < min_depth_m:
                continue
            if max_depth_m is not None and depth_m > max_depth_m:
                continue

            # 分裂波束测角（脉冲窗口内逐样本）
            if complex_data is not None:
                window = complex_data[ping, left:right + 1, :]
                if len(window) >= 2:
                    along, athw = compute_split_beam_angles(
                        window, angle_sens_along, angle_sens_athw,
                        angle_off_along, angle_off_athw,
                    )
                    # 去除 NaN/极端值后统计
                    valid = np.isfinite(along) & np.isfinite(athw)
                    if np.count_nonzero(valid) >= 2:
                        along_mean = float(np.nanmean(along))
                        athw_mean = float(np.nanmean(athw))
                        # 角度标准差（组合幅度）
                        std = float(np.nanstd(along[valid]) ** 2 + np.nanstd(athw[valid]) ** 2) ** 0.5
                    else:
                        along_mean = athw_mean = float("nan")
                        std = float("inf")
                else:
                    along_mean = athw_mean = float("nan")
                    std = float("inf")
            else:
                along_mean = athw_mean = float("nan")
                std = float("inf")

            # 角度标准差过滤（单目标回波角度稳定）
            if std > max_angle_std:
                continue

            # 波束补偿
            comp_db = 0.0
            if np.isfinite(along_mean) and np.isfinite(athw_mean):
                comp_db = float(beam_compensation(along_mean, beamwidth)
                                + beam_compensation(athw_mean, beamwidth))
            if comp_db > max_beam_comp:
                continue

            ts_compensated = cand["peak_ts"] + comp_db

            records.append({
                "ping_idx": ping,
                "sample_idx": peak_idx,
                "range_m": range_m,
                "depth_m": depth_m,
                "ts_db": ts_compensated,
                "ts_uncompensated_db": cand["peak_ts"],
                "alongship_deg": along_mean,
                "athwartship_deg": athw_mean,
                "pulse_len": cand["pulse_len"],
                "norm_pulse": cand["norm_pulse"],
                "beam_comp_db": comp_db,
                "angle_std_deg": std,
            })

    if records:
        df = pd.DataFrame(records)
        df.insert(0, "target_id", range(1, len(df) + 1))
        if channel_id is not None:
            df.insert(1, "channel", str(channel_id))
        logger.info(f"真实 SED 检测到 {len(df)} 个单体目标")
        return df
    return pd.DataFrame(columns=[
        "target_id", "channel", "ping_idx", "sample_idx", "range_m", "depth_m", "ts_db",
        "ts_uncompensated_db", "alongship_deg", "athwartship_deg",
        "pulse_len", "norm_pulse", "beam_comp_db", "angle_std_deg",
    ])


def filter_targets_by_region(
    targets_df: pd.DataFrame,
    upper_depth_m: np.ndarray | None,
    lower_depth_m: np.ndarray | None,
) -> pd.DataFrame:
    """按全局 ping 的上下边界过滤 SED 目标。

    边界缺失、交叉、目标 ping 无法映射或深度越界时均排除目标。
    两个边界均为 ``None`` 时保持原结果。
    """
    if upper_depth_m is None and lower_depth_m is None:
        return targets_df.copy()
    if upper_depth_m is None or lower_depth_m is None:
        raise ValueError("SED region requires both upper and lower boundaries")

    upper = np.asarray(upper_depth_m, dtype=float).reshape(-1)
    lower = np.asarray(lower_depth_m, dtype=float).reshape(-1)
    if len(upper) != len(lower):
        raise ValueError("SED region boundaries must have equal ping counts")
    if targets_df.empty:
        return targets_df.copy()
    if "ping_idx" not in targets_df or "range_m" not in targets_df:
        raise ValueError("SED targets require ping_idx and range_m columns")

    ping_values = pd.to_numeric(targets_df["ping_idx"], errors="coerce").to_numpy()
    depth_values = pd.to_numeric(targets_df.get("depth_m", targets_df["range_m"]), errors="coerce").to_numpy()
    integer_ping = np.isfinite(ping_values) & (ping_values == np.floor(ping_values))
    ping_indices = np.zeros(len(targets_df), dtype=np.int64)
    ping_indices[integer_ping] = ping_values[integer_ping].astype(np.int64)
    valid_ping = integer_ping & (ping_indices >= 0) & (ping_indices < len(upper))

    selected_upper = np.full(len(targets_df), np.nan, dtype=float)
    selected_lower = np.full(len(targets_df), np.nan, dtype=float)
    selected_upper[valid_ping] = upper[ping_indices[valid_ping]]
    selected_lower[valid_ping] = lower[ping_indices[valid_ping]]
    keep = (
        valid_ping
        & np.isfinite(depth_values)
        & np.isfinite(selected_upper)
        & np.isfinite(selected_lower)
        & (selected_upper < selected_lower)
        & (depth_values >= selected_upper)
        & (depth_values <= selected_lower)
    )
    return targets_df.loc[keep].copy().reset_index(drop=True)


def aggregate_targets_to_grid(
    targets_df: pd.DataFrame,
    ds_Sv: xr.Dataset,
    config: dict,
) -> pd.DataFrame:
    """将 SED 检测目标按回声积分网格聚合，输出每网格的 TS 统计。

    复用回声积分的网格定义（ESU 类型/大小 + 层宽），保证与积分结果
    一一对应可对齐合并。每个网格单元输出：
    - n_targets: 检测目标数
    - ts_mean: 目标 TS 均值（线性域能量平均后转 dB）
    - ts_std / ts_min / ts_max: TS 离散度与范围（dB）
    - interval / layer: 与积分表对齐的网格索引
    - ping_start / ping_end / depth_start / depth_end: 网格范围
    - center_lat / center_lon: 网格中心经纬度（distance 模式有 GPS 时）

    Parameters
    ----------
    targets_df : pd.DataFrame
        detect_single_targets_real 的输出（含 ping_idx, range_m, ts_db）
    ds_Sv : xr.Dataset
        Sv 数据集（含 echo_range / GPS）
    config : dict
        配置字典（integration 子项定义网格）

    Returns
    -------
    pd.DataFrame
        每行一个网格单元（含无目标单元，TS 统计为 NaN）
    """
    from src.core.integration import ESUType, _extract_gps, create_integration_grid

    integ_cfg = config.get("integration", {})
    esu_type = ESUType(integ_cfg.get("esu_type", "pings"))
    esu_size = float(integ_cfg.get("esu_size", 500))
    layer_width = float(integ_cfg.get("layer_width", 5.0))

    grid = create_integration_grid(
        ds_Sv,
        esu_type=esu_type,
        esu_size=esu_size,
        layer_width=layer_width,
    )

    # 目标 → 网格单元映射
    interval_idx = np.searchsorted(grid.ping_end, targets_df["ping_idx"].values, side="right")
    target_depth = targets_df.get("depth_m", targets_df["range_m"]).values
    layer_idx = np.searchsorted(grid.depth_end, target_depth, side="right")

    # 越界目标剔除（ping 超出最后 interval、深度超出最后 layer）
    valid = (
        (interval_idx < grid.n_intervals)
        & (layer_idx < grid.n_layers)
        & (target_depth >= grid.depth_start[0])
    )
    interval_idx = interval_idx[valid]
    layer_idx = layer_idx[valid]
    ts_valid = targets_df["ts_db"].values[valid]

    # GPS 中心（每 interval 取 ping 范围中点的经纬度）
    lat_arr, lon_arr = _extract_gps(ds_Sv)
    center_lat, center_lon = {}, {}
    if lat_arr is not None and lon_arr is not None:
        for i in range(grid.n_intervals):
            p0 = grid.ping_start[i]
            p1 = min(grid.ping_end[i], len(lat_arr)) - 1
            lat_slice = lat_arr[p0:p1 + 1]
            lon_slice = lon_arr[p0:p1 + 1]
            lat_valid = lat_slice[np.isfinite(lat_slice)]
            lon_valid = lon_slice[np.isfinite(lon_slice)]
            if len(lat_valid) > 0 and len(lon_valid) > 0:
                center_lat[i] = float(np.mean(lat_valid))
                center_lon[i] = float(np.mean(lon_valid))

    records = []
    for i in range(grid.n_intervals):
        for j in range(grid.n_layers):
            cell_mask = (interval_idx == i) & (layer_idx == j)
            ts_cell = ts_valid[cell_mask]

            row = {
                "interval": i,
                "layer": j,
                "ping_start": int(grid.ping_start[i]),
                "ping_end": int(grid.ping_end[i]),
                "depth_start": float(grid.depth_start[j]),
                "depth_end": float(grid.depth_end[j]),
                "n_targets": int(len(ts_cell)),
                "ts_mean": float("nan"),
                "ts_std": float("nan"),
                "ts_min": float("nan"),
                "ts_max": float("nan"),
                "center_lat": center_lat.get(i, float("nan")),
                "center_lon": center_lon.get(i, float("nan")),
            }
            if len(ts_cell) > 0:
                ts_finite = ts_cell[np.isfinite(ts_cell)]
                if len(ts_finite) > 0:
                    # 线性域能量平均再转回 dB
                    row["ts_mean"] = float(10.0 * np.log10(np.mean(10.0 ** (ts_finite / 10.0))))
                    row["ts_std"] = float(np.std(ts_finite))
                    row["ts_min"] = float(np.min(ts_finite))
                    row["ts_max"] = float(np.max(ts_finite))
            records.append(row)

    df = pd.DataFrame(records)
    logger.info(
        f"SED 网格聚合完成: {grid.n_intervals}×{grid.n_layers} 单元，"
        f"共 {len(ts_valid)} 个目标归入网格"
    )
    return df
