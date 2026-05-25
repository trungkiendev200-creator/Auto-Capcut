"""Tab Create Project — single + batch."""

import os
import threading
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox

from ui.theme import COLORS as C, FONT
from core import create_project as cp


class CreateProjectTab:
    def __init__(self, parent: ctk.CTkFrame, app):
        self.app = app
        self._build(parent)

    def _build(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(expand=True, fill="both", padx=16, pady=10)

        # Batch checkbox
        self.batch_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            frame, text="Tạo đồng loạt (Batch)", variable=self.batch_var,
            font=FONT["body_bold"], text_color=C["text"],
            checkbox_width=20, checkbox_height=20,
            fg_color=C["primary"], hover_color=C["primary_hover"],
            command=self._on_batch_toggle,
        ).pack(anchor="w", pady=(0, 8))

        # Project Name (ẩn khi batch)
        self.name_row = ctk.CTkFrame(frame, fg_color="transparent")
        self.name_row.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(self.name_row, text="Project Name:", font=FONT["body"],
                      text_color=C["text"], width=130, anchor="w").pack(side="left")
        self.name_var = tk.StringVar(value="Auto")
        self.name_entry = ctk.CTkEntry(self.name_row, textvariable=self.name_var, height=32,
                      fg_color=C["input_bg"], border_color=C["input_border"],
                      text_color=C["text"], corner_radius=8)
        self.name_entry.pack(side="left", fill="x", expand=True)

        # Images/Videos Folder
        self.media_row = ctk.CTkFrame(frame, fg_color="transparent")
        self.media_row.pack(fill="x", pady=(0, 6))
        self.media_label = ctk.CTkLabel(self.media_row, text="Images/Videos:", font=FONT["body"],
                      text_color=C["text"], width=130, anchor="w")
        self.media_label.pack(side="left")
        self.media_var = tk.StringVar()
        ctk.CTkEntry(self.media_row, textvariable=self.media_var, height=32,
                      fg_color=C["input_bg"], border_color=C["input_border"],
                      text_color=C["text"], corner_radius=8).pack(side="left", fill="x", expand=True, padx=(0, 6))
        ctk.CTkButton(self.media_row, text="Select", width=65, height=32, corner_radius=8,
                       fg_color=C["primary_light"], text_color=C["primary"],
                       hover_color=C["primary_muted"], font=FONT["small"],
                       command=self._browse_media).pack(side="left")

        # Audio Folder
        r3 = ctk.CTkFrame(frame, fg_color="transparent")
        r3.pack(fill="x", pady=(0, 6))
        self.audio_label = ctk.CTkLabel(r3, text="Audio (Optional):", font=FONT["body"],
                      text_color=C["text"], width=130, anchor="w")
        self.audio_label.pack(side="left")
        self.audio_var = tk.StringVar()
        ctk.CTkEntry(r3, textvariable=self.audio_var, height=32,
                      fg_color=C["input_bg"], border_color=C["input_border"],
                      text_color=C["text"], corner_radius=8).pack(side="left", fill="x", expand=True, padx=(0, 6))
        ctk.CTkButton(r3, text="Select", width=65, height=32, corner_radius=8,
                       fg_color=C["primary_light"], text_color=C["primary"],
                       hover_color=C["primary_muted"], font=FONT["small"],
                       command=self._browse_audio).pack(side="left")

        # Settings row
        settings = ctk.CTkFrame(frame, fg_color=C["primary_light"], corner_radius=8)
        settings.pack(fill="x", pady=(4, 8))

        s_inner = ctk.CTkFrame(settings, fg_color="transparent")
        s_inner.pack(fill="x", padx=12, pady=8)

        ctk.CTkLabel(s_inner, text="Duration:", font=FONT["small"],
                      text_color=C["text"]).pack(side="left")
        self.duration_var = tk.StringVar(value="4")
        ctk.CTkEntry(s_inner, textvariable=self.duration_var, width=45, height=28,
                      fg_color=C["card"], border_color=C["input_border"],
                      text_color=C["text"], corner_radius=6).pack(side="left", padx=(4, 2))
        ctk.CTkLabel(s_inner, text="(s)", font=FONT["small"],
                      text_color=C["text_light"]).pack(side="left", padx=(0, 12))

        ctk.CTkLabel(s_inner, text="Ratio:", font=FONT["small"],
                      text_color=C["text"]).pack(side="left")
        self.ratio_var = tk.StringVar(value="16:9")
        ctk.CTkOptionMenu(s_inner, variable=self.ratio_var,
                            values=["16:9", "9:16", "1:1", "4:3"],
                            width=80, height=28, corner_radius=6,
                            fg_color=C["card"], button_color=C["primary"],
                            text_color=C["text"], font=FONT["small"],
                            ).pack(side="left", padx=(4, 12))

        ctk.CTkLabel(s_inner, text="Quality:", font=FONT["small"],
                      text_color=C["text"]).pack(side="left")
        self.quality_var = tk.StringVar(value="1080p")
        ctk.CTkOptionMenu(s_inner, variable=self.quality_var,
                            values=["1080p", "720p", "4K"],
                            width=80, height=28, corner_radius=6,
                            fg_color=C["card"], button_color=C["primary"],
                            text_color=C["text"], font=FONT["small"],
                            ).pack(side="left", padx=(4, 12))

        ctk.CTkLabel(s_inner, text="FPS:", font=FONT["small"],
                      text_color=C["text"]).pack(side="left")
        self.fps_var = tk.StringVar(value="30")
        ctk.CTkOptionMenu(s_inner, variable=self.fps_var,
                            values=["30", "60"],
                            width=65, height=28, corner_radius=6,
                            fg_color=C["card"], button_color=C["primary"],
                            text_color=C["text"], font=FONT["small"],
                            ).pack(side="left", padx=(4, 0))

        # Create button
        self.create_btn = ctk.CTkButton(
            frame, text="Create Project", height=42, corner_radius=10,
            fg_color=C["green"], hover_color="#059669",
            text_color=C["text_white"], font=FONT["button"],
            command=self._on_create
        )
        self.create_btn.pack(fill="x", pady=(4, 0))

    # ── Batch toggle ──────────────────────────────────────────────
    def _on_batch_toggle(self):
        if self.batch_var.get():
            self.name_row.pack_forget()
            self.media_label.configure(text="Thư mục CHA ảnh:")
            self.audio_label.configure(text="Thư mục CHA audio:")
            self.create_btn.configure(text="Create All Projects")
        else:
            self.name_row.pack(fill="x", pady=(0, 6), before=self.media_row)
            self.media_label.configure(text="Images/Videos:")
            self.audio_label.configure(text="Audio (Optional):")
            self.create_btn.configure(text="Create Project")

    def _browse_media(self):
        path = filedialog.askdirectory(title="Select Folder")
        if path:
            self.media_var.set(path)

    def _browse_audio(self):
        path = filedialog.askdirectory(title="Select Folder")
        if path:
            self.audio_var.set(path)

    # ── Create ────────────────────────────────────────────────────
    def _on_create(self):
        if self.batch_var.get():
            self._on_batch_create()
        else:
            self._on_single_create()

    def _on_single_create(self):
        name = self.name_var.get().strip()
        media = self.media_var.get().strip()
        audio = self.audio_var.get().strip()
        dur_text = self.duration_var.get().strip()

        if not name:
            messagebox.showwarning("Lỗi", "Vui lòng nhập tên project.")
            return
        invalid_chars = '<>:"/\\|?*'
        if any(c in name for c in invalid_chars):
            messagebox.showwarning("Lỗi", f"Tên project không được chứa ký tự: {invalid_chars}")
            return
        if not media:
            messagebox.showwarning("Lỗi", "Vui lòng chọn folder chứa ảnh/video.")
            return
        if not os.path.isdir(media):
            messagebox.showwarning("Lỗi", f"Folder không tồn tại:\n{media}")
            return
        media_exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".mp4", ".mov", ".avi", ".mkv"}
        has_media = any(os.path.splitext(f)[1].lower() in media_exts for f in os.listdir(media))
        if not has_media:
            messagebox.showwarning("Lỗi", "Folder không chứa file ảnh/video nào.")
            return
        if audio and not os.path.isdir(audio):
            messagebox.showwarning("Lỗi", f"Folder audio không tồn tại:\n{audio}")
            return
        try:
            dur = float(dur_text) if dur_text else 4.0
            if dur <= 0:
                messagebox.showwarning("Lỗi", "Duration phải lớn hơn 0.")
                return
        except ValueError:
            messagebox.showwarning("Lỗi", f"Duration không hợp lệ: '{dur_text}'")
            return

        config = cp.CreateConfig(
            project_name=name, media_folder=media, audio_folder=audio,
            image_duration=dur, ratio=self.ratio_var.get(),
            quality=self.quality_var.get(), fps=int(self.fps_var.get()),
        )
        self.create_btn.configure(state="disabled", text="Creating...")
        self.app.log(f"Creating project: {name}")
        threading.Thread(target=self._run_single, args=(config,), daemon=True).start()

    def _run_single(self, config):
        try:
            result = cp.create_project(config, self.app.capcut_path.get())
        except Exception as e:
            import traceback
            result = cp.CreateResult(False, str(e))
            self.app.log(f"Error: {traceback.format_exc()}")

        if result.success:
            self.app.log(f"OK: {result.message}")
            self.app.root.after(0, lambda: self.app.status_var.set(f"  {result.message}"))
            self.app.root.after(0, self.app._load_projects)
        else:
            self.app.log(f"FAIL: {result.message}")
            self.app.root.after(0, lambda: self.app.status_var.set(f"  Error: {result.message}"))

        self.app.root.after(0, lambda: self.create_btn.configure(
            state="normal", text="Create Project"))

    # ── Batch Create ──────────────────────────────────────────────
    def _on_batch_create(self):
        media = self.media_var.get().strip()
        audio = self.audio_var.get().strip()

        if not media:
            messagebox.showwarning("Lỗi", "Vui lòng chọn thư mục CHA chứa ảnh/video.")
            return
        if not os.path.isdir(media):
            messagebox.showwarning("Lỗi", f"Thư mục không tồn tại:\n{media}")
            return
        if not audio:
            messagebox.showwarning("Lỗi", "Vui lòng chọn thư mục CHA chứa audio.\n(Batch yêu cầu cả ảnh và audio)")
            return
        if not os.path.isdir(audio):
            messagebox.showwarning("Lỗi", f"Thư mục audio không tồn tại:\n{audio}")
            return

        # Check có thư mục con không
        media_subs = [d for d in os.listdir(media) if os.path.isdir(os.path.join(media, d))]
        if not media_subs:
            messagebox.showwarning("Lỗi", "Thư mục CHA ảnh không có thư mục con nào.")
            return

        try:
            dur = float(self.duration_var.get() or 4)
            if dur <= 0:
                dur = 4.0
        except ValueError:
            dur = 4.0

        self.create_btn.configure(state="disabled", text="Creating batch...")
        self.app.log(f"=== BATCH CREATE ===")
        self.app.log(f"Media parent: {media}")
        self.app.log(f"Audio parent: {audio}")

        threading.Thread(target=self._run_batch, args=(media, audio, dur), daemon=True).start()

    def _run_batch(self, media_parent, audio_parent, dur):
        def cb(msg):
            self.app.log(f"  {msg}")

        try:
            result = cp.batch_create_projects(
                media_parent=media_parent,
                audio_parent=audio_parent,
                capcut_path=self.app.capcut_path.get(),
                image_duration=dur,
                ratio=self.ratio_var.get(),
                quality=self.quality_var.get(),
                fps=int(self.fps_var.get()),
                callback=cb,
            )
        except Exception as e:
            import traceback
            self.app.log(f"Batch error: {traceback.format_exc()}")
            result = cp.BatchResult()

        summary = f"Batch: {result.created}/{result.total} created"
        if result.skipped:
            summary += f", {len(result.skipped)} skipped"

        self.app.log(f"=== {summary} ===")
        self.app.root.after(0, lambda: self.app.status_var.set(f"  {summary}"))
        self.app.root.after(0, self.app._load_projects)
        self.app.root.after(0, lambda: self.create_btn.configure(
            state="normal", text="Create All Projects"))
