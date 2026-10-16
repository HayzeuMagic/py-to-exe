"""Non-destructive, read-only project scanner.

Walks a selected folder and reports what it finds. Never imports, executes,
or modifies anything under the scanned root.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

from models.project import AssetFile, ManifestFile, ProjectStats, ScannedProject
from utils.filesystem import DEFAULT_SCAN_EXCLUDES, MAX_SCAN_DIRECTORIES, MAX_SCAN_FILES
from utils.logging_config import get_logger

logger = get_logger("project_scanner")

_MANIFEST_NAMES = {
    "requirements.txt": "requirements.txt",
    "pyproject.toml": "pyproject.toml",
    "setup.py": "setup.py",
    "setup.cfg": "setup.cfg",
    "Pipfile": "Pipfile",
    "Pipfile.lock": "Pipfile.lock",
    "poetry.lock": "poetry.lock",
}

_ASSET_CATEGORIES: dict[str, tuple[str, ...]] = {
    "image": (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg"),
    "data": (".json", ".csv", ".xml", ".sqlite", ".db", ".yaml", ".yml"),
    "config": (".ini", ".cfg", ".toml", ".env"),
    "template": (".html", ".htm", ".jinja", ".jinja2", ".tpl"),
    "native_library": (".dll", ".pyd", ".so", ".dylib"),
}


def _categorize_asset(path: Path) -> str | None:
    suffix = path.suffix.lower()
    for category, suffixes in _ASSET_CATEGORIES.items():
        if suffix in suffixes:
            return category
    return None


class ProjectScanner:
    """Scans a project folder and builds a :class:`ScannedProject`."""

    def __init__(self, excludes: frozenset[str] | None = None, follow_symlinks: bool = False):
        self.excludes = excludes if excludes is not None else DEFAULT_SCAN_EXCLUDES
        self.follow_symlinks = follow_symlinks

    def scan(self, root: Path) -> ScannedProject:
        root = Path(root)
        result = ScannedProject(root=root)

        if not root.exists():
            result.scan_errors.append(f"Path does not exist: {root}")
            return result
        if not root.is_dir():
            result.scan_errors.append(f"Path is not a directory: {root}")
            return result

        start = time.monotonic()
        dirs_visited = 0
        files_visited = 0
        visited_real_dirs: set[str] = set()

        for current_dir, dirnames, filenames in os.walk(root, followlinks=self.follow_symlinks):
            dirs_visited += 1
            if dirs_visited > MAX_SCAN_DIRECTORIES:
                result.scan_errors.append(
                    f"Scan stopped after {MAX_SCAN_DIRECTORIES} directories "
                    "(project tree is unexpectedly large)."
                )
                break

            current_path = Path(current_dir)

            # Prevent symlink cycles when follow_symlinks is enabled.
            if self.follow_symlinks:
                try:
                    real = str(current_path.resolve())
                except OSError:
                    dirnames[:] = []
                    continue
                if real in visited_real_dirs:
                    dirnames[:] = []
                    continue
                visited_real_dirs.add(real)

            # Prune excluded directories in-place so os.walk doesn't descend.
            dirnames[:] = sorted(
                d for d in dirnames if d not in self.excludes and not self._is_hidden(d)
            )

            for filename in filenames:
                files_visited += 1
                if files_visited > MAX_SCAN_FILES:
                    result.scan_errors.append(
                        f"Scan stopped after {MAX_SCAN_FILES} files "
                        "(project tree is unexpectedly large)."
                    )
                    dirnames[:] = []
                    break

                file_path = current_path / filename
                try:
                    self._classify_file(file_path, result)
                except OSError as exc:
                    # File disappeared mid-scan, permission denied, broken
                    # symlink target, etc. Record and keep going.
                    result.scan_errors.append(f"Could not read {file_path}: {exc}")
                    continue

        result.stats = ProjectStats(
            total_python_files=len(result.python_files),
            total_files=files_visited,
            total_size_bytes=sum(a.size_bytes for a in result.assets),
            directories_scanned=dirs_visited,
            scan_duration_seconds=time.monotonic() - start,
        )
        logger.info(
            "Scanned %s: %d python files, %d manifests, %d assets, %d errors",
            root, len(result.python_files), len(result.manifests),
            len(result.assets), len(result.scan_errors),
        )
        return result

    @staticmethod
    def _is_hidden(dirname: str) -> bool:
        return dirname.startswith(".") and dirname not in (".",)

    def _classify_file(self, file_path: Path, result: ScannedProject) -> None:
        stat = file_path.stat()

        if file_path.suffix.lower() == ".py":
            result.python_files.append(file_path)
            return

        if file_path.name in _MANIFEST_NAMES:
            result.manifests.append(
                ManifestFile(path=file_path, kind=_MANIFEST_NAMES[file_path.name])
            )
            return

        category = _categorize_asset(file_path)
        if category:
            result.assets.append(
                AssetFile(path=file_path, category=category, size_bytes=stat.st_size)
            )
