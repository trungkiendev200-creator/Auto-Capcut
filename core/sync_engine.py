"""Sync Engine — đồng bộ video/image segments theo audio segments."""

import os
import shutil
from dataclasses import dataclass

from core import capcut


# Chế độ xử lý khi video dài hơn audio
VIDEO_MODE_CUT = "cut"        # Cắt video (trim), giữ speed=1
VIDEO_MODE_SPEED = "speed"    # Tăng speed để video fit vào audio duration


@dataclass
class SyncResult:
    success: bool
    message: str
    synced_count: int = 0
    track_count: int = 0


def sync_project(
    draft_path: str,
    video_mode: str = VIDEO_MODE_CUT,
    backup: bool = True,
) -> SyncResult:
    """
    Đồng bộ thời lượng video segments theo audio segments.

    Logic:
    - Audio là master.
    - Với MỖI video track: video_segment[i] nhận timing từ audio_segment[i].
    - sync_count = min(len(video_segments), len(audio_segments)) cho mỗi track.
    - Video thừa segments → cắt bỏ.
    - Với video thật (type=video) khi video dài hơn audio:
        - CUT: cắt source, giữ speed=1
        - SPEED: giữ nguyên source, tăng speed để fit

    Returns SyncResult.
    """
    json_path = os.path.join(draft_path, "draft_content.json")

    if not os.path.isfile(json_path):
        return SyncResult(False, "draft_content.json not found")

    if backup:
        bak_path = json_path + ".bak"
        shutil.copy2(json_path, bak_path)

    data = capcut.load_draft_content(draft_path)
    video_tracks = capcut.find_video_tracks(data)
    audio_track = capcut.find_audio_track(data)

    if not video_tracks:
        return SyncResult(False, "No video track with segments found")
    if audio_track is None:
        return SyncResult(False, "No audio track with segments found")

    a_segs = audio_track["segments"]
    total_synced = 0
    track_details = []
    speed_materials = {sp["id"]: sp for sp in data.get("materials", {}).get("speeds", [])}

    for vt in video_tracks:
        v_segs = vt["segments"]
        original_count = len(v_segs)
        sync_count = min(original_count, len(a_segs))

        if sync_count == 0:
            continue

        for i in range(sync_count):
            a_start = a_segs[i]["target_timerange"]["start"]
            a_dur = a_segs[i]["target_timerange"]["duration"]

            mat_id = v_segs[i].get("material_id", "")
            mat_type = _get_material_type(data, mat_id)
            source_dur = v_segs[i]["source_timerange"]["duration"]

            # Set target timing = audio timing
            v_segs[i]["target_timerange"]["start"] = a_start
            v_segs[i]["target_timerange"]["duration"] = a_dur

            # Tắt âm video sync (narration audio thay thế)
            v_segs[i]["volume"] = 0.0
            v_segs[i]["last_nonzero_volume"] = 0.0

            if mat_type == "photo":
                # Ảnh: chỉ thay đổi target, không cần xử lý speed/source
                pass
            elif mat_type == "video":
                if video_mode == VIDEO_MODE_SPEED:
                    # SPEED mode: giữ nguyên source_duration, tính speed mới
                    # speed = source_duration / target_duration
                    new_speed = source_dur / a_dur if a_dur > 0 else 1.0
                    v_segs[i]["speed"] = new_speed

                    # Update speed material trong extra_material_refs
                    _update_speed_material(v_segs[i], speed_materials, new_speed)
                else:
                    # CUT mode: cắt source cho vừa target, speed=1
                    v_segs[i]["source_timerange"]["duration"] = a_dur
                    v_segs[i]["speed"] = 1.0
                    _update_speed_material(v_segs[i], speed_materials, 1.0)

        # Cắt segments thừa
        if original_count > sync_count:
            vt["segments"] = v_segs[:sync_count]

        total_synced += sync_count
        track_details.append(f"{sync_count}/{original_count}")

    if total_synced == 0:
        return SyncResult(False, "No segments to sync")

    # Cập nhật duration tổng project
    last_a = a_segs[-1]["target_timerange"]
    data["duration"] = last_a["start"] + last_a["duration"]

    capcut.save_draft_content(draft_path, data)

    mode_label = "speed" if video_mode == VIDEO_MODE_SPEED else "cut"
    msg = (f"Synced {len(video_tracks)} track(s) "
           f"[{', '.join(track_details)}] mode={mode_label}")

    return SyncResult(True, msg, total_synced, len(video_tracks))


def _get_material_type(data: dict, material_id: str) -> str:
    """Tìm type (photo/video) của material theo ID."""
    for v in data.get("materials", {}).get("videos", []):
        if v.get("id") == material_id:
            return v.get("type", "video")
    return "unknown"


def _update_speed_material(
    segment: dict,
    speed_materials: dict[str, dict],
    new_speed: float,
) -> None:
    """Cập nhật speed value trong material speeds được ref bởi segment."""
    for ref_id in segment.get("extra_material_refs", []):
        if ref_id in speed_materials:
            speed_materials[ref_id]["speed"] = new_speed
            return
