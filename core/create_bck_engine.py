"""Create BCK — tạo project CapCut từ source edit (anh/audio/video intro/video edit).

Flow:
    1. Import audio nối tiếp → audio track (bảng tra số N → start/dur).
    2. Chèn video intro (mapping theo số tên file, neo đầu audio):
         - insert_over_audio=True  → ĐÈ: track overlay riêng, audio không đổi.
         - insert_over_audio=False → ĐẨY: chèn trước audio N, đẩy audio sau sang phải.
    3. Đắp video edit + ảnh đồng bộ đúng [start_N, dur_N] của audio (mapping theo số).
       - video edit dài hơn audio → CẮT; ngắn hơn → CHỈNH SPEED chậm cho khít.
    4. Đoạn audio có số KHÔNG khớp với bất kỳ thư mục nào trong source edit
       (không ảnh, không video edit, không intro) → ĐỂ TRỐNG trên track video.

Quy ước:
    - Mapping intro/ảnh/video edit ↔ audio theo SỐ trong tên file (26.* ↔ 26.mp3).
    - Intro giữ tiếng gốc; video edit bị tắt tiếng (narration phát bên dưới).
    - video intro / video edit có thể rỗng → bỏ qua.
"""

import os
import re
import struct
from dataclasses import dataclass, field

from core import capcut
from core import create_project as cp


# ── MP4 duration reader (thường + fragmented), microseconds ────────────

def _iter_atoms(f, pos, end):
    while pos < end:
        f.seek(pos)
        hdr = f.read(8)
        if len(hdr) < 8:
            break
        size, typ = struct.unpack(">I4s", hdr)
        h = 8
        if size == 1:
            size = struct.unpack(">Q", f.read(8))[0]
            h = 16
        elif size == 0:
            size = end - pos
        if size < 8:
            break
        yield typ, pos + h, pos + size
        pos += size


def _find_atom(f, pos, end, want):
    for t, s, e in _iter_atoms(f, pos, end):
        if t == want:
            return (s, e)
    return None


def mp4_duration_us(path: str) -> int | None:
    """Duration (microseconds) cho MP4 thường lẫn fragmented. None nếu fail."""
    try:
        with open(path, "rb") as f:
            end = os.path.getsize(path)
            moov = _find_atom(f, 0, end, b"moov")
            if not moov:
                return None
            # movie timescale từ mvhd
            mv_ts = 0
            mvhd = _find_atom(f, *moov, b"mvhd")
            if mvhd:
                f.seek(mvhd[0]); ver = f.read(1)[0]; f.read(3)
                if ver == 1:
                    f.read(16); mv_ts = struct.unpack(">I", f.read(4))[0]
                else:
                    f.read(8); mv_ts = struct.unpack(">I", f.read(4))[0]
            # tìm track video (hdlr == 'vide') → timescale + duration (mdhd)
            vid_tid = None
            vid_ts = 0
            best = 0.0
            for t, s, e in _iter_atoms(f, *moov):
                if t != b"trak":
                    continue
                tkhd = _find_atom(f, s, e, b"tkhd")
                tid = 0
                if tkhd:
                    f.seek(tkhd[0]); ver = f.read(1)[0]; f.read(3)
                    if ver == 1:
                        f.read(16); tid = struct.unpack(">I", f.read(4))[0]
                    else:
                        f.read(8); tid = struct.unpack(">I", f.read(4))[0]
                mdia = _find_atom(f, s, e, b"mdia")
                if not mdia:
                    continue
                hdlr = _find_atom(f, *mdia, b"hdlr")
                htype = b""
                if hdlr:
                    f.seek(hdlr[0]); f.read(8); htype = f.read(4)
                mdhd = _find_atom(f, *mdia, b"mdhd")
                ts = du = 0
                if mdhd:
                    f.seek(mdhd[0]); ver = f.read(1)[0]; f.read(3)
                    if ver == 1:
                        f.read(16); ts = struct.unpack(">I", f.read(4))[0]; du = struct.unpack(">Q", f.read(8))[0]
                    else:
                        f.read(8); ts = struct.unpack(">I", f.read(4))[0]; du = struct.unpack(">I", f.read(4))[0]
                if htype == b"vide":
                    vid_tid = tid
                    vid_ts = ts
                    if ts and du > 0:
                        best = du / ts
            if best > 0:
                return int(best * 1_000_000)
            # fragmented: cộng sample-duration của track video qua các moof
            ts = vid_ts or mv_ts
            if not ts or vid_tid is None:
                return None
            def_dur_global = 0
            mvex = _find_atom(f, *moov, b"mvex")
            if mvex:
                for t, s, e in _iter_atoms(f, *mvex):
                    if t != b"trex":
                        continue
                    f.seek(s); f.read(4); tid = struct.unpack(">I", f.read(4))[0]
                    f.read(4); dsd = struct.unpack(">I", f.read(4))[0]
                    if tid == vid_tid:
                        def_dur_global = dsd
            total = 0
            for t, s, e in _iter_atoms(f, 0, end):
                if t != b"moof":
                    continue
                for tt, ss, ee in _iter_atoms(f, s, e):
                    if tt != b"traf":
                        continue
                    tfhd = _find_atom(f, ss, ee, b"tfhd")
                    if not tfhd:
                        continue
                    f.seek(tfhd[0]); flags = struct.unpack(">I", f.read(4))[0] & 0xFFFFFF
                    tid = struct.unpack(">I", f.read(4))[0]
                    if tid != vid_tid:
                        continue
                    def_dur = def_dur_global
                    if flags & 0x000001: f.read(8)
                    if flags & 0x000002: f.read(4)
                    if flags & 0x000008:
                        def_dur = struct.unpack(">I", f.read(4))[0]
                    trun = _find_atom(f, ss, ee, b"trun")
                    if not trun:
                        continue
                    f.seek(trun[0]); tf = struct.unpack(">I", f.read(4))[0] & 0xFFFFFF
                    cnt = struct.unpack(">I", f.read(4))[0]
                    if tf & 0x000001: f.read(4)
                    if tf & 0x000004: f.read(4)
                    if tf & 0x000100:  # sample-duration present
                        for _ in range(cnt):
                            total += struct.unpack(">I", f.read(4))[0]
                            sk = 0
                            if tf & 0x000200: sk += 4
                            if tf & 0x000400: sk += 4
                            if tf & 0x000800: sk += 4
                            if sk: f.read(sk)
                    else:
                        total += def_dur * cnt
            return int(total / ts * 1_000_000) if total else None
    except Exception:
        return None


def _video_duration_us(path: str) -> int:
    """Duration video (us). Thử MP4 parser → mutagen → fallback 4s."""
    d = mp4_duration_us(path)
    if d and d > 0:
        return d
    try:
        from mutagen import File
        m = File(path)
        if m and m.info and m.info.length:
            return int(m.info.length * 1_000_000)
    except Exception:
        pass
    return 4_000_000


# ── Scan helpers ──────────────────────────────────────────────────────

def _num_of(filename: str) -> int | None:
    """Số nguyên đầu tiên trong tên file (bỏ extension). VD '26.mp4'→26."""
    stem = os.path.splitext(os.path.basename(filename))[0]
    m = re.search(r"\d+", stem)
    return int(m.group()) if m else None


def _list_files(folder: str, exts: set) -> list[str]:
    if not folder or not os.path.isdir(folder):
        return []
    out = []
    for f in sorted(os.listdir(folder), key=cp._natural_sort_key):
        if os.path.splitext(f)[1].lower() in exts and \
                os.path.isfile(os.path.join(folder, f)):
            out.append(os.path.join(folder, f).replace("\\", "/"))
    return out


def _find_subdir(parent: str, *names) -> str | None:
    """Tìm subfolder khớp tên (không phân biệt hoa thường)."""
    if not os.path.isdir(parent):
        return None
    low = {d.lower(): d for d in os.listdir(parent)
           if os.path.isdir(os.path.join(parent, d))}
    for n in names:
        if n.lower() in low:
            return os.path.join(parent, low[n.lower()])
    return None


# ── Segment factory (video, có hỗ trợ source offset + mute) ───────────

def _add_video_clip(M, path, file_dur_us, src_start, dur, target_start,
                    is_photo=False, mute=False, width=1920, height=1080):
    """Tạo material + segment cho 1 video/ảnh clip, thêm vào dict materials M.

    Trả về segment dict (chưa gắn track).
    """
    name = os.path.basename(path)
    info = {
        "type": "photo" if is_photo else "video",
        "width": width, "height": height,
        "duration": file_dur_us,
        "name": name,
        "has_audio": (not is_photo),
    }
    mat = cp._make_video_material(path, info)
    M["videos"].append(mat)
    speed = cp._make_speed_material(); M["speeds"].append(speed)
    cnv = cp._make_canvas_material(canvas_blur=False); M["canvases"].append(cnv)
    snd = cp._make_sound_channel(); M["sound_channel_mappings"].append(snd)

    seg = cp._make_video_segment(mat["id"], target_start, dur,
                                 speed["id"], cnv["id"], snd["id"])
    # source offset (cắt từ giữa file với stock dài / trim)
    seg["source_timerange"]["start"] = int(src_start)
    seg["source_timerange"]["duration"] = int(dur)
    if mute:
        seg["volume"] = 0.0
        seg["last_nonzero_volume"] = 1.0
    return seg


def _add_synced_video(M, path, file_dur, audio_dur, target_start, mute=True,
                      width=1920, height=1080):
    """Đặt video edit khít đúng [target_start, audio_dur].

    - file_dur >= audio_dur → CẮT (dùng audio_dur đầu, speed 1.0).
    - file_dur <  audio_dur → CHỈNH SPEED chậm lại để phủ kín audio_dur.
    """
    name = os.path.basename(path)
    info = {"type": "video", "width": width, "height": height,
            "duration": file_dur, "name": name, "has_audio": True}
    mat = cp._make_video_material(path, info); M["videos"].append(mat)
    speed_m = cp._make_speed_material()
    cnv = cp._make_canvas_material(canvas_blur=False)
    snd = cp._make_sound_channel()

    if file_dur >= audio_dur:
        src_dur, spd = audio_dur, 1.0          # cắt
    else:
        src_dur, spd = file_dur, file_dur / audio_dur  # stretch (slow)
    speed_m["speed"] = spd
    M["speeds"].append(speed_m)
    M["canvases"].append(cnv)
    M["sound_channel_mappings"].append(snd)

    seg = cp._make_video_segment(mat["id"], target_start, audio_dur,
                                 speed_m["id"], cnv["id"], snd["id"])
    seg["source_timerange"] = {"start": 0, "duration": int(src_dur)}
    seg["target_timerange"] = {"start": int(target_start), "duration": int(audio_dur)}
    seg["speed"] = spd
    if mute:
        seg["volume"] = 0.0
        seg["last_nonzero_volume"] = 1.0
    return seg


def _add_audio_clip(M, path, dur, target_start):
    name = os.path.basename(path)
    mat = cp._make_audio_material(path, dur); M["audios"].append(mat)
    speed = cp._make_speed_material(); M["speeds"].append(speed)
    snd = cp._make_sound_channel(); M["sound_channel_mappings"].append(snd)
    beat = cp._make_beat_material(); M["beats"].append(beat)
    return cp._make_audio_segment(mat["id"], target_start, dur,
                                  speed["id"], snd["id"], beat["id"])


# ── Result ────────────────────────────────────────────────────────────

@dataclass
class BckResult:
    success: bool = False
    message: str = ""
    project_path: str = ""
    n_audio: int = 0
    n_intro: int = 0
    n_image: int = 0
    n_video_edit: int = 0
    n_empty: int = 0
    total_duration_us: int = 0


# ── Main builder ──────────────────────────────────────────────────────

def build_bck_project(
    project_name: str,
    capcut_path: str,
    source_edit_dir: str,
    insert_over_audio: bool = True,
    ratio: str = "16:9",
    quality: str = "1080p",
    fps: int = 30,
    callback=None,
) -> BckResult:
    """Xem docstring module. insert_over_audio: True=ĐÈ, False=ĐẨY."""

    def log(m):
        if callback:
            callback(m)

    res = BckResult()

    # 1. Resolve subfolders
    anh_dir = _find_subdir(source_edit_dir, "anh", "image", "images", "pic")
    audio_dir = _find_subdir(source_edit_dir, "audio", "audios")
    intro_dir = _find_subdir(source_edit_dir, "video intro", "video_intro",
                             "intro", "videointro")
    vedit_dir = _find_subdir(source_edit_dir, "video edit", "video_edit",
                             "videoedit", "edit")
    if not audio_dir:
        return BckResult(False, "Không tìm thấy subfolder 'audio' trong source edit")

    audio_files = _list_files(audio_dir, cp.AUDIO_EXTS)
    if not audio_files:
        return BckResult(False, "Folder audio không có file nào")

    VID_EXTS = cp.VIDEO_EXTS | {".m4v", ".webm"}
    image_files = _list_files(anh_dir, cp.IMAGE_EXTS) if anh_dir else []
    intro_files = _list_files(intro_dir, VID_EXTS) if intro_dir else []
    vedit_files = _list_files(vedit_dir, VID_EXTS) if vedit_dir else []

    image_map = {n: p for p in image_files if (n := _num_of(p)) is not None}
    intro_map = {}
    for p in intro_files:
        n = _num_of(p)
        if n is not None:
            intro_map[n] = {"path": p, "dur": _video_duration_us(p)}
    vedit_map = {}
    for p in vedit_files:
        n = _num_of(p)
        if n is not None:
            vedit_map[n] = {"path": p, "dur": _video_duration_us(p)}

    log(f"audio={len(audio_files)} | intro={len(intro_map)} | anh={len(image_map)} | "
        f"video edit={len(vedit_map)}")

    # 2. Audio sequential (vị trí gốc)
    audios = []  # {num, path, dur, orig_start, start}
    t = 0
    for p in audio_files:
        d = cp._get_audio_duration(p)
        audios.append({"num": _num_of(p), "path": p, "dur": d, "orig_start": t})
        t += d

    # 3. Áp shift do intro (ĐẨY) + tính vị trí intro
    intro_placements = []  # {num, start, dur, path}
    acc = 0
    for a in audios:
        n = a["num"]
        if n in intro_map:
            idur = intro_map[n]["dur"]
            istart = a["orig_start"] + acc
            intro_placements.append({"num": n, "start": istart, "dur": idur,
                                     "path": intro_map[n]["path"]})
            if not insert_over_audio:  # ĐẨY: dịch audio này & sau nó
                acc += idur
        a["start"] = a["orig_start"] + acc

    total_duration = max((a["start"] + a["dur"] for a in audios), default=0)

    # 4. Materials skeleton
    M = cp._build_materials_dict([], [], [], [], [], [])

    main_segs = []     # track video chính
    overlay_segs = []  # track overlay (chỉ ĐÈ)
    audio_segs = []

    # 4a. Audio segments
    for a in audios:
        audio_segs.append(_add_audio_clip(M, a["path"], a["dur"], a["start"]))

    # 4b. Intro segments
    for ip in intro_placements:
        seg = _add_video_clip(M, ip["path"], ip["dur"], 0, ip["dur"], ip["start"],
                              is_photo=False, mute=False)
        if insert_over_audio:
            overlay_segs.append(seg)   # đè: track riêng phía trên
        else:
            main_segs.append(seg)      # đẩy: inline trên track chính

    # 4c. Video edit đồng bộ audio (cắt nếu dài / speed nếu ngắn) — ưu tiên
    n_vedit = 0
    for a in audios:
        n = a["num"]
        if n in vedit_map:
            seg = _add_synced_video(M, vedit_map[n]["path"], vedit_map[n]["dur"],
                                    a["dur"], a["start"], mute=True)
            main_segs.append(seg)
            n_vedit += 1

    # 4d. Ảnh đồng bộ audio (bỏ qua nếu số đó đã có video edit)
    n_image = 0
    for a in audios:
        n = a["num"]
        if n in image_map and n not in vedit_map:
            seg = _add_video_clip(M, image_map[n], a["dur"], 0, a["dur"], a["start"],
                                  is_photo=True, mute=False)
            main_segs.append(seg)
            n_image += 1

    # 5. Đoạn audio có số KHÔNG khớp thư mục nào (không ảnh, không video edit,
    #    và — với ĐÈ — không intro) → để TRỐNG trên track video (không đắp gì).
    #    Intro-ĐẨY chiếm slot riêng nên audio đó vẫn coi như chưa có hình.
    def _has_visual(a):
        n = a["num"]
        return (n in image_map) or (n in vedit_map) or \
               (insert_over_audio and n in intro_map)
    n_empty = sum(1 for a in audios if not _has_visual(a))

    # 7. Tracks (thứ tự: video chính → overlay → audio)
    main_segs.sort(key=lambda s: s["target_timerange"]["start"])
    tracks = [
        {"id": cp._uid(), "type": "video", "segments": main_segs, "flag": 0,
         "attribute": 0, "name": "", "is_default_name": True},
    ]
    if overlay_segs:
        overlay_segs.sort(key=lambda s: s["target_timerange"]["start"])
        for i, s in enumerate(overlay_segs):
            s["render_index"] = 100 + i  # render đè lên track chính
        tracks.append(
            {"id": cp._uid(), "type": "video", "segments": overlay_segs, "flag": 0,
             "attribute": 0, "name": "", "is_default_name": True})
    tracks.append(
        {"id": cp._uid(), "type": "audio", "segments": audio_segs, "flag": 0,
         "attribute": 0, "name": "", "is_default_name": True})

    # 8. Build + save
    project_id = cp._uid()
    canvas = cp._canvas_config(ratio, quality)
    draft = cp.build_draft_content(project_id, project_name, fps,
                                   total_duration, canvas, tracks, M)
    project_folder = cp.save_project(capcut_path, project_name, draft)

    res.success = True
    res.project_path = project_folder
    res.n_audio = len(audios)
    res.n_intro = len(intro_placements)
    res.n_image = n_image
    res.n_video_edit = n_vedit
    res.n_empty = n_empty
    res.total_duration_us = total_duration
    res.message = (f"OK '{project_name}': {res.n_audio} audio, {res.n_intro} intro, "
                   f"{res.n_image} ảnh, {n_vedit} video edit, "
                   f"{n_empty} đoạn trống, "
                   f"dur={total_duration/1_000_000:.1f}s")
    log(res.message)
    return res
