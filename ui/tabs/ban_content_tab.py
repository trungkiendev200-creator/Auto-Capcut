"""Tab Bán Content — tạo 1 project CapCut từ source edit + stock (Create bck).

Import audio nối tiếp → chèn video intro (theo số tên file) → đắp video edit + ảnh
đồng bộ audio (video dài→cắt, ngắn→chỉnh speed) → lấp quãng trống bằng stock
(65% ngắn / 35% dài cắt 4-10s). Tổng video = tổng audio.
"""

import os
import threading
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox

from ui.theme import COLORS as C, FONT
from core import create_bck_engine as bck


class BanContentTab:
    """Tab Bán Content (tách từ sub-tab Create bck)."""

    def __init__(self, parent: ctk.CTkFrame, app):
        self.app = app
        self._build(parent)

    def _build(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(expand=True, fill="both", padx=10, pady=6)
        frame.grid_rowconfigure(2, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        # Form card
        f = ctk.CTkFrame(frame, fg_color=C["card"], corner_radius=8,
                         border_width=1, border_color=C["border"])
        f.grid(row=0, column=0, sticky="ew")
        f = self._pad(f)

        ctk.CTkLabel(
            f,
            text="Tạo 1 project: import audio nối tiếp → chèn video intro (theo số tên file) "
                 "→ đắp video edit + ảnh đồng bộ audio (video dài→cắt, ngắn→chỉnh speed). "
                 "Đoạn audio không khớp thư mục nào trong source edit → để TRỐNG. "
                 "(video intro/video edit có thể rỗng)",
            font=("Segoe UI", 10), text_color=C["text_light"],
            justify="left", wraplength=560,
        ).pack(anchor="w", pady=(0, 8))

        def _folder_row(label):
            r = ctk.CTkFrame(f, fg_color="transparent")
            r.pack(fill="x", pady=(0, 4))
            ctk.CTkLabel(r, text=label, width=110, anchor="w",
                         font=FONT["small"], text_color=C["text_light"]).pack(side="left")
            var = ctk.StringVar()
            ctk.CTkEntry(r, textvariable=var, height=28,
                         fg_color=C["input_bg"], border_color=C["input_border"],
                         text_color=C["text"], corner_radius=6, font=FONT["small"]
                         ).pack(side="left", fill="x", expand=True, padx=(4, 4))
            ctk.CTkButton(r, text="...", width=28, height=28, corner_radius=6,
                          fg_color=C["tab_bg"], text_color=C["text"],
                          hover_color=C["primary_muted"], border_width=1,
                          border_color=C["input_border"], font=FONT["small"],
                          command=lambda: self._browse_dir_to(var)
                          ).pack(side="left")
            return var

        # Project name
        r0 = ctk.CTkFrame(f, fg_color="transparent")
        r0.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(r0, text="Tên dự án:", width=110, anchor="w",
                     font=FONT["small"], text_color=C["text_light"]).pack(side="left")
        self.bck_name_var = ctk.StringVar()
        ctk.CTkEntry(r0, textvariable=self.bck_name_var, height=28,
                     fg_color=C["input_bg"], border_color=C["input_border"],
                     text_color=C["text"], corner_radius=6, font=FONT["small"]
                     ).pack(side="left", fill="x", expand=True, padx=(4, 0))

        self.bck_source_var = _folder_row("Source edit:")

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

        # Settings: ratio / quality / fps
        sett2 = ctk.CTkFrame(f, fg_color=C["primary_light"], corner_radius=6)
        sett2.pack(fill="x", pady=(0, 8))
        s2 = ctk.CTkFrame(sett2, fg_color="transparent")
        s2.pack(fill="x", padx=10, pady=8)
        ctk.CTkLabel(s2, text="Ratio:", font=FONT["small"],
                     text_color=C["text"]).pack(side="left")
        self.bck_ratio_var = tk.StringVar(value="16:9")
        ctk.CTkOptionMenu(s2, variable=self.bck_ratio_var,
                          values=["16:9", "9:16", "1:1", "4:3"],
                          width=75, height=28, corner_radius=6,
                          fg_color=C["card"], button_color=C["primary"],
                          text_color=C["text"], font=FONT["small"]
                          ).pack(side="left", padx=(4, 12))
        ctk.CTkLabel(s2, text="Quality:", font=FONT["small"],
                     text_color=C["text"]).pack(side="left")
        self.bck_quality_var = tk.StringVar(value="1080p")
        ctk.CTkOptionMenu(s2, variable=self.bck_quality_var,
                          values=["1080p", "720p", "4K"],
                          width=80, height=28, corner_radius=6,
                          fg_color=C["card"], button_color=C["primary"],
                          text_color=C["text"], font=FONT["small"]
                          ).pack(side="left", padx=(4, 12))
        ctk.CTkLabel(s2, text="FPS:", font=FONT["small"],
                     text_color=C["text"]).pack(side="left")
        self.bck_fps_var = tk.StringVar(value="30")
        ctk.CTkOptionMenu(s2, variable=self.bck_fps_var,
                          values=["30", "60"],
                          width=60, height=28, corner_radius=6,
                          fg_color=C["card"], button_color=C["primary"],
                          text_color=C["text"], font=FONT["small"]
                          ).pack(side="left", padx=(4, 0))

        self.bck_btn = ctk.CTkButton(
            f, text="Tạo dự án", height=36, corner_radius=8,
            fg_color=C["green"], hover_color="#16a34a",
            text_color=C["text_white"], font=FONT["button"],
            command=self._on_create_bck
        )
        self.bck_btn.pack(fill="x")

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

    # ── helpers ─────────────────────────────────────────────────────
    def _pad(self, card):
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=10, pady=8)
        return inner

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
    def _on_create_bck(self):
        name = self.bck_name_var.get().strip()
        if not name:
            self._set_info("Chưa nhập tên dự án!", C["red_light"], C["red"])
            return
        if any(c in name for c in '<>:"/\\|?*'):
            self._set_info('Tên chứa ký tự không hợp lệ < > : " / \\ | ? *',
                           C["red_light"], C["red"])
            return

        source = self.bck_source_var.get().strip()
        if not source or not os.path.isdir(source):
            self._set_info("Source edit không hợp lệ!", C["red_light"], C["red"])
            return

        capcut_path = self.app.capcut_path.get().strip()
        if not capcut_path or not os.path.isdir(capcut_path):
            self._set_info("CapCut path chưa cấu hình!", C["red_light"], C["red"])
            return

        try:
            fps = int(self.bck_fps_var.get())
        except ValueError:
            self._set_info("FPS không hợp lệ!", C["red_light"], C["red"])
            return

        over = self.bck_intro_mode_var.get() == "Chèn lên audio"
        ratio = self.bck_ratio_var.get()
        quality = self.bck_quality_var.get()

        # Cảnh báo nếu trùng tên project
        try:
            existing = {d.get("draft_name", "")
                        for d in self.app.project_list.projects}
        except Exception:
            existing = set()
        warn = f"\n\n⚠ Project '{name}' đã tồn tại — sẽ GHI ĐÈ!" if name in existing else ""

        confirm = messagebox.askokcancel(
            "Bán Content",
            f"Tạo project '{name}'?\n\n"
            f"Intro: {'ĐÈ lên audio' if over else 'ĐẨY (chèn trước audio)'}\n"
            f"{ratio} | {quality} | {fps}fps{warn}\n\n"
            "Thoát CapCut trước khi tiếp tục.\nOK?"
        )
        if not confirm:
            return

        self.bck_btn.configure(state="disabled", text="Đang tạo...")
        self._set_info(f"Đang tạo '{name}'...", C["primary_light"], C["primary"])
        threading.Thread(
            target=self._run_create_bck,
            args=(name, capcut_path, source, over, ratio, quality, fps),
            daemon=True,
        ).start()

    def _run_create_bck(self, name, capcut_path, source,
                        over, ratio, quality, fps):
        root = self.app.root

        def cb(msg):
            root.after(0, self._append_log, msg)

        try:
            r = bck.build_bck_project(
                project_name=name,
                capcut_path=capcut_path,
                source_edit_dir=source,
                insert_over_audio=over,
                ratio=ratio,
                quality=quality,
                fps=fps,
                callback=cb,
            )
        except Exception:
            import traceback
            cb(f"[EXCEPTION] {traceback.format_exc()}")
            r = bck.BckResult(False, "Exception khi tạo project")

        if r.success:
            summary = (f"Done '{name}': {r.n_audio} audio, {r.n_intro} intro, "
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
            state="normal", text="Tạo dự án"))
        root.after(0, lambda: self.app.status_var.set(f"  {summary}"))

        if r.success:
            root.after(0, self.app._load_projects)
