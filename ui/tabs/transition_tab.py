"""Tab Transitions."""

import os
import threading
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox

from ui.theme import COLORS as C, FONT
from core import transition_engine as te
from core import transition_library as tlib


class TransitionTab:
    def __init__(self, parent: ctk.CTkFrame, app):
        self.app = app
        self.library: list[tlib.TransitionInfo] = []
        self.filtered: list[tlib.TransitionInfo] = []
        self.selected: list[tlib.TransitionInfo] = []  # List dưới (đã chọn)
        self._build(parent)
        threading.Thread(target=self._load_library_bg, daemon=True).start()

    def _build(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(expand=True, fill="both", padx=12, pady=6)
        frame.grid_columnconfigure(0, weight=3)
        frame.grid_columnconfigure(1, weight=2)
        frame.grid_rowconfigure(1, weight=1)
        frame.grid_rowconfigure(3, weight=1)

        # ── Search ────────────────────────────────────────────────────
        search_row = ctk.CTkFrame(frame, fg_color="transparent")
        search_row.grid(row=0, column=0, sticky="ew", pady=(0, 4), padx=(0, 8))

        ctk.CTkLabel(search_row, text="Search:", font=FONT["small"],
                      text_color=C["text"]).pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._on_search())
        ctk.CTkEntry(search_row, textvariable=self.search_var, height=28,
                      fg_color=C["card"], border_color=C["input_border"],
                      text_color=C["text"], corner_radius=6,
                      placeholder_text="Tìm transition...").pack(
            side="left", fill="x", expand=True, padx=(6, 0))

        # ── All transitions list (top) ────────────────────────────────
        list_top = ctk.CTkFrame(frame, fg_color=C["card"], corner_radius=8,
                                 border_width=1, border_color=C["border"])
        list_top.grid(row=1, column=0, sticky="nsew", padx=(0, 8))

        inner_top = tk.Frame(list_top, bg="#ffffff")
        inner_top.pack(fill="both", expand=True, padx=4, pady=4)

        self.listbox_all = tk.Listbox(
            inner_top, selectmode=tk.EXTENDED, font=("Segoe UI", 11),
            bg="#ffffff", fg=C["text"], selectbackground=C["primary_light"],
            selectforeground=C["primary"], activestyle="none",
            highlightthickness=0, borderwidth=0,
        )
        sb_top = tk.Scrollbar(inner_top, orient="vertical", command=self.listbox_all.yview)
        self.listbox_all.configure(yscrollcommand=sb_top.set)
        self.listbox_all.pack(side="left", fill="both", expand=True)
        sb_top.pack(side="right", fill="y")

        # ── Add/Remove buttons ────────────────────────────────────────
        btn_mid = ctk.CTkFrame(frame, fg_color="transparent")
        btn_mid.grid(row=2, column=0, sticky="ew", padx=(0, 8), pady=4)

        ctk.CTkButton(
            btn_mid, text="[+] Thêm", width=90, height=28, corner_radius=6,
            fg_color=C["primary"], hover_color=C["primary_hover"],
            text_color=C["text_white"], font=FONT["small"],
            command=self._add_selected
        ).pack(side="left", padx=(0, 4))

        ctk.CTkButton(
            btn_mid, text="[-] Xóa", width=90, height=28, corner_radius=6,
            fg_color=C["red_light"], hover_color=C["red"],
            text_color=C["red"], font=FONT["small"],
            command=self._remove_selected
        ).pack(side="left")

        self.selected_count = ctk.CTkLabel(
            btn_mid, text="", font=FONT["small"], text_color=C["text_light"]
        )
        self.selected_count.pack(side="right")

        # ── Selected transitions list (bottom) ────────────────────────
        list_bot = ctk.CTkFrame(frame, fg_color=C["card"], corner_radius=8,
                                 border_width=1, border_color=C["border"])
        list_bot.grid(row=3, column=0, sticky="nsew", padx=(0, 8))

        inner_bot = tk.Frame(list_bot, bg="#ffffff")
        inner_bot.pack(fill="both", expand=True, padx=4, pady=4)

        self.listbox_sel = tk.Listbox(
            inner_bot, selectmode=tk.EXTENDED, font=("Segoe UI", 11),
            bg="#ffffff", fg=C["primary"], selectbackground=C["red_light"],
            selectforeground=C["red"], activestyle="none",
            highlightthickness=0, borderwidth=0,
        )
        sb_bot = tk.Scrollbar(inner_bot, orient="vertical", command=self.listbox_sel.yview)
        self.listbox_sel.configure(yscrollcommand=sb_bot.set)
        self.listbox_sel.pack(side="left", fill="both", expand=True)
        sb_bot.pack(side="right", fill="y")

        # ── Right: Options + Buttons ──────────────────────────────────
        right = ctk.CTkFrame(frame, fg_color="transparent")
        right.grid(row=0, column=1, rowspan=4, sticky="nsew")

        # Duration
        opt_box = ctk.CTkFrame(right, fg_color=C["primary_light"], corner_radius=8)
        opt_box.pack(fill="x", pady=(0, 8))

        dur_row = ctk.CTkFrame(opt_box, fg_color="transparent")
        dur_row.pack(fill="x", padx=10, pady=8)
        ctk.CTkLabel(dur_row, text="Thời gian:", font=FONT["small"],
                      text_color=C["text"]).pack(side="left")
        self.duration_var = tk.StringVar(value="0.8")
        ctk.CTkEntry(dur_row, textvariable=self.duration_var, width=55, height=26,
                      fg_color=C["card"], border_color=C["input_border"],
                      text_color=C["text"], corner_radius=6).pack(side="left", padx=(6, 4))
        ctk.CTkLabel(dur_row, text="(giây)", font=FONT["small"],
                      text_color=C["text_light"]).pack(side="left")

        # Interval
        int_row = ctk.CTkFrame(opt_box, fg_color="transparent")
        int_row.pack(fill="x", padx=10, pady=(0, 8))
        ctk.CTkLabel(int_row, text="Khoảng cách:", font=FONT["small"],
                      text_color=C["text"]).pack(side="left")
        self.interval_var = tk.StringVar(value="")
        ctk.CTkEntry(int_row, textvariable=self.interval_var, width=45, height=26,
                      fg_color=C["card"], border_color=C["input_border"],
                      text_color=C["text"], corner_radius=6,
                      placeholder_text="All").pack(side="left", padx=(6, 0))

        # Action buttons
        btn_box = ctk.CTkFrame(right, fg_color=C["card"], corner_radius=8,
                                border_width=1, border_color=C["border"])
        btn_box.pack(fill="x")

        self.apply_btn = ctk.CTkButton(
            btn_box, text="Thêm Transitions", height=40, corner_radius=8,
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

        ctk.CTkButton(
            btn_row2, text="Refresh", height=32, corner_radius=8,
            fg_color=C["primary_light"], hover_color=C["primary_muted"],
            text_color=C["primary"], font=FONT["small"],
            command=lambda: threading.Thread(target=self._load_library_bg, daemon=True).start()
        ).pack(side="left", expand=True, fill="x", padx=(3, 0))

    # ── Library ───────────────────────────────────────────────────────
    def _load_library_bg(self):
        lib = tlib.scan_library()
        self.app.root.after(0, self._set_library, lib)

    def _set_library(self, lib):
        self.library = lib
        self._on_search()

    def _on_search(self):
        query = self.search_var.get().strip().lower()
        if query:
            self.filtered = [t for t in self.library if query in t.name.lower()]
        else:
            self.filtered = list(self.library)
        self._render_all_list()

    def _render_all_list(self):
        self.listbox_all.delete(0, tk.END)
        for t in self.filtered:
            self.listbox_all.insert(tk.END, t.name)

    def _render_selected_list(self):
        self.listbox_sel.delete(0, tk.END)
        for t in self.selected:
            self.listbox_sel.insert(tk.END, t.name)
        count = len(self.selected)
        self.selected_count.configure(text=f"Đã chọn: {count}" if count else "")
        btn_text = f"Thêm Transitions ({count})" if count else "Thêm Transitions"
        self.apply_btn.configure(text=btn_text)

    # ── Add/Remove ────────────────────────────────────────────────────
    def _add_selected(self):
        indices = self.listbox_all.curselection()
        existing_rids = {t.resource_id for t in self.selected}
        for i in indices:
            t = self.filtered[i]
            if t.resource_id not in existing_rids:
                self.selected.append(t)
                existing_rids.add(t.resource_id)
        self._render_selected_list()

    def _remove_selected(self):
        indices = sorted(self.listbox_sel.curselection(), reverse=True)
        for i in indices:
            self.selected.pop(i)
        self._render_selected_list()

    # ── Actions ───────────────────────────────────────────────────────
    def _on_apply(self):
        projects = self.app.project_list.get_selected()
        if not projects:
            messagebox.showwarning("Chưa chọn project", "Vui lòng chọn project bên phải.")
            return
        if not self.selected:
            messagebox.showwarning("Chưa chọn transition", "Thêm transition vào danh sách dưới.")
            return

        confirm = messagebox.askokcancel(
            "Cảnh báo", "Vui lòng thoát CapCut trước!\nBấm OK nếu đã thoát."
        )
        if not confirm:
            return

        try:
            dur = float(self.duration_var.get() or 0.8)
        except ValueError:
            dur = 0.8

        try:
            interval = int(self.interval_var.get().strip()) if self.interval_var.get().strip() else 0
            interval = max(0, interval)
        except ValueError:
            interval = 0

        config = te.TransitionConfig(
            transitions=list(self.selected),
            duration_seconds=dur,
            interval=interval,
        )

        self.apply_btn.configure(state="disabled", text="Đang xử lý...")
        threading.Thread(
            target=self._run_apply, args=(projects, config), daemon=True
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
                r = te.apply_transitions(path, config, backup=True)
            except Exception as e:
                r = te.TransitionResult(False, str(e))
            if r.success:
                root.after(0, self.app.project_list.set_status, idx, "Done", C["green"])
                ok += 1
            else:
                root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])

        count = len(self.selected)
        btn_text = f"Thêm Transitions ({count})" if count else "Thêm Transitions"
        s = f"Transitions: {ok}/{len(selected)} OK"
        root.after(0, lambda: self.apply_btn.configure(state="normal", text=btn_text))
        root.after(0, lambda: self.app.status_var.set(f"  {s}"))

    def _on_clear(self):
        projects = self.app.project_list.get_selected()
        if not projects:
            messagebox.showwarning("Chưa chọn project", "Vui lòng chọn project bên phải.")
            return
        confirm = messagebox.askokcancel(
            "Xóa Transitions",
            f"Xóa tất cả transitions khỏi {len(projects)} project?\nThoát CapCut trước."
        )
        if not confirm:
            return

        self.clear_btn.configure(state="disabled", text="Đang xóa...")
        threading.Thread(target=self._run_clear, args=(projects,), daemon=True).start()

    def _run_clear(self, selected):
        root = self.app.root
        ok = 0
        for idx, draft in selected:
            path = draft.get("draft_fold_path", "")
            if not path or not os.path.isdir(path):
                root.after(0, self.app.project_list.set_status, idx, "Error", C["red"])
                continue
            try:
                r = te.clear_transitions(path, backup=True)
            except Exception as e:
                r = te.TransitionResult(False, str(e))
            if r.success:
                root.after(0, self.app.project_list.set_status, idx, "Cleared", C["green"])
                ok += 1
            else:
                root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])

        s = f"Cleared: {ok}/{len(selected)} OK"
        root.after(0, lambda: self.clear_btn.configure(state="normal", text="Xóa tất cả"))
        root.after(0, lambda: self.app.status_var.set(f"  {s}"))
