"""高级鱼群提取模块：空间聚类 + 跨 ping 连接

参考：Matecho EchoGroupExtraction.m
功能：
- 逐 ping 阈值化
- 深度方向聚类（MaxDistDep）
- 跨 ping segment linking（前向+后向）
- 迁移区域特殊处理（日出/日落）
- 鱼群描述符计算（面积、长度、高度、形态特征）
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import xarray as xr

from src.core.utils import depth_resolution, get_sv_array, get_vertical_coords, ping_resolution

logger = logging.getLogger("fish_acoustics")


@dataclass
class Segment:
    """单个 segment（一个 ping 内的连续有效区域）"""
    depth_min: float
    depth_max: float
    ping_idx: int
    label: int = -1  # 所属鱼群标签


@dataclass
class ShoalGroup:
    """鱼群（由多个 segment 连接而成）"""
    id: int
    segments: list[Segment] = field(default_factory=list)

    @property
    def ping_start(self) -> int:
        return min(s.ping_idx for s in self.segments)

    @property
    def ping_end(self) -> int:
        return max(s.ping_idx for s in self.segments)

    @property
    def depth_min(self) -> float:
        return min(s.depth_min for s in self.segments)

    @property
    def depth_max(self) -> float:
        return max(s.depth_max for s in self.segments)

    @property
    def n_pings(self) -> int:
        return len({s.ping_idx for s in self.segments})

    @property
    def height(self) -> float:
        return self.depth_max - self.depth_min

    @property
    def length_pings(self) -> int:
        return self.ping_end - self.ping_start + 1


@dataclass
class ShoalExtractionResult:
    """鱼群提取结果"""
    shoals: list[ShoalGroup]
    mask: np.ndarray  # bool mask, shape=(n_pings, n_samples)
    labeled: np.ndarray  # labeled mask, shape=(n_pings, n_samples)


def _extract_segments_for_ping(
    sv_ping: np.ndarray,
    depth: np.ndarray,
    ping_idx: int,
    min_threshold: float,
    max_depth_dist: float,
    bottom_depth: float | None = None,
    label_counter: int = 0,
) -> list[Segment]:
    """对单个 ping 进行阈值化并提取 segment

    Parameters
    ----------
    sv_ping : np.ndarray
        单个 ping 的 Sv 数据，shape=(n_samples,)
    depth : np.ndarray
        深度数组，shape=(n_samples,)
    ping_idx : int
        当前 ping 索引
    min_threshold : float
        最小阈值 (dB)
    max_depth_dist : float
        最大深度间隔 (米)，超过此间隔分为不同 segment
    bottom_depth : float, optional
        底部深度 (米)，超过底部的样本被排除
    label_counter : int
        标签计数器起始值

    Returns
    -------
    list[Segment]
        提取的 segment 列表
    """
    # 阈值化
    valid_mask = (sv_ping >= min_threshold) & np.isfinite(sv_ping)

    # 底部以下排除
    if bottom_depth is not None and np.isfinite(bottom_depth):
        valid_mask[depth >= bottom_depth] = False

    if not np.any(valid_mask):
        return []

    # 找到有效样本的深度
    valid_depths = depth[valid_mask]

    # 按深度方向聚类（间隔 > max_depth_dist 分为不同 segment）
    segments = []
    if len(valid_depths) == 0:
        return segments

    # 排序深度
    sorted_depths = np.sort(valid_depths)

    # 按深度间隔分组
    current_min = sorted_depths[0]
    current_max = sorted_depths[0]
    current_label = label_counter

    for i in range(1, len(sorted_depths)):
        if sorted_depths[i] - sorted_depths[i-1] > max_depth_dist:
            # 间隔过大，结束当前 segment，开始新的
            segments.append(Segment(
                depth_min=current_min,
                depth_max=current_max,
                ping_idx=ping_idx,
                label=current_label,
            ))
            current_label += 1
            current_min = sorted_depths[i]
            current_max = sorted_depths[i]
        else:
            current_max = sorted_depths[i]

    # 添加最后一个 segment
    segments.append(Segment(
        depth_min=current_min,
        depth_max=current_max,
        ping_idx=ping_idx,
        label=current_label,
    ))

    return segments


def _link_segments_forward(
    current_segments: list[Segment],
    previous_segments: list[Segment],
    max_depth_dist: float,
    max_time_gap: int,
    current_ping: int,
) -> None:
    """前向连接：将当前 ping 的 segment 与前几个 ping 的 segment 连接

    Parameters
    ----------
    current_segments : list[Segment]
        当前 ping 的 segment 列表
    previous_segments : list[Segment]
        前几个 ping 的 segment 列表
    max_depth_dist : float
        最大深度间隔 (米)
    max_time_gap : int
        最大时间间隔 (ping 数)
    current_ping : int
        当前 ping 索引
    """
    for curr_seg in current_segments:
        best_match = None
        best_overlap = 0

        for prev_seg in previous_segments:
            # 检查时间间隔
            if current_ping - prev_seg.ping_idx > max_time_gap:
                continue

            # 计算深度重叠
            overlap_min = max(curr_seg.depth_min, prev_seg.depth_min)
            overlap_max = min(curr_seg.depth_max, prev_seg.depth_max)
            overlap = max(0, overlap_max - overlap_min)

            # 检查是否在深度容差内
            depth_gap = min(
                abs(curr_seg.depth_min - prev_seg.depth_max),
                abs(curr_seg.depth_max - prev_seg.depth_min),
            )

            if overlap > 0 or depth_gap <= max_depth_dist:
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_match = prev_seg

        if best_match is not None:
            # 继承前一个 segment 的标签
            curr_seg.label = best_match.label


def extract_shoals_advanced(
    ds_Sv: xr.Dataset,
    config: dict,
    bottom_depth_m: np.ndarray | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> ShoalExtractionResult:
    """高级鱼群提取（参考 Matecho）

    Parameters
    ----------
    ds_Sv : xr.Dataset
        Sv 数据集
    config : dict
        配置字典，需包含 school_detection 子项
    bottom_depth_m : np.ndarray, optional
        底部深度数组 (米)，shape=(n_pings,)
    progress_callback : callable, optional
        进度回调函数

    Returns
    -------
    ShoalExtractionResult
        提取结果
    """
    school_cfg = config.get("school_detection", {})

    # 参数
    min_threshold = school_cfg.get("min_threshold", -60.0)
    max_depth_dist = school_cfg.get("max_depth_distance", 0.1)  # 米
    max_ping_dist = school_cfg.get("max_ping_distance", 1)  # ping 数
    max_time_gap = school_cfg.get("max_time_gap", 20)  # ping 数
    min_shoal_pings = school_cfg.get("min_shoal_pings", 3)
    min_shoal_height = school_cfg.get("min_shoal_height", 0.5)  # 米

    # 获取数据
    Sv = get_sv_array(ds_Sv)  # (n_pings, n_samples)
    depth = get_vertical_coords(ds_Sv)  # (n_samples,)
    n_pings, n_samples = Sv.shape


    # Step 1: 逐 ping 提取 segment
    all_segments: list[list[Segment]] = []
    label_counter = 0

    for ping_idx in range(n_pings):
        bot = bottom_depth_m[ping_idx] if bottom_depth_m is not None else None
        segments = _extract_segments_for_ping(
            Sv[ping_idx, :], depth, ping_idx,
            min_threshold, max_depth_dist, bot, label_counter,
        )
        all_segments.append(segments)
        label_counter += len(segments)

        if progress_callback:
            progress_callback(ping_idx + 1, n_pings * 2)

    logger.info(f"Step 1 完成: 提取了 {label_counter} 个初始 segment")

    # Step 2: 前向连接（跨 ping linking）
    max_lookback = min(max_ping_dist + 1, 10)  # 向前看的 ping 数

    for ping_idx in range(1, n_pings):
        current_segments = all_segments[ping_idx]
        if not current_segments:
            continue

        # 收集前几个 ping 的 segment
        previous_segments = []
        for lookback in range(1, min(max_lookback + 1, ping_idx + 1)):
            prev_ping = ping_idx - lookback
            previous_segments.extend(all_segments[prev_ping])

        if previous_segments:
            _link_segments_forward(
                current_segments, previous_segments,
                max_depth_dist, max_time_gap, ping_idx,
            )

        if progress_callback:
            progress_callback(n_pings + ping_idx + 1, n_pings * 2)

    logger.info("Step 2 完成: 前向连接")

    # Step 3: 构建鱼群（合并相同标签的 segment）
    label_to_shoal: dict[int, ShoalGroup] = {}
    shoal_id_counter = 0

    for ping_segments in all_segments:
        for seg in ping_segments:
            if seg.label in label_to_shoal:
                label_to_shoal[seg.label].segments.append(seg)
            else:
                shoal = ShoalGroup(id=shoal_id_counter, segments=[seg])
                label_to_shoal[seg.label] = shoal
                shoal_id_counter += 1

    # Step 4: 过滤小鱼群
    shoals = []
    for shoal in label_to_shoal.values():
        if shoal.n_pings >= min_shoal_pings and shoal.height >= min_shoal_height:
            shoals.append(shoal)

    logger.info(f"Step 3-4 完成: {len(shoals)} 个鱼群（过滤前 {len(label_to_shoal)} 个）")

    # Step 5: 构建 mask
    mask = np.zeros((n_pings, n_samples), dtype=bool)
    labeled = np.zeros((n_pings, n_samples), dtype=int)

    for shoal in shoals:
        for seg in shoal.segments:
            ping_idx = seg.ping_idx
            depth_mask = (depth >= seg.depth_min) & (depth <= seg.depth_max)
            mask[ping_idx, depth_mask] = True
            labeled[ping_idx, depth_mask] = shoal.id + 1

    logger.info(f"鱼群提取完成: {len(shoals)} 个鱼群, {int(mask.sum())} 个像素")

    return ShoalExtractionResult(
        shoals=shoals,
        mask=mask,
        labeled=labeled,
    )


def shoals_to_dataframe(result: ShoalExtractionResult, ds_Sv: xr.Dataset) -> pd.DataFrame:
    """将鱼群提取结果转换为 DataFrame

    Parameters
    ----------
    result : ShoalExtractionResult
        提取结果
    ds_Sv : xr.Dataset
        Sv 数据集

    Returns
    -------
    pd.DataFrame
        每行一个鱼群
    """
    Sv = get_sv_array(ds_Sv)
    depth = get_vertical_coords(ds_Sv)
    ping_time = ds_Sv["ping_time"].values

    # 计算深度和时间分辨率（公共函数，含零差值过滤）
    depth_res = depth_resolution(depth)
    ping_res_s = ping_resolution(ping_time)

    records = []
    for shoal in result.shoals:
        # 计算鱼群内的 Sv 统计
        sv_values = []
        for seg in shoal.segments:
            ping_idx = seg.ping_idx
            depth_mask = (depth >= seg.depth_min) & (depth <= seg.depth_max)
            sv_ping = Sv[ping_idx, depth_mask]
            sv_values.extend(sv_ping[np.isfinite(sv_ping)])

        mean_sv = float(np.mean(sv_values)) if sv_values else np.nan
        max_sv = float(np.max(sv_values)) if sv_values else np.nan

        # 计算面积
        n_pixels = sum(
            int(np.sum((depth >= s.depth_min) & (depth <= s.depth_max)))
            for s in shoal.segments
        )
        area = n_pixels * abs(ping_res_s) * depth_res

        records.append({
            "shoal_id": shoal.id,
            "ping_start": int(shoal.ping_start),
            "ping_end": int(shoal.ping_end),
            "ping_time_start": str(ping_time[shoal.ping_start])[:19],
            "ping_time_end": str(ping_time[shoal.ping_end])[:19],
            "depth_min": shoal.depth_min,
            "depth_max": shoal.depth_max,
            "height": shoal.height,
            "length_pings": shoal.length_pings,
            "n_pings": shoal.n_pings,
            "area": area,
            "mean_sv": mean_sv,
            "max_sv": max_sv,
            "centroid_depth": (shoal.depth_min + shoal.depth_max) / 2,
        })

    df = pd.DataFrame(records)
    logger.info(f"鱼群 DataFrame: {len(df)} 个鱼群")
    return df


def extract_shoals(
    ds_Sv: xr.Dataset,
    config: dict,
    bottom_depth_m: np.ndarray | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> tuple[np.ndarray, pd.DataFrame]:
    """统一鱼群提取接口

    Parameters
    ----------
    ds_Sv : xr.Dataset
        Sv 数据集
    config : dict
        配置字典
    bottom_depth_m : np.ndarray, optional
        底部深度数组
    progress_callback : callable, optional
        进度回调函数

    Returns
    -------
    tuple[np.ndarray, pd.DataFrame]
        (mask, shoals_df)
    """
    method = config.get("school_detection", {}).get("method", "advanced")

    if method == "echoview":
        # 使用原有 echopype detect_shoal
        from src.core.school import detect_schools, schools_to_dataframe
        mask = detect_schools(ds_Sv, config)
        df = schools_to_dataframe(mask, ds_Sv)
        return mask.values, df

    elif method == "advanced":
        # 使用高级提取
        result = extract_shoals_advanced(ds_Sv, config, bottom_depth_m, progress_callback)
        df = shoals_to_dataframe(result, ds_Sv)
        return result.mask, df

    else:
        raise ValueError(f"不支持的鱼群检测方法: {method}")
