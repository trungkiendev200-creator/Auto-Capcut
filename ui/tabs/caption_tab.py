"""Tab Caption — sub-tabs cho các chức năng caption/subtitle."""

import os
import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox

from ui.theme import COLORS as C, FONT
from core import srt_engine


class CaptionTab:
    """Tab Caption với sub-tabs."""

    def __init__(self, parent: ctk.CTkFrame, app):
        self.app = app
        self.export_dir_var = ctk.StringVar()
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

        self._build_export_srt_tab(sub_tabs.add("Export SRT"))

        # Info bar (shared)
        self.info = ctk.CTkLabel(
            frame, text="Chọn project bên phải, chọn output folder rồi bấm Export",
            font=FONT["small"], text_color=C["text_light"],
            fg_color=C["primary_light"], corner_radius=6, height=26
        )
        self.info.grid(row=1, column=0, sticky="ew", pady=(4, 2))

        # Log (shared)
        self.log = ctk.CTkTextbox(
            frame, height=130, fg_color=C["input_bg"],
            border_color=C["input_border"], border_width=1,
            corner_radius=6, text_color=C["text"], font=FONT["mono"]
        )
        self.log.grid(row=2, column=0, sticky="nsew", pady=(2, 0))
        self.log.configure(state="disabled")

    # ── Sub-tab: Export SRT ─────────────────────────────────────────
    def _build_export_srt_tab(self, parent):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=14, pady=10)

        ctk.CTkLabel(
            f, text="Export SRT",
            font=FONT["subheading"], text_color=C["text"]
        ).pack(anchor="w", pady=(0, 2))
        ctk.CTkLabel(
            f, text="Xuất file .srt từ text track của project. "
                    "Tên file = tên project.",
            font=FONT["small"], text_color=C["text_light"]
        ).pack(anchor="w", pady=(0, 12))

        # Folder picker
        r = ctk.CTkFrame(f, fg_color="transparent")
        r.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(r, text="Output folder:", width=110, anchor="w",
                     font=FONT["small"], text_color=C["text"]).pack(side="left")
        ctk.CTkEntry(r, textvariable=self.export_dir_var, height=30,
                     fg_color=C["input_bg"], border_color=C["input_border"],
                     text_color=C["text"], corner_radius=6, font=FONT["small"]
                     ).pack(side="left", fill="x", expand=True, padx=(4, 6))
        ctk.CTkButton(r, text="...", width=32, height=30, corner_radius=6,
                      fg_color=C["tab_bg"], text_color=C["text"],
                      hover_color=C["primary_muted"], border_width=1,
                      border_color=C["input_border"], font=FONT["small"],
                      command=self._browse_dir
                      ).pack(side="left")

        # Button
        self.export_btn = ctk.CTkButton(
            f, text="Export SRT", height=40, corner_radius=10,
            fg_color=C["primary"], hover_color=C["primary_hover"],
            font=FONT["button"], text_color=C["text_white"],
            command=self._on_export_click
        )
        self.export_btn.pack(fill="x")

    # ── helpers ─────────────────────────────────────────────────────
    def _append_log(self, text: str):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _set_info(self, text: str, bg: str, fg: str):
        self.info.configure(text=text, fg_color=bg, text_color=fg)

    def _browse_dir(self):
        path = filedialog.askdirectory(title="Chọn folder lưu file SRT")
        if path:
            self.export_dir_var.set(path)

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

    # ── handler ─────────────────────────────────────────────────────
    def _on_export_click(self):
        selected = self.app.project_list.get_selected()
        if not selected:
            self._set_info("Chưa chọn project nào!", C["red_light"], C["red"])
            return

        out_dir = self.export_dir_var.get().strip()
        if not out_dir or not os.path.isdir(out_dir):
            self._set_info("Output folder không hợp lệ!", C["red_light"], C["red"])
            return

        confirm = messagebox.askokcancel(
            "Export SRT",
            f"Xuất {len(selected)} project ra .srt\n"
            f"Folder: {out_dir}\n\n"
            "Project không có text track sẽ skip.\nOK?"
        )
        if not confirm:
            return

        self.export_btn.configure(state="disabled", text="Đang xuất...")
        self._set_info(f"Đang xuất {len(selected)} project...",
                       C["primary_light"], C["primary"])

        threading.Thread(
            target=self._run_export, args=(selected, out_dir), daemon=True
        ).start()

    def _run_export(self, selected, out_dir):
        root = self.app.root
        ok = skip = fail = 0
        total = len(selected)

        for i, (idx, draft) in enumerate(selected, start=1):
            name = draft.get("draft_name", "?")
            path = self._resolve_path(draft)

            root.after(0, self._append_log, f"── [{i}/{total}] {name} ──")
            root.after(0, self.app.project_list.set_status, idx, "...", C["primary"])

            if not path:
                root.after(0, self._append_log, "  FAIL: draft folder not found")
                root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])
                fail += 1
                continue

            try:
                r = srt_engine.export_srt(path, out_dir, name)
            except Exception as e:
                import traceback
                root.after(0, self._append_log, f"  EXCEPTION: {traceback.format_exc()}")
                r = srt_engine.ExportSrtResult(False, str(e))

            if r.success:
                root.after(0, self._append_log, f"  OK: {r.message}")
                root.after(0, self.app.project_list.set_status, idx, "Done", C["green"])
                ok += 1
            else:
                # Theo spec: project không có text track = SKIP với warning
                no_text = "không tìm thấy text" in r.message.lower() or \
                          "không có sub" in r.message.lower()
                if no_text:
                    root.after(0, self._append_log, f"  SKIP: {r.message}")
                    root.after(0, self.app.project_list.set_status, idx, "Skip", C["text_light"])
                    skip += 1
                else:
                    root.after(0, self._append_log, f"  FAIL: {r.message}")
                    root.after(0, self.app.project_list.set_status, idx, "Fail", C["red"])
                    fail += 1

        summary = f"Export SRT: {ok}/{total} OK, {skip} skip, {fail} fail"
        root.after(0, self._append_log, f"══ {summary} ══")
        bg = C["green_light"] if fail == 0 else C["red_light"]
        fg = C["green"] if fail == 0 else C["red"]
        root.after(0, self._set_info, summary, bg, fg)
        root.after(0, lambda: self.export_btn.configure(state="normal", text="Export SRT"))
        root.after(0, lambda: self.app.status_var.set(f"  {summary}"))
