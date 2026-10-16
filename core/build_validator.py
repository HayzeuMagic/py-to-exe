"""Post-build verification.

Checks that the artifacts PyInstaller was expected to produce actually
exist and are non-empty. This is NOT proof the executable works at
runtime — only that the build produced the expected files.
"""
from __future__ import annotations

from pathlib import Path

from models.build_result import BuildConfig, OutputMode


class ValidationOutcome:
    def __init__(self, ok: bool, output_path: Path | None, size_bytes: int | None, messages: list[str]):
        self.ok = ok
        self.output_path = output_path
        self.size_bytes = size_bytes
        self.messages = messages


class BuildValidator:
    """Verifies PyInstaller's output after the process exits successfully."""

    def validate(self, config: BuildConfig) -> ValidationOutcome:
        messages: list[str] = []

        if config.output_mode == OutputMode.ONE_FILE:
            exe_path = config.output_dir / f"{config.app_name}.exe"
            if not exe_path.exists():
                return ValidationOutcome(False, None, None, [f"Expected executable not found: {exe_path}"])
            size = exe_path.stat().st_size
            if size == 0:
                return ValidationOutcome(False, exe_path, 0, [f"Executable exists but is empty: {exe_path}"])
            return ValidationOutcome(True, exe_path, size, messages)

        # ONE_FOLDER
        dist_dir = config.output_dir / config.app_name
        exe_path = dist_dir / f"{config.app_name}.exe"
        if not dist_dir.exists():
            return ValidationOutcome(False, None, None, [f"Expected output directory not found: {dist_dir}"])
        if not exe_path.exists():
            return ValidationOutcome(False, dist_dir, None, [f"Expected executable not found inside output folder: {exe_path}"])
        size = exe_path.stat().st_size
        if size == 0:
            return ValidationOutcome(False, dist_dir, 0, [f"Executable exists but is empty: {exe_path}"])
        return ValidationOutcome(True, dist_dir, size, messages)
