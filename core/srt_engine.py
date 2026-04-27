"""SRT Engine — xuất file .srt từ text tracks của project CapCut."""

import json
import os
from dataclasses import dataclass

from core import capcut, sync_sub_engine


@dataclass
class ExportSrtResult:
    success: bool
    message: str
    file_path: str = ""
    sub_count: int = 0


def _us_to_srt_timestamp(us: int) -> str:
    """Convert microseconds → SRT timestamp HH:MM:SS,mmm."""
    if us < 0:
        us = 0
    total_ms = us // 1000
    hours, total_ms = divmod(total_ms, 3_600_000)
    mins, total_ms = divmod(total_ms, 60_000)
    secs, ms = divmod(total_ms, 1000)
    return f"{hours:02d}:{mins:02d}:{secs:02d},{ms:03d}"


def subs_to_srt_text(subs) -> str:
    """Convert list[SubInfo] → string SRT chuẩn."""
    lines = []
    for s in subs:
        lines.append(str(s.index))
        lines.append(f"{_us_to_srt_timestamp(s.start)} --> {_us_to_srt_timestamp(s.end)}")
        lines.append(s.text or "")
        lines.append("")  # blank line giữa các entries
    return "\n".join(lines).rstrip() + "\n"


def export_srt(
    draft_path: str,
    output_dir: str,
    project_name: str,
) -> ExportSrtResult:
    """Xuất file .srt từ text track của project.

    Behavior:
        - Project không có text track → fail với message rõ ràng (caller skip + warn).
        - Auto-detect text track tiếng Anh nếu có nhiều track (ưu tiên ASCII).
        - Output file: <output_dir>/<project_name>.srt
        - Encoding: UTF-8 (BOM-less, format chuẩn cho mọi player)
    """
    json_path = os.path.join(draft_path, "draft_content.json")
    if not os.path.isfile(json_path):
        return ExportSrtResult(False, "draft_content.json not found")

    if not output_dir or not os.path.isdir(output_dir):
        return ExportSrtResult(False, "Output folder không hợp lệ")

    try:
        data = capcut.load_draft_content(draft_path)
    except json.JSONDecodeError as e:
        return ExportSrtResult(False, f"draft_content.json bị hỏng: {e}")
    except Exception as e:
        return ExportSrtResult(False, f"Không đọc được draft: {e}")

    track = sync_sub_engine.find_english_text_track(data)
    if track is None:
        return ExportSrtResult(False, "Không tìm thấy text track có sub")

    subs = sync_sub_engine.get_sorted_subs(track, data)
    if not subs:
        return ExportSrtResult(False, "Text track không có sub nào")

    srt_text = subs_to_srt_text(subs)
    file_path = os.path.join(output_dir, f"{project_name}.srt")

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(srt_text)
    except OSError as e:
        return ExportSrtResult(False, f"Không ghi được file: {e}")

    return ExportSrtResult(
        success=True,
        message=f"{len(subs)} sub → {os.path.basename(file_path)}",
        file_path=file_path,
        sub_count=len(subs),
    )
