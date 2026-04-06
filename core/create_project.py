"""Create Project — tạo project CapCut mới từ folder ảnh/video + audio."""

import os
import json
import uuid
import time
from dataclasses import dataclass, field
from PIL import Image

from core import capcut


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv"}
AUDIO_EXTS = {".mp3", ".wav", ".aac", ".m4a", ".ogg"}

CANVAS_PRESETS = {
    "16:9": {"ratio": "16:9", "width": 1920, "height": 1080},
    "9:16": {"ratio": "9:16", "width": 1080, "height": 1920},
    "1:1": {"ratio": "1:1", "width": 1080, "height": 1080},
    "4:3": {"ratio": "4:3", "width": 1440, "height": 1080},
}

QUALITY_PRESETS = {
    "1080p": (1920, 1080),
    "720p": (1280, 720),
    "4K": (3840, 2160),
}


@dataclass
class CreateConfig:
    project_name: str = "New Project"
    media_folder: str = ""
    audio_folder: str = ""
    image_duration: float = 4.0  # Giây
    ratio: str = "16:9"
    quality: str = "1080p"
    fps: int = 30


@dataclass
class CreateResult:
    success: bool
    message: str
    project_path: str = ""


def _uid() -> str:
    return str(uuid.uuid4()).upper()


def _natural_sort_key(filename: str):
    """Sort key: 1.mp3 < 2.mp3 < 10.mp3 (không phải 1 < 10 < 2)."""
    import re
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', filename)]


def _scan_files(folder: str, extensions: set) -> list[str]:
    """Scan folder, trả về list file paths sorted by natural order."""
    if not folder or not os.path.isdir(folder):
        return []
    files = []
    for f in sorted(os.listdir(folder), key=_natural_sort_key):
        ext = os.path.splitext(f)[1].lower()
        if ext in extensions:
            files.append(os.path.join(folder, f).replace("\\", "/"))
    return files


def _get_media_info(filepath: str) -> dict:
    """Lấy thông tin media: type, width, height, duration."""
    ext = os.path.splitext(filepath)[1].lower()
    name = os.path.basename(filepath)

    if ext in IMAGE_EXTS:
        try:
            with Image.open(filepath) as img:
                w, h = img.size
        except Exception:
            w, h = 1920, 1080
        return {"type": "photo", "width": w, "height": h, "duration": 10800000000, "name": name, "has_audio": False}
    else:
        # Video: đọc duration thật
        vid_dur = 10000000  # fallback 10s
        try:
            from mutagen import File
            f = File(filepath)
            if f and f.info:
                vid_dur = int(f.info.length * 1_000_000)
        except Exception:
            pass
        return {"type": "video", "width": 1920, "height": 1080, "duration": vid_dur, "name": name, "has_audio": True}


def _get_audio_duration(filepath: str) -> int:
    """Đọc duration audio chính xác (microseconds)."""
    # Method 1: mutagen (chính xác)
    try:
        from mutagen.mp3 import MP3
        audio = MP3(filepath)
        return int(audio.info.length * 1_000_000)
    except Exception:
        pass

    # Method 2: mutagen generic
    try:
        from mutagen import File
        audio = File(filepath)
        if audio and audio.info:
            return int(audio.info.length * 1_000_000)
    except Exception:
        pass

    # Method 3: fallback estimate từ file size (~96kbps)
    try:
        size = os.path.getsize(filepath)
        return int((size / (96 * 1024 / 8)) * 1_000_000)
    except Exception:
        return 5000000


def _make_video_material(filepath: str, info: dict) -> dict:
    return {
        "id": _uid(),
        "unique_id": "",
        "type": info["type"],
        "duration": info["duration"],
        "path": filepath,
        "media_path": "",
        "local_id": "",
        "has_audio": info["has_audio"],
        "reverse_path": "",
        "intensifies_path": "",
        "reverse_intensifies_path": "",
        "intensifies_audio_path": "",
        "cartoon_path": "",
        "width": info["width"],
        "height": info["height"],
        "category_id": "",
        "category_name": "local",
        "material_id": "",
        "material_name": info["name"],
        "material_url": "",
        "crop": {
            "upper_left_x": 0.0, "upper_left_y": 0.0,
            "upper_right_x": 1.0, "upper_right_y": 0.0,
            "lower_left_x": 0.0, "lower_left_y": 1.0,
            "lower_right_x": 1.0, "lower_right_y": 1.0,
        },
        "crop_ratio": "free",
        "audio_fade": None,
        "crop_scale": 1.0,
        "extra_type_option": 0,
        "stable": {"stable_level": 0, "matrix_path": "", "time_range": {"start": 0, "duration": 0}},
        "matting": {"flag": 0, "path": "", "interactiveTime": [], "has_use_quick_brush": False,
                    "strokes": [], "has_use_quick_eraser": False, "expansion": 0, "feather": 0,
                    "reverse": False, "custom_matting_id": "", "enable_matting_stroke": False},
        "source": 0,
        "source_platform": 0,
        "formula_id": "",
        "check_flag": 62978047,
    }


def _make_audio_material(filepath: str, duration: int) -> dict:
    name = os.path.basename(filepath)
    return {
        "id": _uid(),
        "unique_id": "",
        "type": "extract_music",
        "name": name,
        "duration": duration,
        "path": filepath,
        "category_name": "local",
        "wave_points": [],
        "music_id": "",
        "app_id": 0,
        "text_id": "",
        "tone_type": "",
        "source_platform": 0,
        "video_id": "",
        "effect_id": "",
        "resource_id": "",
        "third_resource_id": "",
        "category_id": "",
        "intensifies_path": "",
        "formula_id": "",
        "check_flag": 1,
    }


def _make_speed_material() -> dict:
    return {"id": _uid(), "type": "speed", "mode": 0, "speed": 1.0, "curve_speed": None}


def _make_canvas_material() -> dict:
    return {
        "id": _uid(), "type": "canvas_color",
        "color": "", "image_id": "", "image_name": "",
        "image_path": "", "source_platform": 0,
        "team_id": "", "category_id": "",
        "category_name": "",
    }


def _make_sound_channel() -> dict:
    return {"id": _uid(), "type": "none", "audio_channel_mapping": 0, "is_config_open": False}


def _make_beat_material() -> dict:
    return {
        "id": _uid(), "type": "beats",
        "ai_beats": {"beats_path": "", "beats_url": "", "downbeat_url": "",
                     "melody_path": "", "melody_percep_path": "", "melody_url": ""},
        "gear": 404, "gear_count": 0, "mode": 404, "user_beats": [],
        "user_delete_ai_beats": None,
    }


def _make_video_segment(material_id: str, start: int, duration: int,
                         speed_id: str, canvas_id: str, sound_id: str) -> dict:
    return {
        "id": _uid(),
        "source_timerange": {"start": 0, "duration": duration},
        "target_timerange": {"start": start, "duration": duration},
        "render_timerange": {"start": 0, "duration": 0},
        "desc": "", "state": 0, "speed": 1.0,
        "is_loop": False, "is_tone_modify": False, "reverse": False,
        "intensifies_audio": False, "cartoon": False,
        "volume": 1.0, "last_nonzero_volume": 1.0,
        "clip": {
            "scale": {"x": 1.0, "y": 1.0}, "rotation": 0.0,
            "transform": {"x": 0.0, "y": 0.0},
            "flip": {"vertical": False, "horizontal": False}, "alpha": 1.0,
        },
        "uniform_scale": {"on": True, "value": 1.0},
        "material_id": material_id,
        "extra_material_refs": [speed_id, canvas_id, sound_id],
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
                              "size_layout": 0, "horizontal_pos_layout": 0, "vertical_pos_layout": 0},
    }


def _make_audio_segment(material_id: str, start: int, duration: int,
                         speed_id: str, sound_id: str, beat_id: str) -> dict:
    return {
        "id": _uid(),
        "source_timerange": {"start": 0, "duration": duration},
        "target_timerange": {"start": start, "duration": duration},
        "render_timerange": {"start": 0, "duration": 0},
        "desc": "", "state": 0, "speed": 1.0,
        "is_loop": False, "is_tone_modify": False, "reverse": False,
        "intensifies_audio": False, "cartoon": False,
        "volume": 1.0, "last_nonzero_volume": 1.0,
        "clip": None, "uniform_scale": None,
        "material_id": material_id,
        "extra_material_refs": [speed_id, sound_id, beat_id],
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
                              "size_layout": 0, "horizontal_pos_layout": 0, "vertical_pos_layout": 0},
    }


def create_project(config: CreateConfig, capcut_path: str) -> CreateResult:
    """Tạo project CapCut mới."""
    # Scan media files
    media_files = _scan_files(config.media_folder, IMAGE_EXTS | VIDEO_EXTS)
    if not media_files:
        return CreateResult(False, "No images/videos found in folder")

    audio_files = _scan_files(config.audio_folder, AUDIO_EXTS)

    # Canvas config
    canvas = CANVAS_PRESETS.get(config.ratio, CANVAS_PRESETS["16:9"]).copy()
    if config.quality in QUALITY_PRESETS:
        qw, qh = QUALITY_PRESETS[config.quality]
        if config.ratio == "9:16":
            canvas["width"], canvas["height"] = qh, qw
        elif config.ratio == "1:1":
            canvas["width"] = canvas["height"] = min(qw, qh)
        else:
            canvas["width"], canvas["height"] = qw, qh

    canvas["background"] = None

    # Duration per image (microseconds)
    img_dur = int(config.image_duration * 1_000_000)

    # Build materials + segments
    video_materials = []
    audio_materials = []
    speed_materials = []
    canvas_materials = []
    sound_channels = []
    beat_materials = []
    video_segments = []
    audio_segments = []

    # Video track
    current_time = 0
    for filepath in media_files:
        info = _get_media_info(filepath)

        mat = _make_video_material(filepath, info)
        video_materials.append(mat)

        speed = _make_speed_material()
        speed_materials.append(speed)
        cnv = _make_canvas_material()
        canvas_materials.append(cnv)
        snd = _make_sound_channel()
        sound_channels.append(snd)

        # Duration: ảnh dùng image_duration, video dùng duration gốc
        if info["type"] == "photo":
            seg_dur = img_dur
        else:
            seg_dur = info["duration"]

        seg = _make_video_segment(mat["id"], current_time, seg_dur,
                                   speed["id"], cnv["id"], snd["id"])
        video_segments.append(seg)
        current_time += seg_dur

    total_video_duration = current_time

    # Audio track
    current_time = 0
    for filepath in audio_files:
        dur = _get_audio_duration(filepath)
        mat = _make_audio_material(filepath, dur)
        audio_materials.append(mat)

        speed = _make_speed_material()
        speed_materials.append(speed)
        snd = _make_sound_channel()
        sound_channels.append(snd)
        beat = _make_beat_material()
        beat_materials.append(beat)

        seg = _make_audio_segment(mat["id"], current_time, dur,
                                   speed["id"], snd["id"], beat["id"])
        audio_segments.append(seg)
        current_time += dur

    total_duration = max(total_video_duration, current_time) if audio_segments else total_video_duration

    # Build draft_content.json
    project_id = _uid()
    tracks = [
        {"id": _uid(), "type": "video", "segments": video_segments, "flag": 0,
         "attribute": 0, "name": "", "is_default_name": True},
    ]
    if audio_segments:
        tracks.append(
            {"id": _uid(), "type": "audio", "segments": audio_segments, "flag": 0,
             "attribute": 0, "name": "", "is_default_name": True}
        )

    draft_content = {
        "id": project_id,
        "version": "",
        "new_version": "163.0.0",
        "name": config.project_name,
        "duration": total_duration,
        "create_time": int(time.time()),
        "update_time": int(time.time()),
        "fps": float(config.fps),
        "is_drop_frame_timecode": False,
        "color_space": 0,
        "config": {"adjust_max_index": 1, "attachment_info": []},
        "canvas_config": canvas,
        "tracks": tracks,
        "group_container": {"groups": []},
        "materials": {
            "flowers": [],
            "videos": video_materials,
            "tail_leaders": [],
            "audios": audio_materials,
            "images": [],
            "texts": [],
            "effects": [],
            "stickers": [],
            "canvases": canvas_materials,
            "transitions": [],
            "audio_effects": [],
            "audio_fades": [],
            "beats": beat_materials,
            "material_animations": [],
            "placeholders": [],
            "placeholder_infos": [],
            "speeds": speed_materials,
            "common_mask": [],
            "chromas": [],
            "text_templates": [],
            "realtime_denoises": [],
            "audio_pannings": [],
            "audio_pitch_shifts": [],
            "video_trackings": [],
            "hsl": [],
            "drafts": [],
            "color_curves": [],
            "hsl_curves": [],
            "primary_color_wheels": [],
            "log_color_wheels": [],
            "video_effects": [],
            "audio_balances": [],
            "handwrites": [],
            "manual_deformations": [],
            "manual_beautys": [],
            "plugin_effects": [],
            "sound_channel_mappings": sound_channels,
            "green_screens": [],
            "shapes": [],
            "material_colors": [],
            "digital_humans": [],
            "smart_crops": [],
            "ai_translates": [],
            "audio_track_indexes": [],
            "loudnesses": [],
            "vocal_beautifys": [],
            "vocal_separations": [],
            "smart_relights": [],
            "time_marks": [],
            "multi_language_refs": [],
            "video_shadows": [],
            "video_strokes": [],
            "video_radius": [],
        },
        "keyframes": {"videos": [], "audios": [], "texts": [], "stickers": [], "filters": [],
                      "handwrites": [], "shapes": [], "transitions": []},
        "keyframe_graph_list": [],
        "platform": {"app_id": 3704, "app_source": "cc", "app_version": "8.3.0",
                     "device_id": "", "hard_disk_id": "", "mac_address": "",
                     "os": "windows", "os_version": "10.0.19045"},
        "last_modified_platform": {"app_id": 3704, "app_source": "cc", "app_version": "8.3.0",
                                   "os": "windows", "os_version": "10.0.19045"},
        "mutable_config": None,
        "cover": "",
        "extra_info": "",
        "relationships": [],
        "render_index_track_mode_on": False,
        "free_render_index_mode_on": False,
        "static_cover_image_path": "",
        "source": "default",
        "time_marks": [],
        "lyrics_effects": [],
        "draft_type": "",
    }

    # Create project folder
    draft_root = capcut.get_draft_root(capcut_path)
    project_folder = os.path.join(draft_root, config.project_name)
    os.makedirs(project_folder, exist_ok=True)

    # Save draft_content.json
    content_path = os.path.join(project_folder, "draft_content.json")
    with open(content_path, "w", encoding="utf-8") as f:
        json.dump(draft_content, f, ensure_ascii=False)

    # Save draft_meta_info.json
    now_us = int(time.time() * 1_000_000)
    draft_meta = {
        "cloud_draft_cover": False,
        "cloud_draft_sync": False,
        "draft_cloud_last_action_download": False,
        "draft_cloud_purchase_info": "",
        "draft_cloud_template_id": "",
        "draft_cloud_tutorial_info": "",
        "draft_cloud_videocut_purchase_info": "",
        "draft_cover": "",
        "draft_fold_path": project_folder.replace("/", "\\"),
        "draft_id": project_id,
        "draft_is_ai_shorts": False,
        "draft_is_cloud_temp_draft": False,
        "draft_is_invisible": False,
        "draft_name": config.project_name,
        "draft_new_version": "",
        "draft_root_path": draft_root.replace("/", "\\"),
        "draft_timeline_materials_size_": 0,
        "tm_draft_create": now_us,
        "tm_draft_modified": now_us,
        "tm_draft_removed": 0,
        "tm_duration": total_duration,
    }
    meta_path = os.path.join(project_folder, "draft_meta_info.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(draft_meta, f, ensure_ascii=False)

    # Update root_meta_info.json
    root_meta_path = os.path.join(draft_root, "root_meta_info.json")
    with open(root_meta_path, "r", encoding="utf-8") as f:
        root_meta = json.load(f)

    root_entry = {
        "cloud_draft_cover": False,
        "cloud_draft_sync": False,
        "draft_cloud_last_action_download": False,
        "draft_cloud_purchase_info": "",
        "draft_cloud_template_id": "",
        "draft_cloud_tutorial_info": "",
        "draft_cloud_videocut_purchase_info": "",
        "draft_cover": "",
        "draft_fold_path": project_folder.replace("\\", "/"),
        "draft_id": project_id,
        "draft_is_ai_shorts": False,
        "draft_is_cloud_temp_draft": False,
        "draft_is_invisible": False,
        "draft_is_web_article_video": False,
        "draft_json_file": content_path.replace("\\", "/"),
        "draft_name": config.project_name,
        "draft_new_version": "",
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
        "tm_duration": total_duration,
    }

    # Remove old entry with same name if exists
    root_meta["all_draft_store"] = [
        d for d in root_meta["all_draft_store"]
        if d.get("draft_name") != config.project_name
    ]
    root_meta["all_draft_store"].insert(0, root_entry)

    with open(root_meta_path, "w", encoding="utf-8") as f:
        json.dump(root_meta, f, ensure_ascii=False)

    msg = f"Created '{config.project_name}': {len(media_files)} media, {len(audio_files)} audio"
    return CreateResult(True, msg, project_folder)


@dataclass
class BatchResult:
    total: int = 0
    created: int = 0
    skipped: list[str] = None

    def __post_init__(self):
        if self.skipped is None:
            self.skipped = []


def batch_create_projects(
    media_parent: str,
    audio_parent: str,
    capcut_path: str,
    image_duration: float = 4.0,
    ratio: str = "16:9",
    quality: str = "1080p",
    fps: int = 30,
    callback=None,
) -> BatchResult:
    """Tạo đồng loạt projects từ thư mục cha.

    Chỉ tạo khi thư mục con ảnh VÀ audio cùng tên đều tồn tại.
    """
    result = BatchResult()

    if not os.path.isdir(media_parent):
        if callback: callback(f"Media parent not found: {media_parent}")
        return result
    if not os.path.isdir(audio_parent):
        if callback: callback(f"Audio parent not found: {audio_parent}")
        return result

    # Scan thư mục con
    media_subs = {d for d in os.listdir(media_parent)
                  if os.path.isdir(os.path.join(media_parent, d))}
    audio_subs = {d for d in os.listdir(audio_parent)
                  if os.path.isdir(os.path.join(audio_parent, d))}

    # Chỉ lấy thư mục có CẢ 2
    matched = sorted(media_subs & audio_subs)
    skipped_media = sorted(media_subs - audio_subs)
    skipped_audio = sorted(audio_subs - media_subs)

    result.total = len(media_subs)

    # Log skipped
    for name in skipped_media:
        msg = f"SKIP '{name}': có ảnh nhưng KHÔNG có audio"
        result.skipped.append(msg)
        if callback: callback(msg)

    for name in skipped_audio:
        msg = f"SKIP '{name}': có audio nhưng KHÔNG có ảnh"
        result.skipped.append(msg)
        if callback: callback(msg)

    if not matched:
        if callback: callback("Không tìm thấy cặp thư mục ảnh+audio nào trùng tên!")
        return result

    if callback: callback(f"Found {len(matched)} matched pairs: {matched[:5]}{'...' if len(matched)>5 else ''}")

    # Tạo từng project
    for name in matched:
        media_folder = os.path.join(media_parent, name)
        audio_folder = os.path.join(audio_parent, name)

        config = CreateConfig(
            project_name=name,
            media_folder=media_folder,
            audio_folder=audio_folder,
            image_duration=image_duration,
            ratio=ratio,
            quality=quality,
            fps=fps,
        )

        if callback: callback(f"Creating '{name}'...")

        r = create_project(config, capcut_path)
        if r.success:
            result.created += 1
            if callback: callback(f"  OK: {r.message}")
        else:
            result.skipped.append(f"FAIL '{name}': {r.message}")
            if callback: callback(f"  FAIL: {r.message}")

    if callback: callback(f"Batch done: {result.created}/{len(matched)} created, {len(result.skipped)} skipped")
    return result
