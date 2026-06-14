"""Ani-Trans-Story — áp animation-in + transition theo đúng bộ của dự án video007.

Pool animation/transition + duration chuẩn được trích trực tiếp từ project video007
(style "story"). Cơ chế áp giống tab Animation / Transitions gốc: mỗi segment random
1 animation-in, mỗi gap random 1 transition; dùng đúng duration chuẩn của từng hiệu ứng.

Không đụng tới audio track / timeranges → sync giữ nguyên.
"""

import os
import uuid
import random
from dataclasses import dataclass

from core import capcut


# ── Pool trích từ video007 ────────────────────────────────────────────
# (name, resource_id, category_id, category_name, duration_us)
STORY_ANIMATIONS = [
    ("Cross Open", "7283445469601075714", "2037708273", "Trending-1", 1100000),
    ("Blur In", "7507508671341956368", "2037708273", "Trending-1", 1000000),
    ("Fade In", "6798320778182922760", "2037708273", "Trending-1", 500000),
    ("Retro Fade-in 2", "7473710409103446545", "2037708273", "Trending-1", 1000000),
    ("Gray Mask", "7473710409040531985", "2037708273", "Trending-1", 1530000),
    ("Sunset Flare", "7548721694081305917", "2037708273", "Trending-1", 1000000),
    ("Color Flow", "7573619569198157064", "2037708273", "Trending-1", 2000000),
    ("Slide Up", "6798333487523828238", "2037708273", "Trending-1", 1000000),
    ("Blur Glitche", "7541337955554610485", "2037708273", "Trending-1", 1200000),
    ("Folding Fan", "7345806151440667137", "2037708273", "Trending-1", 1060000),
    ("Slide & Flip", "7584254937391992117", "2037708279", "Masking-1", 2000000),
    ("Photo Zoom", "7642562410045558034", "2037708279", "Masking-1", 2000000),
    ("Memory Sticker", "7621032969070791943", "2037708279", "Masking-1", 2000000),
    ("Polaroid Spread", "7639298165572717825", "2037708280", "3D Simulation-1", 2000000),
    ("Retro Cyberspace", "7548705331811994941", "2037708280", "3D Simulation-1", 2000000),
    ("Handycam Zoom", "7582194473329904901", "2037708280", "3D Simulation-1", 2000000),
    ("Stick Slideshow-Out", "7618633397702905106", "2037708280", "3D Simulation-1", 2000000),
    ("Image Stack", "7632163110157061393", "2037708280", "3D Simulation-1", 1200000),
    ("Fast Orbit", "7637180534128676116", "2037708280", "3D Simulation-1", 2000000),
    ("Zoom Out", "6798332584276267527", "2037708275", "Basic-1", 700000),
    ("Grain Appears", "7524088817683352849", "2037708275", "Basic-1", 1880000),
    ("Side Rotate", "7584010485788462389", "2037708275", "Basic-1", 1970000),
]

# (name, effect_id, category_id, category_name, duration_us)
STORY_TRANSITIONS = [
    ("Dynamic Album", "7600341643127999751", "25835", "Trending", 1933333),
    ("Open Square", "7606633530843467016", "25835", "Trending", 2000000),
    ("Next Photo", "7600994015391108360", "25835", "Trending", 2000000),
    ("Diamond Surface", "7594852548213837064", "25835", "Trending", 2000000),
    ("Slice Reveal", "7451535589569991185", "25835", "Trending", 2000000),
    ("Wipers", "7451535589381247489", "25835", "Trending", 1466666),
    ("Scotch Tape", "7439647271064441361", "25835", "Trending", 1000000),
    ("Torn Buzz", "7635806719691558164", "25835", "Trending", 2000000),
    ("Laser Split", "7612025965828427015", "25835", "Trending", 2000000),
    ("Lumin Flash", "7342515863662105090", "25835", "Trending", 800000),
    ("Red Dazzle", "7626850679847521554", "25835", "Trending", 2000000),
    ("Carve & Unfold", "7539904073747680565", "25835", "Trending", 2000000),
    ("Flash Pull", "7631458404007054613", "25835", "Trending", 2000000),
    ("Punch Hole", "7594864445583609093", "25835", "Trending", 1066666),
    ("Jagged Arrow", "7623254145520209159", "25835", "Trending", 2000000),
    ("Blurry Tablet", "7591338435999173895", "25835", "Trending", 2000000),
]


@dataclass
class StoryResult:
    success: bool
    message: str
    anim_applied: int = 0
    trans_applied: int = 0


def _uid() -> str:
    return str(uuid.uuid4()).upper()


def _find_effect_path(resource_id: str) -> str:
    """Tìm path file effect trong CapCut cache (nếu đã tải)."""
    cache_base = os.path.join(
        os.environ.get("LOCALAPPDATA", ""), "CapCut", "User Data", "Cache", "effect"
    )
    effect_dir = os.path.join(cache_base, resource_id)
    if os.path.isdir(effect_dir):
        for f in os.listdir(effect_dir):
            if not f.endswith("_tmp"):
                return os.path.join(effect_dir, f)
    return ""


def _make_animation_material(anim: tuple, duration: int) -> dict:
    name, rid, cat_id, cat_name, _ = anim
    return {
        "id": _uid(),
        "type": "sticker_animation",
        "animations": [{
            "id": rid,
            "type": "in",
            "start": 0,
            "duration": duration,
            "path": _find_effect_path(rid),
            "platform": "all",
            "resource_id": rid,
            "third_resource_id": rid,
            "source_platform": 1,
            "name": name,
            "category_id": cat_id,
            "category_name": cat_name,
            "panel": "video",
            "material_type": "video",
            "anim_adjust_params": None,
            "request_id": "",
        }],
        "multi_language_current": "none",
    }


def _make_transition_material(trans: tuple, duration: int) -> dict:
    name, eid, cat_id, cat_name, _ = trans
    return {
        "id": _uid(),
        "type": "transition",
        "name": name,
        "effect_id": eid,
        "resource_id": eid,
        "third_resource_id": "0",
        "source_platform": 1,
        "path": _find_effect_path(eid),
        "duration": duration,
        "is_overlap": True,
        "platform": "all",
        "category_id": cat_id,
        "category_name": cat_name,
        "request_id": "",
        "is_ai_transition": False,
        "video_path": "",
        "task_id": "",
    }


def apply_ani_trans_story(draft_path: str, anim_rids=None, trans_eids=None,
                          anim_interval: int = 1, trans_interval: int = 1,
                          seed: int | None = None) -> StoryResult:
    """Áp animation-in + transition (chọn từ pool video007) lên video tracks.

    - anim_rids: list resource_id animation được chọn (rỗng/None = không áp animation).
    - trans_eids: list effect_id transition được chọn (rỗng/None = không áp transition).
    - anim_interval: cứ N segment áp animation 1 lần (1 = mọi segment).
    - trans_interval: cứ N gap áp transition 1 lần (1 = mọi gap).
    - Mỗi lần áp random 1 cái trong pool đã chọn, duration chuẩn của chính nó.
    - Replace ref cũ + prune orphan. Audio/timeline giữ nguyên.
    """
    anim_set = set(anim_rids or [])
    trans_set = set(trans_eids or [])
    anim_pool = [a for a in STORY_ANIMATIONS if a[1] in anim_set]
    trans_pool = [t for t in STORY_TRANSITIONS if t[1] in trans_set]

    if not anim_pool and not trans_pool:
        return StoryResult(False, "Chưa chọn animation hoặc transition nào")

    try:
        data = capcut.load_draft_content(draft_path)
    except Exception as e:
        return StoryResult(False, f"Không đọc được draft: {e}")

    video_tracks = capcut.find_video_tracks(data)
    if not video_tracks:
        return StoryResult(False, "Không có video track nào có segment")

    rng = random.Random(seed)
    materials = data.setdefault("materials", {})
    mat_anims = materials.setdefault("material_animations", [])
    mat_trans = materials.setdefault("transitions", [])

    anim_applied = 0
    trans_applied = 0

    # ── Animation-in ──────────────────────────────────────────────
    if anim_pool:
        ai = max(1, anim_interval)
        anim_ids = {ma["id"] for ma in mat_anims}
        for vt in video_tracks:
            for idx, seg in enumerate(vt["segments"]):
                if idx % ai != 0:
                    continue
                seg_dur = seg["target_timerange"]["duration"]
                anim = rng.choice(anim_pool)
                dur = min(anim[4], seg_dur)
                mat = _make_animation_material(anim, dur)
                mat_anims.append(mat)
                refs = [r for r in seg.get("extra_material_refs", []) if r not in anim_ids]
                refs.append(mat["id"])
                seg["extra_material_refs"] = refs
                anim_ids.add(mat["id"])
                anim_applied += 1

    # ── Transition (giữa các segment) ─────────────────────────────
    if trans_pool:
        ti = max(1, trans_interval)
        trans_ids = {t["id"] for t in mat_trans}
        for vt in video_tracks:
            segs = vt["segments"]
            for i in range(1, len(segs)):
                gap_idx = i - 1
                if gap_idx % ti != 0:
                    continue
                prev_dur = segs[i - 1]["target_timerange"]["duration"]
                cur_dur = segs[i]["target_timerange"]["duration"]
                trans = rng.choice(trans_pool)
                # Cap an toàn: transition overlap không vượt nửa segment ngắn hơn
                safe_cap = max(1, min(prev_dur, cur_dur) // 2)
                dur = min(trans[4], safe_cap)
                mat = _make_transition_material(trans, dur)
                mat_trans.append(mat)
                seg = segs[i]
                refs = [r for r in seg.get("extra_material_refs", []) if r not in trans_ids]
                refs.append(mat["id"])
                seg["extra_material_refs"] = refs
                trans_ids.add(mat["id"])
                trans_applied += 1

    # Prune material orphan (animation/transition không còn segment nào ref tới)
    # → chạy lại nhiều lần không phình file.
    referenced = set()
    for t in data.get("tracks", []):
        for s in t.get("segments", []):
            referenced.update(s.get("extra_material_refs", []))
    materials["material_animations"] = [m for m in mat_anims if m["id"] in referenced]
    materials["transitions"] = [m for m in mat_trans if m["id"] in referenced]

    try:
        capcut.save_draft_content(draft_path, data)
    except Exception as e:
        return StoryResult(False, f"Lỗi ghi draft: {e}")

    parts = []
    if anim_pool:
        parts.append(f"{anim_applied} animation")
    if trans_pool:
        parts.append(f"{trans_applied} transition")
    return StoryResult(True, "Áp " + " + ".join(parts), anim_applied, trans_applied)
