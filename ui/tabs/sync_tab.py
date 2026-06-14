"""Tab Đồng bộ âm thanh."""

import os
import threading
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox

from ui.theme import COLORS as C, FONT
from core import (sync_engine, split_picture_engine, ani_trans_story_engine,
                  keyframe_engine as kfe, keyframe_adv_engine as kfae)


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
        self._build_story(subtabs.add("Ani-Trans-Story"))
        self._build_kfadv(subtabs.add("Key Frame Nâng Cao"))

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

    # ══════════════════════════════════════════════════════════════════
    # SUB-TAB: Ani-Trans-Story
    # ══════════════════════════════════════════════════════════════════
    def _build_story(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(expand=True, fill="both", padx=12, pady=8)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)
        frame.grid_rowconfigure(1, weight=1)

        self._anim_items = ani_trans_story_engine.STORY_ANIMATIONS
        self._trans_items = ani_trans_story_engine.STORY_TRANSITIONS

        # ── Headers ───────────────────────────────────────────────────
        ctk.CTkLabel(frame, text=f"Animation-in ({len(self._anim_items)})",
                      font=FONT["small_bold"], text_color=C["text"]).grid(
            row=0, column=0, sticky="w", padx=(0, 6), pady=(0, 2))
        ctk.CTkLabel(frame, text=f"Transition ({len(self._trans_items)})",
                      font=FONT["small_bold"], text_color=C["text"]).grid(
            row=0, column=1, sticky="w", padx=(6, 0), pady=(0, 2))

        # ── Listboxes ─────────────────────────────────────────────────
        def _make_list(col, items):
            cont = tk.Frame(frame, bg="#ffffff", highlightthickness=1,
                            highlightbackground=C["border"])
            cont.grid(row=1, column=col, sticky="nsew",
                      padx=((0, 6) if col == 0 else (6, 0)))
            lb = tk.Listbox(
                cont, selectmode=tk.MULTIPLE, font=("Segoe UI", 11),
                bg="#ffffff", fg=C["text"], selectbackground=C["primary_light"],
                selectforeground=C["primary"], activestyle="none",
                highlightthickness=0, borderwidth=0, relief="flat",
            )
            sb = tk.Scrollbar(cont, orient="vertical", command=lb.yview)
            lb.configure(yscrollcommand=sb.set)
            lb.pack(side="left", fill="both", expand=True)
            sb.pack(side="right", fill="y")
            for name, _id, _cid, _cname, dur in items:
                lb.insert(tk.END, f"{name}  ({dur/1_000_000:.2f}s)")
            lb.selection_set(0, tk.END)  # mặc định chọn hết
            return lb

        self.story_anim_lb = _make_list(0, self._anim_items)
        self.story_trans_lb = _make_list(1, self._trans_items)

        # ── Select all / none ─────────────────────────────────────────
        sel_row = ctk.CTkFrame(frame, fg_color="transparent")
        sel_row.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        for text, cmd in [
            ("Anim: All", lambda: self.story_anim_lb.selection_set(0, tk.END)),
            ("Anim: None", lambda: self.story_anim_lb.selection_clear(0, tk.END)),
            ("Trans: All", lambda: self.story_trans_lb.selection_set(0, tk.END)),
            ("Trans: None", lambda: self.story_trans_lb.selection_clear(0, tk.END)),
        ]:
            ctk.CTkButton(sel_row, text=text, height=24, corner_radius=6,
                          fg_color=C["primary_light"], hover_color=C["primary_muted"],
                          text_color=C["primary"], font=("Segoe UI", 10),
                          command=cmd).pack(side="left", padx=2, expand=True, fill="x")

        # ── Intervals ─────────────────────────────────────────────────
        iv = ctk.CTkFrame(frame, fg_color=C["primary_light"], corner_radius=8)
        iv.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        iv_in = ctk.CTkFrame(iv, fg_color="transparent")
        iv_in.pack(fill="x", padx=12, pady=8)
        ctk.CTkLabel(iv_in, text="Animation cách:", font=FONT["small"],
                      text_color=C["text"]).pack(side="left")
        self.story_anim_iv = tk.StringVar(value="1")
        ctk.CTkEntry(iv_in, textvariable=self.story_anim_iv, width=42, height=26,
                      fg_color=C["card"], border_color=C["input_border"],
                      text_color=C["text"], corner_radius=6).pack(side="left", padx=(4, 16))
        ctk.CTkLabel(iv_in, text="Transition cách:", font=FONT["small"],
                      text_color=C["text"]).pack(side="left")
        self.story_trans_iv = tk.StringVar(value="1")
        ctk.CTkEntry(iv_in, textvariable=self.story_trans_iv, width=42, height=26,
                      fg_color=C["card"], border_color=C["input_border"],
                      text_color=C["text"], corner_radius=6).pack(side="left", padx=(4, 0))
        ctk.CTkLabel(iv_in, text="(1 = mọi cái)", font=("Segoe UI", 10),
                      text_color=C["text_light"]).pack(side="left", padx=(8, 0))

        # ── Info ──────────────────────────────────────────────────────
        self.story_info = ctk.CTkLabel(
            frame, text="Chọn project bên phải rồi bấm Áp dụng",
            font=FONT["small"], text_color=C["text_light"],
            fg_color=C["primary_light"], corner_radius=8, height=30
        )
        self.story_info.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        # ── Buttons ───────────────────────────────────────────────────
        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        self.story_btn = ctk.CTkButton(
            btn_row, text="Áp dụng", height=40, corner_radius=10,
            fg_color=C["primary"], hover_color=C["primary_hover"],
            font=FONT["button"], text_color=C["text_white"],
            command=self._on_story_click
        )
        self.story_btn.pack(side="left", expand=True, fill="x", padx=(0, 3))
        self.story_clear_btn = ctk.CTkButton(
            btn_row, text="Xóa hiệu ứng", height=40, width=110, corner_radius=10,
            fg_color=C["red_light"], hover_color=C["red"],
            text_color=C["red"], font=FONT["small_bold"],
            command=self._on_story_clear
        )
        self.story_clear_btn.pack(side="left")

    def _set_story_info(self, text: str, bg: str, fg: str):
        self.story_info.configure(text=text, fg_color=bg, text_color=fg)

    def _get_story_iv(self, var) -> int:
        try:
            return max(1, int(var.get().strip() or 1))
        except ValueError:
            return 1

    def _on_story_click(self):
        selected = self.app.project_list.get_selected()
        if not selected:
            self._set_story_info("Chưa chọn project nào!", C["red_light"], C["red"])
            return

        anim_rids = [self._anim_items[i][1] for i in self.story_anim_lb.curselection()]
        trans_eids = [self._trans_items[i][1] for i in self.story_trans_lb.curselection()]
        if not anim_rids and not trans_eids:
            self._set_story_info("Chọn ít nhất 1 animation hoặc transition!",
                                 C["red_light"], C["red"])
            return

        confirm = messagebox.askokcancel(
            "Cảnh báo",
            "Vui lòng thoát khỏi dự án trong CapCut trước khi áp hiệu ứng!\n\n"
            "Bấm OK nếu đã thoát CapCut."
        )
        if not confirm:
            return

        anim_iv = self._get_story_iv(self.story_anim_iv)
        trans_iv = self._get_story_iv(self.story_trans_iv)

        self.story_btn.configure(state="disabled", text="Đang xử lý...")
        self._set_story_info(
            f"Đang áp hiệu ứng cho {len(selected)} project...",
            C["primary_light"], C["primary"]
        )
        threading.Thread(
            target=self._run_story,
            args=(selected, anim_rids, trans_eids, anim_iv, trans_iv), daemon=True
        ).start()

    def _run_story(self, selected, anim_rids, trans_eids, anim_iv, trans_iv):
        root = self.app.root
        total_ok = 0
        total_fail = 0

        for idx, draft in selected:
            name = draft.get("draft_name", "?")
            path = draft.get("draft_fold_path", "")

            if not path or not os.path.isdir(path):
                root.after(0, self.app.project_list.set_status, idx, "Error", C["red"])
                total_fail += 1
                continue

            root.after(0, self.app.project_list.set_status, idx, "...", C["primary"])

            try:
                result = ani_trans_story_engine.apply_ani_trans_story(
                    path, anim_rids=anim_rids, trans_eids=trans_eids,
                    anim_interval=anim_iv, trans_interval=trans_iv
                )
            except Exception as e:
                result = ani_trans_story_engine.StoryResult(False, str(e))

            if result.success:
                root.after(0, self.app.project_list.set_status, idx, "Done", C["green"])
                total_ok += 1
            else:
                root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])
                total_fail += 1

        summary = f"Hoàn tất: {total_ok} OK, {total_fail} lỗi"
        color = C["green"] if total_fail == 0 else C["red"]
        light = C["green_light"] if total_fail == 0 else C["red_light"]
        root.after(0, lambda: self._set_story_info(summary, light, color))
        root.after(0, lambda: self.story_btn.configure(state="normal", text="Áp dụng"))
        root.after(0, lambda: self.app.status_var.set(f"  {summary}"))

    def _on_story_clear(self):
        selected = self.app.project_list.get_selected()
        if not selected:
            self._set_story_info("Chưa chọn project nào!", C["red_light"], C["red"])
            return
        if not messagebox.askokcancel(
            "Xóa hiệu ứng",
            f"Xóa tất cả animation + transition khỏi {len(selected)} project?\n"
            "Thoát CapCut trước. Bấm OK nếu đã thoát."
        ):
            return
        self.story_clear_btn.configure(state="disabled")
        threading.Thread(target=self._run_story_clear, args=(selected,), daemon=True).start()

    def _run_story_clear(self, selected):
        from core import animation_engine as ae, transition_engine as te
        root = self.app.root
        ok = 0
        for idx, draft in selected:
            path = draft.get("draft_fold_path", "")
            if not path or not os.path.isdir(path):
                root.after(0, self.app.project_list.set_status, idx, "Error", C["red"])
                continue
            try:
                ae.clear_animations(path, backup=True)
                te.clear_transitions(path, backup=True)
                root.after(0, self.app.project_list.set_status, idx, "Cleared", C["green"])
                ok += 1
            except Exception:
                root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])
        s = f"Đã xóa hiệu ứng: {ok}/{len(selected)} OK"
        root.after(0, lambda: self._set_story_info(s, C["green_light"], C["green"]))
        root.after(0, lambda: self.story_clear_btn.configure(state="normal"))
        root.after(0, lambda: self.app.status_var.set(f"  {s}"))

    # ══════════════════════════════════════════════════════════════════
    # SUB-TAB: Key Frame Nâng Cao
    # ══════════════════════════════════════════════════════════════════
    def _build_kfadv(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(expand=True, fill="both", padx=12, pady=6)

        ctk.CTkLabel(
            frame, text="Keyframe bắt đầu sau max(animation, transition) + 0.25s "
                        "→ ảnh đứng yên khi hiệu ứng vào chạy, rồi mới zoom/pan.",
            font=("Segoe UI", 10), text_color=C["text_light"],
            justify="left", wraplength=540
        ).pack(anchor="w", pady=(0, 6))

        # Settings row
        s_row = ctk.CTkFrame(frame, fg_color=C["primary_light"], corner_radius=8)
        s_row.pack(fill="x", pady=(0, 6))
        inner = ctk.CTkFrame(s_row, fg_color="transparent")
        inner.pack(fill="x", padx=10, pady=6)
        ctk.CTkLabel(inner, text="Khoảng cách:", font=FONT["small"],
                      text_color=C["text"]).pack(side="left")
        self.kfa_interval = tk.StringVar(value="")
        ctk.CTkEntry(inner, textvariable=self.kfa_interval, width=45, height=28,
                      fg_color=C["card"], border_color=C["input_border"],
                      text_color=C["text"], corner_radius=6,
                      placeholder_text="All").pack(side="left", padx=(4, 10))
        self.kfa_full = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(inner, text="Full Duration", variable=self.kfa_full,
                          font=FONT["small"], text_color=C["text"],
                          checkbox_width=18, checkbox_height=18,
                          fg_color=C["primary"], hover_color=C["primary_hover"],
                          command=self._kfa_full_toggle).pack(side="left")
        ctk.CTkLabel(inner, text="Time(s):", font=FONT["small"],
                      text_color=C["text"]).pack(side="left", padx=(6, 2))
        self.kfa_time = tk.StringVar(value="0.0")
        self.kfa_time_entry = ctk.CTkEntry(
            inner, textvariable=self.kfa_time, width=50, height=28,
            fg_color=C["card"], border_color=C["input_border"],
            text_color=C["text"], corner_radius=6, state="disabled")
        self.kfa_time_entry.pack(side="left")
        self.kfa_onlypic = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(inner, text="Only Picture", variable=self.kfa_onlypic,
                          font=FONT["small"], text_color=C["text"],
                          checkbox_width=18, checkbox_height=18,
                          fg_color=C["primary"], hover_color=C["primary_hover"]
                          ).pack(side="left", padx=(12, 0))

        # Zoom box
        zoom_box = ctk.CTkFrame(frame, fg_color=C["card"], corner_radius=8,
                                 border_width=1, border_color=C["border"])
        zoom_box.pack(fill="x", pady=(0, 4))

        def _num(parent_row, label, default, w=50):
            ctk.CTkLabel(parent_row, text=label, font=FONT["small"],
                          text_color=C["text_light"]).pack(side="left", padx=(4, 2))
            v = tk.StringVar(value=default)
            ctk.CTkEntry(parent_row, textvariable=v, width=w, height=26,
                          fg_color=C["input_bg"], border_color=C["input_border"],
                          text_color=C["text"], corner_radius=6).pack(side="left")
            return v

        row_zi = ctk.CTkFrame(zoom_box, fg_color="transparent")
        row_zi.pack(fill="x", padx=10, pady=(6, 2))
        self.kfa_zi = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(row_zi, text="Zoom In", variable=self.kfa_zi, width=100,
                          font=FONT["small"], text_color=C["text"],
                          checkbox_width=18, checkbox_height=18,
                          fg_color=C["primary"], hover_color=C["primary_hover"]).pack(side="left")
        self.kfa_zi_s = _num(row_zi, "Start%:", "100")
        self.kfa_zi_e = _num(row_zi, "End%:", "130")

        row_zo = ctk.CTkFrame(zoom_box, fg_color="transparent")
        row_zo.pack(fill="x", padx=10, pady=(2, 6))
        self.kfa_zo = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(row_zo, text="Zoom Out", variable=self.kfa_zo, width=100,
                          font=FONT["small"], text_color=C["text"],
                          checkbox_width=18, checkbox_height=18,
                          fg_color=C["primary"], hover_color=C["primary_hover"]).pack(side="left")
        self.kfa_zo_s = _num(row_zo, "Start%:", "130")
        self.kfa_zo_e = _num(row_zo, "End%:", "100")

        # Move box
        move_box = ctk.CTkFrame(frame, fg_color=C["card"], corner_radius=8,
                                 border_width=1, border_color=C["border"])
        move_box.pack(fill="x", pady=(0, 4))

        row_mx = ctk.CTkFrame(move_box, fg_color="transparent")
        row_mx.pack(fill="x", padx=10, pady=(6, 2))
        self.kfa_mx = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(row_mx, text="Zoom+MoveX", variable=self.kfa_mx, width=130,
                          font=FONT["small"], text_color=C["text"],
                          checkbox_width=18, checkbox_height=18,
                          fg_color=C["primary"], hover_color=C["primary_hover"]).pack(side="left")
        self.kfa_mx_s = _num(row_mx, "Scale%:", "150", 45)
        self.kfa_mx_1 = _num(row_mx, "X1:", "0", 40)
        self.kfa_mx_2 = _num(row_mx, "X2:", "0", 40)

        row_my = ctk.CTkFrame(move_box, fg_color="transparent")
        row_my.pack(fill="x", padx=10, pady=(2, 6))
        self.kfa_my = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(row_my, text="Zoom+MoveY", variable=self.kfa_my, width=130,
                          font=FONT["small"], text_color=C["text"],
                          checkbox_width=18, checkbox_height=18,
                          fg_color=C["primary"], hover_color=C["primary_hover"]).pack(side="left")
        self.kfa_my_s = _num(row_my, "Scale%:", "150", 45)
        self.kfa_my_1 = _num(row_my, "Y1:", "0", 40)
        self.kfa_my_2 = _num(row_my, "Y2:", "0", 40)

        # Buttons
        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.pack(fill="x", pady=(4, 0))
        self.kfa_clear_btn = ctk.CTkButton(
            btn_row, text="Xóa tất cả KeyFrames", height=38, corner_radius=8,
            fg_color=C["red_light"], hover_color=C["red"],
            text_color=C["red"], font=FONT["small_bold"], command=self._on_kfa_clear)
        self.kfa_clear_btn.pack(side="left", expand=True, fill="x", padx=(0, 4))
        self.kfa_apply_btn = ctk.CTkButton(
            btn_row, text="Thêm KeyFrames nâng cao", height=38, corner_radius=8,
            fg_color=C["primary"], hover_color=C["primary_hover"],
            text_color=C["text_white"], font=FONT["small_bold"], command=self._on_kfa_apply)
        self.kfa_apply_btn.pack(side="left", expand=True, fill="x", padx=(4, 0))

    def _kfa_full_toggle(self):
        self.kfa_time_entry.configure(state="disabled" if self.kfa_full.get() else "normal")

    def _kfa_interval(self) -> int:
        try:
            return max(0, int(self.kfa_interval.get().strip() or 0))
        except ValueError:
            return 0

    def _kfa_build_config(self):
        options = []
        if self.kfa_zi.get():
            options.append(kfe.KeyFrameOption(
                name="Zoom In", scale_start=float(self.kfa_zi_s.get() or 100) / 100,
                scale_end=float(self.kfa_zi_e.get() or 130) / 100))
        if self.kfa_zo.get():
            options.append(kfe.KeyFrameOption(
                name="Zoom Out", scale_start=float(self.kfa_zo_s.get() or 130) / 100,
                scale_end=float(self.kfa_zo_e.get() or 100) / 100))
        if self.kfa_mx.get():
            options.append(kfe.KeyFrameOption(
                name="Zoom+MoveX", scale_start=1.0,
                scale_end=float(self.kfa_mx_s.get() or 150) / 100, has_move_x=True,
                move_x_start=float(self.kfa_mx_1.get() or 0),
                move_x_end=float(self.kfa_mx_2.get() or 0)))
        if self.kfa_my.get():
            options.append(kfe.KeyFrameOption(
                name="Zoom+MoveY", scale_start=1.0,
                scale_end=float(self.kfa_my_s.get() or 150) / 100, has_move_y=True,
                move_y_start=float(self.kfa_my_1.get() or 0),
                move_y_end=float(self.kfa_my_2.get() or 0)))
        if not options:
            return None
        return kfe.KeyFrameConfig(
            options=options, full_duration=self.kfa_full.get(),
            time_seconds=float(self.kfa_time.get() or 0),
            interval=self._kfa_interval(), only_picture=self.kfa_onlypic.get())

    def _on_kfa_apply(self):
        selected = self.app.project_list.get_selected()
        if not selected:
            messagebox.showwarning("Chưa chọn project", "Vui lòng chọn project bên phải.")
            return
        try:
            config = self._kfa_build_config()
        except ValueError:
            messagebox.showerror("Lỗi", "Giá trị nhập không hợp lệ.")
            return
        if config is None:
            messagebox.showwarning("Chưa chọn loại", "Tick ít nhất 1 loại keyframe.")
            return
        if not messagebox.askokcancel(
                "Cảnh báo", "Vui lòng thoát khỏi dự án trong CapCut trước!\nBấm OK nếu đã thoát."):
            return
        self.kfa_apply_btn.configure(state="disabled", text="Đang xử lý...")
        threading.Thread(target=self._run_kfa_apply, args=(selected, config), daemon=True).start()

    def _run_kfa_apply(self, selected, config):
        root = self.app.root
        ok = 0
        for idx, draft in selected:
            path = draft.get("draft_fold_path", "")
            if not path or not os.path.isdir(path):
                root.after(0, self.app.project_list.set_status, idx, "Error", C["red"])
                continue
            root.after(0, self.app.project_list.set_status, idx, "...", C["primary"])
            try:
                r = kfae.apply_keyframes_advanced(path, config, backup=True)
            except Exception as e:
                r = kfae.KeyFrameResult(False, str(e))
            if r.success:
                root.after(0, self.app.project_list.set_status, idx, "Done", C["green"])
                ok += 1
            else:
                root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])
        s = f"KeyFrames nâng cao: {ok}/{len(selected)} OK"
        root.after(0, lambda: self.kfa_apply_btn.configure(state="normal", text="Thêm KeyFrames nâng cao"))
        root.after(0, lambda: self.app.status_var.set(f"  {s}"))

    def _on_kfa_clear(self):
        selected = self.app.project_list.get_selected()
        if not selected:
            messagebox.showwarning("Chưa chọn project", "Vui lòng chọn project bên phải.")
            return
        if not messagebox.askokcancel(
                "Xóa KeyFrames",
                f"Xóa tất cả keyframes khỏi {len(selected)} project?\nThoát CapCut trước. Bấm OK."):
            return
        self.kfa_clear_btn.configure(state="disabled", text="Đang xóa...")
        threading.Thread(target=self._run_kfa_clear, args=(selected,), daemon=True).start()

    def _run_kfa_clear(self, selected):
        root = self.app.root
        ok = 0
        for idx, draft in selected:
            path = draft.get("draft_fold_path", "")
            if not path or not os.path.isdir(path):
                root.after(0, self.app.project_list.set_status, idx, "Error", C["red"])
                continue
            try:
                r = kfe.clear_keyframes(path, backup=True)
            except Exception as e:
                r = kfe.KeyFrameResult(False, str(e))
            if r.success:
                root.after(0, self.app.project_list.set_status, idx, "Cleared", C["green"])
                ok += 1
            else:
                root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])
        s = f"Cleared: {ok}/{len(selected)} OK"
        root.after(0, lambda: self.kfa_clear_btn.configure(state="normal", text="Xóa tất cả KeyFrames"))
        root.after(0, lambda: self.app.status_var.set(f"  {s}"))
