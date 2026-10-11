"""Sync Sub Engine — cut & import audio, export SRT, sync media theo sub."""

import os
import json
import copy
import random
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


# ── BDC: mapping ảnh law theo TÊN FILE ───────────────────────────────

def build_picture_map_from_filenames(picture_folder: str) -> tuple[str, list[str]]:
    """Sinh input mapping ảnh→audio từ TÊN FILE (quy trình BDC).

    Tên file là số audio: '03.png' → audio 3, '20.png' → audio 20.
    Khác 17 PROMAX vốn đọc mapping từ 3-insert-law-picture.txt.

    Trả về (input_text, warnings). input_text dùng thẳng cho insert_picture_law
    — giữ nguyên tên gốc bên trái ('03: 3') để engine tìm đúng file '03.png'.
    """
    warns = []
    if not picture_folder or not os.path.isdir(picture_folder):
        return "", ["Không tìm thấy folder 'law picture'"]

    pairs = []  # (audio_num, stem)
    for f in sorted(os.listdir(picture_folder), key=_natural_sort_key):
        stem, ext = os.path.splitext(f)
        if ext.lower() not in IMAGE_EXTS:
            continue
        try:
            num = int(stem)
        except ValueError:
            warns.append(f"bỏ qua '{f}' — tên file không phải số")
            continue
        pairs.append((num, stem))

    seen = {}
    lines = []
    for num, stem in sorted(pairs):
        if num in seen:
            warns.append(f"'{stem}' trùng số audio {num} với '{seen[num]}' — bỏ qua")
            continue
        seen[num] = stem
        lines.append(f"{stem}: {num}")

    if not lines:
        warns.append("Không có ảnh nào đặt tên bằng số trong 'law picture'")
    return "\n".join(lines), warns


# ── Preflight cho quy trình 17 PROMAX ────────────────────────────────

def preflight_17promax(draft_path: str, audio_folder: str, bg_video_path: str,
                       picture_folder: str, cut_text: str, delete_text: str,
                       pic_text: str) -> list[str]:
    """Kiểm tra input của cả 4 bước TRƯỚC khi ghi bất cứ gì. Trả về list lỗi.

    Bước 1 và 2 ghi vào draft trước khi bước sau kịp validate → chỉ cần bước 2
    hoặc 4 sai là project nằm dở dang (đã cắt/chèn audio nhưng chưa xoá sub,
    chưa sync, chưa chèn ảnh) và chạy lại thì cắt chồng. Hàm này chặn từ đầu.

    Chỉ kiểm được input tĩnh: file tồn tại, parse được, index trong phạm vi.
    Bước 3 (Sync Media) phụ thuộc trạng thái sau bước 1-2 nên không tiền kiểm được.
    """
    errs = []

    json_path = os.path.join(draft_path, "draft_content.json")
    if not os.path.isfile(json_path):
        return ["draft_content.json không tồn tại"]

    # ── file/folder ──
    if not audio_folder or not os.path.isdir(audio_folder):
        errs.append("Thiếu folder narration")
    if not bg_video_path or not os.path.isfile(bg_video_path):
        errs.append("Thiếu video nền")
    if not picture_folder or not os.path.isdir(picture_folder):
        errs.append("Thiếu folder 'law picture'")

    try:
        data = capcut.load_draft_content(draft_path)
    except Exception as e:
        return errs + [f"Không đọc được draft: {e}"]

    en_track = find_english_text_track(data)
    if en_track is None:
        return errs + ["Không tìm thấy text track tiếng Anh"]
    n_subs = len(get_sorted_subs(en_track, data))

    # ── bước 1: cut & import audio ──
    cuts = parse_cut_input(cut_text)
    if not cuts:
        errs.append("1-insert-radio.txt: không parse được (format 'STT: 1, 2, 3')")
    for sub_idx, audio_nums in cuts:
        if sub_idx > n_subs:
            errs.append(f"1-insert-radio.txt: sub {sub_idx} vượt phạm vi "
                        f"(project có {n_subs} sub)")
        for n in audio_nums:
            if not any(os.path.isfile(os.path.join(audio_folder, f"{n}{ext}"))
                       for ext in (".mp3", ".wav", ".aac", ".m4a", ".ogg")):
                errs.append(f"1-insert-radio.txt: thiếu file audio {n} trong narration/")

    # ── bước 2: xoá SRT (chỉ cảnh báo, engine tự bỏ index thừa) ──
    if delete_text.strip():
        del_idx = parse_delete_input(delete_text)
        if not del_idx:
            errs.append("2-delete-narration.txt: không parse được (format '5-6' hoặc '20')")
        elif all(i > n_subs or i < 1 for i in del_idx):
            errs.append(f"2-delete-narration.txt: mọi sub đều vượt phạm vi "
                        f"(project có {n_subs} sub)")

    # ── bước 4: insert picture ──
    mappings = parse_picture_law_input(pic_text)
    if not mappings:
        errs.append("3-insert-law-picture.txt: không parse được "
                    "(format 'tên ảnh: 1, 2')")
    elif picture_folder and os.path.isdir(picture_folder):
        have = {os.path.splitext(f)[0].lower() for f in os.listdir(picture_folder)}
        for name, _ in mappings:
            if os.path.splitext(str(name))[0].lower() not in have:
                errs.append(f"3-insert-law-picture.txt: không thấy ảnh '{name}' "
                            f"trong 'law picture/'")

    return errs


def preflight_bdc(draft_path: str, audio_folder: str, bg_video_path: str,
                  picture_folder: str, cut_text: str, delete_text: str) -> list[str]:
    """Preflight cho BDC (3 bước). Như preflight_17promax nhưng mapping ảnh law
    suy từ tên file thay vì đọc 3-insert-law-picture.txt, và không có Sync Media.
    """
    pic_text, _ = build_picture_map_from_filenames(picture_folder)
    errs = preflight_17promax(draft_path, audio_folder, bg_video_path,
                              picture_folder, cut_text, delete_text, pic_text)
    # Thông báo hợp ngữ cảnh BDC: không có file txt nào cho bước ảnh
    return [e.replace("3-insert-law-picture.txt: không parse được "
                      "(format 'tên ảnh: 1, 2')",
                      "law picture/: không có ảnh nào đặt tên bằng số")
            for e in errs]


# ── Cut & Import Audio ───────────────────────────────────────────────

def cut_and_import_audio(
    draft_path: str,
    audio_folder: str,
    bg_video_path: str,
    cut_input_text: str,
    backup: bool = True,
    log_fn=None,
    padding_us: int = 500_000,
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

    # Padding trước/sau audio (cấu hình từ UI; 0 = không đệm, narration sát điểm cắt)
    PADDING_BEFORE = max(0, int(padding_us))
    PADDING_AFTER = max(0, int(padding_us))

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
    Parse input dạng mỗi mục 1 dòng, HOẶC nhiều mục cách nhau bằng dấu phẩy
    trên cùng 1 dòng (trộn lẫn cả hai cũng được):
        5 - 6
        20
        468 - 469
    hoặc:
        5-6, 20, 468-469
    Returns: sorted list of unique sub indices [5, 6, 20, 468, 469]
    """
    result = set()
    for chunk in text.replace(",", "\n").splitlines():
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            parts = chunk.split("-", 1)
            try:
                start = int(parts[0].strip())
                end = int(parts[1].strip())
                for i in range(start, end + 1):
                    result.add(i)
            except ValueError:
                continue
        else:
            try:
                result.add(int(chunk))
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

    # Bỏ index ngoài phạm vi thay vì abort. Gõ lố ở cuối dải (vd 584-592 khi chỉ
    # có 591 sub) là chuyện thường; bỏ số thừa cho đúng ý "xoá tới hết" mà vẫn
    # KHÔNG bao giờ xoá nhầm sub không được yêu cầu (kẹp về sub cuối thì có).
    bad = [i for i in indices if i < 1 or i > len(en_subs)]
    if bad:
        indices = [i for i in indices if 1 <= i <= len(en_subs)]
        _log(f"  ⚠ BỎ QUA {len(bad)} sub ngoài phạm vi (1-{len(en_subs)}): "
             f"{', '.join(map(str, bad[:10]))}{'...' if len(bad) > 10 else ''}")
    if not indices:
        _log(f"  ERROR: không còn sub hợp lệ nào (project có {len(en_subs)} sub)")
        return SyncSubResult(
            False, f"Không có sub nào hợp lệ — project chỉ có {len(en_subs)} sub")

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


# ── BDC: Change Video ────────────────────────────────────────────────
# Xoá track sub + track ảnh, thay narration mp3 + video nền chạy trên nó
# bằng video dựng sẵn trong 'video-narration/' (mỗi scene = 1 file
# '{cue}-narration.mp4', phủ đúng các audio liệt kê trong '{cue}-state.json').

def _mat_type_map(data: dict) -> dict:
    return {m["id"]: m.get("type", "video")
            for m in data.get("materials", {}).get("videos", [])}


def _find_picture_video_tracks(data: dict) -> list[dict]:
    """Video track chỉ chứa ảnh (track 'ảnh' — law picture overlay).

    Nhận diện: mọi segment trong track đều trỏ tới material type='photo'.
    """
    mat_types = _mat_type_map(data)
    result = []
    for t in data.get("tracks", []):
        if t.get("type") != "video":
            continue
        segs = t.get("segments", [])
        if not segs:
            continue
        if all(mat_types.get(s.get("material_id"), "video") == "photo" for s in segs):
            result.append(t)
    return result


def _find_content_video_tracks(data: dict) -> list[dict]:
    """Video track nội dung chính (không phải track ảnh)."""
    picture_ids = {t["id"] for t in _find_picture_video_tracks(data)}
    return [t for t in data.get("tracks", [])
            if t.get("type") == "video" and t.get("id") not in picture_ids]


def scan_narration_scenes(narration_folder: str) -> tuple[list[dict], list[str]]:
    """Đọc các file '*-state.json' trong video-narration/, trả về danh sách scene.

    Mỗi scene: {"cue": str, "nums": [int,...], "mp4_path": str}.
    'nums' là các audio number (khớp N.mp3 trong narration/) mà file
    '{cue}-narration.mp4' đã dựng sẵn để thay thế.
    """
    warns = []
    scenes = []
    if not narration_folder or not os.path.isdir(narration_folder):
        return scenes, ["Không tìm thấy folder video-narration"]

    for f in sorted(os.listdir(narration_folder), key=_natural_sort_key):
        if not f.endswith("-state.json"):
            continue
        cue = f[:-len("-state.json")]
        state_path = os.path.join(narration_folder, f)
        try:
            with open(state_path, "r", encoding="utf-8") as fh:
                state = json.load(fh)
        except Exception as e:
            warns.append(f"{f}: không đọc được ({e})")
            continue

        nums = []
        for it in state.get("items", []):
            try:
                nums.append(int(it["num"]))
            except (KeyError, ValueError, TypeError):
                continue
        if not nums:
            warns.append(f"{f}: không có 'items[].num' hợp lệ")
            continue

        mp4_path = os.path.join(narration_folder, f"{cue}-narration.mp4")
        if not os.path.isfile(mp4_path):
            warns.append(f"{cue}: thiếu file {cue}-narration.mp4")
            continue

        scenes.append({"cue": cue, "nums": sorted(set(nums)), "mp4_path": mp4_path})

    return scenes, warns


def preflight_change_video(draft_path: str, narration_folder: str) -> list[str]:
    """Kiểm tra input trước khi ghi. Chỉ chặn lỗi cấu trúc; thiếu 1 vài audio
    (vd đã bị xoá SRT trước đó) không chặn — engine tự bỏ qua khi chạy thật.
    """
    errs = []

    json_path = os.path.join(draft_path, "draft_content.json")
    if not os.path.isfile(json_path):
        return ["draft_content.json không tồn tại"]

    scenes, warns = scan_narration_scenes(narration_folder)
    errs.extend(warns)
    if not scenes:
        errs.append("video-narration/: không tìm thấy scene hợp lệ nào "
                     "(*-state.json + *-narration.mp4)")
        return errs

    try:
        data = capcut.load_draft_content(draft_path)
    except Exception as e:
        return errs + [f"Không đọc được draft: {e}"]

    content_tracks = _find_content_video_tracks(data)
    if len(content_tracks) == 0:
        errs.append("Không tìm thấy video track chính")
    elif len(content_tracks) > 1:
        errs.append(f"Có {len(content_tracks)} video track chính (chỉ hỗ trợ 1) — "
                     f"kiểm tra lại project")

    audio_track = capcut.find_audio_track(data)
    if not audio_track or not audio_track.get("segments"):
        errs.append("Không tìm thấy audio track narration (project đã Change Video rồi?)")

    return errs


def change_video(
    draft_path: str,
    narration_folder: str,
    backup: bool = True,
    log_fn=None,
) -> SyncSubResult:
    """
    Change Video (BDC) — 2 bước:
      1. Xoá track sub (text) + track ảnh (video track toàn ảnh law).
      2. Thay narration mp3 + video nền chạy trên nó bằng video dựng sẵn
         trong video-narration/, theo timing (delta duration → shift phần
         sau) chứ không giả định khớp tuyệt đối.
    """
    _log = log_fn or (lambda msg: None)

    json_path = os.path.join(draft_path, "draft_content.json")
    if not os.path.isfile(json_path):
        return SyncSubResult(False, "draft_content.json not found")

    scenes, warns = scan_narration_scenes(narration_folder)
    for w in warns:
        _log(f"  ⚠ {w}")
    if not scenes:
        return SyncSubResult(False, "Không tìm thấy scene nào trong video-narration/")

    if backup:
        bak_path = json_path + ".bak"
        if not os.path.isfile(bak_path):
            shutil.copy2(json_path, bak_path)
            _log("  backup created")
        else:
            _log("  backup exists, skipping")

    data = capcut.load_draft_content(draft_path)

    # ── Bước 1: xoá track sub (text) + track ảnh (video toàn ảnh) ──
    n_text_tracks = sum(1 for t in data["tracks"] if t.get("type") == "text")
    picture_tracks = _find_picture_video_tracks(data)
    picture_ids = {t["id"] for t in picture_tracks}
    n_pic_segs = sum(len(t.get("segments", [])) for t in picture_tracks)

    data["tracks"] = [t for t in data["tracks"]
                       if t.get("type") != "text" and t.get("id") not in picture_ids]
    _log(f"  [1/2] Đã xoá {n_text_tracks} track sub, {len(picture_tracks)} track ảnh "
         f"({n_pic_segs} ảnh)")

    content_tracks = _find_content_video_tracks(data)
    if len(content_tracks) != 1:
        return SyncSubResult(
            False, f"Cần đúng 1 video track chính, tìm thấy {len(content_tracks)}")
    content_track = content_tracks[0]

    audio_track = capcut.find_audio_track(data)
    if not audio_track or not audio_track.get("segments"):
        return SyncSubResult(False, "Không tìm thấy audio track narration")

    # Build audio number → segment map (giống insert_picture_law)
    audio_map = {}
    amats = {m["id"]: m for m in data.get("materials", {}).get("audios", [])}
    for seg in audio_track["segments"]:
        m = amats.get(seg.get("material_id"))
        if not m:
            continue
        stem = os.path.splitext(os.path.basename(m.get("path", "")))[0]
        try:
            audio_map[int(stem)] = seg
        except ValueError:
            pass

    # ── Bước 2a: xác định vùng thay thế cho từng scene ──
    regions = []
    for sc in scenes:
        found_segs = [audio_map[n] for n in sc["nums"] if n in audio_map]
        missing = [n for n in sc["nums"] if n not in audio_map]
        if missing:
            _log(f"  ⚠ scene {sc['cue']}: thiếu audio {missing} trong project (đã bị xoá?)")
        if not found_segs:
            _log(f"  ⚠ scene {sc['cue']}: bỏ qua — không còn audio nào trong project")
            continue

        region_start = min(s["target_timerange"]["start"] for s in found_segs)
        region_end = max(s["target_timerange"]["start"] + s["target_timerange"]["duration"]
                          for s in found_segs)
        old_dur = region_end - region_start

        info = _get_media_info(sc["mp4_path"])
        new_dur = info["duration"]
        if new_dur <= 0:
            _log(f"  ⚠ scene {sc['cue']}: không đọc được duration video, bỏ qua")
            continue

        regions.append({
            "cue": sc["cue"], "start": region_start, "end": region_end,
            "delta": new_dur - old_dur, "mp4_path": sc["mp4_path"], "new_dur": new_dur,
            "used_seg_ids": {id(s) for s in found_segs},
        })
        _log(f"  scene {sc['cue']}: {region_start/1e6:.2f}s-{region_end/1e6:.2f}s "
             f"({old_dur/1e6:.2f}s) → {new_dur/1e6:.2f}s (Δ{(new_dur-old_dur)/1e6:+.2f}s)")

    if not regions:
        return SyncSubResult(False, "Không có scene nào áp dụng được")

    regions.sort(key=lambda r: r["start"])

    def calc_offset(t):
        return sum(r["delta"] for r in regions if r["end"] <= t)

    # ── Bước 2b: rebuild video track chính — bỏ đoạn trong vùng, chèn video mới ──
    new_segs = []
    for seg in content_track["segments"]:
        t_start = seg["target_timerange"]["start"]
        t_end = t_start + seg["target_timerange"]["duration"]
        in_region = any(r["start"] <= t_start and t_end <= r["end"] for r in regions)
        if in_region:
            continue
        seg["target_timerange"]["start"] = t_start + calc_offset(t_start)
        new_segs.append(seg)

    for r in regions:
        offset = calc_offset(r["start"])
        info = _get_media_info(r["mp4_path"])
        v_mat = _make_video_material(r["mp4_path"], info)
        data["materials"].setdefault("videos", []).append(v_mat)
        sp_mat = _make_speed_material()
        cv_mat = _make_canvas_material()
        snd_mat = _make_sound_channel()
        data["materials"].setdefault("speeds", []).append(sp_mat)
        data["materials"].setdefault("canvases", []).append(cv_mat)
        data["materials"].setdefault("sound_channel_mappings", []).append(snd_mat)

        new_seg = _make_video_segment(
            material_id=v_mat["id"], start=r["start"] + offset, duration=r["new_dur"],
            speed_id=sp_mat["id"], canvas_id=cv_mat["id"], sound_id=snd_mat["id"],
        )
        new_segs.append(new_seg)

    content_track["segments"] = sorted(new_segs, key=lambda s: s["target_timerange"]["start"])

    # ── Bước 2c: audio track — bỏ segment đã dùng, shift phần còn lại ──
    used_ids = set()
    for r in regions:
        used_ids |= r["used_seg_ids"]

    remaining_audio = []
    for seg in audio_track["segments"]:
        if id(seg) in used_ids:
            continue
        t_start = seg["target_timerange"]["start"]
        seg["target_timerange"]["start"] = t_start + calc_offset(t_start)
        remaining_audio.append(seg)

    if remaining_audio:
        audio_track["segments"] = sorted(
            remaining_audio, key=lambda s: s["target_timerange"]["start"])
        _log(f"  [2/2] Đã thay {len(regions)} scene, còn {len(remaining_audio)} "
             f"audio chưa thay (giữ track audio)")
    else:
        data["tracks"] = [t for t in data["tracks"] if t.get("id") != audio_track["id"]]
        _log(f"  [2/2] Đã thay {len(regions)} scene, xoá hết track audio narration")

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
        f"Change Video: đã thay {len(regions)}/{len(scenes)} scene, "
        f"xoá {n_text_tracks} track sub + {len(picture_tracks)} track ảnh",
        sub_count=len(regions),
    )


# ── Chèn Outro ────────────────────────────────────────────────────────
# Chèn video outro vào CUỐI video track chính của từng project, khớp theo
# tên: 'bodycam-video004' → 'outro-video004.mp4' trong thư mục outro.

_OUTRO_VIDEO_EXTS = (".mp4", ".mov", ".avi", ".mkv")


def resolve_outro_path(outro_folder: str, draft_name: str) -> str | None:
    """Tìm file outro tương ứng 1 project theo tên.

    Quy tắc chính: đổi tiền tố 'bodycam-' → 'outro-'
        'bodycam-video004' → 'outro-video004.mp4'
    Fallback: khớp theo số cuối tên project với file 'outro...<số>.<ext>'
    (phòng khi tên project không có tiền tố 'bodycam-').
    """
    if not outro_folder or not os.path.isdir(outro_folder):
        return None

    if draft_name.startswith("bodycam-"):
        stem = "outro-" + draft_name[len("bodycam-"):]
        for ext in _OUTRO_VIDEO_EXTS:
            p = os.path.join(outro_folder, stem + ext)
            if os.path.isfile(p):
                return p

    m = re.search(r"(\d+)$", draft_name)
    if m:
        num = m.group(1)
        for f in sorted(os.listdir(outro_folder), key=_natural_sort_key):
            fstem, ext = os.path.splitext(f)
            if (ext.lower() in _OUTRO_VIDEO_EXTS and "outro" in fstem.lower()
                    and fstem.lower().endswith(num)):
                return os.path.join(outro_folder, f)

    return None


def preflight_insert_outro(draft_path: str, outro_path: str) -> list[str]:
    """Kiểm tra input trước khi ghi."""
    errs = []

    json_path = os.path.join(draft_path, "draft_content.json")
    if not os.path.isfile(json_path):
        return ["draft_content.json không tồn tại"]

    if not outro_path or not os.path.isfile(outro_path):
        return ["Không tìm thấy file outro tương ứng"]

    try:
        data = capcut.load_draft_content(draft_path)
    except Exception as e:
        return [f"Không đọc được draft: {e}"]

    content_tracks = _find_content_video_tracks(data)
    if len(content_tracks) == 0:
        errs.append("Không tìm thấy video track chính")
    elif len(content_tracks) > 1:
        errs.append(f"Có {len(content_tracks)} video track chính (chỉ hỗ trợ 1) — "
                     f"kiểm tra lại project")

    return errs


def insert_outro(
    draft_path: str,
    outro_path: str,
    backup: bool = True,
    log_fn=None,
) -> SyncSubResult:
    """Chèn video outro vào cuối video track chính (sau điểm kết thúc muộn
    nhất của toàn bộ timeline), không đụng tới các segment/track hiện có."""
    _log = log_fn or (lambda msg: None)

    json_path = os.path.join(draft_path, "draft_content.json")
    if not os.path.isfile(json_path):
        return SyncSubResult(False, "draft_content.json not found")
    if not outro_path or not os.path.isfile(outro_path):
        return SyncSubResult(False, "Outro video not found")

    if backup:
        bak_path = json_path + ".bak"
        if not os.path.isfile(bak_path):
            shutil.copy2(json_path, bak_path)
            _log("  backup created")
        else:
            _log("  backup exists, skipping")

    data = capcut.load_draft_content(draft_path)

    content_tracks = _find_content_video_tracks(data)
    if len(content_tracks) != 1:
        return SyncSubResult(
            False, f"Cần đúng 1 video track chính, tìm thấy {len(content_tracks)}")
    content_track = content_tracks[0]

    all_ends = [0]
    for t in data.get("tracks", []):
        for seg in t.get("segments", []):
            end = seg["target_timerange"]["start"] + seg["target_timerange"]["duration"]
            all_ends.append(end)
    insert_at = max(all_ends)

    info = _get_media_info(outro_path)
    dur = info["duration"]
    if dur <= 0:
        return SyncSubResult(False, "Không đọc được duration outro")

    v_mat = _make_video_material(outro_path, info)
    data["materials"].setdefault("videos", []).append(v_mat)
    sp_mat = _make_speed_material()
    cv_mat = _make_canvas_material()
    snd_mat = _make_sound_channel()
    data["materials"].setdefault("speeds", []).append(sp_mat)
    data["materials"].setdefault("canvases", []).append(cv_mat)
    data["materials"].setdefault("sound_channel_mappings", []).append(snd_mat)

    seg = _make_video_segment(
        material_id=v_mat["id"], start=insert_at, duration=dur,
        speed_id=sp_mat["id"], canvas_id=cv_mat["id"], sound_id=snd_mat["id"],
    )
    content_track["segments"].append(seg)
    content_track["segments"].sort(key=lambda s: s["target_timerange"]["start"])

    data["duration"] = insert_at + dur

    _log(f"  chèn outro tại {insert_at/1e6:.2f}s, dài {dur/1e6:.2f}s "
         f"({os.path.basename(outro_path)})")
    capcut.save_draft_content(draft_path, data)
    _log("  saved OK")

    return SyncSubResult(
        True,
        f"Đã chèn outro ({dur/1e6:.1f}s) vào cuối video",
        sub_count=1,
    )


# ── Chèn Intro ────────────────────────────────────────────────────────
# Chèn video intro vào ĐẦU video track chính của từng project, khớp theo
# tên: 'bodycam-video004' → 'intro-video004.mp4' trong thư mục intro.

def resolve_intro_path(intro_folder: str, draft_name: str) -> str | None:
    """Tìm file intro tương ứng 1 project theo tên.

    Quy tắc chính: đổi tiền tố 'bodycam-' → 'intro-'
        'bodycam-video004' → 'intro-video004.mp4'
    Tìm trong chính thư mục intro, và trong '_render/' bên trong nó (nếu có) —
    một số bộ intro có file final nằm trong '_render/' thay vì ở gốc.
    Fallback: khớp theo số cuối tên project với file 'intro...<số>.<ext>'.
    """
    if not intro_folder or not os.path.isdir(intro_folder):
        return None

    search_dirs = [intro_folder]
    render_dir = os.path.join(intro_folder, "_render")
    if os.path.isdir(render_dir):
        search_dirs.append(render_dir)

    if draft_name.startswith("bodycam-"):
        stem = "intro-" + draft_name[len("bodycam-"):]
        for d in search_dirs:
            for ext in _OUTRO_VIDEO_EXTS:
                p = os.path.join(d, stem + ext)
                if os.path.isfile(p):
                    return p

    m = re.search(r"(\d+)$", draft_name)
    if m:
        num = m.group(1)
        for d in search_dirs:
            for f in sorted(os.listdir(d), key=_natural_sort_key):
                fstem, ext = os.path.splitext(f)
                if (ext.lower() in _OUTRO_VIDEO_EXTS and "intro" in fstem.lower()
                        and fstem.lower().endswith(num)):
                    return os.path.join(d, f)

    return None


def preflight_insert_intro(draft_path: str, intro_path: str) -> list[str]:
    """Kiểm tra input trước khi ghi."""
    errs = []

    json_path = os.path.join(draft_path, "draft_content.json")
    if not os.path.isfile(json_path):
        return ["draft_content.json không tồn tại"]

    if not intro_path or not os.path.isfile(intro_path):
        return ["Không tìm thấy file intro tương ứng"]

    try:
        data = capcut.load_draft_content(draft_path)
    except Exception as e:
        return [f"Không đọc được draft: {e}"]

    content_tracks = _find_content_video_tracks(data)
    if len(content_tracks) == 0:
        errs.append("Không tìm thấy video track chính")
    elif len(content_tracks) > 1:
        errs.append(f"Có {len(content_tracks)} video track chính (chỉ hỗ trợ 1) — "
                     f"kiểm tra lại project")

    return errs


def insert_intro(
    draft_path: str,
    intro_path: str,
    backup: bool = True,
    log_fn=None,
) -> SyncSubResult:
    """Chèn video intro vào ĐẦU video track chính, dịch toàn bộ timeline hiện
    có (mọi track: video, text, audio, effect...) về sau đúng bằng duration
    của intro."""
    _log = log_fn or (lambda msg: None)

    json_path = os.path.join(draft_path, "draft_content.json")
    if not os.path.isfile(json_path):
        return SyncSubResult(False, "draft_content.json not found")
    if not intro_path or not os.path.isfile(intro_path):
        return SyncSubResult(False, "Intro video not found")

    if backup:
        bak_path = json_path + ".bak"
        if not os.path.isfile(bak_path):
            shutil.copy2(json_path, bak_path)
            _log("  backup created")
        else:
            _log("  backup exists, skipping")

    data = capcut.load_draft_content(draft_path)

    content_tracks = _find_content_video_tracks(data)
    if len(content_tracks) != 1:
        return SyncSubResult(
            False, f"Cần đúng 1 video track chính, tìm thấy {len(content_tracks)}")
    content_track = content_tracks[0]

    info = _get_media_info(intro_path)
    dur = info["duration"]
    if dur <= 0:
        return SyncSubResult(False, "Không đọc được duration intro")

    # Dịch mọi segment ở mọi track về sau đúng bằng duration intro
    for t in data.get("tracks", []):
        for seg in t.get("segments", []):
            seg["target_timerange"]["start"] += dur

    v_mat = _make_video_material(intro_path, info)
    data["materials"].setdefault("videos", []).append(v_mat)
    sp_mat = _make_speed_material()
    cv_mat = _make_canvas_material()
    snd_mat = _make_sound_channel()
    data["materials"].setdefault("speeds", []).append(sp_mat)
    data["materials"].setdefault("canvases", []).append(cv_mat)
    data["materials"].setdefault("sound_channel_mappings", []).append(snd_mat)

    seg = _make_video_segment(
        material_id=v_mat["id"], start=0, duration=dur,
        speed_id=sp_mat["id"], canvas_id=cv_mat["id"], sound_id=snd_mat["id"],
    )
    content_track["segments"].append(seg)
    content_track["segments"].sort(key=lambda s: s["target_timerange"]["start"])

    all_ends = []
    for t in data["tracks"]:
        for s in t.get("segments", []):
            end = s["target_timerange"]["start"] + s["target_timerange"]["duration"]
            all_ends.append(end)
    if all_ends:
        data["duration"] = max(all_ends)

    _log(f"  chèn intro tại 0.00s, dài {dur/1e6:.2f}s, dịch toàn bộ timeline "
         f"+{dur/1e6:.2f}s ({os.path.basename(intro_path)})")
    capcut.save_draft_content(draft_path, data)
    _log("  saved OK")

    return SyncSubResult(
        True,
        f"Đã chèn intro ({dur/1e6:.1f}s) vào đầu video, dịch timeline +{dur/1e6:.1f}s",
        sub_count=1,
    )


# ── Clear Sub + Blur trên video narration / outro / intro ─────────────

_NARRATION_NAME_RE = re.compile(r"^\d+-narration\.[^.]+$", re.IGNORECASE)
_SUB_OVERLAP_DELETE_RATIO = 0.5

# Blur hiển thị tên theo ngôn ngữ CapCut đang dùng (vd 'Blur', 'Mờ'...) nên
# so khớp tên không đáng tin — nhận theo resource_id cố định của effect catalog
# (không đổi theo locale).
_BLUR_EFFECT_RESOURCE_IDS = {"7399464929830423813"}


def _is_narration_or_outro(filename: str) -> bool:
    low = filename.lower()
    return (bool(_NARRATION_NAME_RE.match(low))
            or low.startswith("outro") or low.startswith("intro"))


def _merge_ranges(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged = []
    for s, e in sorted(ranges):
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged


def find_narration_outro_ranges(data: dict) -> list[tuple[int, int]]:
    """Khoảng thời gian (µs) của các segment video tên '<số>-narration.*',
    'outro*' và 'intro*'."""
    vmats = {m["id"]: m for m in data.get("materials", {}).get("videos", [])}
    ranges = []
    for t in data.get("tracks", []):
        if t.get("type") != "video":
            continue
        for seg in t.get("segments", []):
            fname = os.path.basename(vmats.get(seg.get("material_id"), {}).get("path", ""))
            if fname and _is_narration_or_outro(fname):
                s = seg["target_timerange"]["start"]
                ranges.append((s, s + seg["target_timerange"]["duration"]))
    return _merge_ranges(ranges)


def _overlap(a_start: int, a_end: int, ranges: list[tuple[int, int]]) -> int:
    return sum(max(0, min(a_end, re) - max(a_start, rs)) for rs, re in ranges)


def _subtract_ranges(start: int, end: int,
                     ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Phần của [start, end] KHÔNG nằm trong ranges."""
    pieces = []
    cursor = start
    for rs, re in ranges:
        if re <= cursor or rs >= end:
            continue
        if rs > cursor:
            pieces.append((cursor, rs))
        cursor = max(cursor, re)
    if cursor < end:
        pieces.append((cursor, end))
    return pieces


def _clone_effect_material(mat: dict) -> dict:
    new_mat = copy.deepcopy(mat)
    new_mat["id"] = _uid()
    for mask in new_mat.get("effect_mask") or []:
        if "id" in mask:
            mask["id"] = _uid()
        if mask.get("constant_material_id"):
            mask["constant_material_id"] = _uid()
    return new_mat


def preflight_clear_sub_blur(draft_path: str) -> list[str]:
    json_path = os.path.join(draft_path, "draft_content.json")
    if not os.path.isfile(json_path):
        return ["draft_content.json không tồn tại"]
    try:
        data = capcut.load_draft_content(draft_path)
    except Exception as e:
        return [f"Không đọc được draft: {e}"]
    if not find_narration_outro_ranges(data):
        return ["Không tìm thấy video '<số>-narration', 'outro' hoặc 'intro' nào trên timeline"]
    return []


def clear_sub_blur(
    draft_path: str,
    backup: bool = True,
    log_fn=None,
) -> SyncSubResult:
    """Xoá sub + cắt blur trên các đoạn video '<số>-narration', 'outro' và 'intro'.

    - Sub (text): xoá segment có ≥50% thời lượng nằm trong các đoạn đó.
    - Blur (effect Blur, nhận theo resource_id — tên hiển thị đổi theo locale
      CapCut nên không so khớp theo tên): chia segment, bỏ phần trùng các đoạn
      đó, mỗi đoạn còn lại có material riêng (nhân bản).
    Project chỉ có sub / chỉ có blur / cả hai đều xử lý phần có; không có gì
    để làm thì không ghi file.
    """
    _log = log_fn or (lambda msg: None)

    json_path = os.path.join(draft_path, "draft_content.json")
    if not os.path.isfile(json_path):
        return SyncSubResult(False, "draft_content.json not found")

    data = capcut.load_draft_content(draft_path)
    ranges = find_narration_outro_ranges(data)
    if not ranges:
        return SyncSubResult(
            False, "Không tìm thấy video '<số>-narration' hoặc 'outro' trên timeline")
    _log(f"  {len(ranges)} đoạn narration/outro: "
         + ", ".join(f"{s/1e6:.1f}-{e/1e6:.1f}s" for s, e in ranges))

    # ── Sub ──
    subs_removed = 0
    n_text_segs = 0
    for t in data["tracks"]:
        if t.get("type") != "text":
            continue
        kept = []
        for seg in t["segments"]:
            n_text_segs += 1
            s = seg["target_timerange"]["start"]
            dur = seg["target_timerange"]["duration"]
            if dur > 0 and _overlap(s, s + dur, ranges) / dur >= _SUB_OVERLAP_DELETE_RATIO:
                subs_removed += 1
            else:
                kept.append(seg)
        t["segments"] = kept
    if n_text_segs == 0:
        _log("  sub: project không có sub")
    else:
        _log(f"  sub: xoá {subs_removed}/{n_text_segs}")

    # ── Blur ──
    fx_mats = data.get("materials", {}).get("video_effects", [])
    fx_by_id = {m["id"]: m for m in fx_mats}
    blur_cut = 0
    blur_found = 0
    emptied_tracks = set()
    for t in data["tracks"]:
        if t.get("type") != "effect":
            continue
        new_segs = []
        for seg in t["segments"]:
            mat = fx_by_id.get(seg.get("material_id"))
            if not mat or not _is_blur_material(mat):
                new_segs.append(seg)
                continue
            blur_found += 1
            s = seg["target_timerange"]["start"]
            e = s + seg["target_timerange"]["duration"]
            pieces = _subtract_ranges(s, e, ranges)
            if pieces == [(s, e)]:
                new_segs.append(seg)
                continue
            blur_cut += 1
            for i, (ps, pe) in enumerate(pieces):
                if i == 0:
                    piece = seg
                    piece_mat = mat
                else:
                    piece = copy.deepcopy(seg)
                    piece["id"] = _uid()
                    piece_mat = _clone_effect_material(mat)
                    piece["material_id"] = piece_mat["id"]
                    fx_mats.append(piece_mat)
                piece["target_timerange"] = {"start": ps, "duration": pe - ps}
                new_segs.append(piece)
        t["segments"] = sorted(new_segs, key=lambda x: x["target_timerange"]["start"])
        if not t["segments"]:
            emptied_tracks.add(t["id"])
    if emptied_tracks:
        data["tracks"] = [t for t in data["tracks"] if t.get("id") not in emptied_tracks]
    if blur_found == 0:
        _log("  blur: project không có blur")
    else:
        _log(f"  blur: cắt {blur_cut}/{blur_found} segment blur")

    if subs_removed == 0 and blur_cut == 0:
        return SyncSubResult(True, "Không có sub/blur nào cần xử lý — bỏ qua, không ghi file")

    if backup:
        bak_path = json_path + ".bak"
        if not os.path.isfile(bak_path):
            shutil.copy2(json_path, bak_path)
            _log("  backup created")
        else:
            _log("  backup exists, skipping")

    capcut.save_draft_content(draft_path, data)
    _log("  saved OK")

    return SyncSubResult(
        True,
        f"Đã xoá {subs_removed} sub, cắt {blur_cut} segment blur",
        sub_count=subs_removed,
    )


# ── Effect narration ──────────────────────────────────────────────────
# Lấy các effect mẫu (không tính Blur) từ project nguồn đã nằm trên narration,
# rồi random 1 effect cho mỗi đoạn narration của project đích.

EFFECT_SOURCE_PROJECT = "effect narration"


def _is_effect_target_name(fname: str) -> bool:
    low = fname.lower()
    return bool(_NARRATION_NAME_RE.match(low)) or low.startswith("intro")


def _narration_video_ranges(data: dict) -> list[tuple[int, int]]:
    vmats = {m["id"]: m for m in data.get("materials", {}).get("videos", [])}
    ranges = []
    for t in data.get("tracks", []):
        if t.get("type") != "video":
            continue
        for seg in t.get("segments", []):
            fname = os.path.basename(vmats.get(seg.get("material_id"), {}).get("path", ""))
            if _is_effect_target_name(fname):
                s = seg["target_timerange"]["start"]
                ranges.append((s, s + seg["target_timerange"]["duration"]))
    return ranges


def _is_blur_material(mat: dict) -> bool:
    rid = mat.get("resource_id") or mat.get("effect_id") or ""
    if str(rid) in _BLUR_EFFECT_RESOURCE_IDS:
        return True
    return "blur" in str(mat.get("name", "")).lower()


def load_narration_effect_pool(source_draft_path: str) -> list[tuple[dict, dict]]:
    """(material, segment) mẫu, mỗi effect khác nhau 1 lần, lấy từ track effect
    của project nguồn (bỏ Blur)."""
    data = capcut.load_draft_content(source_draft_path)
    fx_by_id = {m["id"]: m for m in data.get("materials", {}).get("video_effects", [])}

    pool = {}
    for t in data.get("tracks", []):
        if t.get("type") != "effect":
            continue
        for seg in t.get("segments", []):
            mat = fx_by_id.get(seg.get("material_id"))
            if not mat or _is_blur_material(mat):
                continue
            key = mat.get("resource_id") or mat.get("effect_id") or mat.get("name")
            pool.setdefault(key, (copy.deepcopy(mat), copy.deepcopy(seg)))
    return list(pool.values())


def preflight_narration_effect(draft_path: str, pool: list) -> list[str]:
    json_path = os.path.join(draft_path, "draft_content.json")
    if not os.path.isfile(json_path):
        return ["draft_content.json không tồn tại"]
    if not pool:
        return ["Không lấy được effect mẫu từ project nguồn"]
    try:
        data = capcut.load_draft_content(draft_path)
    except Exception as e:
        return [f"Không đọc được draft: {e}"]
    if not _narration_video_ranges(data):
        return ["Không tìm thấy video '<số>-narration' hoặc 'intro' trên timeline"]
    return []


def apply_narration_effect(
    draft_path: str,
    pool: list,
    backup: bool = True,
    log_fn=None,
) -> SyncSubResult:
    """Với mỗi đoạn '<số>-narration' và 'intro' của project: xoá effect (không phải Blur)
    đang đè lên đoạn đó, rồi chèn 1 effect random từ pool đúng khoảng thời gian
    của đoạn narration. Blur và các thứ khác giữ nguyên."""
    _log = log_fn or (lambda msg: None)

    json_path = os.path.join(draft_path, "draft_content.json")
    if not os.path.isfile(json_path):
        return SyncSubResult(False, "draft_content.json not found")

    data = capcut.load_draft_content(draft_path)
    vmats = {m["id"]: m for m in data.get("materials", {}).get("videos", [])}
    narr_segs = []
    for t in data.get("tracks", []):
        if t.get("type") != "video":
            continue
        for seg in t.get("segments", []):
            fname = os.path.basename(vmats.get(seg.get("material_id"), {}).get("path", ""))
            if _is_effect_target_name(fname):
                narr_segs.append(seg)
    if not narr_segs:
        return SyncSubResult(False, "Không tìm thấy video '<số>-narration' hoặc 'intro' trên timeline")

    narr_ranges = [(s["target_timerange"]["start"],
                    s["target_timerange"]["start"] + s["target_timerange"]["duration"])
                   for s in narr_segs]

    fx_by_id = {m["id"]: m for m in data.get("materials", {}).get("video_effects", [])}
    removed = 0
    for t in data["tracks"]:
        if t.get("type") != "effect":
            continue
        kept = []
        for seg in t["segments"]:
            mat = fx_by_id.get(seg.get("material_id"))
            s = seg["target_timerange"]["start"]
            e = s + seg["target_timerange"]["duration"]
            if mat and not _is_blur_material(mat) and _overlap(s, e, narr_ranges) > 0:
                removed += 1
                continue
            kept.append(seg)
        t["segments"] = kept

    eff_track = next((t for t in data["tracks"] if t.get("type") == "effect"), None)
    if eff_track is None:
        eff_track = {
            "id": _uid(), "type": "effect", "segments": [],
            "flag": 0, "attribute": 0, "name": "", "is_default_name": True,
        }
        insert_idx = next((i + 1 for i, t in enumerate(data["tracks"])
                           if t.get("type") == "video"), len(data["tracks"]))
        data["tracks"].insert(insert_idx, eff_track)

    added = 0
    picked = []
    for seg in narr_segs:
        mat_tpl, seg_tpl = random.choice(pool)
        new_mat = copy.deepcopy(mat_tpl)
        new_mat["id"] = _uid()
        new_seg = copy.deepcopy(seg_tpl)
        new_seg["id"] = _uid()
        new_seg["material_id"] = new_mat["id"]
        new_seg["target_timerange"] = {
            "start": seg["target_timerange"]["start"],
            "duration": seg["target_timerange"]["duration"],
        }
        new_mat["bind_segment_id"] = new_seg["id"]
        data["materials"].setdefault("video_effects", []).append(new_mat)
        eff_track["segments"].append(new_seg)
        picked.append(new_mat.get("name", "?"))
        added += 1

    eff_track["segments"].sort(key=lambda s: s["target_timerange"]["start"])

    if backup:
        bak_path = json_path + ".bak"
        if not os.path.isfile(bak_path):
            shutil.copy2(json_path, bak_path)
            _log("  backup created")
        else:
            _log("  backup exists, skipping")

    capcut.save_draft_content(draft_path, data)
    _log(f"  saved OK: xoá {removed} effect cũ trên narration, chèn {added} effect mới")

    return SyncSubResult(
        True,
        f"Effect narration: chèn {added} effect ({', '.join(sorted(set(picked)))})",
        sub_count=added,
    )
