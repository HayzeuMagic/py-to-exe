"""Build engine tests using a fake "PyInstaller" (a short python -c script)
instead of a real packaging run, per the no-real-build-for-unit-tests rule.
"""
import sys
import time
from pathlib import Path

import pytest

from core import build_manager as build_manager_module
from core.build_manager import BuildManager, CompletedEvent, LogEvent, StageEvent
from core.environment_manager import InterpreterInfo
from models.build_result import BuildConfig, BuildStatus, OutputMode


def make_config(tmp_path: Path) -> BuildConfig:
    entry = tmp_path / "main.py"
    entry.write_text("print('hi')", encoding="utf-8")
    return BuildConfig(
        project_root=tmp_path,
        entry_point=entry,
        app_name="MyApp",
        output_dir=tmp_path / "out",
        output_mode=OutputMode.ONE_FILE,
    )


def make_manager(monkeypatch, has_pyinstaller=True) -> BuildManager:
    manager = BuildManager()
    monkeypatch.setattr(
        manager._env_manager, "inspect",
        lambda interpreter: InterpreterInfo(
            path=interpreter, version="Python 3.12.0", has_pyinstaller=has_pyinstaller,
            pyinstaller_version="6.0.0" if has_pyinstaller else None,
        ),
    )
    monkeypatch.setattr(manager._env_manager, "default_interpreter", lambda: Path(sys.executable))
    return manager


def drain_events(manager: BuildManager, timeout=15):
    deadline = time.monotonic() + timeout
    events = []
    while time.monotonic() < deadline:
        try:
            event = manager.event_queue.get(timeout=0.2)
        except Exception:
            continue
        events.append(event)
        if isinstance(event, CompletedEvent):
            break
    return events


def fake_args(script: str):
    def _build(config, work_dir, spec_dir):
        return ["-c", script]
    return _build


def test_successful_build(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    exe_path = config.output_dir / "MyApp.exe"
    script = (
        "import pathlib, sys\n"
        "print('building...')\n"
        f"p = pathlib.Path(r'{exe_path}')\n"
        "p.parent.mkdir(parents=True, exist_ok=True)\n"
        "p.write_bytes(b'fake-exe')\n"
        "print('done', file=sys.stderr)\n"
    )
    manager = make_manager(monkeypatch)
    monkeypatch.setattr(build_manager_module, "build_pyinstaller_args", fake_args(script))

    errors = manager.start(config)
    assert errors == []

    events = drain_events(manager)
    completed = next(e for e in events if isinstance(e, CompletedEvent))

    assert completed.result.status == BuildStatus.SUCCESS
    assert completed.result.output_path == exe_path
    assert any(isinstance(e, LogEvent) for e in events)
    assert not manager.is_running


def test_nonzero_exit_code_fails(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    script = "import sys; print('boom', file=sys.stderr); sys.exit(1)"

    manager = make_manager(monkeypatch)
    monkeypatch.setattr(build_manager_module, "build_pyinstaller_args", fake_args(script))

    manager.start(config)
    events = drain_events(manager)
    completed = next(e for e in events if isinstance(e, CompletedEvent))

    assert completed.result.status == BuildStatus.FAILED
    assert completed.result.exit_code == 1
    assert not manager.is_running


def test_missing_output_artifact_fails_validation(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    script = "print('exits cleanly but makes nothing')"

    manager = make_manager(monkeypatch)
    monkeypatch.setattr(build_manager_module, "build_pyinstaller_args", fake_args(script))

    manager.start(config)
    events = drain_events(manager)
    completed = next(e for e in events if isinstance(e, CompletedEvent))

    assert completed.result.status == BuildStatus.FAILED
    assert completed.result.errors


def test_missing_pyinstaller_fails_fast(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    manager = make_manager(monkeypatch, has_pyinstaller=False)
    monkeypatch.setattr(build_manager_module, "build_pyinstaller_args", fake_args("pass"))

    manager.start(config)
    events = drain_events(manager)
    completed = next(e for e in events if isinstance(e, CompletedEvent))

    assert completed.result.status == BuildStatus.FAILED
    assert "not available" in completed.result.errors[0].lower()


def test_cancellation(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    script = "import time; time.sleep(30)"

    manager = make_manager(monkeypatch)
    monkeypatch.setattr(build_manager_module, "build_pyinstaller_args", fake_args(script))

    manager.start(config)
    time.sleep(0.5)
    manager.cancel()

    events = drain_events(manager, timeout=15)
    completed = next(e for e in events if isinstance(e, CompletedEvent))

    assert completed.result.status == BuildStatus.CANCELLED
    assert not manager.is_running


def test_invalid_config_rejected_before_starting(tmp_path, monkeypatch):
    manager = make_manager(monkeypatch)
    config = make_config(tmp_path)
    config.app_name = "bad/name"

    errors = manager.start(config)

    assert errors
    assert not manager.is_running


def test_concurrent_build_rejected(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    script = "import time; time.sleep(5)"
    manager = make_manager(monkeypatch)
    monkeypatch.setattr(build_manager_module, "build_pyinstaller_args", fake_args(script))

    manager.start(config)
    errors = manager.start(config)

    assert errors
    assert "already in progress" in errors[0].lower()

    manager.cancel()
    drain_events(manager)
