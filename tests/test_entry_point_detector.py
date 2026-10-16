from pathlib import Path

from core.entry_point_detector import EntryPointDetector
from models.project import EntryPointConfidence


def write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_main_py_detected_high_confidence(tmp_path: Path):
    f = write(tmp_path / "main.py", "if __name__ == '__main__':\n    print('hi')\n")
    candidates = EntryPointDetector().detect([f])
    assert candidates[0].path == f
    assert candidates[0].confidence == EntryPointConfidence.HIGH


def test_app_py_detected(tmp_path: Path):
    f = write(tmp_path / "app.py", "if __name__ == '__main__':\n    pass\n")
    candidates = EntryPointDetector().detect([f])
    assert any(c.path == f for c in candidates)


def test_run_py_detected(tmp_path: Path):
    f = write(tmp_path / "run.py", "if __name__ == '__main__':\n    pass\n")
    candidates = EntryPointDetector().detect([f])
    assert any(c.path == f for c in candidates)


def test_dunder_main_block_without_name_hint(tmp_path: Path):
    f = write(tmp_path / "start_here.py", "if __name__ == '__main__':\n    pass\n")
    candidates = EntryPointDetector().detect([f])
    assert len(candidates) == 1
    assert candidates[0].confidence in (EntryPointConfidence.MEDIUM, EntryPointConfidence.HIGH)


def test_multiple_candidates_ranked(tmp_path: Path):
    main_f = write(tmp_path / "main.py", "if __name__ == '__main__':\n    pass\n")
    helper_f = write(tmp_path / "helper.py", "def f():\n    pass\n")
    other_f = write(tmp_path / "other.py", "if __name__ == '__main__':\n    pass\n")

    candidates = EntryPointDetector().detect([main_f, helper_f, other_f])
    paths = [c.path for c in candidates]

    assert helper_f not in paths  # no signal at all -> not a candidate
    assert paths[0] == main_f  # name hint + dunder-main outranks dunder-main alone


def test_no_candidates(tmp_path: Path):
    f = write(tmp_path / "utils.py", "def helper():\n    return 1\n")
    candidates = EntryPointDetector().detect([f])
    assert candidates == []


def test_syntax_error_with_name_hint_still_surfaced(tmp_path: Path):
    f = write(tmp_path / "main.py", "def broken(:\n   pass")
    candidates = EntryPointDetector().detect([f])
    assert len(candidates) == 1
    assert candidates[0].confidence == EntryPointConfidence.LOW


def test_syntax_error_without_name_hint_not_surfaced(tmp_path: Path):
    f = write(tmp_path / "weird.py", "def broken(:\n   pass")
    candidates = EntryPointDetector().detect([f])
    assert candidates == []
