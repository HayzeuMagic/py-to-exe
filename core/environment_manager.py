"""Manages the Python interpreter/environment used to run PyInstaller builds.

PyForge never silently installs third-party packages. Dependency
installation only happens when explicitly triggered by the user (via
`install_requirements`), and always into a project-specific virtual
environment — never into PyForge's own interpreter.

Complete isolation cannot be fully guaranteed on Windows: pip itself may
execute build backends / setup.py for packages without wheels, and that is
inherent to installing arbitrary third-party packages. This is documented
to the user rather than hidden.
"""
from __future__ import annotations

import subprocess
import sys
import venv
from dataclasses import dataclass
from pathlib import Path

from utils.filesystem import app_data_dir
from utils.logging_config import get_logger

logger = get_logger("environment_manager")


@dataclass(frozen=True)
class InterpreterInfo:
    path: Path
    version: str
    has_pyinstaller: bool
    pyinstaller_version: str | None


class EnvironmentError_(RuntimeError):
    """Raised for interpreter/environment problems (named to avoid shadowing builtins)."""


class EnvironmentManager:
    """Resolves and inspects the Python interpreter used for a build."""

    def default_interpreter(self) -> Path:
        """The interpreter running PyForge itself (used unless overridden)."""
        return Path(sys.executable)

    def project_venv_dir(self, project_root: Path) -> Path:
        """A PyForge-owned venv directory keyed by the project's path hash."""
        import hashlib

        key = hashlib.sha1(str(project_root.resolve()).encode("utf-8")).hexdigest()[:12]
        return app_data_dir() / "envs" / f"{project_root.name}-{key}"

    def inspect(self, interpreter: Path) -> InterpreterInfo:
        version = self._run_capture(interpreter, ["--version"])
        has_pyi, pyi_version = self._check_pyinstaller(interpreter)
        return InterpreterInfo(
            path=interpreter,
            version=version.strip(),
            has_pyinstaller=has_pyi,
            pyinstaller_version=pyi_version,
        )

    def create_project_venv(self, project_root: Path) -> Path:
        """Creates (if needed) an isolated venv for this project. Does not install anything."""
        venv_dir = self.project_venv_dir(project_root)
        python_exe = venv_dir / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        if not python_exe.exists():
            logger.info("Creating project virtual environment at %s", venv_dir)
            builder = venv.EnvBuilder(with_pip=True, upgrade_deps=False)
            builder.create(venv_dir)
        return python_exe

    def install_requirements(self, interpreter: Path, requirement_specs: list[str]) -> tuple[bool, str]:
        """Explicit, user-triggered install of packages into `interpreter`'s environment.

        Never called automatically. Installing a third-party package can run
        that package's own build/setup code; the caller is expected to have
        already warned the user about this before invoking.
        """
        if not requirement_specs:
            return True, "No requirements to install."
        args = [str(interpreter), "-m", "pip", "install", *requirement_specs]
        try:
            proc = subprocess.run(args, capture_output=True, text=True, timeout=900)
        except subprocess.TimeoutExpired:
            return False, "Dependency installation timed out after 15 minutes."
        ok = proc.returncode == 0
        output = proc.stdout + "\n" + proc.stderr
        return ok, output

    def ensure_pyinstaller(self, interpreter: Path) -> tuple[bool, str]:
        """Explicit, user-triggered install of PyInstaller itself into `interpreter`."""
        return self.install_requirements(interpreter, ["pyinstaller>=6.10.0"])

    # -- internals -----------------------------------------------------------

    @staticmethod
    def _run_capture(interpreter: Path, args: list[str]) -> str:
        try:
            proc = subprocess.run(
                [str(interpreter), *args], capture_output=True, text=True, timeout=30
            )
            return proc.stdout or proc.stderr
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise EnvironmentError_(f"Could not run interpreter {interpreter}: {exc}") from exc

    @staticmethod
    def _check_pyinstaller(interpreter: Path) -> tuple[bool, str | None]:
        try:
            proc = subprocess.run(
                [str(interpreter), "-m", "PyInstaller", "--version"],
                capture_output=True, text=True, timeout=30,
            )
            if proc.returncode == 0:
                return True, proc.stdout.strip()
            return False, None
        except (OSError, subprocess.TimeoutExpired):
            return False, None
