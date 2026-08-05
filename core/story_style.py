"""Story Style — hiệu ứng / mask / sticker trích nguyên từ project mẫu "brazil stories01".

Nguồn: CapCut draft "brazil stories01" (folder 0805) do người dùng dựng tay.
    - Hiệu ứng "Khung phim 1" áp lên MỌI segment video (stock nền + ảnh overlay).
    - Mask "Cuộn phim" + clip.scale 0.85 trên segment ảnh.
    - Sticker "INTERACTION ICONS EN SUBSCRIBE" ở góc dưới-phải, dài = cả project.

Mọi resource lấy từ CapCut cache (người dùng đã tải sẵn). Không tìm thấy path →
để rỗng, CapCut sẽ tự tải lại khi mở project.
"""

import os
import uuid


# ── Hằng số trích từ project mẫu ───────────────────────────────────────

# Hiệu ứng video áp lên từng segment
FILM_EFFECT_NAME = "Khung phim 1"
FILM_EFFECT_ID = "7399464865909198086"
FILM_EFFECT_CATEGORY_ID = "100000"
FILM_EFFECT_CATEGORY = "Hiệu ứng video"
FILM_EFFECT_VALUE = 1.0

# Mask trên segment ảnh
FILM_MASK_NAME = "Cuộn phim"
FILM_MASK_RESOURCE_ID = "7374021024985125377"
FILM_MASK_CACHE_ID = "1068046539"   # thư mục cache thật (khác resource_id)
FILM_MASK_CONFIG = {
    "width": 0.28, "height": 1.0, "centerX": 0.0, "centerY": 0.0,
    "rotation": 0.0, "feather": 1.0, "expansion": 0.0,
    "roundCorner": 0.0, "invert": False, "aspectRatio": 1.0,
}

# Ảnh overlay thu nhỏ còn 85%
PHOTO_SCALE = 0.85

# Sticker Subscribe
STICKER_NAME = "INTERACTION ICONS EN SUBSCRIBE"
STICKER_ID = "7472904027596950845"
STICKER_CATEGORY_ID = "100000"
STICKER_CATEGORY = "Yêu thích"
STICKER_ICON_URL = (
    "https://p16-heycan-image-sign-sg.ibyteimg.com/tos-alisg-i-fhsjxsyzit-sg/"
    "c1e79943b7b14083988586463a656473~tplv-fhsjxsyzit-resize:200:200.png"
    "?x-expires=1817461784&x-signature=GexO2BgSOus7OgCT4uxs9ljCim4%3D"
)
STICKER_SCALE = 0.3235489075454812
STICKER_POS_X = 0.7067307692307692
STICKER_POS_Y = -0.7378917378917378
STICKER_RENDER_INDEX = 14000


def _uid() -> str:
    return str(uuid.uuid4()).upper()


def _find_cached(sub: str, *ids: str) -> str:
    """Tìm file resource trong CapCut cache: Cache/<sub>/<id>/<hash>."""
    base = os.path.join(os.environ.get("LOCALAPPDATA", ""),
                        "CapCut", "User Data", "Cache", sub)
    for rid in ids:
        d = os.path.join(base, rid)
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if not f.endswith("_tmp"):
                return os.path.join(d, f).replace("\\", "/")
    return ""


# ── Builders ───────────────────────────────────────────────────────────

def make_film_effect() -> dict:
    """1 material video_effect "Khung phim 1" (mỗi segment cần 1 material riêng)."""
    return {
        "id": _uid(),
        "effect_id": FILM_EFFECT_ID,
        "resource_id": FILM_EFFECT_ID,
        "name": FILM_EFFECT_NAME,
        "type": "video_effect",
        "sub_type": 0,
        "bind_segment_id": "",
        "transparent_params": "",
        "path": _find_cached("effect", FILM_EFFECT_ID),
        "value": FILM_EFFECT_VALUE,
        "category_id": FILM_EFFECT_CATEGORY_ID,
        "category_name": FILM_EFFECT_CATEGORY,
        "platform": "all",
        "apply_target_type": 0,
        "source_platform": 1,
        "version": "",
        "item_effect_type": 0,
        "adjust_params": [],
        "time_range": None,
        "formula_id": "",
        "apply_time_range": None,
        "render_index": 11000,
        "track_render_index": 0,
        "common_keyframes": [],
        "request_id": "",
        "algorithm_artifact_path": "",
        "disable_effect_faces": [],
        "covering_relation_change": 0,
        "enable_mask": True,
        "effect_mask": [],
        "enable_video_mask_stroke": True,
        "enable_video_mask_shadow": True,
        "aigc_current_artifact_path": "",
        "aigc_current_artifact_cnt": 0,
        "aigc_current_artifact_freeze_time": -1,
        "aigc_current_artifact_freeze_progress": 0.0,
        "sdk_extra": "",
    }


def make_film_mask() -> dict:
    """1 material mask "Cuộn phim"."""
    return {
        "id": _uid(),
        "type": "mask",
        "category": "video",
        "category_name": "",
        "category_id": "",
        "panel": "",
        "is_old_version": False,
        "resource_id": FILM_MASK_RESOURCE_ID,
        "constant_material_id": _uid(),
        "name": FILM_MASK_NAME,
        "resource_type": "mirror",
        "path": _find_cached("effect", FILM_MASK_RESOURCE_ID, FILM_MASK_CACHE_ID),
        "position_info": "",
        "config": dict(FILM_MASK_CONFIG),
        "text_config": {
            "content": "", "font_name": "", "font_path": "",
            "font_resource_id": "", "font_size": 15.0, "bold_width": 0.0,
            "italic_degree": 0, "has_underline": False, "line_gap": 0.0,
            "char_spacing": 0.0, "align_type": 15, "scale": 1.0,
        },
        "platform": "all",
        "loader_work_space": "",
        "track_segment": "",
        "contour_path": None,
        "source_platform": 0,
    }


def make_sticker_material() -> dict:
    """1 material sticker Subscribe."""
    return {
        "id": _uid(),
        "unique_id": "",
        "type": "sticker",
        "path": _find_cached("artistEffect", STICKER_ID),
        "icon_url": STICKER_ICON_URL,
        "preview_cover_url": STICKER_ICON_URL,
        "sticker_id": STICKER_ID,
        "resource_id": STICKER_ID,
        "name": STICKER_NAME,
        "category_id": STICKER_CATEGORY_ID,
        "category_name": STICKER_CATEGORY,
        "platform": "all",
        "unicode": "",
        "source_platform": 1,
        "formula_id": "",
        "check_flag": 1,
        "team_id": "",
        "request_id": "",
        "combo_info": {"text_templates": []},
        "sub_type": 0,
        "radius": {"top_left": 0.0, "top_right": 0.0,
                   "bottom_left": 0.0, "bottom_right": 0.0},
        "global_alpha": 1.0,
        "background_color": "",
        "background_alpha": 1.0,
        "border_line_style": 0,
        "border_width": 0.0,
        "border_color": "",
        "has_shadow": False,
        "shadow_color": "",
        "shadow_alpha": 0.8,
        "shadow_smoothing": 0.0,
        "shadow_distance": 0.0,
        "shadow_point": {"x": 0.0, "y": 0.0},
        "shadow_angle": 0.0,
        "shape_param": {"shape_type": 0, "roundness": [],
                        "custom_points": [], "shape_size": []},
        "original_size": [],
        "update_params": "",
        "aigc_type": "none",
        "sequence_type": False,
        "cycle_setting": True,
        "shape_fill_render_style": {
            "color": {
                "solid": {"color": "#FFFFFF", "alpha": 1.0},
                "gradient": {"color": [], "alpha": [], "percent": [],
                             "angle": 90.0, "mode": "all", "style": "linear"},
                "texture": {"path": "", "flip": [], "scale": 1.0, "alpha": 1.0,
                            "angle": 90.0, "blend": "no", "range": 4,
                            "fill": "tile", "resource_id": "", "effect_id": "",
                            "play_speed": 1.0},
                "render_type": "solid",
            },
            "alpha": 1.0,
        },
        "shape_fill_use_flower_color": False,
        "multi_language_current": "none",
        "corner_pin": None,
    }


def make_sticker_segment(material_id: str, duration: int) -> dict:
    """Segment sticker phủ [0, duration], vị trí/tỉ lệ theo project mẫu."""
    return {
        "id": _uid(),
        "source_timerange": None,
        "target_timerange": {"start": 0, "duration": int(duration)},
        "render_timerange": {"start": 0, "duration": 0},
        "desc": "", "state": 0, "speed": 1.0,
        "is_loop": False, "is_tone_modify": False, "reverse": False,
        "intensifies_audio": False, "cartoon": False,
        "volume": 1.0, "last_nonzero_volume": 1.0,
        "clip": {
            "scale": {"x": STICKER_SCALE, "y": STICKER_SCALE},
            "rotation": 0.0,
            "transform": {"x": STICKER_POS_X, "y": STICKER_POS_Y},
            "flip": {"vertical": False, "horizontal": False},
            "alpha": 1.0,
        },
        "uniform_scale": {"on": True, "value": 1.0},
        "material_id": material_id,
        "extra_material_refs": [],
        "render_index": STICKER_RENDER_INDEX,
        "keyframe_refs": [],
        "enable_lut": False, "enable_adjust": False, "enable_hsl": False,
        "visible": True, "group_id": "",
        "enable_color_curves": True, "enable_hsl_curves": True,
        "track_render_index": 2,
        "hdr_settings": None, "enable_color_wheels": True,
        "track_attribute": 0, "is_placeholder": False,
        "template_id": "", "enable_smart_color_adjust": False,
        "template_scene": "default", "common_keyframes": [],
        "caption_info": None,
        "responsive_layout": {"enable": False, "target_follow": "",
                              "size_layout": 0, "horizontal_pos_layout": 0,
                              "vertical_pos_layout": 0},
        "enable_color_match_adjust": False,
        "enable_color_correct_adjust": False,
        "enable_adjust_mask": False,
        "raw_segment_id": "",
        "lyric_keyframes": None,
        "enable_video_mask": True,
        "digital_human_template_group_id": "",
        "color_correct_alg_result": "",
        "source": "segmentsourcenormal",
        "enable_mask_stroke": False,
        "enable_mask_shadow": False,
        "enable_color_adjust_pro": False,
        "segment_color_tag": "",
    }


# ── Áp lên materials/segment ───────────────────────────────────────────

def apply_film_effect(M: dict, segments: list) -> int:
    """Áp "Khung phim 1" lên từng segment (mỗi segment 1 material riêng)."""
    n = 0
    for seg in segments:
        mat = make_film_effect()
        M.setdefault("video_effects", []).append(mat)
        seg.setdefault("extra_material_refs", []).append(mat["id"])
        n += 1
    return n


def apply_film_mask(M: dict, seg: dict) -> None:
    """Áp mask "Cuộn phim" lên 1 segment (kèm đủ 4 cờ mask như project mẫu)."""
    mat = make_film_mask()
    M.setdefault("common_mask", []).append(mat)
    seg.setdefault("extra_material_refs", []).append(mat["id"])
    seg["enable_video_mask"] = True
    seg["enable_adjust_mask"] = False
    seg["enable_mask_stroke"] = False
    seg["enable_mask_shadow"] = False


def add_sticker_track(M: dict, duration: int) -> dict:
    """Tạo material + track sticker Subscribe phủ toàn project."""
    mat = make_sticker_material()
    M.setdefault("stickers", []).append(mat)
    seg = make_sticker_segment(mat["id"], duration)
    return {"id": _uid(), "type": "sticker", "segments": [seg],
            "flag": 0, "attribute": 0, "name": "", "is_default_name": True}
