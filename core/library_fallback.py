"""Library fallback — load từ bundled JSON khi CapCut cache trống."""

import json
import os
import sys


def _get_fallback_path() -> str:
    """Tìm file library_cache.json (bundled hoặc dev)."""
    # PyInstaller bundled
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "assets", "library_cache.json")


def load_fallback(key: str) -> list[dict]:
    """Load fallback data cho 'animations', 'transitions', hoặc 'effects'."""
    path = _get_fallback_path()
    if not os.path.isfile(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get(key, [])
    except Exception:
        return []
