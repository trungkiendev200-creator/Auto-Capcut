"""Split Picture — cắt 1 segment ảnh dài thành nhiều đoạn ngắn liên tiếp.

Mục đích: ảnh tĩnh chiếu lâu rất chán. Cắt 1 ảnh (cùng 1 file) thành N đoạn
ngắn → mỗi đoạn có thể gắn animation/hiệu ứng khác nhau ở tab Animation.

Chỉ tác động video track (segment loại photo). Audio track giữ nguyên hoàn toàn
→ tổng duration project không đổi → sync ảnh/audio không vỡ.
"""

import os
import copy
import math
import uuid
import random
from dataclasses import dataclass

from core import capcut


@dataclass
class SplitResult:
    success: bool
    message: str
    images_split: int = 0      # số ảnh gốc đã bị cắt
    segments_created: int = 0  # tổng số đoạn mới sinh ra (không tính giữ nguyên)


def _uid() -> str:
    return str(uuid.uuid4()).upper()


def _build_id_map(materials: dict) -> dict:
    """id material -> (list_key, material_dict)."""
    idmap = {}
    for key, lst in materials.items():
        if isinstance(lst, list):
            for m in lst:
                if isinstance(m, dict) and "id" in m:
                    idmap[m["id"]] = (key, m)
    return idmap


def _plan_durations(D: int, x_us: int, y_us: int, rng: random.Random) -> list[int] | None:
    """Chia D (microseconds) thành ≥2 đoạn, mỗi đoạn ~∈ [x_us, y_us], tổng = D.

    - Nếu D chia khít được vào [x,y] (tồn tại n: n*x ≤ D ≤ n*y): mỗi đoạn ngẫu
      nhiên trong [x,y] (ưu tiên).
    - Nếu D rơi vào "khoảng chết" (xảy ra khi y < 2x): vẫn cắt thành n đoạn gần
      đều (n = round(D / trung_bình)), pieces lệch [x,y] tối thiểu — tốt hơn nhiều
      so với để nguyên 1 ảnh dài.
    - Trả về None chỉ khi D < 2x (không đủ chỗ cho 2 đoạn).
    """
    if D <= 0 or x_us <= 0 or y_us < x_us:
        return None
    if D < 2 * x_us:
        return None  # không đủ để tách thành ≥2 đoạn

    mid = (x_us + y_us) / 2.0
    n_lo = math.ceil(D / y_us)    # ít đoạn nhất (mỗi đoạn ≤ y)
    n_hi = math.floor(D / x_us)   # nhiều đoạn nhất (mỗi đoạn ≥ x)

    if n_lo <= n_hi:
        # Tile khít được vào [x,y] → phân phối ngẫu nhiên trong [x,y]
        n = max(2, n_lo)
        n = min(n_hi, max(n, round(D / mid)))
        if n < 2:
            return None  # D nằm trong (x, 2x): chỉ đủ 1 đoạn hợp lệ

        pieces = [x_us] * n
        remaining = D - x_us * n          # >= 0
        cap = y_us - x_us
        order = list(range(n))
        rng.shuffle(order)
        for i in order:                   # rải dư ngẫu nhiên
            if remaining <= 0:
                break
            give = rng.randint(0, min(cap, remaining))
            pieces[i] += give
            remaining -= give
        i = 0
        while remaining > 0:              # nhồi nốt phần dư (tổng = D)
            idx = order[i % n]
            room = y_us - pieces[idx]
            if room > 0:
                add = min(room, remaining)
                pieces[idx] += add
                remaining -= add
            i += 1
        return pieces

    # Khoảng chết: chia n đoạn gần đều, lệch [x,y] tối thiểu
    n = max(2, round(D / mid))
    base = D // n
    rem = D - base * n
    pieces = [base + (1 if i < rem else 0) for i in range(n)]
    rng.shuffle(pieces)
    return pieces


def _split_segment(orig: dict, materials: dict, idmap: dict,
                   durations: list[int], mirror: bool = False) -> list[dict]:
    """Tạo list segment mới từ 1 segment ảnh gốc theo các durations cho trước.

    - Giữ nguyên material_id (cùng file ảnh).
    - Nhân bản toàn bộ extra_material_refs (speed/canvas/sound_channel/...) cho
      từng đoạn — đúng cách CapCut tự làm khi split thủ công.
    - target_timerange ghép nối tiếp bắt đầu từ start của segment gốc.
    - mirror=True: lật ngang (Mirror) xen kẽ ~50% số đoạn (đoạn lẻ 1,3,5...) →
      2 đoạn liền kề luôn khác nhau.
    """
    start = orig["target_timerange"]["start"]
    new_segments = []
    cur = start

    for i, dur in enumerate(durations):
        seg = copy.deepcopy(orig)
        seg["id"] = _uid()
        seg["target_timerange"] = {"start": cur, "duration": dur}
        # Ảnh: source không ràng buộc frame thật → đặt khớp duration cho gọn
        seg["source_timerange"] = {"start": 0, "duration": dur}

        # Mirror xen kẽ: lật ngang các đoạn ở vị trí lẻ
        if mirror and i % 2 == 1:
            clip = seg.setdefault("clip", {})
            flip = clip.setdefault("flip", {"vertical": False, "horizontal": False})
            flip["horizontal"] = not flip.get("horizontal", False)

        # Nhân bản từng extra material ref
        new_refs = []
        for ref_id in orig.get("extra_material_refs", []):
            entry = idmap.get(ref_id)
            if entry is None:
                new_refs.append(ref_id)  # không tìm thấy → giữ nguyên
                continue
            list_key, mat = entry
            dup = copy.deepcopy(mat)
            dup["id"] = _uid()
            materials.setdefault(list_key, []).append(dup)
            idmap[dup["id"]] = (list_key, dup)
            new_refs.append(dup["id"])
        seg["extra_material_refs"] = new_refs

        new_segments.append(seg)
        cur += dur

    return new_segments


def split_pictures(draft_path: str, a_sec: float, x_sec: float, y_sec: float,
                   mirror: bool = False, seed: int | None = None) -> SplitResult:
    """Cắt mọi ảnh có duration > a thành các đoạn ∈ [x; y] giây.

    Args:
        draft_path: thư mục project CapCut.
        a_sec: ngưỡng (giây) — chỉ cắt ảnh dài hơn a.
        x_sec, y_sec: khoảng độ dài mỗi đoạn (giây), 0 < x <= y.
        mirror: True = lật ngang (Mirror) xen kẽ ~50% số đoạn trong mỗi ảnh cắt ra.
        seed: seed random (None = ngẫu nhiên thật).
    """
    if not (a_sec > 0 and x_sec > 0 and y_sec >= x_sec):
        return SplitResult(False, "Tham số không hợp lệ (cần a>0, 0<x<=y)")

    a_us = int(a_sec * 1_000_000)
    x_us = int(x_sec * 1_000_000)
    y_us = int(y_sec * 1_000_000)

    try:
        data = capcut.load_draft_content(draft_path)
    except Exception as e:
        return SplitResult(False, f"Không đọc được draft: {e}")

    materials = data.setdefault("materials", {})
    idmap = _build_id_map(materials)
    rng = random.Random(seed)

    images_split = 0
    segments_created = 0

    for track in data.get("tracks", []):
        if track.get("type") != "video":
            continue
        segs = track.get("segments", [])
        if not segs:
            continue

        new_track_segs = []
        for seg in segs:
            mat_entry = idmap.get(seg.get("material_id"))
            is_photo = bool(mat_entry) and mat_entry[1].get("type") == "photo"
            D = seg["target_timerange"]["duration"]

            if not is_photo or D <= a_us:
                new_track_segs.append(seg)
                continue

            durations = _plan_durations(D, x_us, y_us, rng)
            if durations is None or len(durations) < 2:
                new_track_segs.append(seg)  # không cắt được hợp lệ → giữ nguyên
                continue

            pieces = _split_segment(seg, materials, idmap, durations, mirror=mirror)
            new_track_segs.extend(pieces)
            images_split += 1
            segments_created += len(pieces)

        track["segments"] = new_track_segs

    if images_split == 0:
        return SplitResult(True, "Không có ảnh nào cần cắt (đều ≤ a hoặc không tile được)",
                           0, 0)

    try:
        capcut.save_draft_content(draft_path, data)
    except Exception as e:
        return SplitResult(False, f"Lỗi ghi draft: {e}")

    msg = f"Cắt {images_split} ảnh → {segments_created} đoạn"
    return SplitResult(True, msg, images_split, segments_created)
