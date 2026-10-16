# PyForge Architecture

## Layers

```
ui/        CustomTkinter views and reusable components. No PyInstaller or
           filesystem-mutation logic lives here — panels call into core/
           and display what comes back.

core/      All the actual engineering: scanning, analysis, build
           orchestration, process management, validation, reporting.
           No tkinter imports.

models/    Typed dataclasses shared between core and ui. No behavior
           beyond small derived properties.

utils/     Cross-cutting helpers: filesystem paths/safety, logging,
           validation, persisted app settings.
```

This separation means `core/` can be unit tested without a display, and
`ui/` stays thin — it wires user actions to `core/` calls and renders
`models/` objects.

## Data flow (Builder screen)

```
Browse Folder
   -> ProjectScanner.scan(path)              (background thread)
   -> EntryPointDetector.detect(python_files)
   -> ScannedProject                          (models/project.py)
   -> ProjectPanel.set_project(...)
   -> BuildSettingsPanel.set_entry_candidates(...)

Analyze Project
   -> DependencyAnalyzer.analyze(...)         (background thread)
   -> CompatibilityAnalyzer.analyze(...)
   -> DependencyAnalysis + CompatibilityAnalysis
   -> AnalysisPanel.show_analysis(...)

Build Executable
   -> BuildConfig assembled from BuildSettingsPanel fields
   -> core.build_config.validate_build_config(config)
   -> BuildManager.start(config)              (background thread)
        -> EnvironmentManager.inspect(interpreter)
        -> core.build_config.build_pyinstaller_args(config, ...)
        -> ProcessRunner.start([interpreter, "-m", "PyInstaller", ...])
             (streams OutputLine events via a queue.Queue, pumped by two
              daemon threads reading stdout/stderr)
        -> BuildValidator.validate(config)     (after exit code 0)
        -> build_report.save_report(result) + BuildHistoryStore.add_build(...)
   -> MainWindow polls BuildManager.event_queue via root.after(...)
   -> LogPanel renders StageEvent / LogEvent / CompletedEvent
```

All cross-thread communication uses `queue.Queue` plus a `root.after(...)`
poll loop on the Tk main thread — Tkinter widgets are only ever touched
from the main thread.

## Why a scanner that never imports code

`core/project_scanner.py`, `core/entry_point_detector.py`,
`core/dependency_analyzer.py`, and `core/compatibility_analyzer.py` all
work by reading file bytes and parsing them with `ast.parse` — never
`import`, `exec`, or `eval`. This is a hard requirement: a project a user
is about to package is untrusted input, and static analysis must not
become a code-execution vector.

`setup.py` is explicitly special-cased: PyForge never executes it. If a
project's dependency list only lives in `setup.py`'s `setup()` call,
PyForge will show a note that it couldn't be inspected rather than run it.

## Build isolation model

`core/environment_manager.py` resolves which Python interpreter runs
PyInstaller (PyForge's own interpreter by default, or a user-specified one
in Settings). Dependency installation (`install_requirements`,
`ensure_pyinstaller`) is never called automatically — only from an
explicit, confirmed UI action — and always targets the *selected build
interpreter*, never silently falling back to PyForge's own environment.

Complete isolation can't be fully guaranteed on Windows (pip itself may
run a package's build backend), which is documented rather than hidden.

## Where PyForge writes files

All of PyForge's own state lives under `%LOCALAPPDATA%\PyForge`
(`utils/filesystem.py::app_data_dir`), honoring the `PYFORGE_APP_DATA_DIR`
environment variable when set (used by the test suite to stay sandboxed):

```
%LOCALAPPDATA%\PyForge\
    settings.json       user settings (utils/app_settings.py)
    history.db          SQLite build history (core/build_report.py)
    reports/            one JSON report per build
    logs/pyforge.log     internal diagnostic log (utils/logging_config.py)
    logs/builds/*.log    full stdout/stderr for each build
    build_work/          PyInstaller's --workpath/--specpath per project
    envs/                per-project virtual environments (opt-in)
```

The user's project folder is never written to. Build *output* goes to
whatever directory the user chose in Build Configuration.

## Testing strategy

- `core/` modules are tested directly with `pytest` and `tmp_path` —
  no mocking of the filesystem itself, since these modules only read and
  write inside temp directories the test owns.
- `core/build_manager.py` is tested by monkeypatching
  `core.build_manager.build_pyinstaller_args` to return a short
  `python -c "..."` script instead of a real PyInstaller invocation, and
  `EnvironmentManager.inspect`/`default_interpreter` to avoid depending on
  a real PyInstaller install. This exercises the real `ProcessRunner`,
  thread, and queue machinery without the cost of an actual build.
- `conftest.py` sets `PYFORGE_APP_DATA_DIR` to a per-test temp directory
  (autouse fixture) so no test run ever touches the developer's real
  `%LOCALAPPDATA%\PyForge`.
