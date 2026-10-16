"""PyForge design system — colors, spacing, and typography.

A light, white-dominant palette with blue accents (sampled from the Rivan
Security Inc Academy logo's sky-blue ring and navy mark).
"""
from __future__ import annotations

import customtkinter as ctk

# -- Core palette (derived from rivan_logo.png) ------------------------------
NAVY = "#0D2152"
SKY_BLUE = "#60D9FE"
WHITE = "#FFFFFF"

# -- Semantic tokens ---------------------------------------------------------
# App canvas: a very light cool-gray-white so white cards still read as
# distinct surfaces, without ever looking "dark."
BG_APP = "#F3F6FB"
BG_SIDEBAR = "#FFFFFF"
BG_PANEL = "#FFFFFF"
BG_PANEL_RAISED = "#F2F6FC"
BG_INPUT = "#F7F9FC"

BORDER = "#D9E2EF"
BORDER_SUBTLE = "#E9EFF7"

TEXT_PRIMARY = NAVY
TEXT_SECONDARY = "#4C5E7A"
TEXT_MUTED = "#8B9AB5"
TEXT_ON_ACCENT = WHITE

# A more saturated blue than the pale logo ring, so it has enough contrast
# to carry white button text — the logo's sky blue is used for lighter
# highlights/washes instead.
ACCENT = "#0EA5E9"
ACCENT_HOVER = "#0B86BD"
ACCENT_MUTED = "#E3F3FC"
ACCENT_WASH = SKY_BLUE

SUCCESS = "#16A34A"
SUCCESS_BG = "#E7F8EE"
WARNING = "#B45309"
WARNING_BG = "#FFF6E3"
ERROR = "#DC2626"
ERROR_BG = "#FDEAEA"
INFO = ACCENT
INFO_BG = "#E7F6FD"

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
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")


SEVERITY_COLORS = {
    "info": (INFO, INFO_BG),
    "warning": (WARNING, WARNING_BG),
    "error": (ERROR, ERROR_BG),
    "success": (SUCCESS, SUCCESS_BG),
}
