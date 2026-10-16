"""Typed data models describing a scanned Python project."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class EntryPointConfidence(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class EntryPointCandidate:
    path: Path
    confidence: EntryPointConfidence
    reasons: tuple[str, ...]

    @property
    def display_name(self) -> str:
        return self.path.name


@dataclass(frozen=True)
class ManifestFile:
    path: Path
    kind: str  # "requirements.txt", "pyproject.toml", "setup.py", "setup.cfg", "Pipfile", ...


@dataclass(frozen=True)
class AssetFile:
    path: Path
    category: str  # "image", "data", "config", "template", "native_library", "other"
    size_bytes: int


@dataclass
class ProjectStats:
    total_python_files: int = 0
    total_files: int = 0
    total_size_bytes: int = 0
    directories_scanned: int = 0
    scan_duration_seconds: float = 0.0


@dataclass
class ScannedProject:
    """The result of scanning a folder: files, manifests, assets, stats."""

    root: Path
    python_files: list[Path] = field(default_factory=list)
    manifests: list[ManifestFile] = field(default_factory=list)
    assets: list[AssetFile] = field(default_factory=list)
    entry_point_candidates: list[EntryPointCandidate] = field(default_factory=list)
    stats: ProjectStats = field(default_factory=ProjectStats)
    scan_errors: list[str] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.root.name or str(self.root)
