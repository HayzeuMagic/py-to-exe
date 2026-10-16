from pathlib import Path

from core.build_validator import BuildValidator
from models.build_result import BuildConfig, OutputMode


def make_config(tmp_path: Path, mode: OutputMode) -> BuildConfig:
    entry = tmp_path / "main.py"
    entry.write_text("print(1)", encoding="utf-8")
    return BuildConfig(
        project_root=tmp_path,
        entry_point=entry,
        app_name="MyApp",
        output_dir=tmp_path / "out",
        output_mode=mode,
    )


def test_one_file_success(tmp_path: Path):
    config = make_config(tmp_path, OutputMode.ONE_FILE)
    config.output_dir.mkdir(parents=True)
    (config.output_dir / "MyApp.exe").write_bytes(b"fake-exe-bytes")

    outcome = BuildValidator().validate(config)

    assert outcome.ok
    assert outcome.size_bytes == len(b"fake-exe-bytes")


def test_one_file_missing_executable(tmp_path: Path):
    config = make_config(tmp_path, OutputMode.ONE_FILE)
    config.output_dir.mkdir(parents=True)

    outcome = BuildValidator().validate(config)

    assert not outcome.ok
    assert "not found" in outcome.messages[0].lower()


def test_one_file_empty_executable(tmp_path: Path):
    config = make_config(tmp_path, OutputMode.ONE_FILE)
    config.output_dir.mkdir(parents=True)
    (config.output_dir / "MyApp.exe").touch()

    outcome = BuildValidator().validate(config)

    assert not outcome.ok
    assert outcome.size_bytes == 0


def test_one_folder_success(tmp_path: Path):
    config = make_config(tmp_path, OutputMode.ONE_FOLDER)
    dist_dir = config.output_dir / "MyApp"
    dist_dir.mkdir(parents=True)
    (dist_dir / "MyApp.exe").write_bytes(b"fake-exe-bytes")

    outcome = BuildValidator().validate(config)

    assert outcome.ok
    assert outcome.output_path == dist_dir


def test_one_folder_missing_dir(tmp_path: Path):
    config = make_config(tmp_path, OutputMode.ONE_FOLDER)
    config.output_dir.mkdir(parents=True)

    outcome = BuildValidator().validate(config)

    assert not outcome.ok


def test_one_folder_missing_exe_inside_dir(tmp_path: Path):
    config = make_config(tmp_path, OutputMode.ONE_FOLDER)
    dist_dir = config.output_dir / "MyApp"
    dist_dir.mkdir(parents=True)
    (dist_dir / "readme.txt").write_text("not the exe")

    outcome = BuildValidator().validate(config)

    assert not outcome.ok
