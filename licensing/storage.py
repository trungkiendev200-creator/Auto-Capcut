"""License storage — lưu/đọc token vào %APPDATA%."""

import json
import os
from core.settings import get_app_data_dir

_LICENSE_FILE = os.path.join(get_app_data_dir(), "license.json")


def load_license() -> dict | None:
    """Load license data. Returns None if not found."""
    if not os.path.isfile(_LICENSE_FILE):
        return None
    try:
        with open(_LICENSE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_license(data: dict) -> None:
    with open(_LICENSE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def clear_license() -> None:
    if os.path.isfile(_LICENSE_FILE):
        os.remove(_LICENSE_FILE)
