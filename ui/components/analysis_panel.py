"""Compatibility analysis panel (Builder screen, section C)."""
from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from core.asset_detector import SuggestedDataMapping
from models.analysis_result import CompatibilityAnalysis, CompatibilityLevel, DependencyAnalysis, Severity
from ui import theme

_LEVEL_DISPLAY = {
    CompatibilityLevel.NO_ISSUES: ("No obvious issues detected", "success", "✓"),
    CompatibilityLevel.CONFIGURATION_RECOMMENDED: ("Configuration recommended", "info", "ℹ"),
    CompatibilityLevel.WARNINGS: ("Warnings detected", "warning", "⚠"),
    CompatibilityLevel.INCOMPLETE: ("Analysis incomplete", "warning", "⚠"),
    CompatibilityLevel.POTENTIALLY_INCOMPATIBLE: ("Potentially incompatible", "error", "✕"),
}

_SEVERITY_ICON = {Severity.INFO: "ℹ", Severity.WARNING: "⚠", Severity.ERROR: "✕"}


class AnalysisPanel(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=theme.BG_PANEL, corner_radius=theme.RADIUS, **kwargs)
        self._build()

    def _build(self) -> None:
        pad = theme.SPACING_MD

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=pad, pady=(pad, theme.SPACING_SM))
        ctk.CTkLabel(header, text="Compatibility Analysis", font=theme.font(15, "bold"), text_color=theme.TEXT_PRIMARY).pack(side="left")

        self.summary_frame = ctk.CTkFrame(self, fg_color=theme.BG_INPUT, corner_radius=theme.RADIUS_SM)
        self.summary_frame.pack(fill="x", padx=pad, pady=(0, theme.SPACING_SM))
        self.summary_icon = ctk.CTkLabel(self.summary_frame, text="—", font=theme.font(16, "bold"), width=28)
        self.summary_icon.pack(side="left", padx=(theme.SPACING_SM, 0), pady=theme.SPACING_SM)
        self.summary_label = ctk.CTkLabel(
            self.summary_frame, text="Run Analyze Project to see results.",
            font=theme.font(13, "bold"), text_color=theme.TEXT_SECONDARY, anchor="w",
        )
        self.summary_label.pack(side="left", fill="x", expand=True, padx=theme.SPACING_SM, pady=theme.SPACING_SM)

        self.caveat_label = ctk.CTkLabel(
            self,
            text="A static scan is not a guarantee this project will package successfully.",
            font=theme.font(11), text_color=theme.TEXT_MUTED, anchor="w",
        )
        self.caveat_label.pack(fill="x", padx=pad, pady=(0, theme.SPACING_SM))

        self.findings_scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.findings_scroll.pack(fill="both", expand=True, padx=pad, pady=(0, pad))

    def show_empty(self) -> None:
        self.summary_icon.configure(text="—", text_color=theme.TEXT_MUTED)
        self.summary_label.configure(text="No project analyzed yet. Select a folder and click Analyze Project.")
        self._clear_findings()

    def show_analysis(
        self,
        compat: CompatibilityAnalysis,
        deps: DependencyAnalysis,
        mappings: list[SuggestedDataMapping] | None = None,
        on_add_mapping: Callable[[SuggestedDataMapping], None] | None = None,
    ) -> None:
        text, kind, icon = _LEVEL_DISPLAY[compat.level]
        color, _bg = theme.SEVERITY_COLORS[kind]
        self.summary_icon.configure(text=icon, text_color=color)
        self.summary_label.configure(text=text, text_color=color)

        self._clear_findings()

        if mappings and on_add_mapping:
            self._add_mapping_suggestions(mappings, on_add_mapping)

        missing = deps.missing_declarations
        if missing:
            names = ", ".join(sorted(d.import_name for d in missing)[:8])
            self._add_finding_card(
                Severity.WARNING,
                "Possibly missing dependency declarations",
                f"These imports were found in source but not in any manifest: {names}.",
                "Add them to requirements.txt, or add as hidden imports if they're "
                "resolved dynamically.",
                None,
            )

        if not compat.findings and not missing:
            self._add_info_row("No additional findings from static analysis.")
            return

        for finding in sorted(compat.findings, key=lambda f: f.severity.value):
            location = ""
            if finding.affected_file is not None:
                location = str(finding.affected_file)
                if finding.line:
                    location += f":{finding.line}"
            self._add_finding_card(finding.severity, finding.message, "", finding.suggestion, location)

    def _add_mapping_suggestions(
        self, mappings: list[SuggestedDataMapping], on_add_mapping: Callable[[SuggestedDataMapping], None]
    ) -> None:
        card = ctk.CTkFrame(self.findings_scroll, fg_color=theme.INFO_BG, corner_radius=theme.RADIUS_SM)
        card.pack(fill="x", pady=4)
        ctk.CTkLabel(
            card, text="Suggested data files to bundle", font=theme.font(12, "bold"), text_color=theme.TEXT_PRIMARY,
            anchor="w",
        ).pack(fill="x", padx=theme.SPACING_SM, pady=(theme.SPACING_SM, 2))
        ctk.CTkLabel(
            card, text="Detected asset files grouped by folder. Add any your program reads at "
                        "runtime (images, templates, config) so PyInstaller bundles them.",
            font=theme.font(11), text_color=theme.TEXT_SECONDARY, anchor="w", wraplength=560, justify="left",
        ).pack(fill="x", padx=theme.SPACING_SM)

        for mapping in mappings:
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=theme.SPACING_SM, pady=2)
            label = f"{mapping.dest_in_bundle}  ({mapping.file_count} {mapping.category} file(s))"
            ctk.CTkLabel(row, text=label, font=theme.font(11, mono=True), text_color=theme.TEXT_PRIMARY, anchor="w").pack(
                side="left", fill="x", expand=True
            )
            ctk.CTkButton(
                row, text="Add to Build", width=90, height=22, font=theme.font(10), fg_color=theme.ACCENT_MUTED,
                text_color=theme.ACCENT, hover_color=theme.ACCENT, command=lambda m=mapping: on_add_mapping(m),
            ).pack(side="right")

        ctk.CTkFrame(card, fg_color="transparent", height=4).pack()

    def _add_info_row(self, text: str) -> None:
        ctk.CTkLabel(
            self.findings_scroll, text=text, font=theme.font(12), text_color=theme.TEXT_MUTED, anchor="w"
        ).pack(fill="x", pady=theme.SPACING_SM)

    def _add_finding_card(self, severity: Severity, title: str, body: str, suggestion: str, location: str | None) -> None:
        color, bg = theme.SEVERITY_COLORS[severity.value]
        card = ctk.CTkFrame(self.findings_scroll, fg_color=bg, corner_radius=theme.RADIUS_SM)
        card.pack(fill="x", pady=4)

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=theme.SPACING_SM, pady=(theme.SPACING_SM, 0))
        ctk.CTkLabel(top, text=_SEVERITY_ICON[severity], text_color=color, font=theme.font(13, "bold"), width=20).pack(side="left")
        ctk.CTkLabel(
            top, text=title, font=theme.font(12, "bold"), text_color=theme.TEXT_PRIMARY,
            anchor="w", justify="left", wraplength=560,
        ).pack(side="left", fill="x", expand=True)

        if body:
            ctk.CTkLabel(
                card, text=body, font=theme.font(11), text_color=theme.TEXT_SECONDARY,
                anchor="w", justify="left", wraplength=560,
            ).pack(fill="x", padx=theme.SPACING_SM, pady=(2, 0))

        if location:
            ctk.CTkLabel(
                card, text=location, font=theme.font(10, mono=True), text_color=theme.TEXT_MUTED, anchor="w",
            ).pack(fill="x", padx=theme.SPACING_SM, pady=(2, 0))

        if suggestion:
            ctk.CTkLabel(
                card, text=f"Suggestion: {suggestion}", font=theme.font(11), text_color=color,
                anchor="w", justify="left", wraplength=560,
            ).pack(fill="x", padx=theme.SPACING_SM, pady=(2, theme.SPACING_SM))

    def _clear_findings(self) -> None:
        for child in self.findings_scroll.winfo_children():
            child.destroy()
