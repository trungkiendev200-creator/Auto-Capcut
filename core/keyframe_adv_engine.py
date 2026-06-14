"""KeyFrame Nâng Cao — keyframe zoom/pan bắt đầu SAU khi animation-in/transition
của segment chạy xong + 0.25s, để không gây nhiễu thị giác.

Tái sử dụng KeyFrameOption/KeyFrameConfig của keyframe_engine; chỉ khác ở chỗ
điểm keyframe đầu được dời tới mốc effect_end + padding (ảnh đứng yên trong lúc
hiệu ứng vào đang chạy, rồi mới chuyển động).
"""

import os
import shutil

from core import capcut
from core.keyframe_engine import (
    KeyFrameOption, KeyFrameConfig, KeyFrameResult,
    _uid, _make_kf_point,
)


PADDING_US = 250_000          # 0.25s cố định sau khi hiệu ứng vào kết thúc
MIN_MOTION_US = 200_000       # giữ tối thiểu 0.2s cho chuyển động nếu segment ngắn


def _build_effect_maps(materials: dict):
    """id material_animation/transition -> dict, để tra duration nhanh."""
    anim_map = {m["id"]: m for m in materials.get("material_animations", [])
                if isinstance(m, dict) and "id" in m}
    trans_map = {m["id"]: m for m in materials.get("transitions", [])
                 if isinstance(m, dict) and "id" in m}
    return anim_map, trans_map


def _segment_effect_end(seg: dict, anim_map: dict, trans_map: dict) -> int:
    """max(duration animation-in, duration transition) của segment (microseconds)."""
    eff = 0
    for ref in seg.get("extra_material_refs", []):
        ma = anim_map.get(ref)
        if ma:
            for an in ma.get("animations", []):
                if an.get("type") == "in":
                    eff = max(eff, an.get("duration", 0))
        tr = trans_map.get(ref)
        if tr:
            eff = max(eff, tr.get("duration", 0))
    return eff


def _make_kf_group_offset(property_type: str, start_val: float, end_val: float,
                          start_time: int, end_time: int) -> dict:
    """Keyframe group giữ start_val tới start_time rồi ramp tới end_val ở end_time."""
    points = []
    if start_time > 0:
        points.append(_make_kf_point(0, start_val))        # giữ tĩnh từ đầu
        points.append(_make_kf_point(start_time, start_val))
    else:
        points.append(_make_kf_point(0, start_val))
    points.append(_make_kf_point(end_time, end_val))
    return {
        "id": _uid(),
        "material_id": "",
        "property_type": property_type,
        "keyframe_list": points,
    }


def _apply_to_segment_adv(seg: dict, option: KeyFrameOption, config: KeyFrameConfig,
                          canvas_w: int, canvas_h: int, start_time: int,
                          is_photo: bool = False):
    """Như _apply_to_segment nhưng keyframe đầu dời tới start_time."""
    duration = seg["target_timerange"]["duration"]

    # FIX: ảnh thường có source_timerange ngắn (vd 4s) trong khi target dài (18s).
    # CapCut tính keyframe theo source → animation chỉ chạy trong source rồi đóng
    # băng. Đồng bộ source = target để keyframe trải đúng toàn bộ độ dài.
    if is_photo:
        st = seg.get("source_timerange", {})
        if st.get("duration", 0) != duration:
            seg["source_timerange"] = {"start": 0, "duration": duration}

    if config.full_duration:
        end_time = duration
    else:
        end_time = min(int(config.time_seconds * 1_000_000), duration)

    # Clamp: đảm bảo còn tối thiểu MIN_MOTION cho chuyển động
    start_time = max(0, min(start_time, end_time - MIN_MOTION_US))

    groups = []
    groups.append(_make_kf_group_offset(
        "KFTypeScaleX", option.scale_start, option.scale_end, start_time, end_time
    ))

    clip = seg.get("clip", {})
    clip["scale"] = {"x": option.scale_end, "y": option.scale_end}
    seg["uniform_scale"] = {"on": True, "value": 1.0}

    if option.has_move_x:
        kf_x_start = option.move_x_start / canvas_w if canvas_w else 0.0
        kf_x_end = option.move_x_end / canvas_w if canvas_w else 0.0
        groups.append(_make_kf_group_offset(
            "KFTypePositionX", kf_x_start, kf_x_end, start_time, end_time
        ))
        transform = clip.get("transform", {"x": 0.0, "y": 0.0})
        transform["x"] = kf_x_end
        clip["transform"] = transform

    if option.has_move_y:
        kf_y_start = option.move_y_start / canvas_h if canvas_h else 0.0
        kf_y_end = option.move_y_end / canvas_h if canvas_h else 0.0
        groups.append(_make_kf_group_offset(
            "KFTypePositionY", kf_y_start, kf_y_end, start_time, end_time
        ))
        transform = clip.get("transform", {"x": 0.0, "y": 0.0})
        transform["y"] = kf_y_end
        clip["transform"] = transform

    seg["clip"] = clip
    seg["common_keyframes"] = groups


def apply_keyframes_advanced(draft_path: str, config: KeyFrameConfig,
                             backup: bool = True) -> KeyFrameResult:
    """Áp keyframe bắt đầu sau max(animation, transition) + 0.25s mỗi segment."""
    json_path = os.path.join(draft_path, "draft_content.json")
    if not os.path.isfile(json_path):
        return KeyFrameResult(False, "draft_content.json not found")
    if not config.options:
        return KeyFrameResult(False, "No keyframe options selected")

    if backup:
        shutil.copy2(json_path, json_path + ".bak")

    data = capcut.load_draft_content(draft_path)
    video_tracks = capcut.find_video_tracks(data)
    if not video_tracks:
        return KeyFrameResult(False, "No video track with segments found")

    canvas = data.get("canvas_config", {})
    canvas_w = canvas.get("width", 1920)
    canvas_h = canvas.get("height", 1080)

    materials = data.get("materials", {})
    anim_map, trans_map = _build_effect_maps(materials)

    total_applied = 0
    option_count = len(config.options)
    option_idx = 0

    for vt in video_tracks:
        for seg_idx, seg in enumerate(vt["segments"]):
            if config.interval > 0 and seg_idx % config.interval != 0:
                continue
            mat_id = seg.get("material_id", "")
            is_photo = capcut.get_material_type(data, mat_id) == "photo"
            if config.only_picture and not is_photo:
                continue

            option = config.options[option_idx % option_count]
            option_idx += 1

            eff_end = _segment_effect_end(seg, anim_map, trans_map)
            start_time = eff_end + PADDING_US

            _apply_to_segment_adv(seg, option, config, canvas_w, canvas_h,
                                  start_time, is_photo=is_photo)
            total_applied += 1

    capcut.save_draft_content(draft_path, data)

    opt_names = ", ".join(o.name for o in config.options)
    msg = f"Applied {total_applied} keyframes nâng cao ({opt_names})"
    return KeyFrameResult(True, msg, total_applied)
