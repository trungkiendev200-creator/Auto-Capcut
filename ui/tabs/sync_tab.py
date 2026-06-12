"""Tab Đồng bộ âm thanh."""

import os
import threading
import customtkinter as ctk
from tkinter import messagebox

from ui.theme import COLORS as C, FONT
from core import sync_engine, split_picture_engine


class SyncTab:
    """Builds and manages the Sync Audio tab (sub-tabs: Đồng bộ + Split Picture)."""

    VIDEO_MODES = {
        "Cắt Video (Cut)": sync_engine.VIDEO_MODE_CUT,
        "Điều chỉnh Speed": sync_engine.VIDEO_MODE_SPEED,
    }

    def __init__(self, parent: ctk.CTkFrame, app):
        self.app = app
        self._build(parent)

    def _build(self, parent):
        subtabs = ctk.CTkTabview(
            parent, fg_color="transparent", corner_radius=8,
            segmented_button_fg_color=C["tab_bg"],
            segmented_button_selected_color=C["primary"],
            segmented_button_selected_hover_color=C["primary_hover"],
            segmented_button_unselected_color=C["tab_bg"],
            segmented_button_unselected_hover_color=C["tab_hover"],
            text_color=C["text"],
        )
        subtabs.pack(expand=True, fill="both", padx=4, pady=4)

        self._build_sync(subtabs.add("Đồng bộ"))
        self._build_split(subtabs.add("Split Picture"))

    # ══════════════════════════════════════════════════════════════════
    # SUB-TAB: Đồng bộ
    # ══════════════════════════════════════════════════════════════════
    def _build_sync(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(expand=True, fill="both", padx=12, pady=8)

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

    # ══════════════════════════════════════════════════════════════════
    # SUB-TAB: Split Picture
    # ══════════════════════════════════════════════════════════════════
    def _build_split(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(expand=True, fill="both", padx=12, pady=8)

        ctk.CTkLabel(
            frame, text="Split Picture",
            font=FONT["heading"], text_color=C["text"]
        ).pack(anchor="w", pady=(0, 4))

        ctk.CTkLabel(
            frame,
            text="Cắt mỗi ảnh dài hơn 'a' giây thành nhiều đoạn ngắn (cùng 1 ảnh), "
                 "mỗi đoạn dài ngẫu nhiên trong [x; y] giây. Audio giữ nguyên.",
            font=FONT["small"], text_color=C["text_light"], justify="left", wraplength=520
        ).pack(anchor="w", pady=(0, 12))

        # Params row
        param_row = ctk.CTkFrame(frame, fg_color=C["primary_light"], corner_radius=8)
        param_row.pack(fill="x", pady=(0, 10))
        p_inner = ctk.CTkFrame(param_row, fg_color="transparent")
        p_inner.pack(fill="x", padx=12, pady=10)

        def _num_field(label, default, width=55):
            ctk.CTkLabel(p_inner, text=label, font=FONT["small"],
                          text_color=C["text"]).pack(side="left")
            var = ctk.StringVar(value=default)
            ctk.CTkEntry(p_inner, textvariable=var, width=width, height=28,
                          fg_color=C["card"], border_color=C["input_border"],
                          text_color=C["text"], corner_radius=6).pack(side="left", padx=(4, 14))
            return var

        self.split_a_var = _num_field("a (min, s):", "8")
        self.split_x_var = _num_field("x (s):", "3")
        self.split_y_var = _num_field("y (s):", "6")

        # Mirror checkbox
        self.split_mirror_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            frame, text="Phản chiếu 50% ảnh (Mirror) — lật ngang xen kẽ các đoạn cắt ra",
            variable=self.split_mirror_var,
            font=FONT["small"], text_color=C["text"],
            checkbox_width=18, checkbox_height=18,
            fg_color=C["primary"], hover_color=C["primary_hover"],
        ).pack(anchor="w", pady=(0, 10))

        # Info box
        self.split_info = ctk.CTkLabel(
            frame, text="Chọn project bên phải rồi bấm Cắt ảnh",
            font=FONT["body"], text_color=C["text_light"],
            fg_color=C["primary_light"], corner_radius=8, height=36
        )
        self.split_info.pack(fill="x", pady=(0, 8))

        # Log
        self.split_log = ctk.CTkTextbox(
            frame, height=80, fg_color=C["input_bg"],
            border_color=C["input_border"], border_width=1,
            corner_radius=8, text_color=C["text"], font=FONT["mono"]
        )
        self.split_log.pack(fill="both", expand=True, pady=(0, 10))
        self.split_log.configure(state="disabled")

        # Button
        self.split_btn = ctk.CTkButton(
            frame, text="Cắt ảnh", height=42, corner_radius=10,
            fg_color=C["primary"], hover_color=C["primary_hover"],
            font=FONT["button"], text_color=C["text_white"],
            command=self._on_split_click
        )
        self.split_btn.pack(fill="x")

    def _append_split_log(self, text: str):
        self.split_log.configure(state="normal")
        self.split_log.insert("end", text + "\n")
        self.split_log.see("end")
        self.split_log.configure(state="disabled")

    def _set_split_info(self, text: str, bg: str, fg: str):
        self.split_info.configure(text=text, fg_color=bg, text_color=fg)

    def _on_split_click(self):
        selected = self.app.project_list.get_selected()
        if not selected:
            self._set_split_info("Chưa chọn project nào!", C["red_light"], C["red"])
            return

        # Validate tham số
        try:
            a = float(self.split_a_var.get())
            x = float(self.split_x_var.get())
            y = float(self.split_y_var.get())
        except ValueError:
            self._set_split_info("Tham số a/x/y phải là số!", C["red_light"], C["red"])
            return
        if not (a > 0 and x > 0 and y >= x):
            self._set_split_info("Cần a>0, 0<x<=y!", C["red_light"], C["red"])
            return

        mirror = self.split_mirror_var.get()
        confirm = messagebox.askokcancel(
            "Cảnh báo",
            "Vui lòng thoát khỏi dự án trong CapCut trước khi cắt ảnh!\n\n"
            f"a={a}s, mỗi đoạn ∈ [{x}; {y}]s"
            f"{', Mirror 50%' if mirror else ''}.\n"
            "Bấm OK nếu đã thoát CapCut."
        )
        if not confirm:
            return

        self.split_btn.configure(state="disabled", text="Đang xử lý...")
        self._set_split_info(
            f"Đang cắt ảnh cho {len(selected)} project...",
            C["primary_light"], C["primary"]
        )
        threading.Thread(
            target=self._run_split, args=(selected, a, x, y, mirror), daemon=True
        ).start()

    def _run_split(self, selected, a, x, y, mirror):
        root = self.app.root
        total_ok = 0
        total_fail = 0

        for idx, draft in selected:
            name = draft.get("draft_name", "?")
            path = draft.get("draft_fold_path", "")

            if not path or not os.path.isdir(path):
                root.after(0, self._append_split_log, f"[SKIP] {name}: folder not found")
                root.after(0, self.app.project_list.set_status, idx, "Error", C["red"])
                total_fail += 1
                continue

            root.after(0, self._append_split_log, f"[SPLIT] {name}...")
            root.after(0, self.app.project_list.set_status, idx, "...", C["primary"])

            try:
                result = split_picture_engine.split_pictures(path, a, x, y, mirror=mirror)
            except Exception as e:
                result = split_picture_engine.SplitResult(False, str(e))

            if result.success:
                root.after(0, self._append_split_log, f"  OK: {result.message}")
                root.after(0, self.app.project_list.set_status, idx, "Done", C["green"])
                total_ok += 1
            else:
                root.after(0, self._append_split_log, f"  FAIL: {result.message}")
                root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])
                total_fail += 1

        summary = f"Hoàn tất: {total_ok} OK, {total_fail} lỗi"
        color = C["green"] if total_fail == 0 else C["red"]
        light = C["green_light"] if total_fail == 0 else C["red_light"]
        root.after(0, lambda: self._set_split_info(summary, light, color))
        root.after(0, lambda: self.split_btn.configure(state="normal", text="Cắt ảnh"))
        root.after(0, lambda: self.app.status_var.set(f"  {summary}"))
