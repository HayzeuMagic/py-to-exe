"""Validates a BuildConfig and turns it into a PyInstaller argument list."""
from __future__ import annotations

from pathlib import Path

from models.build_result import BuildConfig, ConsoleMode, OutputMode
from utils.validation import (
    ValidationError,
    validate_app_name,
    validate_entry_point,
    validate_hidden_import,
    validate_icon_path,
    validate_output_dir,
)


def validate_build_config(config: BuildConfig) -> list[str]:
    """Returns a list of validation error messages (empty = valid)."""
    errors: list[str] = []

    try:
        validate_app_name(config.app_name)
    except ValidationError as exc:
        errors.append(str(exc))

    try:
        validate_entry_point(config.entry_point, config.project_root)
    except ValidationError as exc:
        errors.append(str(exc))

    try:
        validate_output_dir(config.output_dir, config.project_root)
    except ValidationError as exc:
        errors.append(str(exc))

    try:
        validate_icon_path(config.icon_path)
    except ValidationError as exc:
        errors.append(str(exc))

    for name in config.hidden_imports:
        try:
            validate_hidden_import(name)
        except ValidationError as exc:
            errors.append(str(exc))

    for source, _dest in config.additional_data:
        if not source.exists():
            errors.append(f"Additional data source does not exist: {source}")

    return errors


def build_pyinstaller_args(config: BuildConfig, work_dir: Path, spec_dir: Path) -> list[str]:
    """Builds the `python -m PyInstaller ...` argument list (minus the interpreter)."""
    args: list[str] = ["-m", "PyInstaller", str(config.entry_point)]

    args += ["--name", config.app_name]
    args += ["--distpath", str(config.output_dir)]
    args += ["--workpath", str(work_dir)]
    args += ["--specpath", str(spec_dir)]
    args += ["--noconfirm"]

    args.append("--onefile" if config.output_mode == OutputMode.ONE_FILE else "--onedir")
    args.append("--console" if config.console_mode == ConsoleMode.CONSOLE else "--windowed")

    if config.icon_path is not None:
        args += ["--icon", str(config.icon_path)]

    for source, dest in config.additional_data:
        # PyInstaller's --add-data separator is OS-specific; ';' on Windows.
        args += ["--add-data", f"{source}{';'}{dest}"]

    for name in config.hidden_imports:
        args += ["--hidden-import", name]

    if config.clean_build:
        args.append("--clean")

    if not config.use_upx:
        args.append("--noupx")

    if config.debug_logging:
        args += ["--log-level", "DEBUG"]
    else:
        args += ["--log-level", "INFO"]

    return args
