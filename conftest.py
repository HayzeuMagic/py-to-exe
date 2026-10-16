import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))


@pytest.fixture(autouse=True)
def isolated_app_data_dir(tmp_path, monkeypatch):
    """Redirects PyForge's app-data directory (history DB, logs, reports,
    settings) into a per-test temp folder so the test suite never reads or
    writes the real user's %LOCALAPPDATA%\\PyForge."""
    monkeypatch.setenv("PYFORGE_APP_DATA_DIR", str(tmp_path / "pyforge_appdata"))
