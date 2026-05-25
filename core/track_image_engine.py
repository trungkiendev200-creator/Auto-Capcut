"""Handle Track Image — đổi apply_target_type của effect để không che ảnh overlay.

Trong CapCut 8.5, khi effect có:
    apply_target_type = 2 (segment-level)
    bind_segment_id = ""  (rỗng)
→ effect apply lên toàn timeline tại frame đó, che cả image overlay.

Set apply_target_type = 1 (main track only) → effect chỉ apply lên track chính
(track[0]), image overlay sẽ hiện trên cùng không bị che.
"""

import os
from dataclasses import dataclass

from core import capcut


@dataclass
class TrackImageResult:
    success: bool
    message: str
    effects_changed: int = 0


def fix_image_overlay(draft_path: str) -> TrackImageResult:
    """Đổi apply_target_type của effect từ 2 (global) thành 1 (main track only)."""
    if not os.path.isdir(draft_path):
        return TrackImageResult(False, f"Draft not found: {draft_path}")

    try:
        data = capcut.load_draft_content(draft_path)
    except Exception as e:
        return TrackImageResult(False, f"Cannot load draft: {e}")

    effects = data.get("materials", {}).get("video_effects", [])
    if not effects:
        return TrackImageResult(True, "Project không có effect — bỏ qua")

    changed = 0
    skipped = 0
    for eff in effects:
        cur = eff.get("apply_target_type")
        if cur == 1:
            skipped += 1
            continue
        if cur == 2 and not eff.get("bind_segment_id"):
            eff["apply_target_type"] = 1
            changed += 1
        else:
            skipped += 1

    if changed == 0:
        return TrackImageResult(True, f"Không có effect cần sửa (skip {skipped})")

    try:
        capcut.save_draft_content(draft_path, data)
    except Exception as e:
        return TrackImageResult(False, f"Save failed: {e}")

    return TrackImageResult(
        True,
        f"Đổi {changed} effect: apply_target_type 2→1 (skip {skipped})",
        effects_changed=changed,
    )


@dataclass
class BatchResult:
    total: int = 0
    ok: int = 0
    fail: int = 0
    skipped: int = 0


def batch_fix_image_overlay(draft_paths: list[str], callback=None) -> BatchResult:
    result = BatchResult(total=len(draft_paths))
    for p in draft_paths:
        name = os.path.basename(p.rstrip("/\\"))
        if callback:
            callback(f"-> {name}")
        r = fix_image_overlay(p)
        if r.success:
            if r.effects_changed > 0:
                result.ok += 1
                if callback: callback(f"   OK   {r.message}")
            else:
                result.skipped += 1
                if callback: callback(f"   SKIP {r.message}")
        else:
            result.fail += 1
            if callback: callback(f"   FAIL {r.message}")
    if callback:
        callback(f"Done: ok={result.ok}, skipped={result.skipped}, fail={result.fail}")
    return result
