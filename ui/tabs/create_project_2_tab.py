"""Tab Create Project 2 — các chức năng tạo project mở rộng."""

import os
import threading
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox

from ui.theme import COLORS as C, FONT
from core import create_project as cp
from core import split_project as splitp
from core import split_project_2 as splitp2


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
        self._build_manhwa_tab(sub_tabs.add("Manhwa"))
        self._build_split_tab(sub_tabs.add("Split projects"))
        self._build_split_v2_tab(sub_tabs.add("Split project 2"))

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

    # ── Sub-tab: Manhwa ────────────────────────────────────────────
    def _build_manhwa_tab(self, parent):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=10, pady=8)

        ctk.CTkLabel(
            f,
            text="Mỗi cặp (subfolder ảnh, file video) cùng tên → 1 project. "
                 "Project chứa các ảnh trong subfolder + audio trích từ video.",
            font=("Segoe UI", 10), text_color=C["text_light"],
            justify="left", wraplength=540,
        ).pack(anchor="w", pady=(0, 8))

        # Parent picture
        r1 = ctk.CTkFrame(f, fg_color="transparent")
        r1.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(r1, text="Parent PICTURE:", width=120, anchor="w",
                     font=FONT["small"], text_color=C["text_light"]).pack(side="left")
        self.mh_pic_parent_var = ctk.StringVar()
        ctk.CTkEntry(r1, textvariable=self.mh_pic_parent_var, height=28,
                     fg_color=C["input_bg"], border_color=C["input_border"],
                     text_color=C["text"], corner_radius=6, font=FONT["small"]
                     ).pack(side="left", fill="x", expand=True, padx=(4, 4))
        ctk.CTkButton(r1, text="...", width=28, height=28, corner_radius=6,
                      fg_color=C["tab_bg"], text_color=C["text"],
                      hover_color=C["primary_muted"], border_width=1,
                      border_color=C["input_border"], font=FONT["small"],
                      command=lambda: self._browse_dir_to(self.mh_pic_parent_var)
                      ).pack(side="left")

        # Parent video
        r2 = ctk.CTkFrame(f, fg_color="transparent")
        r2.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(r2, text="Parent VIDEO:", width=120, anchor="w",
                     font=FONT["small"], text_color=C["text_light"]).pack(side="left")
        self.mh_vid_parent_var = ctk.StringVar()
        ctk.CTkEntry(r2, textvariable=self.mh_vid_parent_var, height=28,
                     fg_color=C["input_bg"], border_color=C["input_border"],
                     text_color=C["text"], corner_radius=6, font=FONT["small"]
                     ).pack(side="left", fill="x", expand=True, padx=(4, 4))
        ctk.CTkButton(r2, text="...", width=28, height=28, corner_radius=6,
                      fg_color=C["tab_bg"], text_color=C["text"],
                      hover_color=C["primary_muted"], border_width=1,
                      border_color=C["input_border"], font=FONT["small"],
                      command=lambda: self._browse_dir_to(self.mh_vid_parent_var)
                      ).pack(side="left")

        # Settings card
        sett = ctk.CTkFrame(f, fg_color=C["primary_light"], corner_radius=6)
        sett.pack(fill="x", pady=(8, 8))
        s = ctk.CTkFrame(sett, fg_color="transparent")
        s.pack(fill="x", padx=10, pady=8)

        ctk.CTkLabel(s, text="Image dur:", font=FONT["small"],
                     text_color=C["text"]).pack(side="left")
        self.mh_image_dur_var = ctk.StringVar(value="4")
        ctk.CTkEntry(s, textvariable=self.mh_image_dur_var, height=28, width=55,
                     fg_color=C["card"], border_color=C["input_border"],
                     text_color=C["text"], corner_radius=6, font=FONT["small"],
                     justify="center"
                     ).pack(side="left", padx=(4, 2))
        ctk.CTkLabel(s, text="(s)", font=FONT["small"],
                     text_color=C["text_light"]).pack(side="left", padx=(0, 12))

        ctk.CTkLabel(s, text="Ratio:", font=FONT["small"],
                     text_color=C["text"]).pack(side="left")
        self.mh_ratio_var = ctk.StringVar(value="16:9")
        ctk.CTkOptionMenu(s, variable=self.mh_ratio_var,
                          values=["16:9", "9:16", "1:1", "4:3"],
                          width=70, height=28, corner_radius=6,
                          fg_color=C["card"], button_color=C["primary"],
                          text_color=C["text"], font=FONT["small"]
                          ).pack(side="left", padx=(4, 12))

        ctk.CTkLabel(s, text="Quality:", font=FONT["small"],
                     text_color=C["text"]).pack(side="left")
        self.mh_quality_var = ctk.StringVar(value="1080p")
        ctk.CTkOptionMenu(s, variable=self.mh_quality_var,
                          values=["1080p", "720p", "4K"],
                          width=80, height=28, corner_radius=6,
                          fg_color=C["card"], button_color=C["primary"],
                          text_color=C["text"], font=FONT["small"]
                          ).pack(side="left", padx=(4, 12))

        ctk.CTkLabel(s, text="FPS:", font=FONT["small"],
                     text_color=C["text"]).pack(side="left")
        self.mh_fps_var = ctk.StringVar(value="30")
        ctk.CTkOptionMenu(s, variable=self.mh_fps_var,
                          values=["30", "60"],
                          width=60, height=28, corner_radius=6,
                          fg_color=C["card"], button_color=C["primary"],
                          text_color=C["text"], font=FONT["small"]
                          ).pack(side="left", padx=(4, 0))

        # Canvas Blur checkbox
        r_blur = ctk.CTkFrame(f, fg_color="transparent")
        r_blur.pack(fill="x", pady=(0, 8))
        self.mh_canvas_blur_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            r_blur, text="Canvas Blur (apply to all images)",
            variable=self.mh_canvas_blur_var,
            font=FONT["small"], text_color=C["text"],
            checkbox_width=16, checkbox_height=16,
            fg_color=C["primary"], hover_color=C["primary_hover"],
        ).pack(side="left")

        self.mh_btn = ctk.CTkButton(
            f, text="Tạo dự án và xuất âm thanh", height=36, corner_radius=8,
            fg_color=C["accent"], hover_color="#7c3aed",
            text_color=C["text_white"], font=FONT["button"],
            command=self._on_manhwa_create
        )
        self.mh_btn.pack(fill="x")

    def _browse_dir_to(self, var):
        path = filedialog.askdirectory()
        if path:
            var.set(path)

    def _on_manhwa_create(self):
        pic = self.mh_pic_parent_var.get().strip()
        vid = self.mh_vid_parent_var.get().strip()
        if not pic or not os.path.isdir(pic):
            self._set_info("Parent PICTURE không hợp lệ!", C["red_light"], C["red"])
            return
        if not vid or not os.path.isdir(vid):
            self._set_info("Parent VIDEO không hợp lệ!", C["red_light"], C["red"])
            return

        capcut_path = self.app.capcut_path.get().strip()
        if not capcut_path or not os.path.isdir(capcut_path):
            self._set_info("CapCut path chưa cấu hình!", C["red_light"], C["red"])
            return

        try:
            img_dur = float(self.mh_image_dur_var.get())
            if img_dur <= 0:
                raise ValueError
        except ValueError:
            self._set_info("Image duration không hợp lệ!", C["red_light"], C["red"])
            return

        try:
            fps = int(self.mh_fps_var.get())
        except ValueError:
            self._set_info("FPS không hợp lệ!", C["red_light"], C["red"])
            return

        ratio = self.mh_ratio_var.get()
        quality = self.mh_quality_var.get()
        canvas_blur = self.mh_canvas_blur_var.get()

        # Quick scan to show count in confirm dialog
        try:
            pic_subs = [d for d in os.listdir(pic)
                        if os.path.isdir(os.path.join(pic, d))]
            video_exts = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".webm"}
            vid_basenames = {os.path.splitext(f)[0] for f in os.listdir(vid)
                             if os.path.isfile(os.path.join(vid, f))
                             and os.path.splitext(f)[1].lower() in video_exts}
            matched = sorted(set(pic_subs) & vid_basenames)
        except Exception as e:
            self._set_info(f"Lỗi scan: {e}", C["red_light"], C["red"])
            return

        if not matched:
            self._set_info("Không có cặp subfolder + video nào trùng tên!",
                           C["red_light"], C["red"])
            return

        confirm = messagebox.askokcancel(
            "Tạo Manhwa projects",
            f"{len(matched)} matched pair(s):\n"
            f"{', '.join(matched[:5])}{'...' if len(matched) > 5 else ''}\n\n"
            f"Image duration: {img_dur}s | {ratio} | {quality} | {fps}fps\n"
            f"Canvas Blur: {'ON' if canvas_blur else 'OFF'}\n\n"
            "Project trùng tên sẽ skip.\n"
            "Thoát CapCut trước khi tiếp tục.\nOK?"
        )
        if not confirm:
            return

        self.mh_btn.configure(state="disabled", text="Đang tạo...")
        self._set_info(f"Đang tạo {len(matched)} project...",
                       C["primary_light"], C["primary"])

        threading.Thread(
            target=self._run_manhwa,
            args=(pic, vid, capcut_path, img_dur, ratio, quality, fps, canvas_blur),
            daemon=True,
        ).start()

    def _run_manhwa(self, pic, vid, capcut_path, img_dur, ratio, quality, fps, canvas_blur):
        root = self.app.root

        def cb(msg):
            root.after(0, self._append_log, msg)

        try:
            r = cp.batch_create_manhwa_projects(
                picture_parent=pic,
                video_parent=vid,
                capcut_path=capcut_path,
                image_duration=img_dur,
                ratio=ratio,
                quality=quality,
                fps=fps,
                canvas_blur=canvas_blur,
                callback=cb,
            )
        except Exception as e:
            import traceback
            cb(f"[EXCEPTION] {traceback.format_exc()}")
            r = cp.BatchResult()

        summary = (f"Manhwa: {r.created}/{r.total} created, "
                   f"{len(r.skipped)} skipped")
        cb(f"══ {summary} ══")

        if r.created > 0 and not r.skipped:
            bg, fg = C["green_light"], C["green"]
        elif r.created == 0:
            bg, fg = C["red_light"], C["red"]
        else:
            bg, fg = C["primary_light"], C["primary"]
        root.after(0, self._set_info, summary, bg, fg)
        root.after(0, lambda: self.mh_btn.configure(
            state="normal", text="Tạo dự án và xuất âm thanh"))
        root.after(0, lambda: self.app.status_var.set(f"  {summary}"))

        if r.created > 0:
            root.after(0, self.app._load_projects)

    # ── Sub-tab: Split projects ────────────────────────────────────
    def _build_split_tab(self, parent):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=10, pady=8)

        ctk.CTkLabel(
            f,
            text="Chia project lớn thành nhiều part nhỏ để CapCut render nhanh hơn. "
                 "Tick project ở panel bên phải, đặt Max duration, rồi bấm Split. "
                 "Cắt ở ranh giới video segment gần Max — gộp lại = gốc 100%. "
                 "Project gốc giữ nguyên.",
            font=("Segoe UI", 10), text_color=C["text_light"],
            justify="left", wraplength=540,
        ).pack(anchor="w", pady=(0, 8))

        # Max duration row
        r1 = ctk.CTkFrame(f, fg_color=C["primary_light"], corner_radius=6)
        r1.pack(fill="x", pady=(0, 8))
        s = ctk.CTkFrame(r1, fg_color="transparent")
        s.pack(fill="x", padx=10, pady=8)
        ctk.CTkLabel(s, text="Max duration:", font=FONT["small"],
                     text_color=C["text"]).pack(side="left")
        self.split_max_var = ctk.StringVar(value="60")
        ctk.CTkEntry(s, textvariable=self.split_max_var, height=28, width=60,
                     fg_color=C["card"], border_color=C["input_border"],
                     text_color=C["text"], corner_radius=6, font=FONT["small"],
                     justify="center"
                     ).pack(side="left", padx=(6, 4))
        ctk.CTkLabel(s, text="(phút)", font=FONT["small"],
                     text_color=C["text_light"]).pack(side="left", padx=(0, 12))
        ctk.CTkLabel(
            s,
            text="Dư ≤ 50% max → gộp vào part cuối. Dư > 50% max → tách part mới.",
            font=("Segoe UI", 9), text_color=C["text_light"]
        ).pack(side="left")

        # Button
        self.split_btn = ctk.CTkButton(
            f, text="Split selected projects", height=36, corner_radius=8,
            fg_color=C["primary"], hover_color=C["primary_hover"],
            text_color=C["text_white"], font=FONT["button"],
            command=self._on_split
        )
        self.split_btn.pack(fill="x")

    def _on_split(self):
        try:
            max_min = float(self.split_max_var.get().strip() or 0)
            if max_min <= 0:
                raise ValueError
        except ValueError:
            self._set_info("Max duration không hợp lệ!", C["red_light"], C["red"])
            return

        selected = self.app.project_list.get_selected()
        if not selected:
            self._set_info("Chưa tick project nào ở panel phải!", C["red_light"], C["red"])
            return

        capcut_path = self.app.capcut_path.get().strip()
        if not capcut_path or not os.path.isdir(capcut_path):
            self._set_info("CapCut path chưa cấu hình!", C["red_light"], C["red"])
            return

        names = [d.get("draft_name", "?") for _, d in selected]
        confirm = messagebox.askokcancel(
            "Split projects",
            f"Split {len(selected)} project(s) với max {max_min:.0f} phút?\n\n"
            f"Projects:\n  {chr(10).join('• ' + n for n in names[:5])}"
            f"{'  ...' if len(names) > 5 else ''}\n\n"
            "Project gốc giữ nguyên. Parts đã tồn tại sẽ skip.\nThoát CapCut trước.\nOK?"
        )
        if not confirm:
            return

        self.split_btn.configure(state="disabled", text="Đang split...")
        self._set_info(f"Đang split {len(selected)} project...",
                       C["primary_light"], C["primary"])
        threading.Thread(
            target=self._run_split,
            args=([d for _, d in selected], capcut_path, max_min),
            daemon=True,
        ).start()

    def _run_split(self, drafts, capcut_path, max_min):
        root = self.app.root

        def cb(msg):
            root.after(0, self._append_log, msg)

        try:
            r = splitp.batch_split_projects(
                drafts=drafts,
                capcut_path=capcut_path,
                max_minutes=max_min,
                callback=cb,
            )
        except Exception as e:
            import traceback
            cb(f"[EXCEPTION] {traceback.format_exc()}")
            r = splitp.BatchSplitResult()

        summary = (f"Split: {r.split_ok}/{r.total} projects → "
                   f"{r.parts_total} parts, {len(r.skipped)} skipped")
        cb(f"══ {summary} ══")

        if r.split_ok > 0 and not r.skipped:
            bg, fg = C["green_light"], C["green"]
        elif r.split_ok == 0:
            bg, fg = C["red_light"], C["red"]
        else:
            bg, fg = C["primary_light"], C["primary"]
        root.after(0, self._set_info, summary, bg, fg)
        root.after(0, lambda: self.split_btn.configure(
            state="normal", text="Split selected projects"))
        root.after(0, lambda: self.app.status_var.set(f"  {summary}"))

        if r.split_ok > 0:
            root.after(0, self.app._load_projects)

    # ── Sub-tab: Split project 2 (audio = 1 segment) ───────────────
    def _build_split_v2_tab(self, parent):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=10, pady=8)

        ctk.CTkLabel(
            f,
            text="Split cho project có audio track = 1 segment duy nhất (ví dụ project Manhwa). "
                 "Cắt chính xác ở ranh giới video segment, audio dùng source_timerange offset "
                 "→ ghép lại = gốc 100%. Project gốc giữ nguyên.",
            font=("Segoe UI", 10), text_color=C["text_light"],
            justify="left", wraplength=540,
        ).pack(anchor="w", pady=(0, 8))

        # Max duration row
        r1 = ctk.CTkFrame(f, fg_color=C["primary_light"], corner_radius=6)
        r1.pack(fill="x", pady=(0, 8))
        s = ctk.CTkFrame(r1, fg_color="transparent")
        s.pack(fill="x", padx=10, pady=8)
        ctk.CTkLabel(s, text="Max duration:", font=FONT["small"],
                     text_color=C["text"]).pack(side="left")
        self.split_v2_max_var = ctk.StringVar(value="60")
        ctk.CTkEntry(s, textvariable=self.split_v2_max_var, height=28, width=60,
                     fg_color=C["card"], border_color=C["input_border"],
                     text_color=C["text"], corner_radius=6, font=FONT["small"],
                     justify="center"
                     ).pack(side="left", padx=(6, 4))
        ctk.CTkLabel(s, text="(phút)", font=FONT["small"],
                     text_color=C["text_light"]).pack(side="left", padx=(0, 12))
        ctk.CTkLabel(
            s,
            text="Dư ≤ 50% max → gộp vào part cuối. Dư > 50% max → tách part mới.",
            font=("Segoe UI", 9), text_color=C["text_light"]
        ).pack(side="left")

        self.split_v2_btn = ctk.CTkButton(
            f, text="Split (audio 1 file)", height=36, corner_radius=8,
            fg_color=C["accent"], hover_color="#7c3aed",
            text_color=C["text_white"], font=FONT["button"],
            command=self._on_split_v2
        )
        self.split_v2_btn.pack(fill="x")

    def _on_split_v2(self):
        try:
            max_min = float(self.split_v2_max_var.get().strip() or 0)
            if max_min <= 0:
                raise ValueError
        except ValueError:
            self._set_info("Max duration không hợp lệ!", C["red_light"], C["red"])
            return

        selected = self.app.project_list.get_selected()
        if not selected:
            self._set_info("Chưa tick project nào ở panel phải!", C["red_light"], C["red"])
            return

        capcut_path = self.app.capcut_path.get().strip()
        if not capcut_path or not os.path.isdir(capcut_path):
            self._set_info("CapCut path chưa cấu hình!", C["red_light"], C["red"])
            return

        names = [d.get("draft_name", "?") for _, d in selected]
        confirm = messagebox.askokcancel(
            "Split project 2",
            f"Split {len(selected)} project(s) với max {max_min:.0f} phút?\n\n"
            f"Yêu cầu: audio track = 1 segment duy nhất.\n\n"
            f"Projects:\n  {chr(10).join('• ' + n for n in names[:5])}"
            f"{'  ...' if len(names) > 5 else ''}\n\n"
            "Project gốc giữ nguyên. Parts đã tồn tại sẽ skip.\nThoát CapCut trước.\nOK?"
        )
        if not confirm:
            return

        self.split_v2_btn.configure(state="disabled", text="Đang split...")
        self._set_info(f"Đang split {len(selected)} project (v2)...",
                       C["primary_light"], C["primary"])
        threading.Thread(
            target=self._run_split_v2,
            args=([d for _, d in selected], capcut_path, max_min),
            daemon=True,
        ).start()

    def _run_split_v2(self, drafts, capcut_path, max_min):
        root = self.app.root

        def cb(msg):
            root.after(0, self._append_log, msg)

        try:
            r = splitp2.batch_split_projects_v2(
                drafts=drafts,
                capcut_path=capcut_path,
                max_minutes=max_min,
                callback=cb,
            )
        except Exception as e:
            import traceback
            cb(f"[EXCEPTION] {traceback.format_exc()}")
            r = splitp2.BatchSplitResult()

        summary = (f"Split v2: {r.split_ok}/{r.total} projects → "
                   f"{r.parts_total} parts, {len(r.skipped)} skipped")
        cb(f"══ {summary} ══")

        if r.split_ok > 0 and not r.skipped:
            bg, fg = C["green_light"], C["green"]
        elif r.split_ok == 0:
            bg, fg = C["red_light"], C["red"]
        else:
            bg, fg = C["primary_light"], C["primary"]
        root.after(0, self._set_info, summary, bg, fg)
        root.after(0, lambda: self.split_v2_btn.configure(
            state="normal", text="Split (audio 1 file)"))
        root.after(0, lambda: self.app.status_var.set(f"  {summary}"))

        if r.split_ok > 0:
            root.after(0, self.app._load_projects)
