# GUI and Windows EXE Design

## Goal

Add a GUI to the SMART Patrol XML to KML converter while preserving the existing CLI. The GUI must run as a Windows `.exe`, built reliably from the Linux development environment by using GitHub Actions on a Windows runner.

## Decisions

- Use a core + CLI + GUI architecture.
- Keep the existing CLI behavior backward compatible.
- Use Tkinter for v1 because it is built into Python, stable, and easy to package.
- Build the Windows `.exe` with GitHub Actions on `windows-latest`.
- Default KML output remains beside each XML file.
- GUI language is English.
- Scope is a simple converter with preview, not a GIS/map viewer.

## Alternatives Considered

### A. Thin Tkinter wrapper over current script

Fastest and lowest risk, but preview and testing would remain awkward because the current script mixes command-line concerns with conversion logic.

### B. Refactor into core + GUI + CLI

Recommended. Move reusable conversion logic into a package. Let the CLI and GUI both import the same core functions. This keeps current usage working while making preview, GUI logging, and testing cleaner.

### C. GUI shells out to CLI subprocess

Lowest refactor, but worse error handling and preview support. It would also make progress reporting and batch summaries less reliable.

## Proposed Structure

```text
smartpatrol_kml/
  __init__.py
  converter.py      # current conversion logic, no GUI
  preview.py        # safe metadata/count parsing for preview
  gui.py            # Tkinter desktop app
smart_xml_to_kml.py # CLI shim; imports converter.main
requirements.txt
requirements-dev.txt
.github/workflows/windows-exe.yml
```

`converter.py` keeps current conversion behavior: single XML, folder batch, recursive option, warnings, and `.kml` beside the source unless an output override is provided.

`preview.py` reads XML without writing anything. It reports patrol id, station, dates, leg count, track count, waypoint count, members, and validation warnings.

`gui.py` is a thin application layer over `converter.py` and `preview.py`.

## GUI Design

Tone: field-operations console. The interface should feel like a rugged patrol data tool: dark slate panels, muted borders, amber action button, green success status, red failure status, compact metadata cards.

Main layout:

```text
SMART Patrol XML → KML

Source
[ selected file or folder path ] [Browse File] [Browse Folder]
[x] Recursive  (enabled only for folders)

Output
[ blank = beside XML ] [Choose Output Folder]

Preview
Patrol ID: ...          Station: ...
Dates: ...              Members: ...
Tracks: ...             Waypoints: ...

[ Convert to KML ]

Log
converted: ...
warning: ...
failed: ...

Summary: 3 converted, 0 failed
```

Behavior:

- File selection previews that XML.
- Folder selection shows XML count and previews the first valid XML or states that a batch folder is selected.
- Invalid single-file XML disables conversion and shows a clear preview error.
- Batch conversion continues when one file fails.
- Output folder is optional; blank means write KML beside each XML.
- Recursive checkbox only applies to folders.
- No map viewer, KML viewer, photo linking, or settings screen in v1.

## Data Flow

1. User selects a file or folder.
2. GUI calls preview functions.
3. Preview returns plain data, such as patrol id, station, dates, counts, members, and warnings.
4. User clicks Convert.
5. GUI disables controls and starts a background worker thread.
6. Worker finds XML files using the existing file discovery behavior.
7. Each file is converted with `convert_file()`.
8. Worker posts log events into `queue.Queue`.
9. Tk main loop drains the queue with `after(...)` and updates the log/progress.
10. On finish, controls re-enable and summary shows converted/failed totals.

## Error Handling

- Missing source: show inline status asking the user to select an XML file or folder.
- Malformed XML: preview says invalid XML; conversion disabled for a single file.
- Non-SMART root: preview says not a SMART patrol XML; conversion disabled for a single file.
- Batch failures: log each failed file and keep converting the rest.
- Shapely missing: show startup error dialog; CI should also catch this.
- Output folder issue: validate before conversion when possible; otherwise log the failure.

## Windows EXE Build

Use GitHub Actions instead of cross-compiling from Linux.

Workflow trigger:

```yaml
on:
  push:
    tags: ["v*"]
  workflow_dispatch:
```

Build steps:

1. Check out repository.
2. Set up Python 3.12 on `windows-latest`.
3. Install `requirements.txt` and PyInstaller.
4. Run lightweight import/smoke checks.
5. Build with PyInstaller:

```bash
pyinstaller --onefile --windowed \
  --name SMART-Patrol-XML-to-KML \
  smartpatrol_kml/gui.py
```

6. Upload `dist/SMART-Patrol-XML-to-KML.exe` as an artifact.

Packaging notes:

- `--windowed` hides the console.
- GUI log replaces terminal output.
- Building on Windows avoids Shapely cross-platform binary issues.
- Later optional work: app icon, installer, version metadata, signed binary.

## Testing Plan

- Add preview parsing tests when sample XML fixtures are available.
- Keep CLI smoke checks working.
- Run import checks for `smartpatrol_kml.converter`, `smartpatrol_kml.preview`, and `smartpatrol_kml.gui`.
- Manually smoke-test the GUI on Linux during development.
- Validate the GitHub Actions artifact on Windows before release.

## Implementation Setup

Before implementation:

- Add `.gitignore` for Python, PyInstaller, virtualenv, and build outputs.
- Commit the current baseline and this design document.
- Then implement on a feature branch/worktree.
