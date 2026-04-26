"""Tab Create Project 2 — các chức năng tạo project mở rộng."""

import os
import threading
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox

from ui.theme import COLORS as C, FONT
from core import create_project as cp


class CreateProject2Tab:
    """Tab Create Project 2 với các sub-tab tạo project theo nguồn khác nhau."""

    def __init__(self, parent: ctk.CTkFrame, app):
        self.app = app
        self._build(parent)

    def _build(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(expand=True, fill="both", padx=10, pady=6)
        frame.grid_rowconfigure(2, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        # Sub-tabs
        sub_tabs = ctk.CTkTabview(
            frame, fg_color=C["card"], corner_radius=8,
            border_width=1, border_color=C["border"],
            segmented_button_fg_color=C["tab_bg"],
            segmented_button_selected_color=C["primary"],
            segmented_button_selected_hover_color=C["primary_hover"],
            segmented_button_unselected_color=C["tab_bg"],
            segmented_button_unselected_hover_color=C["tab_hover"],
            text_color=C["text"],
        )
        sub_tabs.grid(row=0, column=0, sticky="nsew")

        self._build_from_videos_tab(sub_tabs.add("Base on folder video"))

        # Info bar
        self.info = ctk.CTkLabel(
            frame, text="Chọn folder rồi bấm Tạo dự án",
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

    # ── Sub-tab: Base on folder video ──────────────────────────────
    def _build_from_videos_tab(self, parent):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=10, pady=8)

        ctk.CTkLabel(
            f,
            text="Tool tạo 1 project / file video. Tên project = tên file. "
                 "Project đã tồn tại trong CapCut sẽ skip.",
            font=("Segoe UI", 10), text_color=C["text_light"],
            justify="left", wraplength=520,
        ).pack(anchor="w", pady=(0, 8))

        # Folder picker
        r1 = ctk.CTkFrame(f, fg_color="transparent")
        r1.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(r1, text="Folder video:", width=100, anchor="w",
                     font=FONT["small"], text_color=C["text_light"]).pack(side="left")
        self.video_folder_var = ctk.StringVar()
        ctk.CTkEntry(r1, textvariable=self.video_folder_var, height=28,
                     fg_color=C["input_bg"], border_color=C["input_border"],
                     text_color=C["text"], corner_radius=6, font=FONT["small"]
                     ).pack(side="left", fill="x", expand=True, padx=(4, 4))
        ctk.CTkButton(r1, text="...", width=28, height=28, corner_radius=6,
                      fg_color=C["tab_bg"], text_color=C["text"],
                      hover_color=C["primary_muted"], border_width=1,
                      border_color=C["input_border"], font=FONT["small"],
                      command=self._browse_folder
                      ).pack(side="left")

        # Settings: ratio / quality / fps
        sett = ctk.CTkFrame(f, fg_color=C["primary_light"], corner_radius=6)
        sett.pack(fill="x", pady=(4, 8))
        s = ctk.CTkFrame(sett, fg_color="transparent")
        s.pack(fill="x", padx=10, pady=8)

        ctk.CTkLabel(s, text="Ratio:", font=FONT["small"],
                     text_color=C["text"]).pack(side="left")
        self.ratio_var = tk.StringVar(value="16:9")
        ctk.CTkOptionMenu(s, variable=self.ratio_var,
                          values=["16:9", "9:16", "1:1", "4:3"],
                          width=80, height=28, corner_radius=6,
                          fg_color=C["card"], button_color=C["primary"],
                          text_color=C["text"], font=FONT["small"]
                          ).pack(side="left", padx=(4, 12))

        ctk.CTkLabel(s, text="Quality:", font=FONT["small"],
                     text_color=C["text"]).pack(side="left")
        self.quality_var = tk.StringVar(value="1080p")
        ctk.CTkOptionMenu(s, variable=self.quality_var,
                          values=["1080p", "720p", "4K"],
                          width=80, height=28, corner_radius=6,
                          fg_color=C["card"], button_color=C["primary"],
                          text_color=C["text"], font=FONT["small"]
                          ).pack(side="left", padx=(4, 12))

        ctk.CTkLabel(s, text="FPS:", font=FONT["small"],
                     text_color=C["text"]).pack(side="left")
        self.fps_var = tk.StringVar(value="30")
        ctk.CTkOptionMenu(s, variable=self.fps_var,
                          values=["30", "60"],
                          width=65, height=28, corner_radius=6,
                          fg_color=C["card"], button_color=C["primary"],
                          text_color=C["text"], font=FONT["small"]
                          ).pack(side="left", padx=(4, 0))

        # Button
        self.create_btn = ctk.CTkButton(
            f, text="Tạo dự án", height=36, corner_radius=8,
            fg_color=C["green"], hover_color="#16a34a",
            text_color=C["text_white"], font=FONT["button"],
            command=self._on_create
        )
        self.create_btn.pack(fill="x")

    # ── helpers ─────────────────────────────────────────────────────
    def _append_log(self, text: str):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _set_info(self, text: str, bg: str, fg: str):
        self.info.configure(text=text, fg_color=bg, text_color=fg)

    def _browse_folder(self):
        path = filedialog.askdirectory(title="Chọn folder chứa video")
        if path:
            self.video_folder_var.set(path)

    # ── handler ─────────────────────────────────────────────────────
    def _on_create(self):
        folder = self.video_folder_var.get().strip()
        if not folder or not os.path.isdir(folder):
            self._set_info("Folder không hợp lệ!", C["red_light"], C["red"])
            return

        capcut_path = self.app.capcut_path.get().strip()
        if not capcut_path or not os.path.isdir(capcut_path):
            self._set_info("CapCut path chưa cấu hình!", C["red_light"], C["red"])
            return

        try:
            fps = int(self.fps_var.get())
        except ValueError:
            self._set_info("FPS không hợp lệ!", C["red_light"], C["red"])
            return

        ratio = self.ratio_var.get()
        quality = self.quality_var.get()

        # Quick scan để show số file trong confirm
        video_exts = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".webm"}
        try:
            videos = [f for f in os.listdir(folder)
                      if os.path.isfile(os.path.join(folder, f))
                      and os.path.splitext(f)[1].lower() in video_exts]
        except Exception as e:
            self._set_info(f"Lỗi đọc folder: {e}", C["red_light"], C["red"])
            return

        if not videos:
            self._set_info("Folder không có file video nào!", C["red_light"], C["red"])
            return

        confirm = messagebox.askokcancel(
            "Tạo dự án từ folder video",
            f"Sẽ tạo project cho {len(videos)} video.\n"
            f"Ratio: {ratio} | Quality: {quality} | FPS: {fps}\n\n"
            "Project trùng tên sẽ skip.\n"
            "Thoát CapCut trước khi tiếp tục.\nOK?"
        )
        if not confirm:
            return

        self.create_btn.configure(state="disabled", text="Đang tạo...")
        self._set_info(f"Đang tạo {len(videos)} project...",
                       C["primary_light"], C["primary"])

        threading.Thread(
            target=self._run_create,
            args=(folder, capcut_path, ratio, quality, fps),
            daemon=True
        ).start()

    def _run_create(self, folder, capcut_path, ratio, quality, fps):
        root = self.app.root

        def cb(msg):
            root.after(0, self._append_log, msg)

        try:
            r = cp.batch_create_from_videos(
                folder=folder,
                capcut_path=capcut_path,
                ratio=ratio,
                quality=quality,
                fps=fps,
                callback=cb,
            )
        except Exception as e:
            import traceback
            cb(f"[EXCEPTION] {traceback.format_exc()}")
            r = cp.BatchResult()

        summary = (f"Done: {r.created}/{r.total} created, "
                   f"{len(r.skipped)} skipped")
        cb(f"══ {summary} ══")

        bg = C["green_light"] if r.created > 0 and not r.skipped else (
            C["red_light"] if r.created == 0 else C["primary_light"])
        fg = C["green"] if r.created > 0 and not r.skipped else (
            C["red"] if r.created == 0 else C["primary"])
        root.after(0, self._set_info, summary, bg, fg)
        root.after(0, lambda: self.create_btn.configure(
            state="normal", text="Tạo dự án"))
        root.after(0, lambda: self.app.status_var.set(f"  {summary}"))

        # Refresh project list để thấy project mới
        if r.created > 0:
            root.after(0, self.app._load_projects)
