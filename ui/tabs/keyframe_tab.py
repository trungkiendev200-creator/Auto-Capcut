"""Tab KeyFrames."""

import os
import threading
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox

from ui.theme import COLORS as C, FONT
from core import keyframe_engine as kfe


class KeyFrameTab:
    def __init__(self, parent: ctk.CTkFrame, app):
        self.app = app
        self._build(parent)

    def _build(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(expand=True, fill="both", padx=12, pady=6)

        # ── Row 1: Settings ───────────────────────────────────────────
        s_row = ctk.CTkFrame(frame, fg_color=C["primary_light"], corner_radius=8)
        s_row.pack(fill="x", pady=(0, 6))

        inner = ctk.CTkFrame(s_row, fg_color="transparent")
        inner.pack(fill="x", padx=10, pady=6)

        ctk.CTkLabel(inner, text="Khoảng cách:", font=FONT["small"],
                      text_color=C["text"]).pack(side="left")
        self.interval_var = tk.StringVar(value="")
        ctk.CTkEntry(inner, textvariable=self.interval_var, width=45, height=28,
                      fg_color=C["card"], border_color=C["input_border"],
                      text_color=C["text"], corner_radius=6,
                      placeholder_text="All").pack(side="left", padx=(4, 10))

        self.full_dur_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            inner, text="Full Duration", variable=self.full_dur_var,
            font=FONT["small"], text_color=C["text"],
            checkbox_width=18, checkbox_height=18,
            fg_color=C["primary"], hover_color=C["primary_hover"],
            command=self._on_full_dur_toggle,
        ).pack(side="left")

        ctk.CTkLabel(inner, text="Time(s):", font=FONT["small"],
                      text_color=C["text"]).pack(side="left", padx=(6, 2))
        self.time_var = tk.StringVar(value="0.0")
        self.time_entry = ctk.CTkEntry(
            inner, textvariable=self.time_var, width=50, height=28,
            fg_color=C["card"], border_color=C["input_border"],
            text_color=C["text"], corner_radius=6, state="disabled"
        )
        self.time_entry.pack(side="left")

        self.only_pic_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            inner, text="Only Picture", variable=self.only_pic_var,
            font=FONT["small"], text_color=C["text"],
            checkbox_width=18, checkbox_height=18,
            fg_color=C["primary"], hover_color=C["primary_hover"],
        ).pack(side="left", padx=(12, 0))

        # ── Row 2: Zoom In / Out ──────────────────────────────────────
        zoom_box = ctk.CTkFrame(frame, fg_color=C["card"], corner_radius=8,
                                 border_width=1, border_color=C["border"])
        zoom_box.pack(fill="x", pady=(0, 4))

        # Zoom In
        row_zi = ctk.CTkFrame(zoom_box, fg_color="transparent")
        row_zi.pack(fill="x", padx=10, pady=(6, 2))
        self.zoom_in_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(row_zi, text="Zoom In", variable=self.zoom_in_var,
                          width=100, font=FONT["small"], text_color=C["text"],
                          checkbox_width=18, checkbox_height=18,
                          fg_color=C["primary"], hover_color=C["primary_hover"]
                          ).pack(side="left")
        ctk.CTkLabel(row_zi, text="Start%:", font=FONT["small"],
                      text_color=C["text_light"]).pack(side="left", padx=(4, 2))
        self.zi_start = tk.StringVar(value="100")
        ctk.CTkEntry(row_zi, textvariable=self.zi_start, width=50, height=26,
                      fg_color=C["input_bg"], border_color=C["input_border"],
                      text_color=C["text"], corner_radius=6).pack(side="left")
        ctk.CTkLabel(row_zi, text="End%:", font=FONT["small"],
                      text_color=C["text_light"]).pack(side="left", padx=(10, 2))
        self.zi_end = tk.StringVar(value="130")
        ctk.CTkEntry(row_zi, textvariable=self.zi_end, width=50, height=26,
                      fg_color=C["input_bg"], border_color=C["input_border"],
                      text_color=C["text"], corner_radius=6).pack(side="left")

        # Zoom Out
        row_zo = ctk.CTkFrame(zoom_box, fg_color="transparent")
        row_zo.pack(fill="x", padx=10, pady=(2, 6))
        self.zoom_out_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(row_zo, text="Zoom Out", variable=self.zoom_out_var,
                          width=100, font=FONT["small"], text_color=C["text"],
                          checkbox_width=18, checkbox_height=18,
                          fg_color=C["primary"], hover_color=C["primary_hover"]
                          ).pack(side="left")
        ctk.CTkLabel(row_zo, text="Start%:", font=FONT["small"],
                      text_color=C["text_light"]).pack(side="left", padx=(4, 2))
        self.zo_start = tk.StringVar(value="130")
        ctk.CTkEntry(row_zo, textvariable=self.zo_start, width=50, height=26,
                      fg_color=C["input_bg"], border_color=C["input_border"],
                      text_color=C["text"], corner_radius=6).pack(side="left")
        ctk.CTkLabel(row_zo, text="End%:", font=FONT["small"],
                      text_color=C["text_light"]).pack(side="left", padx=(10, 2))
        self.zo_end = tk.StringVar(value="100")
        ctk.CTkEntry(row_zo, textvariable=self.zo_end, width=50, height=26,
                      fg_color=C["input_bg"], border_color=C["input_border"],
                      text_color=C["text"], corner_radius=6).pack(side="left")

        # ── Row 3: Zoom + Move ────────────────────────────────────────
        move_box = ctk.CTkFrame(frame, fg_color=C["card"], corner_radius=8,
                                 border_width=1, border_color=C["border"])
        move_box.pack(fill="x", pady=(0, 4))

        # Move X
        row_mx = ctk.CTkFrame(move_box, fg_color="transparent")
        row_mx.pack(fill="x", padx=10, pady=(6, 2))
        self.move_x_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(row_mx, text="Zoom+MoveX", variable=self.move_x_var,
                          width=130, font=FONT["small"], text_color=C["text"],
                          checkbox_width=18, checkbox_height=18,
                          fg_color=C["primary"], hover_color=C["primary_hover"]
                          ).pack(side="left")
        ctk.CTkLabel(row_mx, text="Scale%:", font=FONT["small"],
                      text_color=C["text_light"]).pack(side="left", padx=(2, 2))
        self.mx_scale = tk.StringVar(value="150")
        ctk.CTkEntry(row_mx, textvariable=self.mx_scale, width=45, height=26,
                      fg_color=C["input_bg"], border_color=C["input_border"],
                      text_color=C["text"], corner_radius=6).pack(side="left")
        ctk.CTkLabel(row_mx, text="X1:", font=FONT["small"],
                      text_color=C["text_light"]).pack(side="left", padx=(8, 2))
        self.mx_x1 = tk.StringVar(value="0")
        ctk.CTkEntry(row_mx, textvariable=self.mx_x1, width=40, height=26,
                      fg_color=C["input_bg"], border_color=C["input_border"],
                      text_color=C["text"], corner_radius=6).pack(side="left")
        ctk.CTkLabel(row_mx, text="X2:", font=FONT["small"],
                      text_color=C["text_light"]).pack(side="left", padx=(6, 2))
        self.mx_x2 = tk.StringVar(value="0")
        ctk.CTkEntry(row_mx, textvariable=self.mx_x2, width=40, height=26,
                      fg_color=C["input_bg"], border_color=C["input_border"],
                      text_color=C["text"], corner_radius=6).pack(side="left")

        # Move Y
        row_my = ctk.CTkFrame(move_box, fg_color="transparent")
        row_my.pack(fill="x", padx=10, pady=(2, 6))
        self.move_y_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(row_my, text="Zoom+MoveY", variable=self.move_y_var,
                          width=130, font=FONT["small"], text_color=C["text"],
                          checkbox_width=18, checkbox_height=18,
                          fg_color=C["primary"], hover_color=C["primary_hover"]
                          ).pack(side="left")
        ctk.CTkLabel(row_my, text="Scale%:", font=FONT["small"],
                      text_color=C["text_light"]).pack(side="left", padx=(2, 2))
        self.my_scale = tk.StringVar(value="150")
        ctk.CTkEntry(row_my, textvariable=self.my_scale, width=45, height=26,
                      fg_color=C["input_bg"], border_color=C["input_border"],
                      text_color=C["text"], corner_radius=6).pack(side="left")
        ctk.CTkLabel(row_my, text="Y1:", font=FONT["small"],
                      text_color=C["text_light"]).pack(side="left", padx=(8, 2))
        self.my_y1 = tk.StringVar(value="0")
        ctk.CTkEntry(row_my, textvariable=self.my_y1, width=40, height=26,
                      fg_color=C["input_bg"], border_color=C["input_border"],
                      text_color=C["text"], corner_radius=6).pack(side="left")
        ctk.CTkLabel(row_my, text="Y2:", font=FONT["small"],
                      text_color=C["text_light"]).pack(side="left", padx=(6, 2))
        self.my_y2 = tk.StringVar(value="0")
        ctk.CTkEntry(row_my, textvariable=self.my_y2, width=40, height=26,
                      fg_color=C["input_bg"], border_color=C["input_border"],
                      text_color=C["text"], corner_radius=6).pack(side="left")

        # ── Buttons ───────────────────────────────────────────────────
        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.pack(fill="x", pady=(4, 0))

        self.clear_btn = ctk.CTkButton(
            btn_row, text="Xóa tất cả KeyFrames", height=38, corner_radius=8,
            fg_color=C["red_light"], hover_color=C["red"],
            text_color=C["red"], font=FONT["small_bold"],
            command=self._on_clear
        )
        self.clear_btn.pack(side="left", expand=True, fill="x", padx=(0, 4))

        self.apply_btn = ctk.CTkButton(
            btn_row, text="Thêm KeyFrames", height=38, corner_radius=8,
            fg_color=C["primary"], hover_color=C["primary_hover"],
            text_color=C["text_white"], font=FONT["small_bold"],
            command=self._on_apply
        )
        self.apply_btn.pack(side="left", expand=True, fill="x", padx=(4, 0))

    # ── Helpers ───────────────────────────────────────────────────────
    def _on_full_dur_toggle(self):
        if self.full_dur_var.get():
            self.time_entry.configure(state="disabled")
        else:
            self.time_entry.configure(state="normal")

    def _get_interval(self) -> int:
        val = self.interval_var.get().strip()
        if not val:
            return 0  # 0 = tất cả
        try:
            return max(0, int(val))
        except ValueError:
            return 0

    def _build_config(self) -> kfe.KeyFrameConfig | None:
        options = []

        if self.zoom_in_var.get():
            options.append(kfe.KeyFrameOption(
                name="Zoom In",
                scale_start=float(self.zi_start.get() or 100) / 100,
                scale_end=float(self.zi_end.get() or 130) / 100,
            ))

        if self.zoom_out_var.get():
            options.append(kfe.KeyFrameOption(
                name="Zoom Out",
                scale_start=float(self.zo_start.get() or 130) / 100,
                scale_end=float(self.zo_end.get() or 100) / 100,
            ))

        if self.move_x_var.get():
            options.append(kfe.KeyFrameOption(
                name="Zoom+MoveX",
                scale_start=1.0,  # Luôn bắt đầu từ 100%
                scale_end=float(self.mx_scale.get() or 150) / 100,
                has_move_x=True,
                move_x_start=float(self.mx_x1.get() or 0),
                move_x_end=float(self.mx_x2.get() or 0),
            ))

        if self.move_y_var.get():
            options.append(kfe.KeyFrameOption(
                name="Zoom+MoveY",
                scale_start=1.0,  # Luôn bắt đầu từ 100%
                scale_end=float(self.my_scale.get() or 150) / 100,
                has_move_y=True,
                move_y_start=float(self.my_y1.get() or 0),
                move_y_end=float(self.my_y2.get() or 0),
            ))

        if not options:
            return None

        return kfe.KeyFrameConfig(
            options=options,
            full_duration=self.full_dur_var.get(),
            time_seconds=float(self.time_var.get() or 0),
            interval=self._get_interval(),
            only_picture=self.only_pic_var.get(),
        )

    # ── Actions ───────────────────────────────────────────────────────
    def _on_apply(self):
        selected = self.app.project_list.get_selected()
        if not selected:
            messagebox.showwarning("Chưa chọn project", "Vui lòng chọn project bên phải.")
            return

        try:
            config = self._build_config()
        except ValueError:
            messagebox.showerror("Lỗi", "Giá trị nhập không hợp lệ.")
            return

        if config is None:
            messagebox.showwarning("Chưa chọn loại", "Tick ít nhất 1 loại keyframe.")
            return

        confirm = messagebox.askokcancel(
            "Cảnh báo",
            "Vui lòng thoát khỏi dự án trong CapCut trước!\nBấm OK nếu đã thoát."
        )
        if not confirm:
            return

        self.apply_btn.configure(state="disabled", text="Đang xử lý...")
        threading.Thread(
            target=self._run_apply, args=(selected, config), daemon=True
        ).start()

    def _run_apply(self, selected, config):
        root = self.app.root
        ok_count = 0

        for idx, draft in selected:
            path = draft.get("draft_fold_path", "")
            if not path or not os.path.isdir(path):
                root.after(0, self.app.project_list.set_status, idx, "Error", C["red"])
                continue

            root.after(0, self.app.project_list.set_status, idx, "...", C["primary"])
            try:
                result = kfe.apply_keyframes(path, config, backup=True)
            except Exception as e:
                result = kfe.KeyFrameResult(False, str(e))

            if result.success:
                root.after(0, self.app.project_list.set_status, idx, "Done", C["green"])
                ok_count += 1
            else:
                root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])

        summary = f"KeyFrames: {ok_count}/{len(selected)} OK"
        root.after(0, lambda: self.apply_btn.configure(state="normal", text="Thêm KeyFrames"))
        root.after(0, lambda: self.app.status_var.set(f"  {summary}"))

    def _on_clear(self):
        selected = self.app.project_list.get_selected()
        if not selected:
            messagebox.showwarning("Chưa chọn project", "Vui lòng chọn project bên phải.")
            return

        confirm = messagebox.askokcancel(
            "Xóa KeyFrames",
            f"Xóa tất cả keyframes khỏi {len(selected)} project?\nThoát CapCut trước. Bấm OK."
        )
        if not confirm:
            return

        self.clear_btn.configure(state="disabled", text="Đang xóa...")
        threading.Thread(target=self._run_clear, args=(selected,), daemon=True).start()

    def _run_clear(self, selected):
        root = self.app.root
        ok_count = 0

        for idx, draft in selected:
            path = draft.get("draft_fold_path", "")
            if not path or not os.path.isdir(path):
                root.after(0, self.app.project_list.set_status, idx, "Error", C["red"])
                continue

            try:
                result = kfe.clear_keyframes(path, backup=True)
            except Exception as e:
                result = kfe.KeyFrameResult(False, str(e))

            if result.success:
                root.after(0, self.app.project_list.set_status, idx, "Cleared", C["green"])
                ok_count += 1
            else:
                root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])

        summary = f"Cleared: {ok_count}/{len(selected)} OK"
        root.after(0, lambda: self.clear_btn.configure(
            state="normal", text="Xóa tất cả KeyFrames"))
        root.after(0, lambda: self.app.status_var.set(f"  {summary}"))
