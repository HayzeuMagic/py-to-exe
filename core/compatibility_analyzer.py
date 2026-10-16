"""Best-effort packaging-compatibility analyzer.

Everything here is a heuristic derived from static source inspection. It
flags *patterns* that commonly cause PyInstaller packaging problems; it
never claims to prove a project will or won't build successfully.
"""
from __future__ import annotations

import ast
from pathlib import Path

from models.analysis_result import CompatibilityAnalysis, CompatibilityLevel, Finding, Severity
from models.project import AssetFile, ManifestFile, ScannedProject
from utils.logging_config import get_logger

logger = get_logger("compatibility_analyzer")

_PLATFORM_ONLY_MODULES = {
    "winreg": "Windows-only module", "win32com": "Windows-only (pywin32)",
    "posix": "POSIX-only module", "fcntl": "POSIX-only module", "grp": "POSIX-only module", "pwd": "POSIX-only module",
}

_SUBPROCESS_FUNCS = {"run", "Popen", "call", "check_call", "check_output"}


class _Visitor(ast.NodeVisitor):
    """Single-pass AST visitor collecting compatibility signals for one file."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.findings: list[Finding] = []

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802 - ast API
        func = node.func
        name = None
        if isinstance(func, ast.Name):
            name = func.id
        elif isinstance(func, ast.Attribute):
            name = func.attr

        if name in ("eval", "exec"):
            self.findings.append(
                Finding(
                    severity=Severity.INFO,
                    category="dynamic_execution",
                    message=f"Uses {name}() — dynamically executed code can hide imports "
                            "that static analysis won't see.",
                    suggestion="If the evaluated code imports third-party packages, add them "
                               "as hidden imports so PyInstaller bundles them.",
                    affected_file=self.file_path,
                    line=node.lineno,
                )
            )
        elif name == "import_module":
            self.findings.append(
                Finding(
                    severity=Severity.WARNING,
                    category="dynamic_import",
                    message="Uses importlib.import_module() for a dynamic import.",
                    suggestion="PyInstaller's static import scan may miss dynamically-named "
                               "modules. Add the target module(s) as hidden imports.",
                    affected_file=self.file_path,
                    line=node.lineno,
                )
            )
        elif name in _SUBPROCESS_FUNCS and isinstance(func, (ast.Attribute, ast.Name)):
            self.findings.append(
                Finding(
                    severity=Severity.INFO,
                    category="subprocess",
                    message=f"Calls subprocess.{name}() — the project launches an external process.",
                    suggestion="Make sure any external executable it depends on is bundled as "
                               "a data file or is expected to already exist on the target machine.",
                    affected_file=self.file_path,
                    line=node.lineno,
                )
            )
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:  # noqa: N802
        if node.attr == "_MEIPASS":
            self.findings.append(
                Finding(
                    severity=Severity.INFO,
                    category="pyinstaller_aware",
                    message="References sys._MEIPASS — already PyInstaller-aware for locating "
                            "bundled data at runtime.",
                    suggestion="No action needed; this is the correct pattern for one-file builds.",
                    affected_file=self.file_path,
                    line=node.lineno,
                    is_heuristic=False,
                )
            )
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:  # noqa: N802
        if node.id == "__file__":
            self.findings.append(
                Finding(
                    severity=Severity.INFO,
                    category="file_path_assumption",
                    message="Uses __file__ to locate resources relative to the script.",
                    suggestion="In a one-file build, __file__ points inside a temporary "
                               "extraction directory, not the original project folder. Prefer "
                               "sys._MEIPASS (when frozen) for bundled data paths.",
                    affected_file=self.file_path,
                    line=node.lineno,
                )
            )
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        for alias in node.names:
            top = alias.name.split(".")[0]
            if top in _PLATFORM_ONLY_MODULES:
                self.findings.append(
                    Finding(
                        severity=Severity.INFO,
                        category="platform_specific",
                        message=f"Imports '{top}' ({_PLATFORM_ONLY_MODULES[top]}).",
                        suggestion="Fine for a Windows-only build target if this matches your "
                                   "deployment platform; otherwise guard the import.",
                        affected_file=self.file_path,
                        line=node.lineno,
                    )
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        if node.level and node.level > 0:
            self.findings.append(
                Finding(
                    severity=Severity.INFO,
                    category="relative_import",
                    message=f"Uses a relative import (level {node.level}).",
                    suggestion="Make sure the package structure is preserved — relative imports "
                               "require the entry point to be run as part of its package.",
                    affected_file=self.file_path,
                    line=node.lineno,
                )
            )
        self.generic_visit(node)


class CompatibilityAnalyzer:
    """Runs static AST + filesystem heuristics and produces a summary level."""

    def analyze(self, project: ScannedProject) -> CompatibilityAnalysis:
        findings: list[Finding] = []
        parse_failures = 0

        for file_path in project.python_files:
            try:
                source = file_path.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(source, filename=str(file_path))
            except (SyntaxError, OSError, UnicodeError) as exc:
                parse_failures += 1
                findings.append(
                    Finding(
                        severity=Severity.WARNING,
                        category="parse_error",
                        message=f"Could not parse this file for analysis: {exc}",
                        suggestion="Fix the syntax error, or be aware this file was not analyzed.",
                        affected_file=file_path,
                        is_heuristic=False,
                    )
                )
                continue

            visitor = _Visitor(file_path)
            visitor.visit(tree)
            findings.extend(visitor.findings)

        findings.extend(self._asset_findings(project.assets))
        findings.extend(self._manifest_findings(project.manifests))

        if not project.entry_point_candidates:
            findings.append(
                Finding(
                    severity=Severity.WARNING,
                    category="entry_point",
                    message="No obvious entry point was detected automatically.",
                    suggestion="Select the correct script to run manually in Build Configuration.",
                    is_heuristic=True,
                )
            )

        level = self._summarize(findings, parse_failures, len(project.python_files))
        return CompatibilityAnalysis(level=level, findings=findings)

    @staticmethod
    def _asset_findings(assets: list[AssetFile]) -> list[Finding]:
        findings = []
        natives = [a for a in assets if a.category == "native_library"]
        if natives:
            findings.append(
                Finding(
                    severity=Severity.WARNING,
                    category="native_library",
                    message=f"Found {len(natives)} native library file(s) (.dll/.pyd/.so) in the project.",
                    suggestion="These usually need to be bundled explicitly as additional data "
                               "files and may be architecture-specific.",
                    is_heuristic=True,
                )
            )
        templates = [a for a in assets if a.category == "template"]
        if templates:
            findings.append(
                Finding(
                    severity=Severity.INFO,
                    category="assets",
                    message=f"Found {len(templates)} template file(s) (e.g. HTML/Jinja).",
                    suggestion="Add the containing folder as additional data so templates are "
                               "available at runtime.",
                    is_heuristic=True,
                )
            )
        return findings

    @staticmethod
    def _manifest_findings(manifests: list[ManifestFile]) -> list[Finding]:
        findings = []
        if not any(m.kind in ("requirements.txt", "pyproject.toml", "Pipfile", "setup.cfg") for m in manifests):
            findings.append(
                Finding(
                    severity=Severity.WARNING,
                    category="missing_manifest",
                    message="No dependency manifest (requirements.txt, pyproject.toml, ...) was found.",
                    suggestion="Dependencies will be inferred from imports only. Consider adding "
                               "a requirements.txt for clarity, or verify all needed packages are "
                               "installed in the build environment.",
                    is_heuristic=True,
                )
            )
        return findings

    @staticmethod
    def _summarize(findings: list[Finding], parse_failures: int, total_py_files: int) -> CompatibilityLevel:
        if total_py_files and parse_failures == total_py_files:
            return CompatibilityLevel.INCOMPLETE
        if parse_failures > 0 and parse_failures >= max(1, total_py_files // 2):
            return CompatibilityLevel.INCOMPLETE

        errors = [f for f in findings if f.severity == Severity.ERROR]
        warnings = [f for f in findings if f.severity == Severity.WARNING]

        if errors:
            return CompatibilityLevel.POTENTIALLY_INCOMPATIBLE
        if len(warnings) >= 4:
            return CompatibilityLevel.WARNINGS
        if warnings:
            return CompatibilityLevel.CONFIGURATION_RECOMMENDED
        return CompatibilityLevel.NO_ISSUES
