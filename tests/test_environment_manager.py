"""Regression tests for the frozen-executable self-relaunch bug: when
PyForge is packaged with PyInstaller, sys.executable is PyForge's own exe,
not a general Python interpreter. Treating it as one would relaunch
PyForge itself, which on startup repeats the same check -- spawning
unbounded new windows.
"""
import sys
from pathlib import Path

import pytest

from core import environment_manager as env_module
from core.environment_manager import EnvironmentError_, EnvironmentManager


def test_default_interpreter_is_sys_executable_when_not_frozen(monkeypatch):
    monkeypatch.setattr(env_module, "is_pyforge_frozen", lambda: False)
    manager = EnvironmentManager()
    assert manager.default_interpreter() == Path(sys.executable)


def test_default_interpreter_never_returns_self_when_frozen(monkeypatch, tmp_path):
    fake_self = tmp_path / "PyForge.exe"
    fake_self.write_bytes(b"fake")
    fake_python = tmp_path / "python.exe"
    fake_python.write_bytes(b"fake")

    monkeypatch.setattr(env_module, "is_pyforge_frozen", lambda: True)
    monkeypatch.setattr(env_module, "_running_executable", lambda: fake_self.resolve())
    monkeypatch.setattr(env_module.shutil, "which", lambda name: str(fake_python) if name == "python" else None)

    manager = EnvironmentManager()
    result = manager.default_interpreter()

    assert result == fake_python.resolve()
    assert result != fake_self.resolve()


def test_default_interpreter_raises_when_frozen_and_no_system_python(monkeypatch, tmp_path):
    fake_self = tmp_path / "PyForge.exe"
    fake_self.write_bytes(b"fake")

    monkeypatch.setattr(env_module, "is_pyforge_frozen", lambda: True)
    monkeypatch.setattr(env_module, "_running_executable", lambda: fake_self.resolve())
    monkeypatch.setattr(env_module.shutil, "which", lambda name: None)

    manager = EnvironmentManager()
    with pytest.raises(EnvironmentError_):
        manager.default_interpreter()


def test_assert_safe_interpreter_refuses_self_when_frozen(monkeypatch, tmp_path):
    fake_self = tmp_path / "PyForge.exe"
    fake_self.write_bytes(b"fake")

    monkeypatch.setattr(env_module, "is_pyforge_frozen", lambda: True)
    monkeypatch.setattr(env_module, "_running_executable", lambda: fake_self.resolve())

    manager = EnvironmentManager()
    with pytest.raises(EnvironmentError_):
        manager.inspect(fake_self)


def test_assert_safe_interpreter_allows_other_interpreter_when_frozen(monkeypatch, tmp_path):
    fake_self = tmp_path / "PyForge.exe"
    fake_self.write_bytes(b"fake")

    monkeypatch.setattr(env_module, "is_pyforge_frozen", lambda: True)
    monkeypatch.setattr(env_module, "_running_executable", lambda: fake_self.resolve())

    manager = EnvironmentManager()
    # Should not raise EnvironmentError_ for a different path (it may still
    # fail to actually run, which inspect() handles separately).
    manager._assert_safe_interpreter(Path(sys.executable))


def test_assert_safe_interpreter_noop_when_not_frozen(monkeypatch, tmp_path):
    fake_self = tmp_path / "PyForge.exe"
    fake_self.write_bytes(b"fake")
    monkeypatch.setattr(env_module, "is_pyforge_frozen", lambda: False)

    manager = EnvironmentManager()
    # Even pointing straight at "self" is fine when not frozen (this is a
    # normal python.exe/script run, not PyForge's own packaged exe).
    manager._assert_safe_interpreter(fake_self)
