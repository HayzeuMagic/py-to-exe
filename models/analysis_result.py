"""Typed data models for dependency + compatibility analysis results."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Severity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class CompatibilityLevel(Enum):
    """Overall summary bucket shown to the user. Never a guarantee."""

    NO_ISSUES = "no_issues_detected"
    CONFIGURATION_RECOMMENDED = "configuration_recommended"
    WARNINGS = "warnings_detected"
    INCOMPLETE = "analysis_incomplete"
    POTENTIALLY_INCOMPATIBLE = "potentially_incompatible"


@dataclass(frozen=True)
class Finding:
    """A single static-analysis observation."""

    severity: Severity
    category: str
    message: str
    suggestion: str
    affected_file: Path | None = None
    line: int | None = None
    is_heuristic: bool = True  # False only for confirmed/verified facts


@dataclass(frozen=True)
class DependencyFinding:
    """One third-party import and what is known about it."""

    import_name: str
    distribution_name: str | None  # best-guess PyPI distribution name
    declared_in_manifest: bool
    installed: bool | None  # None if unknown / not checked
    source_files: tuple[Path, ...] = ()
    is_optional: bool = False
    note: str = ""


@dataclass
class DependencyAnalysis:
    stdlib_imports: set[str] = field(default_factory=set)
    local_imports: set[str] = field(default_factory=set)
    third_party: list[DependencyFinding] = field(default_factory=list)
    declared_requirements: list[str] = field(default_factory=list)
    manifest_parse_errors: list[str] = field(default_factory=list)

    @property
    def missing_declarations(self) -> list[DependencyFinding]:
        return [d for d in self.third_party if not d.declared_in_manifest and not d.is_optional]


@dataclass
class CompatibilityAnalysis:
    level: CompatibilityLevel
    findings: list[Finding] = field(default_factory=list)

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == Severity.ERROR]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == Severity.WARNING]
