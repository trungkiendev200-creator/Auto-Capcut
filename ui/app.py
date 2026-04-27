"""Main application window — redesigned clean UI."""

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import threading

from ui.theme import COLORS as C, FONT
from ui.widgets import ProjectListFrame
from ui.tabs.sync_tab import SyncTab
from ui.tabs.sync_sub_tab import SyncSubTab
from ui.tabs.keyframe_tab import KeyFrameTab
from ui.tabs.animation_tab import AnimationTab
from ui.tabs.transition_tab import TransitionTab
from ui.tabs.effect_tab import EffectTab
from ui.tabs.create_project_tab import CreateProjectTab
from ui.tabs.create_project_2_tab import CreateProject2Tab
from ui.tabs.cut_percent_tab import CutPercentTab
from ui.tabs.caption_tab import CaptionTab
from ui.tabs import placeholder
from core import capcut, settings


class AutoCapcut:
    def __init__(self):
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        self.root.title("Auto CapCut")
        self.root.geometry("1250x720")
        self.root.resizable(False, False)
        self.root.configure(fg_color=C["bg"])

        self.capcut_path = tk.StringVar()
        self.export_path = tk.StringVar()
        self.status_var = tk.StringVar(value="XS-Auto-Capcut")

        self._build_ui()
        self._load_settings()
        self._load_projects()

    def _build_ui(self):
        self.root.grid_columnconfigure(0, weight=3, minsize=780)
        self.root.grid_columnconfigure(1, weight=2, minsize=420)
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=0)

        self._build_left_panel()
        self._build_right_panel()
        self._build_status_bar()

    # ── LEFT PANEL ────────────────────────────────────────────────────
    def _build_left_panel(self):
        left = ctk.CTkFrame(self.root, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(12, 4), pady=(10, 4))
        left.grid_rowconfigure(1, weight=1)
        left.grid_columnconfigure(0, weight=1)

        self._build_settings_card(left)

        # Tabs — clean minimal style
        tabview = ctk.CTkTabview(
            left, fg_color=C["card"], corner_radius=10,
            border_width=1, border_color=C["border"],
            segmented_button_fg_color=C["tab_bg"],
            segmented_button_selected_color=C["primary"],
            segmented_button_selected_hover_color=C["primary_hover"],
            segmented_button_unselected_color=C["tab_bg"],
            segmented_button_unselected_hover_color=C["tab_hover"],
            text_color=C["text"],
            text_color_disabled=C["text_light"],
        )
        tabview.grid(row=1, column=0, sticky="nsew")

        self.create_tab = CreateProjectTab(tabview.add("Create Project"), app=self)
        self.create_tab_2 = CreateProject2Tab(tabview.add("Create Project 2"), app=self)
        self.sync_tab = SyncTab(tabview.add("Sync Audio"), app=self)
        self.cut_percent_tab = CutPercentTab(tabview.add("Cut %"), app=self)
        self.sync_sub_tab = SyncSubTab(tabview.add("VIP5AE"), app=self)
        self.keyframe_tab = KeyFrameTab(tabview.add("Key Frame"), app=self)
        self.animation_tab = AnimationTab(tabview.add("Animation"), app=self)
        self.transition_tab = TransitionTab(tabview.add("Transitions"), app=self)
        self.effect_tab = EffectTab(tabview.add("Effect"), app=self)

        self.caption_tab = CaptionTab(tabview.add("Caption"), app=self)

        log_tab = tabview.add("Log")
        self.log_box = ctk.CTkTextbox(
            log_tab, fg_color="#f1f5f9", border_width=0,
            corner_radius=8, text_color=C["text"],
            font=FONT["mono"],
        )
        self.log_box.pack(fill="both", expand=True, padx=6, pady=6)
        self.log_box.configure(state="disabled")

    def _build_settings_card(self, parent):
        card = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=10,
                             border_width=1, border_color=C["border"])
        card.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=10)

        # Row 1: Capcut Path
        r1 = ctk.CTkFrame(inner, fg_color="transparent")
        r1.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(r1, text="CapCut:", width=65, anchor="w",
                      font=FONT["small"], text_color=C["text_light"]).pack(side="left")
        ctk.CTkEntry(r1, textvariable=self.capcut_path, height=30,
                      fg_color=C["input_bg"], border_color=C["input_border"],
                      text_color=C["text"], corner_radius=6,
                      font=FONT["small"]).pack(side="left", fill="x", expand=True, padx=(4, 6))
        ctk.CTkButton(r1, text="...", width=32, height=30, corner_radius=6,
                       fg_color=C["tab_bg"], text_color=C["text"],
                       hover_color=C["primary_muted"], border_width=1,
                       border_color=C["input_border"],
                       font=FONT["small"], command=self._browse_capcut).pack(side="left")

        # Row 2: Export Path + Save
        r2 = ctk.CTkFrame(inner, fg_color="transparent")
        r2.pack(fill="x")
        ctk.CTkLabel(r2, text="Export:", width=65, anchor="w",
                      font=FONT["small"], text_color=C["text_light"]).pack(side="left")
        ctk.CTkEntry(r2, textvariable=self.export_path, height=30,
                      fg_color=C["input_bg"], border_color=C["input_border"],
                      text_color=C["text"], corner_radius=6,
                      font=FONT["small"]).pack(side="left", fill="x", expand=True, padx=(4, 6))
        ctk.CTkButton(r2, text="...", width=32, height=30, corner_radius=6,
                       fg_color=C["tab_bg"], text_color=C["text"],
                       hover_color=C["primary_muted"], border_width=1,
                       border_color=C["input_border"],
                       font=FONT["small"], command=self._browse_export).pack(side="left", padx=(0, 6))
        ctk.CTkButton(r2, text="Save", width=55, height=30, corner_radius=6,
                       fg_color=C["primary"], hover_color=C["primary_hover"],
                       text_color=C["text_white"],
                       font=FONT["small_bold"], command=self._save_settings).pack(side="left")

    # ── RIGHT PANEL ───────────────────────────────────────────────────
    def _build_right_panel(self):
        right = ctk.CTkFrame(self.root, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(4, 12), pady=(10, 4))
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        # Project header
        phdr = ctk.CTkFrame(right, fg_color=C["primary"], corner_radius=8, height=34)
        phdr.grid(row=0, column=0, sticky="ew")
        phdr.pack_propagate(False)
        ctk.CTkLabel(phdr, text="  Projects", font=FONT["subheading"],
                      text_color=C["text_white"]).pack(side="left", padx=10, pady=4)

        # Project list
        self.project_list = ProjectListFrame(right)
        self.project_list.grid(row=1, column=0, sticky="nsew", pady=(4, 4))

        # Action buttons
        btn_bar = ctk.CTkFrame(right, fg_color="transparent")
        btn_bar.grid(row=2, column=0, sticky="ew")

        for text, cmd, fg, tc, hover in [
            ("Refresh", self._load_projects, C["primary"], C["text_white"], C["primary_hover"]),
            ("All", lambda: self.project_list.select_all(), C["primary_light"], C["primary"], C["primary_muted"]),
            ("None", lambda: self.project_list.deselect_all(), C["primary_light"], C["primary"], C["primary_muted"]),
        ]:
            ctk.CTkButton(
                btn_bar, text=text, height=30, corner_radius=6,
                fg_color=fg, hover_color=hover,
                font=FONT["small_bold"], text_color=tc, command=cmd
            ).pack(side="left", padx=2, expand=True, fill="x")

        # Render section
        render_box = ctk.CTkFrame(right, fg_color=C["card"], corner_radius=8,
                                   border_width=1, border_color=C["border"])
        render_box.grid(row=3, column=0, sticky="ew", pady=(6, 0))

        render_inner = ctk.CTkFrame(render_box, fg_color="transparent")
        render_inner.pack(fill="x", padx=8, pady=6)

        self.auto_shutdown_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            render_inner, text="Shutdown after", variable=self.auto_shutdown_var,
            font=FONT["small"], text_color=C["text_light"],
            checkbox_width=16, checkbox_height=16,
            fg_color=C["primary"], hover_color=C["primary_hover"],
        ).pack(side="left")

        self.stop_render_btn = ctk.CTkButton(
            render_inner, text="Stop", height=30, width=55, corner_radius=6,
            fg_color=C["red_light"], hover_color=C["red"],
            text_color=C["red"], font=FONT["small"],
            command=self._on_stop_render, state="disabled"
        )
        self.stop_render_btn.pack(side="right", padx=(4, 0))

        self.render_btn = ctk.CTkButton(
            render_inner, text="Auto Render", height=30, corner_radius=6,
            fg_color=C["green"], hover_color="#16a34a",
            text_color=C["text_white"], font=FONT["small_bold"],
            command=self._on_auto_render_wip
        )
        self.render_btn.pack(side="right")

        # Calibrate row
        cal_row = ctk.CTkFrame(render_box, fg_color="transparent")
        cal_row.pack(fill="x", padx=8, pady=(0, 6))
        ctk.CTkButton(
            cal_row, text="Calibrate", height=26, corner_radius=6,
            fg_color=C["primary_light"], hover_color=C["primary_muted"],
            text_color=C["primary"], font=("Segoe UI", 10),
            command=self._on_calibrate
        ).pack(side="left")
        self.cal_status = ctk.CTkLabel(
            cal_row, text="", font=("Segoe UI", 10), text_color=C["text_light"]
        )
        self.cal_status.pack(side="left", padx=(6, 0))

    # ── STATUS BAR ────────────────────────────────────────────────────
    def _build_status_bar(self):
        bar = ctk.CTkFrame(self.root, fg_color=C["card"], height=26, corner_radius=0,
                            border_width=1, border_color=C["border"])
        bar.grid(row=1, column=0, columnspan=2, sticky="ew")
        bar.pack_propagate(False)
        ctk.CTkLabel(bar, textvariable=self.status_var,
                      font=("Segoe UI", 10), text_color=C["text_light"],
                      anchor="w").pack(side="left", padx=12)

    # ── LOG ───────────────────────────────────────────────────────────
    def log(self, text: str):
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {text}\n"
        def _write():
            self.log_box.configure(state="normal")
            self.log_box.insert("end", line)
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        self.root.after(0, _write)

    # ── CALIBRATE ─────────────────────────────────────────────────────
    def _on_calibrate(self):
        """Chụp template từ CapCut đang mở ở editor."""
        from core import auto_render
        confirm = messagebox.askokcancel(
            "Calibrate",
            "Mở CapCut → vào editor 1 project bất kỳ → bấm Export để mở dialog.\n\n"
            "Giữ nguyên dialog Export → bấm OK."
        )
        if not confirm:
            return

        self.root.iconify()
        time.sleep(1)

        def run():
            ok = auto_render.capture_templates(callback=self.log)
            self.root.after(0, self.root.deiconify)
            if ok:
                self.root.after(0, lambda: self.cal_status.configure(
                    text="Ready!", text_color=C["green"]))
            else:
                self.root.after(0, lambda: self.cal_status.configure(
                    text="Failed", text_color=C["red"]))

        threading.Thread(target=run, daemon=True).start()

    # ── ACTIONS ───────────────────────────────────────────────────────
    def _load_projects(self):
        try:
            drafts = capcut.load_projects(self.capcut_path.get())
            self.project_list.load(drafts)
            self.status_var.set(f"  {len(drafts)} projects loaded")
            # Clear input data trong SYNC SUB tab
            if hasattr(self, 'sync_sub_tab'):
                self.sync_sub_tab.clear_inputs()
        except FileNotFoundError:
            self.status_var.set("  Meta file not found")
        except Exception as e:
            self.status_var.set(f"  Error: {e}")

    def _browse_capcut(self):
        path = filedialog.askdirectory(title="Select CapCut folder")
        if path:
            self.capcut_path.set(path)
            self._load_projects()

    def _browse_export(self):
        path = filedialog.askdirectory(title="Select export folder")
        if path:
            self.export_path.set(path)

    def _save_settings(self):
        try:
            settings.save(self.capcut_path.get(), self.export_path.get())
            self.status_var.set("  Settings saved!")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _load_settings(self):
        s = settings.load()
        self.capcut_path.set(s["capcut_path"])
        self.export_path.set(s["export_path"])

    # ── AUTO RENDER ───────────────────────────────────────────────────
    def _on_auto_render_wip(self):
        messagebox.showinfo("Auto Render", "Chức năng đang hoàn thiện.")

    def _on_auto_render(self):
        selected = self.project_list.get_selected()
        if not selected:
            messagebox.showwarning("No project", "Select projects on the right panel.")
            return
        export_path = self.export_path.get()
        if not export_path:
            messagebox.showwarning("No Export Path", "Set Export Path in Settings.")
            return
        confirm = messagebox.askokcancel(
            "Auto Render",
            f"Render {len(selected)} project(s).\nExport to: {export_path}\n\n"
            "CapCut will open/close automatically.\nDo not use mouse/keyboard.\n\nOK to start."
        )
        if not confirm:
            return
        self._render_stop = False
        self.render_btn.configure(state="disabled", text="Rendering...")
        self.stop_render_btn.configure(state="normal")
        threading.Thread(target=self._run_render, args=(selected, export_path), daemon=True).start()

    def _on_stop_render(self):
        self._render_stop = True
        self.status_var.set("  Stopping...")
        self.stop_render_btn.configure(state="disabled")

    def _run_render(self, selected, export_path):
        from core import auto_render
        config = auto_render.RenderConfig(export_path=export_path, auto_shutdown=self.auto_shutdown_var.get())
        self.log(f"=== RENDER START ({len(selected)} projects) ===")
        self.log(f"Export: {export_path}")
        total_ok, total = 0, len(selected)

        for i, (idx, draft) in enumerate(selected):
            if self._render_stop:
                self.log("STOPPED by user")
                break
            name = draft.get("draft_name", "?")
            self.log(f"--- [{i+1}/{total}] {name} ---")
            def cb(msg, _idx=idx, _i=i):
                self.log(f"  {msg}")
                self.root.after(0, lambda: self.status_var.set(f"  [{_i+1}/{total}] {msg}"))
                self.root.after(0, self.project_list.set_status, _idx, "...", C["primary"])
            self.root.after(0, self.project_list.set_status, idx, "Render", C["primary"])
            try:
                ok, msg = auto_render.render_project(draft, config, tool_window=self.root, callback=cb)
            except Exception as e:
                ok, msg = False, str(e)
                import traceback
                self.log(f"  EXCEPTION: {traceback.format_exc()}")
            if ok:
                self.log(f"  OK: {msg}")
                self.root.after(0, self.project_list.set_status, idx, "Done", C["green"])
                total_ok += 1
            else:
                self.log(f"  FAIL: {msg}")
                self.root.after(0, self.project_list.set_status, idx, "Fail", C["red"])

        summary = f"Render: {total_ok}/{total} OK"
        self.log(f"=== {summary} ===")
        self.root.after(0, lambda: self.status_var.set(f"  {summary}"))
        self.root.after(0, lambda: self.render_btn.configure(state="normal", text="Auto Render"))
        self.root.after(0, lambda: self.stop_render_btn.configure(state="disabled", text="Stop"))
        if config.auto_shutdown and total_ok > 0 and not self._render_stop:
            self.log("Shutting down in 30s...")
            auto_render.shutdown_pc()

    def run(self):
        self.root.mainloop()
