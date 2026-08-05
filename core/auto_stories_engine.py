"""Auto Stories — tạo project ghép VOICE + ẢNH (map theo tên) + VIDEO STOCK nền (random).

Bố cục mỗi project (dựng theo project mẫu "brazil stories01"):
    Track dưới (main): VIDEO STOCK nền — cover full khung, tắt tiếng, lấp/cắt = voice.
    Track trên (overlay, flag=2): ẢNH — canh giữa, scale 0.85, dài = voice.
    Track sticker: Subscribe ở góc dưới-phải, dài = toàn bộ project.
    Track audio: VOICE — dài = toàn bộ project.

Quy tắc:
    - Map voice ↔ ảnh theo TÊN file trùng (video21.mp3 ↔ video21.png).
    - Mỗi project gán 1 video stock ngẫu nhiên, KHÔNG trùng giữa các project.
    - Voice thiếu ảnh cùng tên → bỏ qua (ghi cảnh báo).
    - Nếu số video stock < số project cần tạo → CẢNH BÁO và KHÔNG chạy.
    - Video stock ngắn hơn voice → lặp lại (cắt nối, speed 1.0); dài hơn → cắt.
    - Tên project = "<tiền tố> <tên voice>" (vd "brazil stories video21").

Style (bật/tắt qua StoryStyle, mặc định BẬT hết — xem core/story_style.py):
    - Hiệu ứng "Khung phim 1" trên MỌI segment video (stock + ảnh).
    - Mask "Cuộn phim" + scale 0.85 trên segment ảnh.
    - Sticker "INTERACTION ICONS EN SUBSCRIBE".
"""

import os
import random
from dataclasses import dataclass, field

from core import create_project as cp
from core import create_bck_engine as bck
from core import story_style as ss


VIDEO_EXTS = cp.VIDEO_EXTS | {".m4v", ".webm"}
PHOTO_MATERIAL_DUR = 10800000000  # duration "vô hạn" của material ảnh (giống create_project)


@dataclass
class StoryStyle:
    """Bật/tắt các thành phần style lấy từ project mẫu "brazil stories01"."""
    film_effect: bool = True    # hiệu ứng "Khung phim 1" trên mọi segment video
    photo_mask: bool = True     # mask "Cuộn phim" + scale 0.85 trên ảnh
    sticker: bool = True        # sticker Subscribe góc dưới-phải


@dataclass
class StoryResult:
    success: bool = True
    error: str = ""
    total: int = 0
    created: int = 0
    created_names: list = field(default_factory=list)
    failed: list = field(default_factory=list)          # tên project lỗi
    skipped_no_pic: list = field(default_factory=list)   # stem voice thiếu ảnh


# ── helpers ────────────────────────────────────────────────────────────

def _stem(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0]


def _list_files(folder: str, exts: set) -> list[str]:
    if not folder or not os.path.isdir(folder):
        return []
    out = []
    for f in sorted(os.listdir(folder), key=cp._natural_sort_key):
        if os.path.splitext(f)[1].lower() in exts and \
                os.path.isfile(os.path.join(folder, f)):
            out.append(os.path.join(folder, f).replace("\\", "/"))
    return out


def _image_dims(path: str) -> tuple[int, int]:
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size
    except Exception:
        return 1920, 1080


def _cover_scale(canvas_w: int, canvas_h: int,
                 media_w: int = 1920, media_h: int = 1080) -> float:
    """Hệ số clip.scale để media (base-fit = contain) phủ KÍN canvas (cover).

    Base-fit của CapCut ở scale 1.0 = contain. Cover = max(cw/mw, ch/mh),
    nên nhân thêm max/min của 2 tỉ lệ. Media cùng tỉ lệ canvas → 1.0.
    """
    if not media_w or not media_h:
        return 1.0
    rw = canvas_w / media_w
    rh = canvas_h / media_h
    hi, lo = max(rw, rh), min(rw, rh)
    return hi / lo if lo else 1.0


def _add_bg_stock(M: dict, path: str, stock_dur: int, voice_dur: int,
                  cover_scale: float, mute: bool = True) -> list[dict]:
    """Thêm video nền phủ [0, voice_dur]. Ngắn hơn → lặp; dài hơn → cắt.

    Dùng CHUNG 1 material, tạo nhiều segment nối tiếp. Trả về list segment.
    """
    if stock_dur <= 0:
        raise ValueError("Không đọc được độ dài video stock")

    name = os.path.basename(path)
    info = {"type": "video", "width": 1920, "height": 1080,
            "duration": stock_dur, "name": name, "has_audio": True}
    mat = cp._make_video_material(path, info)
    M["videos"].append(mat)

    segs = []
    filled = 0
    scaled = abs(cover_scale - 1.0) > 1e-6
    while filled < voice_dur:
        piece = min(stock_dur, voice_dur - filled)
        speed = cp._make_speed_material(); M["speeds"].append(speed)
        cnv = cp._make_canvas_material(canvas_blur=False); M["canvases"].append(cnv)
        snd = cp._make_sound_channel(); M["sound_channel_mappings"].append(snd)

        seg = cp._make_video_segment(mat["id"], int(filled), int(piece),
                                     speed["id"], cnv["id"], snd["id"])
        seg["source_timerange"] = {"start": 0, "duration": int(piece)}
        seg["target_timerange"] = {"start": int(filled), "duration": int(piece)}
        if scaled:
            seg["clip"]["scale"] = {"x": cover_scale, "y": cover_scale}
        if mute:
            seg["volume"] = 0.0
            seg["last_nonzero_volume"] = 1.0
        segs.append(seg)
        filled += piece
    return segs


def _add_picture(M: dict, path: str, voice_dur: int) -> dict:
    """Thêm ảnh overlay (fit, canh giữa), dài = voice_dur. Trả về segment."""
    w, h = _image_dims(path)
    seg = bck._add_video_clip(
        M, path, PHOTO_MATERIAL_DUR, 0, int(voice_dur), 0,
        is_photo=True, mute=False, width=w, height=h,
    )
    return seg


def _stock_duration(path: str) -> int:
    dur = bck.mp4_duration_us(path)
    if dur and dur > 0:
        return dur
    # fallback: mutagen qua _get_media_info
    try:
        return int(cp._get_media_info(path)["duration"])
    except Exception:
        return 0


def _build_one(voice_path: str, pic_path: str, stock_path: str,
               project_name: str, capcut_path: str,
               ratio: str, quality: str, fps: int,
               style: StoryStyle | None = None) -> tuple[str, int]:
    """Dựng + lưu 1 project. Trả về (project_folder, voice_dur)."""
    style = style or StoryStyle()
    voice_dur = cp._get_audio_duration(voice_path)
    stock_dur = _stock_duration(stock_path)

    canvas = cp._canvas_config(ratio, quality)
    cover = _cover_scale(canvas["width"], canvas["height"])

    M = cp._build_materials_dict([], [], [], [], [], [])

    # 1. Video stock nền (main track)
    bg_segs = _add_bg_stock(M, stock_path, stock_dur, voice_dur, cover, mute=True)

    # 2. Ảnh overlay (render đè lên trên) — track flag=2 như project mẫu
    pic_seg = _add_picture(M, pic_path, voice_dur)
    pic_seg["render_index"] = 1
    pic_seg["track_render_index"] = 1

    # 3. Voice (audio track)
    audio_seg = bck._add_audio_clip(M, voice_path, voice_dur, 0)

    # 4. Style theo project mẫu "brazil stories01"
    if style.film_effect:
        ss.apply_film_effect(M, bg_segs + [pic_seg])
    if style.photo_mask:
        pic_seg["clip"]["scale"] = {"x": ss.PHOTO_SCALE, "y": ss.PHOTO_SCALE}
        ss.apply_film_mask(M, pic_seg)

    tracks = [
        {"id": cp._uid(), "type": "video", "segments": bg_segs, "flag": 0,
         "attribute": 0, "name": "", "is_default_name": True},
        {"id": cp._uid(), "type": "video", "segments": [pic_seg], "flag": 2,
         "attribute": 0, "name": "", "is_default_name": True},
    ]
    if style.sticker:
        tracks.append(ss.add_sticker_track(M, int(voice_dur)))
    tracks.append({"id": cp._uid(), "type": "audio", "segments": [audio_seg],
                   "flag": 0, "attribute": 0, "name": "", "is_default_name": True})

    project_id = cp._uid()
    draft = cp.build_draft_content(project_id, project_name, fps,
                                   int(voice_dur), canvas, tracks, M)
    folder = cp.save_project(capcut_path, project_name, draft)
    return folder, voice_dur


# ── public entry ───────────────────────────────────────────────────────

def create_auto_stories(picture_folder: str, voice_folder: str, stock_folder: str,
                        prefix: str, capcut_path: str,
                        ratio: str = "16:9", quality: str = "1080p", fps: int = 30,
                        style: StoryStyle | None = None,
                        callback=None) -> StoryResult:
    def log(m):
        if callback:
            callback(m)

    style = style or StoryStyle()
    res = StoryResult()

    voices = _list_files(voice_folder, cp.AUDIO_EXTS)
    pics = _list_files(picture_folder, cp.IMAGE_EXTS)
    stocks = _list_files(stock_folder, VIDEO_EXTS)

    if not voices:
        res.success = False; res.error = "Thư mục VOICE trống hoặc không hợp lệ."
        return res
    if not pics:
        res.success = False; res.error = "Thư mục PICTURE trống hoặc không hợp lệ."
        return res
    if not stocks:
        res.success = False; res.error = "Thư mục VIDEO STOCK trống hoặc không hợp lệ."
        return res

    # map ảnh theo stem (tên file, không phân biệt hoa/thường)
    pic_by_stem: dict[str, str] = {}
    for p in pics:
        pic_by_stem.setdefault(_stem(p).lower(), p)

    pairs = []  # (voice_path, pic_path, stem)
    for v in voices:
        st = _stem(v)
        pic = pic_by_stem.get(st.lower())
        if pic:
            pairs.append((v, pic, st))
        else:
            res.skipped_no_pic.append(st)

    if not pairs:
        res.success = False
        res.error = "Không có voice nào khớp ảnh cùng tên. Kiểm tra lại dữ liệu."
        return res

    # KIỂM TRA DỮ LIỆU: đủ video stock cho mỗi project (không trùng)
    if len(stocks) < len(pairs):
        res.success = False
        res.error = (
            f"THIẾU VIDEO STOCK: cần {len(pairs)} video (mỗi project 1 video không trùng) "
            f"nhưng chỉ có {len(stocks)}. Bổ sung video stock rồi chạy lại."
        )
        return res

    res.total = len(pairs)

    # gán stock ngẫu nhiên, không trùng
    stock_pool = list(stocks)
    random.shuffle(stock_pool)

    prefix = (prefix or "").strip()

    on = [n for n, v in (("Khung phim 1", style.film_effect),
                         ("Mask cuộn phim + scale 0.85", style.photo_mask),
                         ("Sticker Subscribe", style.sticker)) if v]
    log(f"Bắt đầu: {len(pairs)} project | stock={len(stocks)} | "
        f"bỏ qua (thiếu ảnh)={len(res.skipped_no_pic)}")
    log("Style: " + (", ".join(on) if on else "(không áp style nào)"))

    for i, (voice, pic, st) in enumerate(pairs):
        stock = stock_pool[i]
        name = f"{prefix} {st}".strip() if prefix else st
        log(f"-> {name}  [voice={os.path.basename(voice)}, "
            f"pic={os.path.basename(pic)}, stock={os.path.basename(stock)}]")
        try:
            _, vdur = _build_one(voice, pic, stock, name, capcut_path,
                                 ratio, quality, fps, style=style)
            res.created += 1
            res.created_names.append(name)
            log(f"   OK  dur={vdur / 1_000_000 / 60:.1f} phút")
        except Exception as e:
            import traceback
            res.failed.append(name)
            log(f"   FAIL {e}")
            log(traceback.format_exc())

    if res.skipped_no_pic:
        log(f"Bỏ qua {len(res.skipped_no_pic)} voice thiếu ảnh: "
            f"{', '.join(res.skipped_no_pic)}")
    log(f"Done: tạo {res.created}/{res.total} project"
        + (f", lỗi {len(res.failed)}" if res.failed else ""))
    return res
