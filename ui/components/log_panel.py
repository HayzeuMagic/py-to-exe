"""Build output panel (Builder screen, section F)."""
from __future__ import annotations

import time

import customtkinter as ctk

from models.build_result import BuildResult, BuildStatus
from ui import theme

_STATUS_DISPLAY = {
    BuildStatus.PENDING: ("Idle", theme.TEXT_MUTED),
    BuildStatus.RUNNING: ("Running", theme.ACCENT),
    BuildStatus.SUCCESS: ("Success", theme.SUCCESS),
    BuildStatus.FAILED: ("Failed", theme.ERROR),
    BuildStatus.CANCELLED: ("Cancelled", theme.WARNING),
}


class LogPanel(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=theme.BG_PANEL, corner_radius=theme.RADIUS, **kwargs)
        self._start_time: float | None = None
        self._build()

    def _build(self) -> None:
        pad = theme.SPACING_MD

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=pad, pady=(pad, theme.SPACING_SM))
        ctk.CTkLabel(header, text="Build Output", font=theme.font(15, "bold"), text_color=theme.TEXT_PRIMARY).pack(side="left")

        self.status_badge = ctk.CTkLabel(
            header, text="Idle", font=theme.font(12, "bold"), text_color=theme.TEXT_MUTED,
            fg_color=theme.BG_INPUT, corner_radius=theme.RADIUS_SM, width=90, height=24,
        )
        self.status_badge.pack(side="right")

        info_row = ctk.CTkFrame(self, fg_color="transparent")
        info_row.pack(fill="x", padx=pad, pady=(0, theme.SPACING_SM))
        self.stage_label = ctk.CTkLabel(info_row, text="Stage: —", font=theme.font(12), text_color=theme.TEXT_SECONDARY)
        self.stage_label.pack(side="left")
        self.elapsed_label = ctk.CTkLabel(info_row, text="Elapsed: 0s", font=theme.font(12), text_color=theme.TEXT_SECONDARY)
        self.elapsed_label.pack(side="right")

        self.progress_bar = ctk.CTkProgressBar(self, fg_color=theme.BG_INPUT, progress_color=theme.ACCENT, mode="indeterminate")
        self.progress_bar.pack(fill="x", padx=pad, pady=(0, theme.SPACING_SM))

        self.log_box = ctk.CTkTextbox(
            self, fg_color=theme.BG_INPUT, text_color=theme.TEXT_PRIMARY, font=theme.font(11, mono=True),
            wrap="none",
        )
        self.log_box.pack(fill="both", expand=True, padx=pad, pady=(0, theme.SPACING_SM))
        self.log_box.configure(state="disabled")
        self.log_box.tag_config("stderr", foreground=theme.WARNING)
        self.log_box.tag_config("stdout", foreground=theme.TEXT_SECONDARY)

        self.result_label = ctk.CTkLabel(
            self, text="", font=theme.font(12), text_color=theme.TEXT_SECONDARY, anchor="w", wraplength=600, justify="left"
        )
        self.result_label.pack(fill="x", padx=pad, pady=(0, pad))

    def reset(self) -> None:
        self._start_time = time.monotonic()
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")
        self.stage_label.configure(text="Stage: Starting…")
        self.elapsed_label.configure(text="Elapsed: 0s")
        self.result_label.configure(text="")
        self.set_status(BuildStatus.RUNNING)
        self.progress_bar.configure(mode="indeterminate")
        self.progress_bar.start()

    def set_stage(self, stage: str) -> None:
        self.stage_label.configure(text=f"Stage: {stage}")

    def tick_elapsed(self) -> None:
        if self._start_time is None:
            return
        elapsed = int(time.monotonic() - self._start_time)
        self.elapsed_label.configure(text=f"Elapsed: {elapsed}s")

    def append_log(self, stream: str, text: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text + "\n", stream)
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def set_status(self, status: BuildStatus) -> None:
        text, color = _STATUS_DISPLAY[status]
        self.status_badge.configure(text=text, text_color=color)

    def show_result(self, result: BuildResult) -> None:
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        self.progress_bar.set(1.0 if result.status == BuildStatus.SUCCESS else 0.0)
        self.set_status(result.status)
        self.stage_label.configure(text="Stage: Done")

        if result.status == BuildStatus.SUCCESS:
            self.result_label.configure(
                text=f"Built successfully: {result.output_path}\n"
                     f"PyInstaller build completed and the expected output artifact was verified to exist. "
                     f"This does not confirm the program runs correctly — use 'Run Executable' to test it.",
                text_color=theme.SUCCESS,
            )
        elif result.status == BuildStatus.CANCELLED:
            self.result_label.configure(text="Build was cancelled.", text_color=theme.WARNING)
        else:
            error_text = result.errors[-1] if result.errors else "Build failed. See log above for details."
            self.result_label.configure(text=f"Build failed: {error_text}", text_color=theme.ERROR)
