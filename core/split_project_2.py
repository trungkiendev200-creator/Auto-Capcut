"""Split project 2 — chia project có audio track = 1 segment duy nhất.

Tối ưu cho project Manhwa (1 audio file trỏ tới MP4, hàng ngàn ảnh).
Cắt ở ranh giới video segment, audio dùng source_timerange offset chính xác
để khi nối lại = gốc 100%.
"""

import os
import json
import time
import uuid
import copy
import shutil
from dataclasses import dataclass, field

from core import capcut
from core.split_project import (
    SplitResult, BatchSplitResult,
    _compute_n_parts, _find_cut_points,
    _write_draft_content, _cleanup_stale_files,
    _rewrite_timelines_uuid, _update_draft_meta, _update_root_meta,
)


def _uid() -> str:
    return str(uuid.uuid4()).upper()


def _slice_video_segments(segments: list, part_start: int, part_end: int) -> list:
    """Filter video segments — chỉ giữ segment fully inside [part_start, part_end)."""
    new_segs = []
    for seg in segments:
        tr = seg.get("target_timerange", {}) or {}
        s = tr.get("start", 0)
        d = tr.get("duration", 0)
        e = s + d

        # Video segments không được cross boundary (cut points đã snap về video end)
        if e <= part_start or s >= part_end:
            continue

        new_seg = copy.deepcopy(seg)
        new_tr = new_seg.setdefault("target_timerange", {})
        new_tr["start"] = s - part_start
        new_tr["duration"] = d  # giữ nguyên duration

        new_segs.append(new_seg)

    return new_segs


def _slice_single_audio_segment(audio_seg: dict, part_start: int, part_end: int) -> dict | None:
    """Cắt 1 audio segment cho 1 part. Audio gốc bao toàn bộ → cắt theo part range.

    Return None nếu part nằm hoàn toàn ngoài audio segment.
    """
    tr = audio_seg.get("target_timerange", {}) or {}
    sr = audio_seg.get("source_timerange", {}) or {}
    a_start = tr.get("start", 0)
    a_dur = tr.get("duration", 0)
    a_end = a_start + a_dur

    # Phần overlap với part range
    clip_start = max(a_start, part_start)
    clip_end = min(a_end, part_end)
    if clip_end <= clip_start:
        return None

    clip_dur = clip_end - clip_start

    new_seg = copy.deepcopy(audio_seg)
    # Target: timeline của part bắt đầu lại từ 0
    new_seg["target_timerange"] = {
        "start": clip_start - part_start,
        "duration": clip_dur,
    }
    # Source: offset theo phần đã clip ở đầu
    src_start = sr.get("start", 0) + (clip_start - a_start)
    new_seg["source_timerange"] = {
        "start": src_start,
        "duration": clip_dur,
    }
    return new_seg


def _slice_content(data: dict, part_start: int, part_end: int,
                   new_id: str, new_name: str) -> dict:
    """Slice draft cho 1 part. Audio xử lý đặc biệt cho case 1 segment."""
    new_data = copy.deepcopy(data)

    for t in new_data.get("tracks", []):
        tt = t.get("type")
        segs = t.get("segments", [])

        if tt == "video":
            t["segments"] = _slice_video_segments(segs, part_start, part_end)
        elif tt == "audio":
            # Audio track = 1 segment duy nhất → cắt riêng
            if len(segs) == 1:
                sliced = _slice_single_audio_segment(segs[0], part_start, part_end)
                t["segments"] = [sliced] if sliced else []
            else:
                # Fallback: nếu nhiều audio segments, dùng logic generic giống split_project
                from core.split_project import _slice_track_segments
                t["segments"] = _slice_track_segments(segs, part_start, part_end)
        else:
            # Sticker / text / effect tracks → dùng logic generic
            from core.split_project import _slice_track_segments
            t["segments"] = _slice_track_segments(segs, part_start, part_end)

    new_data["duration"] = part_end - part_start
    new_data["id"] = new_id
    new_data["name"] = new_name
    return new_data


def split_project_v2(
    source_path: str,
    capcut_path: str,
    max_minutes: float,
    callback=None,
) -> SplitResult:
    """Chia project có audio = 1 segment duy nhất.

    Cut points snap về end của video segment gần `k × max` nhất.
    Audio segment được split theo cùng vị trí với source_timerange offset chính xác.
    """
    name = os.path.basename(source_path.rstrip("/\\"))
    if callback:
        callback(f"Loading '{name}'...")

    if not os.path.isdir(source_path):
        return SplitResult(False, f"Folder not found: {source_path}")

    try:
        data = capcut.load_draft_content(source_path)
    except Exception as e:
        return SplitResult(False, f"Load draft failed: {e}")

    # Validate cấu trúc: 1 video track có nhiều seg, 1 audio track có 1 seg
    video_tracks = [t for t in data.get("tracks", []) if t.get("type") == "video"]
    audio_tracks = [t for t in data.get("tracks", []) if t.get("type") == "audio"]

    if not video_tracks:
        return SplitResult(False, "Không có video track")
    video_segs = video_tracks[0].get("segments", [])
    if len(video_segs) < 2:
        return SplitResult(False, "Video < 2 segments — không split được")

    if not audio_tracks:
        return SplitResult(False, "Không có audio track")
    audio_segs = audio_tracks[0].get("segments", [])
    if len(audio_segs) != 1:
        return SplitResult(False,
            f"Audio không phải 1 segment (có {len(audio_segs)}). "
            "Dùng Split projects (v1) thay thế.")

    # Total duration = max end của tracks
    total_us = 0
    for t in data.get("tracks", []):
        for s in t.get("segments", []):
            tr = s.get("target_timerange", {}) or {}
            end = tr.get("start", 0) + tr.get("duration", 0)
            if end > total_us:
                total_us = end

    if total_us <= 0:
        return SplitResult(False, "Duration = 0")

    max_us = int(max_minutes * 60 * 1_000_000)
    if max_us <= 0:
        return SplitResult(False, "Max duration phải > 0")

    n_parts = _compute_n_parts(total_us, max_us)
    if n_parts <= 1:
        return SplitResult(False, f"{total_us/60_000_000:.1f}min ≤ max — không cần split")

    cuts = _find_cut_points(video_segs, n_parts, max_us, total_us)
    if callback:
        callback(f"Total {total_us/60_000_000:.1f}min → {n_parts} parts")
        for i in range(n_parts):
            part_dur = (cuts[i+1] - cuts[i]) / 60_000_000
            callback(f"  part {i+1}: {part_dur:.2f}min")

    draft_root = capcut.get_draft_root(capcut_path)
    created_names = []

    for i in range(n_parts):
        part_start = cuts[i]
        part_end = cuts[i+1]
        part_name = f"{name} part {i+1}"
        part_folder = os.path.join(draft_root, part_name)

        if os.path.exists(part_folder):
            if callback:
                callback(f"SKIP {part_name}: đã tồn tại")
            continue

        if callback:
            callback(f"Creating {part_name}...")

        shutil.copytree(source_path, part_folder)

        new_id = _uid()
        part_data = _slice_content(data, part_start, part_end, new_id, part_name)
        _write_draft_content(part_folder, part_data)
        _cleanup_stale_files(part_folder)
        _rewrite_timelines_uuid(part_folder, new_id)
        _update_draft_meta(part_folder, part_name, new_id, part_data["duration"])
        _update_root_meta(capcut_path, part_folder, part_name, new_id, part_data["duration"])

        created_names.append(part_name)
        if callback:
            callback(f"  OK part {i+1} ({part_data['duration']/60_000_000:.2f}min)")

    return SplitResult(
        success=bool(created_names),
        message=f"Split '{name}': {len(created_names)}/{n_parts} parts",
        parts_created=len(created_names),
        part_names=created_names,
    )


def batch_split_projects_v2(
    drafts: list[dict],
    capcut_path: str,
    max_minutes: float,
    callback=None,
) -> BatchSplitResult:
    """Split nhiều projects (v2). drafts là list dict từ root_meta_info."""
    result = BatchSplitResult(total=len(drafts))

    for d in drafts:
        path = d.get("draft_fold_path", "")
        name = d.get("draft_name", "?")
        if not path or not os.path.isdir(path):
            result.skipped.append(f"{name}: invalid path")
            if callback:
                callback(f"SKIP {name}: invalid path")
            continue

        if callback:
            callback(f"--- {name} ---")
        r = split_project_v2(path, capcut_path, max_minutes, callback)
        if r.success:
            result.split_ok += 1
            result.parts_total += r.parts_created
        else:
            result.skipped.append(f"{name}: {r.message}")
            if callback:
                callback(f"  {r.message}")

    return result
