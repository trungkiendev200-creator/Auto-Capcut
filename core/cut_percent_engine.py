"""Cut Percent Engine — trim từng video segment X% đầu + Y% cuối."""

import os
import shutil
from dataclasses import dataclass

from core import capcut


@dataclass
class CutPercentResult:
    success: bool
    message: str
    cut_count: int = 0
    skip_threshold: int = 0
    skip_n: int = 0
    duration_before_us: int = 0
    duration_after_us: int = 0


def cut_video_percent(
    draft_path: str,
    cut_before_pct: float,
    cut_after_pct: float,
    threshold_sec: float | None,
    every_n: int,
    backup: bool = True,
    log_fn=None,
) -> CutPercentResult:
    """Cắt source X% đầu + Y% cuối của mỗi segment trong video track CHÍNH.

    Args:
        cut_before_pct: % cắt từ đầu source (0-100).
        cut_after_pct:  % cắt từ cuối source (0-100).
        threshold_sec:  None = không filter; else skip segment có duration < threshold.
        every_n:        0 = cắt tất cả eligible; >=2 = chỉ cắt eligible[i] với i % N == 0.
                        N=1 cũng = cắt tất cả (mỗi 1 = mọi segment).
        backup:         tạo .bak nếu chưa có.

    Behavior:
        - Chỉ động vào video track đầu tiên (track chính).
        - Audio + text + overlay video tracks: KHÔNG động.
        - Sau khi cắt source, target shift trái dồn các segment khít.
        - data["duration"] = max target_end của TẤT CẢ tracks (giữ audio/text không bị cắt).
    """
    _log = log_fn or (lambda msg: None)

    # Validate
    if cut_before_pct < 0 or cut_after_pct < 0:
        return CutPercentResult(False, "Cut % không được âm")
    if cut_before_pct + cut_after_pct >= 100:
        return CutPercentResult(False, "Cut Before + Cut After phải < 100%")
    if every_n < 0:
        return CutPercentResult(False, "N không được âm")
    if threshold_sec is not None and threshold_sec < 0:
        return CutPercentResult(False, "Threshold không được âm")

    json_path = os.path.join(draft_path, "draft_content.json")
    if not os.path.isfile(json_path):
        return CutPercentResult(False, "draft_content.json not found")

    if backup:
        bak = json_path + ".bak"
        if not os.path.isfile(bak):
            shutil.copy2(json_path, bak)
            _log("  backup created")
        else:
            _log("  backup exists, skipping")

    data = capcut.load_draft_content(draft_path)
    duration_before = data.get("duration", 0)
    _log(f"  duration before: {duration_before/1_000_000:.2f}s")

    video_tracks = capcut.find_video_tracks(data)
    if not video_tracks:
        return CutPercentResult(False, "Không tìm thấy video track")

    main_track = video_tracks[0]
    segs = main_track.get("segments", [])
    if not segs:
        return CutPercentResult(False, "Track chính không có segment nào")

    _log(f"  main video track: {len(segs)} segments")

    threshold_us = int(threshold_sec * 1_000_000) if threshold_sec is not None else None

    cut_count = 0
    skip_threshold = 0
    skip_n = 0
    eligible_idx = 0

    # Sort by target_start để đếm eligible đúng thứ tự timeline
    segs.sort(key=lambda s: s["target_timerange"]["start"])

    for seg in segs:
        tgt_dur = seg["target_timerange"]["duration"]

        # Filter threshold (apply trên target_dur — đây là độ dài segment trên timeline).
        # Dùng <= để khớp behavior đối thủ: segment dur = threshold cũng skip.
        if threshold_us is not None and tgt_dur <= threshold_us:
            skip_threshold += 1
            continue

        # Eligible — quyết định cut hay skip theo N
        if every_n > 1 and (eligible_idx % every_n) != 0:
            skip_n += 1
            eligible_idx += 1
            continue

        eligible_idx += 1

        # Cắt source
        src = seg["source_timerange"]
        old_src_start = src["start"]
        old_src_dur = src["duration"]
        cut_start_us = int(old_src_dur * cut_before_pct / 100)
        cut_end_us = int(old_src_dur * cut_after_pct / 100)
        new_src_dur = old_src_dur - cut_start_us - cut_end_us
        if new_src_dur <= 0:
            # Defensive: tổng cắt > duration → skip segment này
            skip_threshold += 1
            continue

        src["start"] = old_src_start + cut_start_us
        src["duration"] = new_src_dur

        # Target dur đồng bộ với source mới (giữ nguyên speed)
        speed = seg.get("speed", 1.0) or 1.0
        seg["target_timerange"]["duration"] = int(new_src_dur / speed)

        cut_count += 1

    # Shift target trái dồn segments khít
    cumulative = 0
    for seg in segs:
        seg["target_timerange"]["start"] = cumulative
        cumulative += seg["target_timerange"]["duration"]

    _log(f"  cut: {cut_count}, skip<threshold: {skip_threshold}, skip-by-N: {skip_n}")
    _log(f"  main video new end: {cumulative/1_000_000:.2f}s")

    # Update duration = video target end (khớp behavior đối thủ — chỉ tính video,
    # bỏ qua audio/text ngay cả khi chúng extend dài hơn).
    data["duration"] = cumulative
    _log(f"  duration after: {cumulative/1_000_000:.2f}s")

    capcut.save_draft_content(draft_path, data)

    return CutPercentResult(
        success=True,
        message=f"Cắt {cut_count} segment ({skip_threshold} skip<threshold, {skip_n} skip-by-N)",
        cut_count=cut_count,
        skip_threshold=skip_threshold,
        skip_n=skip_n,
        duration_before_us=duration_before,
        duration_after_us=cumulative,
    )
