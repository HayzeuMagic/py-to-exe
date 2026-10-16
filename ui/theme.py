"""PyForge design system — colors, spacing, and typography.

Palette is derived from the Rivan Security Inc Academy logo: deep navy,
sky blue accent, and white/near-white text.
"""
from __future__ import annotations

import customtkinter as ctk

# -- Core palette (sampled from rivan_logo.png) -----------------------------
NAVY = "#0D2152"
NAVY_DEEP = "#081630"
SKY_BLUE = "#60D9FE"
SKY_BLUE_HOVER = "#3EC6F0"
WHITE = "#FFFFFF"

# -- Semantic tokens ---------------------------------------------------------
BG_APP = "#0A1830"
BG_SIDEBAR = NAVY_DEEP
BG_PANEL = "#0F2242"
BG_PANEL_RAISED = "#132A52"
BG_INPUT = "#0C1E3E"

BORDER = "#1E3A66"
BORDER_SUBTLE = "#162B50"

TEXT_PRIMARY = "#F2F6FC"
TEXT_SECONDARY = "#9FB3D1"
TEXT_MUTED = "#6B7FA3"
TEXT_ON_ACCENT = NAVY_DEEP

ACCENT = SKY_BLUE
ACCENT_HOVER = SKY_BLUE_HOVER
ACCENT_MUTED = "#1F4A6B"

SUCCESS = "#4ADE80"
SUCCESS_BG = "#123524"
WARNING = "#FBBF24"
WARNING_BG = "#3A2F10"
ERROR = "#F87171"
ERROR_BG = "#3A1518"
INFO = SKY_BLUE
INFO_BG = "#102B3E"

FONT_FAMILY = "Segoe UI"
FONT_FAMILY_MONO = "Consolas"

SPACING_XS = 4
SPACING_SM = 8
SPACING_MD = 16
SPACING_LG = 24
SPACING_XL = 32

RADIUS = 8
RADIUS_SM = 6


def font(size: int = 13, weight: str = "normal", mono: bool = False) -> ctk.CTkFont:
    family = FONT_FAMILY_MONO if mono else FONT_FAMILY
    return ctk.CTkFont(family=family, size=size, weight=weight)


def apply_appearance() -> None:
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")


SEVERITY_COLORS = {
    "info": (INFO, INFO_BG),
    "warning": (WARNING, WARNING_BG),
    "error": (ERROR, ERROR_BG),
    "success": (SUCCESS, SUCCESS_BG),
}
