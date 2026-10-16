"""Left navigation sidebar."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

import customtkinter as ctk
from PIL import Image

from ui import theme
from utils.filesystem import resource_path

NAV_ITEMS = ["Builder", "Build History", "Settings", "About"]

ASSETS_DIR = resource_path("assets", "icons")


class Sidebar(ctk.CTkFrame):
    def __init__(self, master, on_navigate: Callable[[str], None], **kwargs):
        super().__init__(master, fg_color=theme.BG_SIDEBAR, corner_radius=0, width=220, **kwargs)
        self.grid_propagate(False)
        self.on_navigate = on_navigate
        self._buttons: dict[str, ctk.CTkButton] = {}
        self._active = NAV_ITEMS[0]

        self._build_header()
        self._build_nav()

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=theme.SPACING_MD, pady=(theme.SPACING_LG, theme.SPACING_MD))

        logo_path = ASSETS_DIR / "rivan_logo.png"
        if logo_path.exists():
            img = Image.open(logo_path)
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(48, 48))
            logo_label = ctk.CTkLabel(header, image=ctk_img, text="")
            logo_label.pack(side="left", padx=(0, theme.SPACING_SM))

        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.pack(side="left", fill="x")
        ctk.CTkLabel(
            title_frame, text="PyForge", font=theme.font(18, "bold"), text_color=theme.TEXT_PRIMARY
        ).pack(anchor="w")
        ctk.CTkLabel(
            title_frame, text="by Rivan Security", font=theme.font(11), text_color=theme.TEXT_SECONDARY
        ).pack(anchor="w")

        ctk.CTkFrame(self, fg_color=theme.BORDER_SUBTLE, height=1).pack(fill="x", padx=theme.SPACING_MD, pady=(0, theme.SPACING_MD))

    def _build_nav(self) -> None:
        for item in NAV_ITEMS:
            btn = ctk.CTkButton(
                self,
                text=item,
                anchor="w",
                font=theme.font(13),
                fg_color="transparent",
                hover_color=theme.BG_PANEL_RAISED,
                text_color=theme.TEXT_SECONDARY,
                corner_radius=theme.RADIUS_SM,
                height=40,
                command=lambda i=item: self._select(i),
            )
            btn.pack(fill="x", padx=theme.SPACING_SM, pady=2)
            self._buttons[item] = btn
        self._select(self._active)

    def _select(self, item: str) -> None:
        self._active = item
        for name, btn in self._buttons.items():
            if name == item:
                btn.configure(fg_color=theme.ACCENT_MUTED, text_color=theme.ACCENT)
            else:
                btn.configure(fg_color="transparent", text_color=theme.TEXT_SECONDARY)
        self.on_navigate(item)
