"""Tab BODYCAM — PROMAX/17 PROMAX/BDC pipeline, Chèn Intro/Outro, clear-sub-blur."""

import os
import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox

from ui.theme import COLORS as C, FONT
from core import sync_sub_engine


class SyncSubTab:
    """Tab BODYCAM with sub-tabs."""

    def __init__(self, parent: ctk.CTkFrame, app):
        self.app = app
        self.p17_parent_var = ctk.StringVar()
        self.p17_bg_var = ctk.StringVar()
        self.bdc_parent_var = ctk.StringVar()
        self.bdc_bg_var = ctk.StringVar()
        self.outro_folder_var = ctk.StringVar()
        self.intro_folder_var = ctk.StringVar()
        self._build(parent)

    def _build(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(expand=True, fill="both", padx=10, pady=6)
        frame.grid_rowconfigure(0, weight=6)
        frame.grid_rowconfigure(2, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        # ── Sub-tabs ──
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

        self._build_17promax_tab(sub_tabs.add("17 PROMAX"))
        self._build_bdc_tab(sub_tabs.add("BDC"))
        self._build_outro_tab(sub_tabs.add("Chèn Intro/Outro"))

        # ── Info bar ──
        self.info = ctk.CTkLabel(
            frame, text="Chọn 1 project bên phải",
            font=FONT["small"], text_color=C["text_light"],
            fg_color=C["primary_light"], corner_radius=6, height=26
        )
        self.info.grid(row=1, column=0, sticky="ew", pady=(4, 2))

        # ── Log ──
        self.log = ctk.CTkTextbox(
            frame, height=100, fg_color=C["input_bg"],
            border_color=C["input_border"], border_width=1,
            corner_radius=6, text_color=C["text"], font=FONT["mono"]
        )
        self.log.grid(row=2, column=0, sticky="nsew", pady=(2, 0))
        self.log.configure(state="disabled")

    def clear_inputs(self):
        """Clear tất cả input fields và log."""
        self.outro_folder_var.set("")
        self.intro_folder_var.set("")
        if hasattr(self, "promax_speed_var"):
            self.promax_speed_var.set("1.3")
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        self._set_info("Chọn 1 project bên phải", C["primary_light"], C["text_light"])

    # ── Helpers ──────────────────────────────────────────────────────
    def _append_log(self, text: str):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _set_info(self, text: str, bg: str, fg: str):
        self.info.configure(text=text, fg_color=bg, text_color=fg)

    def _browse_dir(self, var):
        path = filedialog.askdirectory()
        if path:
            var.set(path)

    def _resolve_path(self, draft: dict) -> str:
        """Resolve draft folder path, fallback to capcut_path + name."""
        path = draft.get("draft_fold_path", "")
        if path and os.path.isdir(path):
            return path
        name = draft.get("draft_name", "")
        capcut_path = self.app.capcut_path.get()
        if capcut_path and name:
            from core.capcut import get_draft_root
            alt = os.path.join(get_draft_root(capcut_path), name)
            if os.path.isdir(alt):
                return alt
        return ""

    def _make_log_fn(self):
        root = self.app.root
        def _log(msg):
            root.after(0, self._append_log, msg)
        return _log

    def _validate_promax_data(self, selected, parent_folder):
        """Check all projects have required folders + txt files.

        Rules: file 2 (delete-narration.txt) can be empty.
        File 1 (insert-radio.txt) and file 3 (insert-law-picture.txt) must NOT be empty.
        Returns list of error strings (empty list = all OK).
        """
        errors = []
        for idx, draft in selected:
            name = draft.get("draft_name", "?")
            draft_path = self._resolve_path(draft)
            if not draft_path:
                errors.append(f"[{name}] Không tìm thấy draft folder trong CapCut")
                continue

            sub = os.path.join(parent_folder, name)
            if not os.path.isdir(sub):
                errors.append(f"[{name}] Thiếu subfolder: {sub}")
                continue

            checks = [
                ("narration/", os.path.isdir(os.path.join(sub, "narration")), None),
                ("law picture/", os.path.isdir(os.path.join(sub, "law picture")), None),
                ("1-insert-radio.txt",
                 os.path.isfile(os.path.join(sub, "1-insert-radio.txt")),
                 False),  # must not be empty
                ("2-delete-narration.txt",
                 os.path.isfile(os.path.join(sub, "2-delete-narration.txt")),
                 True),   # can be empty
                ("3-insert-law-picture.txt",
                 os.path.isfile(os.path.join(sub, "3-insert-law-picture.txt")),
                 False),  # must not be empty
            ]
            for label, exists, allow_empty in checks:
                if not exists:
                    errors.append(f"[{name}] Thiếu: {label}")
                    continue
                if allow_empty is False:
                    try:
                        txt = self._read_text(os.path.join(sub, label))
                        if not txt.strip():
                            errors.append(f"[{name}] File trống: {label}")
                    except Exception as e:
                        errors.append(f"[{name}] Không đọc được {label}: {e}")

            # Also verify narration folder has at least 1 audio file
            narr = os.path.join(sub, "narration")
            if os.path.isdir(narr):
                has_audio = any(
                    f.lower().endswith((".mp3", ".wav", ".aac", ".m4a", ".ogg"))
                    for f in os.listdir(narr)
                )
                if not has_audio:
                    errors.append(f"[{name}] narration/ không có file audio")

            # Picture folder must have at least 1 image
            pic = os.path.join(sub, "law picture")
            if os.path.isdir(pic):
                has_img = any(
                    f.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".bmp"))
                    for f in os.listdir(pic)
                )
                if not has_img:
                    errors.append(f"[{name}] law picture/ không có file ảnh")

        return errors

    # ── Sub-tab: 17 PROMAX ────────────────────────────────────────
    def _build_17promax_tab(self, parent):
        import tkinter as tk

        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=10, pady=6)

        # Parent folder
        r1 = ctk.CTkFrame(f, fg_color="transparent")
        r1.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(r1, text="Thư mục cha:", width=95, anchor="w",
                     font=FONT["small"], text_color=C["text_light"]).pack(side="left")
        ctk.CTkEntry(r1, textvariable=self.p17_parent_var, height=28,
                     fg_color=C["input_bg"], border_color=C["input_border"],
                     text_color=C["text"], corner_radius=6, font=FONT["small"]
                     ).pack(side="left", fill="x", expand=True, padx=(4, 4))
        ctk.CTkButton(r1, text="...", width=28, height=28, corner_radius=6,
                      fg_color=C["tab_bg"], text_color=C["text"],
                      hover_color=C["primary_muted"], border_width=1,
                      border_color=C["input_border"], font=FONT["small"],
                      command=lambda: self._browse_dir(self.p17_parent_var)
                      ).pack(side="left")

        # BG video
        r2 = ctk.CTkFrame(f, fg_color="transparent")
        r2.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(r2, text="Video nền:", width=95, anchor="w",
                     font=FONT["small"], text_color=C["text_light"]).pack(side="left")
        ctk.CTkEntry(r2, textvariable=self.p17_bg_var, height=28,
                     fg_color=C["input_bg"], border_color=C["input_border"],
                     text_color=C["text"], corner_radius=6, font=FONT["small"]
                     ).pack(side="left", fill="x", expand=True, padx=(4, 4))
        ctk.CTkButton(r2, text="...", width=28, height=28, corner_radius=6,
                      fg_color=C["tab_bg"], text_color=C["text"],
                      hover_color=C["primary_muted"], border_width=1,
                      border_color=C["input_border"], font=FONT["small"],
                      command=lambda: self._browse_file_to(
                          self.p17_bg_var, "Chọn video nền",
                          [("Video", "*.mp4 *.mov *.avi *.mkv"), ("All", "*.*")])
                      ).pack(side="left")

        # Speed + animation
        r3 = ctk.CTkFrame(f, fg_color="transparent")
        r3.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(r3, text="Sync Speed:", width=95, anchor="w",
                     font=FONT["small"], text_color=C["text_light"]).pack(side="left")
        self.p17_speed_var = ctk.StringVar(value="1.3")
        ctk.CTkEntry(r3, textvariable=self.p17_speed_var, height=28, width=80,
                     fg_color=C["input_bg"], border_color=C["input_border"],
                     text_color=C["text"], corner_radius=6, font=FONT["small"]
                     ).pack(side="left", padx=(4, 0))
        self.p17_anim_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            r3, text="Animation cho ảnh", variable=self.p17_anim_var,
            font=FONT["small"], text_color=C["text_light"],
            checkbox_width=16, checkbox_height=16,
            fg_color=C["primary"], hover_color=C["primary_hover"],
        ).pack(side="left", padx=(12, 0))

        # Padding (tùy chọn) — đệm 2 bên narration tại điểm cắt
        r4 = ctk.CTkFrame(f, fg_color="transparent")
        r4.pack(fill="x", pady=(0, 4))
        self.p17_padding_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            r4, text="Padding", variable=self.p17_padding_var,
            font=FONT["small"], text_color=C["text_light"],
            checkbox_width=16, checkbox_height=16,
            fg_color=C["primary"], hover_color=C["primary_hover"],
        ).pack(side="left")
        ctk.CTkLabel(r4, text="Thời gian (giây):", font=FONT["small"],
                     text_color=C["text_light"]).pack(side="left", padx=(12, 4))
        self.p17_padding_sec_var = ctk.StringVar(value="0.25")
        ctk.CTkEntry(r4, textvariable=self.p17_padding_sec_var, height=28, width=70,
                     fg_color=C["input_bg"], border_color=C["input_border"],
                     text_color=C["text"], corner_radius=6, font=FONT["small"]
                     ).pack(side="left")

        info_text = (
            "Quy trình mới (bỏ hook / intro / text intro):\n"
            "  [1] Cut & Import Audio (1-insert-radio.txt + narration/) — có padding tùy chọn\n"
            "  [2] Delete SRT (2-delete-narration.txt)\n"
            "  [3] Sync Media @speed (cắt random video gốc)\n"
            "  [4] Insert Picture (3-insert-law-picture.txt + law picture/)\n"
            "Project cần có SRT sẵn. Padding tắt → narration sát điểm cắt."
        )
        ctk.CTkLabel(f, text=info_text, font=("Segoe UI", 10),
                     text_color=C["text_light"], justify="left", wraplength=520
                     ).pack(anchor="w", pady=(4, 6))

        self.p17_btn = ctk.CTkButton(
            f, text="Run 17 PROMAX", height=36, corner_radius=8,
            fg_color=C["accent"], hover_color="#7c3aed",
            text_color=C["text_white"], font=FONT["button"],
            command=self._on_run_17promax
        )
        self.p17_btn.pack(fill="x")

    def _browse_file_to(self, var, title, filetypes):
        path = filedialog.askopenfilename(title=title, filetypes=filetypes)
        if path:
            var.set(path)

    def _validate_17promax_data(self, selected, parent_folder):
        # Quy trình mới: bỏ hook/intro → dùng chung validate PROMAX
        return self._validate_promax_data(selected, parent_folder)

    def _on_run_17promax(self):
        try:
            selected = self.app.project_list.get_selected()
            if not selected:
                self._set_info("Chưa chọn project nào!", C["red_light"], C["red"])
                return

            parent_folder = self.p17_parent_var.get().strip()
            bg_video = self.p17_bg_var.get().strip()
            if not parent_folder or not os.path.isdir(parent_folder):
                self._set_info("Thư mục cha không hợp lệ!", C["red_light"], C["red"])
                return
            if not bg_video or not os.path.isfile(bg_video):
                self._set_info("Video nền không hợp lệ!", C["red_light"], C["red"])
                return

            try:
                speed = float(self.p17_speed_var.get())
                if speed <= 0:
                    raise ValueError
            except ValueError:
                self._set_info("Speed không hợp lệ!", C["red_light"], C["red"])
                return

            add_anim = self.p17_anim_var.get()

            # Padding tùy chọn (giây → microseconds); tắt → 0
            if self.p17_padding_var.get():
                try:
                    padding_us = int(float(self.p17_padding_sec_var.get()) * 1_000_000)
                    if padding_us < 0:
                        raise ValueError
                except ValueError:
                    self._set_info("Padding (giây) không hợp lệ!", C["red_light"], C["red"])
                    return
            else:
                padding_us = 0

            errors = self._validate_17promax_data(selected, parent_folder)
            if errors:
                self._append_log("[17 PROMAX VALIDATE] Data không hợp lệ:")
                for e in errors:
                    self._append_log(f"  - {e}")
                self._set_info(f"Validate fail: {len(errors)} lỗi",
                               C["red_light"], C["red"])
                messagebox.showerror(
                    "17 PROMAX — Validate Fail",
                    "Kiểm tra dữ liệu thất bại. Chưa chạy gì cả.\n\n" + "\n".join(errors)
                )
                return

            names = [d.get("draft_name", "?") for _, d in selected]
            preview = ", ".join(names[:5]) + ("..." if len(names) > 5 else "")
            pad_label = f"{padding_us / 1_000_000:g}s" if padding_us > 0 else "OFF"
            confirm = messagebox.askokcancel(
                "17 PROMAX",
                f"Validate OK. Chạy {len(selected)} project:\n{preview}\n\n"
                f"Speed: {speed}x | Animation: {'ON' if add_anim else 'OFF'} | "
                f"Padding: {pad_label}\n\n"
                "Thoát CapCut trước khi tiếp tục.\nOK?"
            )
            if not confirm:
                return

            self.p17_btn.configure(state="disabled", text="Đang chạy...")
            self._set_info(f"17 PROMAX: {len(selected)} projects...",
                           C["primary_light"], C["primary"])

            threading.Thread(
                target=self._run_17promax,
                args=(selected, parent_folder, bg_video, speed, add_anim, padding_us),
                daemon=True,
            ).start()
        except Exception as e:
            import traceback
            self._append_log(f"[17 PROMAX] EXCEPTION: {traceback.format_exc()}")
            self._set_info(f"Error: {e}", C["red_light"], C["red"])

    def _run_17promax(self, selected, parent_folder, bg_video, speed, add_anim,
                      padding_us=0):
        root = self.app.root
        _log = self._make_log_fn()

        ok_count = 0
        fail_count = 0
        total = len(selected)

        for i, (idx, draft) in enumerate(selected, start=1):
            name = draft.get("draft_name", "?")
            draft_path = self._resolve_path(draft)

            _log(f"── [{i}/{total}] 17 PROMAX: {name} ──")
            root.after(0, self.app.project_list.set_status, idx, "...", C["primary"])
            root.after(0, self._set_info,
                       f"[{i}/{total}] {name}...",
                       C["primary_light"], C["primary"])

            if not draft_path:
                _log(f"  FAIL: draft folder not found")
                root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])
                fail_count += 1
                continue

            sub_folder = os.path.join(parent_folder, name)
            narration_folder = os.path.join(sub_folder, "narration")
            picture_folder = os.path.join(sub_folder, "law picture")
            cut_file = os.path.join(sub_folder, "1-insert-radio.txt")
            delete_file = os.path.join(sub_folder, "2-delete-narration.txt")
            pic_file = os.path.join(sub_folder, "3-insert-law-picture.txt")

            try:
                cut_text = self._read_text(cut_file)
                delete_text = self._read_text(delete_file)
                pic_text = self._read_text(pic_file)
            except Exception as e:
                _log(f"  FAIL: read txt error: {e}")
                root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])
                fail_count += 1
                continue

            # ── Preflight: kiểm tra input cả 4 bước TRƯỚC khi ghi ──
            # Bước 1 ghi vào draft trước khi bước 2/4 kịp validate → sai ở bước
            # sau là project nằm dở dang và chạy lại sẽ cắt chồng.
            try:
                errs = sync_sub_engine.preflight_17promax(
                    draft_path, narration_folder, bg_video, picture_folder,
                    cut_text, delete_text, pic_text,
                )
            except Exception as e:
                errs = [f"preflight lỗi: {e}"]
            if errs:
                _log(f"  PREFLIGHT FAIL ({len(errs)} lỗi) — bỏ qua, KHÔNG đụng vào project:")
                for m in errs[:10]:
                    _log(f"    - {m}")
                if len(errs) > 10:
                    _log(f"    ... và {len(errs) - 10} lỗi nữa")
                root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])
                fail_count += 1
                continue
            _log("  preflight OK")

            project_ok = True

            # ── 4 bước (quy trình mới, không hook/intro) ──
            _log(f"  [1/4] Cut & Import Audio (padding="
                 f"{padding_us/1_000_000:g}s)")
            try:
                r = sync_sub_engine.cut_and_import_audio(
                    draft_path, narration_folder, bg_video, cut_text,
                    backup=True, log_fn=_log, padding_us=padding_us
                )
                if not r.success:
                    _log(f"    FAIL: {r.message}")
                    project_ok = False
                else:
                    _log(f"    OK: {r.message}")
            except Exception as e:
                import traceback
                _log(f"    EXCEPTION: {traceback.format_exc()}")
                project_ok = False

            if project_ok:
                if delete_text.strip():
                    _log(f"  [2/4] Xóa SRT")
                    try:
                        r = sync_sub_engine.delete_srt_and_cut(
                            draft_path, delete_text, backup=True, log_fn=_log
                        )
                        if not r.success:
                            _log(f"    FAIL: {r.message}")
                            project_ok = False
                        else:
                            _log(f"    OK: {r.message}")
                    except Exception as e:
                        import traceback
                        _log(f"    EXCEPTION: {traceback.format_exc()}")
                        project_ok = False
                else:
                    _log(f"  [2/4] Xóa SRT: file trống, bỏ qua")

            if project_ok:
                _log(f"  [3/4] Sync Media @{speed}x")
                try:
                    r = sync_sub_engine.sync_media_sub(
                        draft_path, speed=speed, backup=True, log_fn=_log
                    )
                    if not r.success:
                        _log(f"    FAIL: {r.message}")
                        project_ok = False
                    else:
                        _log(f"    OK: {r.message}")
                except Exception as e:
                    import traceback
                    _log(f"    EXCEPTION: {traceback.format_exc()}")
                    project_ok = False

            if project_ok:
                _log(f"  [4/4] Insert Picture")
                try:
                    r = sync_sub_engine.insert_picture_law(
                        draft_path, picture_folder, pic_text,
                        add_animation=add_anim, backup=True, log_fn=_log
                    )
                    if not r.success:
                        _log(f"    FAIL: {r.message}")
                        project_ok = False
                    else:
                        _log(f"    OK: {r.message}")
                except Exception as e:
                    import traceback
                    _log(f"    EXCEPTION: {traceback.format_exc()}")
                    project_ok = False

            if project_ok:
                ok_count += 1
                root.after(0, self.app.project_list.set_status, idx, "Done", C["green"])
                _log(f"  ✓ DONE: {name}")
            else:
                fail_count += 1
                root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])
                _log(f"  ✗ FAIL: {name}")

        summary = f"17 PROMAX xong: {ok_count}/{total} OK, {fail_count} fail"
        _log(f"══ {summary} ══")
        color_bg = C["green_light"] if fail_count == 0 else C["red_light"]
        color_fg = C["green"] if fail_count == 0 else C["red"]
        root.after(0, self._set_info, summary, color_bg, color_fg)
        root.after(0, lambda: self.p17_btn.configure(
            state="normal", text="Run 17 PROMAX"))

    # ── Sub-tab: BDC ───────────────────────────────────────────────
    def _build_bdc_tab(self, parent):
        import tkinter as tk

        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=10, pady=6)

        # Parent folder
        r1 = ctk.CTkFrame(f, fg_color="transparent")
        r1.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(r1, text="Thư mục cha:", width=95, anchor="w",
                     font=FONT["small"], text_color=C["text_light"]).pack(side="left")
        ctk.CTkEntry(r1, textvariable=self.bdc_parent_var, height=28,
                     fg_color=C["input_bg"], border_color=C["input_border"],
                     text_color=C["text"], corner_radius=6, font=FONT["small"]
                     ).pack(side="left", fill="x", expand=True, padx=(4, 4))
        ctk.CTkButton(r1, text="...", width=28, height=28, corner_radius=6,
                      fg_color=C["tab_bg"], text_color=C["text"],
                      hover_color=C["primary_muted"], border_width=1,
                      border_color=C["input_border"], font=FONT["small"],
                      command=lambda: self._browse_dir(self.bdc_parent_var)
                      ).pack(side="left")

        # BG video
        r2 = ctk.CTkFrame(f, fg_color="transparent")
        r2.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(r2, text="Video nền:", width=95, anchor="w",
                     font=FONT["small"], text_color=C["text_light"]).pack(side="left")
        ctk.CTkEntry(r2, textvariable=self.bdc_bg_var, height=28,
                     fg_color=C["input_bg"], border_color=C["input_border"],
                     text_color=C["text"], corner_radius=6, font=FONT["small"]
                     ).pack(side="left", fill="x", expand=True, padx=(4, 4))
        ctk.CTkButton(r2, text="...", width=28, height=28, corner_radius=6,
                      fg_color=C["tab_bg"], text_color=C["text"],
                      hover_color=C["primary_muted"], border_width=1,
                      border_color=C["input_border"], font=FONT["small"],
                      command=lambda: self._browse_file_to(
                          self.bdc_bg_var, "Chọn video nền",
                          [("Video", "*.mp4 *.mov *.avi *.mkv"), ("All", "*.*")])
                      ).pack(side="left")

        # Sync speed + animation
        r3 = ctk.CTkFrame(f, fg_color="transparent")
        r3.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(r3, text="Sync Speed:", width=95, anchor="w",
                     font=FONT["small"], text_color=C["text_light"]).pack(side="left")
        self.bdc_speed_var = ctk.StringVar(value="1.3")
        ctk.CTkEntry(r3, textvariable=self.bdc_speed_var, height=28, width=80,
                     fg_color=C["input_bg"], border_color=C["input_border"],
                     text_color=C["text"], corner_radius=6, font=FONT["small"]
                     ).pack(side="left", padx=(4, 0))
        self.bdc_anim_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            r3, text="Animation cho ảnh", variable=self.bdc_anim_var,
            font=FONT["small"], text_color=C["text_light"],
            checkbox_width=16, checkbox_height=16,
            fg_color=C["primary"], hover_color=C["primary_hover"],
        ).pack(side="left", padx=(12, 0))

        # Padding
        r4 = ctk.CTkFrame(f, fg_color="transparent")
        r4.pack(fill="x", pady=(0, 4))
        self.bdc_padding_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            r4, text="Padding", variable=self.bdc_padding_var,
            font=FONT["small"], text_color=C["text_light"],
            checkbox_width=16, checkbox_height=16,
            fg_color=C["primary"], hover_color=C["primary_hover"],
        ).pack(side="left")
        ctk.CTkLabel(r4, text="Thời gian (giây):", font=FONT["small"],
                     text_color=C["text_light"]).pack(side="left", padx=(12, 4))
        self.bdc_padding_sec_var = ctk.StringVar(value="0.25")
        ctk.CTkEntry(r4, textvariable=self.bdc_padding_sec_var, height=28, width=70,
                     fg_color=C["input_bg"], border_color=C["input_border"],
                     text_color=C["text"], corner_radius=6, font=FONT["small"]
                     ).pack(side="left")

        info_text = (
            "BDC — 4 bước, giống 17 PROMAX, chỉ khác cách map ảnh law:\n"
            "  [1] Cut & Import Audio (1-insert-radio.txt + narration/) — có padding tùy chọn\n"
            "  [2] Delete SRT (2-delete-narration.txt)\n"
            "  [3] Sync Media @speed (cắt random video gốc thay video nền)\n"
            "  [4] Insert Picture (law picture/) — mapping theo TÊN FILE ẢNH\n"
            "Ảnh đặt tên bằng số = số narration: 03.png → audio 3, 20.png → audio 20.\n"
            "KHÔNG cần 3-insert-law-picture.txt. Project cần có SRT sẵn."
        )
        ctk.CTkLabel(f, text=info_text, font=("Segoe UI", 10),
                     text_color=C["text_light"], justify="left", wraplength=520
                     ).pack(anchor="w", pady=(4, 6))

        self.bdc_btn = ctk.CTkButton(
            f, text="Run BDC", height=36, corner_radius=8,
            fg_color=C["accent"], hover_color="#7c3aed",
            text_color=C["text_white"], font=FONT["button"],
            command=self._on_run_bdc
        )
        self.bdc_btn.pack(fill="x")

        # ── Change Video (chức năng phụ) ────────────────────────────
        cv_info = (
            "change-video — chức năng phụ: xoá track sub + track ảnh, rồi thay "
            "narration mp3 + video chạy trên nó bằng video dựng sẵn trong "
            "'<Thư mục cha>/<project>/video-narration/'.\n"
            "Mỗi '{cue}-state.json' = 1 scene, khớp theo audio 'items[].num', "
            "video thay thế là '{cue}-narration.mp4' cùng thư mục."
        )
        ctk.CTkLabel(f, text=cv_info, font=("Segoe UI", 10),
                     text_color=C["text_light"], justify="left", wraplength=520
                     ).pack(anchor="w", pady=(10, 4))

        self.bdc_changevideo_btn = ctk.CTkButton(
            f, text="Change Video", height=36, corner_radius=8,
            fg_color=C["primary"], hover_color=C["primary_hover"],
            text_color=C["text_white"], font=FONT["button"],
            command=self._on_run_change_video
        )
        self.bdc_changevideo_btn.pack(fill="x")

    def _validate_bdc_data(self, selected, parent_folder):
        """Như _validate_promax_data nhưng KHÔNG cần 3-insert-law-picture.txt;
        thay vào đó 'law picture/' phải có ít nhất 1 ảnh đặt tên bằng số."""
        errors = []
        for idx, draft in selected:
            name = draft.get("draft_name", "?")
            if not self._resolve_path(draft):
                errors.append(f"[{name}] Không tìm thấy draft folder trong CapCut")
                continue

            sub = os.path.join(parent_folder, name)
            if not os.path.isdir(sub):
                errors.append(f"[{name}] Thiếu subfolder: {sub}")
                continue

            narr = os.path.join(sub, "narration")
            pics = os.path.join(sub, "law picture")
            if not os.path.isdir(narr):
                errors.append(f"[{name}] Thiếu: narration/")
            elif not any(f.lower().endswith((".mp3", ".wav", ".aac", ".m4a", ".ogg"))
                         for f in os.listdir(narr)):
                errors.append(f"[{name}] narration/ không có file audio")

            if not os.path.isdir(pics):
                errors.append(f"[{name}] Thiếu: law picture/")
            else:
                pic_text, warns = sync_sub_engine.build_picture_map_from_filenames(pics)
                if not pic_text.strip():
                    errors.append(f"[{name}] law picture/ không có ảnh nào "
                                  f"đặt tên bằng số (vd 03.png)")
                for w in warns:
                    errors.append(f"[{name}] law picture/: {w}")

            for label, allow_empty in (("1-insert-radio.txt", False),
                                       ("2-delete-narration.txt", True)):
                p = os.path.join(sub, label)
                if not os.path.isfile(p):
                    errors.append(f"[{name}] Thiếu: {label}")
                elif not allow_empty:
                    try:
                        if not self._read_text(p).strip():
                            errors.append(f"[{name}] File trống: {label}")
                    except Exception as e:
                        errors.append(f"[{name}] Không đọc được {label}: {e}")
        return errors

    def _on_run_bdc(self):
        try:
            selected = self.app.project_list.get_selected()
            if not selected:
                self._set_info("Chưa chọn project nào!", C["red_light"], C["red"])
                return

            parent_folder = self.bdc_parent_var.get().strip()
            bg_video = self.bdc_bg_var.get().strip()
            if not parent_folder or not os.path.isdir(parent_folder):
                self._set_info("Thư mục cha không hợp lệ!", C["red_light"], C["red"])
                return
            if not bg_video or not os.path.isfile(bg_video):
                self._set_info("Video nền không hợp lệ!", C["red_light"], C["red"])
                return

            try:
                speed = float(self.bdc_speed_var.get())
                if speed <= 0:
                    raise ValueError
            except ValueError:
                self._set_info("Speed không hợp lệ!", C["red_light"], C["red"])
                return

            add_anim = self.bdc_anim_var.get()
            if self.bdc_padding_var.get():
                try:
                    padding_us = int(float(self.bdc_padding_sec_var.get()) * 1_000_000)
                    if padding_us < 0:
                        raise ValueError
                except ValueError:
                    self._set_info("Padding (giây) không hợp lệ!", C["red_light"], C["red"])
                    return
            else:
                padding_us = 0

            errors = self._validate_bdc_data(selected, parent_folder)
            if errors:
                self._append_log("[BDC VALIDATE] Data không hợp lệ:")
                for e in errors:
                    self._append_log(f"  - {e}")
                self._set_info(f"Validate fail: {len(errors)} lỗi",
                               C["red_light"], C["red"])
                messagebox.showerror(
                    "BDC — Validate Fail",
                    "Kiểm tra dữ liệu thất bại. Chưa chạy gì cả.\n\n" + "\n".join(errors)
                )
                return

            names = [d.get("draft_name", "?") for _, d in selected]
            preview = ", ".join(names[:5]) + ("..." if len(names) > 5 else "")
            pad_label = f"{padding_us / 1_000_000:g}s" if padding_us > 0 else "OFF"
            confirm = messagebox.askokcancel(
                "BDC",
                f"Validate OK. Chạy {len(selected)} project:\n{preview}\n\n"
                f"Speed: {speed}x | Animation: {'ON' if add_anim else 'OFF'} | "
                f"Padding: {pad_label}\n"
                f"Ảnh law map theo TÊN FILE (03.png → audio 3)\n\n"
                "Thoát CapCut trước khi tiếp tục.\nOK?"
            )
            if not confirm:
                return

            self.bdc_btn.configure(state="disabled", text="Đang chạy...")
            self._set_info(f"BDC: {len(selected)} projects...",
                           C["primary_light"], C["primary"])

            threading.Thread(
                target=self._run_bdc,
                args=(selected, parent_folder, bg_video, speed, add_anim, padding_us),
                daemon=True,
            ).start()
        except Exception as e:
            import traceback
            self._append_log(f"[BDC] EXCEPTION: {traceback.format_exc()}")
            self._set_info(f"Error: {e}", C["red_light"], C["red"])

    def _run_bdc(self, selected, parent_folder, bg_video, speed, add_anim, padding_us):
        root = self.app.root
        _log = self._make_log_fn()

        ok_count = 0
        fail_count = 0
        total = len(selected)

        for i, (idx, draft) in enumerate(selected, start=1):
            name = draft.get("draft_name", "?")
            draft_path = self._resolve_path(draft)

            _log(f"── [{i}/{total}] BDC: {name} ──")
            root.after(0, self.app.project_list.set_status, idx, "...", C["primary"])
            root.after(0, self._set_info, f"[{i}/{total}] {name}...",
                       C["primary_light"], C["primary"])

            if not draft_path:
                _log("  FAIL: draft folder not found")
                root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])
                fail_count += 1
                continue

            sub_folder = os.path.join(parent_folder, name)
            narration_folder = os.path.join(sub_folder, "narration")
            picture_folder = os.path.join(sub_folder, "law picture")

            try:
                cut_text = self._read_text(os.path.join(sub_folder, "1-insert-radio.txt"))
                delete_text = self._read_text(
                    os.path.join(sub_folder, "2-delete-narration.txt"))
            except Exception as e:
                _log(f"  FAIL: read txt error: {e}")
                root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])
                fail_count += 1
                continue

            # Mapping ảnh law từ tên file (thay cho 3-insert-law-picture.txt)
            pic_text, pic_warns = sync_sub_engine.build_picture_map_from_filenames(
                picture_folder)
            for w in pic_warns:
                _log(f"  ⚠ law picture: {w}")
            _log(f"  mapping ảnh theo tên file: {len(pic_text.splitlines())} ảnh")

            # ── Preflight: chặn trước khi ghi ──
            try:
                errs = sync_sub_engine.preflight_bdc(
                    draft_path, narration_folder, bg_video, picture_folder,
                    cut_text, delete_text,
                )
            except Exception as e:
                errs = [f"preflight lỗi: {e}"]
            if errs:
                _log(f"  PREFLIGHT FAIL ({len(errs)} lỗi) — bỏ qua, KHÔNG đụng vào project:")
                for m in errs[:10]:
                    _log(f"    - {m}")
                if len(errs) > 10:
                    _log(f"    ... và {len(errs) - 10} lỗi nữa")
                root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])
                fail_count += 1
                continue
            _log("  preflight OK")

            project_ok = True

            _log(f"  [1/4] Cut & Import Audio (padding={padding_us/1_000_000:g}s)")
            try:
                r = sync_sub_engine.cut_and_import_audio(
                    draft_path, narration_folder, bg_video, cut_text,
                    backup=True, log_fn=_log, padding_us=padding_us)
                _log(f"    {'OK' if r.success else 'FAIL'}: {r.message}")
                project_ok = r.success
            except Exception:
                import traceback
                _log(f"    EXCEPTION: {traceback.format_exc()}")
                project_ok = False

            if project_ok:
                if delete_text.strip():
                    _log("  [2/4] Xóa SRT")
                    try:
                        r = sync_sub_engine.delete_srt_and_cut(
                            draft_path, delete_text, backup=True, log_fn=_log)
                        _log(f"    {'OK' if r.success else 'FAIL'}: {r.message}")
                        project_ok = r.success
                    except Exception:
                        import traceback
                        _log(f"    EXCEPTION: {traceback.format_exc()}")
                        project_ok = False
                else:
                    _log("  [2/4] Xóa SRT: file trống, bỏ qua")

            if project_ok:
                _log(f"  [3/4] Sync Media @{speed}x")
                try:
                    r = sync_sub_engine.sync_media_sub(
                        draft_path, speed=speed, backup=True, log_fn=_log)
                    _log(f"    {'OK' if r.success else 'FAIL'}: {r.message}")
                    project_ok = r.success
                except Exception:
                    import traceback
                    _log(f"    EXCEPTION: {traceback.format_exc()}")
                    project_ok = False

            if project_ok:
                _log("  [4/4] Insert Picture (map theo tên file)")
                try:
                    r = sync_sub_engine.insert_picture_law(
                        draft_path, picture_folder, pic_text,
                        add_animation=add_anim, backup=True, log_fn=_log)
                    _log(f"    {'OK' if r.success else 'FAIL'}: {r.message}")
                    project_ok = r.success
                except Exception:
                    import traceback
                    _log(f"    EXCEPTION: {traceback.format_exc()}")
                    project_ok = False

            if project_ok:
                ok_count += 1
                root.after(0, self.app.project_list.set_status, idx, "OK", C["green"])
                _log(f"  ✓ DONE: {name}")
            else:
                fail_count += 1
                root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])
                _log(f"  ✗ FAIL: {name}")

        summary = f"BDC xong: {ok_count}/{total} OK, {fail_count} fail"
        _log(f"══ {summary} ══")
        color_bg = C["green_light"] if fail_count == 0 else C["red_light"]
        color_fg = C["green"] if fail_count == 0 else C["red"]
        root.after(0, self._set_info, summary, color_bg, color_fg)
        root.after(0, lambda: self.bdc_btn.configure(state="normal", text="Run BDC"))

    # ── Change Video (chức năng phụ của BDC) ────────────────────────
    def _validate_change_video_data(self, selected, parent_folder):
        """Check mỗi project có subfolder 'video-narration/' với ít nhất 1 scene
        hợp lệ (*-state.json + *-narration.mp4 tương ứng)."""
        errors = []
        for idx, draft in selected:
            name = draft.get("draft_name", "?")
            if not self._resolve_path(draft):
                errors.append(f"[{name}] Không tìm thấy draft folder trong CapCut")
                continue

            sub = os.path.join(parent_folder, name)
            narr = os.path.join(sub, "video-narration")
            if not os.path.isdir(narr):
                errors.append(f"[{name}] Thiếu subfolder: video-narration/")
                continue

            scenes, warns = sync_sub_engine.scan_narration_scenes(narr)
            if not scenes:
                errors.append(f"[{name}] video-narration/ không có scene hợp lệ nào "
                              f"(*-state.json + *-narration.mp4)")
            for w in warns:
                errors.append(f"[{name}] video-narration/: {w}")
        return errors

    def _on_run_change_video(self):
        try:
            selected = self.app.project_list.get_selected()
            if not selected:
                self._set_info("Chưa chọn project nào!", C["red_light"], C["red"])
                return

            parent_folder = self.bdc_parent_var.get().strip()
            if not parent_folder or not os.path.isdir(parent_folder):
                self._set_info("Thư mục cha không hợp lệ!", C["red_light"], C["red"])
                return

            errors = self._validate_change_video_data(selected, parent_folder)
            if errors:
                self._append_log("[CHANGE VIDEO VALIDATE] Data không hợp lệ:")
                for e in errors:
                    self._append_log(f"  - {e}")
                self._set_info(f"Validate fail: {len(errors)} lỗi",
                               C["red_light"], C["red"])
                messagebox.showerror(
                    "Change Video — Validate Fail",
                    "Kiểm tra dữ liệu thất bại. Chưa chạy gì cả.\n\n" + "\n".join(errors)
                )
                return

            names = [d.get("draft_name", "?") for _, d in selected]
            preview = ", ".join(names[:5]) + ("..." if len(names) > 5 else "")
            confirm = messagebox.askokcancel(
                "Change Video",
                f"Validate OK. Chạy {len(selected)} project:\n{preview}\n\n"
                "Sẽ xoá track sub + track ảnh, thay narration bằng video trong "
                "'video-narration/'.\n\n"
                "Thoát CapCut trước khi tiếp tục.\nOK?"
            )
            if not confirm:
                return

            self.bdc_changevideo_btn.configure(state="disabled", text="Đang chạy...")
            self._set_info(f"Change Video: {len(selected)} projects...",
                           C["primary_light"], C["primary"])

            threading.Thread(
                target=self._run_change_video,
                args=(selected, parent_folder),
                daemon=True,
            ).start()
        except Exception as e:
            import traceback
            self._append_log(f"[CHANGE VIDEO] EXCEPTION: {traceback.format_exc()}")
            self._set_info(f"Error: {e}", C["red_light"], C["red"])

    def _run_change_video(self, selected, parent_folder):
        root = self.app.root
        _log = self._make_log_fn()

        ok_count = 0
        fail_count = 0
        total = len(selected)

        for i, (idx, draft) in enumerate(selected, start=1):
            name = draft.get("draft_name", "?")
            draft_path = self._resolve_path(draft)

            _log(f"── [{i}/{total}] Change Video: {name} ──")
            root.after(0, self.app.project_list.set_status, idx, "...", C["primary"])
            root.after(0, self._set_info, f"[{i}/{total}] {name}...",
                       C["primary_light"], C["primary"])

            if not draft_path:
                _log("  FAIL: draft folder not found")
                root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])
                fail_count += 1
                continue

            narration_folder = os.path.join(parent_folder, name, "video-narration")

            try:
                errs = sync_sub_engine.preflight_change_video(draft_path, narration_folder)
            except Exception as e:
                errs = [f"preflight lỗi: {e}"]
            if errs:
                _log(f"  PREFLIGHT FAIL ({len(errs)} lỗi) — bỏ qua, KHÔNG đụng vào project:")
                for m in errs[:10]:
                    _log(f"    - {m}")
                if len(errs) > 10:
                    _log(f"    ... và {len(errs) - 10} lỗi nữa")
                root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])
                fail_count += 1
                continue
            _log("  preflight OK")

            try:
                r = sync_sub_engine.change_video(
                    draft_path, narration_folder, backup=True, log_fn=_log)
                _log(f"  {'OK' if r.success else 'FAIL'}: {r.message}")
                project_ok = r.success
            except Exception:
                import traceback
                _log(f"  EXCEPTION: {traceback.format_exc()}")
                project_ok = False

            if project_ok:
                ok_count += 1
                root.after(0, self.app.project_list.set_status, idx, "OK", C["green"])
                _log(f"  ✓ DONE: {name}")
            else:
                fail_count += 1
                root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])
                _log(f"  ✗ FAIL: {name}")

        summary = f"Change Video xong: {ok_count}/{total} OK, {fail_count} fail"
        _log(f"══ {summary} ══")
        color_bg = C["green_light"] if fail_count == 0 else C["red_light"]
        color_fg = C["green"] if fail_count == 0 else C["red"]
        root.after(0, self._set_info, summary, color_bg, color_fg)
        root.after(0, lambda: self.bdc_changevideo_btn.configure(
            state="normal", text="Change Video"))

    # ── Sub-tab: Chèn Intro ──────────────────────────────────────────
    def _build_intro_section(self, f):
        ctk.CTkLabel(f, text="Chèn Intro", font=FONT["small_bold"],
                     text_color=C["text"]).pack(anchor="w", pady=(0, 2))

        r1 = ctk.CTkFrame(f, fg_color="transparent")
        r1.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(r1, text="Thư mục intro:", width=95, anchor="w",
                     font=FONT["small"], text_color=C["text_light"]).pack(side="left")
        ctk.CTkEntry(r1, textvariable=self.intro_folder_var, height=28,
                     fg_color=C["input_bg"], border_color=C["input_border"],
                     text_color=C["text"], corner_radius=6, font=FONT["small"]
                     ).pack(side="left", fill="x", expand=True, padx=(4, 4))
        ctk.CTkButton(r1, text="...", width=28, height=28, corner_radius=6,
                      fg_color=C["tab_bg"], text_color=C["text"],
                      hover_color=C["primary_muted"], border_width=1,
                      border_color=C["input_border"], font=FONT["small"],
                      command=lambda: self._browse_dir(self.intro_folder_var)
                      ).pack(side="left")

        self.intro_btn = ctk.CTkButton(
            f, text="Chèn Intro", height=36, corner_radius=8,
            fg_color=C["accent"], hover_color="#7c3aed",
            text_color=C["text_white"], font=FONT["button"],
            command=self._on_run_intro
        )
        self.intro_btn.pack(fill="x")

        ctk.CTkFrame(f, fg_color=C["border"], height=1
                     ).pack(fill="x", pady=(14, 10))

    def _validate_intro_data(self, selected, intro_folder):
        """Check mỗi project có file intro tương ứng trong intro_folder."""
        errors = []
        for idx, draft in selected:
            name = draft.get("draft_name", "?")
            if not self._resolve_path(draft):
                errors.append(f"[{name}] Không tìm thấy draft folder trong CapCut")
                continue

            intro_path = sync_sub_engine.resolve_intro_path(intro_folder, name)
            if not intro_path:
                errors.append(f"[{name}] Không tìm thấy file intro tương ứng "
                              f"(vd 'intro-video004.mp4' cho 'bodycam-video004')")
        return errors

    def _on_run_intro(self):
        try:
            selected = self.app.project_list.get_selected()
            if not selected:
                self._set_info("Chưa chọn project nào!", C["red_light"], C["red"])
                return

            intro_folder = self.intro_folder_var.get().strip()
            if not intro_folder or not os.path.isdir(intro_folder):
                self._set_info("Thư mục intro không hợp lệ!", C["red_light"], C["red"])
                return

            errors = self._validate_intro_data(selected, intro_folder)
            if errors:
                self._append_log("[INTRO VALIDATE] Data không hợp lệ:")
                for e in errors:
                    self._append_log(f"  - {e}")
                self._set_info(f"Validate fail: {len(errors)} lỗi",
                               C["red_light"], C["red"])
                messagebox.showerror(
                    "Chèn Intro — Validate Fail",
                    "Kiểm tra dữ liệu thất bại. Chưa chạy gì cả.\n\n" + "\n".join(errors)
                )
                return

            names = [d.get("draft_name", "?") for _, d in selected]
            preview = ", ".join(names[:5]) + ("..." if len(names) > 5 else "")
            confirm = messagebox.askokcancel(
                "Chèn Intro",
                f"Validate OK. Chạy {len(selected)} project:\n{preview}\n\n"
                f"Intro folder: {intro_folder}\n\n"
                "Dịch toàn bộ timeline hiện có về sau.\n"
                "Thoát CapCut trước khi tiếp tục.\nOK?"
            )
            if not confirm:
                return

            self.intro_btn.configure(state="disabled", text="Đang chạy...")
            self._set_info(f"Chèn Intro: {len(selected)} projects...",
                           C["primary_light"], C["primary"])

            threading.Thread(
                target=self._run_intro,
                args=(selected, intro_folder),
                daemon=True,
            ).start()
        except Exception as e:
            import traceback
            self._append_log(f"[INTRO] EXCEPTION: {traceback.format_exc()}")
            self._set_info(f"Error: {e}", C["red_light"], C["red"])

    def _run_intro(self, selected, intro_folder):
        root = self.app.root
        _log = self._make_log_fn()

        ok_count = 0
        fail_count = 0
        total = len(selected)

        for i, (idx, draft) in enumerate(selected, start=1):
            name = draft.get("draft_name", "?")
            draft_path = self._resolve_path(draft)

            _log(f"── [{i}/{total}] Chèn Intro: {name} ──")
            root.after(0, self.app.project_list.set_status, idx, "...", C["primary"])
            root.after(0, self._set_info, f"[{i}/{total}] {name}...",
                       C["primary_light"], C["primary"])

            if not draft_path:
                _log("  FAIL: draft folder not found")
                root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])
                fail_count += 1
                continue

            intro_path = sync_sub_engine.resolve_intro_path(intro_folder, name)
            if not intro_path:
                _log(f"  FAIL: không tìm thấy intro cho '{name}'")
                root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])
                fail_count += 1
                continue
            _log(f"  intro: {os.path.basename(intro_path)}")

            try:
                errs = sync_sub_engine.preflight_insert_intro(draft_path, intro_path)
            except Exception as e:
                errs = [f"preflight lỗi: {e}"]
            if errs:
                _log(f"  PREFLIGHT FAIL ({len(errs)} lỗi) — bỏ qua, KHÔNG đụng vào project:")
                for m in errs[:10]:
                    _log(f"    - {m}")
                root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])
                fail_count += 1
                continue
            _log("  preflight OK")

            try:
                r = sync_sub_engine.insert_intro(
                    draft_path, intro_path, backup=True, log_fn=_log)
                _log(f"  {'OK' if r.success else 'FAIL'}: {r.message}")
                project_ok = r.success
            except Exception:
                import traceback
                _log(f"  EXCEPTION: {traceback.format_exc()}")
                project_ok = False

            if project_ok:
                ok_count += 1
                root.after(0, self.app.project_list.set_status, idx, "OK", C["green"])
                _log(f"  ✓ DONE: {name}")
            else:
                fail_count += 1
                root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])
                _log(f"  ✗ FAIL: {name}")

        summary = f"Chèn Intro xong: {ok_count}/{total} OK, {fail_count} fail"
        _log(f"══ {summary} ══")
        color_bg = C["green_light"] if fail_count == 0 else C["red_light"]
        color_fg = C["green"] if fail_count == 0 else C["red"]
        root.after(0, self._set_info, summary, color_bg, color_fg)
        root.after(0, lambda: self.intro_btn.configure(
            state="normal", text="Chèn Intro"))

    # ── Sub-tab: Chèn Intro/Outro ────────────────────────────────────
    def _build_outro_tab(self, parent):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=10, pady=6)

        self._build_intro_section(f)

        ctk.CTkLabel(f, text="Chèn Outro", font=FONT["small_bold"],
                     text_color=C["text"]).pack(anchor="w", pady=(0, 2))

        r1 = ctk.CTkFrame(f, fg_color="transparent")
        r1.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(r1, text="Thư mục outro:", width=95, anchor="w",
                     font=FONT["small"], text_color=C["text_light"]).pack(side="left")
        ctk.CTkEntry(r1, textvariable=self.outro_folder_var, height=28,
                     fg_color=C["input_bg"], border_color=C["input_border"],
                     text_color=C["text"], corner_radius=6, font=FONT["small"]
                     ).pack(side="left", fill="x", expand=True, padx=(4, 4))
        ctk.CTkButton(r1, text="...", width=28, height=28, corner_radius=6,
                      fg_color=C["tab_bg"], text_color=C["text"],
                      hover_color=C["primary_muted"], border_width=1,
                      border_color=C["input_border"], font=FONT["small"],
                      command=lambda: self._browse_dir(self.outro_folder_var)
                      ).pack(side="left")

        self.outro_btn = ctk.CTkButton(
            f, text="Chèn Outro", height=36, corner_radius=8,
            fg_color=C["accent"], hover_color="#7c3aed",
            text_color=C["text_white"], font=FONT["button"],
            command=self._on_run_outro
        )
        self.outro_btn.pack(fill="x")

        ctk.CTkFrame(f, fg_color=C["border"], height=1
                     ).pack(fill="x", pady=(14, 10))

        ctk.CTkLabel(f, text="clear-sub-blur", font=FONT["small_bold"],
                     text_color=C["text"]).pack(anchor="w", pady=(0, 6))

        self.clear_sub_blur_btn = ctk.CTkButton(
            f, text="clear-sub-blur", height=36, corner_radius=8,
            fg_color=C["primary"], hover_color=C["primary_hover"],
            text_color=C["text_white"], font=FONT["button"],
            command=self._on_run_clear_sub_blur
        )
        self.clear_sub_blur_btn.pack(fill="x")

        ctk.CTkFrame(f, fg_color=C["border"], height=1
                     ).pack(fill="x", pady=(14, 10))

        ctk.CTkLabel(f, text="Effect narration", font=FONT["small_bold"],
                     text_color=C["text"]).pack(anchor="w", pady=(0, 6))

        self.effect_narration_btn = ctk.CTkButton(
            f, text="Effect narration", height=36, corner_radius=8,
            fg_color=C["accent"], hover_color="#7c3aed",
            text_color=C["text_white"], font=FONT["button"],
            command=self._on_run_effect_narration
        )
        self.effect_narration_btn.pack(fill="x")

    def _on_run_effect_narration(self):
        try:
            selected = self.app.project_list.get_selected()
            if not selected:
                self._set_info("Chưa chọn project nào!", C["red_light"], C["red"])
                return

            names = [d.get("draft_name", "?") for _, d in selected]
            preview = ", ".join(names[:5]) + ("..." if len(names) > 5 else "")
            confirm = messagebox.askokcancel(
                "Effect narration",
                f"Chạy {len(selected)} project:\n{preview}\n\n"
                f"Random effect mẫu từ '{sync_sub_engine.EFFECT_SOURCE_PROJECT}' "
                "cho các đoạn narration.\n\n"
                "Thoát CapCut trước khi tiếp tục.\nOK?"
            )
            if not confirm:
                return

            self.effect_narration_btn.configure(state="disabled", text="Đang chạy...")
            self._set_info(f"Effect narration: {len(selected)} projects...",
                           C["primary_light"], C["primary"])

            threading.Thread(
                target=self._run_effect_narration, args=(selected,), daemon=True
            ).start()
        except Exception as e:
            import traceback
            self._append_log(f"[EFFECT NARRATION] EXCEPTION: {traceback.format_exc()}")
            self._set_info(f"Error: {e}", C["red_light"], C["red"])

    def _run_effect_narration(self, selected):
        root = self.app.root
        _log = self._make_log_fn()

        ok_count = 0
        fail_count = 0
        total = len(selected)

        source_path = self._resolve_path({"draft_name": sync_sub_engine.EFFECT_SOURCE_PROJECT})
        pool = []
        pool_err = None
        if not source_path:
            pool_err = f"không tìm thấy project nguồn '{sync_sub_engine.EFFECT_SOURCE_PROJECT}'"
        else:
            try:
                pool = sync_sub_engine.load_narration_effect_pool(source_path)
            except Exception as e:
                pool_err = f"không đọc được effect mẫu: {e}"
        if pool_err or not pool:
            _log(f"  FAIL: {pool_err or 'không có effect mẫu nào'}")
            for idx, _ in selected:
                root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])
            root.after(0, self._set_info, "Effect narration: lỗi lấy effect mẫu",
                       C["red_light"], C["red"])
            root.after(0, lambda: self.effect_narration_btn.configure(
                state="normal", text="Effect narration"))
            return
        _log(f"  effect mẫu: {', '.join(sorted({m.get('name','?') for m, _ in pool}))}")

        for i, (idx, draft) in enumerate(selected, start=1):
            name = draft.get("draft_name", "?")
            draft_path = self._resolve_path(draft)

            _log(f"── [{i}/{total}] Effect narration: {name} ──")
            root.after(0, self.app.project_list.set_status, idx, "...", C["primary"])
            root.after(0, self._set_info, f"[{i}/{total}] {name}...",
                       C["primary_light"], C["primary"])

            if not draft_path:
                _log("  FAIL: draft folder not found")
                root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])
                fail_count += 1
                continue

            try:
                errs = sync_sub_engine.preflight_narration_effect(draft_path, pool)
            except Exception as e:
                errs = [f"preflight lỗi: {e}"]
            if errs:
                _log(f"  PREFLIGHT FAIL — bỏ qua, KHÔNG đụng vào project:")
                for m in errs[:10]:
                    _log(f"    - {m}")
                root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])
                fail_count += 1
                continue

            try:
                r = sync_sub_engine.apply_narration_effect(
                    draft_path, pool, backup=True, log_fn=_log)
                _log(f"  {'OK' if r.success else 'FAIL'}: {r.message}")
                project_ok = r.success
            except Exception:
                import traceback
                _log(f"  EXCEPTION: {traceback.format_exc()}")
                project_ok = False

            if project_ok:
                ok_count += 1
                root.after(0, self.app.project_list.set_status, idx, "OK", C["green"])
                _log(f"  ✓ DONE: {name}")
            else:
                fail_count += 1
                root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])
                _log(f"  ✗ FAIL: {name}")

        summary = f"Effect narration xong: {ok_count}/{total} OK, {fail_count} fail"
        _log(f"══ {summary} ══")
        color_bg = C["green_light"] if fail_count == 0 else C["red_light"]
        color_fg = C["green"] if fail_count == 0 else C["red"]
        root.after(0, self._set_info, summary, color_bg, color_fg)
        root.after(0, lambda: self.effect_narration_btn.configure(
            state="normal", text="Effect narration"))

    def _on_run_clear_sub_blur(self):
        try:
            selected = self.app.project_list.get_selected()
            if not selected:
                self._set_info("Chưa chọn project nào!", C["red_light"], C["red"])
                return

            names = [d.get("draft_name", "?") for _, d in selected]
            preview = ", ".join(names[:5]) + ("..." if len(names) > 5 else "")
            confirm = messagebox.askokcancel(
                "clear-sub-blur",
                f"Chạy {len(selected)} project:\n{preview}\n\n"
                "Xoá sub + cắt blur trên video narration và outro.\n\n"
                "Thoát CapCut trước khi tiếp tục.\nOK?"
            )
            if not confirm:
                return

            self.clear_sub_blur_btn.configure(state="disabled", text="Đang chạy...")
            self._set_info(f"clear-sub-blur: {len(selected)} projects...",
                           C["primary_light"], C["primary"])

            threading.Thread(
                target=self._run_clear_sub_blur, args=(selected,), daemon=True
            ).start()
        except Exception as e:
            import traceback
            self._append_log(f"[CLEAR-SUB-BLUR] EXCEPTION: {traceback.format_exc()}")
            self._set_info(f"Error: {e}", C["red_light"], C["red"])

    def _run_clear_sub_blur(self, selected):
        root = self.app.root
        _log = self._make_log_fn()

        ok_count = 0
        fail_count = 0
        total = len(selected)

        for i, (idx, draft) in enumerate(selected, start=1):
            name = draft.get("draft_name", "?")
            draft_path = self._resolve_path(draft)

            _log(f"── [{i}/{total}] clear-sub-blur: {name} ──")
            root.after(0, self.app.project_list.set_status, idx, "...", C["primary"])
            root.after(0, self._set_info, f"[{i}/{total}] {name}...",
                       C["primary_light"], C["primary"])

            if not draft_path:
                _log("  FAIL: draft folder not found")
                root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])
                fail_count += 1
                continue

            try:
                errs = sync_sub_engine.preflight_clear_sub_blur(draft_path)
            except Exception as e:
                errs = [f"preflight lỗi: {e}"]
            if errs:
                _log(f"  PREFLIGHT FAIL — bỏ qua, KHÔNG đụng vào project:")
                for m in errs[:10]:
                    _log(f"    - {m}")
                root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])
                fail_count += 1
                continue

            try:
                r = sync_sub_engine.clear_sub_blur(draft_path, backup=True, log_fn=_log)
                _log(f"  {'OK' if r.success else 'FAIL'}: {r.message}")
                project_ok = r.success
            except Exception:
                import traceback
                _log(f"  EXCEPTION: {traceback.format_exc()}")
                project_ok = False

            if project_ok:
                ok_count += 1
                root.after(0, self.app.project_list.set_status, idx, "OK", C["green"])
                _log(f"  ✓ DONE: {name}")
            else:
                fail_count += 1
                root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])
                _log(f"  ✗ FAIL: {name}")

        summary = f"clear-sub-blur xong: {ok_count}/{total} OK, {fail_count} fail"
        _log(f"══ {summary} ══")
        color_bg = C["green_light"] if fail_count == 0 else C["red_light"]
        color_fg = C["green"] if fail_count == 0 else C["red"]
        root.after(0, self._set_info, summary, color_bg, color_fg)
        root.after(0, lambda: self.clear_sub_blur_btn.configure(
            state="normal", text="clear-sub-blur"))

    def _validate_outro_data(self, selected, outro_folder):
        """Check mỗi project có file outro tương ứng trong outro_folder."""
        errors = []
        for idx, draft in selected:
            name = draft.get("draft_name", "?")
            if not self._resolve_path(draft):
                errors.append(f"[{name}] Không tìm thấy draft folder trong CapCut")
                continue

            outro_path = sync_sub_engine.resolve_outro_path(outro_folder, name)
            if not outro_path:
                errors.append(f"[{name}] Không tìm thấy file outro tương ứng "
                              f"(vd 'outro-video004.mp4' cho 'bodycam-video004')")
        return errors

    def _on_run_outro(self):
        try:
            selected = self.app.project_list.get_selected()
            if not selected:
                self._set_info("Chưa chọn project nào!", C["red_light"], C["red"])
                return

            outro_folder = self.outro_folder_var.get().strip()
            if not outro_folder or not os.path.isdir(outro_folder):
                self._set_info("Thư mục outro không hợp lệ!", C["red_light"], C["red"])
                return

            errors = self._validate_outro_data(selected, outro_folder)
            if errors:
                self._append_log("[OUTRO VALIDATE] Data không hợp lệ:")
                for e in errors:
                    self._append_log(f"  - {e}")
                self._set_info(f"Validate fail: {len(errors)} lỗi",
                               C["red_light"], C["red"])
                messagebox.showerror(
                    "Chèn Outro — Validate Fail",
                    "Kiểm tra dữ liệu thất bại. Chưa chạy gì cả.\n\n" + "\n".join(errors)
                )
                return

            names = [d.get("draft_name", "?") for _, d in selected]
            preview = ", ".join(names[:5]) + ("..." if len(names) > 5 else "")
            confirm = messagebox.askokcancel(
                "Chèn Outro",
                f"Validate OK. Chạy {len(selected)} project:\n{preview}\n\n"
                f"Outro folder: {outro_folder}\n\n"
                "Thoát CapCut trước khi tiếp tục.\nOK?"
            )
            if not confirm:
                return

            self.outro_btn.configure(state="disabled", text="Đang chạy...")
            self._set_info(f"Chèn Outro: {len(selected)} projects...",
                           C["primary_light"], C["primary"])

            threading.Thread(
                target=self._run_outro,
                args=(selected, outro_folder),
                daemon=True,
            ).start()
        except Exception as e:
            import traceback
            self._append_log(f"[OUTRO] EXCEPTION: {traceback.format_exc()}")
            self._set_info(f"Error: {e}", C["red_light"], C["red"])

    def _run_outro(self, selected, outro_folder):
        root = self.app.root
        _log = self._make_log_fn()

        ok_count = 0
        fail_count = 0
        total = len(selected)

        for i, (idx, draft) in enumerate(selected, start=1):
            name = draft.get("draft_name", "?")
            draft_path = self._resolve_path(draft)

            _log(f"── [{i}/{total}] Chèn Outro: {name} ──")
            root.after(0, self.app.project_list.set_status, idx, "...", C["primary"])
            root.after(0, self._set_info, f"[{i}/{total}] {name}...",
                       C["primary_light"], C["primary"])

            if not draft_path:
                _log("  FAIL: draft folder not found")
                root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])
                fail_count += 1
                continue

            outro_path = sync_sub_engine.resolve_outro_path(outro_folder, name)
            if not outro_path:
                _log(f"  FAIL: không tìm thấy outro cho '{name}'")
                root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])
                fail_count += 1
                continue
            _log(f"  outro: {os.path.basename(outro_path)}")

            try:
                errs = sync_sub_engine.preflight_insert_outro(draft_path, outro_path)
            except Exception as e:
                errs = [f"preflight lỗi: {e}"]
            if errs:
                _log(f"  PREFLIGHT FAIL ({len(errs)} lỗi) — bỏ qua, KHÔNG đụng vào project:")
                for m in errs[:10]:
                    _log(f"    - {m}")
                root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])
                fail_count += 1
                continue
            _log("  preflight OK")

            try:
                r = sync_sub_engine.insert_outro(
                    draft_path, outro_path, backup=True, log_fn=_log)
                _log(f"  {'OK' if r.success else 'FAIL'}: {r.message}")
                project_ok = r.success
            except Exception:
                import traceback
                _log(f"  EXCEPTION: {traceback.format_exc()}")
                project_ok = False

            if project_ok:
                ok_count += 1
                root.after(0, self.app.project_list.set_status, idx, "OK", C["green"])
                _log(f"  ✓ DONE: {name}")
            else:
                fail_count += 1
                root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])
                _log(f"  ✗ FAIL: {name}")

        summary = f"Chèn Outro xong: {ok_count}/{total} OK, {fail_count} fail"
        _log(f"══ {summary} ══")
        color_bg = C["green_light"] if fail_count == 0 else C["red_light"]
        color_fg = C["green"] if fail_count == 0 else C["red"]
        root.after(0, self._set_info, summary, color_bg, color_fg)
        root.after(0, lambda: self.outro_btn.configure(
            state="normal", text="Chèn Outro"))

    @staticmethod
    def _read_text(path: str) -> str:
        for enc in ("utf-8-sig", "utf-8", "utf-16", "cp1252"):
            try:
                with open(path, "r", encoding=enc) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
        with open(path, "rb") as f:
            return f.read().decode("utf-8", errors="ignore")
