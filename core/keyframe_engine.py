"""KeyFrame Engine — thêm/xóa keyframes cho segments trong CapCut project."""

import os
import shutil
import uuid
from dataclasses import dataclass, field

from core import capcut


@dataclass
class KeyFrameOption:
    """Một loại keyframe (Zoom In, Zoom Out, Zoom+Move X/Y)."""
    name: str
    scale_start: float = 1.0   # 1.0 = 100%
    scale_end: float = 1.3     # 1.3 = 130%
    move_x_start: float = 0.0
    move_x_end: float = 0.0
    move_y_start: float = 0.0
    move_y_end: float = 0.0
    has_move_x: bool = False
    has_move_y: bool = False


@dataclass
class KeyFrameConfig:
    options: list[KeyFrameOption] = field(default_factory=list)
    full_duration: bool = True
    time_seconds: float = 0.0
    interval: int = 1
    only_picture: bool = False  # True = chỉ áp cho ảnh, bỏ qua video


@dataclass
class KeyFrameResult:
    success: bool
    message: str
    applied_count: int = 0


def _uid() -> str:
    return str(uuid.uuid4()).upper()


def _make_kf_point(time_offset: int, value: float) -> dict:
    return {
        "id": _uid(),
        "curveType": "Line",
        "time_offset": time_offset,
        "left_control": {"x": 0.0, "y": 0.0},
        "right_control": {"x": 0.0, "y": 0.0},
        "values": [value],
        "string_value": "",
        "graphID": "",
    }


def _make_kf_group(property_type: str, start_val: float, end_val: float,
                    end_time: int) -> dict:
    return {
        "id": _uid(),
        "material_id": "",
        "property_type": property_type,
        "keyframe_list": [
            _make_kf_point(0, start_val),
            _make_kf_point(end_time, end_val),
        ],
    }


def _apply_to_segment(seg: dict, option: KeyFrameOption, config: KeyFrameConfig,
                       canvas_w: int, canvas_h: int, is_photo: bool = False):
    """Áp keyframes cho 1 segment.

    Position values: user nhập pixel → engine chuyển sang tỉ lệ canvas.
    CapCut formula: keyframe_value = pixel / canvas_dimension
    """
    duration = seg["target_timerange"]["duration"]

    # FIX: ảnh có source_timerange ngắn (vd 4s) hơn target (vd 18s) → CapCut tính
    # keyframe theo source nên animation chỉ chạy trong source rồi đóng băng.
    # Đồng bộ source = target để keyframe trải đúng toàn bộ độ dài.
    if is_photo:
        st = seg.get("source_timerange", {})
        if st.get("duration", 0) != duration:
            seg["source_timerange"] = {"start": 0, "duration": duration}

    if config.full_duration:
        end_time = duration
    else:
        end_time = int(config.time_seconds * 1_000_000)
        end_time = min(end_time, duration)

    groups = []

    # ── Scale (Zoom) ──────────────────────────────────────────────
    groups.append(_make_kf_group(
        "KFTypeScaleX", option.scale_start, option.scale_end, end_time
    ))

    clip = seg.get("clip", {})
    clip["scale"] = {"x": option.scale_end, "y": option.scale_end}
    seg["uniform_scale"] = {"on": True, "value": 1.0}

    # ── Position X (pixel → pixel/canvas_width) ──────────────────
    if option.has_move_x:
        kf_x_start = option.move_x_start / canvas_w if canvas_w else 0.0
        kf_x_end = option.move_x_end / canvas_w if canvas_w else 0.0
        groups.append(_make_kf_group(
            "KFTypePositionX", kf_x_start, kf_x_end, end_time
        ))
        transform = clip.get("transform", {"x": 0.0, "y": 0.0})
        transform["x"] = kf_x_end
        clip["transform"] = transform

    # ── Position Y (pixel → pixel/canvas_height) ─────────────────
    if option.has_move_y:
        kf_y_start = option.move_y_start / canvas_h if canvas_h else 0.0
        kf_y_end = option.move_y_end / canvas_h if canvas_h else 0.0
        groups.append(_make_kf_group(
            "KFTypePositionY", kf_y_start, kf_y_end, end_time
        ))
        transform = clip.get("transform", {"x": 0.0, "y": 0.0})
        transform["y"] = kf_y_end
        clip["transform"] = transform

    seg["clip"] = clip
    seg["common_keyframes"] = groups


def apply_keyframes(draft_path: str, config: KeyFrameConfig,
                     backup: bool = True) -> KeyFrameResult:
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

    # Đọc canvas size để chuyển đổi pixel → tỉ lệ
    canvas = data.get("canvas_config", {})
    canvas_w = canvas.get("width", 1920)
    canvas_h = canvas.get("height", 1080)

    total_applied = 0
    option_count = len(config.options)
    option_idx = 0

    for vt in video_tracks:
        for seg_idx, seg in enumerate(vt["segments"]):
            # interval=0: tất cả. interval=3: file 0,3,6,9... (cứ 3 file 1 lần)
            if config.interval > 0 and seg_idx % config.interval != 0:
                continue

            mat_id = seg.get("material_id", "")
            is_photo = capcut.get_material_type(data, mat_id) == "photo"
            # Only Picture: bỏ qua video, chỉ áp cho ảnh
            if config.only_picture and not is_photo:
                continue

            option = config.options[option_idx % option_count]
            option_idx += 1

            _apply_to_segment(seg, option, config, canvas_w, canvas_h, is_photo=is_photo)
            total_applied += 1

    capcut.save_draft_content(draft_path, data)

    opt_names = ", ".join(o.name for o in config.options)
    msg = f"Applied {total_applied} keyframes ({opt_names}), interval={config.interval}"
    return KeyFrameResult(True, msg, total_applied)


def clear_keyframes(draft_path: str, backup: bool = True) -> KeyFrameResult:
    json_path = os.path.join(draft_path, "draft_content.json")

    if not os.path.isfile(json_path):
        return KeyFrameResult(False, "draft_content.json not found")

    if backup:
        shutil.copy2(json_path, json_path + ".bak")

    data = capcut.load_draft_content(draft_path)
    video_tracks = capcut.find_video_tracks(data)

    cleared = 0
    for vt in video_tracks:
        for seg in vt["segments"]:
            if seg.get("common_keyframes"):
                seg["common_keyframes"] = []
                clip = seg.get("clip", {})
                clip["scale"] = {"x": 1.0, "y": 1.0}
                clip["transform"] = {"x": 0.0, "y": 0.0}
                seg["clip"] = clip
                cleared += 1

    capcut.save_draft_content(draft_path, data)
    return KeyFrameResult(True, f"Cleared keyframes from {cleared} segments", cleared)
