"""Text Template — lưu/áp dụng style caption (font, effect, animation, vị trí)
giữa các project, không đụng nội dung chữ / timing của từng caption."""

import os
import json
import copy
import shutil
import time
import uuid

from core import capcut, settings
from core.sync_sub_engine import find_all_text_tracks, SyncSubResult

_uid = lambda: str(uuid.uuid4()).upper()


def _resolve_text_material(data: dict, seg: dict) -> dict | None:
    """Tìm materials.texts thật của 1 caption segment.

    Bình thường segment.material_id trỏ THẲNG vào materials.texts. Nhưng nếu
    caption đã được áp 1 "Text Template" store của CapCut (vd project mẫu
    bodycam-video064), segment.material_id lại trỏ vào materials.text_templates,
    và phải đi tiếp qua text_info_resources[].text_material_id mới ra
    materials.texts thật.
    """
    mid = seg.get("material_id")
    texts_by_id = {m["id"]: m for m in data.get("materials", {}).get("texts", [])}
    if mid in texts_by_id:
        return texts_by_id[mid]

    tmpl_by_id = {m["id"]: m for m in data.get("materials", {}).get("text_templates", [])}
    tmpl = tmpl_by_id.get(mid)
    if tmpl:
        for info in tmpl.get("text_info_resources", []):
            real_id = info.get("text_material_id")
            if real_id in texts_by_id:
                return texts_by_id[real_id]
    return None

# Các field "style thuần" trên materials.texts — không phụ thuộc nội dung/
# timing của từng caption, an toàn để copy nguyên xi giữa các project.
_STYLE_FIELDS = [
    "text_color", "text_alpha", "font_name", "font_title", "font_size", "font_path",
    "font_id", "font_resource_id", "initial_scale", "font_url", "typesetting",
    "alignment", "line_feed", "use_effect_default_color", "is_rich_text",
    "shape_clip_x", "shape_clip_y", "ktv_color", "bold_width", "italic_degree",
    "underline", "underline_width", "underline_offset", "sub_type",
    "font_category_name", "font_source_platform", "font_third_resource_id",
    "font_category_id", "letter_spacing", "line_spacing",
    "has_shadow", "shadow_color", "shadow_alpha", "shadow_smoothing",
    "shadow_distance", "shadow_point", "shadow_angle",
    "shadow_thickness_projection_enable", "shadow_thickness_projection_angle",
    "shadow_thickness_projection_distance",
    "border_alpha", "border_color", "border_width", "border_mode", "style_name",
    "fonts", "background_color", "background_alpha", "background_style",
    "background_round_radius", "background_width", "background_height",
    "background_vertical_offset", "background_horizontal_offset", "background_fill",
    "single_char_bg_enable", "single_char_bg_color", "single_char_bg_alpha",
    "single_char_bg_round_radius", "single_char_bg_width", "single_char_bg_height",
    "single_char_bg_vertical_offset", "single_char_bg_horizontal_offset",
    "font_team_id", "force_apply_line_max_width", "line_max_width",
    "oneline_cutoff", "cutoff_postfix", "subtitle_template_original_fontsize",
    "inner_padding", "is_lyric_effect", "lyrics_template",
    "global_alpha", "layer_weight", "check_flag", "text_size",
]


# ── Registry (lưu trên đĩa, %APPDATA%\AutoCapCut\text_templates\) ──────

def _templates_dir() -> str:
    d = os.path.join(settings.get_app_data_dir(), "text_templates")
    os.makedirs(d, exist_ok=True)
    return d


def list_templates() -> list[dict]:
    """Danh sách nhẹ (không kèm style payload) để hiển thị UI."""
    d = _templates_dir()
    out = []
    for f in os.listdir(d):
        if not f.endswith(".json"):
            continue
        try:
            with open(os.path.join(d, f), "r", encoding="utf-8") as fh:
                data = json.load(fh)
            out.append({
                "id": data.get("id", f[:-5]),
                "name": data.get("name", f[:-5]),
                "source_project": data.get("source_project", ""),
                "created_at": data.get("created_at", ""),
            })
        except Exception:
            continue
    out.sort(key=lambda t: t.get("created_at", ""))
    return out


def get_template(template_id: str) -> dict | None:
    path = os.path.join(_templates_dir(), f"{template_id}.json")
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_template(name: str, source_project: str, style: dict) -> str:
    template_id = _uid()
    data = {
        "id": template_id,
        "name": name,
        "source_project": source_project,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "style": style,
    }
    path = os.path.join(_templates_dir(), f"{template_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return template_id


def delete_template(template_id: str) -> bool:
    path = os.path.join(_templates_dir(), f"{template_id}.json")
    if os.path.isfile(path):
        os.remove(path)
        return True
    return False


# ── Capture: trích style từ 1 project mẫu ──────────────────────────────

def capture_style_from_project(draft_path: str) -> dict:
    """Lấy caption ĐẦU TIÊN của project làm đại diện style (font/effect/
    animation/vị trí) — áp dụng cho những project mà mọi caption dùng
    chung 1 kiểu (trường hợp phổ biến khi áp text template có sẵn của CapCut).
    """
    data = capcut.load_draft_content(draft_path)
    text_tracks = find_all_text_tracks(data)
    if not text_tracks:
        raise ValueError("Project không có text track nào")

    seg = None
    for tt in text_tracks:
        segs = sorted(tt["segments"], key=lambda s: s["target_timerange"]["start"])
        if segs:
            seg = segs[0]
            break
    if seg is None:
        raise ValueError("Project không có caption nào")

    tmat = _resolve_text_material(data, seg)
    if not tmat:
        raise ValueError("Không tìm thấy text material cho caption đầu tiên")

    try:
        content = json.loads(tmat.get("content", "{}"))
    except json.JSONDecodeError:
        raise ValueError("content của caption đầu tiên không parse được")

    styles = content.get("styles") or []
    content_style = None
    if styles:
        content_style = copy.deepcopy(styles[0])
        content_style.pop("range", None)

    style_fields = {k: copy.deepcopy(tmat[k]) for k in _STYLE_FIELDS if k in tmat}

    refs = seg.get("extra_material_refs", [])
    anim_by_id = {m["id"]: m for m in data["materials"].get("material_animations", [])}
    fx_by_id = {m["id"]: m for m in data["materials"].get("effects", [])}

    effect_material = None
    animation_material = None
    for r in refs:
        if effect_material is None and r in fx_by_id and \
                fx_by_id[r].get("type") == "text_effect":
            effect_material = copy.deepcopy(fx_by_id[r])
            effect_material.pop("id", None)
        elif animation_material is None and r in anim_by_id:
            animation_material = copy.deepcopy(anim_by_id[r])
            animation_material.pop("id", None)

    return {
        "style_fields": style_fields,
        "content_style": content_style,
        "effect_material": effect_material,
        "animation_material": animation_material,
        "seg_clip": copy.deepcopy(seg.get("clip")),
        "seg_uniform_scale": copy.deepcopy(seg.get("uniform_scale")),
    }


# ── Apply: đưa style vào TẤT CẢ caption của project đích ───────────────

def preflight_apply_template(draft_path: str) -> list[str]:
    json_path = os.path.join(draft_path, "draft_content.json")
    if not os.path.isfile(json_path):
        return ["draft_content.json không tồn tại"]
    try:
        data = capcut.load_draft_content(draft_path)
    except Exception as e:
        return [f"Không đọc được draft: {e}"]
    if not find_all_text_tracks(data):
        return ["Project không có text track / caption nào"]
    return []


def apply_text_template(
    draft_path: str,
    style: dict,
    backup: bool = True,
    log_fn=None,
) -> SyncSubResult:
    """Áp style đã capture vào mọi caption của project — giữ nguyên nội dung
    chữ, timing, chỉ thay font/màu/effect/animation/vị trí hiển thị."""
    _log = log_fn or (lambda msg: None)

    json_path = os.path.join(draft_path, "draft_content.json")
    if not os.path.isfile(json_path):
        return SyncSubResult(False, "draft_content.json not found")

    data = capcut.load_draft_content(draft_path)
    text_tracks = find_all_text_tracks(data)
    if not text_tracks:
        return SyncSubResult(False, "Không tìm thấy text track nào")

    style_fields = style.get("style_fields") or {}
    content_style = style.get("content_style")
    effect_tpl = style.get("effect_material")
    anim_tpl = style.get("animation_material")
    seg_clip = style.get("seg_clip")
    seg_uniform_scale = style.get("seg_uniform_scale")

    total_segs = 0
    applied = 0

    for tt in text_tracks:
        for seg in tt["segments"]:
            total_segs += 1
            tmat = _resolve_text_material(data, seg)
            if not tmat:
                _log(f"  ⚠ segment {seg.get('id','?')[:8]}: không tìm thấy text material")
                continue

            try:
                content = json.loads(tmat.get("content", "{}"))
            except json.JSONDecodeError:
                _log(f"  ⚠ segment {seg.get('id','?')[:8]}: content không parse được, bỏ qua")
                continue

            text = content.get("text", "")

            if content_style is not None:
                new_style = copy.deepcopy(content_style)
                new_style["range"] = [0, len(text)]
                content["styles"] = [new_style]
                tmat["content"] = json.dumps(content, ensure_ascii=False)

            for k, v in style_fields.items():
                tmat[k] = copy.deepcopy(v)

            new_refs = []
            if anim_tpl is not None:
                new_anim = copy.deepcopy(anim_tpl)
                new_anim["id"] = _uid()
                dur = seg["target_timerange"]["duration"]
                for a in new_anim.get("animations", []):
                    a["start"] = 0
                    a["duration"] = dur
                data["materials"].setdefault("material_animations", []).append(new_anim)
                new_refs.append(new_anim["id"])
            if effect_tpl is not None:
                new_fx = copy.deepcopy(effect_tpl)
                new_fx["id"] = _uid()
                data["materials"].setdefault("effects", []).append(new_fx)
                new_refs.append(new_fx["id"])
            if new_refs:
                seg["extra_material_refs"] = new_refs

            if seg_clip is not None:
                seg["clip"] = copy.deepcopy(seg_clip)
            if seg_uniform_scale is not None:
                seg["uniform_scale"] = copy.deepcopy(seg_uniform_scale)

            applied += 1

    if applied == 0:
        return SyncSubResult(False, "Không có caption nào để áp dụng template")

    if backup:
        bak_path = json_path + ".bak"
        if not os.path.isfile(bak_path):
            shutil.copy2(json_path, bak_path)
            _log("  backup created")
        else:
            _log("  backup exists, skipping")

    capcut.save_draft_content(draft_path, data)
    _log(f"  saved OK ({applied}/{total_segs} caption)")

    return SyncSubResult(
        True,
        f"Đã áp dụng template cho {applied}/{total_segs} caption",
        sub_count=applied,
    )
