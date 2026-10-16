from pathlib import Path

import pytest

from core.build_config import build_pyinstaller_args, validate_build_config
from models.build_result import BuildConfig, ConsoleMode, OutputMode


def make_config(tmp_path: Path, **overrides) -> BuildConfig:
    entry = tmp_path / "main.py"
    entry.write_text("print('hi')", encoding="utf-8")
    defaults = dict(
        project_root=tmp_path,
        entry_point=entry,
        app_name="MyApp",
        output_dir=tmp_path / "out",
    )
    defaults.update(overrides)
    return BuildConfig(**defaults)


def test_valid_config_has_no_errors(tmp_path: Path):
    config = make_config(tmp_path)
    assert validate_build_config(config) == []


def test_invalid_output_dir_equal_to_project_root(tmp_path: Path):
    config = make_config(tmp_path, output_dir=tmp_path)
    errors = validate_build_config(config)
    assert any("output directory" in e.lower() for e in errors)


def test_invalid_entry_point_missing(tmp_path: Path):
    config = make_config(tmp_path, entry_point=tmp_path / "missing.py")
    errors = validate_build_config(config)
    assert any("does not exist" in e for e in errors)


def test_invalid_app_name_with_bad_chars(tmp_path: Path):
    config = make_config(tmp_path, app_name="bad/name")
    errors = validate_build_config(config)
    assert errors


def test_invalid_icon_wrong_extension(tmp_path: Path):
    icon = tmp_path / "icon.png"
    icon.write_bytes(b"fake")
    config = make_config(tmp_path, icon_path=icon)
    errors = validate_build_config(config)
    assert any("icon" in e.lower() for e in errors)


def test_valid_icon(tmp_path: Path):
    icon = tmp_path / "icon.ico"
    icon.write_bytes(b"fake-ico-bytes")
    config = make_config(tmp_path, icon_path=icon)
    assert validate_build_config(config) == []


def test_missing_additional_data_source(tmp_path: Path):
    config = make_config(tmp_path, additional_data=[(tmp_path / "nope.txt", ".")])
    errors = validate_build_config(config)
    assert any("does not exist" in e for e in errors)


def test_one_file_args(tmp_path: Path):
    config = make_config(tmp_path, output_mode=OutputMode.ONE_FILE, console_mode=ConsoleMode.CONSOLE)
    args = build_pyinstaller_args(config, work_dir=tmp_path / "work", spec_dir=tmp_path / "spec")
    assert "--onefile" in args
    assert "--console" in args


def test_one_folder_windowed_args(tmp_path: Path):
    config = make_config(tmp_path, output_mode=OutputMode.ONE_FOLDER, console_mode=ConsoleMode.WINDOWED)
    args = build_pyinstaller_args(config, work_dir=tmp_path / "work", spec_dir=tmp_path / "spec")
    assert "--onedir" in args
    assert "--windowed" in args


def test_hidden_imports_in_args(tmp_path: Path):
    config = make_config(tmp_path, hidden_imports=["pkg.module"])
    args = build_pyinstaller_args(config, work_dir=tmp_path / "work", spec_dir=tmp_path / "spec")
    assert "--hidden-import" in args
    assert "pkg.module" in args


def test_unsafe_app_name_rejected(tmp_path: Path):
    config = make_config(tmp_path, app_name="CON")
    errors = validate_build_config(config)
    assert errors  # Windows-reserved name
