"""Project selection + overview panel (Builder screen, sections A & B)."""
from __future__ import annotations

from pathlib import Path
from tkinter import filedialog
from typing import Callable

import customtkinter as ctk

from models.project import ScannedProject
from ui import theme
from utils.filesystem import format_bytes


class ProjectPanel(ctk.CTkFrame):
    def __init__(
        self,
        master,
        on_browse: Callable[[Path], None],
        on_rescan: Callable[[], None],
        on_clear: Callable[[], None],
        **kwargs,
    ):
        super().__init__(master, fg_color=theme.BG_PANEL, corner_radius=theme.RADIUS, **kwargs)
        self.on_browse = on_browse
        self.on_rescan = on_rescan
        self.on_clear = on_clear
        self._project: ScannedProject | None = None

        self._build()

    def _build(self) -> None:
        pad = theme.SPACING_MD

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=pad, pady=(pad, theme.SPACING_SM))
        ctk.CTkLabel(header, text="Project", font=theme.font(15, "bold"), text_color=theme.TEXT_PRIMARY).pack(side="left")

        path_row = ctk.CTkFrame(self, fg_color=theme.BG_INPUT, corner_radius=theme.RADIUS_SM)
        path_row.pack(fill="x", padx=pad, pady=(0, theme.SPACING_SM))

        self.path_label = ctk.CTkLabel(
            path_row, text="No folder selected", font=theme.font(12), text_color=theme.TEXT_MUTED,
            anchor="w",
        )
        self.path_label.pack(side="left", fill="x", expand=True, padx=theme.SPACING_SM, pady=theme.SPACING_SM)

        button_row = ctk.CTkFrame(self, fg_color="transparent")
        button_row.pack(fill="x", padx=pad, pady=(0, pad))

        ctk.CTkButton(
            button_row, text="Browse Folder…", font=theme.font(12), fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_HOVER, text_color=theme.TEXT_ON_ACCENT, width=130,
            command=self._browse,
        ).pack(side="left")

        self.rescan_btn = ctk.CTkButton(
            button_row, text="Rescan", font=theme.font(12), fg_color="transparent",
            border_width=1, border_color=theme.BORDER, hover_color=theme.BG_PANEL_RAISED,
            text_color=theme.TEXT_SECONDARY, width=90, state="disabled", command=self.on_rescan,
        )
        self.rescan_btn.pack(side="left", padx=(theme.SPACING_SM, 0))

        self.clear_btn = ctk.CTkButton(
            button_row, text="Clear", font=theme.font(12), fg_color="transparent",
            border_width=1, border_color=theme.BORDER, hover_color=theme.BG_PANEL_RAISED,
            text_color=theme.TEXT_SECONDARY, width=90, state="disabled", command=self._clear,
        )
        self.clear_btn.pack(side="left", padx=(theme.SPACING_SM, 0))

        ctk.CTkFrame(self, fg_color=theme.BORDER_SUBTLE, height=1).pack(fill="x", padx=pad)

        # -- Overview stats grid --
        self.stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.stats_frame.pack(fill="x", padx=pad, pady=pad)
        self._stat_labels: dict[str, ctk.CTkLabel] = {}
        self._build_stats_grid()

    def _build_stats_grid(self) -> None:
        stats = [
            ("python_files", "Python Files"),
            ("entry_points", "Entry Point Candidates"),
            ("manifests", "Dependency Manifests"),
            ("assets", "Asset Files"),
            ("total_size", "Project Size"),
            ("last_scan", "Last Scan"),
        ]
        for col, (key, label) in enumerate(stats):
            cell = ctk.CTkFrame(self.stats_frame, fg_color=theme.BG_PANEL_RAISED, corner_radius=theme.RADIUS_SM)
            cell.grid(row=col // 3, column=col % 3, sticky="nsew", padx=4, pady=4)
            self.stats_frame.grid_columnconfigure(col % 3, weight=1)

            ctk.CTkLabel(cell, text=label, font=theme.font(11), text_color=theme.TEXT_MUTED).pack(
                anchor="w", padx=theme.SPACING_SM, pady=(theme.SPACING_SM, 0)
            )
            value_label = ctk.CTkLabel(cell, text="—", font=theme.font(18, "bold"), text_color=theme.TEXT_PRIMARY)
            value_label.pack(anchor="w", padx=theme.SPACING_SM, pady=(0, theme.SPACING_SM))
            self._stat_labels[key] = value_label

    def _browse(self) -> None:
        folder = filedialog.askdirectory(title="Select Python project folder", mustexist=True)
        if folder:
            self.on_browse(Path(folder))

    def _clear(self) -> None:
        self._project = None
        self.path_label.configure(text="No folder selected", text_color=theme.TEXT_MUTED)
        self.rescan_btn.configure(state="disabled")
        self.clear_btn.configure(state="disabled")
        for label in self._stat_labels.values():
            label.configure(text="—")
        self.on_clear()

    def show_scanning(self, path: Path) -> None:
        self.path_label.configure(text=str(path), text_color=theme.TEXT_PRIMARY)

    def set_project(self, project: ScannedProject, scan_time: str) -> None:
        self._project = project
        self.path_label.configure(text=str(project.root), text_color=theme.TEXT_PRIMARY)
        self.rescan_btn.configure(state="normal")
        self.clear_btn.configure(state="normal")

        self._stat_labels["python_files"].configure(text=str(project.stats.total_python_files))
        self._stat_labels["entry_points"].configure(text=str(len(project.entry_point_candidates)))
        self._stat_labels["manifests"].configure(text=str(len(project.manifests)))
        self._stat_labels["assets"].configure(text=str(len(project.assets)))
        self._stat_labels["total_size"].configure(text=format_bytes(project.stats.total_size_bytes))
        self._stat_labels["last_scan"].configure(text=scan_time)
