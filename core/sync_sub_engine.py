"""Sync Sub Engine — cut & import audio, export SRT, sync media theo sub."""

import os
import json
import copy
import shutil
import uuid
import re
from dataclasses import dataclass

from core import capcut
from core.create_project import (
    IMAGE_EXTS, VIDEO_EXTS, AUDIO_EXTS,
    _natural_sort_key, _get_media_info, _get_audio_duration,
    _make_video_material, _make_audio_material,
    _make_video_segment, _make_audio_segment,
    _make_speed_material, _make_canvas_material,
    _make_sound_channel, _make_beat_material,
)

VIDEO_MODE_CUT = "cut"
VIDEO_MODE_SPEED = "speed"

_uid = lambda: str(uuid.uuid4()).upper()


# ── Data classes ─────────────────────────────────────────────────────

@dataclass
class SyncSubResult:
    success: bool
    message: str
    sub_count: int = 0
    media_count: int = 0


@dataclass
class SubInfo:
    """Thông tin 1 sub segment."""
    index: int          # STT liên tục (1-based)
    start: int          # microseconds
    duration: int       # microseconds
    end: int            # microseconds
    text: str           # Nội dung sub
    audio_index: int = 0
    audio_name: str = ""


# ── Helpers ──────────────────────────────────────────────────────────

def _get_text_content(data: dict, material_id: str) -> str:
    """Lấy nội dung text từ material ID."""
    for m in data.get("materials", {}).get("texts", []):
        if m.get("id") == material_id:
            try:
                return json.loads(m["content"]).get("text", "")
            except (json.JSONDecodeError, KeyError):
                return ""
    return ""


def find_english_text_track(data: dict) -> dict | None:
    """Tìm text track tiếng Anh (track có sub tiếng Anh)."""
    text_tracks = [t for t in data.get("tracks", [])
                   if t.get("type") == "text" and len(t.get("segments", [])) > 0]
    if not text_tracks:
        return None
    if len(text_tracks) == 1:
        return text_tracks[0]

    # Kiểm tra nội dung sub đầu tiên để xác định ngôn ngữ
    for t in text_tracks:
        seg = t["segments"][0]
        text = _get_text_content(data, seg.get("material_id", ""))
        # Tiếng Anh: chủ yếu ký tự ASCII
        ascii_ratio = sum(1 for c in text if ord(c) < 128) / max(len(text), 1)
        if ascii_ratio > 0.8:
            return t

    return text_tracks[-1]  # fallback: track cuối


def find_all_text_tracks(data: dict) -> list[dict]:
    """Tìm tất cả text tracks có segments."""
    return [t for t in data.get("tracks", [])
            if t.get("type") == "text" and len(t.get("segments", [])) > 0]


def get_sorted_subs(text_track: dict, data: dict) -> list[SubInfo]:
    """Lấy danh sách sub sorted theo thời gian, đánh STT 1-based."""
    segs = sorted(text_track["segments"],
                  key=lambda s: s["target_timerange"]["start"])
    result = []
    for i, seg in enumerate(segs):
        start = seg["target_timerange"]["start"]
        dur = seg["target_timerange"]["duration"]
        text = _get_text_content(data, seg.get("material_id", ""))
        result.append(SubInfo(
            index=i + 1,
            start=start,
            duration=dur,
            end=start + dur,
            text=text,
        ))
    return result


def _scan_media_files(folder: str) -> list[str]:
    """Scan folder media, trả về list file paths sorted by natural order."""
    if not folder or not os.path.isdir(folder):
        return []
    files = []
    for f in sorted(os.listdir(folder), key=_natural_sort_key):
        ext = os.path.splitext(f)[1].lower()
        if ext in IMAGE_EXTS | VIDEO_EXTS:
            files.append(os.path.join(folder, f).replace("\\", "/"))
    return files


# ── Parse cut input ──────────────────────────────────────────────────

def parse_cut_input(text: str) -> list[tuple[int, list[int]]]:
    """
    Parse input dạng:
        0: 1, 2, 3        ← chèn ở đầu timeline (trước sub 1)
        55: 1, 2, 3       ← chèn sau sub 55
        443: 4, 5, 6, 7

    Returns: [(0, [1,2,3]), (55, [1,2,3]), ...]
    """
    result = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        parts = line.split(":", 1)
        try:
            sub_idx = int(parts[0].strip())
            audio_nums = [int(x.strip()) for x in parts[1].split(",") if x.strip()]
            if sub_idx >= 0 and audio_nums:
                result.append((sub_idx, audio_nums))
        except ValueError:
            continue
    return result


# ── Cut & Import Audio ───────────────────────────────────────────────

def cut_and_import_audio(
    draft_path: str,
    audio_folder: str,
    bg_video_path: str,
    cut_input_text: str,
    backup: bool = True,
    log_fn=None,
) -> SyncSubResult:
    """
    Cắt video tại vị trí sau mỗi sub chỉ định, chèn audio + video nền vào.

    Flow:
    1. Parse input → danh sách (sub_index, [audio_numbers])
    2. Tìm end time của mỗi sub (từ English text track)
    3. Xử lý từ cuối lên đầu (tránh sai timing do shift)
    4. Tại mỗi điểm cắt:
       - Split video segment tại cut_time
       - Chèn video nền với duration = tổng audio
       - Chèn audio segments
       - Shift tất cả sub + video phía sau
    """
    _log = log_fn or (lambda msg: None)

    json_path = os.path.join(draft_path, "draft_content.json")
    _log(f"  draft_path: {draft_path}")
    _log(f"  json exists: {os.path.isfile(json_path)}")
    if not os.path.isfile(json_path):
        return SyncSubResult(False, "draft_content.json not found")

    # Validate inputs
    _log(f"  audio_folder: {audio_folder} exists={os.path.isdir(audio_folder)}")
    _log(f"  bg_video: {bg_video_path} exists={os.path.isfile(bg_video_path)}")
    if not audio_folder or not os.path.isdir(audio_folder):
        return SyncSubResult(False, "Audio folder not found")
    if not bg_video_path or not os.path.isfile(bg_video_path):
        return SyncSubResult(False, "Video nền not found")

    cuts = parse_cut_input(cut_input_text)
    _log(f"  parsed cuts: {cuts}")
    if not cuts:
        return SyncSubResult(False, "Không parse được input. Format: STT: audio1, audio2, ...")

    if backup:
        bak_path = json_path + ".bak"
        if not os.path.isfile(bak_path):
            shutil.copy2(json_path, bak_path)
            _log(f"  backup created")
        else:
            _log(f"  backup already exists, skipping")

    data = capcut.load_draft_content(draft_path)
    _log(f"  loaded: {sum(len(t.get('segments',[])) for t in data['tracks'])} total segments")

    # Tìm English text track để xác định vị trí cắt
    en_track = find_english_text_track(data)
    if en_track is None:
        return SyncSubResult(False, "Không tìm thấy text track tiếng Anh")

    en_subs = get_sorted_subs(en_track, data)
    all_text_tracks = find_all_text_tracks(data)
    video_tracks = capcut.find_video_tracks(data)

    if not video_tracks:
        return SyncSubResult(False, "Không tìm thấy video track")

    # Validate sub indices
    for sub_idx, audio_nums in cuts:
        if sub_idx > len(en_subs):
            return SyncSubResult(False, f"Sub {sub_idx} không tồn tại (chỉ có {len(en_subs)} sub)")

    # Validate audio files exist
    for _, audio_nums in cuts:
        for n in audio_nums:
            found = False
            for ext in [".mp3", ".wav", ".aac", ".m4a", ".ogg"]:
                if os.path.isfile(os.path.join(audio_folder, f"{n}{ext}")):
                    found = True
                    break
            if not found:
                _log(f"  ERROR: Audio file {n} not found in {audio_folder}")
                return SyncSubResult(False, f"Audio file {n} not found in {audio_folder}")

    # Tạo material cho video nền
    bg_info = _get_media_info(bg_video_path)
    bg_mat = _make_video_material(bg_video_path, bg_info)
    data.setdefault("materials", {}).setdefault("videos", []).append(bg_mat)

    # Tìm hoặc tạo audio track
    audio_track = capcut.find_audio_track(data)
    if audio_track is None:
        audio_track = {
            "id": _uid(), "type": "audio", "segments": [],
            "flag": 0, "attribute": 0, "name": "", "is_default_name": True,
        }
        data["tracks"].append(audio_track)

    # Sort cuts theo sub_index tăng dần
    cuts.sort(key=lambda x: x[0])

    PADDING_BEFORE = 500_000  # 0.5s trước audio
    PADDING_AFTER = 500_000   # 0.5s sau audio

    # ── Phase 1: Thu thập thông tin tất cả cuts ──
    cut_infos = []  # (cut_time_original, insert_dur, audio_files, audio_durations)
    for sub_idx, audio_nums in cuts:
        if sub_idx == 0:
            # Special case: chèn ở ĐẦU timeline (trước sub 1)
            cut_time = 0
        else:
            sub = en_subs[sub_idx - 1]
            cut_time = sub.end

        audio_files = []
        audio_durations = []
        for n in audio_nums:
            af = None
            for ext in [".mp3", ".wav", ".aac", ".m4a", ".ogg"]:
                candidate = os.path.join(audio_folder, f"{n}{ext}").replace("\\", "/")
                if os.path.isfile(candidate):
                    af = candidate
                    break
            dur = _get_audio_duration(af)
            audio_files.append(af)
            audio_durations.append(dur)

        audio_total = sum(audio_durations)
        insert_dur = PADDING_BEFORE + audio_total + PADDING_AFTER
        cut_infos.append((cut_time, insert_dur, audio_files, audio_durations))

    # ── Phase 2: Hàm tính offset ──
    def calc_offset_strict(original_time):
        """Offset cho video/audio: chỉ shift nếu > cut_time."""
        offset = 0
        for ct, idur, _, _ in cut_infos:
            if original_time > ct:
                offset += idur
        return offset

    def calc_offset_inclusive(original_time):
        """Offset cho text: shift nếu >= cut_time (sub tại cut_time cũng shift)."""
        offset = 0
        for ct, idur, _, _ in cut_infos:
            if original_time >= ct:
                offset += idur
        return offset

    # ── Phase 3: Rebuild video track ──
    for vt in video_tracks:
        new_segs = []
        for seg in vt["segments"]:
            t_start = seg["target_timerange"]["start"]
            t_dur = seg["target_timerange"]["duration"]
            t_end = t_start + t_dur
            s_start = seg["source_timerange"]["start"]
            speed = seg.get("speed", 1.0)

            # Tìm tất cả cut points nằm trong segment này
            cuts_in_seg = [(ct, idur) for ct, idur, _, _ in cut_infos
                           if t_start < ct < t_end]

            if not cuts_in_seg:
                # Không có cut → shift toàn bộ segment.
                # Dùng INCLUSIVE: segment có t_start = cut_time (boundary, đặc biệt
                # khi sub_idx=0 → cut_time=0) cũng phải shift.
                offset = calc_offset_inclusive(t_start)
                seg["target_timerange"]["start"] = t_start + offset
                new_segs.append(seg)
            else:
                # Có cut(s) → split segment
                prev_time = t_start
                prev_source = s_start
                accumulated_insert = calc_offset_inclusive(t_start)

                for ct, idur in cuts_in_seg:
                    # Part trước cut
                    if ct > prev_time:
                        part = copy.deepcopy(seg)
                        part["id"] = _uid()
                        part_dur = ct - prev_time
                        part["target_timerange"]["start"] = prev_time + accumulated_insert
                        part["target_timerange"]["duration"] = part_dur
                        part["source_timerange"]["start"] = prev_source
                        part["source_timerange"]["duration"] = int(part_dur * speed)
                        new_segs.append(part)

                    accumulated_insert += idur
                    prev_source = prev_source + int((ct - prev_time) * speed)
                    prev_time = ct

                # Part cuối (sau cut cuối cùng)
                if prev_time < t_end:
                    part = copy.deepcopy(seg)
                    part["id"] = _uid()
                    part_dur = t_end - prev_time
                    part["target_timerange"]["start"] = prev_time + accumulated_insert
                    part["target_timerange"]["duration"] = part_dur
                    part["source_timerange"]["start"] = prev_source
                    part["source_timerange"]["duration"] = int(part_dur * speed)
                    new_segs.append(part)

        vt["segments"] = new_segs

    # ── Phase 4: Chèn video nền + audio tại mỗi cut ──
    total_audio_inserted = 0
    for cut_time, insert_dur, audio_files, audio_durations in cut_infos:
        offset = calc_offset_strict(cut_time)
        new_cut_time = cut_time + offset

        # Video nền
        sp_mat = _make_speed_material()
        cv_mat = _make_canvas_material()
        snd_mat = _make_sound_channel()
        data["materials"].setdefault("speeds", []).append(sp_mat)
        data["materials"].setdefault("canvases", []).append(cv_mat)
        data["materials"].setdefault("sound_channel_mappings", []).append(snd_mat)

        bg_seg = _make_video_segment(
            material_id=bg_mat["id"], start=new_cut_time, duration=insert_dur,
            speed_id=sp_mat["id"], canvas_id=cv_mat["id"], sound_id=snd_mat["id"],
        )
        bg_seg["source_timerange"]["start"] = 0
        bg_seg["source_timerange"]["duration"] = min(bg_info["duration"], insert_dur)
        bg_seg["volume"] = 0.0  # Tắt âm thanh video nền
        bg_seg["last_nonzero_volume"] = 0.0
        video_tracks[0]["segments"].append(bg_seg)

        # Audio segments
        current_time = new_cut_time + PADDING_BEFORE
        for af, dur in zip(audio_files, audio_durations):
            a_mat = _make_audio_material(af, dur)
            a_sp = _make_speed_material()
            a_snd = _make_sound_channel()
            a_beat = _make_beat_material()
            data["materials"].setdefault("audios", []).append(a_mat)
            data["materials"]["speeds"].append(a_sp)
            data["materials"]["sound_channel_mappings"].append(a_snd)
            data["materials"].setdefault("beats", []).append(a_beat)

            a_seg = _make_audio_segment(
                material_id=a_mat["id"], start=current_time, duration=dur,
                speed_id=a_sp["id"], sound_id=a_snd["id"], beat_id=a_beat["id"],
            )
            audio_track["segments"].append(a_seg)
            current_time += dur

        total_audio_inserted += len(audio_files)

    # ── Phase 5: Shift tất cả text segments ──
    for tt in all_text_tracks:
        for seg in tt["segments"]:
            orig_start = seg["target_timerange"]["start"]
            seg["target_timerange"]["start"] = orig_start + calc_offset_inclusive(orig_start)

    # Sort all segments
    for vt in video_tracks:
        vt["segments"].sort(key=lambda s: s["target_timerange"]["start"])
    audio_track["segments"].sort(key=lambda s: s["target_timerange"]["start"])

    # Cập nhật duration tổng project
    all_ends = []
    for t in data["tracks"]:
        for seg in t.get("segments", []):
            end = seg["target_timerange"]["start"] + seg["target_timerange"]["duration"]
            all_ends.append(end)
    if all_ends:
        data["duration"] = max(all_ends)

    _log(f"  saving {sum(len(t.get('segments',[])) for t in data['tracks'])} segments...")
    capcut.save_draft_content(draft_path, data)
    _log("  saved OK")

    return SyncSubResult(
        True,
        f"Đã cắt tại {len(cuts)} vị trí, chèn {total_audio_inserted} audio",
        sub_count=len(cuts),
        media_count=total_audio_inserted,
    )


# ── Parse delete input ───────────────────────────────────────────────

def parse_delete_input(text: str) -> list[int]:
    """
    Parse input dạng:
        5 - 6
        20
        468 - 469
    Returns: sorted list of unique sub indices [5, 6, 20, 468, 469]
    """
    result = set()
    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        if "-" in line:
            parts = line.split("-", 1)
            try:
                start = int(parts[0].strip())
                end = int(parts[1].strip())
                for i in range(start, end + 1):
                    result.add(i)
            except ValueError:
                continue
        else:
            try:
                result.add(int(line.strip()))
            except ValueError:
                continue
    return sorted(result)


# ── Delete SRT & Cut Video ───────────────────────────────────────────

def delete_srt_and_cut(
    draft_path: str,
    delete_input_text: str,
    backup: bool = True,
    log_fn=None,
) -> SyncSubResult:
    """
    Xóa sub segments và cắt bỏ video tương ứng, shift lại để lấp khoảng trống.

    Flow:
    1. Parse input → danh sách sub indices cần xóa
    2. Tìm timing từng sub → gộp liền kề thành vùng xóa
    3. Xóa sub khỏi tất cả text tracks
    4. Cắt video: loại bỏ phần video trong vùng xóa
    5. Shift ngược tất cả segments phía sau mỗi vùng xóa
    """
    _log = log_fn or (lambda msg: None)

    json_path = os.path.join(draft_path, "draft_content.json")
    _log(f"  draft_path: {draft_path}")
    _log(f"  json exists: {os.path.isfile(json_path)}")
    if not os.path.isfile(json_path):
        return SyncSubResult(False, "draft_content.json not found")

    indices = parse_delete_input(delete_input_text)
    _log(f"  parsed indices: {indices}")
    if not indices:
        return SyncSubResult(False, "Không parse được input. Format: 5-6 hoặc 20")

    if backup:
        bak_path = json_path + ".bak"
        if not os.path.isfile(bak_path):
            shutil.copy2(json_path, bak_path)
            _log("  backup created")
        else:
            _log("  backup exists, skipping")

    data = capcut.load_draft_content(draft_path)
    _log(f"  loaded tracks: {[(t['type'], len(t.get('segments',[]))) for t in data['tracks']]}")

    en_track = find_english_text_track(data)
    if en_track is None:
        _log("  ERROR: no english text track found")
        return SyncSubResult(False, "Không tìm thấy text track tiếng Anh")

    en_subs = get_sorted_subs(en_track, data)
    _log(f"  EN subs: {len(en_subs)}")

    # Validate indices
    for idx in indices:
        if idx < 1 or idx > len(en_subs):
            _log(f"  ERROR: sub {idx} out of range (1-{len(en_subs)})")
            return SyncSubResult(False, f"Sub {idx} không tồn tại (1-{len(en_subs)})")

    # Tìm timing các sub cần xóa, gộp liền kề thành vùng
    delete_ranges = []  # [(start, end, duration)]
    i = 0
    while i < len(indices):
        j = i
        while j + 1 < len(indices) and indices[j + 1] == indices[j] + 1:
            j += 1
        range_start = en_subs[indices[i] - 1].start
        range_end = en_subs[indices[j] - 1].end
        delete_ranges.append((range_start, range_end, range_end - range_start))
        _log(f"  range: sub {indices[i]}-{indices[j]} = {range_start/1e6:.2f}s - {range_end/1e6:.2f}s ({(range_end-range_start)/1e6:.2f}s)")
        i = j + 1

    _log(f"  total delete ranges: {len(delete_ranges)}")
    all_text_tracks = find_all_text_tracks(data)
    video_tracks = capcut.find_video_tracks(data)
    audio_track = capcut.find_audio_track(data)

    # ── Tính offset giảm cho mỗi vị trí trên timeline gốc ──
    def calc_shrink(original_time):
        """Tính tổng duration cần shift ngược cho vị trí này."""
        shrink = 0
        for r_start, r_end, r_dur in delete_ranges:
            if original_time >= r_end:
                shrink += r_dur
        return shrink

    # ── Xử lý video tracks ──
    for vt in video_tracks:
        new_segs = []
        for seg in vt["segments"]:
            t_start = seg["target_timerange"]["start"]
            t_dur = seg["target_timerange"]["duration"]
            t_end = t_start + t_dur
            s_start = seg["source_timerange"]["start"]
            speed = seg.get("speed", 1.0)

            # Tìm delete ranges overlap với segment này
            overlaps = [(rs, re, rd) for rs, re, rd in delete_ranges
                        if rs < t_end and re > t_start]

            if not overlaps:
                # Không overlap → shift ngược
                shrink = calc_shrink(t_start)
                seg["target_timerange"]["start"] = t_start - shrink
                new_segs.append(seg)
            else:
                # Có overlap → cắt segment, giữ phần ngoài vùng xóa
                cursor = t_start
                source_cursor = s_start

                for rs, re, rd in overlaps:
                    # Phần trước vùng xóa
                    if cursor < rs:
                        part = copy.deepcopy(seg)
                        part["id"] = _uid()
                        part_dur = rs - cursor
                        shrink = calc_shrink(cursor)
                        part["target_timerange"]["start"] = cursor - shrink
                        part["target_timerange"]["duration"] = part_dur
                        part["source_timerange"]["start"] = source_cursor
                        part["source_timerange"]["duration"] = int(part_dur * speed)
                        new_segs.append(part)

                    # Skip qua vùng xóa
                    skip_start = max(cursor, rs)
                    skip_end = min(t_end, re)
                    source_cursor += int((skip_end - cursor) * speed) if cursor < re else 0
                    if cursor < rs:
                        source_cursor = s_start + int((rs - t_start) * speed) + int((re - rs) * speed)
                    else:
                        source_cursor = s_start + int((re - t_start) * speed)
                    cursor = re

                # Phần sau vùng xóa cuối cùng
                if cursor < t_end:
                    part = copy.deepcopy(seg)
                    part["id"] = _uid()
                    part_dur = t_end - cursor
                    shrink = calc_shrink(cursor)
                    part["target_timerange"]["start"] = cursor - shrink
                    part["target_timerange"]["duration"] = part_dur
                    source_offset = int((cursor - t_start) * speed)
                    part["source_timerange"]["start"] = s_start + source_offset
                    part["source_timerange"]["duration"] = int(part_dur * speed)
                    new_segs.append(part)

        vt["segments"] = new_segs

    # ── Xóa + shift text tracks ──
    delete_set = set(indices)
    for tt in all_text_tracks:
        segs_sorted = sorted(tt["segments"],
                             key=lambda s: s["target_timerange"]["start"])
        # Tìm sub index trong track này dựa trên timing match với en_subs
        new_segs = []
        for seg in segs_sorted:
            seg_start = seg["target_timerange"]["start"]
            seg_end = seg_start + seg["target_timerange"]["duration"]

            # Kiểm tra xem segment này có nằm trong vùng xóa không
            in_delete = False
            for rs, re, _ in delete_ranges:
                if seg_start >= rs and seg_end <= re:
                    in_delete = True
                    break

            if in_delete:
                continue  # Xóa segment này

            # Shift ngược
            shrink = calc_shrink(seg_start)
            seg["target_timerange"]["start"] = seg_start - shrink
            new_segs.append(seg)

        tt["segments"] = new_segs

    # ── Shift audio track ──
    if audio_track:
        new_segs = []
        for seg in audio_track["segments"]:
            seg_start = seg["target_timerange"]["start"]
            seg_end = seg_start + seg["target_timerange"]["duration"]

            # Audio nằm hoàn toàn trong vùng xóa → xóa
            in_delete = False
            for rs, re, _ in delete_ranges:
                if seg_start >= rs and seg_end <= re:
                    in_delete = True
                    break

            if in_delete:
                continue

            # Shift ngược
            shrink = calc_shrink(seg_start)
            seg["target_timerange"]["start"] = seg_start - shrink
            new_segs.append(seg)

        audio_track["segments"] = new_segs

    # Cập nhật duration
    all_ends = []
    for t in data["tracks"]:
        for seg in t.get("segments", []):
            end = seg["target_timerange"]["start"] + seg["target_timerange"]["duration"]
            all_ends.append(end)
    if all_ends:
        data["duration"] = max(all_ends)

    _log(f"  saving... tracks: {[(t['type'], len(t.get('segments',[]))) for t in data['tracks']]}")
    capcut.save_draft_content(draft_path, data)
    _log("  saved OK")

    total_dur = sum(rd for _, _, rd in delete_ranges)
    return SyncSubResult(
        True,
        f"Đã xóa {len(indices)} sub ({len(delete_ranges)} vùng, -{total_dur/1e6:.1f}s)",
        sub_count=len(indices),
    )


# ── Export SRT Info ──────────────────────────────────────────────────

def export_srt_info(data: dict) -> str:
    """
    Xuất thông tin SRT từ English text track.
    Nếu có audio track → group theo audio.
    Nếu không → xuất toàn bộ sub.
    """
    audio_track = capcut.find_audio_track(data)

    if audio_track and len(audio_track.get("segments", [])) > 0:
        return _export_srt_by_audio(data)
    else:
        return _export_srt_all(data)


def _export_srt_by_audio(data: dict) -> str:
    """Xuất SRT grouped theo audio segments (dùng cho project đã có audio)."""
    en_track = find_english_text_track(data)
    if en_track is None:
        return "Không tìm thấy text track tiếng Anh."

    audio_track = capcut.find_audio_track(data)
    a_segs = sorted(audio_track["segments"],
                    key=lambda s: s["target_timerange"]["start"])
    en_subs = get_sorted_subs(en_track, data)

    # Map audio names
    audio_names = {}
    for seg in a_segs:
        mat_id = seg.get("material_id", "")
        for m in data.get("materials", {}).get("audios", []):
            if m.get("id") == mat_id:
                audio_names[mat_id] = os.path.basename(m.get("path", ""))
                break

    lines = []
    assigned = set()
    stt = 1

    for ai, a_seg in enumerate(a_segs):
        a_start = a_seg["target_timerange"]["start"]
        a_end = a_start + a_seg["target_timerange"]["duration"]
        a_name = audio_names.get(a_seg.get("material_id", ""), f"audio_{ai+1}")

        lines.append(f"==Audio {ai + 1}: {a_name}==")

        audio_subs = []
        for sub in en_subs:
            if sub.index in assigned:
                continue
            if sub.start >= a_start and sub.start < a_end:
                audio_subs.append(sub)
                assigned.add(sub.index)

        digits = max(3, len(str(len(en_subs))))
        for sub in audio_subs:
            lines.append(str(stt).zfill(digits))
            lines.append(f"{sub.start / 1e6:.2f}s - {sub.end / 1e6:.2f}s")
            lines.append(sub.text)
            lines.append("")
            stt += 1

    return "\n".join(lines)


def _export_srt_all(data: dict) -> str:
    """Xuất toàn bộ SRT (chưa có audio track)."""
    en_track = find_english_text_track(data)
    if en_track is None:
        return "Không tìm thấy text track tiếng Anh."

    en_subs = get_sorted_subs(en_track, data)
    digits = max(3, len(str(len(en_subs))))

    lines = []
    for sub in en_subs:
        lines.append(str(sub.index).zfill(digits))
        lines.append(f"{sub.start / 1e6:.2f}s - {sub.end / 1e6:.2f}s")
        lines.append(sub.text)
        lines.append("")

    lines.append(f"=== Total: {len(en_subs)} subs ===")
    return "\n".join(lines)


# ── Sync Media-Sub ───────────────────────────────────────────────────

def sync_media_sub(
    draft_path: str,
    speed: float = 1.3,
    backup: bool = True,
    log_fn=None,
) -> SyncSubResult:
    """
    Thay video nền bằng video gốc cắt random @speed.

    Flow:
    1. Detect video nền vs video gốc trên timeline
    2. Gộp source từ tất cả video gốc thành pool
    3. Random cắt từ pool @speed thay thế từng video nền
    """
    import random
    _log = log_fn or (lambda msg: None)

    json_path = os.path.join(draft_path, "draft_content.json")
    _log(f"  draft_path: {draft_path}")
    if not os.path.isfile(json_path):
        return SyncSubResult(False, "draft_content.json not found")

    if backup:
        bak_path = json_path + ".bak"
        if not os.path.isfile(bak_path):
            shutil.copy2(json_path, bak_path)

    data = capcut.load_draft_content(draft_path)
    video_tracks = capcut.find_video_tracks(data)
    if not video_tracks:
        return SyncSubResult(False, "Không tìm thấy video track")

    # ── Detect video nền vs video gốc ──
    # Đếm số lần xuất hiện của mỗi material
    mat_names = {}
    for m in data.get("materials", {}).get("videos", []):
        mat_names[m["id"]] = os.path.basename(m.get("path", ""))

    mat_count = {}
    all_segs = []
    for vt in video_tracks:
        for seg in vt.get("segments", []):
            mid = seg.get("material_id", "")
            mname = mat_names.get(mid, "")
            mat_count[mname] = mat_count.get(mname, 0) + 1
            all_segs.append(seg)

    if len(mat_count) < 2:
        return SyncSubResult(False, "Cần ít nhất 2 loại video (gốc + nền)")

    # Video nền = material chứa "nen" trong tên
    bg_name = None
    for name in mat_count:
        if "nen" in name.lower():
            bg_name = name
            break

    if bg_name is None:
        _log(f"  ERROR: không tìm thấy video nền (cần file có 'nen' trong tên)")
        _log(f"  materials found: {list(mat_count.keys())}")
        return SyncSubResult(False, "Không tìm thấy video nền. Đã chạy Sync Media rồi?")

    _log(f"  video nền: '{bg_name}' ({mat_count[bg_name]} segments)")
    _log(f"  video gốc: {[n for n in mat_count if n != bg_name]}")

    # Phân loại segments
    bg_segments = []   # video nền → sẽ thay thế
    src_segments = []  # video gốc → pool source + giữ nguyên

    for seg in all_segs:
        mid = seg.get("material_id", "")
        mname = mat_names.get(mid, "")
        if mname == bg_name:
            bg_segments.append(seg)
        else:
            src_segments.append(seg)

    bg_segments.sort(key=lambda s: s["target_timerange"]["start"])
    src_segments.sort(key=lambda s: s["target_timerange"]["start"])

    if not bg_segments:
        return SyncSubResult(False, "Không tìm thấy video nền trên timeline")
    if not src_segments:
        return SyncSubResult(False, "Không tìm thấy video gốc trên timeline")

    # ── Tìm audio track ──
    audio_track = capcut.find_audio_track(data)
    if not audio_track or not audio_track.get("segments"):
        return SyncSubResult(False, "Không tìm thấy audio narration")

    a_segs = sorted(audio_track["segments"],
                    key=lambda s: s["target_timerange"]["start"])
    _log(f"  {len(bg_segments)} video nền, {len(src_segments)} video gốc, {len(a_segs)} audio")

    # ── Build source pool từ video gốc (speed=1.0) ──
    pool = []
    for seg in src_segments:
        if seg.get("speed", 1.0) == 1.0:
            pool.append((
                seg["material_id"],
                seg["source_timerange"]["start"],
                seg["source_timerange"]["duration"],
            ))
    total_pool = sum(p[2] for p in pool)
    _log(f"  pool total: {total_pool/1e6:.1f}s ({len(pool)} segments)")

    # ── Với mỗi video nền: tìm audio nằm trong, tạo video cho mỗi audio ──
    # Phần padding (trước audio đầu, sau audio cuối) cũng tạo video lấp đầy
    new_segments = []
    replaced = 0

    for bg_seg in bg_segments:
        bg_start = bg_seg["target_timerange"]["start"]
        bg_end = bg_start + bg_seg["target_timerange"]["duration"]

        # Tìm audio nằm trong video nền này
        audios_in_bg = []
        for a_seg in a_segs:
            a_start = a_seg["target_timerange"]["start"]
            a_end = a_start + a_seg["target_timerange"]["duration"]
            if a_start >= bg_start and a_end <= bg_end:
                audios_in_bg.append(a_seg)

        # Tạo danh sách các đoạn cần lấp: padding trước, mỗi audio, padding sau
        fill_ranges = []  # (target_start, target_duration)

        if audios_in_bg:
            first_a = audios_in_bg[0]["target_timerange"]["start"]
            last_a_end = (audios_in_bg[-1]["target_timerange"]["start"] +
                         audios_in_bg[-1]["target_timerange"]["duration"])

            # Padding trước audio đầu
            if first_a > bg_start:
                fill_ranges.append((bg_start, first_a - bg_start))

            # Mỗi audio
            for a_seg in audios_in_bg:
                fill_ranges.append((
                    a_seg["target_timerange"]["start"],
                    a_seg["target_timerange"]["duration"],
                ))

            # Padding sau audio cuối
            if last_a_end < bg_end:
                fill_ranges.append((last_a_end, bg_end - last_a_end))
        else:
            # Không có audio → lấp toàn bộ video nền
            fill_ranges.append((bg_start, bg_seg["target_timerange"]["duration"]))

        # Tạo video segment cho mỗi fill range
        for target_start, target_dur in fill_ranges:
            source_needed = int(target_dur * speed)

            valid_pools = [(mid, ss, sd) for mid, ss, sd in pool if sd >= source_needed]
            if not valid_pools:
                valid_pools = sorted(pool, key=lambda x: x[2], reverse=True)
            if not valid_pools:
                continue

            mat_id, pool_start, pool_dur = random.choice(valid_pools)
            max_offset = max(0, pool_dur - source_needed)
            rand_offset = random.randint(0, max(1, max_offset))
            src_start = pool_start + rand_offset
            src_dur = min(source_needed, pool_dur - rand_offset)

            sp_mat = _make_speed_material()
            cv_mat = _make_canvas_material()
            snd_mat = _make_sound_channel()
            sp_mat["speed"] = speed
            data["materials"].setdefault("speeds", []).append(sp_mat)
            data["materials"].setdefault("canvases", []).append(cv_mat)
            data["materials"].setdefault("sound_channel_mappings", []).append(snd_mat)

            new_seg = _make_video_segment(
                material_id=mat_id,
                start=target_start,
                duration=target_dur,
                speed_id=sp_mat["id"],
                canvas_id=cv_mat["id"],
                sound_id=snd_mat["id"],
            )
            new_seg["source_timerange"]["start"] = src_start
            new_seg["source_timerange"]["duration"] = src_dur
            new_seg["speed"] = speed
            new_seg["volume"] = 0.0  # Tắt âm thanh video trên audio
            new_seg["last_nonzero_volume"] = 0.0

            new_segments.append(new_seg)
            replaced += 1

    _log(f"  created {replaced} video segments (from {len(bg_segments)} bg, {len(a_segs)} audio) @{speed}x")

    # ── Rebuild video track: giữ video gốc + thay video nền bằng new_segments ──
    final_segments = list(src_segments) + new_segments
    final_segments.sort(key=lambda s: s["target_timerange"]["start"])

    data["tracks"] = [t for t in data["tracks"] if t.get("type") != "video"]
    data["tracks"].insert(0, {
        "id": _uid(), "type": "video", "segments": final_segments,
        "flag": 0, "attribute": 0, "name": "", "is_default_name": True,
    })

    _log(f"  saving {sum(len(t.get('segments',[])) for t in data['tracks'])} segments...")
    capcut.save_draft_content(draft_path, data)
    _log("  saved OK")

    return SyncSubResult(
        True,
        f"Đã tạo {replaced} video @{speed}x thay {len(bg_segments)} video nền (random)",
        sub_count=replaced,
    )


# ── Parse picture law input ──────────────────────────────────────────

_PICTURE_LAW_MAX_DISPLAY = 5_000_000  # 5 giây hiển thị tối đa

# 10 animation In cơ bản (CapCut built-in, luôn hoạt động)
_LAW_ANIM_IN_IDS = [
    "6798320778182922760",  # Fade In
    "7428455170477968646",  # Fade In (alt)
    "7591713637883071745",  # Plain Fade-In
    "7592158908869856529",  # Close-In Fade
    "7591708891096911120",  # Blink Fade
    "7592672543039819025",  # Blur & Fade
    "6798332871267324423",  # Slide Left
    "6798333076469453320",  # Slide Right
    "6798333705401143816",  # Slide Down
    "7428457240924916997",  # Mini Zoom
]

# 10 animation Out cơ bản
_LAW_ANIM_OUT_IDS = [
    "6798320902548230669",  # Fade Out
    "7428455170478066950",  # Fade Out (alt)
    "6724919382104871427",  # Fade Out (classic)
    "7568299335264390401",  # Flip Fade
    "7534984788604620085",  # Fade-out Dab
    "7540499373445139713",  # Blossom Fade
    "7522413719364619536",  # Grain Fades
    "7612001165626068232",  # Heartbeat Fade-Out
    "7616882928823307527",  # Narrowed Fade
    "7607242532749118725",  # Wispy Fade-Out
]


def parse_picture_law_input(text: str) -> list[tuple[str, list[int]]]:
    """
    Parse input dạng:
        law_vanhook: 4
        card1_terry: 2, 3, 4
    Returns: [(filename, [audio_numbers]), ...]
    """
    result = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        parts = line.split(":", 1)
        try:
            name = parts[0].strip()
            nums = [int(x.strip()) for x in parts[1].split(",") if x.strip()]
            if name and nums:
                result.append((name, nums))
        except ValueError:
            continue
    return result


# ── Insert Picture Law ───────────────────────────────────────────────

def insert_picture_law(
    draft_path: str,
    picture_folder: str,
    input_text: str,
    add_animation: bool = True,
    backup: bool = True,
    log_fn=None,
) -> SyncSubResult:
    """
    Chèn ảnh law vào track mới, đồng bộ timing với audio narration.
    Hỗ trợ 1 ảnh → 1 hoặc nhiều audio. Hiển thị tối đa 5s đầu mỗi audio.
    Tự động chèn animation in/out random.
    """
    import random
    from core.animation_engine import _make_animation_entry
    from core.animation_library import AnimationInfo

    _log = log_fn or (lambda msg: None)

    json_path = os.path.join(draft_path, "draft_content.json")
    _log(f"  draft_path: {draft_path}")
    if not os.path.isfile(json_path):
        return SyncSubResult(False, "draft_content.json not found")

    if not picture_folder or not os.path.isdir(picture_folder):
        return SyncSubResult(False, "Picture folder not found")

    mappings = parse_picture_law_input(input_text)
    _log(f"  parsed: {len(mappings)} entries")
    if not mappings:
        return SyncSubResult(False, "Không parse được input. Format: filename: audio1, audio2")

    if backup:
        bak_path = json_path + ".bak"
        if not os.path.isfile(bak_path):
            shutil.copy2(json_path, bak_path)

    data = capcut.load_draft_content(draft_path)

    # Tìm audio track
    audio_track = capcut.find_audio_track(data)
    if not audio_track or not audio_track.get("segments"):
        return SyncSubResult(False, "Không tìm thấy audio narration")

    # Build map: audio number → segment
    audio_map = {}
    for seg in audio_track["segments"]:
        mat_id = seg.get("material_id", "")
        for m in data.get("materials", {}).get("audios", []):
            if m.get("id") == mat_id:
                fname = os.path.basename(m.get("path", ""))
                name_no_ext = os.path.splitext(fname)[0]
                try:
                    audio_map[int(name_no_ext)] = seg
                except ValueError:
                    pass
                break

    _log(f"  audio map: {sorted(audio_map.keys())}")

    # Load animation library nếu cần
    anim_in_list = []
    anim_out_list = []
    if add_animation:
        try:
            from core import animation_library as alib
            lib = alib.scan_library()
            anim_in_list = [a for a in lib if a.resource_id in _LAW_ANIM_IN_IDS]
            anim_out_list = [a for a in lib if a.resource_id in _LAW_ANIM_OUT_IDS]
            _log(f"  animations: {len(anim_in_list)} in, {len(anim_out_list)} out")
        except Exception as e:
            _log(f"  WARN: animation load failed: {e}")
            add_animation = False

    IMAGE_EXTS_ALL = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    new_segments = []
    new_mat_anims = []
    inserted = 0

    for pic_name, audio_nums in mappings:
        # Tìm file ảnh
        pic_path = None
        for ext in IMAGE_EXTS_ALL:
            candidate = os.path.join(picture_folder, f"{pic_name}{ext}").replace("\\", "/")
            if os.path.isfile(candidate):
                pic_path = candidate
                break

        if pic_path is None:
            _log(f"  WARN: ảnh '{pic_name}' không tìm thấy")
            continue

        # Tạo material cho ảnh (1 lần cho tất cả segments của ảnh này)
        info = _get_media_info(pic_path)
        v_mat = _make_video_material(pic_path, info)
        data["materials"].setdefault("videos", []).append(v_mat)

        # Tạo 1 segment cho mỗi audio
        for audio_num in audio_nums:
            if audio_num not in audio_map:
                _log(f"  WARN: audio {audio_num} không tồn tại")
                continue

            a_seg = audio_map[audio_num]
            a_start = a_seg["target_timerange"]["start"]
            a_dur = a_seg["target_timerange"]["duration"]

            # Duration: tối đa 5s, hoặc full nếu audio < 5s
            display_dur = min(a_dur, _PICTURE_LAW_MAX_DISPLAY)

            sp_mat = _make_speed_material()
            cv_mat = _make_canvas_material()
            snd_mat = _make_sound_channel()
            data["materials"].setdefault("speeds", []).append(sp_mat)
            data["materials"].setdefault("canvases", []).append(cv_mat)
            data["materials"].setdefault("sound_channel_mappings", []).append(snd_mat)

            seg = _make_video_segment(
                material_id=v_mat["id"],
                start=a_start,
                duration=display_dur,
                speed_id=sp_mat["id"],
                canvas_id=cv_mat["id"],
                sound_id=snd_mat["id"],
            )

            # Animation in + out (random)
            if add_animation and anim_in_list and anim_out_list:
                anim_in = random.choice(anim_in_list)
                anim_out = random.choice(anim_out_list)
                anim_dur = min(500_000, display_dur // 2)  # 0.5s hoặc nửa segment

                in_entry = _make_animation_entry(anim_in, "in", anim_dur, 0)
                out_start = max(0, display_dur - anim_dur)
                out_entry = _make_animation_entry(anim_out, "out", anim_dur, out_start)

                mat_anim = {
                    "id": _uid(),
                    "type": "sticker_animation",
                    "animations": [in_entry, out_entry],
                    "multi_language_current": "none",
                }
                new_mat_anims.append(mat_anim)
                seg["extra_material_refs"].append(mat_anim["id"])

            new_segments.append(seg)
            inserted += 1
            _log(f"  {pic_name} → audio {audio_num} @{a_start/1e6:.1f}s dur={display_dur/1e6:.1f}s")

    if not new_segments:
        return SyncSubResult(False, "Không chèn được ảnh nào")

    # Add animation materials
    if new_mat_anims:
        data["materials"].setdefault("material_animations", []).extend(new_mat_anims)

    # Tạo track mới (overlay)
    new_track = {
        "id": _uid(),
        "type": "video",
        "segments": sorted(new_segments, key=lambda s: s["target_timerange"]["start"]),
        "flag": 0,
        "attribute": 0,
        "name": "",
        "is_default_name": True,
    }

    # Chèn track sau video track đầu tiên
    insert_idx = 0
    for i, t in enumerate(data["tracks"]):
        if t.get("type") == "video":
            insert_idx = i + 1
            break
    data["tracks"].insert(insert_idx, new_track)

    _log(f"  saving {sum(len(t.get('segments',[])) for t in data['tracks'])} segments...")
    capcut.save_draft_content(draft_path, data)
    _log("  saved OK")

    anim_text = " + animation" if add_animation else ""
    return SyncSubResult(
        True,
        f"Đã chèn {inserted} ảnh law{anim_text}",
        sub_count=inserted,
    )
