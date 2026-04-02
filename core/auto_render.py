"""Auto Render — tự động mở CapCut, export project.

Approach: Keyboard shortcuts (100% reliable, mọi máy đều hoạt động)
- Ctrl+M = Export Video
- Enter = Confirm Export dialog
- Ctrl+Alt+Q = Return to home page
- Escape = Close dialog
"""

import os
import time
import json
import subprocess
from dataclasses import dataclass

import pyautogui
import win32gui
import win32con
import ctypes

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.3


@dataclass
class RenderConfig:
    export_path: str = ""
    auto_shutdown: bool = False
    wait_capcut_load: int = 20
    wait_project_load: int = 20
    wait_export_dialog: int = 3
    render_check_interval: int = 5


def get_capcut_exe() -> str:
    base = os.path.join(os.environ.get("LOCALAPPDATA", ""), "CapCut", "Apps")
    if not os.path.isdir(base):
        return ""
    for d in sorted(os.listdir(base), reverse=True):
        exe = os.path.join(base, d, "CapCut.exe")
        if os.path.isfile(exe):
            return exe
    exe = os.path.join(base, "CapCut.exe")
    return exe if os.path.isfile(exe) else ""


def kill_capcut():
    os.system('taskkill /F /IM CapCut.exe >nul 2>&1')
    os.system('taskkill /F /IM VEDetector.exe >nul 2>&1')
    os.system('taskkill /F /IM VEHelper.exe >nul 2>&1')
    time.sleep(3)


def open_capcut():
    exe = get_capcut_exe()
    if not exe:
        raise FileNotFoundError("CapCut.exe not found")
    subprocess.Popen([exe], shell=False)


def _minimize_all_except_capcut():
    """Minimize all windows except CapCut Qt windows."""
    def cb(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        text = win32gui.GetWindowText(hwnd)
        cls = win32gui.GetClassName(hwnd)
        if not text or cls in ('Shell_TrayWnd', 'Progman', 'WorkerW'):
            return
        if 'Qt622' in cls:
            return
        win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
    win32gui.EnumWindows(cb, None)
    time.sleep(1)


def _activate_capcut(callback=None):
    """Đưa CapCut lên foreground."""
    _minimize_all_except_capcut()
    time.sleep(1)

    # Double-check: send Alt key trick to allow SetForegroundWindow
    hwnds = []
    def cb(hwnd, _):
        if win32gui.GetWindowText(hwnd) == 'CapCut' and 'Qt622' in win32gui.GetClassName(hwnd):
            hwnds.append(hwnd)
    win32gui.EnumWindows(cb, None)

    if hwnds:
        hwnd = hwnds[0]
        ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)  # Alt press
        ctypes.windll.user32.keybd_event(0x12, 0, 2, 0)  # Alt release
        time.sleep(0.1)
        ctypes.windll.user32.SetForegroundWindow(hwnd)
        time.sleep(0.5)

    fg = win32gui.GetForegroundWindow()
    fg_text = win32gui.GetWindowText(fg)
    if callback:
        callback(f"Foreground: {fg_text}")
    return 'CapCut' in fg_text


def _wait_capcut_loaded(timeout: int = 40, callback=None) -> bool:
    """Đợi CapCut load xong (dark theme visible)."""
    start = time.time()
    while time.time() - start < timeout:
        _minimize_all_except_capcut()
        time.sleep(1)

        img = pyautogui.screenshot()
        w, h = img.size

        # CapCut dark theme: nhiều pixel tối ở giữa màn hình
        dark = 0
        for x in range(0, w, 10):
            r, g, b = img.getpixel((x, h // 2))[:3]
            if r < 50 and g < 50 and b < 50:
                dark += 1

        if callback:
            callback(f"Loading... dark_pixels={dark}")

        if dark > 50:
            return True

        time.sleep(2)
    return False


def promote_project(draft: dict, callback=None) -> bool:
    """Đưa project lên đầu danh sách CapCut."""
    try:
        draft_root = draft.get("draft_root_path", "")
        if not draft_root:
            fold = draft.get("draft_fold_path", "")
            if fold:
                draft_root = os.path.dirname(fold)

        meta_path = os.path.join(draft_root, "root_meta_info.json")
        if not os.path.isfile(meta_path):
            return False

        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        target = draft.get("draft_name", "")
        drafts = meta.get("all_draft_store", [])
        max_t = max((d.get("tm_draft_modified", 0) for d in drafts), default=0)

        for d in drafts:
            if d.get("draft_name") == target:
                d["tm_draft_modified"] = max_t + 1000000
                break

        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False)

        if callback:
            callback(f"Promoted '{target}' to top")
        return True
    except Exception as e:
        if callback:
            callback(f"promote error: {e}")
        return False


def click_first_project(callback=None) -> bool:
    """Click project đầu tiên.

    Tỉ lệ cố định: project đầu tiên luôn ở ~3.5% X, ~43% Y
    trong CapCut maximized window. Đã verify trên 1920x1080.
    """
    try:
        img = pyautogui.screenshot()
        w, h = img.size

        # Project đầu tiên: ~3.5% từ trái, ~43% từ trên
        thumb_x = int(w * 0.04)
        thumb_y = int(h * 0.44)

        if callback:
            callback(f"Clicking first project at ({thumb_x}, {thumb_y}) [screen {w}x{h}]")

        pyautogui.doubleClick(thumb_x, thumb_y)
        return True
    except Exception as e:
        if callback:
            callback(f"click error: {e}")
        return False


def wait_render_complete(export_path: str, timeout: int = 3600,
                          check_interval: int = 5, callback=None) -> bool:
    """Đợi file video mới xuất hiện trong export folder."""
    existing = set()
    if os.path.isdir(export_path):
        existing = set(os.listdir(export_path))

    start = time.time()
    while time.time() - start < timeout:
        time.sleep(check_interval)

        if os.path.isdir(export_path):
            current = set(os.listdir(export_path))
            new_vids = [f for f in (current - existing)
                        if f.endswith(('.mp4', '.mov', '.avi', '.mkv'))
                        and not f.endswith('.tmp')]
            if new_vids:
                fpath = os.path.join(export_path, new_vids[0])
                s1 = os.path.getsize(fpath)
                time.sleep(3)
                s2 = os.path.getsize(fpath)
                if s1 == s2 and s1 > 0:
                    if callback:
                        callback(f"Done! {new_vids[0]} ({s2 // 1024 // 1024}MB)")
                    return True

        elapsed = int(time.time() - start)
        if callback and elapsed % 15 == 0:
            callback(f"Rendering... {elapsed}s")

    return False


def render_project(draft: dict, config: RenderConfig, callback=None) -> tuple[bool, str]:
    """Render 1 project CapCut.

    Flow:
    1. Kill CapCut → promote project → open CapCut
    2. Minimize others → wait load
    3. Click first project (promoted)
    4. Wait editor load
    5. Ctrl+M → Export dialog
    6. Enter → start render
    7. Wait file appears in export folder
    8. Kill CapCut
    """
    name = draft.get("draft_name", "")
    if not name:
        return False, "No project name"

    try:
        # Step 1: Kill CapCut
        if callback: callback("Closing CapCut...")
        kill_capcut()

        # Step 2: Promote project to top
        if callback: callback("Promoting project...")
        promote_project(draft, callback=callback)

        # Step 3: Open CapCut
        if callback: callback("Opening CapCut...")
        open_capcut()
        time.sleep(8)

        # Step 4: Wait CapCut loaded
        if callback: callback("Waiting CapCut to load...")
        if not _wait_capcut_loaded(timeout=config.wait_capcut_load, callback=callback):
            return False, "CapCut failed to load"

        if callback: callback("CapCut loaded!")
        time.sleep(2)

        # Step 5: Click first project
        _activate_capcut(callback=callback)
        time.sleep(1)
        if callback: callback(f"Opening project: {name}...")
        if not click_first_project(callback=callback):
            return False, "Cannot click first project"

        # Step 6: Wait editor load
        if callback: callback(f"Waiting editor to load ({config.wait_project_load}s)...")
        time.sleep(config.wait_project_load)

        # Step 7: Click Export button (góc phải trên editor)
        _activate_capcut(callback=callback)
        time.sleep(1)
        screen_w, screen_h = pyautogui.size()
        export_x = int(screen_w * 0.935)
        export_y = int(screen_h * 0.015)
        if callback: callback(f"Clicking Export button at ({export_x}, {export_y})...")
        pyautogui.click(export_x, export_y)
        time.sleep(config.wait_export_dialog)

        # Step 8: Click Export trong dialog (giữa dưới dialog)
        dialog_x = int(screen_w * 0.47)
        dialog_y = int(screen_h * 0.58)
        if callback: callback(f"Clicking dialog Export at ({dialog_x}, {dialog_y})...")
        pyautogui.click(dialog_x, dialog_y)
        time.sleep(2)

        # Step 9: Wait render complete
        if callback: callback("Waiting for render to complete...")
        ok = wait_render_complete(config.export_path, timeout=3600,
                                   check_interval=config.render_check_interval,
                                   callback=callback)
        if not ok:
            return False, "Render timeout"

        # Step 10: Kill CapCut
        time.sleep(2)
        kill_capcut()
        return True, f"Rendered: {name}"

    except Exception as e:
        kill_capcut()
        return False, f"Error: {e}"


def shutdown_pc():
    os.system('shutdown /s /t 30 /c "AutoCapCut: Render complete. Shutting down in 30s."')
