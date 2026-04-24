"""Transition Library — quét danh sách transitions từ CapCut cache."""

import json
import os
import sqlite3
from dataclasses import dataclass


@dataclass
class TransitionInfo:
    name: str
    resource_id: str
    category: str
    category_id: str
    effect_type: int = 19  # CapCut transition type


def scan_library(capcut_path: str | None = None) -> list[TransitionInfo]:
    """Quét transition library. Fallback từ bundled JSON nếu cache trống."""
    if capcut_path is None:
        capcut_path = os.path.join(os.environ.get("LOCALAPPDATA", ""), "CapCut")

    all_trans: dict[str, TransitionInfo] = {}

    cache_dir = os.path.join(capcut_path, "User Data", "Cache", "ressdk_db")
    if os.path.isdir(cache_dir):
        for db_folder in os.listdir(cache_dir):
            db_path = os.path.join(cache_dir, db_folder, "rp.db")
            if os.path.isfile(db_path):
                _scan_db(db_path, all_trans)

    # Merge bundled JSON làm baseline: cache CapCut đã thêm trước, fallback
    # điền phần thiếu. Đảm bảo mọi máy đều thấy full library.
    from core.library_fallback import load_fallback
    for item in load_fallback("transitions"):
        rid = item.get("resource_id", "")
        if rid and rid not in all_trans:
            all_trans[rid] = TransitionInfo(
                name=item.get("name", ""),
                resource_id=rid,
                category=item.get("category", ""),
                category_id=item.get("category_id", ""),
            )

    result = list(all_trans.values())
    result.sort(key=lambda t: t.name)
    return result


def _scan_db(db_path: str, out: dict[str, TransitionInfo]):
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
            if "effect_item_list" not in text:
                continue
            data = json.loads(text)
        except Exception:
            continue

        cat_resources = data.get("data", {}).get("category_resources", {})
        categories = data.get("data", {}).get("categories", [])

        for cat in categories:
            cat_id = str(cat.get("category_id", ""))
            cat_name = cat.get("category_name", "")

            effects = cat_resources.get(cat_id, {}).get("effect_item_list", [])
            for eff in effects:
                common = eff.get("common_attr", {})
                if common.get("effect_type") != 19:
                    continue

                title = common.get("title", "")
                rid = str(common.get("effect_id", ""))

                if title and rid and rid not in out:
                    out[rid] = TransitionInfo(
                        name=title,
                        resource_id=rid,
                        category=cat_name,
                        category_id=cat_id,
                    )
