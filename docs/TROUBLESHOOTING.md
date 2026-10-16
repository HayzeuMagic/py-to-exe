# Troubleshooting

### "PyInstaller was not found for &lt;interpreter&gt;"

The interpreter PyForge is configured to use (Settings > Build Environment)
doesn't have PyInstaller installed. Click **Install / Upgrade PyInstaller**
in Settings, confirm the dialog, and wait for it to finish.

### Build fails immediately with a validation error

The config form validates before a build starts — common causes:

- **Application name** contains characters other than letters, numbers,
  spaces, `-`, `_`, `.`, or is a Windows-reserved name (`CON`, `PRN`, `COM1`, …).
- **Entry point** doesn't exist or isn't a `.py` file.
- **Output directory** is empty, equals the project root, or is a drive root.
- **Icon** isn't a `.ico` file.
- An **additional data** source no longer exists on disk.

Fix the highlighted field and try again.

### Build runs but PyInstaller exits non-zero

Check the live log in Build Output (or the full log via *Open Output
Folder* → `%LOCALAPPDATA%\PyForge\logs\builds\`). Common PyInstaller
causes:

- A module imported dynamically (via `importlib.import_module`, plugin
  discovery, etc.) wasn't detected. Add it under **Hidden Imports**.
- A data file your code reads at runtime (templates, images, config)
  wasn't bundled. Add it under **Additional Files / Directories**.
- A native library (`.dll`/`.pyd`) needs to sit next to the executable.
  Add its folder under **Additional Files / Directories**.

### Build succeeds but the built .exe doesn't start correctly

A successful build only means PyInstaller produced a non-empty
executable — it does **not** mean the program runs correctly. Common
runtime issues after packaging:

- Code using `__file__` to find resources breaks in a one-file build,
  because `__file__` resolves inside a temporary extraction directory at
  runtime. Use `sys._MEIPASS` (only set when frozen) instead.
- Code assuming the current working directory is the project folder.
  PyInstaller executables can be launched from anywhere.
- A package with optional C extensions that weren't collected. Try
  One Folder mode first (easier to inspect what's actually bundled)
  before One File.

Use **Run Executable** (with the confirmation dialog) to test the build
directly from PyForge, and check `%LOCALAPPDATA%\PyForge\logs\builds\` for
the full PyInstaller log.

### "A build is already in progress"

Only one build runs at a time. Wait for it to finish or click
**Cancel Build**.

### Scan reports "Scan stopped after N directories/files"

The selected folder is unexpectedly large (or points at something like a
whole drive). Point PyForge at the actual project folder, or add large
unrelated subfolders to **Scanner Exclusions** in Settings.

### Dependency install fails

The output of a failed `pip install` is shown in an error dialog (last
~1500 characters). Common causes: no internet connection, a package
requiring a C compiler that isn't installed, or a version conflict.
Installing into a dedicated interpreter/venv (Settings > custom
interpreter) avoids conflicts with PyForge's own dependencies.

### I don't see my change in Build History after a build

The Build History screen only refreshes when you navigate to it (or click
**Refresh**) — it doesn't live-update while you're on the Builder screen.
