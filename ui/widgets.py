"""Reusable UI widgets."""

import customtkinter as ctk
import tkinter as tk
from ui.theme import COLORS as C, FONT


class ProjectListFrame(ctk.CTkFrame):
    """Project list with checkboxes and status indicators."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=C["card"], corner_radius=12,
                         border_width=1, border_color=C["border"], **kwargs)
        self.projects: list[dict] = []
        self.check_vars: list[tk.BooleanVar] = []
        self.status_labels: list[ctk.CTkLabel] = []

        # Header
        header = ctk.CTkFrame(self, fg_color=C["primary"], corner_radius=8, height=40)
        header.pack(fill="x", padx=4, pady=(4, 0))
        header.pack_propagate(False)

        self.select_all_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            header, text="", width=20, height=20,
            variable=self.select_all_var, command=self._toggle_all,
            checkbox_width=18, checkbox_height=18,
            fg_color=C["text_white"], checkmark_color=C["primary"],
            hover_color=C["primary_muted"], border_color=C["text_white"],
        ).pack(side="left", padx=(14, 10), pady=8)

        ctk.CTkLabel(header, text="Project Name", font=FONT["body_bold"],
                      text_color=C["text_white"]).pack(side="left", pady=8)
        ctk.CTkLabel(header, text="Status", font=FONT["body_bold"],
                      text_color=C["text_white"], width=65
                      ).pack(side="right", padx=(0, 18), pady=8)

        # Scrollable list
        self.scroll = ctk.CTkScrollableFrame(
            self, fg_color=C["card"], corner_radius=0,
            scrollbar_button_color=C["primary_muted"],
            scrollbar_button_hover_color=C["primary"],
        )
        self.scroll.pack(fill="both", expand=True, padx=4, pady=(2, 4))

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
            row = ctk.CTkFrame(self.scroll, fg_color=bg, corner_radius=8, height=38)
            row.pack(fill="x", padx=2, pady=2)
            row.pack_propagate(False)

            ctk.CTkCheckBox(
                row, text="", width=20, height=20, variable=var,
                checkbox_width=18, checkbox_height=18,
                fg_color=C["primary"], hover_color=C["primary_hover"],
                border_color=C["input_border"], checkmark_color=C["text_white"],
                command=self._update_select_all,
            ).pack(side="left", padx=(12, 10), pady=6)

            ctk.CTkLabel(
                row, text=draft.get("draft_name", "?"),
                font=FONT["body"], text_color=C["text"], anchor="w"
            ).pack(side="left", padx=4, fill="x", expand=True)

            status_lbl = ctk.CTkLabel(
                row, text="", font=FONT["small"],
                text_color=C["text_light"], width=65
            )
            status_lbl.pack(side="right", padx=(0, 14))
            self.status_labels.append(status_lbl)

    def set_status(self, idx: int, text: str, color: str | None = None):
        if 0 <= idx < len(self.status_labels):
            self.status_labels[idx].configure(
                text=text, text_color=color or C["text_light"]
            )

    def _toggle_all(self):
        val = self.select_all_var.get()
        for v in self.check_vars:
            v.set(val)

    def _update_select_all(self):
        self.select_all_var.set(
            all(v.get() for v in self.check_vars) if self.check_vars else False
        )

    def get_selected(self) -> list[tuple[int, dict]]:
        """Returns list of (index, draft_dict) for checked projects."""
        return [
            (i, self.projects[i])
            for i, v in enumerate(self.check_vars) if v.get()
        ]

    def select_all(self):
        self.select_all_var.set(True)
        self._toggle_all()

    def deselect_all(self):
        self.select_all_var.set(False)
        self._toggle_all()
