"""Static dependency analysis.

Collects imports via AST (never execution), parses manifest files with
dedicated parsers (never by executing setup.py), and cross-references
imports against stdlib, declared requirements, and installed packages.
"""
from __future__ import annotations

import ast
import re
import sys
from importlib import metadata as importlib_metadata
from pathlib import Path

from models.analysis_result import DependencyAnalysis, DependencyFinding
from models.project import ManifestFile
from utils.logging_config import get_logger

logger = get_logger("dependency_analyzer")

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover - only on < 3.11
    import tomli as tomllib  # type: ignore[no-redef]

_STDLIB_NAMES: frozenset[str] = frozenset(sys.stdlib_module_names) | {"__future__"}

#: Import name -> PyPI distribution name, for the common mismatches static
#: analysis can't resolve on its own.
_IMPORT_TO_DISTRIBUTION: dict[str, str] = {
    "PIL": "Pillow",
    "cv2": "opencv-python",
    "yaml": "PyYAML",
    "bs4": "beautifulsoup4",
    "sklearn": "scikit-learn",
    "dotenv": "python-dotenv",
    "dateutil": "python-dateutil",
    "serial": "pyserial",
    "customtkinter": "customtkinter",
    "win32api": "pywin32",
    "win32con": "pywin32",
    "win32gui": "pywin32",
    "wx": "wxPython",
    "Crypto": "pycryptodome",
    "jwt": "PyJWT",
    "OpenSSL": "pyOpenSSL",
    "attr": "attrs",
    "google": "google-api-python-client",
    "docx": "python-docx",
    "pptx": "python-pptx",
    "lxml": "lxml",
    "requests": "requests",
    "numpy": "numpy",
    "pandas": "pandas",
    "flask": "Flask",
    "django": "Django",
}

_REQUIREMENT_NAME_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


class DependencyAnalyzer:
    """Builds a :class:`DependencyAnalysis` for a scanned project."""

    def analyze(self, project_root: Path, python_files: list[Path], manifests: list[ManifestFile]) -> DependencyAnalysis:
        result = DependencyAnalysis()

        local_module_names = self._local_module_names(project_root, python_files)
        import_locations: dict[str, list[Path]] = {}

        for file_path in python_files:
            for name in self._imports_in_file(file_path):
                import_locations.setdefault(name, []).append(file_path)

        for name, locations in sorted(import_locations.items()):
            top_level = name.split(".")[0]
            if top_level in _STDLIB_NAMES:
                result.stdlib_imports.add(top_level)
            elif top_level in local_module_names:
                result.local_imports.add(top_level)
            else:
                result.third_party.append(self._build_finding(top_level, locations))

        for manifest in manifests:
            try:
                self._merge_manifest(manifest, result)
            except Exception as exc:  # noqa: BLE001 - manifest parsing must never crash analysis
                logger.warning("Failed to parse manifest %s: %s", manifest.path, exc)
                result.manifest_parse_errors.append(f"{manifest.path.name}: {exc}")

        declared_lower = {_normalize_dist_name(r) for r in result.declared_requirements}
        updated: list[DependencyFinding] = []
        for finding in result.third_party:
            dist = finding.distribution_name or finding.import_name
            declared = _normalize_dist_name(dist) in declared_lower or _normalize_dist_name(finding.import_name) in declared_lower
            updated.append(
                DependencyFinding(
                    import_name=finding.import_name,
                    distribution_name=finding.distribution_name,
                    declared_in_manifest=declared,
                    installed=finding.installed,
                    source_files=finding.source_files,
                    is_optional=finding.is_optional,
                    note=finding.note,
                )
            )
        result.third_party = updated

        return result

    # -- imports -----------------------------------------------------------

    def _imports_in_file(self, file_path: Path) -> set[str]:
        names: set[str] = set()
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(file_path))
        except (SyntaxError, OSError, UnicodeError) as exc:
            logger.debug("Could not parse %s for imports: %s", file_path, exc)
            return names

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    names.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.level and node.level > 0:
                    continue  # relative import -> local, not third-party
                if node.module:
                    names.add(node.module.split(".")[0])
        return names

    def _local_module_names(self, project_root: Path, python_files: list[Path]) -> set[str]:
        names: set[str] = set()
        for file_path in python_files:
            rel = file_path.relative_to(project_root)
            if file_path.name == "__init__.py":
                if rel.parent != Path("."):
                    names.add(rel.parent.parts[0] if rel.parent.parts else rel.parent.name)
            else:
                names.add(file_path.stem)
            if rel.parts:
                names.add(rel.parts[0].removesuffix(".py"))
        return names

    def _build_finding(self, import_name: str, locations: list[Path]) -> DependencyFinding:
        distribution = _IMPORT_TO_DISTRIBUTION.get(import_name, import_name)
        installed = self._is_installed(distribution, import_name)
        return DependencyFinding(
            import_name=import_name,
            distribution_name=distribution,
            declared_in_manifest=False,
            installed=installed,
            source_files=tuple(locations),
        )

    @staticmethod
    def _is_installed(distribution: str, import_name: str) -> bool | None:
        for candidate in (distribution, import_name):
            try:
                importlib_metadata.distribution(candidate)
                return True
            except importlib_metadata.PackageNotFoundError:
                continue
        return False

    # -- manifests -----------------------------------------------------------

    def _merge_manifest(self, manifest: ManifestFile, result: DependencyAnalysis) -> None:
        if manifest.kind == "requirements.txt":
            result.declared_requirements.extend(self._parse_requirements_txt(manifest.path))
        elif manifest.kind == "pyproject.toml":
            result.declared_requirements.extend(self._parse_pyproject(manifest.path))
        elif manifest.kind == "setup.cfg":
            result.declared_requirements.extend(self._parse_setup_cfg(manifest.path))
        elif manifest.kind == "setup.py":
            # setup.py is untrusted source code and is never executed.
            logger.info("setup.py found at %s; not executed (treated as untrusted).", manifest.path)
        elif manifest.kind == "Pipfile":
            result.declared_requirements.extend(self._parse_pipfile(manifest.path))

    @staticmethod
    def _parse_requirements_txt(path: Path) -> list[str]:
        names: list[str] = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            match = _REQUIREMENT_NAME_RE.match(line)
            if match:
                names.append(match.group(1))
        return names

    @staticmethod
    def _parse_pyproject(path: Path) -> list[str]:
        data = tomllib.loads(path.read_text(encoding="utf-8", errors="replace"))
        names: list[str] = []

        project = data.get("project", {})
        for dep in project.get("dependencies", []):
            match = _REQUIREMENT_NAME_RE.match(dep)
            if match:
                names.append(match.group(1))

        poetry = data.get("tool", {}).get("poetry", {})
        for section in ("dependencies", "dev-dependencies"):
            for name in poetry.get(section, {}):
                if name.lower() != "python":
                    names.append(name)

        return names

    @staticmethod
    def _parse_setup_cfg(path: Path) -> list[str]:
        import configparser

        parser = configparser.ConfigParser()
        parser.read(path, encoding="utf-8")
        names: list[str] = []
        if parser.has_section("options") and parser.has_option("options", "install_requires"):
            raw = parser.get("options", "install_requires")
            for line in raw.splitlines():
                match = _REQUIREMENT_NAME_RE.match(line.strip())
                if match:
                    names.append(match.group(1))
        return names

    @staticmethod
    def _parse_pipfile(path: Path) -> list[str]:
        data = tomllib.loads(path.read_text(encoding="utf-8", errors="replace"))
        names: list[str] = []
        for section in ("packages", "dev-packages"):
            names.extend(data.get(section, {}).keys())
        return names


def _normalize_dist_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()
