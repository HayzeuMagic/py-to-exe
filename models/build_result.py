"""Typed data models describing build configuration, progress, and results."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path


class OutputMode(Enum):
    ONE_FILE = "one_file"
    ONE_FOLDER = "one_folder"


class ConsoleMode(Enum):
    CONSOLE = "console"
    WINDOWED = "windowed"


class BuildStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BuildConfig:
    """User-chosen build options, validated before a build starts."""

    project_root: Path
    entry_point: Path
    app_name: str
    output_dir: Path
    output_mode: OutputMode = OutputMode.ONE_FILE
    console_mode: ConsoleMode = ConsoleMode.CONSOLE
    icon_path: Path | None = None
    additional_data: list[tuple[Path, str]] = field(default_factory=list)  # (source, dest_in_bundle)
    hidden_imports: list[str] = field(default_factory=list)
    clean_build: bool = False
    use_upx: bool = False
    debug_logging: bool = False
    interpreter: Path | None = None  # resolved at build time if None


@dataclass
class BuildStage:
    name: str
    started_at: datetime
    finished_at: datetime | None = None


@dataclass
class BuildResult:
    config: BuildConfig
    status: BuildStatus
    started_at: datetime
    finished_at: datetime | None = None
    exit_code: int | None = None
    output_path: Path | None = None  # the exe (one-file) or dist dir (one-folder)
    artifact_size_bytes: int | None = None
    log_path: Path | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    python_version: str = ""
    pyinstaller_version: str = ""

    @property
    def duration_seconds(self) -> float:
        if self.finished_at is None:
            return 0.0
        return (self.finished_at - self.started_at).total_seconds()

    @property
    def succeeded(self) -> bool:
        return self.status == BuildStatus.SUCCESS
