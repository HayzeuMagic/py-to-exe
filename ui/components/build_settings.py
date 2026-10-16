"""Build configuration form (Builder screen, section D)."""
from __future__ import annotations

from pathlib import Path
from tkinter import filedialog
from typing import Callable

import customtkinter as ctk

from models.project import EntryPointCandidate
from ui import theme


class BuildSettingsPanel(ctk.CTkFrame):
    def __init__(self, master, on_change: Callable[[], None] | None = None, **kwargs):
        super().__init__(master, fg_color=theme.BG_PANEL, corner_radius=theme.RADIUS, **kwargs)
        self.on_change = on_change or (lambda: None)
        self.project_root: Path | None = None
        self._entry_candidates: list[EntryPointCandidate] = []
        self.additional_data: list[tuple[Path, str]] = []
        self.hidden_imports: list[str] = []

        self._build()

    def _build(self) -> None:
        pad = theme.SPACING_MD
        ctk.CTkLabel(self, text="Build Configuration", font=theme.font(15, "bold"), text_color=theme.TEXT_PRIMARY).pack(
            anchor="w", padx=pad, pady=(pad, theme.SPACING_SM)
        )

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=pad, pady=(0, pad))

        # Entry point
        self._section_label(scroll, "Entry Point")
        entry_row = ctk.CTkFrame(scroll, fg_color="transparent")
        entry_row.pack(fill="x", pady=(0, theme.SPACING_SM))
        self.entry_point_var = ctk.StringVar(value="")
        self.entry_point_menu = ctk.CTkOptionMenu(
            entry_row, variable=self.entry_point_var, values=["(scan a project first)"],
            fg_color=theme.BG_INPUT, button_color=theme.ACCENT_MUTED, button_hover_color=theme.ACCENT,
            text_color=theme.TEXT_PRIMARY, dropdown_fg_color=theme.BG_PANEL_RAISED,
            command=lambda _=None: self.on_change(),
        )
        self.entry_point_menu.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            entry_row, text="Browse…", width=80, fg_color="transparent", border_width=1,
            border_color=theme.BORDER, text_color=theme.TEXT_SECONDARY, hover_color=theme.BG_PANEL_RAISED,
            command=self._browse_entry_point,
        ).pack(side="left", padx=(theme.SPACING_SM, 0))

        # App name
        self._section_label(scroll, "Application Name")
        self.app_name_entry = ctk.CTkEntry(scroll, fg_color=theme.BG_INPUT, text_color=theme.TEXT_PRIMARY, border_color=theme.BORDER)
        self.app_name_entry.pack(fill="x", pady=(0, theme.SPACING_SM))
        self.app_name_entry.insert(0, "MyApp")

        # Output dir
        self._section_label(scroll, "Output Directory")
        out_row = ctk.CTkFrame(scroll, fg_color="transparent")
        out_row.pack(fill="x", pady=(0, theme.SPACING_SM))
        self.output_dir_entry = ctk.CTkEntry(out_row, fg_color=theme.BG_INPUT, text_color=theme.TEXT_PRIMARY, border_color=theme.BORDER)
        self.output_dir_entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            out_row, text="Browse…", width=80, fg_color="transparent", border_width=1,
            border_color=theme.BORDER, text_color=theme.TEXT_SECONDARY, hover_color=theme.BG_PANEL_RAISED,
            command=self._browse_output_dir,
        ).pack(side="left", padx=(theme.SPACING_SM, 0))

        # Output mode + console mode
        modes_row = ctk.CTkFrame(scroll, fg_color="transparent")
        modes_row.pack(fill="x", pady=(0, theme.SPACING_SM))

        mode_col = ctk.CTkFrame(modes_row, fg_color="transparent")
        mode_col.pack(side="left", fill="x", expand=True)
        self._section_label(mode_col, "Output Mode")
        self.output_mode_var = ctk.StringVar(value="one_file")
        ctk.CTkRadioButton(mode_col, text="One File", variable=self.output_mode_var, value="one_file",
                            fg_color=theme.ACCENT, text_color=theme.TEXT_PRIMARY).pack(anchor="w")
        ctk.CTkRadioButton(mode_col, text="One Folder", variable=self.output_mode_var, value="one_folder",
                            fg_color=theme.ACCENT, text_color=theme.TEXT_PRIMARY).pack(anchor="w")

        console_col = ctk.CTkFrame(modes_row, fg_color="transparent")
        console_col.pack(side="left", fill="x", expand=True)
        self._section_label(console_col, "Console Mode")
        self.console_mode_var = ctk.StringVar(value="console")
        ctk.CTkRadioButton(console_col, text="Console", variable=self.console_mode_var, value="console",
                            fg_color=theme.ACCENT, text_color=theme.TEXT_PRIMARY).pack(anchor="w")
        ctk.CTkRadioButton(console_col, text="Windowed", variable=self.console_mode_var, value="windowed",
                            fg_color=theme.ACCENT, text_color=theme.TEXT_PRIMARY,
                            command=self._on_console_mode_change).pack(anchor="w")

        self.windowed_hint = ctk.CTkLabel(
            scroll, text="", font=theme.font(10), text_color=theme.WARNING, anchor="w", wraplength=480, justify="left"
        )
        self.windowed_hint.pack(fill="x", pady=(0, theme.SPACING_SM))

        # Icon
        self._section_label(scroll, "Application Icon (.ico, optional)")
        icon_row = ctk.CTkFrame(scroll, fg_color="transparent")
        icon_row.pack(fill="x", pady=(0, theme.SPACING_SM))
        self.icon_entry = ctk.CTkEntry(icon_row, fg_color=theme.BG_INPUT, text_color=theme.TEXT_PRIMARY, border_color=theme.BORDER)
        self.icon_entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            icon_row, text="Browse…", width=80, fg_color="transparent", border_width=1,
            border_color=theme.BORDER, text_color=theme.TEXT_SECONDARY, hover_color=theme.BG_PANEL_RAISED,
            command=self._browse_icon,
        ).pack(side="left", padx=(theme.SPACING_SM, 0))

        # Hidden imports
        self._section_label(scroll, "Hidden Imports (optional)")
        hidden_row = ctk.CTkFrame(scroll, fg_color="transparent")
        hidden_row.pack(fill="x", pady=(0, 4))
        self.hidden_import_entry = ctk.CTkEntry(hidden_row, fg_color=theme.BG_INPUT, text_color=theme.TEXT_PRIMARY,
                                                  border_color=theme.BORDER, placeholder_text="e.g. my_plugin.module")
        self.hidden_import_entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            hidden_row, text="Add", width=60, fg_color=theme.ACCENT_MUTED, text_color=theme.ACCENT,
            hover_color=theme.ACCENT, command=self._add_hidden_import,
        ).pack(side="left", padx=(theme.SPACING_SM, 0))
        self.hidden_imports_list = ctk.CTkFrame(scroll, fg_color="transparent")
        self.hidden_imports_list.pack(fill="x", pady=(0, theme.SPACING_SM))

        # Additional data
        self._section_label(scroll, "Additional Files / Directories (optional)")
        ctk.CTkButton(
            scroll, text="Add Data File or Folder…", fg_color="transparent", border_width=1,
            border_color=theme.BORDER, text_color=theme.TEXT_SECONDARY, hover_color=theme.BG_PANEL_RAISED,
            command=self._add_data_file, anchor="w",
        ).pack(fill="x", pady=(0, 4))
        self.additional_data_list = ctk.CTkFrame(scroll, fg_color="transparent")
        self.additional_data_list.pack(fill="x", pady=(0, theme.SPACING_SM))

        # Advanced toggles
        self._section_label(scroll, "Advanced")
        self.clean_build_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(scroll, text="Clean build (remove previous PyInstaller work files)",
                         variable=self.clean_build_var, fg_color=theme.ACCENT, text_color=theme.TEXT_PRIMARY).pack(anchor="w", pady=2)
        self.upx_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(scroll, text="Use UPX compression (if available)",
                         variable=self.upx_var, fg_color=theme.ACCENT, text_color=theme.TEXT_PRIMARY).pack(anchor="w", pady=2)
        self.debug_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(scroll, text="Verbose/debug build logging",
                         variable=self.debug_var, fg_color=theme.ACCENT, text_color=theme.TEXT_PRIMARY).pack(anchor="w", pady=2)

    def _section_label(self, parent, text: str) -> None:
        ctk.CTkLabel(parent, text=text, font=theme.font(11, "bold"), text_color=theme.TEXT_SECONDARY, anchor="w").pack(
            fill="x", pady=(theme.SPACING_SM, 2)
        )

    def _on_console_mode_change(self) -> None:
        if self.console_mode_var.get() == "windowed":
            self.windowed_hint.configure(
                text="Windowed mode suppresses console output. If this app prints to the "
                     "terminal or needs user input there, use Console mode instead for easier debugging."
            )
        else:
            self.windowed_hint.configure(text="")

    def _browse_entry_point(self) -> None:
        initial = str(self.project_root) if self.project_root else None
        path = filedialog.askopenfilename(title="Select entry-point Python file", filetypes=[("Python files", "*.py")], initialdir=initial)
        if path:
            self._set_entry_point_value(Path(path))

    def _browse_output_dir(self) -> None:
        folder = filedialog.askdirectory(title="Select output directory")
        if folder:
            self.output_dir_entry.delete(0, "end")
            self.output_dir_entry.insert(0, folder)
            self.on_change()

    def _browse_icon(self) -> None:
        path = filedialog.askopenfilename(title="Select .ico icon", filetypes=[("Icon files", "*.ico")])
        if path:
            self.icon_entry.delete(0, "end")
            self.icon_entry.insert(0, path)
            self.on_change()

    def _add_hidden_import(self) -> None:
        name = self.hidden_import_entry.get().strip()
        if not name or name in self.hidden_imports:
            return
        self.hidden_imports.append(name)
        self.hidden_import_entry.delete(0, "end")
        self._refresh_hidden_imports()
        self.on_change()

    def _refresh_hidden_imports(self) -> None:
        for child in self.hidden_imports_list.winfo_children():
            child.destroy()
        for name in self.hidden_imports:
            row = ctk.CTkFrame(self.hidden_imports_list, fg_color=theme.BG_INPUT, corner_radius=theme.RADIUS_SM)
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=name, font=theme.font(11, mono=True), text_color=theme.TEXT_PRIMARY).pack(
                side="left", padx=theme.SPACING_SM, pady=4
            )
            ctk.CTkButton(
                row, text="Remove", width=60, height=22, fg_color="transparent", text_color=theme.ERROR,
                hover_color=theme.ERROR_BG, command=lambda n=name: self._remove_hidden_import(n),
            ).pack(side="right", padx=4, pady=2)

    def _remove_hidden_import(self, name: str) -> None:
        self.hidden_imports = [n for n in self.hidden_imports if n != name]
        self._refresh_hidden_imports()
        self.on_change()

    def _add_data_file(self) -> None:
        path = filedialog.askopenfilename(title="Select a file to bundle") or filedialog.askdirectory(title="Or select a folder to bundle")
        if not path:
            return
        source = Path(path)
        dest = source.name if source.is_file() else "."
        self.additional_data.append((source, dest))
        self._refresh_additional_data()
        self.on_change()

    def _refresh_additional_data(self) -> None:
        for child in self.additional_data_list.winfo_children():
            child.destroy()
        for source, dest in self.additional_data:
            row = ctk.CTkFrame(self.additional_data_list, fg_color=theme.BG_INPUT, corner_radius=theme.RADIUS_SM)
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=f"{source.name} → {dest}", font=theme.font(11), text_color=theme.TEXT_PRIMARY).pack(
                side="left", padx=theme.SPACING_SM, pady=4
            )
            ctk.CTkButton(
                row, text="Remove", width=60, height=22, fg_color="transparent", text_color=theme.ERROR,
                hover_color=theme.ERROR_BG, command=lambda s=source: self._remove_data(s),
            ).pack(side="right", padx=4, pady=2)

    def _remove_data(self, source: Path) -> None:
        self.additional_data = [(s, d) for s, d in self.additional_data if s != source]
        self._refresh_additional_data()
        self.on_change()

    def add_data_mapping(self, source: Path, dest: str) -> None:
        """Adds a bundle mapping programmatically (e.g. from a suggestion)."""
        if any(s == source for s, _d in self.additional_data):
            return
        self.additional_data.append((source, dest))
        self._refresh_additional_data()
        self.on_change()

    # -- external API ---------------------------------------------------------

    def set_project_root(self, root: Path) -> None:
        self.project_root = root
        if not self.output_dir_entry.get().strip():
            self.output_dir_entry.insert(0, str(root / "pyforge_output"))
        self.app_name_entry.delete(0, "end")
        self.app_name_entry.insert(0, root.name or "MyApp")

    def set_entry_candidates(self, candidates: list[EntryPointCandidate], project_root: Path) -> None:
        self._entry_candidates = candidates
        values = [str(c.path.relative_to(project_root)) for c in candidates]
        if not values:
            values = ["(no candidates found — Browse to select manually)"]
            self.entry_point_menu.configure(values=values, state="disabled")
        else:
            self.entry_point_menu.configure(values=values, state="normal")
            self.entry_point_var.set(values[0])

    def _set_entry_point_value(self, path: Path) -> None:
        if self.project_root and path.is_relative_to(self.project_root):
            display = str(path.relative_to(self.project_root))
        else:
            display = str(path)
        current_values = list(self.entry_point_menu.cget("values"))
        if display not in current_values:
            current_values.append(display)
            self.entry_point_menu.configure(values=current_values, state="normal")
        self.entry_point_var.set(display)
        self.on_change()

    def get_entry_point_path(self) -> Path | None:
        value = self.entry_point_var.get()
        if not value or value.startswith("("):
            return None
        if self.project_root is None:
            return None
        candidate = self.project_root / value
        if candidate.exists():
            return candidate
        return Path(value) if Path(value).exists() else None

    def get_app_name(self) -> str:
        return self.app_name_entry.get().strip()

    def get_output_dir(self) -> Path | None:
        value = self.output_dir_entry.get().strip()
        return Path(value) if value else None

    def get_icon_path(self) -> Path | None:
        value = self.icon_entry.get().strip()
        return Path(value) if value else None
