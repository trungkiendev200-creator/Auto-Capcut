"""Main application window."""

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox

from ui.theme import COLORS as C, FONT
from ui.widgets import ProjectListFrame
from ui.tabs.sync_tab import SyncTab
from ui.tabs.keyframe_tab import KeyFrameTab
from ui.tabs.animation_tab import AnimationTab
from ui.tabs import placeholder
from core import capcut, settings


class AutoCapcut:
    def __init__(self):
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        self.root.title("Auto CapCut")
        self.root.geometry("1050x620")
        self.root.resizable(False, False)
        self.root.configure(fg_color=C["bg"])

        self.capcut_path = tk.StringVar()
        self.export_path = tk.StringVar()
        self.status_var = tk.StringVar(value="Ready")

        self._build_ui()
        self._load_settings()
        self._load_projects()

    # ── UI ────────────────────────────────────────────────────────────
    def _build_ui(self):
        self.root.grid_columnconfigure(0, weight=3, minsize=640)
        self.root.grid_columnconfigure(1, weight=2, minsize=370)
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=0)

        self._build_left_panel()
        self._build_right_panel()
        self._build_status_bar()

    def _build_left_panel(self):
        left = ctk.CTkFrame(self.root, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(14, 6), pady=(14, 6))
        left.grid_rowconfigure(1, weight=1)
        left.grid_columnconfigure(0, weight=1)

        # Settings card
        self._build_settings_card(left)

        # Tabs
        tabview = ctk.CTkTabview(
            left, fg_color=C["card"], corner_radius=12,
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

        # Sync Audio tab
        self.sync_tab = SyncTab(tabview.add("Sync Audio"), app=self)

        # KeyFrames tab
        self.keyframe_tab = KeyFrameTab(tabview.add("KeyFrames"), app=self)

        # Animation tab
        self.animation_tab = AnimationTab(tabview.add("Animation"), app=self)

        # Placeholder tabs
        for name in ["Effect", "Transitions", "Captions"]:
            placeholder.build(tabview.add(name), name)

    def _build_settings_card(self, parent):
        card = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=12,
                             border_width=1, border_color=C["border"])
        card.grid(row=0, column=0, sticky="ew", pady=(0, 12))

        hdr = ctk.CTkFrame(card, fg_color=C["primary"], corner_radius=8, height=38)
        hdr.pack(fill="x", padx=4, pady=(4, 10))
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="  Settings", font=FONT["subheading"],
                      text_color=C["text_white"]).pack(side="left", padx=12, pady=6)

        for label_text, var, cmd in [
            ("Capcut Path:", self.capcut_path, self._browse_capcut),
            ("Export Path:", self.export_path, self._browse_export),
        ]:
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=3)
            ctk.CTkLabel(row, text=label_text, width=95, anchor="w",
                          font=FONT["body"], text_color=C["text_light"]).pack(side="left")
            ctk.CTkEntry(row, textvariable=var, height=34,
                          fg_color=C["input_bg"], border_color=C["input_border"],
                          text_color=C["text"], corner_radius=8).pack(
                side="left", fill="x", expand=True, padx=(8, 8))
            ctk.CTkButton(row, text="Browse", width=75, height=34, corner_radius=8,
                           fg_color=C["primary_light"], text_color=C["primary"],
                           hover_color=C["primary_muted"], border_width=1,
                           border_color=C["primary_muted"],
                           font=FONT["small"], command=cmd).pack(side="left")

        save_row = ctk.CTkFrame(card, fg_color="transparent")
        save_row.pack(fill="x", padx=16, pady=(6, 14))
        ctk.CTkButton(
            save_row, text="Save Settings", width=130, height=36, corner_radius=8,
            fg_color=C["primary"], hover_color=C["primary_hover"],
            font=FONT["body_bold"], text_color=C["text_white"],
            command=self._save_settings
        ).pack(side="right")

    def _build_right_panel(self):
        right = ctk.CTkFrame(self.root, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 14), pady=(14, 6))
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        phdr = ctk.CTkFrame(right, fg_color=C["primary"], corner_radius=10, height=38)
        phdr.grid(row=0, column=0, sticky="ew")
        phdr.pack_propagate(False)
        ctk.CTkLabel(phdr, text="  Project List", font=FONT["subheading"],
                      text_color=C["text_white"]).pack(side="left", padx=12, pady=6)

        self.project_list = ProjectListFrame(right)
        self.project_list.grid(row=1, column=0, sticky="nsew", pady=(4, 8))

        btn_bar = ctk.CTkFrame(right, fg_color="transparent")
        btn_bar.grid(row=2, column=0, sticky="ew")

        for text, cmd, fg, tc, hover in [
            ("Refresh", self._load_projects, C["primary"], C["text_white"], C["primary_hover"]),
            ("Select All", lambda: self.project_list.select_all(), C["primary_light"], C["primary"], C["primary_muted"]),
            ("Deselect", lambda: self.project_list.deselect_all(), C["primary_light"], C["primary"], C["primary_muted"]),
        ]:
            ctk.CTkButton(
                btn_bar, text=text, height=34, corner_radius=8,
                fg_color=fg, hover_color=hover,
                font=FONT["small_bold"], text_color=tc, command=cmd
            ).pack(side="left", padx=3, expand=True, fill="x")

    def _build_status_bar(self):
        ctk.CTkLabel(
            self.root, textvariable=self.status_var, height=28,
            fg_color=C["card"], corner_radius=0,
            font=FONT["small"], text_color=C["text_light"]
        ).grid(row=1, column=0, columnspan=2, sticky="ew")

    # ── Actions ───────────────────────────────────────────────────────
    def _load_projects(self):
        try:
            drafts = capcut.load_projects(self.capcut_path.get())
            self.project_list.load(drafts)
            self.status_var.set(f"  Loaded {len(drafts)} projects")
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

    def run(self):
        self.root.mainloop()
