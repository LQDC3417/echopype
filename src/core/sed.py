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
    ts = ds_TS["TS"].values
    if ts.ndim == 3:
        ts = ts[0]  # (n_pings, n_samples)
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
    echo_range = None
    dr = 0.003  # 默认采样间距（米）
    if "echo_range" in ds_TS:
        er = ds_TS["echo_range"].values
        while er.ndim > 1:
            er = er[0]
        valid = np.isfinite(er)
        if np.any(valid):
            vidx = np.where(valid)[0]
            if len(vidx) >= 2:
                dr = float((er[vidx[1]] - er[vidx[0]]) / (vidx[1] - vidx[0]))
        echo_range = np.arange(len(er), dtype=np.float64) * dr

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
            if echo_range is not None:
                depth_m = float(echo_range[peak_idx])
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
                "range_m": depth_m if echo_range is not None else float(peak_idx),
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
        logger.info(f"真实 SED 检测到 {len(df)} 个单体目标")
        return df
    return pd.DataFrame(columns=[
        "target_id", "ping_idx", "sample_idx", "range_m", "ts_db",
        "ts_uncompensated_db", "alongship_deg", "athwartship_deg",
        "pulse_len", "norm_pulse", "beam_comp_db", "angle_std_deg",
    ])
