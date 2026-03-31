"""Auto CapCut — Entry point."""

import sys
import os
import threading

sys.path.insert(0, os.path.dirname(__file__))

from version import __version__
from licensing import client, storage
from core.settings import get_app_data_dir, get_bundle_dir


def main():
    _load_api_config()

    # Check license
    if not client.is_licensed():
        import customtkinter as ctk
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        from licensing.ui import show_activation_dialog
        root = ctk.CTk()
        root.withdraw()
        if not show_activation_dialog(root):
            sys.exit(0)
        root.destroy()

    # Launch app
    icon_path = _get_icon_path()
    from ui.app import AutoCapcut
    app = AutoCapcut()
    if icon_path and os.path.isfile(icon_path):
        try:
            app.root.iconbitmap(icon_path)
        except Exception:
            pass
    app.root.title(f"Auto CapCut v{__version__}")

    # Check update in background
    threading.Thread(target=_check_update, args=(app,), daemon=True).start()

    app.run()


def _check_update(app):
    """Check GitHub Releases for new version. Hiện thông báo nếu có update."""
    try:
        from updater.checker import check_for_update
        from updater.replacer import download_update, apply_update
        from tkinter import messagebox

        update = check_for_update()
        if not update:
            return

        new_ver = update["version"]
        url = update["download_url"]

        def ask():
            answer = messagebox.askyesno(
                "Có bản cập nhật mới!",
                f"Phiên bản mới: v{new_ver}\n"
                f"Phiên bản hiện tại: v{__version__}\n\n"
                f"Bạn có muốn cập nhật ngay không?"
            )
            if answer:
                app.status_var.set(f"  Đang tải bản cập nhật v{new_ver}...")
                threading.Thread(
                    target=_do_update, args=(app, url, new_ver), daemon=True
                ).start()

        app.root.after(2000, ask)  # Đợi 2s cho app load xong

    except Exception:
        pass


def _do_update(app, url, new_ver):
    """Download và apply update."""
    try:
        from updater.replacer import download_update, apply_update

        def on_progress(pct):
            app.root.after(0, lambda: app.status_var.set(
                f"  Đang tải v{new_ver}... {int(pct*100)}%"
            ))

        new_exe = download_update(url, progress_callback=on_progress)

        if getattr(sys, "frozen", False):
            # .exe mode: tự thay thế
            app.root.after(0, lambda: app.status_var.set("  Đang cập nhật, app sẽ khởi động lại..."))
            app.root.after(1000, lambda: apply_update(new_exe))
        else:
            # Dev mode: chỉ thông báo
            from tkinter import messagebox
            app.root.after(0, lambda: messagebox.showinfo(
                "Cập nhật", f"Đã tải v{new_ver} xong!\nFile: {new_exe}"
            ))
    except Exception as e:
        app.root.after(0, lambda: app.status_var.set(f"  Lỗi cập nhật: {e}"))


def _load_api_config():
    config_path = os.path.join(get_app_data_dir(), "api_config.json")
    if os.path.isfile(config_path):
        import json
        try:
            with open(config_path, "r") as f:
                cfg = json.load(f)
            if cfg.get("license_api_url"):
                client.set_api_url(cfg["license_api_url"])
        except Exception:
            pass


def _get_icon_path() -> str:
    bundled = os.path.join(get_bundle_dir(), "assets", "icon.ico")
    if os.path.isfile(bundled):
        return bundled
    cached = os.path.join(get_app_data_dir(), "icon.ico")
    if os.path.isfile(cached):
        return cached
    return ""


if __name__ == "__main__":
    main()
