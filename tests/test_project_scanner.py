from pathlib import Path

from core.project_scanner import ProjectScanner


def make_file(path: Path, content: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_valid_project_multiple_files(tmp_path: Path):
    make_file(tmp_path / "main.py", "print('hi')")
    make_file(tmp_path / "utils.py", "x = 1")
    make_file(tmp_path / "requirements.txt", "requests\n")
    make_file(tmp_path / "assets" / "logo.png", "fake-bytes")

    result = ProjectScanner().scan(tmp_path)

    assert result.stats.total_python_files == 2
    assert len(result.manifests) == 1
    assert len(result.assets) == 1
    assert not result.scan_errors


def test_empty_directory(tmp_path: Path):
    result = ProjectScanner().scan(tmp_path)
    assert result.stats.total_python_files == 0
    assert result.python_files == []
    assert not result.scan_errors


def test_no_python_files(tmp_path: Path):
    make_file(tmp_path / "readme.txt", "hello")
    result = ProjectScanner().scan(tmp_path)
    assert result.stats.total_python_files == 0


def test_nonexistent_path(tmp_path: Path):
    result = ProjectScanner().scan(tmp_path / "does-not-exist")
    assert result.scan_errors
    assert result.stats.total_python_files == 0


def test_path_is_file_not_directory(tmp_path: Path):
    file_path = tmp_path / "file.py"
    make_file(file_path, "x = 1")
    result = ProjectScanner().scan(file_path)
    assert result.scan_errors


def test_ignored_directories_excluded(tmp_path: Path):
    make_file(tmp_path / "main.py", "print(1)")
    make_file(tmp_path / ".venv" / "lib" / "site.py", "x = 1")
    make_file(tmp_path / "__pycache__" / "cache.py", "x = 1")
    make_file(tmp_path / "node_modules" / "pkg" / "index.py", "x = 1")

    result = ProjectScanner().scan(tmp_path)

    scanned_names = {p.name for p in result.python_files}
    assert scanned_names == {"main.py"}


def test_nested_packages(tmp_path: Path):
    make_file(tmp_path / "pkg" / "__init__.py", "")
    make_file(tmp_path / "pkg" / "sub" / "__init__.py", "")
    make_file(tmp_path / "pkg" / "sub" / "module.py", "x = 1")

    result = ProjectScanner().scan(tmp_path)

    assert result.stats.total_python_files == 3


def test_unicode_paths(tmp_path: Path):
    unicode_dir = tmp_path / "项目" / "模块"
    make_file(unicode_dir / "主程序.py", "print('你好')")

    result = ProjectScanner().scan(tmp_path)

    assert result.stats.total_python_files == 1
    assert result.python_files[0].name == "主程序.py"


def test_malformed_source_code_still_counted(tmp_path: Path):
    make_file(tmp_path / "broken.py", "def f(:\n    pass")
    result = ProjectScanner().scan(tmp_path)
    # Scanner only classifies files; it doesn't parse them, so a syntax
    # error shouldn't prevent the file from being discovered.
    assert result.stats.total_python_files == 1


def test_custom_excludes(tmp_path: Path):
    make_file(tmp_path / "main.py", "x = 1")
    make_file(tmp_path / "custom_ignore" / "mod.py", "x = 1")

    result = ProjectScanner(excludes=frozenset({"custom_ignore"})).scan(tmp_path)

    names = {p.name for p in result.python_files}
    assert names == {"main.py"}


def test_scan_handles_permission_error(tmp_path: Path, monkeypatch):
    make_file(tmp_path / "main.py", "x = 1")

    scanner = ProjectScanner()
    original_classify = scanner._classify_file

    def flaky_classify(file_path, result):
        if file_path.name == "main.py":
            raise OSError("permission denied")
        return original_classify(file_path, result)

    monkeypatch.setattr(scanner, "_classify_file", flaky_classify)
    result = scanner.scan(tmp_path)

    assert result.scan_errors
    assert result.stats.total_python_files == 0
