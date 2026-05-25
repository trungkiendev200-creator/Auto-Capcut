"""Handle Stock engine — các chức năng xử lý stock video.

Hiện có:
- shuffle_stock: hoán đổi nội dung (material + source + clip + speed) của N% segments
  trong main video track. target_timerange giữ nguyên → duration không đổi.
"""

import os
import copy
import uuid
import random
from dataclasses import dataclass

from core import capcut


def _uid() -> str:
    return str(uuid.uuid4()).upper()


def parse_vitri_text(text: str) -> list[tuple[int, str]]:
    """Parse 'STT: TEXT' mỗi dòng. Trả về list (stt, text)."""
    result: list[tuple[int, str]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if ":" not in line:
            continue
        idx_str, txt = line.split(":", 1)
        try:
            stt = int(idx_str.strip())
        except ValueError:
            continue
        result.append((stt, txt.strip()))
    return result


def _audio_end_us(data: dict) -> int:
    end = 0
    for t in data.get("tracks", []):
        if t.get("type") != "audio":
            continue
        for s in t.get("segments", []):
            ts = s["target_timerange"]
            e = ts["start"] + ts["duration"]
            if e > end:
                end = e
    return end


@dataclass
class StockResult:
    success: bool
    message: str
    shuffled: int = 0
    total: int = 0


def _find_main_video_track(data: dict) -> dict | None:
    photo_ids = {
        v["id"] for v in data.get("materials", {}).get("videos", [])
        if v.get("type") == "photo"
    }
    for t in data.get("tracks", []):
        if t.get("type") != "video":
            continue
        segs = t.get("segments", [])
        if not segs:
            continue
        if photo_ids and all(s.get("material_id") in photo_ids for s in segs):
            continue
        return t
    return None


def shuffle_stock(draft_path: str, shuffle_pct: float, log_fn=None) -> StockResult:
    """Shuffle nội dung của shuffle_pct% segments trong main video track.

    Hoán đổi material_id + source_timerange + clip + speed giữa các slot được chọn.
    target_timerange (vị trí + duration trên timeline) giữ nguyên.
    """
    def log(msg):
        if log_fn:
            log_fn(msg)

    if not os.path.isdir(draft_path):
        return StockResult(False, f"Draft not found: {draft_path}")

    try:
        data = capcut.load_draft_content(draft_path)
    except Exception as e:
        return StockResult(False, f"Cannot load draft: {e}")

    main_track = _find_main_video_track(data)
    if not main_track:
        return StockResult(False, "Không tìm thấy main video track")

    segs = sorted(main_track["segments"], key=lambda s: s["target_timerange"]["start"])
    n = len(segs)
    if n < 2:
        return StockResult(True, f"Skip: chỉ có {n} segment", total=n)

    n_shuffle = int(round(n * shuffle_pct / 100.0))
    if n_shuffle < 2:
        return StockResult(True, f"Skip: shuffle_pct quá thấp ({n_shuffle}/{n})", total=n)

    indices = sorted(random.sample(range(n), n_shuffle))

    snapshot = [{
        "material_id": segs[i]["material_id"],
        "source_timerange": copy.deepcopy(segs[i]["source_timerange"]),
        "clip": copy.deepcopy(segs[i].get("clip")),
        "speed": segs[i].get("speed", 1.0),
    } for i in indices]

    random.shuffle(snapshot)

    for j, i in enumerate(indices):
        segs[i]["material_id"] = snapshot[j]["material_id"]
        segs[i]["source_timerange"] = snapshot[j]["source_timerange"]
        if snapshot[j]["clip"] is not None:
            segs[i]["clip"] = snapshot[j]["clip"]
        segs[i]["speed"] = snapshot[j]["speed"]

    log(f"  Shuffled {n_shuffle}/{n} segments ({shuffle_pct:.0f}%)")

    try:
        capcut.save_draft_content(draft_path, data)
    except Exception as e:
        return StockResult(False, f"Save failed: {e}")

    return StockResult(
        True,
        f"OK: shuffled {n_shuffle}/{n} segments",
        shuffled=n_shuffle, total=n,
    )


@dataclass
class SyncAudioResult:
    success: bool
    message: str
    action: str = ""  # "trim" | "extend" | "skip"
    delta_us: int = 0  # signed: video_end - audio_end


def sync_to_audio(draft_path: str, log_fn=None) -> SyncAudioResult:
    """Đồng bộ main video track với audio:

    - video_end > audio_end → CẮT: xóa các segment có start >= audio_end,
      trim segment đang chứa audio_end.
    - video_end < audio_end → COPY: clone random segments append vào cuối
      tới khi đạt audio_end; segment cuối có thể được trim.
    """
    def log(msg):
        if log_fn:
            log_fn(msg)

    if not os.path.isdir(draft_path):
        return SyncAudioResult(False, f"Draft not found: {draft_path}")

    try:
        data = capcut.load_draft_content(draft_path)
    except Exception as e:
        return SyncAudioResult(False, f"Cannot load draft: {e}")

    main_track = _find_main_video_track(data)
    if not main_track:
        return SyncAudioResult(False, "Không tìm thấy main video track")

    audio_end = _audio_end_us(data)
    if audio_end <= 0:
        return SyncAudioResult(False, "Không tìm thấy audio track (hoặc audio rỗng)")

    segs = sorted(main_track["segments"], key=lambda s: s["target_timerange"]["start"])
    if not segs:
        return SyncAudioResult(False, "Main video track không có segment")

    video_end = segs[-1]["target_timerange"]["start"] + segs[-1]["target_timerange"]["duration"]
    delta = video_end - audio_end

    log(f"  video_end={video_end/1e6:.2f}s | audio_end={audio_end/1e6:.2f}s | delta={delta/1e6:+.2f}s")

    if abs(delta) < 1000:  # < 1ms
        return SyncAudioResult(True, "Đã đồng bộ rồi (delta < 1ms)", action="skip",
                                delta_us=delta)

    if delta > 0:
        # CASE 1: Video > Audio → cắt
        new_segs = []
        removed = 0
        trimmed = False
        for s in segs:
            ts = s["target_timerange"]["start"]
            td = s["target_timerange"]["duration"]
            te = ts + td
            if ts >= audio_end:
                removed += 1
                continue
            if te > audio_end:
                # Trim segment này đến audio_end
                new_td = audio_end - ts
                if new_td <= 0:
                    removed += 1
                    continue
                ratio = new_td / td
                old_src_dur = s["source_timerange"]["duration"]
                new_src_dur = max(1, int(old_src_dur * ratio))
                s["target_timerange"] = {"start": ts, "duration": new_td}
                s["source_timerange"]["duration"] = new_src_dur
                trimmed = True
                new_segs.append(s)
            else:
                new_segs.append(s)
        main_track["segments"] = new_segs
        data["duration"] = audio_end
        msg = (f"CẮT: video {video_end/1e6:.1f}s → {audio_end/1e6:.1f}s "
               f"(xóa {removed} seg, trim seg cuối: {trimmed})")
        action = "trim"

    else:
        # CASE 2: Audio > Video → copy random vào cuối
        deficit = audio_end - video_end
        cur = video_end
        n_copied = 0
        max_iter = 10000
        # Pool để random: dùng các segs gốc (không phải segs đã append)
        pool = list(segs)
        while cur < audio_end and max_iter > 0:
            max_iter -= 1
            ref = random.choice(pool)
            new_seg = copy.deepcopy(ref)
            new_seg["id"] = _uid()
            ref_dur = ref["target_timerange"]["duration"]
            remaining = audio_end - cur
            if ref_dur > remaining:
                # Trim
                ratio = remaining / ref_dur
                old_src_dur = ref["source_timerange"]["duration"]
                new_src_dur = max(1, int(old_src_dur * ratio))
                new_seg["target_timerange"] = {"start": cur, "duration": remaining}
                new_seg["source_timerange"] = {
                    "start": ref["source_timerange"]["start"],
                    "duration": new_src_dur,
                }
                main_track["segments"].append(new_seg)
                cur = audio_end
                n_copied += 1
            else:
                new_seg["target_timerange"] = {"start": cur, "duration": ref_dur}
                # source giữ nguyên (đã deepcopy)
                main_track["segments"].append(new_seg)
                cur += ref_dur
                n_copied += 1
        data["duration"] = audio_end
        msg = (f"COPY: audio {audio_end/1e6:.1f}s > video {video_end/1e6:.1f}s, "
               f"thêm {n_copied} seg (+{deficit/1e6:.1f}s)")
        action = "extend"

    log(f"  {msg}")

    try:
        capcut.save_draft_content(draft_path, data)
    except Exception as e:
        return SyncAudioResult(False, f"Save failed: {e}")

    return SyncAudioResult(True, msg, action=action, delta_us=delta)


@dataclass
class HandleTextResult:
    success: bool
    message: str
    added: int = 0


def handle_text(draft_path: str, vitri_text: str, log_fn=None) -> HandleTextResult:
    """Tạo text track MỚI với các text từ vitri-text.txt, mapping STT theo text
    track gốc trong project.

    Mỗi dòng `STT: TEXT` → tạo 1 text segment:
      - content text = TEXT mới
      - target_timerange = target của sub STT trong track text gốc
      - style = clone từ text material gốc

    Fail nếu STT vượt range subs.
    """
    import json as _json

    def log(msg):
        if log_fn:
            log_fn(msg)

    if not os.path.isdir(draft_path):
        return HandleTextResult(False, f"Draft not found: {draft_path}")

    entries = parse_vitri_text(vitri_text)
    if not entries:
        return HandleTextResult(False, "vitri-text.txt rỗng hoặc không parse được")

    try:
        data = capcut.load_draft_content(draft_path)
    except Exception as e:
        return HandleTextResult(False, f"Cannot load draft: {e}")

    # Tìm text track gốc (track text đầu tiên có segments)
    text_track = None
    for t in data.get("tracks", []):
        if t.get("type") == "text" and t.get("segments"):
            text_track = t
            break
    if not text_track:
        return HandleTextResult(False, "Không tìm thấy text track trong project")

    text_segs = sorted(text_track["segments"], key=lambda s: s["target_timerange"]["start"])
    n_subs = len(text_segs)
    log(f"  Text track gốc: {n_subs} subs | vitri-text: {len(entries)} entries")

    # Map text materials
    text_mats_map = {m["id"]: m for m in data.get("materials", {}).get("texts", [])}

    # Validate STT trước
    for stt, _ in entries:
        if not (1 <= stt <= n_subs):
            return HandleTextResult(False, f"STT {stt} ngoài range (1..{n_subs})")

    # Build new materials + segments
    new_mats = []
    new_segs = []
    for stt, new_text in entries:
        ref_seg = text_segs[stt - 1]
        ref_mat = text_mats_map.get(ref_seg.get("material_id"))
        if not ref_mat:
            return HandleTextResult(False, f"STT {stt}: không tìm thấy text material")

        # Clone material → replace content text + range
        new_mat = copy.deepcopy(ref_mat)
        new_mat["id"] = _uid()
        try:
            content = _json.loads(ref_mat.get("content", "{}"))
        except Exception:
            content = {"styles": [], "text": ""}
        content["text"] = new_text
        if content.get("styles"):
            content["styles"][0]["range"] = [0, len(new_text)]
            content["styles"] = content["styles"][:1]
        new_mat["content"] = _json.dumps(content, ensure_ascii=False)
        new_mats.append(new_mat)

        # Clone segment, replace material_id (target giữ nguyên = ref_seg target)
        new_seg = copy.deepcopy(ref_seg)
        new_seg["id"] = _uid()
        new_seg["material_id"] = new_mat["id"]
        new_seg["target_timerange"] = copy.deepcopy(ref_seg["target_timerange"])
        new_segs.append(new_seg)

    # Append materials
    data.setdefault("materials", {}).setdefault("texts", []).extend(new_mats)

    # Create new text track
    new_track = {
        "id": _uid(),
        "type": "text",
        "segments": new_segs,
        "flag": 0,
        "attribute": 0,
        "name": "",
        "is_default_name": True,
    }
    data.setdefault("tracks", []).append(new_track)

    try:
        capcut.save_draft_content(draft_path, data)
    except Exception as e:
        return HandleTextResult(False, f"Save failed: {e}")

    return HandleTextResult(
        True,
        f"OK: tạo track text mới với {len(new_segs)} segments",
        added=len(new_segs),
    )
