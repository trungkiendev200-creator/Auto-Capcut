"""Animation Engine — áp dụng/xóa animation cho segments trong CapCut project."""

import os
import shutil
import uuid
from dataclasses import dataclass, field

from core import capcut
from core.animation_library import AnimationInfo


@dataclass
class AnimationConfig:
    animations: list[AnimationInfo] = field(default_factory=list)
    anim_type: str = "in"       # "in", "out" — combo sẽ tạo cả in+out
    duration_seconds: float = 0  # 0=default(0.5s), 9999=full segment time
    interval: int = 1            # Cứ N segment animation 1 lần
    multi_per_frame: bool = False # True=chèn nhiều animation 1 frame, False=xen kẽ


@dataclass
class AnimationResult:
    success: bool
    message: str
    applied_count: int = 0


def _uid() -> str:
    return str(uuid.uuid4()).upper()


def _make_animation_entry(anim: AnimationInfo, anim_type: str,
                           duration: int, start: int) -> dict:
    """Tạo 1 animation entry trong material_animation.animations[]."""
    cache_base = os.path.join(
        os.environ.get("LOCALAPPDATA", ""), "CapCut", "User Data", "Cache", "effect"
    )
    # Tìm path trong cache (nếu có)
    effect_dir = os.path.join(cache_base, anim.resource_id)
    effect_path = ""
    if os.path.isdir(effect_dir):
        for f in os.listdir(effect_dir):
            if not f.endswith("_tmp"):
                effect_path = os.path.join(effect_dir, f)
                break

    return {
        "id": anim.resource_id,
        "type": anim_type,
        "start": start,
        "duration": duration,
        "path": effect_path,
        "platform": "all",
        "resource_id": anim.resource_id,
        "third_resource_id": anim.resource_id,
        "source_platform": 1,
        "name": anim.name,
        "category_id": anim.category_id,
        "category_name": "",
        "panel": "video",
        "material_type": "video",
        "anim_adjust_params": None,
        "request_id": "",
    }


def _calc_duration(config: AnimationConfig, seg_duration: int,
                    anim: AnimationInfo) -> int:
    """Tính duration animation (microseconds). time=0 dùng default của animation."""
    if config.duration_seconds == 9999:
        return seg_duration
    elif config.duration_seconds == 0:
        return min(anim.default_duration, seg_duration)
    else:
        return min(int(config.duration_seconds * 1_000_000), seg_duration)


def _build_material_animation(anims_to_apply: list[AnimationInfo],
                                config: AnimationConfig,
                                seg_duration: int) -> dict:
    """Tạo 1 material_animation object cho 1 segment."""
    animations = []

    for anim in anims_to_apply:
        dur = _calc_duration(config, seg_duration, anim)

        if anim.category == "Combo":
            animations.append(_make_animation_entry(anim, "in", dur, 0))
            out_start = max(0, seg_duration - dur)
            animations.append(_make_animation_entry(anim, "out", dur, out_start))
        elif config.anim_type == "out" or anim.category == "Out":
            out_start = max(0, seg_duration - dur)
            animations.append(_make_animation_entry(anim, "out", dur, out_start))
        else:
            animations.append(_make_animation_entry(anim, "in", dur, 0))

    return {
        "id": _uid(),
        "type": "sticker_animation",
        "animations": animations,
        "multi_language_current": "none",
    }


def apply_animations(draft_path: str, config: AnimationConfig,
                      backup: bool = True) -> AnimationResult:
    """
    Áp dụng animation cho segments trong video tracks.

    - interval=1: tất cả, N: cứ N segment 1 lần
    - multi_per_frame=False: xen kẽ giữa animations
    - multi_per_frame=True: tất cả animations cho mỗi segment
    """
    json_path = os.path.join(draft_path, "draft_content.json")
    if not os.path.isfile(json_path):
        return AnimationResult(False, "draft_content.json not found")

    if not config.animations:
        return AnimationResult(False, "No animations selected")

    if backup:
        shutil.copy2(json_path, json_path + ".bak")

    data = capcut.load_draft_content(draft_path)
    video_tracks = capcut.find_video_tracks(data)

    if not video_tracks:
        return AnimationResult(False, "No video track with segments found")

    mat_anims = data.setdefault("materials", {}).setdefault("material_animations", [])

    total_applied = 0
    anim_count = len(config.animations)
    anim_idx = 0

    for vt in video_tracks:
        for seg_idx, seg in enumerate(vt["segments"]):
            # interval=0: tất cả. interval=3: file 0,3,6,9... (cứ 3 file 1 lần)
            if config.interval > 0 and seg_idx % config.interval != 0:
                continue

            seg_dur = seg["target_timerange"]["duration"]

            # Chọn animation(s) cho segment này
            if config.multi_per_frame:
                anims_to_apply = config.animations  # Tất cả
            else:
                anims_to_apply = [config.animations[anim_idx % anim_count]]
                anim_idx += 1

            # Tạo material_animation
            mat_anim = _build_material_animation(anims_to_apply, config, seg_dur)
            mat_anims.append(mat_anim)

            # Xóa ref animation cũ (nếu có) và thêm ref mới
            _replace_animation_ref(seg, mat_anims, mat_anim["id"])
            total_applied += 1

    capcut.save_draft_content(draft_path, data)

    names = ", ".join(a.name for a in config.animations[:3])
    if len(config.animations) > 3:
        names += f"... +{len(config.animations)-3}"
    msg = f"Applied {total_applied} animations ({names})"
    return AnimationResult(True, msg, total_applied)


def _replace_animation_ref(seg: dict, all_mat_anims: list, new_id: str):
    """Xóa animation ref cũ trong extra_material_refs, thêm ref mới."""
    mat_anim_ids = {ma["id"] for ma in all_mat_anims}
    refs = seg.get("extra_material_refs", [])

    # Xóa ref cũ đến material_animations
    refs = [r for r in refs if r not in mat_anim_ids or r == new_id]

    # Thêm ref mới nếu chưa có
    if new_id not in refs:
        refs.append(new_id)

    seg["extra_material_refs"] = refs


def clear_animations(draft_path: str, backup: bool = True) -> AnimationResult:
    """Xóa tất cả animation khỏi video segments."""
    json_path = os.path.join(draft_path, "draft_content.json")
    if not os.path.isfile(json_path):
        return AnimationResult(False, "draft_content.json not found")

    if backup:
        shutil.copy2(json_path, json_path + ".bak")

    data = capcut.load_draft_content(draft_path)
    video_tracks = capcut.find_video_tracks(data)

    # Collect IDs of all material_animations
    mat_anims = data.get("materials", {}).get("material_animations", [])
    mat_anim_ids = {ma["id"] for ma in mat_anims}

    cleared = 0
    for vt in video_tracks:
        for seg in vt["segments"]:
            refs = seg.get("extra_material_refs", [])
            new_refs = [r for r in refs if r not in mat_anim_ids]
            if len(new_refs) != len(refs):
                seg["extra_material_refs"] = new_refs
                cleared += 1

    # Clear material_animations list — reset to empty animations
    for ma in mat_anims:
        ma["animations"] = []

    capcut.save_draft_content(draft_path, data)
    return AnimationResult(True, f"Cleared animations from {cleared} segments", cleared)
