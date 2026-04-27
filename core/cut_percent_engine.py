"""Cut Percent Engine — trim segment X% đầu + Y% cuối + tách âm thanh."""

import copy
import json
import os
import shutil
import uuid
from dataclasses import dataclass

from core import capcut


def _uid() -> str:
    return str(uuid.uuid4()).upper()


@dataclass
class CutPercentResult:
    success: bool
    message: str
    cut_count: int = 0
    skip_threshold: int = 0
    skip_n: int = 0
    skip_photo: int = 0
    duration_before_us: int = 0
    duration_after_us: int = 0


def _is_photo_segment(seg: dict, data: dict) -> bool:
    """True nếu segment là ảnh (material type = 'photo')."""
    mat_id = seg.get("material_id", "")
    if not mat_id:
        return False
    for m in data.get("materials", {}).get("videos", []):
        if m.get("id") == mat_id:
            t = m.get("type", "")
            return t == "photo"
    return False


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
        threshold_sec:  None = không filter; else skip segment có target_dur <= threshold.
        every_n:        Pattern "Cắt cách nhau N đoạn".
                        Cut khi (i+1) % (N+1) == 0 với i = segment index trong track.
                        N=0 → cắt mọi segment.
                        N=1 → cắt segment thứ 2, 4, 6, ... (1-based).
                        N=2 → cắt segment thứ 3, 6, 9, ...
                        Index i đếm trên TOÀN BỘ track (kể cả segment skip ảnh/threshold).
        backup:         tạo .bak nếu chưa có.

    Behavior:
        - Chỉ động vào video track đầu tiên (track chính).
        - Audio + text + overlay video tracks: KHÔNG động.
        - Segment ảnh (photo): chỉ shift target.start, không cắt source.
        - Sau khi cắt source, target shift trái dồn các segment khít.
        - data["duration"] = video target end (chỉ tính track chính).
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

    try:
        data = capcut.load_draft_content(draft_path)
    except json.JSONDecodeError as e:
        return CutPercentResult(False, f"draft_content.json bị hỏng: {e}")
    except Exception as e:
        return CutPercentResult(False, f"Không đọc được draft: {e}")

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
    skip_n_count = 0
    skip_photo = 0

    # Sort by target_start để xử lý đúng thứ tự timeline
    segs.sort(key=lambda s: s["target_timerange"]["start"])

    for i, seg in enumerate(segs):
        tgt_dur = seg["target_timerange"]["duration"]

        # 1) Skip ảnh — không cắt source, chỉ shift target ở bước sau
        if _is_photo_segment(seg, data):
            skip_photo += 1
            continue

        # 2) Filter threshold (target_dur <= threshold → skip)
        if threshold_us is not None and tgt_dur <= threshold_us:
            skip_threshold += 1
            continue

        # 3) Pattern N — cut khi (i+1) % (N+1) == 0 với i = index trong track
        # N=0 → mọi segment (1+0)%1=0, (2+0)%1=0, ... → tất cả True
        # N=2 → cut khi (i+1)%3==0 → i=2, 5, 8, ...
        if (i + 1) % (every_n + 1) != 0:
            skip_n_count += 1
            continue

        # Cắt source
        src = seg["source_timerange"]
        old_src_start = src["start"]
        old_src_dur = src["duration"]
        cut_start_us = int(old_src_dur * cut_before_pct / 100)
        cut_end_us = int(old_src_dur * cut_after_pct / 100)
        new_src_dur = old_src_dur - cut_start_us - cut_end_us
        if new_src_dur <= 0:
            # Defensive: tổng cắt > duration → bỏ qua segment này
            skip_threshold += 1
            continue

        src["start"] = old_src_start + cut_start_us
        src["duration"] = new_src_dur

        # Target dur đồng bộ với source mới (chia speed nếu segment có speed != 1)
        speed = seg.get("speed", 1.0) or 1.0
        seg["target_timerange"]["duration"] = int(new_src_dur / speed)

        cut_count += 1

    # Shift target trái dồn segments khít
    cumulative = 0
    for seg in segs:
        seg["target_timerange"]["start"] = cumulative
        cumulative += seg["target_timerange"]["duration"]

    _log(f"  cut: {cut_count}, skip<thr: {skip_threshold}, skip-by-N: {skip_n_count}, skip-photo: {skip_photo}")
    _log(f"  main video new end: {cumulative/1_000_000:.2f}s")

    # Update duration = video target end (chỉ video track chính, khớp đối thủ)
    data["duration"] = cumulative
    _log(f"  duration after: {cumulative/1_000_000:.2f}s")

    capcut.save_draft_content(draft_path, data)

    msg_parts = [f"Cắt {cut_count}"]
    if skip_threshold:
        msg_parts.append(f"{skip_threshold} skip<thr")
    if skip_n_count:
        msg_parts.append(f"{skip_n_count} skip-N")
    if skip_photo:
        msg_parts.append(f"{skip_photo} ảnh")

    return CutPercentResult(
        success=True,
        message=" / ".join(msg_parts),
        cut_count=cut_count,
        skip_threshold=skip_threshold,
        skip_n=skip_n_count,
        skip_photo=skip_photo,
        duration_before_us=duration_before,
        duration_after_us=cumulative,
    )


# ── Extract Audio ─────────────────────────────────────────────────────

@dataclass
class ExtractAudioResult:
    success: bool
    message: str
    extracted_count: int = 0
    skip_photo: int = 0


def _make_audio_material_from_video(video_mat: dict) -> dict:
    """Tạo audio material loại video_original_sound trỏ về cùng file video."""
    return {
        "ai_music_enter_from": "",
        "ai_music_generate_scene": 0,
        "ai_music_type": 0,
        "aigc_history_id": "",
        "aigc_item_id": "",
        "app_id": 0,
        "category_id": "",
        "category_name": "",
        "check_flag": 1,
        "cloned_model_type": "",
        "copyright_limit_type": "none",
        "duration": video_mat.get("duration", 0),
        "effect_id": "",
        "formula_id": "",
        "id": _uid(),
        "intensifies_path": "",
        "is_ai_clone_tone": False,
        "is_ai_clone_tone_post": False,
        "is_text_edit_overdub": False,
        "is_ugc": False,
        "local_material_id": "",
        "lyric_type": 0,
        "mock_tone_speaker": "",
        "moyin_emotion": "",
        "music_id": "",
        "music_source": "",
        "name": os.path.splitext(os.path.basename(video_mat.get("path", "") or ""))[0]
                 or video_mat.get("name", ""),
        "path": video_mat.get("path", ""),
        "pgc_id": "",
        "pgc_name": "",
        "query": "",
        "request_id": "",
        "resource_id": "",
        "search_id": "",
        "similiar_music_info": {"original_song_id": "", "original_song_name": ""},
        "sound_separate_type": "",
        "source_from": "",
        "source_platform": 0,
        "team_id": "",
        "text_id": "",
        "third_resource_id": "",
        "tone_category_id": "",
        "tone_category_name": "",
        "tone_effect_id": "",
        "tone_effect_name": "",
        "tone_emotion_name_key": "",
        "tone_emotion_role": "",
        "tone_emotion_scale": 0.0,
        "tone_emotion_selection": "",
        "tone_emotion_style": "",
        "tone_platform": "",
        "tone_second_category_id": "",
        "tone_second_category_name": "",
        "tone_speaker": "",
        "tone_type": "",
        "tts_benefit_info": {
            "benefit_amount": -1,
            "benefit_log_extra": "",
            "benefit_log_id": "",
            "benefit_type": "none",
        },
        "tts_generate_scene": "",
        "tts_task_id": "",
        "type": "video_original_sound",
        "unique_id": "",
        "video_id": "",
        "wave_points": [],
    }


def _make_extract_extras() -> tuple[list[str], list]:
    """Tạo 5 extra materials per audio segment (speed, placeholder_info,
    beats, sound_channel_mapping, vocal_separation). Trả về (ref_ids, materials_to_add).
    """
    speed = {"curve_speed": None, "id": _uid(), "mode": 0, "speed": 1.0, "type": "speed"}
    placeholder = {
        "error_path": "", "error_text": "", "id": _uid(), "meta_type": "none",
        "res_path": "", "res_text": "", "type": "placeholder_info"
    }
    beats = {
        "ai_beats": {
            "beat_speed_infos": [], "beats_path": "", "beats_url": "",
            "melody_path": "", "melody_percents": [0.6], "melody_url": ""
        },
        "enable_ai_beats": False, "gear": 404, "gear_count": 0,
        "id": _uid(), "mode": 404, "type": "beats",
        "user_beats": [], "user_delete_ai_beats": None,
    }
    sound_chan = {
        "audio_channel_mapping": 0, "id": _uid(),
        "is_config_open": False, "type": "none",
    }
    vocal_sep = {
        "choice": 0, "enter_from": "", "final_algorithm": "",
        "id": _uid(), "production_path": "", "removed_sounds": [],
        "time_range": None, "type": "vocal_separation",
    }
    refs = [speed["id"], placeholder["id"], beats["id"],
            sound_chan["id"], vocal_sep["id"]]
    return refs, [
        ("speeds", speed),
        ("placeholder_infos", placeholder),
        ("beats", beats),
        ("sound_channel_mappings", sound_chan),
        ("vocal_separations", vocal_sep),
    ]


def _make_audio_segment_from_video(
    audio_mat_id: str, extra_refs: list[str], video_seg: dict
) -> dict:
    """Tạo audio segment với timing copy từ video segment."""
    return {
        "caption_info": None,
        "cartoon": False,
        "clip": None,
        "color_correct_alg_result": "",
        "common_keyframes": [],
        "desc": "",
        "digital_human_template_group_id": "",
        "enable_adjust": False,
        "enable_adjust_mask": False,
        "enable_color_adjust_pro": False,
        "enable_color_correct_adjust": False,
        "enable_color_curves": True,
        "enable_color_match_adjust": False,
        "enable_color_wheels": True,
        "enable_hsl": False,
        "enable_hsl_curves": True,
        "enable_lut": False,
        "enable_mask_shadow": False,
        "enable_mask_stroke": False,
        "enable_smart_color_adjust": False,
        "enable_video_mask": True,
        "extra_material_refs": list(extra_refs),
        "group_id": "",
        "hdr_settings": None,
        "id": _uid(),
        "intensifies_audio": False,
        "is_loop": False,
        "is_placeholder": False,
        "is_tone_modify": False,
        "keyframe_refs": [],
        "last_nonzero_volume": 1.0,
        "lyric_keyframes": None,
        "material_id": audio_mat_id,
        "raw_segment_id": "",
        "render_index": 0,
        "render_timerange": {"duration": 0, "start": 0},
        "responsive_layout": {
            "enable": False, "horizontal_pos_layout": 0,
            "size_layout": 0, "target_follow": "", "vertical_pos_layout": 0,
        },
        "reverse": False,
        "source": "segmentsourcenormal",
        "source_timerange": copy.deepcopy(video_seg["source_timerange"]),
        "speed": 1.0,
        "state": 0,
        "target_timerange": copy.deepcopy(video_seg["target_timerange"]),
        "template_id": "",
        "template_scene": "default",
        "track_attribute": 0,
        "track_render_index": 0,
        "uniform_scale": None,
        "visible": True,
        "volume": 1.0,
    }


def extract_audio_from_videos(
    draft_path: str,
    backup: bool = True,
    log_fn=None,
) -> ExtractAudioResult:
    """Tách âm thanh từ tất cả video segments trên video track CHÍNH.

    Behavior (giống CapCut "Tách âm thanh"):
        - Mỗi video segment trên track chính → 1 audio segment trên track audio mới
        - Audio segment có cùng target/source timerange với video segment
        - Mỗi audio segment có audio material riêng (type=video_original_sound)
          trỏ về cùng file mp4 với video material gốc
        - Video segment KHÔNG bị mute (volume nguyên 1.0) — match CapCut native
        - Photo segments: skip (không có audio)
        - Audio track mới được tạo và append (không merge với audio track có sẵn)
    """
    _log = log_fn or (lambda msg: None)

    json_path = os.path.join(draft_path, "draft_content.json")
    if not os.path.isfile(json_path):
        return ExtractAudioResult(False, "draft_content.json not found")

    if backup:
        bak = json_path + ".bak"
        if not os.path.isfile(bak):
            shutil.copy2(json_path, bak)
            _log("  backup created")
        else:
            _log("  backup exists, skipping")

    try:
        data = capcut.load_draft_content(draft_path)
    except json.JSONDecodeError as e:
        return ExtractAudioResult(False, f"draft_content.json bị hỏng: {e}")
    except Exception as e:
        return ExtractAudioResult(False, f"Không đọc được draft: {e}")

    video_tracks = capcut.find_video_tracks(data)
    if not video_tracks:
        return ExtractAudioResult(False, "Không tìm thấy video track")

    main_track = video_tracks[0]
    segs = main_track.get("segments", [])
    if not segs:
        return ExtractAudioResult(False, "Track chính không có segment nào")

    _log(f"  main video track: {len(segs)} segments")

    # Index video materials by id
    v_mats = data.get("materials", {}).setdefault("videos", [])
    v_mat_by_id = {m.get("id"): m for m in v_mats}

    # New materials lists to append
    new_audio_mats = []
    new_extra_groups = []  # list of (key, material_dict) tuples
    new_audio_segs = []

    extracted = 0
    skip_photo = 0

    for seg in segs:
        v_mat = v_mat_by_id.get(seg.get("material_id", ""))
        if not v_mat:
            continue
        if v_mat.get("type") == "photo":
            skip_photo += 1
            continue

        # Tạo audio material trỏ về cùng file video
        a_mat = _make_audio_material_from_video(v_mat)
        new_audio_mats.append(a_mat)

        # Tạo 5 extra materials
        extra_refs, extras = _make_extract_extras()
        new_extra_groups.extend(extras)

        # Tạo audio segment với timing giống video segment
        a_seg = _make_audio_segment_from_video(a_mat["id"], extra_refs, seg)
        new_audio_segs.append(a_seg)

        extracted += 1

    if extracted == 0:
        return ExtractAudioResult(False, "Không có video segment nào để extract")

    # Append new materials vào draft
    data.setdefault("materials", {}).setdefault("audios", []).extend(new_audio_mats)
    for key, mat in new_extra_groups:
        data["materials"].setdefault(key, []).append(mat)

    # Tạo audio track mới và append vào tracks
    audio_track = {
        "id": _uid(),
        "type": "audio",
        "segments": new_audio_segs,
        "flag": 0,
        "attribute": 0,
        "name": "",
        "is_default_name": True,
    }
    data.setdefault("tracks", []).append(audio_track)

    _log(f"  extracted: {extracted}, skip-photo: {skip_photo}")

    capcut.save_draft_content(draft_path, data)

    msg = f"Trích xuất {extracted} audio segments"
    if skip_photo:
        msg += f" ({skip_photo} skip ảnh)"
    return ExtractAudioResult(
        success=True,
        message=msg,
        extracted_count=extracted,
        skip_photo=skip_photo,
    )
