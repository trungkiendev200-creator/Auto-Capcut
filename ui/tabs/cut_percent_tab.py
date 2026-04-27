"""Tab Cut % — sub-tabs: Cut Video + Trích xuất âm thanh."""

import os
import threading
import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox

from ui.theme import COLORS as C, FONT
from core import cut_percent_engine, sync_engine


class CutPercentTab:
    """Tab Cut % với sub-tabs cho từng chức năng."""

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

        self._build_extract_audio_tab(sub_tabs.add("Trích xuất âm thanh"))
        self._build_cut_video_tab(sub_tabs.add("Cut %"))

        # ── Info bar (shared) ──
        self.info = ctk.CTkLabel(
            frame, text="Chọn project bên phải rồi bấm chạy",
            font=FONT["small"], text_color=C["text_light"],
            fg_color=C["primary_light"], corner_radius=6, height=26
        )
        self.info.grid(row=1, column=0, sticky="ew", pady=(4, 2))

        # ── Log (shared) ──
        self.log = ctk.CTkTextbox(
            frame, height=110, fg_color=C["input_bg"],
            border_color=C["input_border"], border_width=1,
            corner_radius=6, text_color=C["text"], font=FONT["mono"]
        )
        self.log.grid(row=2, column=0, sticky="nsew", pady=(2, 0))
        self.log.configure(state="disabled")

    # ── Sub-tab: Trích xuất âm thanh ───────────────────────────────
    def _build_extract_audio_tab(self, parent):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=14, pady=10)

        ctk.CTkLabel(
            f, text="Trích xuất âm thanh",
            font=FONT["subheading"], text_color=C["text"]
        ).pack(anchor="w", pady=(0, 2))
        ctk.CTkLabel(
            f, text="Tách audio từ video segments trên track chính (giống CapCut).",
            font=FONT["small"], text_color=C["text_light"]
        ).pack(anchor="w", pady=(0, 10))

        # Info card
        card = ctk.CTkFrame(f, fg_color=C["primary_light"], corner_radius=8)
        card.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(
            card,
            text="• Video segment → audio segment cùng timing trên track mới\n"
                 "• Audio trỏ về cùng file mp4, video gốc giữ nguyên (không mute)\n"
                 "• Photo segments được bỏ qua\n"
                 "• Hỗ trợ batch: chọn nhiều project bên phải",
            font=FONT["small"], text_color=C["text"],
            justify="left", anchor="w",
        ).pack(fill="x", padx=14, pady=10)

        # Button
        self.extract_btn = ctk.CTkButton(
            f, text="Trích xuất âm thanh", height=40, corner_radius=10,
            fg_color=C["accent"], hover_color="#7c3aed",
            font=FONT["button"], text_color=C["text_white"],
            command=self._on_extract_click
        )
        self.extract_btn.pack(fill="x")

    # ── Sub-tab: Cut % ─────────────────────────────────────────────
    def _build_cut_video_tab(self, parent):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=14, pady=10)

        ctk.CTkLabel(
            f, text="Cắt video theo phần trăm",
            font=FONT["subheading"], text_color=C["text"]
        ).pack(anchor="w", pady=(0, 2))
        ctk.CTkLabel(
            f, text="Cắt source X% đầu + Y% cuối mỗi segment ở video track chính.",
            font=FONT["small"], text_color=C["text_light"]
        ).pack(anchor="w", pady=(0, 10))

        # ── Card 1: Cut percentages ──
        card1 = ctk.CTkFrame(f, fg_color=C["primary_light"], corner_radius=8)
        card1.pack(fill="x", pady=(0, 6))
        c1 = ctk.CTkFrame(card1, fg_color="transparent")
        c1.pack(fill="x", padx=14, pady=10)

        ctk.CTkLabel(c1, text="Cut Before:", font=FONT["small"],
                     text_color=C["text"]).pack(side="left")
        self.cut_before_var = ctk.StringVar(value="10")
        ctk.CTkEntry(c1, textvariable=self.cut_before_var, height=28, width=60,
                     fg_color=C["card"], border_color=C["input_border"],
                     text_color=C["text"], corner_radius=6, font=FONT["small"],
                     justify="center"
                     ).pack(side="left", padx=(6, 2))
        ctk.CTkLabel(c1, text="%", font=FONT["small"],
                     text_color=C["text_light"]).pack(side="left", padx=(0, 18))

        ctk.CTkLabel(c1, text="Cut After:", font=FONT["small"],
                     text_color=C["text"]).pack(side="left")
        self.cut_after_var = ctk.StringVar(value="10")
        ctk.CTkEntry(c1, textvariable=self.cut_after_var, height=28, width=60,
                     fg_color=C["card"], border_color=C["input_border"],
                     text_color=C["text"], corner_radius=6, font=FONT["small"],
                     justify="center"
                     ).pack(side="left", padx=(6, 2))
        ctk.CTkLabel(c1, text="%", font=FONT["small"],
                     text_color=C["text_light"]).pack(side="left")

        # ── Card 2: Filters (grid: label - entry - unit/hint - checkbox bật/tắt) ──
        card2 = ctk.CTkFrame(f, fg_color=C["card"], corner_radius=8,
                             border_width=1, border_color=C["border"])
        card2.pack(fill="x", pady=(0, 6))
        c2 = ctk.CTkFrame(card2, fg_color="transparent")
        c2.pack(fill="x", padx=14, pady=10)
        c2.grid_columnconfigure(0, weight=0, minsize=140)  # label
        c2.grid_columnconfigure(1, weight=0)               # entry
        c2.grid_columnconfigure(2, weight=1)               # unit + hint (expandable)
        c2.grid_columnconfigure(3, weight=0)               # checkbox at end

        # Row 0: threshold
        ctk.CTkLabel(c2, text="Bỏ qua segment ≤", font=FONT["small"],
                     text_color=C["text"], anchor="w"
                     ).grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.threshold_var = ctk.StringVar(value="1")
        ctk.CTkEntry(c2, textvariable=self.threshold_var, height=26, width=60,
                     fg_color=C["input_bg"], border_color=C["input_border"],
                     text_color=C["text"], corner_radius=6, font=FONT["small"],
                     justify="center"
                     ).grid(row=0, column=1, sticky="w", pady=(0, 4))
        ctk.CTkLabel(c2, text="giây", font=FONT["small"],
                     text_color=C["text_light"]
                     ).grid(row=0, column=2, sticky="w", padx=(6, 0), pady=(0, 4))
        self.threshold_on_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            c2, text="", variable=self.threshold_on_var, width=18,
            checkbox_width=16, checkbox_height=16,
            fg_color=C["primary"], hover_color=C["primary_hover"],
        ).grid(row=0, column=3, sticky="e", padx=(8, 0), pady=(0, 4))

        # Row 1: every N
        ctk.CTkLabel(c2, text="Cắt cách nhau:", font=FONT["small"],
                     text_color=C["text"], anchor="w"
                     ).grid(row=1, column=0, sticky="w")
        self.every_n_var = ctk.StringVar(value="0")
        ctk.CTkEntry(c2, textvariable=self.every_n_var, height=26, width=60,
                     fg_color=C["input_bg"], border_color=C["input_border"],
                     text_color=C["text"], corner_radius=6, font=FONT["small"],
                     justify="center"
                     ).grid(row=1, column=1, sticky="w")
        ctk.CTkLabel(c2, text="đoạn (0 = mọi đoạn, 2 = cứ 2 cắt 1)",
                     font=("Segoe UI", 10),
                     text_color=C["text_light"]
                     ).grid(row=1, column=2, columnspan=2, sticky="w", padx=(6, 0))

        # ── Auto Sync ──
        r_sync = ctk.CTkFrame(f, fg_color="transparent")
        r_sync.pack(fill="x", pady=(0, 8))
        self.auto_sync_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            r_sync, text="Auto Sync — đổi speed video để khớp audio",
            variable=self.auto_sync_var,
            font=FONT["small"], text_color=C["text"],
            checkbox_width=16, checkbox_height=16,
            fg_color=C["primary"], hover_color=C["primary_hover"],
        ).pack(side="left")

        # Button
        self.cut_btn = ctk.CTkButton(
            f, text="Cắt Video", height=40, corner_radius=10,
            fg_color=C["primary"], hover_color=C["primary_hover"],
            font=FONT["button"], text_color=C["text_white"],
            command=self._on_cut_click
        )
        self.cut_btn.pack(fill="x")

    # ── helpers ─────────────────────────────────────────────────────
    def _append_log(self, text: str):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _set_info(self, text: str, bg: str, fg: str):
        self.info.configure(text=text, fg_color=bg, text_color=fg)

    def _make_log_fn(self):
        root = self.app.root
        def _log(msg):
            root.after(0, self._append_log, msg)
        return _log

    def _resolve_path(self, draft: dict) -> str:
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

    # ── Cut Video handlers ──────────────────────────────────────────
    def _parse_cut_inputs(self):
        try:
            cb = float(self.cut_before_var.get())
            ca = float(self.cut_after_var.get())
        except ValueError:
            return None, "Cut Before / Cut After phải là số"
        if cb < 0 or ca < 0:
            return None, "Cut % không được âm"
        if cb + ca >= 100:
            return None, "Cut Before + Cut After phải < 100%"

        threshold = None
        if self.threshold_on_var.get():
            try:
                threshold = float(self.threshold_var.get())
            except ValueError:
                return None, "Threshold phải là số"
            if threshold < 0:
                return None, "Threshold không được âm"

        try:
            n = int(self.every_n_var.get())
        except ValueError:
            return None, "N phải là số nguyên"
        if n < 0:
            return None, "N không được âm"

        return {
            "cut_before": cb, "cut_after": ca,
            "threshold": threshold, "every_n": n,
            "auto_sync": self.auto_sync_var.get(),
        }, None

    def _on_cut_click(self):
        selected = self.app.project_list.get_selected()
        if not selected:
            self._set_info("Chưa chọn project nào!", C["red_light"], C["red"])
            return

        params, err = self._parse_cut_inputs()
        if err:
            self._set_info(err, C["red_light"], C["red"])
            return

        confirm = messagebox.askokcancel(
            "Cut %",
            f"Cắt {len(selected)} project:\n"
            f"Cut Before: {params['cut_before']}% | Cut After: {params['cut_after']}%\n"
            f"Threshold: {params['threshold'] if params['threshold'] is not None else 'OFF'}s | "
            f"N: {params['every_n']} | Auto Sync: {'ON' if params['auto_sync'] else 'OFF'}\n\n"
            "Thoát CapCut trước khi tiếp tục.\nOK?"
        )
        if not confirm:
            return

        self.cut_btn.configure(state="disabled", text="Đang cắt...")
        self._set_info(f"Đang cắt {len(selected)} project...",
                       C["primary_light"], C["primary"])

        threading.Thread(
            target=self._run_cut, args=(selected, params), daemon=True
        ).start()

    def _run_cut(self, selected, params):
        root = self.app.root
        _log = self._make_log_fn()
        ok = fail = 0
        total = len(selected)

        for i, (idx, draft) in enumerate(selected, start=1):
            name = draft.get("draft_name", "?")
            path = self._resolve_path(draft)

            _log(f"── [{i}/{total}] CUT %: {name} ──")
            root.after(0, self.app.project_list.set_status, idx, "...", C["primary"])

            if not path:
                _log("  FAIL: draft folder not found")
                root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])
                fail += 1
                continue

            try:
                r = cut_percent_engine.cut_video_percent(
                    path,
                    cut_before_pct=params["cut_before"],
                    cut_after_pct=params["cut_after"],
                    threshold_sec=params["threshold"],
                    every_n=params["every_n"],
                    backup=True,
                    log_fn=_log,
                )
            except Exception as e:
                import traceback
                _log(f"  EXCEPTION: {traceback.format_exc()}")
                r = cut_percent_engine.CutPercentResult(False, str(e))

            if not r.success:
                _log(f"  FAIL: {r.message}")
                root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])
                fail += 1
                continue

            _log(f"  OK: {r.message}")

            if params["auto_sync"]:
                _log("  [Auto Sync] đổi speed video để khớp audio...")
                try:
                    sr = sync_engine.sync_project(
                        path, video_mode=sync_engine.VIDEO_MODE_SPEED, backup=False
                    )
                    if sr.success:
                        _log(f"    sync OK: {sr.message}")
                    else:
                        _log(f"    sync FAIL: {sr.message}")
                        root.after(0, self.app.project_list.set_status, idx,
                                   "Cut OK / Sync Fail", C["red"])
                        fail += 1
                        continue
                except Exception as e:
                    import traceback
                    _log(f"    sync EXCEPTION: {traceback.format_exc()}")
                    root.after(0, self.app.project_list.set_status, idx,
                               "Cut OK / Sync Fail", C["red"])
                    fail += 1
                    continue

            ok += 1
            root.after(0, self.app.project_list.set_status, idx, "Done", C["green"])

        summary = f"Cut %: {ok}/{total} OK, {fail} fail"
        _log(f"══ {summary} ══")
        bg = C["green_light"] if fail == 0 else C["red_light"]
        fg = C["green"] if fail == 0 else C["red"]
        root.after(0, self._set_info, summary, bg, fg)
        root.after(0, lambda: self.cut_btn.configure(state="normal", text="Cắt Video"))
        root.after(0, lambda: self.app.status_var.set(f"  {summary}"))

    # ── Extract Audio handlers ──────────────────────────────────────
    def _on_extract_click(self):
        selected = self.app.project_list.get_selected()
        if not selected:
            self._set_info("Chưa chọn project nào!", C["red_light"], C["red"])
            return

        confirm = messagebox.askokcancel(
            "Trích xuất âm thanh",
            f"Tách âm thanh từ {len(selected)} project.\n\n"
            "Mỗi video segment trên track chính sẽ được tạo audio segment "
            "tương ứng trên audio track mới.\n\n"
            "Thoát CapCut trước khi tiếp tục.\nOK?"
        )
        if not confirm:
            return

        self.extract_btn.configure(state="disabled", text="Đang trích xuất...")
        self._set_info(f"Đang trích xuất {len(selected)} project...",
                       C["primary_light"], C["primary"])

        threading.Thread(
            target=self._run_extract, args=(selected,), daemon=True
        ).start()

    def _run_extract(self, selected):
        root = self.app.root
        _log = self._make_log_fn()
        ok = fail = 0
        total = len(selected)

        for i, (idx, draft) in enumerate(selected, start=1):
            name = draft.get("draft_name", "?")
            path = self._resolve_path(draft)

            _log(f"── [{i}/{total}] EXTRACT AUDIO: {name} ──")
            root.after(0, self.app.project_list.set_status, idx, "...", C["primary"])

            if not path:
                _log("  FAIL: draft folder not found")
                root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])
                fail += 1
                continue

            try:
                r = cut_percent_engine.extract_audio_from_videos(
                    path, backup=True, log_fn=_log
                )
            except Exception as e:
                import traceback
                _log(f"  EXCEPTION: {traceback.format_exc()}")
                r = cut_percent_engine.ExtractAudioResult(False, str(e))

            if r.success:
                _log(f"  OK: {r.message}")
                ok += 1
                root.after(0, self.app.project_list.set_status, idx, "Done", C["green"])
            else:
                _log(f"  FAIL: {r.message}")
                fail += 1
                root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])

        summary = f"Extract: {ok}/{total} OK, {fail} fail"
        _log(f"══ {summary} ══")
        bg = C["green_light"] if fail == 0 else C["red_light"]
        fg = C["green"] if fail == 0 else C["red"]
        root.after(0, self._set_info, summary, bg, fg)
        root.after(0, lambda: self.extract_btn.configure(
            state="normal", text="Trích xuất âm thanh"))
        root.after(0, lambda: self.app.status_var.set(f"  {summary}"))
