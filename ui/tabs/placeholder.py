"""Placeholder tab for features coming soon."""

import customtkinter as ctk
from ui.theme import COLORS as C, FONT


def build(parent: ctk.CTkFrame, name: str):
    ctk.CTkLabel(
        parent, text=f"{name}\nComing soon...",
        font=FONT["body"], text_color=C["text_light"]
    ).pack(expand=True)
