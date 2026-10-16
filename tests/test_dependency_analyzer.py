from pathlib import Path

from core.dependency_analyzer import DependencyAnalyzer
from models.project import ManifestFile


def write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_requirements_txt_parsed(tmp_path: Path):
    req = write(tmp_path / "requirements.txt", "requests==2.31.0\n# comment\nnumpy>=1.0\n-e ./local\n")
    analysis = DependencyAnalyzer().analyze(
        tmp_path, [], [ManifestFile(path=req, kind="requirements.txt")]
    )
    assert "requests" in analysis.declared_requirements
    assert "numpy" in analysis.declared_requirements


def test_pyproject_toml_parsed(tmp_path: Path):
    pyproject = write(
        tmp_path / "pyproject.toml",
        '[project]\nname = "demo"\ndependencies = ["flask>=2.0", "click"]\n',
    )
    analysis = DependencyAnalyzer().analyze(
        tmp_path, [], [ManifestFile(path=pyproject, kind="pyproject.toml")]
    )
    assert "flask" in analysis.declared_requirements
    assert "click" in analysis.declared_requirements


def test_stdlib_imports_classified(tmp_path: Path):
    f = write(tmp_path / "main.py", "import os\nimport sys\nfrom pathlib import Path\n")
    analysis = DependencyAnalyzer().analyze(tmp_path, [f], [])
    assert "os" in analysis.stdlib_imports
    assert "sys" in analysis.stdlib_imports
    assert "pathlib" in analysis.stdlib_imports
    assert not analysis.third_party


def test_third_party_imports_detected(tmp_path: Path):
    f = write(tmp_path / "main.py", "import requests\nimport numpy as np\n")
    analysis = DependencyAnalyzer().analyze(tmp_path, [f], [])
    names = {d.import_name for d in analysis.third_party}
    assert names == {"requests", "numpy"}


def test_relative_imports_not_third_party(tmp_path: Path):
    write(tmp_path / "pkg" / "__init__.py", "")
    f = write(tmp_path / "pkg" / "main.py", "from . import helper\nfrom .helper import thing\n")
    analysis = DependencyAnalyzer().analyze(tmp_path, [f], [])
    assert not analysis.third_party


def test_local_module_imports_not_third_party(tmp_path: Path):
    helper = write(tmp_path / "helper.py", "x = 1\n")
    main = write(tmp_path / "main.py", "import helper\n")
    analysis = DependencyAnalyzer().analyze(tmp_path, [helper, main], [])
    assert not analysis.third_party
    assert "helper" in analysis.local_imports


def test_missing_manifest_malformed_is_reported_not_raised(tmp_path: Path):
    bad_pyproject = write(tmp_path / "pyproject.toml", "this is not valid toml [[[")
    analysis = DependencyAnalyzer().analyze(
        tmp_path, [], [ManifestFile(path=bad_pyproject, kind="pyproject.toml")]
    )
    assert analysis.manifest_parse_errors


def test_setup_py_is_never_executed(tmp_path: Path, monkeypatch):
    # If setup.py were executed, this would create a marker file / raise.
    setup_py = write(
        tmp_path / "setup.py",
        "raise RuntimeError('setup.py must never be executed by PyForge')\n",
    )
    analysis = DependencyAnalyzer().analyze(
        tmp_path, [], [ManifestFile(path=setup_py, kind="setup.py")]
    )
    # Should not raise, and should not have "executed" anything.
    assert analysis.manifest_parse_errors == []


def test_declared_requirement_marks_import_as_declared(tmp_path: Path):
    req = write(tmp_path / "requirements.txt", "requests\n")
    main = write(tmp_path / "main.py", "import requests\n")
    analysis = DependencyAnalyzer().analyze(
        tmp_path, [main], [ManifestFile(path=req, kind="requirements.txt")]
    )
    finding = next(d for d in analysis.third_party if d.import_name == "requests")
    assert finding.declared_in_manifest is True
    assert analysis.missing_declarations == []
