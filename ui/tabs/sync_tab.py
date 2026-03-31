"""Tab Đồng bộ âm thanh."""

import os
import threading
import customtkinter as ctk
from tkinter import messagebox

from ui.theme import COLORS as C, FONT
from core import sync_engine


class SyncTab:
    """Builds and manages the Sync Audio tab."""

    VIDEO_MODES = {
        "Cắt Video (Cut)": sync_engine.VIDEO_MODE_CUT,
        "Điều chỉnh Speed": sync_engine.VIDEO_MODE_SPEED,
    }

    def __init__(self, parent: ctk.CTkFrame, app):
        self.app = app
        self._build(parent)

    def _build(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(expand=True, fill="both", padx=16, pady=10)

        # Title
        ctk.CTkLabel(
            frame, text="Đồng bộ âm thanh",
            font=FONT["heading"], text_color=C["text"]
        ).pack(anchor="w", pady=(0, 4))

        ctk.CTkLabel(
            frame,
            text="Điều chỉnh thời lượng ảnh/video khớp với audio tương ứng. Audio là chuẩn.",
            font=FONT["small"], text_color=C["text_light"], justify="left"
        ).pack(anchor="w", pady=(0, 12))

        # Video mode option
        mode_row = ctk.CTkFrame(frame, fg_color=C["primary_light"], corner_radius=8)
        mode_row.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            mode_row, text="Nếu video dài hơn âm thanh:",
            font=FONT["body"], text_color=C["text"]
        ).pack(side="left", padx=(12, 8), pady=10)

        self.mode_var = ctk.StringVar(value="Cắt Video (Cut)")
        self.mode_dropdown = ctk.CTkOptionMenu(
            mode_row, variable=self.mode_var,
            values=list(self.VIDEO_MODES.keys()),
            width=180, height=32, corner_radius=8,
            fg_color=C["card"], button_color=C["primary"],
            button_hover_color=C["primary_hover"],
            dropdown_fg_color=C["card"],
            dropdown_hover_color=C["primary_light"],
            text_color=C["text"],
            dropdown_text_color=C["text"],
            font=FONT["small"],
        )
        self.mode_dropdown.pack(side="left", padx=(0, 12), pady=10)

        # Info box
        self.info = ctk.CTkLabel(
            frame, text="Chọn project bên phải rồi bấm Đồng bộ",
            font=FONT["body"], text_color=C["text_light"],
            fg_color=C["primary_light"], corner_radius=8, height=36
        )
        self.info.pack(fill="x", pady=(0, 8))

        # Log
        self.log = ctk.CTkTextbox(
            frame, height=80, fg_color=C["input_bg"],
            border_color=C["input_border"], border_width=1,
            corner_radius=8, text_color=C["text"], font=FONT["mono"]
        )
        self.log.pack(fill="both", expand=True, pady=(0, 10))
        self.log.configure(state="disabled")

        # Button
        self.btn = ctk.CTkButton(
            frame, text="Đồng bộ âm thanh", height=42, corner_radius=10,
            fg_color=C["primary"], hover_color=C["primary_hover"],
            font=FONT["button"], text_color=C["text_white"],
            command=self._on_click
        )
        self.btn.pack(fill="x")

    def _append_log(self, text: str):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _set_info(self, text: str, bg: str, fg: str):
        self.info.configure(text=text, fg_color=bg, text_color=fg)

    def _get_video_mode(self) -> str:
        return self.VIDEO_MODES.get(self.mode_var.get(), sync_engine.VIDEO_MODE_CUT)

    def _on_click(self):
        selected = self.app.project_list.get_selected()
        if not selected:
            self._set_info("Chưa chọn project nào!", C["red_light"], C["red"])
            return

        confirm = messagebox.askokcancel(
            "Cảnh báo",
            "Vui lòng thoát khỏi dự án trong CapCut trước khi đồng bộ!\n\n"
            "Nếu CapCut đang mở dự án, file có thể bị ghi đè.\n\n"
            "Bấm OK nếu đã thoát CapCut."
        )
        if not confirm:
            return

        self.btn.configure(state="disabled", text="Đang xử lý...")
        self._set_info(
            f"Đang đồng bộ {len(selected)} project...",
            C["primary_light"], C["primary"]
        )

        video_mode = self._get_video_mode()
        threading.Thread(
            target=self._run, args=(selected, video_mode), daemon=True
        ).start()

    def _run(self, selected: list[tuple[int, dict]], video_mode: str):
        root = self.app.root
        total_ok = 0
        total_fail = 0

        for idx, draft in selected:
            name = draft.get("draft_name", "?")
            path = draft.get("draft_fold_path", "")

            if not path or not os.path.isdir(path):
                root.after(0, self._append_log, f"[SKIP] {name}: folder not found")
                root.after(0, self.app.project_list.set_status, idx, "Error", C["red"])
                total_fail += 1
                continue

            root.after(0, self._append_log, f"[SYNC] {name}...")
            root.after(0, self.app.project_list.set_status, idx, "...", C["primary"])

            try:
                result = sync_engine.sync_project(
                    path, video_mode=video_mode, backup=True
                )
            except Exception as e:
                result = sync_engine.SyncResult(False, str(e))

            if result.success:
                root.after(0, self._append_log, f"  OK: {result.message}")
                root.after(0, self.app.project_list.set_status, idx, "Done", C["green"])
                total_ok += 1
            else:
                root.after(0, self._append_log, f"  FAIL: {result.message}")
                root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])
                total_fail += 1

        summary = f"Hoàn tất: {total_ok} OK, {total_fail} lỗi"
        color = C["green"] if total_fail == 0 else C["red"]
        light = C["green_light"] if total_fail == 0 else C["red_light"]
        root.after(0, lambda: self._set_info(summary, light, color))
        root.after(0, lambda: self.btn.configure(state="normal", text="Đồng bộ âm thanh"))
        root.after(0, lambda: self.app.status_var.set(f"  {summary}"))
