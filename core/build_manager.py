"""Orchestrates a full build: validate -> resolve environment -> run PyInstaller
-> validate output -> persist report + history.

Runs the actual PyInstaller process in a background thread via
ProcessRunner. UI code should poll `event_queue` (thread-safe) from a
`root.after(...)` loop rather than blocking on the worker thread.
"""
from __future__ import annotations

import hashlib
import queue
import shutil
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from core.build_config import build_pyinstaller_args, validate_build_config
from core.build_report import BuildHistoryStore, save_report
from core.build_validator import BuildValidator
from core.environment_manager import EnvironmentManager
from core.process_runner import OutputLine, ProcessFinished, ProcessRunner
from models.build_result import BuildConfig, BuildResult, BuildStatus
from utils.filesystem import app_builds_dir, app_logs_dir, is_within
from utils.logging_config import get_logger

logger = get_logger("build_manager")


@dataclass(frozen=True)
class StageEvent:
    stage: str


@dataclass(frozen=True)
class LogEvent:
    stream: str
    text: str


@dataclass(frozen=True)
class CompletedEvent:
    result: BuildResult


BuildEvent = StageEvent | LogEvent | CompletedEvent


class BuildManager:
    """Coordinates one build at a time. Create a new instance per build if
    concurrent builds against different projects are ever needed."""

    def __init__(self) -> None:
        self.event_queue: "queue.Queue[BuildEvent]" = queue.Queue()
        self._runner: ProcessRunner | None = None
        self._thread: threading.Thread | None = None
        self._env_manager = EnvironmentManager()
        self._validator = BuildValidator()
        self._history = BuildHistoryStore()
        self._busy = False

    @property
    def is_running(self) -> bool:
        return self._busy

    def work_dir_for(self, config: BuildConfig) -> Path:
        key = hashlib.sha1(str(config.project_root.resolve()).encode("utf-8")).hexdigest()[:12]
        return app_builds_dir() / f"{config.app_name}-{key}"

    def start(self, config: BuildConfig) -> list[str]:
        """Validates and starts a build in a background thread.

        Returns a list of validation errors (empty if the build started).
        """
        if self._busy:
            return ["A build is already in progress. Cancel it or wait for it to finish."]

        errors = validate_build_config(config)
        if errors:
            return errors

        self._busy = True
        self._thread = threading.Thread(target=self._run_build, args=(config,), daemon=True)
        self._thread.start()
        return []

    def cancel(self) -> None:
        if self._runner is not None:
            self._runner.cancel()

    def _run_build(self, config: BuildConfig) -> None:
        started_at = datetime.now()
        result = BuildResult(config=config, status=BuildStatus.RUNNING, started_at=started_at)

        work_dir = self.work_dir_for(config)
        spec_dir = work_dir / "spec"
        log_dir = app_logs_dir() / "builds"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"{started_at:%Y%m%d-%H%M%S}-{config.app_name}.log"
        result.log_path = log_path

        try:
            self.event_queue.put(StageEvent("Preparing build environment"))

            if config.clean_build and work_dir.exists():
                # Only ever delete directories PyForge itself created under
                # its own app-data build-work root.
                if is_within(work_dir, app_builds_dir()):
                    shutil.rmtree(work_dir, ignore_errors=True)
                else:
                    logger.warning("Refusing to clean non-PyForge-owned directory: %s", work_dir)

            work_dir.mkdir(parents=True, exist_ok=True)
            spec_dir.mkdir(parents=True, exist_ok=True)
            config.output_dir.mkdir(parents=True, exist_ok=True)

            interpreter = config.interpreter or self._env_manager.default_interpreter()
            info = self._env_manager.inspect(interpreter)
            result.python_version = info.version
            result.pyinstaller_version = info.pyinstaller_version or "unknown"

            if not info.has_pyinstaller:
                result.status = BuildStatus.FAILED
                result.errors.append(
                    f"PyInstaller is not available for interpreter {interpreter}. "
                    "Install it explicitly (Settings > Build Environment) before building."
                )
                self._finish(result)
                return

            args = build_pyinstaller_args(config, work_dir=work_dir, spec_dir=spec_dir)

            self.event_queue.put(StageEvent("Running PyInstaller"))

            with open(log_path, "w", encoding="utf-8") as log_file:
                self._runner = ProcessRunner()
                self._runner.start([str(interpreter), *args], cwd=config.project_root)

                while True:
                    item = self._runner.output_queue.get()
                    if isinstance(item, OutputLine):
                        log_file.write(f"[{item.stream}] {item.text}\n")
                        log_file.flush()
                        self.event_queue.put(LogEvent(item.stream, item.text))
                        if item.stream == "stderr":
                            lowered = item.text.lower()
                            if "warning" in lowered:
                                result.warnings.append(item.text)
                            elif "error" in lowered:
                                result.errors.append(item.text)
                    elif isinstance(item, ProcessFinished):
                        result.exit_code = item.exit_code
                        result.finished_at = datetime.now()
                        if item.cancelled:
                            result.status = BuildStatus.CANCELLED
                        elif item.exit_code == 0:
                            self.event_queue.put(StageEvent("Validating output"))
                            outcome = self._validator.validate(config)
                            if outcome.ok:
                                result.status = BuildStatus.SUCCESS
                                result.output_path = outcome.output_path
                                result.artifact_size_bytes = outcome.size_bytes
                            else:
                                result.status = BuildStatus.FAILED
                                result.errors.extend(outcome.messages)
                        else:
                            result.status = BuildStatus.FAILED
                            result.errors.append(f"PyInstaller exited with code {item.exit_code}.")
                        break

        except Exception as exc:  # noqa: BLE001 - must not crash the worker thread
            logger.exception("Build failed with an unexpected error")
            result.status = BuildStatus.FAILED
            result.finished_at = datetime.now()
            result.errors.append(f"Unexpected error: {exc}")

        self._finish(result)

    def _finish(self, result: BuildResult) -> None:
        if result.finished_at is None:
            result.finished_at = datetime.now()
        try:
            report_path = save_report(result)
            self._history.add_build(result, report_path=report_path)
        except Exception:  # noqa: BLE001 - history persistence must not hide the real result
            logger.exception("Failed to persist build history/report")

        self._busy = False
        self._runner = None
        self.event_queue.put(CompletedEvent(result))
