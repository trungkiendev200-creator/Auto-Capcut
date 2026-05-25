"""Split project — chia 1 CapCut project thành nhiều parts theo max duration."""

import os
import json
import time
import uuid
import copy
import shutil
from dataclasses import dataclass, field

from core import capcut


@dataclass
class SplitResult:
    success: bool
    message: str
    parts_created: int = 0
    part_names: list[str] = field(default_factory=list)


@dataclass
class BatchSplitResult:
    total: int = 0
    split_ok: int = 0
    parts_total: int = 0
    skipped: list[str] = field(default_factory=list)


def _uid() -> str:
    return str(uuid.uuid4()).upper()


def _project_total_duration(data: dict) -> int:
    """Tính total duration = max end position of all segments (microseconds)."""
    total = data.get("duration", 0)
    for t in data.get("tracks", []):
        for seg in t.get("segments", []):
            tr = seg.get("target_timerange", {}) or {}
            end = tr.get("start", 0) + tr.get("duration", 0)
            if end > total:
                total = end
    return total


def _compute_n_parts(total_us: int, max_us: int) -> int:
    """Số parts theo logic:
    - remainder ≤ 50% max → gộp vào part cuối (n_parts = n_full)
    - remainder > 50% max → tách riêng (n_parts = n_full + 1)
    """
    if total_us <= max_us:
        return 1
    n_full = total_us // max_us
    remainder = total_us - n_full * max_us
    if remainder == 0:
        return n_full
    if remainder <= max_us // 2:
        return n_full
    return n_full + 1


def _find_cut_points(video_segs: list, n_parts: int, max_us: int, total_us: int) -> list[int]:
    """Trả về list cut points (microseconds), len = n_parts + 1.

    cut_points[0] = 0, cut_points[-1] = total_us.
    Trung gian = end của video segment gần `k × max_us` nhất.
    """
    cuts = [0]
    # Sort video segments by target start
    sorted_segs = sorted(
        video_segs,
        key=lambda s: (s.get("target_timerange", {}) or {}).get("start", 0)
    )
    seg_ends = []
    for s in sorted_segs:
        tr = s.get("target_timerange", {}) or {}
        seg_ends.append(tr.get("start", 0) + tr.get("duration", 0))

    for k in range(1, n_parts):
        target = k * max_us
        best_end = None
        best_diff = None
        for end in seg_ends:
            if end <= cuts[-1]:
                continue
            diff = abs(end - target)
            if best_diff is None or diff < best_diff:
                best_diff = diff
                best_end = end
        if best_end is None or best_end <= cuts[-1]:
            # Fallback: theo target chính xác (không nên xảy ra nếu có đủ segments)
            best_end = target
        cuts.append(best_end)

    cuts.append(total_us)
    return cuts


def _slice_track_segments(segments: list, part_start: int, part_end: int) -> list:
    """Filter + shift segments để rơi vào [part_start, part_end). Crossing thì trim.

    Audio segments crossing boundary sẽ split nhưng material giữ nguyên,
    chỉ chỉnh source_timerange để khi gộp lại = gốc 100%.
    """
    new_segs = []
    for seg in segments:
        tr = seg.get("target_timerange", {}) or {}
        s = tr.get("start", 0)
        d = tr.get("duration", 0)
        e = s + d

        if e <= part_start or s >= part_end:
            continue  # outside

        new_seg = copy.deepcopy(seg)
        new_tr = new_seg.setdefault("target_timerange", {})
        new_src = new_seg.get("source_timerange") or None

        if s >= part_start and e <= part_end:
            # Fully inside — shift only
            new_tr["start"] = s - part_start
            new_tr["duration"] = d
        else:
            # Compute clipped range trong target timeline
            clip_start = max(s, part_start)
            clip_end = min(e, part_end)
            clip_dur = clip_end - clip_start

            new_tr["start"] = clip_start - part_start
            new_tr["duration"] = clip_dur

            # Adjust source_timerange tương ứng (giữ media reference)
            if new_src:
                # offset trong source = phần đã clip ở đầu trên target
                left_trim = clip_start - s
                src_start = new_src.get("start", 0) + left_trim
                new_src["start"] = src_start
                new_src["duration"] = clip_dur

        new_segs.append(new_seg)

    return new_segs


def _slice_content(data: dict, part_start: int, part_end: int,
                   new_id: str, new_name: str) -> dict:
    """Clone draft_content, gán id/name mới, slice tất cả tracks."""
    new_data = copy.deepcopy(data)

    for t in new_data.get("tracks", []):
        t["segments"] = _slice_track_segments(t.get("segments", []), part_start, part_end)

    new_data["duration"] = part_end - part_start
    new_data["id"] = new_id
    new_data["name"] = new_name
    return new_data


def _write_draft_content(part_folder: str, data: dict) -> None:
    """Ghi draft_content.json vào root + Timelines/<uuid>/."""
    content = json.dumps(data, ensure_ascii=False)

    root_path = os.path.join(part_folder, "draft_content.json")
    with open(root_path, "w", encoding="utf-8") as f:
        f.write(content)

    timelines_dir = os.path.join(part_folder, "Timelines")
    if os.path.isdir(timelines_dir):
        for d in os.listdir(timelines_dir):
            sub = os.path.join(timelines_dir, d)
            if os.path.isdir(sub):
                tl_json = os.path.join(sub, "draft_content.json")
                if os.path.isfile(tl_json):
                    with open(tl_json, "w", encoding="utf-8") as f:
                        f.write(content)


def _cleanup_stale_files(part_folder: str) -> None:
    """Xóa .bak và .tmp lỗi thời sau khi sliced."""
    stale_names = {"draft_content.json.bak", "template-2.tmp", "template.tmp"}
    for root, _, files in os.walk(part_folder):
        for f in files:
            if f in stale_names:
                try:
                    os.remove(os.path.join(root, f))
                except OSError:
                    pass


def _rewrite_timelines_uuid(part_folder: str, new_id: str) -> None:
    """Rename Timelines/<oldId>/ → Timelines/<newId>/ và cập nhật project.json."""
    timelines_dir = os.path.join(part_folder, "Timelines")
    if not os.path.isdir(timelines_dir):
        return

    # Find existing subfolder (should be 1)
    subs = [d for d in os.listdir(timelines_dir)
            if os.path.isdir(os.path.join(timelines_dir, d))]
    if not subs:
        return
    old_sub = subs[0]
    if old_sub == new_id:
        return  # already matches

    old_path = os.path.join(timelines_dir, old_sub)
    new_path = os.path.join(timelines_dir, new_id)
    try:
        os.rename(old_path, new_path)
    except OSError:
        return

    # Update Timelines/project.json
    proj_json = os.path.join(timelines_dir, "project.json")
    if os.path.isfile(proj_json):
        try:
            with open(proj_json, "r", encoding="utf-8") as f:
                proj = json.load(f)
            if proj.get("id") == old_sub:
                proj["id"] = new_id
            if proj.get("main_timeline_id") == old_sub:
                proj["main_timeline_id"] = new_id
            for tl in proj.get("timelines", []):
                if tl.get("id") == old_sub:
                    tl["id"] = new_id
            with open(proj_json, "w", encoding="utf-8") as f:
                json.dump(proj, f, ensure_ascii=False)
        except (OSError, json.JSONDecodeError):
            pass


def _update_draft_meta(part_folder: str, part_name: str, new_id: str, duration_us: int) -> None:
    """Cập nhật draft_meta_info.json trong part folder."""
    meta_path = os.path.join(part_folder, "draft_meta_info.json")
    if not os.path.isfile(meta_path):
        return
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
    except (OSError, json.JSONDecodeError):
        return

    now_us = int(time.time() * 1_000_000)
    meta["draft_id"] = new_id
    meta["draft_fold_path"] = part_folder.replace("\\", "/")
    meta["draft_name"] = part_name
    meta["tm_draft_create"] = now_us
    meta["tm_draft_modified"] = now_us
    meta["tm_duration"] = duration_us

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False)


def _update_root_meta(capcut_path: str, part_folder: str, part_name: str,
                     new_id: str, duration_us: int) -> None:
    """Thêm entry mới vào root_meta_info.json."""
    draft_root = capcut.get_draft_root(capcut_path)
    root_meta_path = os.path.join(draft_root, "root_meta_info.json")
    with open(root_meta_path, "r", encoding="utf-8") as f:
        root_meta = json.load(f)

    now_us = int(time.time() * 1_000_000)
    content_path = os.path.join(part_folder, "draft_content.json")
    entry = {
        "cloud_draft_cover": False,
        "cloud_draft_sync": False,
        "draft_cloud_last_action_download": False,
        "draft_cloud_purchase_info": "",
        "draft_cloud_template_id": "",
        "draft_cloud_tutorial_info": "",
        "draft_cloud_videocut_purchase_info": "",
        "draft_cover": "",
        "draft_fold_path": part_folder.replace("\\", "/"),
        "draft_id": new_id,
        "draft_is_ai_shorts": False,
        "draft_is_cloud_temp_draft": False,
        "draft_is_invisible": False,
        "draft_is_web_article_video": False,
        "draft_json_file": content_path.replace("\\", "/"),
        "draft_name": part_name,
        "draft_new_version": "164.0.0",
        "draft_root_path": draft_root.replace("/", "\\"),
        "draft_timeline_materials_size": 0,
        "draft_type": "",
        "draft_web_article_video_enter_from": "",
        "streaming_edit_draft_ready": True,
        "tm_draft_cloud_completed": "",
        "tm_draft_cloud_entry_id": -1,
        "tm_draft_cloud_modified": 0,
        "tm_draft_cloud_parent_entry_id": -1,
        "tm_draft_cloud_space_id": -1,
        "tm_draft_cloud_user_id": -1,
        "tm_draft_create": now_us,
        "tm_draft_modified": now_us,
        "tm_draft_removed": 0,
        "tm_duration": duration_us,
    }

    # Replace existing with same name
    root_meta["all_draft_store"] = [
        d for d in root_meta["all_draft_store"]
        if d.get("draft_name") != part_name
    ]
    root_meta["all_draft_store"].insert(0, entry)

    with open(root_meta_path, "w", encoding="utf-8") as f:
        json.dump(root_meta, f, ensure_ascii=False)


def split_project(
    source_path: str,
    capcut_path: str,
    max_minutes: float,
    callback=None,
) -> SplitResult:
    """Chia source project thành nhiều parts (giữ nguyên project gốc).

    max_minutes: max duration mỗi part (phút).
    Returns SplitResult.
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

    # Validate có video track
    video_tracks = [t for t in data.get("tracks", []) if t.get("type") == "video"]
    if not video_tracks:
        return SplitResult(False, "Không có video track")
    video_segs = video_tracks[0].get("segments", [])
    if len(video_segs) < 2:
        return SplitResult(False, "Chỉ có 1 video segment — không split được")

    # Tính total từ tracks
    total_us = _project_total_duration(data)
    if total_us <= 0:
        return SplitResult(False, "Duration = 0")

    max_us = int(max_minutes * 60 * 1_000_000)
    if max_us <= 0:
        return SplitResult(False, "Max duration phải > 0")

    n_parts = _compute_n_parts(total_us, max_us)
    if n_parts <= 1:
        total_min = total_us / 60_000_000
        return SplitResult(False, f"{total_min:.1f}min ≤ max — không cần split")

    cuts = _find_cut_points(video_segs, n_parts, max_us, total_us)
    if callback:
        callback(f"Total {total_us/60_000_000:.1f}min → {n_parts} parts")
        for i in range(n_parts):
            part_dur = (cuts[i+1] - cuts[i]) / 60_000_000
            callback(f"  part {i+1}: {part_dur:.1f}min")

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

        # Copy whole source folder
        shutil.copytree(source_path, part_folder)

        # Generate new UUID, slice content, write files
        new_id = _uid()
        part_data = _slice_content(data, part_start, part_end, new_id, part_name)
        _write_draft_content(part_folder, part_data)
        _cleanup_stale_files(part_folder)
        _rewrite_timelines_uuid(part_folder, new_id)
        _update_draft_meta(part_folder, part_name, new_id, part_data["duration"])
        _update_root_meta(capcut_path, part_folder, part_name, new_id, part_data["duration"])

        created_names.append(part_name)
        if callback:
            callback(f"  OK part {i+1} ({part_data['duration']/60_000_000:.1f}min)")

    return SplitResult(
        success=bool(created_names),
        message=f"Split '{name}': {len(created_names)}/{n_parts} parts",
        parts_created=len(created_names),
        part_names=created_names,
    )


def batch_split_projects(
    drafts: list[dict],
    capcut_path: str,
    max_minutes: float,
    callback=None,
) -> BatchSplitResult:
    """Split nhiều projects. drafts là list dict từ root_meta_info."""
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
        r = split_project(path, capcut_path, max_minutes, callback)
        if r.success:
            result.split_ok += 1
            result.parts_total += r.parts_created
        else:
            result.skipped.append(f"{name}: {r.message}")
            if callback:
                callback(f"  {r.message}")

    return result
