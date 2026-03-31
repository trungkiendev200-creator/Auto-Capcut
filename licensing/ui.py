"""License activation dialog."""

import customtkinter as ctk
from ui.theme import COLORS as C, FONT
from licensing import client


class ActivationDialog:
    """Hiện dialog nhập key. Trả về True nếu activated, False nếu user đóng."""

    def __init__(self, parent=None):
        self.activated = False

        self.window = ctk.CTkToplevel(parent) if parent else ctk.CTk()
        self.window.title("Auto CapCut - Activation")
        self.window.geometry("420x280")
        self.window.resizable(False, False)
        self.window.configure(fg_color=C["bg"])

        # Center on screen
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() - 420) // 2
        y = (self.window.winfo_screenheight() - 280) // 2
        self.window.geometry(f"420x280+{x}+{y}")

        self._build()

        if parent:
            self.window.transient(parent)
            self.window.grab_set()
            self.window.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build(self):
        w = self.window

        # Header
        ctk.CTkLabel(
            w, text="Auto CapCut", font=("Segoe UI", 22, "bold"),
            text_color=C["primary"]
        ).pack(pady=(25, 5))

        ctk.CTkLabel(
            w, text="Nhập License Key để kích hoạt",
            font=FONT["body"], text_color=C["text_light"]
        ).pack(pady=(0, 15))

        # Key entry
        self.key_var = ctk.StringVar()
        self.key_entry = ctk.CTkEntry(
            w, textvariable=self.key_var, width=320, height=40,
            placeholder_text="XXXX-XXXX-XXXX-XXXX",
            fg_color=C["card"], border_color=C["input_border"],
            text_color=C["text"], corner_radius=8,
            font=("Consolas", 14),
        )
        self.key_entry.pack(pady=(0, 10))

        # Status label
        self.status = ctk.CTkLabel(
            w, text="", font=FONT["small"], text_color=C["text_light"], height=20
        )
        self.status.pack(pady=(0, 10))

        # Activate button
        self.btn = ctk.CTkButton(
            w, text="Kích hoạt", width=200, height=42, corner_radius=10,
            fg_color=C["primary"], hover_color=C["primary_hover"],
            font=FONT["body_bold"], text_color=C["text_white"],
            command=self._on_activate,
        )
        self.btn.pack()

    def _on_activate(self):
        key = self.key_var.get().strip()
        if not key:
            self.status.configure(text="Vui lòng nhập key!", text_color=C["red"])
            return

        self.btn.configure(state="disabled", text="Đang kiểm tra...")
        self.status.configure(text="Đang kết nối server...", text_color=C["text_light"])
        self.window.update()

        ok, msg = client.activate(key)

        if ok:
            self.status.configure(text=msg, text_color=C["green"])
            self.activated = True
            self.window.after(800, self.window.destroy)
        else:
            self.status.configure(text=msg, text_color=C["red"])
            self.btn.configure(state="normal", text="Kích hoạt")

    def _on_close(self):
        self.activated = False
        self.window.destroy()

    def wait(self) -> bool:
        """Block until dialog closes. Returns True if activated."""
        self.window.wait_window()
        return self.activated


def show_activation_dialog(parent=None) -> bool:
    """Show activation dialog. Returns True if successfully activated."""
    dialog = ActivationDialog(parent)
    return dialog.wait()
