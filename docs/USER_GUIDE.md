# PyForge User Guide

## Builder screen

The Builder screen is split into four areas:

**Top-left — Project.** Browse to a folder, see file/manifest/asset counts
and the last scan time. Rescan after editing files; Clear to start over.

**Top-right — Compatibility Analysis.** After clicking Analyze Project
(bottom-left toolbar), this shows an overall compatibility level plus a
scrollable list of individual findings, each with severity, an
explanation, the affected file when known, and a suggested fix. Possible
levels, from best to most concerning:

1. No issues detected
2. Configuration recommended
3. Warnings detected
4. Analysis incomplete (too many files failed to parse)
5. Potentially incompatible

None of these levels are a guarantee — they summarize what static
analysis could see.

**Bottom-left — Build Configuration + toolbar.** The toolbar has:
*Analyze Project*, *Build Executable*, *Cancel Build*, *Open Output
Folder*, *View Build Report*, *Run Executable*. Buttons disable themselves
when their action isn't valid yet (e.g. no project scanned, or no
completed build to open).

Below the toolbar: entry point selection (auto-detected candidates, or
Browse for any `.py` file), application name, output directory, One
File/One Folder, Console/Windowed (with a reminder for Windowed mode),
optional icon, hidden imports, additional data files/folders, and
advanced toggles (clean build, UPX, debug logging).

**Bottom-right — Build Output.** Shows the current stage, elapsed time, an
indeterminate progress bar (PyInstaller doesn't expose a trustworthy
percentage), a live scrolling log (stdout in gray, stderr in amber), and a
final status line once the build finishes.

## Build History screen

Lists every past build: app name, status badge, project path, timestamp,
duration, mode, and interpreter/PyInstaller versions. Each entry has
*Open Output*, *Open Log*, *View Report*, and *Remove Entry* actions.
Removing an entry only deletes its history row — artifacts and logs on
disk are untouched.

## Settings screen

Appearance (dark/light), default output mode/console mode, log verbosity,
scanner exclusions (comma-separated directory names skipped during
scanning), a custom Python interpreter path (leave blank to use PyForge's
own), and a one-click PyInstaller install/upgrade for the selected
interpreter (always confirmed first — this runs `pip`, which can execute
a package's own build code). *Clear All Build History* removes every
history row (not the underlying files). *Reset to Defaults* restores
every setting.

## About screen

Version, Rivan Security Inc attribution, and a reminder that a static
scan and a successful build are not proof of correct runtime behavior.

## Running the executable you built

Click **Run Executable** after a successful build. PyForge always asks
for confirmation first, because this executes code that was built from
your project's source — the same caution you'd apply to running any
program from an unfamiliar source.
