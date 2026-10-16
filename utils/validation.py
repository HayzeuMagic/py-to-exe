"""Shared validation helpers for build configuration and user input."""
from __future__ import annotations

import re
from pathlib import Path

from utils.filesystem import is_safe_filename_component

_VALID_APP_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.\-]{0,99}$")

#: Names Windows reserves; unsafe as an executable base name.
_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


class ValidationError(ValueError):
    """Raised when a build option or user-supplied path fails validation."""


def validate_app_name(name: str) -> str:
    name = name.strip()
    if not name:
        raise ValidationError("Application name cannot be empty.")
    if not _VALID_APP_NAME_RE.match(name):
        raise ValidationError(
            "Application name may only contain letters, numbers, spaces, "
            "dashes, underscores, and periods."
        )
    if name.upper() in _WINDOWS_RESERVED:
        raise ValidationError(f"'{name}' is a reserved Windows name and can't be used.")
    if not is_safe_filename_component(name):
        raise ValidationError("Application name is not a valid file name.")
    return name


def validate_entry_point(entry_point: Path, project_root: Path) -> Path:
    if not entry_point.exists():
        raise ValidationError(f"Entry point does not exist: {entry_point}")
    if entry_point.suffix.lower() != ".py":
        raise ValidationError("Entry point must be a .py file.")
    if not entry_point.is_file():
        raise ValidationError("Entry point must be a file, not a directory.")
    return entry_point


def validate_output_dir(output_dir: Path, project_root: Path) -> Path:
    if str(output_dir).strip() == "":
        raise ValidationError("Output directory cannot be empty.")
    resolved = output_dir.resolve()
    project_resolved = project_root.resolve()
    if resolved == project_resolved:
        raise ValidationError(
            "Output directory cannot be the project root itself — choose a "
            "subfolder or a separate location to avoid mixing build output "
            "with your source files."
        )
    # Refuse building directly into drive roots or similarly dangerous spots.
    if resolved.parent == resolved:
        raise ValidationError("Output directory cannot be a filesystem root.")
    return resolved


def validate_icon_path(icon_path: Path | None) -> Path | None:
    if icon_path is None:
        return None
    if not icon_path.exists():
        raise ValidationError(f"Icon file does not exist: {icon_path}")
    if icon_path.suffix.lower() != ".ico":
        raise ValidationError("Icon must be a .ico file for Windows builds.")
    if icon_path.stat().st_size == 0:
        raise ValidationError("Icon file is empty.")
    return icon_path

def validate_hidden_import(name: str) -> str:
    name = name.strip()
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$", name):
        raise ValidationError(f"'{name}' is not a valid Python module name.")
    return name
