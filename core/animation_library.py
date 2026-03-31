"""Animation Library — quét danh sách animation từ CapCut cache."""

import json
import os
import sqlite3
from dataclasses import dataclass


@dataclass
class AnimationInfo:
    name: str
    resource_id: str
    category: str       # "In", "Out", "Combo"
    category_id: str
    effect_type: int = 13
    default_duration: int = 500000  # microseconds, 500000 = 0.5s fallback


# Category ID → type mapping (from CapCut API)
CATEGORY_TYPE_MAP = {
    "6824": "In",
    "6825": "Out",
    "6826": "Combo",
}


def scan_library(capcut_path: str | None = None) -> list[AnimationInfo]:
    """Quét animation library từ CapCut ressdk_db cache.

    Returns list of AnimationInfo sorted by category then name.
    """
    if capcut_path is None:
        capcut_path = os.path.join(os.environ.get("LOCALAPPDATA", ""), "CapCut")

    cache_dir = os.path.join(capcut_path, "User Data", "Cache", "ressdk_db")
    if not os.path.isdir(cache_dir):
        return []

    all_anims: dict[str, AnimationInfo] = {}  # resource_id → info (dedup)

    for db_folder in os.listdir(cache_dir):
        db_path = os.path.join(cache_dir, db_folder, "rp.db")
        if not os.path.isfile(db_path):
            continue
        _scan_db(db_path, all_anims)

    result = list(all_anims.values())
    # Sort: In first, then Out, then Combo, then by name
    order = {"In": 0, "Out": 1, "Combo": 2}
    result.sort(key=lambda a: (order.get(a.category, 9), a.name))
    return result


def _scan_db(db_path: str, out: dict[str, AnimationInfo]):
    """Scan 1 database file for animation panel data."""
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT response_body FROM http_cache")
        rows = cur.fetchall()
        conn.close()
    except Exception:
        return

    for (body,) in rows:
        try:
            text = body.decode("utf-8", errors="ignore") if isinstance(body, bytes) else str(body)
            # Quick check: skip if no animation-related content
            if "effect_item_list" not in text:
                continue
            data = json.loads(text)
        except Exception:
            continue

        categories = data.get("data", {}).get("categories", [])
        cat_resources = data.get("data", {}).get("category_resources", {})

        for cat in categories:
            cat_id = str(cat.get("category_id", ""))
            cat_name = cat.get("category_name", "")

            # Determine animation type from known IDs or name
            anim_type = CATEGORY_TYPE_MAP.get(cat_id, "")
            if not anim_type:
                name_lower = cat_name.lower()
                if name_lower == "in":
                    anim_type = "In"
                elif name_lower == "out":
                    anim_type = "Out"
                elif name_lower == "combo":
                    anim_type = "Combo"
                else:
                    continue  # Not an animation category

            effects = cat_resources.get(cat_id, {}).get("effect_item_list", [])
            for eff in effects:
                common = eff.get("common_attr", {})
                title = common.get("title", "")
                rid = str(common.get("effect_id", ""))
                etype = common.get("effect_type", 13)

                # Đọc default duration từ sdk_extra.setting.animation_duration
                default_dur = 500000  # fallback 0.5s
                sdk_extra = common.get("sdk_extra", "")
                if sdk_extra:
                    try:
                        sdk_data = json.loads(sdk_extra) if isinstance(sdk_extra, str) else sdk_extra
                        anim_dur = sdk_data.get("setting", {}).get("animation_duration")
                        if anim_dur is not None:
                            default_dur = int(float(anim_dur) * 1_000_000)
                    except Exception:
                        pass

                if title and rid and rid not in out:
                    out[rid] = AnimationInfo(
                        name=title,
                        resource_id=rid,
                        category=anim_type,
                        category_id=cat_id,
                        effect_type=etype,
                        default_duration=default_dur,
                    )
