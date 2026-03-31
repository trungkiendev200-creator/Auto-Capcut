"""Self-update — download .exe mới và tự thay thế."""

import os
import sys
import subprocess
import urllib.request
from core.settings import get_app_data_dir


def download_update(url: str, progress_callback=None) -> str:
    """Download .exe mới. Returns path to downloaded file."""
    update_dir = os.path.join(get_app_data_dir(), "update")
    os.makedirs(update_dir, exist_ok=True)
    target = os.path.join(update_dir, "AutoCapCut_new.exe")

    req = urllib.request.Request(url, headers={"User-Agent": "AutoCapCut"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        with open(target, "wb") as f:
            while True:
                chunk = resp.read(8192)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if progress_callback and total > 0:
                    progress_callback(downloaded / total)

    return target


def apply_update(new_exe_path: str):
    """Tạo batch script để thay thế .exe và restart."""
    if not getattr(sys, "frozen", False):
        return  # Chỉ hoạt động với .exe

    current_exe = sys.executable
    update_dir = os.path.dirname(new_exe_path)
    bat_path = os.path.join(update_dir, "update.bat")

    script = f'''@echo off
timeout /t 2 /nobreak >nul
move /y "{new_exe_path}" "{current_exe}"
start "" "{current_exe}"
del "%~f0"
'''
    with open(bat_path, "w") as f:
        f.write(script)

    # Launch batch script (detached, hidden)
    subprocess.Popen(
        ["cmd", "/c", bat_path],
        creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
    )
    sys.exit(0)
