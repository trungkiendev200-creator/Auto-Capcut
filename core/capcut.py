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
    """Load draft_content.json từ folder của 1 project."""
    json_path = os.path.join(draft_path, "draft_content.json")
    if not os.path.isfile(json_path):
        raise FileNotFoundError(f"draft_content.json not found in {draft_path}")

    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_draft_content(draft_path: str, data: dict) -> None:
    """Ghi draft_content.json."""
    json_path = os.path.join(draft_path, "draft_content.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


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
