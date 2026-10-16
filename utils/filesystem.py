"""Filesystem helpers shared by the scanner, build engine, and history store.

All helpers here are read-oriented or operate only inside paths PyForge owns
(its own app-data directory, or a build output directory the user explicitly
selected). Nothing in this module touches a user's project source files.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

#: The project root when running from source (three levels up from this
#: file: utils/filesystem.py -> utils -> project root).
_SOURCE_ROOT = Path(__file__).resolve().parent.parent


def resource_path(*parts: str) -> Path:
    """Resolves a path to a bundled resource (e.g. assets/icons/app.ico).

    When PyForge itself is frozen by PyInstaller, bundled data lives under
    sys._MEIPASS rather than next to the source files — using __file__
    directly here would be exactly the packaging mistake PyForge's own
    compatibility analyzer warns projects about.
    """
    base = Path(getattr(sys, "_MEIPASS", _SOURCE_ROOT))
    return base.joinpath(*parts)

#: Directories excluded from project scanning by default.
DEFAULT_SCAN_EXCLUDES: frozenset[str] = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "env",
        ".env",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
        ".idea",
        ".vscode",
        "pyforge_builds",
    }
)

#: Hard ceiling on directories visited during a scan, to protect against
#: unintentionally pointing PyForge at a huge or pathological tree.
MAX_SCAN_DIRECTORIES = 50_000
MAX_SCAN_FILES = 100_000


def app_data_dir() -> Path:
    """Per-user, writable directory for PyForge's own settings/history/logs.

    Never the install directory, never the user's project directory.
    Honors PYFORGE_APP_DATA_DIR when set, so automated tests (and anyone
    who wants an isolated instance) never touch the real user profile.
    """
    override = os.environ.get("PYFORGE_APP_DATA_DIR")
    if override:
        path = Path(override)
        path.mkdir(parents=True, exist_ok=True)
        return path

    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            path = Path(base) / "PyForge"
        else:
            path = Path.home() / "AppData" / "Local" / "PyForge"
    else:
        path = Path.home() / ".pyforge"
    path.mkdir(parents=True, exist_ok=True)
    return path


def app_builds_dir() -> Path:
    """Directory PyForge uses for its own build work directories (not output)."""
    path = app_data_dir() / "build_work"
    path.mkdir(parents=True, exist_ok=True)
    return path


def app_logs_dir() -> Path:
    path = app_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def is_within(child: Path, parent: Path) -> bool:
    """True if `child` resolves to a location inside `parent`."""
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def safe_iter_dir(path: Path):
    """Iterate directory entries, skipping ones that raise OSError."""
    try:
        yield from os.scandir(path)
    except OSError:
        return


def directory_size(path: Path) -> int:
    """Best-effort recursive size of a directory. Ignores unreadable entries."""
    total = 0
    for entry in safe_iter_dir(path):
        try:
            if entry.is_dir(follow_symlinks=False):
                total += directory_size(Path(entry.path))
            elif entry.is_file(follow_symlinks=False):
                total += entry.stat(follow_symlinks=False).st_size
        except OSError:
            continue
    return total


def format_bytes(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def is_safe_filename_component(name: str) -> bool:
    """Reject path-traversal and empty/whitespace-only components."""
    if not name or name.strip() != name:
        return False
    if name in (".", ".."):
        return False
    if any(sep in name for sep in ("/", "\\")):
        return False
    return True
