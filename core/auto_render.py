"""Auto Render v8 — Win32 + Screenshot detection + Keyboard shortcuts.

- Win32 API: window management, keyboard, mouse
- mss + cv2: detect project thumbnail chính xác (không hard-code tọa độ)
- Keyboard shortcuts: Export (Ctrl+E), Confirm (Enter)
"""

import os
import time
import json
import subprocess
from dataclasses import dataclass
import ctypes
import ctypes.wintypes

import cv2
import numpy as np
import mss

# ═══════════════════════════════════════════════════════════════
#  Win32 Constants & API
# ═══════════════════════════════════════════════════════════════
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

SW_MINIMIZE = 6
SW_MAXIMIZE = 3
SW_RESTORE = 9
GW_OWNER = 4

KEYEVENTF_KEYUP = 0x0002
VK_ESCAPE = 0x1B
VK_RETURN = 0x0D
VK_CONTROL = 0x11
VK_E = 0x45

ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
DEBUG_DIR = os.path.join(ASSETS_DIR, "debug_render")


@dataclass
class RenderConfig:
    export_path: str = ""
    auto_shutdown: bool = False


# ═══════════════════════════════════════════════════════════════
#  Debug
# ═══════════════════════════════════════════════════════════════
def _save_debug(img, name):
    os.makedirs(DEBUG_DIR, exist_ok=True)
    cv2.imwrite(os.path.join(DEBUG_DIR, name), img)


# ═══════════════════════════════════════════════════════════════
#  Screenshot
# ═══════════════════════════════════════════════════════════════
def _capture_window(hwnd):
    """Chụp screenshot vùng CapCut window."""
    rect = ctypes.wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    region = {
        "left": rect.left,
        "top": rect.top,
        "width": rect.right - rect.left,
        "height": rect.bottom - rect.top,
    }
    with mss.mss() as sct:
        img = np.array(sct.grab(region))
    return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR), rect


# ═══════════════════════════════════════════════════════════════
#  Win32 Helpers
# ═══════════════════════════════════════════════════════════════
def _press_key(vk):
    user32.keybd_event(vk, 0, 0, 0)
    time.sleep(0.05)
    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)


def _hotkey(modifier, vk):
    user32.keybd_event(modifier, 0, 0, 0)
    time.sleep(0.05)
    user32.keybd_event(vk, 0, 0, 0)
    time.sleep(0.05)
    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.05)
    user32.keybd_event(modifier, 0, KEYEVENTF_KEYUP, 0)


def _find_capcut_hwnd():
    result = []

    def callback(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value
        cls_buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls_buf, 256)
        cls = cls_buf.value
        if "Qt6" in cls and ("CapCut" in title or "cap cut" in title.lower()):
            result.append(hwnd)
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    user32.EnumWindows(WNDENUMPROC(callback), 0)
    return result[0] if result else None


def _bring_to_front(hwnd):
    if not hwnd:
        return False
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
        time.sleep(0.5)
    user32.ShowWindow(hwnd, SW_MAXIMIZE)
    time.sleep(0.3)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.3)
    user32.BringWindowToTop(hwnd)
    return True


def _get_window_title(hwnd):
    if not hwnd:
        return ""
    length = user32.GetWindowTextLengthW(hwnd)
    if length == 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def _minimize_window(hwnd):
    if hwnd:
        user32.ShowWindow(hwnd, SW_MINIMIZE)


def _get_hwnd_from_tkinter(tk_window):
    try:
        return int(tk_window.wm_frame(), 16)
    except Exception:
        return None


def _click_at(x, y):
    user32.SetCursorPos(int(x), int(y))
    time.sleep(0.1)
    user32.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.05)
    user32.mouse_event(0x0004, 0, 0, 0, 0)


def _double_click_at(x, y):
    _click_at(x, y)
    time.sleep(0.08)
    _click_at(x, y)


# ═══════════════════════════════════════════════════════════════
#  CapCut Helpers
# ═══════════════════════════════════════════════════════════════
def get_capcut_exe():
    base = os.path.join(os.environ.get("LOCALAPPDATA", ""), "CapCut", "Apps")
    if not os.path.isdir(base):
        return ""
    for d in sorted(os.listdir(base), reverse=True):
        exe = os.path.join(base, d, "CapCut.exe")
        if os.path.isfile(exe):
            return exe
    return ""


def kill_capcut(cb=None):
    if cb:
        cb("Kill CapCut...")
    CREATE_NO_WINDOW = 0x08000000
    for name in ("CapCut.exe", "VEDetector.exe", "VEHelper.exe"):
        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", name],
                capture_output=True, timeout=5,
                creationflags=CREATE_NO_WINDOW,
            )
        except Exception:
            pass
    time.sleep(3)


def promote_project(draft, cb=None):
    try:
        draft_root = draft.get("draft_root_path", "") or os.path.dirname(draft.get("draft_fold_path", ""))
        meta_path = os.path.join(draft_root, "root_meta_info.json")
        if not os.path.isfile(meta_path):
            return False
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        target = draft.get("draft_name", "")
        max_t = max((d.get("tm_draft_modified", 0) for d in meta["all_draft_store"]), default=0)
        for d in meta["all_draft_store"]:
            if d.get("draft_name") == target:
                d["tm_draft_modified"] = max_t + 1000000
                break
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False)
        if cb:
            cb(f"Promoted '{target}'")
        return True
    except Exception as e:
        if cb:
            cb(f"Promote error: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
#  Project Detection (cv2)
# ═══════════════════════════════════════════════════════════════
def _find_first_project_pos(hwnd, cb=None):
    """Tìm vị trí project đầu tiên bằng column analysis.

    Chiến lược:
    1. Chụp screenshot, crop ROI vùng project (44-58% height)
    2. Tính brightness trung bình mỗi cột dọc (vertical column mean)
    3. Tìm các "valley" (cột tối = gap giữa thumbnails) và "peak" (cột sáng hơn = thumbnail)
    4. Thumbnail đầu tiên = vùng giữa gap đầu (sidebar) và gap thứ 2
    5. Click center của vùng đó
    """
    screen, win_rect = _capture_window(hwnd)
    h, w = screen.shape[:2]
    _save_debug(screen, "01_home.png")

    if cb:
        cb(f"Screenshot: {w}x{h}")

    gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)

    # === ROI: vùng thumbnails only (44-56% height) ===
    # Chỉ lấy vùng chứa thumbnail bodies, bỏ "Projects" label và tên project
    x1 = int(w * 0.08)
    x2 = int(w * 0.85)
    y1 = int(h * 0.44)
    y2 = int(h * 0.56)
    roi = gray[y1:y2, x1:x2]
    roi_h, roi_w = roi.shape
    _save_debug(roi, "02_roi.png")

    if cb:
        cb(f"ROI: x=[{x1},{x2}] y=[{y1},{y2}] ({roi_w}x{roi_h})")

    # === Column analysis: brightness trung bình mỗi cột dọc ===
    col_means = np.mean(roi, axis=0)  # shape: (roi_w,)

    # Smooth để bớt noise
    kernel_size = 11
    col_smooth = np.convolve(col_means, np.ones(kernel_size)/kernel_size, mode='same')

    # Background level = median (phần lớn là background tối)
    bg_level = np.median(col_smooth)

    if cb:
        cb(f"Background level: {bg_level:.1f}")

    # === Tìm các vùng "sáng hơn background" = thumbnails ===
    # Thumbnail dù tối vẫn có content (DISCLAIMER text, preview, etc.)
    # nên brightness hơi cao hơn background thuần
    threshold = bg_level + 3  # chỉ cần hơn background 3 level

    above = col_smooth > threshold
    # Tìm các transitions (từ tối→sáng và sáng→tối)
    diff = np.diff(above.astype(int))
    rises = np.where(diff == 1)[0] + 1   # bắt đầu thumbnail
    falls = np.where(diff == -1)[0] + 1  # kết thúc thumbnail

    # Handle edge cases
    if above[0]:
        rises = np.insert(rises, 0, 0)
    if above[-1]:
        falls = np.append(falls, roi_w)

    # Ghép thành segments
    segments = list(zip(rises[:len(falls)], falls[:len(rises)]))

    # Lọc: thumbnail phải rộng >= 40px
    thumbnails = [(s, e) for s, e in segments if (e - s) >= 40]

    if cb:
        cb(f"Found {len(thumbnails)} thumbnail segments:")
        for i, (s, e) in enumerate(thumbnails):
            cx = x1 + (s + e) // 2
            cb(f"  seg[{i}]: x=[{x1+s},{x1+e}] width={e-s} center_x={cx}")

    # === Debug image ===
    debug_img = screen.copy()
    for s, e in thumbnails:
        abs_s = x1 + s
        abs_e = x1 + e
        cv2.rectangle(debug_img, (abs_s, y1), (abs_e, y2), (0, 255, 0), 2)

    if thumbnails:
        # Thumbnail đầu tiên
        s, e = thumbnails[0]
        click_x = x1 + (s + e) // 2
        click_y = (y1 + y2) // 2  # center Y of thumbnail row

        cv2.circle(debug_img, (click_x, click_y), 12, (0, 0, 255), 3)
        cv2.putText(debug_img, "CLICK", (click_x + 15, click_y - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        _save_debug(debug_img, "04_detected.png")

        screen_x = win_rect.left + click_x
        screen_y = win_rect.top + click_y

        if cb:
            cb(f"First thumbnail: x=[{x1+s},{x1+e}] center=({click_x},{click_y})")
            cb(f"Click at screen ({screen_x},{screen_y})")

        return screen_x, screen_y

    _save_debug(debug_img, "04_detected.png")

    if cb:
        cb("No thumbnails detected! Check debug images.")
    return None


# ═══════════════════════════════════════════════════════════════
#  Wait helpers
# ═══════════════════════════════════════════════════════════════
def _wait_capcut_window(timeout=60, cb=None):
    start = time.time()
    while time.time() - start < timeout:
        hwnd = _find_capcut_hwnd()
        if hwnd:
            if cb:
                cb(f"CapCut window found (hwnd={hwnd})")
            return hwnd
        elapsed = int(time.time() - start)
        if cb and elapsed % 5 == 0 and elapsed > 0:
            cb(f"Waiting CapCut window... {elapsed}s")
        time.sleep(1)
    return None


def _wait_capcut_home(hwnd, timeout=60, cb=None):
    """Chờ CapCut Home load xong bằng screenshot: check dark pixel > 60%."""
    start = time.time()
    while time.time() - start < timeout:
        if user32.IsWindowVisible(hwnd):
            try:
                screen, _ = _capture_window(hwnd)
                gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
                dark_pct = np.sum(gray < 50) / gray.size * 100
                elapsed = int(time.time() - start)
                if cb and elapsed % 3 == 0:
                    cb(f"Loading... dark={dark_pct:.0f}% ({elapsed}s)")
                if dark_pct > 60:
                    if cb:
                        cb(f"Home loaded! dark={dark_pct:.0f}%")
                    _save_debug(screen, "00_home_loaded.png")
                    time.sleep(5)
                    return True
            except Exception:
                pass
        time.sleep(2)
    return False


def _wait_editor_loaded(hwnd, project_name, timeout=60, cb=None):
    """Chờ editor load: detect bằng screenshot thay đổi so với Home."""
    start = time.time()
    original_title = _get_window_title(hwnd)

    # Chụp screenshot Home làm baseline
    try:
        home_screen, _ = _capture_window(hwnd)
        home_gray = cv2.cvtColor(home_screen, cv2.COLOR_BGR2GRAY)
    except Exception:
        home_gray = None

    if cb:
        cb(f"Original title: '{original_title}'")

    while time.time() - start < timeout:
        time.sleep(2)
        elapsed = int(time.time() - start)

        # Check 1: title thay đổi
        current_title = _get_window_title(hwnd)
        if current_title and current_title != original_title:
            if cb:
                cb(f"Title changed: '{current_title}' ({elapsed}s)")
            time.sleep(3)
            return True

        # Check 2: screenshot thay đổi đáng kể so với Home
        if home_gray is not None and elapsed >= 5:
            try:
                current_screen, _ = _capture_window(hwnd)
                current_gray = cv2.cvtColor(current_screen, cv2.COLOR_BGR2GRAY)
                diff = cv2.absdiff(home_gray, current_gray)
                change_pct = np.sum(diff > 30) / diff.size * 100
                if cb:
                    cb(f"Screen change: {change_pct:.1f}% ({elapsed}s)")
                _save_debug(current_screen, f"05_editor_{elapsed}s.png")
                if change_pct > 30:
                    if cb:
                        cb(f"Editor detected! change={change_pct:.1f}% ({elapsed}s)")
                    time.sleep(3)
                    return True
            except Exception:
                pass

        # Check 3: timeout fallback
        if elapsed >= 25:
            if cb:
                cb(f"Assuming editor loaded ({elapsed}s)")
            time.sleep(3)
            return True

        if cb and elapsed % 5 == 0:
            cb(f"Waiting editor... {elapsed}s")

    return False


def wait_render_complete(export_path, timeout=3600, cb=None):
    existing = set(os.listdir(export_path)) if os.path.isdir(export_path) else set()
    start = time.time()
    while time.time() - start < timeout:
        time.sleep(5)
        if os.path.isdir(export_path):
            new = set(os.listdir(export_path)) - existing
            vids = [f for f in new if f.lower().endswith(('.mp4', '.mov', '.avi', '.mkv')) and not f.endswith('.tmp')]
            if vids:
                fp = os.path.join(export_path, vids[0])
                s1 = os.path.getsize(fp)
                time.sleep(3)
                s2 = os.path.getsize(fp)
                if s1 == s2 and s1 > 0:
                    if cb:
                        cb(f"DONE! {vids[0]} ({s2 // 1024 // 1024}MB)")
                    return True
        elapsed = int(time.time() - start)
        if cb and elapsed % 15 == 0:
            cb(f"Rendering... {elapsed}s")
    return False


# ═══════════════════════════════════════════════════════════════
#  Main Render Flow
# ═══════════════════════════════════════════════════════════════
def render_project(draft, config, tool_window=None, callback=None):
    name = draft.get("draft_name", "")
    if not name:
        return False, "No project name"
    cb = callback

    try:
        # === 1. Kill CapCut + promote ===
        if cb:
            cb("[1] Kill CapCut + promote")
        kill_capcut(cb)
        promote_project(draft, cb)

        # === 2. Minimize tool window ===
        if tool_window:
            if cb:
                cb("[2] Minimize tool window")
            tool_hwnd = _get_hwnd_from_tkinter(tool_window)
            if tool_hwnd:
                _minimize_window(tool_hwnd)
            else:
                tool_window.after(0, tool_window.iconify)
            time.sleep(1)

        # === 3. Mở CapCut ===
        exe = get_capcut_exe()
        if not exe:
            return False, "CapCut.exe not found"
        if cb:
            cb("[3] Opening CapCut...")
        subprocess.Popen([exe])

        # === 4. Chờ CapCut window ===
        if cb:
            cb("[4] Waiting CapCut window...")
        hwnd = _wait_capcut_window(timeout=60, cb=cb)
        if not hwnd:
            return False, "CapCut window not found"

        # === 5. Maximize + foreground ===
        if cb:
            cb("[5] Bring CapCut to front")
        _bring_to_front(hwnd)

        # === 6. Chờ Home load (screenshot dark check) ===
        if cb:
            cb("[6] Waiting Home to load...")
        if not _wait_capcut_home(hwnd, timeout=60, cb=cb):
            return False, "CapCut Home failed to load"

        # === 7. Close popups ===
        if cb:
            cb("[7] Close popups (Escape)")
        _bring_to_front(hwnd)
        time.sleep(0.5)
        _press_key(VK_ESCAPE)
        time.sleep(1)
        _press_key(VK_ESCAPE)
        time.sleep(2)

        # === 8. Tìm + click project đầu tiên ===
        if cb:
            cb(f"[8] Finding project: {name}")
        _bring_to_front(hwnd)
        time.sleep(1)
        pos = _find_first_project_pos(hwnd, cb)
        if not pos:
            return False, "Cannot find project on screen"
        if cb:
            cb(f"[8] Double-click project at ({pos[0]},{pos[1]})")
        _double_click_at(pos[0], pos[1])

        # === 9. Chờ editor load (screenshot diff) ===
        if cb:
            cb("[9] Waiting editor to load...")
        if not _wait_editor_loaded(hwnd, name, timeout=60, cb=cb):
            return False, "Editor failed to load"

        # === 10. Export: Ctrl+E ===
        if cb:
            cb("[10] Export (Ctrl+E)")
        _bring_to_front(hwnd)
        time.sleep(1)
        _hotkey(VK_CONTROL, VK_E)
        time.sleep(4)

        # === 11. Confirm: Enter ===
        if cb:
            cb("[11] Confirm export (Enter)")
        _press_key(VK_RETURN)
        time.sleep(3)

        # === 12. Chờ render ===
        if cb:
            cb("[12] Waiting render complete...")
        ok = wait_render_complete(config.export_path, timeout=3600, cb=cb)
        if not ok:
            return False, "Render timeout"

        # === 13. Done ===
        time.sleep(2)
        kill_capcut(cb)
        return True, f"Rendered: {name}"

    except Exception as e:
        import traceback
        if cb:
            cb(f"EXCEPTION: {traceback.format_exc()}")
        kill_capcut()
        return False, f"Error: {e}"

    finally:
        if tool_window:
            tool_window.after(0, tool_window.deiconify)


def has_templates():
    return True


def capture_templates(cb=None):
    if cb:
        cb("v8: Không cần calibrate — auto detect project position.")
    return True


def shutdown_pc():
    os.system('shutdown /s /t 30 /c "AutoCapCut: Render complete."')
