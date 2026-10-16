"""Build report generation and persistent build history.

Build metadata is stored in a SQLite database in PyForge's app-data
directory — never inside the user's project folder. Removing a history
entry only removes the database row; it never deletes build artifacts or
logs unless the caller explicitly requests that separately.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path

from models.build_result import BuildResult, BuildStatus
from utils.filesystem import app_data_dir
from utils.logging_config import get_logger

logger = get_logger("build_report")


def reports_dir() -> Path:
    path = app_data_dir() / "reports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _history_db_path() -> Path:
    return app_data_dir() / "history.db"


def generate_report(result: BuildResult) -> dict:
    """Builds a JSON-serializable structured report for one build."""
    return {
        "project_path": str(result.config.project_root),
        "project_name": result.config.project_root.name,
        "entry_point": str(result.config.entry_point),
        "app_name": result.config.app_name,
        "output_mode": result.config.output_mode.value,
        "console_mode": result.config.console_mode.value,
        "status": result.status.value,
        "started_at": result.started_at.isoformat(),
        "finished_at": result.finished_at.isoformat() if result.finished_at else None,
        "duration_seconds": result.duration_seconds,
        "exit_code": result.exit_code,
        "output_path": str(result.output_path) if result.output_path else None,
        "artifact_size_bytes": result.artifact_size_bytes,
        "log_path": str(result.log_path) if result.log_path else None,
        "warnings": result.warnings,
        "errors": result.errors,
        "python_version": result.python_version,
        "pyinstaller_version": result.pyinstaller_version,
        "validation_notes": {
            "static_analysis_completed": True,
            "build_process_succeeded": result.status == BuildStatus.SUCCESS,
            "output_artifact_verified": result.artifact_size_bytes is not None and result.artifact_size_bytes > 0,
            "runtime_behavior_tested": False,
        },
    }


def save_report(result: BuildResult) -> Path:
    report = generate_report(result)
    report_id = uuid.uuid4().hex[:12]
    path = reports_dir() / f"{result.started_at:%Y%m%d-%H%M%S}-{report_id}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return path


class BuildHistoryStore:
    """SQLite-backed store of build history metadata."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or _history_db_path()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS builds (
                    id TEXT PRIMARY KEY,
                    project_path TEXT NOT NULL,
                    project_name TEXT NOT NULL,
                    entry_point TEXT NOT NULL,
                    app_name TEXT NOT NULL,
                    output_mode TEXT NOT NULL,
                    console_mode TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    duration_seconds REAL,
                    output_path TEXT,
                    python_version TEXT,
                    pyinstaller_version TEXT,
                    warnings_json TEXT,
                    log_path TEXT,
                    report_path TEXT
                )
                """
            )
            conn.commit()

    def add_build(self, result: BuildResult, report_path: Path | None = None) -> str:
        build_id = uuid.uuid4().hex
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO builds (
                    id, project_path, project_name, entry_point, app_name,
                    output_mode, console_mode, status, started_at, duration_seconds,
                    output_path, python_version, pyinstaller_version, warnings_json,
                    log_path, report_path
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    build_id,
                    str(result.config.project_root),
                    result.config.project_root.name,
                    str(result.config.entry_point),
                    result.config.app_name,
                    result.config.output_mode.value,
                    result.config.console_mode.value,
                    result.status.value,
                    result.started_at.isoformat(),
                    result.duration_seconds,
                    str(result.output_path) if result.output_path else None,
                    result.python_version,
                    result.pyinstaller_version,
                    json.dumps(result.warnings),
                    str(result.log_path) if result.log_path else None,
                    str(report_path) if report_path else None,
                ),
            )
            conn.commit()
        return build_id

    def list_builds(self, limit: int = 200) -> list[sqlite3.Row]:
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT * FROM builds ORDER BY started_at DESC LIMIT ?", (limit,)
            )
            return cursor.fetchall()

    def get_build(self, build_id: str) -> sqlite3.Row | None:
        with self._connect() as conn:
            cursor = conn.execute("SELECT * FROM builds WHERE id = ?", (build_id,))
            return cursor.fetchone()

    def remove_build(self, build_id: str) -> None:
        """Removes the history entry only. Never deletes build artifacts."""
        with self._connect() as conn:
            conn.execute("DELETE FROM builds WHERE id = ?", (build_id,))
            conn.commit()
