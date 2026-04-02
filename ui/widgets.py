"""Reusable UI widgets — redesigned."""

import customtkinter as ctk
import tkinter as tk
from ui.theme import COLORS as C, FONT


class ProjectListFrame(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=C["card"], corner_radius=10,
                         border_width=1, border_color=C["border"], **kwargs)
        self.projects: list[dict] = []
        self.check_vars: list[tk.BooleanVar] = []
        self.status_labels: list[ctk.CTkLabel] = []

        # Header
        header = ctk.CTkFrame(self, fg_color=C["primary"], corner_radius=6, height=32)
        header.pack(fill="x", padx=3, pady=(3, 0))
        header.pack_propagate(False)

        self.select_all_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            header, text="", width=18, height=18,
            variable=self.select_all_var, command=self._toggle_all,
            checkbox_width=16, checkbox_height=16,
            fg_color=C["text_white"], checkmark_color=C["primary"],
            hover_color=C["primary_muted"], border_color=C["text_white"],
        ).pack(side="left", padx=(10, 8), pady=5)

        ctk.CTkLabel(header, text="Name", font=FONT["small_bold"],
                      text_color=C["text_white"]).pack(side="left", pady=5)
        ctk.CTkLabel(header, text="Status", font=FONT["small_bold"],
                      text_color=C["text_white"], width=55
                      ).pack(side="right", padx=(0, 12), pady=5)

        # Scrollable
        self.scroll = ctk.CTkScrollableFrame(
            self, fg_color=C["card"], corner_radius=0,
            scrollbar_button_color=C["primary_muted"],
            scrollbar_button_hover_color=C["primary"],
        )
        self.scroll.pack(fill="both", expand=True, padx=3, pady=(1, 3))

    def load(self, projects: list[dict]):
        self.projects = projects
        self.check_vars.clear()
        self.status_labels.clear()
        for w in self.scroll.winfo_children():
            w.destroy()

        for idx, draft in enumerate(projects):
            var = tk.BooleanVar(value=False)
            self.check_vars.append(var)

            bg = C["row_a"] if idx % 2 == 0 else C["row_b"]
            row = ctk.CTkFrame(self.scroll, fg_color=bg, corner_radius=6, height=32)
            row.pack(fill="x", padx=2, pady=1)
            row.pack_propagate(False)

            ctk.CTkCheckBox(
                row, text="", width=18, height=18, variable=var,
                checkbox_width=16, checkbox_height=16,
                fg_color=C["primary"], hover_color=C["primary_hover"],
                border_color=C["input_border"], checkmark_color=C["text_white"],
                command=self._update_select_all,
            ).pack(side="left", padx=(10, 6), pady=4)

            ctk.CTkLabel(
                row, text=draft.get("draft_name", "?"),
                font=FONT["small"], text_color=C["text"], anchor="w"
            ).pack(side="left", padx=2, fill="x", expand=True)

            lbl = ctk.CTkLabel(row, text="", font=("Segoe UI", 10),
                                text_color=C["text_light"], width=55)
            lbl.pack(side="right", padx=(0, 10))
            self.status_labels.append(lbl)

    def set_status(self, idx: int, text: str, color: str | None = None):
        if 0 <= idx < len(self.status_labels):
            self.status_labels[idx].configure(text=text, text_color=color or C["text_light"])

    def _toggle_all(self):
        val = self.select_all_var.get()
        for v in self.check_vars:
            v.set(val)

    def _update_select_all(self):
        self.select_all_var.set(
            all(v.get() for v in self.check_vars) if self.check_vars else False
        )

    def get_selected(self) -> list[tuple[int, dict]]:
        return [(i, self.projects[i]) for i, v in enumerate(self.check_vars) if v.get()]

    def select_all(self):
        self.select_all_var.set(True)
        self._toggle_all()

    def deselect_all(self):
        self.select_all_var.set(False)
        self._toggle_all()
