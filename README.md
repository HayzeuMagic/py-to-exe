# PyForge

**PyForge** is a Windows desktop application, by **Rivan Security Inc**, for packaging Python projects into Windows executables. You pick a project folder, PyForge scans it without running any of its code, flags likely packaging issues, and then drives [PyInstaller](https://pyinstaller.org/) to build a One File or One Folder executable — with live logs, cancellation, build history, and a persisted build report.

PyForge does not claim every Python project can be converted. Some projects use native dependencies, dynamic imports, or platform-specific code that static analysis can't fully resolve — PyForge surfaces what it can see and lets you decide how to proceed.

## Features

- **Non-destructive project scanner** — recursively finds `.py` files, dependency manifests, and asset files without importing or executing anything in your project.
- **Entry-point detection** — ranks candidate entry points (`main.py`, `app.py`, `run.py`, files with `if __name__ == "__main__":`) using AST analysis, with reasons shown for each candidate.
- **Dependency analysis** — parses `requirements.txt`, `pyproject.toml`, `setup.cfg`, and `Pipfile` with dedicated parsers (never by executing `setup.py`), and cross-references them against imports found via AST.
- **Compatibility analysis** — flags common PyInstaller pitfalls (dynamic imports, `__file__` path assumptions, native libraries, subprocess calls, relative imports, missing manifests) with a severity, explanation, affected file, and suggested fix for each finding.
- **Build configuration** — entry point, app name, output directory, One File / One Folder, Console / Windowed, icon, additional data files, hidden imports, clean build, UPX, and debug logging.
- **Background build engine** — runs PyInstaller in a worker thread with live stdout/stderr streaming, an indeterminate progress indicator (PyInstaller doesn't expose a reliable percentage), and cooperative cancellation.
- **Build validation** — confirms the expected executable/output folder actually exists and is non-empty before reporting success. This verifies the build produced artifacts — it does not verify runtime correctness.
- **Build history & reports** — every build's metadata is stored in a local SQLite database (`%LOCALAPPDATA%\PyForge\history.db`), with a JSON report per build and a link to the full log.
- **Settings** — appearance, default build options, scanner exclusions, log verbosity, and build-environment (interpreter) configuration, persisted locally.
- **Rivan Security color scheme** — dark navy / sky-blue theme matching the Rivan Security Inc Academy brand.

## Supported build modes

| Mode | Description |
|---|---|
| One File | A single `.exe` that self-extracts to a temp directory at runtime. |
| One Folder | A folder containing the `.exe` and its supporting files. Starts faster; easier to inspect. |
| Console | Keeps a console window attached — stdout/stderr are visible. |
| Windowed | No console window. Use only if your app doesn't need terminal I/O. |

## System requirements

- Windows 10 or 11
- Python 3.12 (or another Python 3.11+ interpreter)
- PyInstaller 6.10+ (installed automatically into the selected build interpreter when you confirm it in Settings, or via `pip install -r requirements.txt` for PyForge's own interpreter)

## Installation

```powershell
# From the project root
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Launching PyForge

```powershell
python main.py
```

## Using PyForge

### 1. Scan a project

Go to **Builder**, click **Browse Folder…**, and select a folder containing Python source. PyForge scans it in the background (your project's code is never imported or executed) and shows file counts, manifests, assets, and entry-point candidates. Use **Rescan Project** after you change files on disk, or **Clear Project** to start over.

### 2. Analyze compatibility

Click **Analyze Project**. The Compatibility Analysis panel shows an overall level:

- **No issues detected** — no static-analysis findings.
- **Configuration recommended** — a small number of findings that are usually easy to address (e.g. add a hidden import).
- **Warnings detected** — several findings worth reviewing before building.
- **Analysis incomplete** — too many files failed to parse to draw a reliable conclusion.
- **Potentially incompatible** — static analysis found a blocking pattern.

Each finding lists severity, an explanation, the affected file (when known), and a suggested fix. **A static scan is not a guarantee of a successful build** — it is the best signal static analysis can offer before actually running PyInstaller.

### 3. Configure the build

In **Build Configuration**, choose the entry point (auto-detected candidates are offered; you can also browse for any `.py` file), application name, output directory, One File/One Folder, Console/Windowed, an optional `.ico` icon, additional data files/folders, and hidden imports. Windowed mode shows a reminder that console output will be suppressed.

### 4. Build

Click **Build Executable**. PyForge validates your configuration, then runs PyInstaller in the background. The Build Output panel shows the current stage, elapsed time, an indeterminate progress bar, and live logs. Use **Cancel Build** to stop a running build.

After a successful build, PyForge verifies the output artifact exists and is non-empty before marking the build a success. Use **Open Output Folder** to see the result, **View Build Report** for the structured report, and the explicit **Run Executable** action if you want to launch the built program yourself — this is never done automatically, since it executes code from your project.

### 5. Review history

The **Build History** screen lists every build with its status, duration, and links to its output, log, and report. Removing a history entry only removes the database row — it never deletes files on disk.

## Limitations

- Static analysis cannot see everything a dynamic `eval`/`exec`/`importlib.import_module` call might do at runtime — add hidden imports manually if PyInstaller misses something.
- Projects with native extensions, platform-specific code, or external runtime dependencies (system DLLs, external services) may need additional manual configuration that PyForge cannot fully automate.
- A successful build is not proof the program behaves correctly — always test the generated executable.
- Complete environment isolation cannot be fully guaranteed on Windows: installing third-party packages via pip can execute that package's own build backend. PyForge never installs anything without your explicit confirmation, and never into its own interpreter by default.

## Security considerations

- PyForge never executes, imports, or `eval`s any file from a scanned project during analysis.
- `setup.py` is treated as untrusted source code and is never executed to discover dependencies.
- Dependency and PyInstaller installation only happens when you explicitly trigger it from Settings, with a confirmation dialog explaining what will run.
- PyInstaller is always invoked with an explicit argument list (never a shell string built from project input).
- PyForge does not delete or move your project's source files. Build work directories live under `%LOCALAPPDATA%\PyForge`, separate from your project.
- A "clean build" only ever deletes directories PyForge itself created under its own app-data folder.
- Running a built executable is always an explicit, separately confirmed action — PyForge never launches a generated `.exe` on its own.
- A static scan and a successful build are not a security certification. Packaging an untrusted project does not sandbox it.

## Distribution — packaging PyForge itself

PyForge can package itself the same way it packages any other project —
but be clear about what's being bundled:

- **PyForge's own executable** bundles PyForge's UI code and its own
  dependencies (CustomTkinter, Pillow, etc.) via PyInstaller.
- **The projects PyForge packages for other users** are separate builds
  with their own dependencies, entirely unrelated to PyForge's bundle.

Bundling PyForge does **not** automatically give target projects a Python
interpreter, their dependencies, or native libraries they need — PyForge
remains a *build tool*; each project it packages still needs its own
correctly-configured build (which is what the Builder screen is for).

To build a distributable PyForge.exe from source:

```powershell
python -m PyInstaller main.py --name PyForge --onefile --windowed `
  --icon assets\icons\app.ico `
  --add-data "assets;assets"
```

Run it from the project root with the project's own virtual environment
active. The `--add-data` flag bundles the `assets/` folder (icons, logo)
so they're available at runtime via `sys._MEIPASS` when frozen — the UI
code already falls back gracefully if an asset is missing.

PyForge's own settings, history, logs, and build-work files are written
to `%LOCALAPPDATA%\PyForge` regardless of whether PyForge itself is
running from source or as a frozen executable — never to the install
directory.

## Troubleshooting

See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

## Running tests

```powershell
python -m pytest tests/ -v
```

Tests run against a sandboxed app-data directory (via `PYFORGE_APP_DATA_DIR`, set automatically by `conftest.py`) and never touch your real `%LOCALAPPDATA%\PyForge`.

## More documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — module layout and data flow.
- [docs/USER_GUIDE.md](docs/USER_GUIDE.md) — walkthrough with screenshots-in-words of every screen.
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) — common build failures and fixes.

## License

MIT — see [LICENSE](LICENSE). © Rivan Security Inc.
