"""Cache dùng chung cho scan library CapCut (animation / transition / effect).

VẤN ĐỀ: mỗi library tự mở SQLite cache (~vài trăm MB) của CapCut và json.loads
lại toàn bộ row → 3 lần quét TRÙNG lúc khởi động, chạy trên 3 thread tranh GIL
làm app đơ vài giây.

GIẢI PHÁP:
  1. QUÉT 1 LẦN: đọc mỗi rp.db một lần, json.loads mỗi row một lần, trích cả 3
     nhóm (animation/transition/effect) trong cùng vòng lặp.
  2. CACHE ĐĨA: lưu kết quả kèm vân tay (size+mtime của các rp.db). Lần mở sau
     nếu DB không đổi → load JSON nhỏ (~ms), bỏ qua parse toàn bộ DB.
  3. MEMO RAM + Lock: 3 thread tab gọi đồng thời chỉ quét thật 1 lần.

Trả về dict raw (list các dict thuần) để mỗi library tự dựng dataclass của mình.
"""

import json
import os
import sqlite3
import threading

from core.settings import get_app_data_dir


# category_id → loại animation (theo CapCut API)
CATEGORY_TYPE_MAP = {
    "6824": "In",
    "6825": "Out",
    "6826": "Combo",
}
_NAME_TYPE_MAP = {"in": "In", "out": "Out", "combo": "Combo"}

_LOCK = threading.Lock()
_MEM: dict[str, dict] = {}   # fingerprint -> {"animation":[...], "transition":[...], "effect":[...]}


def _cache_dir(capcut_path: str) -> str:
    return os.path.join(capcut_path, "User Data", "Cache", "ressdk_db")


def _db_files(capcut_path: str) -> list[str]:
    cd = _cache_dir(capcut_path)
    out = []
    if os.path.isdir(cd):
        for d in sorted(os.listdir(cd)):
            p = os.path.join(cd, d, "rp.db")
            if os.path.isfile(p):
                out.append(p)
    return out


def _fingerprint(capcut_path: str) -> str:
    """Vân tay các rp.db (path:size:mtime). Đổi khi CapCut cập nhật cache."""
    parts = []
    for p in _db_files(capcut_path):
        try:
            st = os.stat(p)
            parts.append(f"{p}:{st.st_size}:{int(st.st_mtime)}")
        except OSError:
            pass
    return "|".join(parts)


def _cache_file() -> str:
    return os.path.join(get_app_data_dir(), "library_scan_cache.json")


def _load_disk(fingerprint: str) -> dict | None:
    if not fingerprint:
        return None
    try:
        with open(_cache_file(), "r", encoding="utf-8") as f:
            d = json.load(f)
        if d.get("fingerprint") == fingerprint:
            data = d.get("data")
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return None


def _save_disk(fingerprint: str, data: dict) -> None:
    if not fingerprint:
        return
    try:
        with open(_cache_file(), "w", encoding="utf-8") as f:
            json.dump({"fingerprint": fingerprint, "data": data}, f,
                      ensure_ascii=False)
    except Exception:
        pass


def get_raw(capcut_path: str, force: bool = False) -> dict:
    """Trả về {"animation":[dict...], "transition":[...], "effect":[...]}.

    force=True → bỏ qua cache (RAM + đĩa), quét lại thật.
    """
    fp = _fingerprint(capcut_path)

    if not force:
        hit = _MEM.get(fp)
        if hit is not None:
            return hit

    with _LOCK:
        if not force:
            hit = _MEM.get(fp)
            if hit is not None:
                return hit
            data = _load_disk(fp)
            if data is not None:
                _MEM[fp] = data
                return data

        data = _scan_all(capcut_path)
        _save_disk(fp, data)
        _MEM[fp] = data
        return data


def _scan_all(capcut_path: str) -> dict:
    """Quét 1 lần toàn bộ rp.db, phân loại thành 3 nhóm."""
    anim: dict[str, dict] = {}
    trans: dict[str, dict] = {}
    eff: dict[str, dict] = {}

    for db_path in _db_files(capcut_path):
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT response_body FROM http_cache")
            rows = cur.fetchall()
            conn.close()
        except Exception:
            continue

        for (body,) in rows:
            try:
                text = (body.decode("utf-8", errors="ignore")
                        if isinstance(body, bytes) else str(body))
                if "effect_item_list" not in text:
                    continue
                data = json.loads(text)
            except Exception:
                continue
            _classify(data, anim, trans, eff)

    return {
        "animation": list(anim.values()),
        "transition": list(trans.values()),
        "effect": list(eff.values()),
    }


def _classify(data: dict, anim: dict, trans: dict, eff: dict) -> None:
    """Phân loại 1 response body đã parse vào 3 nhóm (giữ nguyên logic từng library)."""
    d = data.get("data", {})
    categories = d.get("categories", [])
    cat_resources = d.get("category_resources", {})

    for cat in categories:
        cat_id = str(cat.get("category_id", ""))
        cat_name = cat.get("category_name", "")

        anim_type = CATEGORY_TYPE_MAP.get(cat_id, "")
        if not anim_type:
            anim_type = _NAME_TYPE_MAP.get(cat_name.lower(), "")

        effects = cat_resources.get(cat_id, {}).get("effect_item_list", [])
        for e in effects:
            common = e.get("common_attr", {})
            title = common.get("title", "")
            rid = str(common.get("effect_id", ""))
            if not title or not rid:
                continue
            etype = common.get("effect_type")

            # Transition: effect_type == 19 (bất kể category)
            if etype == 19 and rid not in trans:
                trans[rid] = {"name": title, "resource_id": rid,
                              "category": cat_name, "category_id": cat_id}

            # Effect: effect_type == 7 (bất kể category)
            if etype == 7 and rid not in eff:
                eff[rid] = {"name": title, "resource_id": rid,
                            "category": cat_name, "category_id": cat_id}

            # Animation: theo category In/Out/Combo (bất kể effect_type)
            if anim_type and rid not in anim:
                default_dur = 500000
                sdk_extra = common.get("sdk_extra", "")
                if sdk_extra:
                    try:
                        sd = (json.loads(sdk_extra)
                              if isinstance(sdk_extra, str) else sdk_extra)
                        ad = sd.get("setting", {}).get("animation_duration")
                        if ad is not None:
                            default_dur = int(float(ad) * 1_000_000)
                    except Exception:
                        pass
                anim[rid] = {"name": title, "resource_id": rid,
                             "category": anim_type, "category_id": cat_id,
                             "effect_type": etype if etype is not None else 13,
                             "default_duration": default_dur}
