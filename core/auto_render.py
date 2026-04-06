"""Auto Render v6 — theo cách tool đối thủ.

CopyFromScreen (mss) + Template Matching (cv2) + Win32 mouse_event (ctypes).
Ảnh mẫu cần calibrate 1 lần từ CapCut thật.
"""

import os
import time
import json
import subprocess
from dataclasses import dataclass
import ctypes

import cv2
import numpy as np
import mss

ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
TEMPLATE_DIR = os.path.join(ASSETS_DIR, "templates")
DEBUG_DIR = os.path.join(ASSETS_DIR, "debug_render")

# Win32 mouse constants
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004


@dataclass
class RenderConfig:
    export_path: str = ""
    auto_shutdown: bool = False


# ═══════════════════════════════════════════════════════════════
#  Core: Screenshot + Find + Click (giống đối thủ)
# ═══════════════════════════════════════════════════════════════
def capture_screen() -> np.ndarray:
    """CopyFromScreen equivalent — chụp đúng cái gì trên monitor."""
    with mss.mss() as sct:
        return cv2.cvtColor(np.array(sct.grab(sct.monitors[1])), cv2.COLOR_BGRA2BGR)


def find_template(screen, template_path, threshold=0.8):
    """Tìm ảnh mẫu trên screenshot. Returns (cx, cy) hoặc None."""
    if not os.path.isfile(template_path):
        return None
    tpl = cv2.imread(template_path)
    if tpl is None:
        return None
    result = cv2.matchTemplate(screen, tpl, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    if max_val >= threshold:
        return (max_loc[0] + tpl.shape[1] // 2, max_loc[1] + tpl.shape[0] // 2)
    return None


def find_any_template(screen, template_paths, threshold=0.8):
    """Thử nhiều ảnh mẫu, trả về cái đầu tiên match."""
    for path in template_paths:
        pos = find_template(screen, path, threshold)
        if pos:
            return pos
    return None


def click_at(x, y, cb=None):
    """Click bằng Win32 API — SetCursorPos + mouse_event."""
    if cb: cb(f"  Click ({x},{y})")
    ctypes.windll.user32.SetCursorPos(x, y)
    time.sleep(0.1)
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, x, y, 0, 0)
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, x, y, 0, 0)


def double_click_at(x, y, cb=None):
    if cb: cb(f"  DblClick ({x},{y})")
    click_at(x, y)
    time.sleep(0.1)
    click_at(x, y)


def wait_for_image(template_path, timeout=30, threshold=0.8, cb=None):
    """Chờ đến khi thấy ảnh mẫu trên screen."""
    start = time.time()
    while time.time() - start < timeout:
        screen = capture_screen()
        pos = find_template(screen, template_path, threshold)
        if pos:
            if cb: cb(f"  Found {os.path.basename(template_path)} at ({pos[0]},{pos[1]})")
            return pos
        time.sleep(0.5)
    return None


def save_debug(img, name):
    os.makedirs(DEBUG_DIR, exist_ok=True)
    cv2.imwrite(os.path.join(DEBUG_DIR, name), img)


# ═══════════════════════════════════════════════════════════════
#  Calibrate: chụp ảnh mẫu nút Export từ CapCut
# ═══════════════════════════════════════════════════════════════
def capture_templates(cb=None) -> bool:
    """User mở CapCut editor + mở Export dialog → tool tự crop templates."""
    os.makedirs(TEMPLATE_DIR, exist_ok=True)
    screen = capture_screen()
    h, w = screen.shape[:2]
    save_debug(screen, "calibrate.png")
    if cb: cb(f"  Screen: {w}x{h}")

    # Tìm teal buttons
    hsv = cv2.cvtColor(screen, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array([75, 120, 150]), np.array([100, 255, 255]))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    saved = 0
    for c in contours:
        x, y, bw, bh = cv2.boundingRect(c)
        area = cv2.contourArea(c)
        if area < 300 or bw < 40 or bw > 200:
            continue

        pad = 5
        crop = screen[max(0,y-pad):y+bh+pad, max(0,x-pad):x+bw+pad]

        if y < h * 0.05 and saved == 0:
            cv2.imwrite(os.path.join(TEMPLATE_DIR, "export_btn.png"), crop)
            if cb: cb(f"  Saved export_btn.png ({x},{y}) {bw}x{bh}")
            saved += 1
        elif y > h * 0.4 and y < h - 60 and saved <= 1:
            cv2.imwrite(os.path.join(TEMPLATE_DIR, "dialog_export.png"), crop)
            if cb: cb(f"  Saved dialog_export.png ({x},{y}) {bw}x{bh}")
            saved += 1

    if saved == 0:
        if cb: cb("  No teal buttons found! Open CapCut editor + Export dialog first.")
        return False

    if cb: cb(f"  Calibration done! ({saved} templates)")
    return True


def has_templates():
    return os.path.isfile(os.path.join(TEMPLATE_DIR, "export_btn.png"))


# ═══════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════
def get_capcut_exe():
    base = os.path.join(os.environ.get("LOCALAPPDATA", ""), "CapCut", "Apps")
    if not os.path.isdir(base): return ""
    for d in sorted(os.listdir(base), reverse=True):
        exe = os.path.join(base, d, "CapCut.exe")
        if os.path.isfile(exe): return exe
    return ""


def kill_capcut(cb=None):
    if cb: cb("  Kill CapCut...")
    os.system('taskkill /F /IM CapCut.exe >nul 2>&1')
    os.system('taskkill /F /IM VEDetector.exe >nul 2>&1')
    os.system('taskkill /F /IM VEHelper.exe >nul 2>&1')
    time.sleep(3)


def promote_project(draft, cb=None):
    try:
        draft_root = draft.get("draft_root_path", "") or os.path.dirname(draft.get("draft_fold_path", ""))
        meta_path = os.path.join(draft_root, "root_meta_info.json")
        if not os.path.isfile(meta_path): return False
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        target = draft.get("draft_name", "")
        max_t = max((d.get("tm_draft_modified", 0) for d in meta["all_draft_store"]), default=0)
        for d in meta["all_draft_store"]:
            if d.get("draft_name") == target:
                d["tm_draft_modified"] = max_t + 1000000; break
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False)
        if cb: cb(f"  Promoted '{target}'")
        return True
    except Exception as e:
        if cb: cb(f"  Promote error: {e}"); return False


def _find_project_pos(screen, cb=None):
    """Tìm project đầu tiên trên trang Home."""
    h, w = screen.shape[:2]
    gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
    for y in range(int(h * 0.25), int(h * 0.50), 2):
        row = gray[y, int(w * 0.08):int(w * 0.20)]
        if np.sum(row > 180) > 20:
            cx = int(w * 0.12)
            cy = y + int(h * 0.06)
            if cb: cb(f"  Projects at y={y}, thumb at ({cx},{cy})")
            return (cx, cy)
    return None


def _find_teal_top(screen):
    """Tìm nút teal ở top 5% (Export button trên toolbar)."""
    h, w = screen.shape[:2]
    hsv = cv2.cvtColor(screen, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array([75, 120, 150]), np.array([100, 255, 255]))
    # Chỉ search top 5%
    mask[int(h*0.05):, :] = 0
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in contours:
        x, y, bw, bh = cv2.boundingRect(c)
        if cv2.contourArea(c) > 300 and 40 < bw < 200:
            return (x + bw // 2, y + bh // 2)
    return None


def _find_teal_dialog(screen):
    """Tìm nút teal ở vùng dialog (40-90% height)."""
    h, w = screen.shape[:2]
    hsv = cv2.cvtColor(screen, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array([75, 120, 150]), np.array([100, 255, 255]))
    mask[:int(h*0.4), :] = 0
    mask[int(h*0.9):, :] = 0
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in contours:
        x, y, bw, bh = cv2.boundingRect(c)
        if cv2.contourArea(c) > 300 and 40 < bw < 200:
            return (x + bw // 2, y + bh // 2)
    return None


def wait_render_complete(export_path, timeout=3600, cb=None):
    existing = set(os.listdir(export_path)) if os.path.isdir(export_path) else set()
    start = time.time()
    while time.time() - start < timeout:
        time.sleep(5)
        if os.path.isdir(export_path):
            new = set(os.listdir(export_path)) - existing
            vids = [f for f in new if f.lower().endswith(('.mp4','.mov','.avi','.mkv')) and not f.endswith('.tmp')]
            if vids:
                fp = os.path.join(export_path, vids[0])
                s1 = os.path.getsize(fp); time.sleep(3); s2 = os.path.getsize(fp)
                if s1 == s2 and s1 > 0:
                    if cb: cb(f"  DONE! {vids[0]} ({s2//1024//1024}MB)")
                    return True
        elapsed = int(time.time() - start)
        if cb and elapsed % 15 == 0: cb(f"  Rendering... {elapsed}s")
    return False


# ═══════════════════════════════════════════════════════════════
#  Main Render (giống flow đối thủ)
# ═══════════════════════════════════════════════════════════════
def render_project(draft, config, tool_window=None, callback=None):
    name = draft.get("draft_name", "")
    if not name: return False, "No project name"
    cb = callback

    try:
        # === 1. Kill + promote ===
        if cb: cb("[1] Kill CapCut + promote")
        kill_capcut(cb)
        promote_project(draft, cb)

        # === 2. Minimize tool (thu nhỏ xuống taskbar) ===
        if tool_window:
            if cb: cb("[2] Minimizing tool to taskbar...")
            tool_window.after(0, tool_window.iconify)
            time.sleep(2)

        # === 3. Mở CapCut ===
        exe = get_capcut_exe()
        if not exe: return False, "CapCut.exe not found"
        if cb: cb("[3] Opening CapCut...")
        subprocess.Popen([exe])

        # === 4. Đợi CapCut loaded (loop chụp mss → check dark >70%) ===
        if cb: cb("[4] Waiting CapCut to load...")
        loaded = False
        for i in range(40):  # max 80s
            time.sleep(2)
            screen = capture_screen()
            gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
            dp = np.sum(gray < 40) / gray.size * 100
            if i % 5 == 0:
                save_debug(screen, f"03_wait_{i:02d}.png")
                if cb: cb(f"  [{i*2}s] dark={dp:.0f}%")
            if dp > 70:
                loaded = True
                save_debug(screen, "03_loaded.png")
                if cb: cb(f"  Loaded! dark={dp:.0f}%")
                time.sleep(5)  # extra wait cho UI render xong
                break
        if not loaded:
            return False, "CapCut failed to load"

        # === 4. Close popups (Escape) ===
        if cb: cb("[5] Close popups (Escape)")
        import pyautogui
        pyautogui.press('escape')
        time.sleep(1)
        pyautogui.press('escape')
        time.sleep(2)

        # === 5. Chụp + tìm project ===
        if cb: cb("[6] Finding project...")
        screen = capture_screen()
        save_debug(screen, "05_find_project.png")
        pos = _find_project_pos(screen, cb)
        if not pos:
            return False, "Cannot find project on screen"

        # === 6. Click project ===
        if cb: cb(f"[7] Double-click project")
        double_click_at(pos[0], pos[1], cb)

        # === 7. Đợi editor (loop: chụp → tìm Export teal ở top) ===
        if cb: cb("[8] Waiting editor (Export button)...")
        export_pos = None
        for i in range(30):  # max 60s
            time.sleep(2)
            screen = capture_screen()
            if i % 5 == 0:
                save_debug(screen, f"07_editor_{i:02d}.png")

            # Method 1: template matching
            if has_templates():
                export_pos = find_template(screen, os.path.join(TEMPLATE_DIR, "export_btn.png"), 0.7)
                if export_pos:
                    if cb: cb(f"  Template match! ({export_pos[0]},{export_pos[1]})")
                    break

            # Method 2: color detection
            export_pos = _find_teal_top(screen)
            if export_pos:
                if cb: cb(f"  Teal detected! ({export_pos[0]},{export_pos[1]})")
                save_debug(screen, "07_editor_ready.png")
                break

            if cb and i % 3 == 0: cb(f"  [{i*2}s] waiting...")

        if not export_pos:
            save_debug(capture_screen(), "07_fail.png")
            return False, "Export button not found"

        # === 8. Click Export ===
        if cb: cb(f"[9] Click Export")
        click_at(export_pos[0], export_pos[1], cb)
        time.sleep(4)

        # === 9. Tìm dialog Export ===
        if cb: cb("[10] Finding dialog Export...")
        screen = capture_screen()
        save_debug(screen, "09_dialog.png")

        dialog_pos = None
        # Template first
        if os.path.isfile(os.path.join(TEMPLATE_DIR, "dialog_export.png")):
            dialog_pos = find_template(screen, os.path.join(TEMPLATE_DIR, "dialog_export.png"), 0.7)
        # Color fallback
        if not dialog_pos:
            dialog_pos = _find_teal_dialog(screen)

        if not dialog_pos:
            # Retry
            time.sleep(3)
            screen = capture_screen()
            save_debug(screen, "09_retry.png")
            dialog_pos = _find_teal_dialog(screen)

        if not dialog_pos:
            if cb:
                btns = []
                hsv = cv2.cvtColor(screen, cv2.COLOR_BGR2HSV)
                mask = cv2.inRange(hsv, np.array([75,120,150]), np.array([100,255,255]))
                cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                for c in cnts:
                    x,y,w,h = cv2.boundingRect(c)
                    if cv2.contourArea(c) > 200:
                        cb(f"  Teal: ({x},{y}) {w}x{h} area={cv2.contourArea(c):.0f}")
            return False, "Dialog Export not found"

        # === 10. Click dialog Export ===
        if cb: cb(f"[11] Click dialog Export")
        click_at(dialog_pos[0], dialog_pos[1], cb)
        time.sleep(3)

        # === 11. Wait render ===
        if cb: cb("[12] Waiting render...")
        ok = wait_render_complete(config.export_path, timeout=3600, cb=cb)
        if not ok: return False, "Render timeout"

        time.sleep(2)
        kill_capcut(cb)
        return True, f"Rendered: {name}"

    except Exception as e:
        import traceback
        if cb: cb(f"EXCEPTION: {traceback.format_exc()}")
        kill_capcut()
        return False, f"Error: {e}"

    finally:
        # Restore tool window
        if tool_window:
            tool_window.after(0, tool_window.deiconify)


def shutdown_pc():
    os.system('shutdown /s /t 30 /c "AutoCapCut: Render complete."')
