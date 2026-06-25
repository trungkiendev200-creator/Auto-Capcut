"""Tab Import Data — import audio + ảnh/video (map theo số) vào 1 project CapCut
ĐÃ TẠO SẴN (do người dùng tạo trong CapCut, đã tắt main-track magnet bằng phím P).

Tool chỉ thay tracks/materials/duration trong draft của project đã chọn, giữ nguyên
mọi setting khác → tránh việc magnet hút dồn ảnh khi mở.
"""

import os
import threading
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox

from ui.theme import COLORS as C, FONT
from core import create_bck_engine as bck


class BanContentTab:
    """Tab Import Data (import vào project có sẵn)."""

    def __init__(self, parent: ctk.CTkFrame, app):
        self.app = app
        self._build(parent)

    def _build(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(expand=True, fill="both", padx=10, pady=6)
        frame.grid_rowconfigure(2, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        card = ctk.CTkFrame(frame, fg_color=C["card"], corner_radius=8,
                            border_width=1, border_color=C["border"])
        card.grid(row=0, column=0, sticky="ew")
        f = ctk.CTkFrame(card, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=10, pady=8)

        ctk.CTkLabel(
            f,
            text="Import audio + ảnh/video (map theo SỐ tên file) vào 1 project ĐÃ TẠO SẴN.\n"
                 "Các bước: (1) Trong CapCut tạo project rỗng + bấm P tắt main-track magnet → "
                 "thoát CapCut. (2) Tick chọn project đó ở panel phải. (3) Chọn Source edit + Import.\n"
                 "Câu audio không có ảnh/video cùng số → để trống.",
            font=("Segoe UI", 10), text_color=C["text_light"],
            justify="left", wraplength=560,
        ).pack(anchor="w", pady=(0, 8))

        # Source edit folder
        r = ctk.CTkFrame(f, fg_color="transparent")
        r.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(r, text="Source edit:", width=110, anchor="w",
                     font=FONT["small"], text_color=C["text_light"]).pack(side="left")
        self.bck_source_var = ctk.StringVar()
        ctk.CTkEntry(r, textvariable=self.bck_source_var, height=28,
                     fg_color=C["input_bg"], border_color=C["input_border"],
                     text_color=C["text"], corner_radius=6, font=FONT["small"]
                     ).pack(side="left", fill="x", expand=True, padx=(4, 4))
        ctk.CTkButton(r, text="...", width=28, height=28, corner_radius=6,
                      fg_color=C["tab_bg"], text_color=C["text"],
                      hover_color=C["primary_muted"], border_width=1,
                      border_color=C["input_border"], font=FONT["small"],
                      command=lambda: self._browse_dir_to(self.bck_source_var)
                      ).pack(side="left")

        # Settings: vị trí intro
        sett = ctk.CTkFrame(f, fg_color=C["primary_light"], corner_radius=6)
        sett.pack(fill="x", pady=(8, 6))
        s = ctk.CTkFrame(sett, fg_color="transparent")
        s.pack(fill="x", padx=10, pady=8)
        ctk.CTkLabel(s, text="Vị trí intro:", font=FONT["small"],
                     text_color=C["text"]).pack(side="left")
        self.bck_intro_mode_var = tk.StringVar(value="Chèn lên audio")
        ctk.CTkSegmentedButton(
            s, values=["Chèn lên audio", "Không chèn lên audio"],
            variable=self.bck_intro_mode_var, height=28,
            font=FONT["small"], fg_color=C["card"],
            selected_color=C["primary"], selected_hover_color=C["primary_hover"],
            unselected_color=C["card"], text_color=C["text"],
        ).pack(side="left", padx=(6, 0))

        self.bck_btn = ctk.CTkButton(
            f, text="Import vào project đã chọn", height=36, corner_radius=8,
            fg_color=C["green"], hover_color="#16a34a",
            text_color=C["text_white"], font=FONT["button"],
            command=self._on_import
        )
        self.bck_btn.pack(fill="x", pady=(2, 0))

        # Info bar
        self.info = ctk.CTkLabel(
            frame, text="Tick 1 project ở panel phải + chọn Source edit rồi Import",
            font=FONT["small"], text_color=C["text_light"],
            fg_color=C["primary_light"], corner_radius=6, height=26
        )
        self.info.grid(row=1, column=0, sticky="ew", pady=(4, 2))

        # Log
        self.log = ctk.CTkTextbox(
            frame, height=140, fg_color=C["input_bg"],
            border_color=C["input_border"], border_width=1,
            corner_radius=6, text_color=C["text"], font=FONT["mono"]
        )
        self.log.grid(row=2, column=0, sticky="nsew", pady=(2, 0))
        self.log.configure(state="disabled")

    # ── helpers ─────────────────────────────────────────────────────
    def _append_log(self, text: str):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _set_info(self, text: str, bg: str, fg: str):
        self.info.configure(text=text, fg_color=bg, text_color=fg)

    def _browse_dir_to(self, var):
        path = filedialog.askdirectory()
        if path:
            var.set(path)

    # ── handler ─────────────────────────────────────────────────────
    def _on_import(self):
        source = self.bck_source_var.get().strip()
        if not source or not os.path.isdir(source):
            self._set_info("Source edit không hợp lệ!", C["red_light"], C["red"])
            return

        selected = self.app.project_list.get_selected()
        if not selected:
            self._set_info("Chưa tick project nào ở panel phải!",
                           C["red_light"], C["red"])
            return
        if len(selected) > 1:
            self._set_info("Chỉ chọn 1 project để import!", C["red_light"], C["red"])
            return

        _, draft = selected[0]
        folder = draft.get("draft_fold_path", "")
        name = draft.get("draft_name", "?")
        if not folder or not os.path.isdir(folder):
            self._set_info(f"Không tìm thấy folder project '{name}'!",
                           C["red_light"], C["red"])
            return

        over = self.bck_intro_mode_var.get() == "Chèn lên audio"

        confirm = messagebox.askokcancel(
            "Import Data",
            f"Import data vào project '{name}'?\n\n"
            f"Intro: {'ĐÈ lên audio' if over else 'ĐẨY (chèn trước audio)'}\n\n"
            "⚠ Nội dung timeline hiện tại của project sẽ bị THAY THẾ.\n"
            "Đảm bảo đã tắt main-track magnet (P) và thoát CapCut.\nOK?"
        )
        if not confirm:
            return

        self.bck_btn.configure(state="disabled", text="Đang import...")
        self._set_info(f"Đang import vào '{name}'...",
                       C["primary_light"], C["primary"])
        threading.Thread(
            target=self._run_import,
            args=(folder, source, over),
            daemon=True,
        ).start()

    def _run_import(self, folder, source, over):
        root = self.app.root

        def cb(msg):
            root.after(0, self._append_log, msg)

        try:
            r = bck.import_into_project(
                project_folder=folder,
                source_edit_dir=source,
                insert_over_audio=over,
                callback=cb,
            )
        except Exception:
            import traceback
            cb(f"[EXCEPTION] {traceback.format_exc()}")
            r = bck.BckResult(False, "Exception khi import")

        if r.success:
            summary = (f"Done: {r.n_audio} audio, {r.n_intro} intro, "
                       f"{r.n_image} ảnh, {r.n_video_edit} vedit, "
                       f"{r.n_empty} trống, "
                       f"{r.total_duration_us/1_000_000:.0f}s")
            bg, fg = C["green_light"], C["green"]
        else:
            summary = f"FAIL: {r.message}"
            bg, fg = C["red_light"], C["red"]
        cb(f"══ {summary} ══")
        root.after(0, self._set_info, summary, bg, fg)
        root.after(0, lambda: self.bck_btn.configure(
            state="normal", text="Import vào project đã chọn"))
        root.after(0, lambda: self.app.status_var.set(f"  {summary}"))
