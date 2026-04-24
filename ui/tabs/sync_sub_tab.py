"""Tab SYNC SUB(COPS) — cut & import audio, export SRT, delete SRT, sync media."""

import os
import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox

from ui.theme import COLORS as C, FONT
from core import sync_sub_engine, capcut


class SyncSubTab:
    """Tab SYNC SUB(COPS) with sub-tabs."""

    VIDEO_MODES = {
        "Cắt Video (Cut)": sync_sub_engine.VIDEO_MODE_CUT,
        "Điều chỉnh Speed": sync_sub_engine.VIDEO_MODE_SPEED,
    }

    PASSWORD = "sondapda"

    def __init__(self, parent: ctk.CTkFrame, app):
        self.app = app
        self.audio_folder_var = ctk.StringVar()
        self.bg_video_var = ctk.StringVar()
        self.pic_folder_var = ctk.StringVar()
        self.promax_parent_var = ctk.StringVar()
        self.promax_bg_var = ctk.StringVar()
        self._unlocked = False
        self._parent = parent
        self._build_lock_screen(parent)

    def _build_lock_screen(self, parent):
        self._lock_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self._lock_frame.pack(expand=True, fill="both", padx=10, pady=6)

        box = ctk.CTkFrame(
            self._lock_frame, fg_color=C["card"], corner_radius=10,
            border_width=1, border_color=C["border"]
        )
        box.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            box, text="VIP5AE — Khu vực bảo mật",
            font=FONT["button"], text_color=C["text"]
        ).pack(padx=30, pady=(22, 4))
        ctk.CTkLabel(
            box, text="Nhập mật khẩu cấp 2 để tiếp tục",
            font=FONT["small"], text_color=C["text_light"]
        ).pack(padx=30, pady=(0, 10))

        self._pw_var = ctk.StringVar()
        self._pw_entry = ctk.CTkEntry(
            box, textvariable=self._pw_var, show="*", width=240, height=32,
            fg_color=C["input_bg"], border_color=C["input_border"],
            text_color=C["text"], corner_radius=6, font=FONT["small"],
            placeholder_text="Mật khẩu"
        )
        self._pw_entry.pack(padx=30, pady=(0, 6))
        self._pw_entry.bind("<Return>", lambda e: self._try_unlock())

        self._pw_msg = ctk.CTkLabel(
            box, text="", font=FONT["small"], text_color=C["red"]
        )
        self._pw_msg.pack(padx=30, pady=(0, 4))

        ctk.CTkButton(
            box, text="Mở khóa", height=32, width=240, corner_radius=6,
            fg_color=C["primary"], hover_color=C["primary_hover"],
            text_color=C["text_white"], font=FONT["small_bold"],
            command=self._try_unlock
        ).pack(padx=30, pady=(2, 22))

    def _try_unlock(self):
        if self._pw_var.get() == self.PASSWORD:
            self._unlocked = True
            self._lock_frame.destroy()
            self._build(self._parent)
        else:
            self._pw_msg.configure(text="Sai mật khẩu!")
            self._pw_var.set("")

    def _build(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(expand=True, fill="both", padx=10, pady=6)
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

        self._build_cut_tab(sub_tabs.add("Cut & Import"))
        self._build_delete_tab(sub_tabs.add("Xóa SRT"))
        self._build_sync_tab(sub_tabs.add("Sync Media"))
        self._build_picture_law_tab(sub_tabs.add("Insert Picture"))
        self._build_promax_tab(sub_tabs.add("PROMAX"))

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
        self.log.grid(row=2, column=0, sticky="nsew", pady=(2, 4))
        self.log.configure(state="disabled")

        # ── Bottom: Export SRT button ──
        self.export_btn = ctk.CTkButton(
            frame, text="Xuất SRT Info", height=32, corner_radius=8,
            fg_color=C["accent"], hover_color="#7c3aed",
            text_color=C["text_white"], font=FONT["small_bold"],
            command=self._on_export_srt
        )
        self.export_btn.grid(row=3, column=0, sticky="ew")

    # ── Build sub-tab: Cut & Import ──────────────────────────────────
    def _build_cut_tab(self, parent):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=10, pady=6)

        # Audio folder
        r1 = ctk.CTkFrame(f, fg_color="transparent")
        r1.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(r1, text="Audio folder:", width=85, anchor="w",
                     font=FONT["small"], text_color=C["text_light"]).pack(side="left")
        ctk.CTkEntry(r1, textvariable=self.audio_folder_var, height=28,
                     fg_color=C["input_bg"], border_color=C["input_border"],
                     text_color=C["text"], corner_radius=6, font=FONT["small"]
                     ).pack(side="left", fill="x", expand=True, padx=(4, 4))
        ctk.CTkButton(r1, text="...", width=28, height=28, corner_radius=6,
                      fg_color=C["tab_bg"], text_color=C["text"],
                      hover_color=C["primary_muted"], border_width=1,
                      border_color=C["input_border"], font=FONT["small"],
                      command=lambda: self._browse_dir(self.audio_folder_var)
                      ).pack(side="left")

        # Video nền
        r2 = ctk.CTkFrame(f, fg_color="transparent")
        r2.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(r2, text="Video nền:", width=85, anchor="w",
                     font=FONT["small"], text_color=C["text_light"]).pack(side="left")
        ctk.CTkEntry(r2, textvariable=self.bg_video_var, height=28,
                     fg_color=C["input_bg"], border_color=C["input_border"],
                     text_color=C["text"], corner_radius=6, font=FONT["small"]
                     ).pack(side="left", fill="x", expand=True, padx=(4, 4))
        ctk.CTkButton(r2, text="...", width=28, height=28, corner_radius=6,
                      fg_color=C["tab_bg"], text_color=C["text"],
                      hover_color=C["primary_muted"], border_width=1,
                      border_color=C["input_border"], font=FONT["small"],
                      command=self._browse_bg_video
                      ).pack(side="left")

        # Input label
        ctk.CTkLabel(f, text="Format: STT_SRT: audio1, audio2, ...",
                     font=("Segoe UI", 10), text_color=C["text_light"]
                     ).pack(anchor="w", pady=(2, 2))

        # Cut input
        self.cut_input = ctk.CTkTextbox(
            f, height=65, fg_color=C["input_bg"],
            border_color=C["input_border"], border_width=1,
            corner_radius=6, text_color=C["text"], font=FONT["mono"]
        )
        self.cut_input.pack(fill="x", pady=(0, 6))

        # Button
        self.cut_btn = ctk.CTkButton(
            f, text="Cut & Import Audio", height=36, corner_radius=8,
            fg_color=C["primary"], hover_color=C["primary_hover"],
            text_color=C["text_white"], font=FONT["button"],
            command=self._on_cut_import
        )
        self.cut_btn.pack(fill="x")

    # ── Build sub-tab: Xóa SRT ──────────────────────────────────────
    def _build_delete_tab(self, parent):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=10, pady=6)

        ctk.CTkLabel(f, text="Nhập STT sub cần xóa (VD: 5-6, 20, 468-469)",
                     font=FONT["small"], text_color=C["text_light"]
                     ).pack(anchor="w", pady=(0, 4))

        self.delete_input = ctk.CTkTextbox(
            f, height=80, fg_color=C["input_bg"],
            border_color=C["input_border"], border_width=1,
            corner_radius=6, text_color=C["text"], font=FONT["mono"]
        )
        self.delete_input.pack(fill="x", pady=(0, 6))

        self.delete_btn = ctk.CTkButton(
            f, text="Xóa SRT & Cắt Video", height=36, corner_radius=8,
            fg_color=C["red"], hover_color="#dc2626",
            text_color=C["text_white"], font=FONT["button"],
            command=self._on_delete
        )
        self.delete_btn.pack(fill="x")

    # ── Build sub-tab: Sync Media ────────────────────────────────────
    def _build_sync_tab(self, parent):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=10, pady=6)

        ctk.CTkLabel(f, text="Thay video nền bằng video gốc cắt random",
                     font=FONT["small"], text_color=C["text_light"]
                     ).pack(anchor="w", pady=(0, 6))

        # Speed
        r1 = ctk.CTkFrame(f, fg_color="transparent")
        r1.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(r1, text="Speed:", width=85, anchor="w",
                     font=FONT["small"], text_color=C["text_light"]).pack(side="left")
        self.speed_var = ctk.StringVar(value="1.3")
        ctk.CTkEntry(r1, textvariable=self.speed_var, height=28, width=80,
                     fg_color=C["input_bg"], border_color=C["input_border"],
                     text_color=C["text"], corner_radius=6, font=FONT["small"]
                     ).pack(side="left", padx=(4, 0))
        ctk.CTkLabel(r1, text="x  (1.0 = bình thường, 1.3 = nhanh 30%)",
                     font=("Segoe UI", 10), text_color=C["text_light"]
                     ).pack(side="left", padx=(8, 0))

        # Button
        self.sync_btn = ctk.CTkButton(
            f, text="Sync Media", height=36, corner_radius=8,
            fg_color=C["green"], hover_color="#16a34a",
            text_color=C["text_white"], font=FONT["button"],
            command=self._on_sync
        )
        self.sync_btn.pack(fill="x")

    # ── Public ───────────────────────────────────────────────────────
    # ── Build sub-tab: Insert Picture Law ──────────────────────────
    def _build_picture_law_tab(self, parent):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=10, pady=6)

        # Picture folder
        r1 = ctk.CTkFrame(f, fg_color="transparent")
        r1.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(r1, text="Ảnh folder:", width=85, anchor="w",
                     font=FONT["small"], text_color=C["text_light"]).pack(side="left")
        ctk.CTkEntry(r1, textvariable=self.pic_folder_var, height=28,
                     fg_color=C["input_bg"], border_color=C["input_border"],
                     text_color=C["text"], corner_radius=6, font=FONT["small"]
                     ).pack(side="left", fill="x", expand=True, padx=(4, 4))
        ctk.CTkButton(r1, text="...", width=28, height=28, corner_radius=6,
                      fg_color=C["tab_bg"], text_color=C["text"],
                      hover_color=C["primary_muted"], border_width=1,
                      border_color=C["input_border"], font=FONT["small"],
                      command=lambda: self._browse_dir(self.pic_folder_var)
                      ).pack(side="left")

        ctk.CTkLabel(f, text="Format: tên_ảnh: audio1, audio2  (VD: law_vanhook: 4, 5)",
                     font=("Segoe UI", 10), text_color=C["text_light"]
                     ).pack(anchor="w", pady=(2, 2))

        self.pic_input = ctk.CTkTextbox(
            f, height=70, fg_color=C["input_bg"],
            border_color=C["input_border"], border_width=1,
            corner_radius=6, text_color=C["text"], font=FONT["mono"]
        )
        self.pic_input.pack(fill="x", pady=(0, 4))

        # Animation checkbox
        import tkinter as tk
        self.pic_anim_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            f, text="Tự động animation (In + Out random)", variable=self.pic_anim_var,
            font=FONT["small"], text_color=C["text_light"],
            checkbox_width=16, checkbox_height=16,
            fg_color=C["primary"], hover_color=C["primary_hover"],
        ).pack(anchor="w", pady=(0, 6))

        self.pic_btn = ctk.CTkButton(
            f, text="Insert Picture Law", height=36, corner_radius=8,
            fg_color=C["accent"], hover_color="#7c3aed",
            text_color=C["text_white"], font=FONT["button"],
            command=self._on_insert_picture
        )
        self.pic_btn.pack(fill="x")

    def clear_inputs(self):
        """Clear tất cả input fields và log."""
        if not self._unlocked:
            return
        self.audio_folder_var.set("")
        self.bg_video_var.set("")
        self.pic_folder_var.set("")
        self.promax_parent_var.set("")
        self.promax_bg_var.set("")
        self.speed_var.set("1.3")
        if hasattr(self, "promax_speed_var"):
            self.promax_speed_var.set("1.3")
        self.cut_input.configure(state="normal")
        self.cut_input.delete("1.0", "end")
        self.delete_input.configure(state="normal")
        self.delete_input.delete("1.0", "end")
        self.pic_input.configure(state="normal")
        self.pic_input.delete("1.0", "end")
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

    def _browse_bg_video(self):
        path = filedialog.askopenfilename(
            title="Chọn video nền",
            filetypes=[("Video", "*.mp4 *.mov *.avi *.mkv"), ("All", "*.*")]
        )
        if path:
            self.bg_video_var.set(path)

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

    def _get_selected_project(self) -> tuple[int, dict] | None:
        selected = self.app.project_list.get_selected()
        if not selected:
            self._set_info("Chưa chọn project!", C["red_light"], C["red"])
            return None
        if len(selected) > 1:
            self._set_info("Chỉ chọn 1 project!", C["red_light"], C["red"])
            return None
        return selected[0]

    def _make_log_fn(self):
        root = self.app.root
        def _log(msg):
            root.after(0, self._append_log, msg)
        return _log

    # ── Export SRT ───────────────────────────────────────────────────
    def _on_export_srt(self):
        sel = self._get_selected_project()
        if sel is None:
            return
        idx, draft = sel
        name = draft.get("draft_name", "?")
        path = self._resolve_path(draft)
        if not path:
            self._set_info(f"Folder not found: {name}", C["red_light"], C["red"])
            return

        self.export_btn.configure(state="disabled", text="Đang xuất...")
        threading.Thread(target=self._run_export, args=(path, name), daemon=True).start()

    def _run_export(self, draft_path: str, project_name: str):
        root = self.app.root
        try:
            data = capcut.load_draft_content(draft_path)
            result_text = sync_sub_engine.export_srt_info(data)

            save_path = filedialog.asksaveasfilename(
                title="Lưu file SRT info",
                defaultextension=".txt",
                initialfile=f"{project_name}_srt_info.txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
            )
            if save_path:
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(result_text)
                root.after(0, self._append_log, f"[EXPORT] Saved: {save_path}")
                root.after(0, self._set_info,
                           f"Xuất SRT OK → {os.path.basename(save_path)}",
                           C["green_light"], C["green"])
            else:
                root.after(0, self._append_log, result_text)
                root.after(0, self._set_info, "SRT hiển thị trong log",
                           C["primary_light"], C["primary"])
        except Exception as e:
            root.after(0, self._append_log, f"[ERROR] {e}")
            root.after(0, self._set_info, f"Lỗi: {e}", C["red_light"], C["red"])
        finally:
            root.after(0, lambda: self.export_btn.configure(
                state="normal", text="Xuất SRT Info"))

    # ── Cut & Import Audio ──────────────────────────────────────────
    def _on_cut_import(self):
        try:
            sel = self._get_selected_project()
            if sel is None:
                return
            idx, draft = sel
            name = draft.get("draft_name", "?")
            path = self._resolve_path(draft)
            if not path:
                self._set_info(f"Folder not found: {name}", C["red_light"], C["red"])
                self._append_log(f"[CUT] FAIL: folder not found for {name}")
                return

            audio_folder = self.audio_folder_var.get()
            bg_video = self.bg_video_var.get()
            cut_text = self.cut_input.get("1.0", "end").strip()

            if not audio_folder:
                self._set_info("Chưa chọn audio folder!", C["red_light"], C["red"])
                return
            if not bg_video:
                self._set_info("Chưa chọn video nền!", C["red_light"], C["red"])
                return
            if not cut_text:
                self._set_info("Chưa nhập thông tin cắt!", C["red_light"], C["red"])
                return

            self._append_log(f"[CUT] Starting: {name}")
            self._append_log(f"  resolve_path: {path}")

            confirm = messagebox.askokcancel(
                "Cut & Import Audio",
                f"Project: {name}\nAudio: {audio_folder}\n"
                f"Video nền: {os.path.basename(bg_video)}\n\n"
                "Thoát CapCut trước khi tiếp tục.\nOK?"
            )
            if not confirm:
                self._append_log("  Cancelled by user")
                return

            self.cut_btn.configure(state="disabled", text="Đang xử lý...")
            self._set_info(f"Đang cut & import {name}...", C["primary_light"], C["primary"])

            threading.Thread(
                target=self._run_cut_import,
                args=(idx, draft, path, audio_folder, bg_video, cut_text),
                daemon=True
            ).start()
        except Exception as e:
            import traceback
            self._append_log(f"[CUT ERROR] {traceback.format_exc()}")
            self._set_info(f"Lỗi: {e}", C["red_light"], C["red"])

    def _run_cut_import(self, idx, draft, draft_path, audio_folder, bg_video, cut_text):
        root = self.app.root
        name = draft.get("draft_name", "?")
        _log = self._make_log_fn()
        _log(f"[CUT] {name}")
        _log(f"  path: {draft_path}")
        _log(f"  audio: {audio_folder}")
        _log(f"  bg: {bg_video}")
        _log(f"  input: {repr(cut_text[:200])}")
        root.after(0, self.app.project_list.set_status, idx, "...", C["primary"])

        try:
            result = sync_sub_engine.cut_and_import_audio(
                draft_path, audio_folder, bg_video, cut_text,
                backup=True, log_fn=_log
            )
        except Exception as e:
            import traceback
            err = traceback.format_exc()
            _log(f"[EXCEPTION] {err}")
            result = sync_sub_engine.SyncSubResult(False, str(e))

        if result.success:
            root.after(0, self._append_log, f"  OK: {result.message}")
            root.after(0, self.app.project_list.set_status, idx, "Done", C["green"])
            root.after(0, self._set_info, result.message, C["green_light"], C["green"])
        else:
            root.after(0, self._append_log, f"  FAIL: {result.message}")
            root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])
            root.after(0, self._set_info, result.message, C["red_light"], C["red"])

        root.after(0, lambda: self.cut_btn.configure(
            state="normal", text="Cut & Import Audio"))

    # ── Delete SRT & Cut Video ──────────────────────────────────────
    def _on_delete(self):
        sel = self._get_selected_project()
        if sel is None:
            return
        idx, draft = sel
        name = draft.get("draft_name", "?")
        path = self._resolve_path(draft)
        if not path:
            self._set_info(f"Folder not found: {name}", C["red_light"], C["red"])
            return

        delete_text = self.delete_input.get("1.0", "end").strip()
        if not delete_text:
            self._set_info("Chưa nhập STT sub cần xóa!", C["red_light"], C["red"])
            return

        indices = sync_sub_engine.parse_delete_input(delete_text)
        if not indices:
            self._set_info("Format sai! VD: 5-6, 20", C["red_light"], C["red"])
            return

        confirm = messagebox.askokcancel(
            "Xóa SRT & Cắt Video",
            f"Project: {name}\n"
            f"Xóa {len(indices)} sub: {', '.join(map(str, indices[:10]))}{'...' if len(indices) > 10 else ''}\n\n"
            "Thoát CapCut trước.\nOK?"
        )
        if not confirm:
            return

        self.delete_btn.configure(state="disabled", text="Đang xóa...")
        self._set_info(f"Đang xóa {name}...", C["primary_light"], C["primary"])

        threading.Thread(
            target=self._run_delete,
            args=(idx, draft, path, delete_text),
            daemon=True
        ).start()

    def _run_delete(self, idx, draft, draft_path, delete_text):
        root = self.app.root
        name = draft.get("draft_name", "?")
        root.after(0, self._append_log, f"[DELETE] {name}")
        root.after(0, self.app.project_list.set_status, idx, "...", C["primary"])

        try:
            result = sync_sub_engine.delete_srt_and_cut(
                draft_path, delete_text, backup=True, log_fn=self._make_log_fn()
            )
        except Exception as e:
            import traceback
            root.after(0, self._append_log, f"[ERROR] {traceback.format_exc()}")
            result = sync_sub_engine.SyncSubResult(False, str(e))

        if result.success:
            root.after(0, self._append_log, f"  OK: {result.message}")
            root.after(0, self.app.project_list.set_status, idx, "Done", C["green"])
            root.after(0, self._set_info, result.message, C["green_light"], C["green"])
        else:
            root.after(0, self._append_log, f"  FAIL: {result.message}")
            root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])
            root.after(0, self._set_info, result.message, C["red_light"], C["red"])

        root.after(0, lambda: self.delete_btn.configure(
            state="normal", text="Xóa SRT & Cắt Video"))

    # ── Sync Media ────────────────────────────────────────────────
    def _on_sync(self):
        try:
            sel = self._get_selected_project()
            if sel is None:
                return
            idx, draft = sel
            name = draft.get("draft_name", "?")
            path = self._resolve_path(draft)
            if not path:
                self._set_info(f"Folder not found: {name}", C["red_light"], C["red"])
                return

            try:
                speed = float(self.speed_var.get())
                if speed <= 0:
                    raise ValueError
            except ValueError:
                self._set_info("Speed không hợp lệ!", C["red_light"], C["red"])
                return

            confirm = messagebox.askokcancel(
                "Sync Media",
                f"Project: {name}\nSpeed: {speed}x\n\n"
                "Video nền sẽ bị thay bằng video gốc cắt random.\n"
                "Thoát CapCut trước.\nOK?"
            )
            if not confirm:
                return

            self.sync_btn.configure(state="disabled", text="Đang sync...")
            self._set_info(f"Đang sync {name}...", C["primary_light"], C["primary"])

            threading.Thread(
                target=self._run_sync,
                args=(idx, draft, path, speed),
                daemon=True
            ).start()
        except Exception as e:
            import traceback
            self._append_log(f"[SYNC ERROR] {traceback.format_exc()}")

    def _run_sync(self, idx, draft, draft_path, speed):
        root = self.app.root
        name = draft.get("draft_name", "?")
        _log = self._make_log_fn()
        _log(f"[SYNC] {name} @{speed}x")
        root.after(0, self.app.project_list.set_status, idx, "...", C["primary"])

        try:
            result = sync_sub_engine.sync_media_sub(
                draft_path, speed=speed,
                backup=True, log_fn=_log
            )
        except Exception as e:
            import traceback
            _log(f"[EXCEPTION] {traceback.format_exc()}")
            result = sync_sub_engine.SyncSubResult(False, str(e))

        if result.success:
            root.after(0, self._append_log, f"  OK: {result.message}")
            root.after(0, self.app.project_list.set_status, idx, "Done", C["green"])
            root.after(0, self._set_info, result.message, C["green_light"], C["green"])
        else:
            root.after(0, self._append_log, f"  FAIL: {result.message}")
            root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])
            root.after(0, self._set_info, result.message, C["red_light"], C["red"])

        root.after(0, lambda: self.sync_btn.configure(
            state="normal", text="Sync Media"))

    # ── Insert Picture Law ──────────────────────────────────────────
    def _on_insert_picture(self):
        try:
            sel = self._get_selected_project()
            if sel is None:
                return
            idx, draft = sel
            name = draft.get("draft_name", "?")
            path = self._resolve_path(draft)
            if not path:
                self._set_info(f"Folder not found: {name}", C["red_light"], C["red"])
                return

            pic_folder = self.pic_folder_var.get()
            pic_text = self.pic_input.get("1.0", "end").strip()

            if not pic_folder:
                self._set_info("Chưa chọn ảnh folder!", C["red_light"], C["red"])
                return
            if not pic_text:
                self._set_info("Chưa nhập mapping ảnh!", C["red_light"], C["red"])
                return

            confirm = messagebox.askokcancel(
                "Insert Picture Law",
                f"Project: {name}\nẢnh folder: {pic_folder}\n\n"
                "Thoát CapCut trước.\nOK?"
            )
            if not confirm:
                return

            self.pic_btn.configure(state="disabled", text="Đang chèn...")
            self._set_info(f"Đang chèn ảnh {name}...", C["primary_light"], C["primary"])

            add_anim = self.pic_anim_var.get()

            threading.Thread(
                target=self._run_insert_picture,
                args=(idx, draft, path, pic_folder, pic_text, add_anim),
                daemon=True
            ).start()
        except Exception as e:
            import traceback
            self._append_log(f"[PIC ERROR] {traceback.format_exc()}")

    def _run_insert_picture(self, idx, draft, draft_path, pic_folder, pic_text, add_anim):
        root = self.app.root
        name = draft.get("draft_name", "?")
        _log = self._make_log_fn()
        _log(f"[INSERT PIC] {name} (animation={'ON' if add_anim else 'OFF'})")
        root.after(0, self.app.project_list.set_status, idx, "...", C["primary"])

        try:
            result = sync_sub_engine.insert_picture_law(
                draft_path, pic_folder, pic_text,
                add_animation=add_anim, backup=True, log_fn=_log
            )
        except Exception as e:
            import traceback
            _log(f"[EXCEPTION] {traceback.format_exc()}")
            result = sync_sub_engine.SyncSubResult(False, str(e))

        if result.success:
            root.after(0, self._append_log, f"  OK: {result.message}")
            root.after(0, self.app.project_list.set_status, idx, "Done", C["green"])
            root.after(0, self._set_info, result.message, C["green_light"], C["green"])
        else:
            root.after(0, self._append_log, f"  FAIL: {result.message}")
            root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])
            root.after(0, self._set_info, result.message, C["red_light"], C["red"])

        root.after(0, lambda: self.pic_btn.configure(
            state="normal", text="Insert Picture Law"))

    # ── Build sub-tab: PROMAX ──────────────────────────────────────
    def _build_promax_tab(self, parent):
        import tkinter as tk

        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=10, pady=6)

        # Parent folder
        r1 = ctk.CTkFrame(f, fg_color="transparent")
        r1.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(r1, text="Thư mục cha:", width=95, anchor="w",
                     font=FONT["small"], text_color=C["text_light"]).pack(side="left")
        ctk.CTkEntry(r1, textvariable=self.promax_parent_var, height=28,
                     fg_color=C["input_bg"], border_color=C["input_border"],
                     text_color=C["text"], corner_radius=6, font=FONT["small"]
                     ).pack(side="left", fill="x", expand=True, padx=(4, 4))
        ctk.CTkButton(r1, text="...", width=28, height=28, corner_radius=6,
                      fg_color=C["tab_bg"], text_color=C["text"],
                      hover_color=C["primary_muted"], border_width=1,
                      border_color=C["input_border"], font=FONT["small"],
                      command=lambda: self._browse_dir(self.promax_parent_var)
                      ).pack(side="left")

        # Background video
        r2 = ctk.CTkFrame(f, fg_color="transparent")
        r2.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(r2, text="Video nền:", width=95, anchor="w",
                     font=FONT["small"], text_color=C["text_light"]).pack(side="left")
        ctk.CTkEntry(r2, textvariable=self.promax_bg_var, height=28,
                     fg_color=C["input_bg"], border_color=C["input_border"],
                     text_color=C["text"], corner_radius=6, font=FONT["small"]
                     ).pack(side="left", fill="x", expand=True, padx=(4, 4))
        ctk.CTkButton(r2, text="...", width=28, height=28, corner_radius=6,
                      fg_color=C["tab_bg"], text_color=C["text"],
                      hover_color=C["primary_muted"], border_width=1,
                      border_color=C["input_border"], font=FONT["small"],
                      command=self._browse_promax_bg
                      ).pack(side="left")

        # Speed
        r3 = ctk.CTkFrame(f, fg_color="transparent")
        r3.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(r3, text="Sync Speed:", width=95, anchor="w",
                     font=FONT["small"], text_color=C["text_light"]).pack(side="left")
        self.promax_speed_var = ctk.StringVar(value="1.3")
        ctk.CTkEntry(r3, textvariable=self.promax_speed_var, height=28, width=80,
                     fg_color=C["input_bg"], border_color=C["input_border"],
                     text_color=C["text"], corner_radius=6, font=FONT["small"]
                     ).pack(side="left", padx=(4, 0))
        self.promax_anim_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            r3, text="Animation cho ảnh", variable=self.promax_anim_var,
            font=FONT["small"], text_color=C["text_light"],
            checkbox_width=16, checkbox_height=16,
            fg_color=C["primary"], hover_color=C["primary_hover"],
        ).pack(side="left", padx=(12, 0))

        # Info
        info_text = (
            "Chọn nhiều project bên phải. Mỗi project map với thư mục con "
            "cùng tên trong thư mục cha.\n"
            "Mỗi subfolder cần có: narration/, law picture/, "
            "1-insert-radio.txt, 2-delete-narration.txt, 3-insert-law-picture.txt.\n"
            "Tool sẽ chạy tuần tự: Cut & Import → Xóa SRT → Sync Media → Insert Picture."
        )
        ctk.CTkLabel(f, text=info_text, font=("Segoe UI", 10),
                     text_color=C["text_light"], justify="left", wraplength=520
                     ).pack(anchor="w", pady=(4, 6))

        self.promax_btn = ctk.CTkButton(
            f, text="Run PROMAX", height=36, corner_radius=8,
            fg_color=C["accent"], hover_color="#7c3aed",
            text_color=C["text_white"], font=FONT["button"],
            command=self._on_run_promax
        )
        self.promax_btn.pack(fill="x")

    def _browse_promax_bg(self):
        path = filedialog.askopenfilename(
            title="Chọn video nền",
            filetypes=[("Video", "*.mp4 *.mov *.avi *.mkv"), ("All", "*.*")]
        )
        if path:
            self.promax_bg_var.set(path)

    # ── PROMAX: Run ────────────────────────────────────────────────
    def _on_run_promax(self):
        try:
            selected = self.app.project_list.get_selected()
            if not selected:
                self._set_info("Chưa chọn project nào!", C["red_light"], C["red"])
                return

            parent_folder = self.promax_parent_var.get().strip()
            bg_video = self.promax_bg_var.get().strip()

            if not parent_folder or not os.path.isdir(parent_folder):
                self._set_info("Thư mục cha không hợp lệ!", C["red_light"], C["red"])
                return
            if not bg_video or not os.path.isfile(bg_video):
                self._set_info("Video nền không hợp lệ!", C["red_light"], C["red"])
                return

            try:
                speed = float(self.promax_speed_var.get())
                if speed <= 0:
                    raise ValueError
            except ValueError:
                self._set_info("Speed không hợp lệ!", C["red_light"], C["red"])
                return

            add_anim = self.promax_anim_var.get()

            # Pre-flight validation: check all projects BEFORE running
            errors = self._validate_promax_data(selected, parent_folder)
            if errors:
                err_text = "\n".join(errors)
                self._append_log("[PROMAX VALIDATE] Data không hợp lệ:")
                for e in errors:
                    self._append_log(f"  - {e}")
                self._set_info(
                    f"Validate fail: {len(errors)} lỗi",
                    C["red_light"], C["red"]
                )
                messagebox.showerror(
                    "PROMAX — Validate Fail",
                    "Kiểm tra dữ liệu thất bại. Chưa chạy gì cả.\n\n"
                    + err_text
                )
                return

            names = [d.get("draft_name", "?") for _, d in selected]
            preview = ", ".join(names[:5]) + ("..." if len(names) > 5 else "")
            confirm = messagebox.askokcancel(
                "PROMAX",
                f"Validate OK. Chạy {len(selected)} project:\n{preview}\n\n"
                f"Parent: {parent_folder}\n"
                f"BG: {os.path.basename(bg_video)}\n"
                f"Speed: {speed}x | Animation: {'ON' if add_anim else 'OFF'}\n\n"
                "Thoát CapCut trước khi tiếp tục.\nOK?"
            )
            if not confirm:
                return

            self.promax_btn.configure(state="disabled", text="Đang chạy...")
            self._set_info(f"PROMAX: {len(selected)} projects...",
                           C["primary_light"], C["primary"])

            threading.Thread(
                target=self._run_promax,
                args=(selected, parent_folder, bg_video, speed, add_anim),
                daemon=True
            ).start()
        except Exception as e:
            import traceback
            self._append_log(f"[PROMAX ERROR] {traceback.format_exc()}")
            self._set_info(f"Lỗi: {e}", C["red_light"], C["red"])

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

    def _run_promax(self, selected, parent_folder, bg_video, speed, add_anim):
        root = self.app.root
        _log = self._make_log_fn()

        ok_count = 0
        fail_count = 0
        total = len(selected)

        for i, (idx, draft) in enumerate(selected, start=1):
            name = draft.get("draft_name", "?")
            draft_path = self._resolve_path(draft)

            _log(f"── [{i}/{total}] PROMAX: {name} ──")
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
            if not os.path.isdir(sub_folder):
                _log(f"  SKIP: subfolder not found: {sub_folder}")
                root.after(0, self.app.project_list.set_status, idx, "Skip", C["red"])
                fail_count += 1
                continue

            narration_folder = os.path.join(sub_folder, "narration")
            picture_folder = os.path.join(sub_folder, "law picture")
            cut_file = os.path.join(sub_folder, "1-insert-radio.txt")
            delete_file = os.path.join(sub_folder, "2-delete-narration.txt")
            pic_file = os.path.join(sub_folder, "3-insert-law-picture.txt")

            missing = []
            if not os.path.isdir(narration_folder):
                missing.append("narration/")
            if not os.path.isdir(picture_folder):
                missing.append("law picture/")
            if not os.path.isfile(cut_file):
                missing.append("1-insert-radio.txt")
            if not os.path.isfile(delete_file):
                missing.append("2-delete-narration.txt")
            if not os.path.isfile(pic_file):
                missing.append("3-insert-law-picture.txt")
            if missing:
                _log(f"  FAIL: missing {', '.join(missing)}")
                root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])
                fail_count += 1
                continue

            try:
                cut_text = self._read_text(cut_file)
                delete_text = self._read_text(delete_file)
                pic_text = self._read_text(pic_file)
            except Exception as e:
                _log(f"  FAIL: read txt error: {e}")
                root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])
                fail_count += 1
                continue

            project_ok = True

            # Step 1: Cut & Import
            _log(f"  [1/4] Cut & Import Audio")
            try:
                r = sync_sub_engine.cut_and_import_audio(
                    draft_path, narration_folder, bg_video, cut_text,
                    backup=True, log_fn=_log
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

            # Step 2: Delete SRT (optional)
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

            # Step 3: Sync Media
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

            # Step 4: Insert Picture
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

        summary = f"PROMAX xong: {ok_count}/{total} OK, {fail_count} fail"
        _log(f"══ {summary} ══")
        color_bg = C["green_light"] if fail_count == 0 else C["red_light"]
        color_fg = C["green"] if fail_count == 0 else C["red"]
        root.after(0, self._set_info, summary, color_bg, color_fg)
        root.after(0, lambda: self.promax_btn.configure(
            state="normal", text="Run PROMAX"))

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
