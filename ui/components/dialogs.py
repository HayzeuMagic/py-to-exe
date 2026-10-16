"""Reusable modal dialogs."""
from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from ui import theme


class ConfirmDialog(ctk.CTkToplevel):
    """A modal confirm/cancel dialog. Call `ConfirmDialog.ask(...)` for a blocking helper."""

    def __init__(
        self,
        master,
        title: str,
        message: str,
        confirm_text: str = "Confirm",
        cancel_text: str = "Cancel",
        danger: bool = False,
    ):
        super().__init__(master)
        self.title(title)
        self.configure(fg_color=theme.BG_PANEL)
        self.geometry("420x220")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        self.result = False

        ctk.CTkLabel(
            self, text=title, font=theme.font(16, "bold"), text_color=theme.TEXT_PRIMARY
        ).pack(padx=theme.SPACING_LG, pady=(theme.SPACING_LG, theme.SPACING_SM), anchor="w")

        ctk.CTkLabel(
            self, text=message, font=theme.font(13), text_color=theme.TEXT_SECONDARY,
            wraplength=360, justify="left",
        ).pack(padx=theme.SPACING_LG, pady=(0, theme.SPACING_MD), anchor="w")

        button_row = ctk.CTkFrame(self, fg_color="transparent")
        button_row.pack(side="bottom", fill="x", padx=theme.SPACING_LG, pady=theme.SPACING_LG)

        ctk.CTkButton(
            button_row, text=cancel_text, fg_color="transparent", border_width=1,
            border_color=theme.BORDER, hover_color=theme.BG_PANEL_RAISED,
            text_color=theme.TEXT_SECONDARY, command=self._cancel,
        ).pack(side="right", padx=(theme.SPACING_SM, 0))

        ctk.CTkButton(
            button_row, text=confirm_text,
            fg_color=theme.ERROR if danger else theme.ACCENT,
            hover_color="#B91C1C" if danger else theme.ACCENT_HOVER,
            text_color=theme.WHITE if danger else theme.TEXT_ON_ACCENT,
            command=self._confirm,
        ).pack(side="right")

        self.protocol("WM_DELETE_WINDOW", self._cancel)

    def _confirm(self) -> None:
        self.result = True
        self.destroy()

    def _cancel(self) -> None:
        self.result = False
        self.destroy()

    @staticmethod
    def ask(master, title: str, message: str, confirm_text="Confirm", cancel_text="Cancel", danger=False) -> bool:
        dialog = ConfirmDialog(master, title, message, confirm_text, cancel_text, danger)
        master.wait_window(dialog)
        return dialog.result


class AlertDialog(ctk.CTkToplevel):
    def __init__(self, master, title: str, message: str, kind: str = "info"):
        super().__init__(master)
        self.title(title)
        self.configure(fg_color=theme.BG_PANEL)
        self.geometry("420x200")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        accent, _ = theme.SEVERITY_COLORS.get(kind, theme.SEVERITY_COLORS["info"])

        ctk.CTkLabel(
            self, text=title, font=theme.font(16, "bold"), text_color=accent
        ).pack(padx=theme.SPACING_LG, pady=(theme.SPACING_LG, theme.SPACING_SM), anchor="w")

        ctk.CTkLabel(
            self, text=message, font=theme.font(13), text_color=theme.TEXT_SECONDARY,
            wraplength=360, justify="left",
        ).pack(padx=theme.SPACING_LG, pady=(0, theme.SPACING_MD), anchor="w")

        ctk.CTkButton(
            self, text="OK", fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
            text_color=theme.TEXT_ON_ACCENT, command=self.destroy,
        ).pack(side="bottom", pady=theme.SPACING_LG)

        self.protocol("WM_DELETE_WINDOW", self.destroy)

    @staticmethod
    def show(master, title: str, message: str, kind: str = "info") -> None:
        dialog = AlertDialog(master, title, message, kind)
        master.wait_window(dialog)
