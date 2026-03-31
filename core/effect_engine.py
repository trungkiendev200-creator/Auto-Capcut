"""Effect Engine — áp dụng/xóa video effects cho segments trong CapCut project."""

import os
import shutil
import uuid
import random
from dataclasses import dataclass, field

from core import capcut
from core.effect_library import EffectInfo


@dataclass
class EffectConfig:
    effects: list[EffectInfo] = field(default_factory=list)
    value: float = 1.0  # Intensity 0.0-1.0 (100% = 1.0)
    interval: int = 0   # 0=tất cả, N=cứ N segment 1 lần


@dataclass
class EffectResult:
    success: bool
    message: str
    applied_count: int = 0


def _uid() -> str:
    return str(uuid.uuid4()).upper()


def _make_effect_material(eff: EffectInfo, value: float) -> dict:
    cache_base = os.path.join(
        os.environ.get("LOCALAPPDATA", ""), "CapCut", "User Data", "Cache", "effect"
    )
    effect_path = ""
    effect_dir = os.path.join(cache_base, eff.resource_id)
    if os.path.isdir(effect_dir):
        for f in os.listdir(effect_dir):
            if not f.endswith("_tmp"):
                effect_path = os.path.join(effect_dir, f)
                break

    return {
        "id": _uid(),
        "effect_id": eff.resource_id,
        "resource_id": eff.resource_id,
        "name": eff.name,
        "type": "video_effect",
        "sub_type": 0,
        "bind_segment_id": "",
        "transparent_params": "",
        "path": effect_path,
        "value": value,
        "category_id": eff.category_id,
        "category_name": eff.category,
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
    }


def apply_effects(draft_path: str, config: EffectConfig,
                   backup: bool = True) -> EffectResult:
    """
    Áp video effects random cho segments.
    Effect bind qua extra_material_refs + materials.video_effects.
    """
    json_path = os.path.join(draft_path, "draft_content.json")
    if not os.path.isfile(json_path):
        return EffectResult(False, "draft_content.json not found")

    if not config.effects:
        return EffectResult(False, "No effects selected")

    if backup:
        shutil.copy2(json_path, json_path + ".bak")

    data = capcut.load_draft_content(draft_path)
    video_tracks = capcut.find_video_tracks(data)

    if not video_tracks:
        return EffectResult(False, "No video track with segments found")

    mat_effects = data.setdefault("materials", {}).setdefault("video_effects", [])
    existing_ids = {e["id"] for e in mat_effects}

    total_applied = 0

    for vt in video_tracks:
        for seg_idx, seg in enumerate(vt["segments"]):
            # Interval check
            if config.interval > 0 and seg_idx % config.interval != 0:
                continue

            # Random chọn 1 effect
            eff = random.choice(config.effects)

            mat = _make_effect_material(eff, config.value)
            mat_effects.append(mat)

            # Xóa effect ref cũ, thêm mới
            refs = seg.get("extra_material_refs", [])
            refs = [r for r in refs if r not in existing_ids]
            refs.append(mat["id"])
            seg["extra_material_refs"] = refs

            existing_ids.add(mat["id"])
            total_applied += 1

    capcut.save_draft_content(draft_path, data)

    names = ", ".join(e.name for e in config.effects[:3])
    if len(config.effects) > 3:
        names += f"... +{len(config.effects) - 3}"
    msg = f"Applied {total_applied} effects ({names})"
    return EffectResult(True, msg, total_applied)


def clear_effects(draft_path: str, backup: bool = True) -> EffectResult:
    json_path = os.path.join(draft_path, "draft_content.json")
    if not os.path.isfile(json_path):
        return EffectResult(False, "draft_content.json not found")

    if backup:
        shutil.copy2(json_path, json_path + ".bak")

    data = capcut.load_draft_content(draft_path)
    video_tracks = capcut.find_video_tracks(data)

    mat_effects = data.get("materials", {}).get("video_effects", [])
    effect_ids = {e["id"] for e in mat_effects}

    cleared = 0
    for vt in video_tracks:
        for seg in vt["segments"]:
            refs = seg.get("extra_material_refs", [])
            new_refs = [r for r in refs if r not in effect_ids]
            if len(new_refs) != len(refs):
                seg["extra_material_refs"] = new_refs
                cleared += 1

    data["materials"]["video_effects"] = []
    capcut.save_draft_content(draft_path, data)
    return EffectResult(True, f"Cleared {cleared} effects", cleared)
