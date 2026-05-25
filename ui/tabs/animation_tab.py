"""Tab Animation — optimized with native Listbox + persistent selection."""

import os
import threading
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox

from ui.theme import COLORS as C, FONT
from core import animation_engine as ae
from core import animation_library as alib


class AnimationTab:
    def __init__(self, parent: ctk.CTkFrame, app):
        self.app = app
        self.library: list[alib.AnimationInfo] = []
        self.filtered: list[alib.AnimationInfo] = []
        self.selected_rids: set[str] = set()  # Giữ selection xuyên suốt các tab
        self._build(parent)
        # Defer until mainloop running — bg thread's root.after() needs it
        self.app.root.after(100, lambda: threading.Thread(
            target=self._load_library_bg, daemon=True).start())

    def _build(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(expand=True, fill="both", padx=12, pady=6)
        frame.grid_columnconfigure(0, weight=3)
        frame.grid_columnconfigure(1, weight=2)
        frame.grid_rowconfigure(1, weight=1)

        # ── Left: Tab + List ──────────────────────────────────────────
        tab_row = ctk.CTkFrame(frame, fg_color="transparent")
        tab_row.grid(row=0, column=0, sticky="ew", pady=(0, 4))

        self.tab_var = tk.StringVar(value="In")
        for label in ["In", "Out", "Combo"]:
            ctk.CTkRadioButton(
                tab_row, text=label, variable=self.tab_var, value=label,
                font=FONT["small_bold"], text_color=C["text"],
                fg_color=C["primary"], hover_color=C["primary_hover"],
                command=self._on_tab_change,
            ).pack(side="left", padx=(0, 12))

        self.count_label = ctk.CTkLabel(
            tab_row, text="", font=FONT["small"], text_color=C["text_light"]
        )
        self.count_label.pack(side="right")

        list_container = ctk.CTkFrame(
            frame, fg_color=C["card"], corner_radius=8,
            border_width=1, border_color=C["border"]
        )
        list_container.grid(row=1, column=0, sticky="nsew", padx=(0, 8))

        inner = tk.Frame(list_container, bg="#ffffff")
        inner.pack(fill="both", expand=True, padx=4, pady=4)

        self.listbox = tk.Listbox(
            inner, selectmode=tk.MULTIPLE, font=("Segoe UI", 11),
            bg="#ffffff", fg=C["text"], selectbackground=C["primary_light"],
            selectforeground=C["primary"], activestyle="none",
            highlightthickness=0, borderwidth=0, relief="flat",
        )
        scrollbar = tk.Scrollbar(inner, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scrollbar.set)
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Bind click to track selection
        self.listbox.bind("<<ListboxSelect>>", self._on_listbox_select)

        # ── Right: Options ────────────────────────────────────────────
        right = ctk.CTkFrame(frame, fg_color="transparent")
        right.grid(row=0, column=1, rowspan=2, sticky="nsew")

        opt_box = ctk.CTkFrame(right, fg_color=C["primary_light"], corner_radius=8)
        opt_box.pack(fill="x", pady=(0, 6))

        r1 = ctk.CTkFrame(opt_box, fg_color="transparent")
        r1.pack(fill="x", padx=10, pady=(8, 4))
        ctk.CTkLabel(r1, text="Random cách nhau:", font=FONT["small"],
                      text_color=C["text"]).pack(side="left")
        self.interval_var = tk.StringVar(value="1")
        ctk.CTkEntry(r1, textvariable=self.interval_var, width=45, height=26,
                      fg_color=C["card"], border_color=C["input_border"],
                      text_color=C["text"], corner_radius=6).pack(side="left", padx=(6, 0))

        r2 = ctk.CTkFrame(opt_box, fg_color="transparent")
        r2.pack(fill="x", padx=10, pady=(0, 4))
        ctk.CTkLabel(r2, text="Thời gian:", font=FONT["small"],
                      text_color=C["text"]).pack(side="left")
        self.duration_var = tk.StringVar(value="0")
        ctk.CTkEntry(r2, textvariable=self.duration_var, width=50, height=26,
                      fg_color=C["card"], border_color=C["input_border"],
                      text_color=C["text"], corner_radius=6).pack(side="left", padx=(6, 4))
        ctk.CTkLabel(r2, text="(giây)", font=FONT["small"],
                      text_color=C["text_light"]).pack(side="left")

        r2b = ctk.CTkFrame(opt_box, fg_color="transparent")
        r2b.pack(fill="x", padx=10, pady=(0, 8))
        ctk.CTkLabel(r2b, text="0: default  |  9999: fulltime",
                      font=("Segoe UI", 10), text_color=C["text_light"]).pack(side="left")

        self.multi_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            opt_box, text="Chèn nhiều Animation\n1 Frame",
            variable=self.multi_var, font=FONT["small"],
            text_color=C["text"], checkbox_width=18, checkbox_height=18,
            fg_color=C["primary"], hover_color=C["primary_hover"],
        ).pack(padx=10, pady=(0, 10), anchor="w")

        # Buttons group
        btn_box = ctk.CTkFrame(right, fg_color=C["card"], corner_radius=8,
                                border_width=1, border_color=C["border"])
        btn_box.pack(fill="x", pady=(8, 0))

        self.apply_btn = ctk.CTkButton(
            btn_box, text="Thêm Animation", height=40, corner_radius=8,
            fg_color=C["primary"], hover_color=C["primary_hover"],
            text_color=C["text_white"], font=FONT["small_bold"],
            command=self._on_apply
        )
        self.apply_btn.pack(fill="x", padx=8, pady=(8, 4))

        btn_row2 = ctk.CTkFrame(btn_box, fg_color="transparent")
        btn_row2.pack(fill="x", padx=8, pady=(0, 8))

        self.clear_btn = ctk.CTkButton(
            btn_row2, text="Xóa tất cả", height=32, corner_radius=8,
            fg_color=C["red_light"], hover_color=C["red"],
            text_color=C["red"], font=FONT["small"],
            command=self._on_clear
        )
        self.clear_btn.pack(side="left", expand=True, fill="x", padx=(0, 3))

        self.refresh_btn = ctk.CTkButton(
            btn_row2, text="Refresh", height=32, corner_radius=8,
            fg_color=C["primary_light"], hover_color=C["primary_muted"],
            text_color=C["primary"], font=FONT["small"],
            command=self._on_refresh
        )
        self.refresh_btn.pack(side="left", expand=True, fill="x", padx=(3, 0))

    # ── Library ───────────────────────────────────────────────────────
    def _on_refresh(self):
        self.selected_rids.clear()
        self.listbox.selection_clear(0, tk.END)
        self._update_btn_text()
        threading.Thread(target=self._load_library_bg, daemon=True).start()

    def _load_library_bg(self):
        lib = alib.scan_library()
        self.app.root.after(0, self._set_library, lib)

    def _set_library(self, lib):
        self.library = lib
        self.app.status_var.set("  XS-Auto-Capcut")
        tab = self.tab_var.get()
        self.filtered = [a for a in self.library if a.category == tab]
        self._render_list()
        self._update_btn_text()

    def _on_tab_change(self):
        # Lưu selection hiện tại trước khi đổi tab
        self._save_selection()
        tab = self.tab_var.get()
        self.filtered = [a for a in self.library if a.category == tab]
        self._render_list()

    def _render_list(self):
        self.listbox.delete(0, tk.END)
        for idx, anim in enumerate(self.filtered):
            self.listbox.insert(tk.END, anim.name)
            if anim.resource_id in self.selected_rids:
                self.listbox.selection_set(idx)
        self.count_label.configure(text=f"{len(self.filtered)} effects")

    # ── Selection tracking ────────────────────────────────────────────
    def _on_listbox_select(self, event=None):
        """Cập nhật selected_rids khi user click listbox."""
        self._save_selection()
        self._update_btn_text()

    def _save_selection(self):
        """Lưu selection từ listbox vào selected_rids."""
        # Xóa rids của tab hiện tại khỏi set
        for anim in self.filtered:
            self.selected_rids.discard(anim.resource_id)
        # Thêm lại các rids đang được chọn
        for i in self.listbox.curselection():
            self.selected_rids.add(self.filtered[i].resource_id)

    def _update_btn_text(self):
        """Cập nhật text nút: 'Thêm Animation' hoặc 'Thêm Animation (N)'."""
        count = len(self.selected_rids)
        if count > 0:
            self.apply_btn.configure(text=f"Thêm Animation ({count})")
        else:
            self.apply_btn.configure(text="Thêm Animation")

    def _get_all_selected_anims(self) -> list[alib.AnimationInfo]:
        """Lấy tất cả animations đã chọn xuyên suốt In/Out/Combo."""
        self._save_selection()
        return [a for a in self.library if a.resource_id in self.selected_rids]

    # ── Actions ───────────────────────────────────────────────────────
    def _get_interval(self) -> int:
        val = self.interval_var.get().strip()
        if not val:
            return 0
        try:
            return max(0, int(val))
        except ValueError:
            return 0

    def _get_duration(self) -> float:
        try:
            return float(self.duration_var.get() or 0)
        except ValueError:
            return 0

    def _on_apply(self):
        selected_projects = self.app.project_list.get_selected()
        if not selected_projects:
            messagebox.showwarning("Chưa chọn project", "Vui lòng chọn project bên phải.")
            return

        selected_anims = self._get_all_selected_anims()
        if not selected_anims:
            messagebox.showwarning("Chưa chọn animation", "Vui lòng chọn ít nhất 1 animation.")
            return

        confirm = messagebox.askokcancel(
            "Cảnh báo",
            "Vui lòng thoát khỏi dự án trong CapCut trước!\nBấm OK nếu đã thoát."
        )
        if not confirm:
            return

        # Determine anim_type based on what's selected
        types = set(a.category.lower() for a in selected_anims)
        if len(types) == 1:
            anim_type = types.pop()
        else:
            anim_type = "in"  # Mixed selection — engine handles per-animation

        config = ae.AnimationConfig(
            animations=selected_anims,
            anim_type=anim_type,
            duration_seconds=self._get_duration(),
            interval=self._get_interval(),
            multi_per_frame=self.multi_var.get(),
        )

        self.apply_btn.configure(state="disabled", text="Đang xử lý...")
        threading.Thread(
            target=self._run_apply, args=(selected_projects, config), daemon=True
        ).start()

    def _run_apply(self, selected, config):
        root = self.app.root
        ok = 0
        for idx, draft in selected:
            path = draft.get("draft_fold_path", "")
            if not path or not os.path.isdir(path):
                root.after(0, self.app.project_list.set_status, idx, "Error", C["red"])
                continue
            root.after(0, self.app.project_list.set_status, idx, "...", C["primary"])
            try:
                r = ae.apply_animations(path, config, backup=True)
            except Exception as e:
                r = ae.AnimationResult(False, str(e))
            if r.success:
                root.after(0, self.app.project_list.set_status, idx, "Done", C["green"])
                ok += 1
            else:
                root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])

        count = len(self.selected_rids)
        s = f"Animation: {ok}/{len(selected)} OK"
        btn_text = f"Thêm Animation ({count})" if count > 0 else "Thêm Animation"
        root.after(0, lambda: self.apply_btn.configure(state="normal", text=btn_text))
        root.after(0, lambda: self.app.status_var.set(f"  {s}"))

    def _on_clear(self):
        selected = self.app.project_list.get_selected()
        if not selected:
            messagebox.showwarning("Chưa chọn project", "Vui lòng chọn project bên phải.")
            return
        confirm = messagebox.askokcancel(
            "Xóa Animation",
            f"Xóa tất cả animation khỏi {len(selected)} project?\nThoát CapCut trước."
        )
        if not confirm:
            return

        self.clear_btn.configure(state="disabled", text="Đang xóa...")
        threading.Thread(target=self._run_clear, args=(selected,), daemon=True).start()

    def _run_clear(self, selected):
        root = self.app.root
        ok = 0
        for idx, draft in selected:
            path = draft.get("draft_fold_path", "")
            if not path or not os.path.isdir(path):
                root.after(0, self.app.project_list.set_status, idx, "Error", C["red"])
                continue
            try:
                r = ae.clear_animations(path, backup=True)
            except Exception as e:
                r = ae.AnimationResult(False, str(e))
            if r.success:
                root.after(0, self.app.project_list.set_status, idx, "Cleared", C["green"])
                ok += 1
            else:
                root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])

        s = f"Cleared: {ok}/{len(selected)} OK"
        root.after(0, lambda: self.clear_btn.configure(
            state="normal", text="Xóa tất cả Animation"))
        root.after(0, lambda: self.app.status_var.set(f"  {s}"))
