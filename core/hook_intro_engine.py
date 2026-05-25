"""Hook + Intro engine — prepend hook clips và intro.mp3 vào đầu timeline.

Workflow:
1. snapshot_hook(draft, hook_stts) — TRƯỚC PROMAX: parse SRT, clone main video
   segments overlapping với hook timeline_ranges. Lưu lại các segment đã clone.
2. (PROMAX chạy bình thường, có thể xóa/thay đổi subs.)
3. prepend_hook_and_intro(draft, snapshot, intro_mp3) — SAU PROMAX: shift mọi
   segment hiện có sang phải +prepend_dur, đặt hook clones vào [0, hook_total],
   filler clips (volume=0) vào [hook_total, prepend_dur], intro.mp3 audio segment.
"""

import os
import copy
import uuid
import random
from dataclasses import dataclass, field

from core import capcut


def _uid() -> str:
    return str(uuid.uuid4()).upper()


def parse_hook_input(text: str) -> list[tuple[int, int]]:
    """Parse 4-hook.txt: mỗi dòng = 1 hook range.

    Vd:
        13-15
        35-38
        47-48
        30
    → [(13,15), (35,38), (47,48), (30,30)]
    """
    ranges: list[tuple[int, int]] = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        if "-" in line:
            parts = line.split("-", 1)
            try:
                a = int(parts[0].strip())
                b = int(parts[1].strip())
                if a > b:
                    a, b = b, a
                ranges.append((a, b))
            except ValueError:
                continue
        else:
            try:
                v = int(line)
                ranges.append((v, v))
            except ValueError:
                continue
    return ranges


def _find_main_video_track(data: dict) -> dict | None:
    """Tìm main video track: video track không phải image overlay (không toàn photo)."""
    photo_ids = {
        v["id"] for v in data.get("materials", {}).get("videos", [])
        if v.get("type") == "photo"
    }
    for t in data.get("tracks", []):
        if t.get("type") != "video":
            continue
        segs = t.get("segments", [])
        if not segs:
            continue
        # Image overlay = mọi seg đều ref photo material
        if photo_ids and all(s.get("material_id") in photo_ids for s in segs):
            continue
        return t
    return None


def _get_text_segments_sorted(data: dict) -> list[dict]:
    segs = []
    for t in data.get("tracks", []):
        if t.get("type") == "text":
            segs.extend(t.get("segments", []))
    segs.sort(key=lambda s: s["target_timerange"]["start"])
    return segs


def _clone_video_seg_to_range(seg: dict, range_start: int, range_end: int) -> dict | None:
    """Clone seg, trim overlap [range_start, range_end]. Return new seg with target_timerange
    matching the overlap (start = ov_start), source_timerange shifted accordingly."""
    ts = seg["target_timerange"]
    seg_start = ts["start"]
    seg_end = seg_start + ts["duration"]

    ov_start = max(seg_start, range_start)
    ov_end = min(seg_end, range_end)
    if ov_start >= ov_end:
        return None

    new_seg = copy.deepcopy(seg)
    new_seg["id"] = _uid()

    ov_dur = ov_end - ov_start
    new_seg["target_timerange"] = {"start": ov_start, "duration": ov_dur}

    # Shift source theo speed
    speed = seg.get("speed", 1.0) or 1.0
    ss = seg.get("source_timerange") or {"start": 0, "duration": ts["duration"]}
    src_offset = int((ov_start - seg_start) * speed)
    new_seg["source_timerange"] = {
        "start": ss["start"] + src_offset,
        "duration": int(ov_dur * speed),
    }
    return new_seg


@dataclass
class HookSnapshot:
    hook_ranges: list[tuple[int, int]] = field(default_factory=list)
    hook_video_segs: list[list[dict]] = field(default_factory=list)
    main_video_material_id: str = ""
    main_video_duration_us: int = 0
    extra_material_refs_template: list[str] = field(default_factory=list)


def snapshot_hook(draft_path: str, hook_ranges_stt: list[tuple[int, int]]) -> HookSnapshot:
    """Snapshot hook video segments TRƯỚC PROMAX.

    hook_ranges_stt: list of (start_stt, end_stt) inclusive, mỗi tuple là 1 hook
    continuous range trong SRT.
    """
    if not hook_ranges_stt:
        raise ValueError("hook_ranges rỗng")

    data = capcut.load_draft_content(draft_path)

    main_track = _find_main_video_track(data)
    if not main_track:
        raise RuntimeError("Không tìm thấy main video track")

    text_segs = _get_text_segments_sorted(data)
    if not text_segs:
        raise RuntimeError("Không có text/SRT trong project")

    snap = HookSnapshot()
    n_subs = len(text_segs)
    for (a, b) in hook_ranges_stt:
        if not (1 <= a <= n_subs):
            raise RuntimeError(f"Hook STT {a} ngoài range (1..{n_subs})")
        if not (1 <= b <= n_subs):
            raise RuntimeError(f"Hook STT {b} ngoài range (1..{n_subs})")
        sub_a = text_segs[a - 1]["target_timerange"]
        sub_b = text_segs[b - 1]["target_timerange"]
        start = sub_a["start"]
        end = sub_b["start"] + sub_b["duration"]
        snap.hook_ranges.append((start, end - start))

    snap.hook_ranges.sort(key=lambda r: r[0])

    main_segs_sorted = sorted(
        main_track["segments"], key=lambda s: s["target_timerange"]["start"]
    )

    for (rs, rd) in snap.hook_ranges:
        re = rs + rd
        cloned = []
        for seg in main_segs_sorted:
            c = _clone_video_seg_to_range(seg, rs, re)
            if c:
                cloned.append(c)
        if not cloned:
            raise RuntimeError(
                f"Hook range [{rs/1e6:.2f}s, {re/1e6:.2f}s] không match video segment nào"
            )
        snap.hook_video_segs.append(cloned)

    # Material info từ first segment để dùng cho filler clips
    first_seg = main_segs_sorted[0]
    snap.main_video_material_id = first_seg["material_id"]
    snap.extra_material_refs_template = list(first_seg.get("extra_material_refs", []))
    for v in data.get("materials", {}).get("videos", []):
        if v.get("id") == snap.main_video_material_id:
            snap.main_video_duration_us = v.get("duration", 0)
            break

    return snap


def _get_audio_duration_us(path: str) -> int:
    try:
        from mutagen.mp3 import MP3
        return int(MP3(path).info.length * 1_000_000)
    except Exception:
        pass
    try:
        from mutagen import File
        a = File(path)
        if a and a.info:
            return int(a.info.length * 1_000_000)
    except Exception:
        pass
    size = os.path.getsize(path)
    return int((size / (96 * 1024 / 8)) * 1_000_000)


def _make_audio_material(path: str, dur: int) -> dict:
    return {
        "id": _uid(),
        "unique_id": "",
        "type": "extract_music",
        "name": os.path.basename(path),
        "duration": dur,
        "path": path.replace("\\", "/"),
        "category_name": "local",
        "wave_points": [],
        "music_id": "", "app_id": 0, "text_id": "",
        "tone_type": "", "source_platform": 0,
        "video_id": "", "effect_id": "",
        "resource_id": "", "third_resource_id": "",
        "category_id": "", "intensifies_path": "",
        "formula_id": "", "check_flag": 1,
    }


def _make_audio_segment(material_id: str, start: int, dur: int, extras: list[str]) -> dict:
    return {
        "id": _uid(),
        "source_timerange": {"start": 0, "duration": dur},
        "target_timerange": {"start": start, "duration": dur},
        "render_timerange": {"start": 0, "duration": 0},
        "desc": "", "state": 0, "speed": 1.0,
        "is_loop": False, "is_tone_modify": False, "reverse": False,
        "intensifies_audio": False, "cartoon": False,
        "volume": 1.0, "last_nonzero_volume": 1.0,
        "clip": None, "uniform_scale": None,
        "material_id": material_id,
        "extra_material_refs": extras,
        "render_index": 0, "keyframe_refs": [],
        "enable_lut": False, "enable_adjust": False, "enable_hsl": False,
        "visible": True, "group_id": "",
        "enable_color_curves": True, "enable_hsl_curves": True,
        "track_render_index": 1,
        "hdr_settings": None, "enable_color_wheels": True,
        "track_attribute": 0, "is_placeholder": False,
        "template_id": "", "enable_smart_color_adjust": False,
        "template_scene": "default", "common_keyframes": [],
        "caption_info": None,
        "responsive_layout": {"enable": False, "target_follow": "",
                              "size_layout": 0, "horizontal_pos_layout": 0,
                              "vertical_pos_layout": 0},
    }


def _make_filler_video_segment(material_id: str, source_start: int, source_dur: int,
                                target_start: int, target_dur: int,
                                extras: list[str]) -> dict:
    return {
        "id": _uid(),
        "source_timerange": {"start": source_start, "duration": source_dur},
        "target_timerange": {"start": target_start, "duration": target_dur},
        "render_timerange": {"start": 0, "duration": 0},
        "desc": "", "state": 0, "speed": 1.0,
        "is_loop": False, "is_tone_modify": False, "reverse": False,
        "intensifies_audio": False, "cartoon": False,
        "volume": 0.0, "last_nonzero_volume": 0.0,
        "clip": {
            "scale": {"x": 1.0, "y": 1.0}, "rotation": 0.0,
            "transform": {"x": 0.0, "y": 0.0},
            "flip": {"vertical": False, "horizontal": False}, "alpha": 1.0,
        },
        "uniform_scale": {"on": True, "value": 1.0},
        "material_id": material_id,
        "extra_material_refs": extras,
        "render_index": 0, "keyframe_refs": [],
        "enable_lut": True, "enable_adjust": True, "enable_hsl": False,
        "visible": True, "group_id": "",
        "enable_color_curves": True, "enable_hsl_curves": True,
        "track_render_index": 0,
        "hdr_settings": {"mode": 1, "intensity": 1.0, "nits": 1000},
        "enable_color_wheels": True, "track_attribute": 0,
        "is_placeholder": False, "template_id": "",
        "enable_smart_color_adjust": False, "template_scene": "default",
        "common_keyframes": [], "caption_info": None,
        "responsive_layout": {"enable": False, "target_follow": "",
                              "size_layout": 0, "horizontal_pos_layout": 0,
                              "vertical_pos_layout": 0},
    }


def _make_intro_text_material(template_mat: dict, new_text: str) -> dict:
    """Clone text material từ template, thay content.text + range."""
    import json as _json
    new_mat = copy.deepcopy(template_mat)
    new_mat["id"] = _uid()
    try:
        content = _json.loads(template_mat.get("content", "{}"))
    except Exception:
        content = {"styles": [], "text": ""}
    content["text"] = new_text
    # Update range của styles[0] cho khớp text mới (nếu có)
    if content.get("styles"):
        content["styles"][0]["range"] = [0, len(new_text)]
        # Bỏ các styles khác (range thừa)
        content["styles"] = content["styles"][:1]
    new_mat["content"] = _json.dumps(content, ensure_ascii=False)
    return new_mat


def _make_intro_text_segment(template_seg: dict, material_id: str,
                              target_start: int, target_dur: int) -> dict:
    new_seg = copy.deepcopy(template_seg)
    new_seg["id"] = _uid()
    new_seg["material_id"] = material_id
    new_seg["target_timerange"] = {"start": target_start, "duration": target_dur}
    return new_seg


@dataclass
class PrependResult:
    success: bool
    message: str
    prepend_dur_us: int = 0


def prepend_hook_and_intro(draft_path: str, snapshot: HookSnapshot,
                            intro_mp3_path: str,
                            intro_text: str = "") -> PrependResult:
    """SAU PROMAX: prepend hook clones + filler + intro.mp3 vào đầu timeline.

    Nếu `intro_text` non-empty và project có text material làm template,
    tạo thêm 1 text track riêng với text intro tại [hook_total, hook_total+intro_dur].
    """
    if not os.path.isfile(intro_mp3_path):
        return PrependResult(False, f"intro.mp3 không tồn tại: {intro_mp3_path}")

    data = capcut.load_draft_content(draft_path)

    main_track = _find_main_video_track(data)
    if not main_track:
        return PrependResult(False, "Không tìm thấy main video track sau PROMAX")

    hook_total = sum(seg["target_timerange"]["duration"]
                     for cloned in snapshot.hook_video_segs
                     for seg in cloned)
    intro_dur = _get_audio_duration_us(intro_mp3_path)
    prepend_dur = hook_total + intro_dur
    if prepend_dur <= 0:
        return PrependResult(False, "prepend_dur = 0")

    # Shift mọi segment hiện có sang phải
    for t in data.get("tracks", []):
        for seg in t.get("segments", []):
            ts = seg.get("target_timerange")
            if ts:
                ts["start"] += prepend_dur

    # Hook clones: đặt liên tiếp từ 0
    new_segs = []
    cur = 0
    for cloned_group in snapshot.hook_video_segs:
        for seg in cloned_group:
            seg_copy = copy.deepcopy(seg)
            dur = seg_copy["target_timerange"]["duration"]
            seg_copy["target_timerange"] = {"start": cur, "duration": dur}
            seg_copy["id"] = _uid()
            seg_copy["volume"] = 1.0
            seg_copy["last_nonzero_volume"] = 1.0
            new_segs.append(seg_copy)
            cur += dur

    # Filler clips
    N = random.randint(2, 4)
    base_dur = intro_dur // N
    remainder = intro_dur - base_dur * N

    main_dur = snapshot.main_video_duration_us
    if main_dur < base_dur:
        return PrependResult(False, f"Video gốc quá ngắn ({main_dur}us) cho filler ({base_dur}us)")

    for i in range(N):
        clip_dur = base_dur + (remainder if i == N - 1 else 0)
        max_src_start = max(0, main_dur - clip_dur)
        src_start = random.randint(0, max_src_start) if max_src_start > 0 else 0
        seg = _make_filler_video_segment(
            material_id=snapshot.main_video_material_id,
            source_start=src_start, source_dur=clip_dur,
            target_start=cur, target_dur=clip_dur,
            extras=list(snapshot.extra_material_refs_template),
        )
        new_segs.append(seg)
        cur += clip_dur

    # Chèn vào main video track ở đầu
    main_track["segments"] = new_segs + main_track["segments"]

    # Intro audio: tạo material + segment
    intro_mat = _make_audio_material(intro_mp3_path, intro_dur)
    data.setdefault("materials", {}).setdefault("audios", []).append(intro_mat)

    from core import create_project as cp
    speed_mat = cp._make_speed_material()
    sound_mat = cp._make_sound_channel()
    beat_mat = cp._make_beat_material()
    data["materials"].setdefault("speeds", []).append(speed_mat)
    data["materials"].setdefault("sound_channel_mappings", []).append(sound_mat)
    data["materials"].setdefault("beats", []).append(beat_mat)
    extras = [speed_mat["id"], sound_mat["id"], beat_mat["id"]]

    intro_seg = _make_audio_segment(intro_mat["id"], hook_total, intro_dur, extras)

    audio_track = None
    for t in data.get("tracks", []):
        if t.get("type") == "audio":
            audio_track = t
            break
    if audio_track is None:
        audio_track = {
            "id": _uid(), "type": "audio", "segments": [],
            "flag": 0, "attribute": 0, "name": "", "is_default_name": True,
        }
        data["tracks"].append(audio_track)
    audio_track["segments"].insert(0, intro_seg)

    # Text intro (optional): tạo text track riêng nếu intro_text non-empty và có template
    text_added = False
    if intro_text and intro_text.strip():
        # Tìm template text material + segment trong project (sau khi đã shift)
        template_text_mat = None
        template_text_seg = None
        text_mats = data.get("materials", {}).get("texts", [])
        if text_mats:
            template_text_mat = text_mats[0]
            for t in data.get("tracks", []):
                if t.get("type") == "text" and t.get("segments"):
                    template_text_seg = t["segments"][0]
                    break

        if template_text_mat and template_text_seg:
            new_text_mat = _make_intro_text_material(template_text_mat, intro_text.strip())
            text_mats.append(new_text_mat)

            new_text_seg = _make_intro_text_segment(
                template_text_seg, new_text_mat["id"],
                target_start=hook_total, target_dur=intro_dur,
            )

            # Text track riêng
            new_text_track = {
                "id": _uid(), "type": "text", "segments": [new_text_seg],
                "flag": 0, "attribute": 0, "name": "", "is_default_name": True,
            }
            data["tracks"].append(new_text_track)
            text_added = True

    data["duration"] = data.get("duration", 0) + prepend_dur

    try:
        capcut.save_draft_content(draft_path, data)
    except Exception as e:
        return PrependResult(False, f"Save failed: {e}")

    text_msg = " + intro text" if text_added else ""
    return PrependResult(
        True,
        f"Prepended hook ({hook_total/1_000_000:.1f}s) + intro ({intro_dur/1_000_000:.1f}s), "
        f"filler {N} clips{text_msg}",
        prepend_dur_us=prepend_dur,
    )
