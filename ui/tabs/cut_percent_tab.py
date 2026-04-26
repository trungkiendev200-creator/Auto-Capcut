"""Tab Cut % — Cắt source video theo phần trăm đầu/cuối từng segment."""

import os
import threading
import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox

from ui.theme import COLORS as C, FONT
from core import cut_percent_engine, sync_engine


class CutPercentTab:
    """Cắt source X% đầu + Y% cuối mỗi segment ở video track chính."""

    def __init__(self, parent: ctk.CTkFrame, app):
        self.app = app
        self._build(parent)

    def _build(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(expand=True, fill="both", padx=16, pady=10)

        ctk.CTkLabel(
            frame, text="Cut %",
            font=FONT["heading"], text_color=C["text"]
        ).pack(anchor="w", pady=(0, 4))

        ctk.CTkLabel(
            frame,
            text="Cắt source X% đầu + Y% cuối mỗi segment ở video track chính. "
                 "Audio + text + overlay không bị động đến.",
            font=FONT["small"], text_color=C["text_light"], justify="left"
        ).pack(anchor="w", pady=(0, 10))

        # ── Inputs row 1: Cut Before ──
        r1 = ctk.CTkFrame(frame, fg_color="transparent")
        r1.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(r1, text="Cut Before:", width=130, anchor="w",
                     font=FONT["small"], text_color=C["text_light"]).pack(side="left")
        self.cut_before_var = ctk.StringVar(value="10")
        ctk.CTkEntry(r1, textvariable=self.cut_before_var, height=28, width=80,
                     fg_color=C["input_bg"], border_color=C["input_border"],
                     text_color=C["text"], corner_radius=6, font=FONT["small"]
                     ).pack(side="left")
        ctk.CTkLabel(r1, text="(%)", font=FONT["small"],
                     text_color=C["text_light"]).pack(side="left", padx=(6, 0))

        # ── Cut After ──
        r2 = ctk.CTkFrame(frame, fg_color="transparent")
        r2.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(r2, text="Cut After:", width=130, anchor="w",
                     font=FONT["small"], text_color=C["text_light"]).pack(side="left")
        self.cut_after_var = ctk.StringVar(value="10")
        ctk.CTkEntry(r2, textvariable=self.cut_after_var, height=28, width=80,
                     fg_color=C["input_bg"], border_color=C["input_border"],
                     text_color=C["text"], corner_radius=6, font=FONT["small"]
                     ).pack(side="left")
        ctk.CTkLabel(r2, text="(%)", font=FONT["small"],
                     text_color=C["text_light"]).pack(side="left", padx=(6, 0))

        # ── Threshold ──
        r3 = ctk.CTkFrame(frame, fg_color="transparent")
        r3.pack(fill="x", pady=(0, 6))
        self.threshold_on_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            r3, text="Không cắt đoạn <", variable=self.threshold_on_var,
            font=FONT["small"], text_color=C["text_light"],
            checkbox_width=16, checkbox_height=16,
            fg_color=C["primary"], hover_color=C["primary_hover"],
            width=130,
        ).pack(side="left")
        self.threshold_var = ctk.StringVar(value="1")
        ctk.CTkEntry(r3, textvariable=self.threshold_var, height=28, width=80,
                     fg_color=C["input_bg"], border_color=C["input_border"],
                     text_color=C["text"], corner_radius=6, font=FONT["small"]
                     ).pack(side="left")
        ctk.CTkLabel(r3, text="(s)", font=FONT["small"],
                     text_color=C["text_light"]).pack(side="left", padx=(6, 0))

        # ── N (cắt cách nhau) ──
        r4 = ctk.CTkFrame(frame, fg_color="transparent")
        r4.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(r4, text="Cắt cách nhau:", width=130, anchor="w",
                     font=FONT["small"], text_color=C["text_light"]).pack(side="left")
        self.every_n_var = ctk.StringVar(value="0")
        ctk.CTkEntry(r4, textvariable=self.every_n_var, height=28, width=80,
                     fg_color=C["input_bg"], border_color=C["input_border"],
                     text_color=C["text"], corner_radius=6, font=FONT["small"]
                     ).pack(side="left")
        ctk.CTkLabel(r4, text="đoạn (0 = cắt mọi đoạn; 2 = cứ 2 cắt 1)",
                     font=("Segoe UI", 10),
                     text_color=C["text_light"]).pack(side="left", padx=(6, 0))

        # ── Auto Sync ──
        r5 = ctk.CTkFrame(frame, fg_color="transparent")
        r5.pack(fill="x", pady=(0, 8))
        self.auto_sync_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            r5, text="Auto Sync sau khi cắt (đồng bộ video với audio)",
            variable=self.auto_sync_var,
            font=FONT["small"], text_color=C["text_light"],
            checkbox_width=16, checkbox_height=16,
            fg_color=C["primary"], hover_color=C["primary_hover"],
        ).pack(side="left")

        # ── Info bar ──
        self.info = ctk.CTkLabel(
            frame, text="Chọn project bên phải rồi bấm Cắt Video",
            font=FONT["body"], text_color=C["text_light"],
            fg_color=C["primary_light"], corner_radius=8, height=32
        )
        self.info.pack(fill="x", pady=(0, 6))

        # ── Log ──
        self.log = ctk.CTkTextbox(
            frame, height=120, fg_color=C["input_bg"],
            border_color=C["input_border"], border_width=1,
            corner_radius=8, text_color=C["text"], font=FONT["mono"]
        )
        self.log.pack(fill="both", expand=True, pady=(0, 8))
        self.log.configure(state="disabled")

        # ── Button ──
        self.btn = ctk.CTkButton(
            frame, text="Cắt Video", height=40, corner_radius=10,
            fg_color=C["primary"], hover_color=C["primary_hover"],
            font=FONT["button"], text_color=C["text_white"],
            command=self._on_click
        )
        self.btn.pack(fill="x")

    # ── helpers ─────────────────────────────────────────────────────────
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

    def _parse_inputs(self):
        """Parse và validate inputs. Return (params, error_msg)."""
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
            "cut_before": cb,
            "cut_after": ca,
            "threshold": threshold,
            "every_n": n,
            "auto_sync": self.auto_sync_var.get(),
        }, None

    # ── handler ─────────────────────────────────────────────────────────
    def _on_click(self):
        selected = self.app.project_list.get_selected()
        if not selected:
            self._set_info("Chưa chọn project nào!", C["red_light"], C["red"])
            return

        params, err = self._parse_inputs()
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

        self.btn.configure(state="disabled", text="Đang cắt...")
        self._set_info(
            f"Đang cắt {len(selected)} project...",
            C["primary_light"], C["primary"]
        )

        threading.Thread(
            target=self._run, args=(selected, params), daemon=True
        ).start()

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

    def _run(self, selected, params):
        root = self.app.root
        _log = self._make_log_fn()
        ok_count = 0
        fail_count = 0
        total = len(selected)

        for i, (idx, draft) in enumerate(selected, start=1):
            name = draft.get("draft_name", "?")
            path = self._resolve_path(draft)

            _log(f"── [{i}/{total}] CUT %: {name} ──")
            root.after(0, self.app.project_list.set_status, idx, "...", C["primary"])

            if not path:
                _log(f"  FAIL: draft folder not found")
                root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])
                fail_count += 1
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
                fail_count += 1
                continue

            _log(f"  OK: {r.message}")

            # Auto sync
            if params["auto_sync"]:
                _log(f"  [Auto Sync] đang đồng bộ video với audio...")
                try:
                    sr = sync_engine.sync_project(
                        path, video_mode=sync_engine.VIDEO_MODE_CUT, backup=False
                    )
                    if sr.success:
                        _log(f"    sync OK: {sr.message}")
                    else:
                        _log(f"    sync FAIL: {sr.message}")
                        root.after(0, self.app.project_list.set_status, idx,
                                   "Cut OK / Sync Fail", C["red"])
                        fail_count += 1
                        continue
                except Exception as e:
                    import traceback
                    _log(f"    sync EXCEPTION: {traceback.format_exc()}")
                    root.after(0, self.app.project_list.set_status, idx,
                               "Cut OK / Sync Fail", C["red"])
                    fail_count += 1
                    continue

            ok_count += 1
            root.after(0, self.app.project_list.set_status, idx, "Done", C["green"])

        summary = f"Cut %: {ok_count}/{total} OK, {fail_count} fail"
        _log(f"══ {summary} ══")
        bg = C["green_light"] if fail_count == 0 else C["red_light"]
        fg = C["green"] if fail_count == 0 else C["red"]
        root.after(0, self._set_info, summary, bg, fg)
        root.after(0, lambda: self.btn.configure(state="normal", text="Cắt Video"))
        root.after(0, lambda: self.app.status_var.set(f"  {summary}"))
