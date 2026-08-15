"""¸ß¼¶ÓãÈºÌáÈ¡Ä£¿é£º¿Õ¼ä¾ÛÀà + ¿ç ping Á¬½Ó

²Î¿¼£ºMatecho EchoGroupExtraction.m
¹¦ÄÜ£º
- Öð ping ãÐÖµ»¯
- Éî¶È·½Ïò¾ÛÀà£¨MaxDistDep£©
- ¿ç ping segment linking£¨Ç°Ïò+ºóÏò£©
- Ç¨ÒÆÇøÓòÌØÊâ´¦Àí£¨ÈÕ³ö/ÈÕÂä£©
- ÓãÈºÃèÊö·û¼ÆËã£¨Ãæ»ý¡¢³¤¶È¡¢¸ß¶È¡¢ÐÎÌ¬ÌØÕ÷£©
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import xarray as xr

from src.core.utils import get_sv_array, get_vertical_coords

logger = logging.getLogger("fish_acoustics")


@dataclass
class Segment:
    """µ¥¸ö segment£¨Ò»¸ö ping ÄÚµÄÁ¬ÐøÓÐÐ§ÇøÓò£©"""
    depth_min: float
    depth_max: float
    ping_idx: int
    label: int = -1  # ËùÊôÓãÈº±êÇ©


@dataclass
class ShoalGroup:
    """ÓãÈº£¨ÓÉ¶à¸ö segment Á¬½Ó¶ø³É£©"""
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
    """ÓãÈºÌáÈ¡½á¹û"""
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
    """¶Ôµ¥¸ö ping ½øÐÐãÐÖµ»¯²¢ÌáÈ¡ segment

    Parameters
    ----------
    sv_ping : np.ndarray
        µ¥¸ö ping µÄ Sv Êý¾Ý£¬shape=(n_samples,)
    depth : np.ndarray
        Éî¶ÈÊý×é£¬shape=(n_samples,)
    ping_idx : int
        µ±Ç° ping Ë÷Òý
    min_threshold : float
        ×îÐ¡ãÐÖµ (dB)
    max_depth_dist : float
        ×î´óÉî¶È¼ä¸ô (Ã×)£¬³¬¹ý´Ë¼ä¸ô·ÖÎª²»Í¬ segment
    bottom_depth : float, optional
        µ×²¿Éî¶È (Ã×)£¬³¬¹ýµ×²¿µÄÑù±¾±»ÅÅ³ý
    label_counter : int
        ±êÇ©¼ÆÊýÆ÷ÆðÊ¼Öµ

    Returns
    -------
    list[Segment]
        ÌáÈ¡µÄ segment ÁÐ±í
    """
    # ãÐÖµ»¯
    valid_mask = (sv_ping >= min_threshold) & np.isfinite(sv_ping)

    # µ×²¿ÒÔÏÂÅÅ³ý
    if bottom_depth is not None and np.isfinite(bottom_depth):
        valid_mask[depth >= bottom_depth] = False

    if not np.any(valid_mask):
        return []

    # ÕÒµ½ÓÐÐ§Ñù±¾µÄÉî¶È
    valid_depths = depth[valid_mask]

    # °´Éî¶È·½Ïò¾ÛÀà£¨¼ä¸ô > max_depth_dist ·ÖÎª²»Í¬ segment£©
    segments = []
    if len(valid_depths) == 0:
        return segments

    # ÅÅÐòÉî¶È
    sorted_depths = np.sort(valid_depths)

    # °´Éî¶È¼ä¸ô·Ö×é
    current_min = sorted_depths[0]
    current_max = sorted_depths[0]
    current_label = label_counter

    for i in range(1, len(sorted_depths)):
        if sorted_depths[i] - sorted_depths[i-1] > max_depth_dist:
            # ¼ä¸ô¹ý´ó£¬½áÊøµ±Ç° segment£¬¿ªÊ¼ÐÂµÄ
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

    # Ìí¼Ó×îºóÒ»¸ö segment
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
    """Ç°ÏòÁ¬½Ó£º½«µ±Ç° ping µÄ segment ÓëÇ°¼¸¸ö ping µÄ segment Á¬½Ó

    Parameters
    ----------
    current_segments : list[Segment]
        µ±Ç° ping µÄ segment ÁÐ±í
    previous_segments : list[Segment]
        Ç°¼¸¸ö ping µÄ segment ÁÐ±í
    max_depth_dist : float
        ×î´óÉî¶È¼ä¸ô (Ã×)
    max_time_gap : int
        ×î´óÊ±¼ä¼ä¸ô (ping Êý)
    current_ping : int
        µ±Ç° ping Ë÷Òý
    """
    for curr_seg in current_segments:
        best_match = None
        best_overlap = 0

        for prev_seg in previous_segments:
            # ¼ì²éÊ±¼ä¼ä¸ô
            if current_ping - prev_seg.ping_idx > max_time_gap:
                continue

            # ¼ÆËãÉî¶ÈÖØµþ
            overlap_min = max(curr_seg.depth_min, prev_seg.depth_min)
            overlap_max = min(curr_seg.depth_max, prev_seg.depth_max)
            overlap = max(0, overlap_max - overlap_min)

            # ¼ì²éÊÇ·ñÔÚÉî¶ÈÈÝ²îÄÚ
            depth_gap = min(
                abs(curr_seg.depth_min - prev_seg.depth_max),
                abs(curr_seg.depth_max - prev_seg.depth_min),
            )

            if overlap > 0 or depth_gap <= max_depth_dist:
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_match = prev_seg

        if best_match is not None:
            # ¼Ì³ÐÇ°Ò»¸ö segment µÄ±êÇ©
            curr_seg.label = best_match.label


def extract_shoals_advanced(
    ds_Sv: xr.Dataset,
    config: dict,
    bottom_depth_m: np.ndarray | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> ShoalExtractionResult:
    """¸ß¼¶ÓãÈºÌáÈ¡£¨²Î¿¼ Matecho£©

    Parameters
    ----------
    ds_Sv : xr.Dataset
        Sv Êý¾Ý¼¯
    config : dict
        ÅäÖÃ×Öµä£¬Ðè°üº¬ school_detection ×ÓÏî
    bottom_depth_m : np.ndarray, optional
        µ×²¿Éî¶ÈÊý×é (Ã×)£¬shape=(n_pings,)
    progress_callback : callable, optional
        ½ø¶È»Øµ÷º¯Êý

    Returns
    -------
    ShoalExtractionResult
        ÌáÈ¡½á¹û
    """
    school_cfg = config.get("school_detection", {})

    # ²ÎÊý
    min_threshold = school_cfg.get("min_threshold", -60.0)
    max_depth_dist = school_cfg.get("max_depth_distance", 0.1)  # Ã×
    max_ping_dist = school_cfg.get("max_ping_distance", 1)  # ping Êý
    max_time_gap = school_cfg.get("max_time_gap", 20)  # ping Êý
    min_shoal_pings = school_cfg.get("min_shoal_pings", 3)
    min_shoal_height = school_cfg.get("min_shoal_height", 0.5)  # Ã×

    # »ñÈ¡Êý¾Ý
    Sv = get_sv_array(ds_Sv)  # (n_pings, n_samples)
    depth = get_vertical_coords(ds_Sv)  # (n_samples,)
    n_pings, n_samples = Sv.shape


    # Step 1: Öð ping ÌáÈ¡ segment
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

    logger.info(f"Step 1 Íê³É: ÌáÈ¡ÁË {label_counter} ¸ö³õÊ¼ segment")

    # Step 2: Ç°ÏòÁ¬½Ó£¨¿ç ping linking£©
    max_lookback = min(max_ping_dist + 1, 10)  # ÏòÇ°¿´µÄ ping Êý

    for ping_idx in range(1, n_pings):
        current_segments = all_segments[ping_idx]
        if not current_segments:
            continue

        # ÊÕ¼¯Ç°¼¸¸ö ping µÄ segment
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

    logger.info("Step 2 Íê³É: Ç°ÏòÁ¬½Ó")

    # Step 3: ¹¹½¨ÓãÈº£¨ºÏ²¢ÏàÍ¬±êÇ©µÄ segment£©
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

    # Step 4: ¹ýÂËÐ¡ÓãÈº
    shoals = []
    for shoal in label_to_shoal.values():
        if shoal.n_pings >= min_shoal_pings and shoal.height >= min_shoal_height:
            shoals.append(shoal)

    logger.info(f"Step 3-4 Íê³É: {len(shoals)} ¸öÓãÈº£¨¹ýÂËÇ° {len(label_to_shoal)} ¸ö£©")

    # Step 5: ¹¹½¨ mask
    mask = np.zeros((n_pings, n_samples), dtype=bool)
    labeled = np.zeros((n_pings, n_samples), dtype=int)

    for shoal in shoals:
        for seg in shoal.segments:
            ping_idx = seg.ping_idx
            depth_mask = (depth >= seg.depth_min) & (depth <= seg.depth_max)
            mask[ping_idx, depth_mask] = True
            labeled[ping_idx, depth_mask] = shoal.id + 1

    logger.info(f"ÓãÈºÌáÈ¡Íê³É: {len(shoals)} ¸öÓãÈº, {int(mask.sum())} ¸öÏñËØ")

    return ShoalExtractionResult(
        shoals=shoals,
        mask=mask,
        labeled=labeled,
    )


def shoals_to_dataframe(result: ShoalExtractionResult, ds_Sv: xr.Dataset) -> pd.DataFrame:
    """½«ÓãÈºÌáÈ¡½á¹û×ª»»Îª DataFrame

    Parameters
    ----------
    result : ShoalExtractionResult
        ÌáÈ¡½á¹û
    ds_Sv : xr.Dataset
        Sv Êý¾Ý¼¯

    Returns
    -------
    pd.DataFrame
        Ã¿ÐÐÒ»¸öÓãÈº
    """
    Sv = get_sv_array(ds_Sv)
    depth = get_vertical_coords(ds_Sv)
    ping_time = ds_Sv["ping_time"].values

    # ¼ÆËãÉî¶ÈºÍÊ±¼ä·Ö±æÂÊ
    if len(depth) > 1:
        depth_diffs = np.abs(np.diff(depth))
        non_zero_diffs = depth_diffs[depth_diffs > 0]
        depth_res = float(np.median(non_zero_diffs)) if len(non_zero_diffs) > 0 else 0.1
    else:
        depth_res = 0.1

    if len(ping_time) > 1:
        if np.issubdtype(ping_time.dtype, np.datetime64):
            ping_res_s = float(np.diff(ping_time[:2]) / np.timedelta64(1, 's'))
        else:
            ping_res_s = float(np.diff(ping_time[:2])[0])
    else:
        ping_res_s = 1.0

    records = []
    for shoal in result.shoals:
        # ¼ÆËãÓãÈºÄÚµÄ Sv Í³¼Æ
        sv_values = []
        for seg in shoal.segments:
            ping_idx = seg.ping_idx
            depth_mask = (depth >= seg.depth_min) & (depth <= seg.depth_max)
            sv_ping = Sv[ping_idx, depth_mask]
            sv_values.extend(sv_ping[np.isfinite(sv_ping)])

        mean_sv = float(np.mean(sv_values)) if sv_values else np.nan
        max_sv = float(np.max(sv_values)) if sv_values else np.nan

        # ¼ÆËãÃæ»ý
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
    logger.info(f"ÓãÈº DataFrame: {len(df)} ¸öÓãÈº")
    return df


def extract_shoals(
    ds_Sv: xr.Dataset,
    config: dict,
    bottom_depth_m: np.ndarray | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> tuple[np.ndarray, pd.DataFrame]:
    """Í³Ò»ÓãÈºÌáÈ¡½Ó¿Ú

    Parameters
    ----------
    ds_Sv : xr.Dataset
        Sv Êý¾Ý¼¯
    config : dict
        ÅäÖÃ×Öµä
    bottom_depth_m : np.ndarray, optional
        µ×²¿Éî¶ÈÊý×é
    progress_callback : callable, optional
        ½ø¶È»Øµ÷º¯Êý

    Returns
    -------
    tuple[np.ndarray, pd.DataFrame]
        (mask, shoals_df)
    """
    method = config.get("school_detection", {}).get("method", "advanced")

    if method == "echoview":
        # Ê¹ÓÃÔ­ÓÐ echopype detect_shoal
        from src.core.school import detect_schools, schools_to_dataframe
        mask = detect_schools(ds_Sv, config)
        df = schools_to_dataframe(mask, ds_Sv)
        return mask.values, df

    elif method == "advanced":
        # Ê¹ÓÃ¸ß¼¶ÌáÈ¡
        result = extract_shoals_advanced(ds_Sv, config, bottom_depth_m, progress_callback)
        df = shoals_to_dataframe(result, ds_Sv)
        return result.mask, df

    else:
        raise ValueError(f"²»Ö§³ÖµÄÓãÈº¼ì²â·½·¨: {method}")