"""Settings manager — load/save settings.json."""

import json
import os
import sys


DEFAULT_CAPCUT_PATH = os.path.join(
    os.environ.get("LOCALAPPDATA", ""), "Capcut"
)

APP_NAME = "AutoCapCut"


def get_app_data_dir() -> str:
    """Thư mục lưu data persistent (settings, license, ...). Hoạt động cả dev lẫn .exe."""
    base = os.environ.get("APPDATA", os.path.expanduser("~"))
    app_dir = os.path.join(base, APP_NAME)
    os.makedirs(app_dir, exist_ok=True)
    return app_dir


def get_bundle_dir() -> str:
    """Thư mục chứa assets bundled. Trong dev = project root, trong .exe = _MEIPASS."""
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


_SETTINGS_FILE = os.path.join(get_app_data_dir(), "settings.json")


def load() -> dict:
    defaults = {
        "capcut_path": DEFAULT_CAPCUT_PATH,
        "export_path": "",
    }
    if os.path.isfile(_SETTINGS_FILE):
        try:
            with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            defaults.update(saved)
        except Exception:
            pass
    return defaults


def save(capcut_path: str, export_path: str) -> None:
    data = {
        "capcut_path": capcut_path,
        "export_path": export_path,
    }
    with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
