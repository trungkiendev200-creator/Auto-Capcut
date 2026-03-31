"""Transition Engine — áp dụng/xóa transitions giữa segments trong CapCut project."""

import os
import shutil
import uuid
import random
from dataclasses import dataclass, field

from core import capcut
from core.transition_library import TransitionInfo


@dataclass
class TransitionConfig:
    transitions: list[TransitionInfo] = field(default_factory=list)
    duration_seconds: float = 0.8
    interval: int = 0  # 0=tất cả, N=cứ N vị trí giữa 1 lần


@dataclass
class TransitionResult:
    success: bool
    message: str
    applied_count: int = 0


def _uid() -> str:
    return str(uuid.uuid4()).upper()


def _make_transition_material(trans: TransitionInfo, duration: int) -> dict:
    """Tạo 1 transition material entry."""
    cache_base = os.path.join(
        os.environ.get("LOCALAPPDATA", ""), "CapCut", "User Data", "Cache", "effect"
    )
    effect_path = ""
    effect_dir = os.path.join(cache_base, trans.resource_id)
    if os.path.isdir(effect_dir):
        for f in os.listdir(effect_dir):
            if not f.endswith("_tmp"):
                effect_path = os.path.join(effect_dir, f)
                break

    return {
        "id": _uid(),
        "type": "transition",
        "name": trans.name,
        "effect_id": trans.resource_id,
        "resource_id": trans.resource_id,
        "third_resource_id": trans.resource_id,
        "source_platform": 1,
        "path": effect_path,
        "duration": duration,
        "is_overlap": True,
        "platform": "all",
        "category_id": trans.category_id,
        "category_name": trans.category,
        "request_id": "",
        "is_ai_transition": False,
        "video_path": "",
        "task_id": "",
    }


def apply_transitions(draft_path: str, config: TransitionConfig,
                       backup: bool = True) -> TransitionResult:
    """
    Áp transitions random giữa các segments.
    Transition nằm trong extra_material_refs của segment phía sau.
    """
    json_path = os.path.join(draft_path, "draft_content.json")
    if not os.path.isfile(json_path):
        return TransitionResult(False, "draft_content.json not found")

    if not config.transitions:
        return TransitionResult(False, "No transitions selected")

    if backup:
        shutil.copy2(json_path, json_path + ".bak")

    data = capcut.load_draft_content(draft_path)
    video_tracks = capcut.find_video_tracks(data)

    if not video_tracks:
        return TransitionResult(False, "No video track with segments found")

    mat_transitions = data.setdefault("materials", {}).setdefault("transitions", [])
    # Collect existing transition IDs for cleanup
    existing_trans_ids = {t["id"] for t in mat_transitions}

    duration = int(config.duration_seconds * 1_000_000)
    total_applied = 0

    for vt in video_tracks:
        segments = vt["segments"]
        gap_idx = 0  # Đếm vị trí giữa (bắt đầu từ 0)
        for seg_idx, seg in enumerate(segments):
            if seg_idx == 0:
                continue

            # Khoảng cách: 0=tất cả, N=cứ N vị trí 1 lần
            if config.interval > 0 and gap_idx % config.interval != 0:
                gap_idx += 1
                continue
            gap_idx += 1

            # Random chọn 1 transition
            trans = random.choice(config.transitions)

            # Tạo transition material
            mat = _make_transition_material(trans, duration)
            mat_transitions.append(mat)

            # Xóa transition ref cũ và thêm mới
            refs = seg.get("extra_material_refs", [])
            refs = [r for r in refs if r not in existing_trans_ids]
            refs.append(mat["id"])
            seg["extra_material_refs"] = refs

            # Cập nhật existing_trans_ids
            existing_trans_ids.add(mat["id"])
            total_applied += 1

    capcut.save_draft_content(draft_path, data)

    names = ", ".join(t.name for t in config.transitions[:3])
    if len(config.transitions) > 3:
        names += f"... +{len(config.transitions) - 3}"
    msg = f"Applied {total_applied} transitions ({names})"
    return TransitionResult(True, msg, total_applied)


def clear_transitions(draft_path: str, backup: bool = True) -> TransitionResult:
    """Xóa tất cả transitions khỏi project."""
    json_path = os.path.join(draft_path, "draft_content.json")
    if not os.path.isfile(json_path):
        return TransitionResult(False, "draft_content.json not found")

    if backup:
        shutil.copy2(json_path, json_path + ".bak")

    data = capcut.load_draft_content(draft_path)
    video_tracks = capcut.find_video_tracks(data)

    mat_transitions = data.get("materials", {}).get("transitions", [])
    trans_ids = {t["id"] for t in mat_transitions}

    cleared = 0
    for vt in video_tracks:
        for seg in vt["segments"]:
            refs = seg.get("extra_material_refs", [])
            new_refs = [r for r in refs if r not in trans_ids]
            if len(new_refs) != len(refs):
                seg["extra_material_refs"] = new_refs
                cleared += 1

    # Clear transitions list
    data["materials"]["transitions"] = []

    capcut.save_draft_content(draft_path, data)
    return TransitionResult(True, f"Cleared {cleared} transitions", cleared)
