"""CapCut project reader — đọc meta info và draft_content.json."""

import json
import os


DRAFT_SUBPATH = os.path.join("User Data", "Projects", "com.lveditor.draft")


def get_draft_root(capcut_path: str) -> str:
    return os.path.join(capcut_path, DRAFT_SUBPATH)


def get_meta_path(capcut_path: str) -> str:
    return os.path.join(get_draft_root(capcut_path), "root_meta_info.json")


def load_projects(capcut_path: str) -> list[dict]:
    """Load danh sách projects từ root_meta_info.json.

    Returns list of draft dicts, sorted by modified time (newest first).
    Bỏ qua projects đã bị xóa.
    """
    meta_path = get_meta_path(capcut_path)
    if not os.path.isfile(meta_path):
        raise FileNotFoundError(f"Meta file not found: {meta_path}")

    with open(meta_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    drafts = data.get("all_draft_store", [])
    drafts = [d for d in drafts if d.get("tm_draft_removed", 0) == 0]
    drafts.sort(key=lambda d: d.get("tm_draft_modified", 0), reverse=True)
    return drafts


def load_draft_content(draft_path: str) -> dict:
    """Load draft_content.json — ưu tiên Timelines nếu có (CapCut mới)."""
    # Thử Timelines trước (CapCut mới dùng folder này)
    timelines_dir = os.path.join(draft_path, "Timelines")
    if os.path.isdir(timelines_dir):
        for d in os.listdir(timelines_dir):
            tl_json = os.path.join(timelines_dir, d, "draft_content.json")
            if os.path.isfile(tl_json):
                with open(tl_json, "r", encoding="utf-8") as f:
                    return json.load(f)

    # Fallback: root draft_content.json
    json_path = os.path.join(draft_path, "draft_content.json")
    if not os.path.isfile(json_path):
        raise FileNotFoundError(f"draft_content.json not found in {draft_path}")

    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_draft_content(draft_path: str, data: dict) -> None:
    """Ghi draft_content.json vào root + Timelines. Kill CapCut nếu đang chạy."""
    import subprocess
    import time as _time

    # Kill tất cả CapCut processes trước khi ghi
    for proc_name in ["CapCut.exe", "CapCutLoader.exe", "CapCut_Service.exe"]:
        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", proc_name],
                capture_output=True, timeout=5
            )
        except Exception:
            pass

    _time.sleep(1)

    # Auto fix: tắt âm thanh video nằm trên vùng audio narration
    audio_ranges = []
    for t in data.get("tracks", []):
        if t.get("type") == "audio":
            for seg in t.get("segments", []):
                a_start = seg["target_timerange"]["start"]
                a_end = a_start + seg["target_timerange"]["duration"]
                audio_ranges.append((a_start, a_end))

    if audio_ranges:
        muted_material_ids = set()
        for t in data.get("tracks", []):
            if t.get("type") == "video":
                for seg in t.get("segments", []):
                    v_start = seg["target_timerange"]["start"]
                    v_end = v_start + seg["target_timerange"]["duration"]
                    # Video overlap với bất kỳ audio nào → tắt âm
                    for a_start, a_end in audio_ranges:
                        if v_start < a_end and v_end > a_start:
                            seg["volume"] = 0.0
                            seg["last_nonzero_volume"] = 0.0
                            muted_material_ids.add(seg.get("material_id", ""))
                            break

        # Set has_audio=false trên material để CapCut không khôi phục âm thanh
        for vid_mat in data.get("materials", {}).get("videos", []):
            if vid_mat.get("id") in muted_material_ids and vid_mat.get("has_audio"):
                vid_mat["has_audio"] = False

    content = json.dumps(data, ensure_ascii=False)

    # Collect tất cả paths cần ghi
    paths_to_write = []

    # Root draft_content.json + .bk
    root_json = os.path.join(draft_path, "draft_content.json")
    paths_to_write.append(root_json)
    if os.path.isfile(root_json + ".bk"):
        paths_to_write.append(root_json + ".bk")

    # Timelines/<UUID>/draft_content.json (CapCut mới dùng folder này)
    timelines_dir = os.path.join(draft_path, "Timelines")
    if os.path.isdir(timelines_dir):
        for d in os.listdir(timelines_dir):
            sub = os.path.join(timelines_dir, d)
            if os.path.isdir(sub):
                tl_json = os.path.join(sub, "draft_content.json")
                if os.path.isfile(tl_json):
                    paths_to_write.append(tl_json)

    # Ghi tất cả
    for path in paths_to_write:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())


def find_video_tracks(data: dict) -> list[dict]:
    """Tìm tất cả video tracks có segments."""
    return [
        t for t in data.get("tracks", [])
        if t.get("type") == "video" and len(t.get("segments", [])) > 0
    ]


def find_audio_track(data: dict) -> dict | None:
    """Tìm audio track đầu tiên có segments."""
    for t in data.get("tracks", []):
        if t.get("type") == "audio" and len(t.get("segments", [])) > 0:
            return t
    return None


def get_material_type(data: dict, material_id: str) -> str:
    """Tìm type (photo/video) của material theo ID."""
    for v in data.get("materials", {}).get("videos", []):
        if v.get("id") == material_id:
            return v.get("type", "video")
    return "unknown"
