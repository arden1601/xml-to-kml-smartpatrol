# GUI Windows EXE Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a Tkinter GUI with XML preview and Windows `.exe` packaging while preserving the current command-line converter behavior.

**Architecture:** Refactor the single script into a small `smartpatrol_kml` package. The CLI shim and GUI both call the same converter functions. Preview parsing is read-only and independent from conversion.

**Tech Stack:** Python 3.12, stdlib Tkinter/ttk, stdlib `xml.etree.ElementTree`, Shapely, pytest, PyInstaller, GitHub Actions `windows-latest`.

---

## Context

Current files in the worktree:

- `smart_xml_to_kml.py` — single-file CLI and converter implementation.
- `requirements.txt` — runtime dependency: `shapely>=2.1,<3`.
- `README.md` — CLI usage docs.
- `docs/plans/2026-06-01-gui-windows-exe-design.md` — approved GUI/packaging design.

Primary constraints:

- Preserve existing CLI commands:
  - `python3 smart_xml_to_kml.py input.xml`
  - `python3 smart_xml_to_kml.py input.xml -o output.kml`
  - `python3 smart_xml_to_kml.py /path/to/folder --recursive`
- GUI default output remains beside each XML.
- Windows `.exe` is built in GitHub Actions on Windows, not cross-compiled from Linux.
- v1 GUI is simple converter + preview; no map viewer.

---

## Task 1: Add test/dev scaffolding

**Files:**

- Create: `requirements-dev.txt`
- Create: `tests/fixtures/minimal_patrol.xml`
- Create: `tests/test_converter_cli.py`

**Step 1: Add dev dependencies**

Create `requirements-dev.txt`:

```text
pytest>=8,<9
pyinstaller>=6,<7
```

Do not duplicate `shapely` here; CI and local setup install both `requirements.txt` and `requirements-dev.txt`.

**Step 2: Add minimal SMART patrol fixture**

Create `tests/fixtures/minimal_patrol.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<patrol xmlns="http://www.smartconservationsoftware.org/xml/1.3/patrol"
        id="PATROL-001"
        patrolType="Marine"
        startDate="2026-05-06"
        endDate="2026-05-08"
        isArmed="false">
  <station value="Resort Teluk Terima" />
  <legs id="1">
    <transportType value="Boat" />
    <members givenName="Budi" familyName="Santoso" employeeId="E001" isLeader="true" />
    <mandate value="Routine patrol" />
    <days date="2026-05-06">
      <waypoints id="WP1" x="114.500000" y="-8.100000" time="08:30:00">
        <observations categoryKey="marine.wildlife.turtle">
          <attributes attributeKey="species">
            <sValue>Green turtle</sValue>
          </attributes>
          <attachments filename="photo1.jpg" />
        </observations>
      </waypoints>
    </days>
  </legs>
  <comment>Routine check</comment>
  <attributes key="sumberdana" stringValue="dipa" />
</patrol>
```

This fixture intentionally has no track geometry. Converter should still produce a valid KML with 0 tracks and 1 waypoint.

**Step 3: Write converter smoke test before refactor**

Create `tests/test_converter_cli.py`:

```python
from pathlib import Path
import xml.etree.ElementTree as ET

import smart_xml_to_kml


def test_convert_minimal_patrol_fixture(tmp_path: Path) -> None:
    source = Path(__file__).parent / "fixtures" / "minimal_patrol.xml"
    output = tmp_path / "minimal.kml"

    stats = smart_xml_to_kml.convert_file(source, output)

    assert stats.tracks == 0
    assert stats.waypoints == 1
    assert output.exists()

    tree = ET.parse(output)
    root = tree.getroot()
    assert root.tag.endswith("kml")
    text = output.read_text(encoding="utf-8")
    assert "PATROL-001" in text
    assert "Green turtle" in text
    assert "sumberdana" in text
```

**Step 4: Run test to verify baseline passes**

Run:

```bash
python -m pytest tests/test_converter_cli.py -v
```

Expected: PASS. If Shapely is missing, install dependencies first:

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
```

**Step 5: Commit**

```bash
git add requirements-dev.txt tests/fixtures/minimal_patrol.xml tests/test_converter_cli.py
git commit -m "test: add converter smoke fixture"
```

---

## Task 2: Create package and move converter logic

**Files:**

- Create: `smartpatrol_kml/__init__.py`
- Create: `smartpatrol_kml/converter.py`
- Modify: `smart_xml_to_kml.py`
- Modify: `tests/test_converter_cli.py`

**Step 1: Create package init**

Create `smartpatrol_kml/__init__.py`:

```python
"""SMART Patrol XML to KML conversion tools."""

__version__ = "0.1.0"
```

**Step 2: Move implementation**

Move all existing code from `smart_xml_to_kml.py` into `smartpatrol_kml/converter.py`, unchanged except:

- Keep imports and all functions/classes intact.
- Keep `if __name__ == "__main__": raise SystemExit(main())` at bottom for direct module execution.
- Keep public functions used by tests: `convert_file`, `find_xml_files`, `main`.

**Step 3: Replace root script with CLI shim**

Replace `smart_xml_to_kml.py` with:

```python
#!/usr/bin/env python3
"""Command-line entry point for SMART Patrol XML to KML conversion."""

from smartpatrol_kml.converter import ConvertStats, convert_file, find_xml_files, main

__all__ = ["ConvertStats", "convert_file", "find_xml_files", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
```

The re-export keeps existing imports in `tests/test_converter_cli.py` working.

**Step 4: Add package import test**

Append to `tests/test_converter_cli.py`:

```python
def test_cli_shim_reexports_converter_api() -> None:
    assert smart_xml_to_kml.convert_file is not None
    assert smart_xml_to_kml.find_xml_files is not None
```

**Step 5: Run tests**

Run:

```bash
python -m pytest tests/test_converter_cli.py -v
```

Expected: PASS.

**Step 6: Smoke CLI manually**

Run:

```bash
python smart_xml_to_kml.py tests/fixtures/minimal_patrol.xml -o /tmp/minimal-patrol.kml
```

Expected output includes:

```text
converted: ...minimal_patrol.xml -> /tmp/minimal-patrol.kml (0 tracks, 1 waypoints, 0 warnings)
summary: 1 converted, 0 failed
```

**Step 7: Commit**

```bash
git add smartpatrol_kml/__init__.py smartpatrol_kml/converter.py smart_xml_to_kml.py tests/test_converter_cli.py
git commit -m "refactor: move converter into package"
```

---

## Task 3: Add preview parser

**Files:**

- Create: `smartpatrol_kml/preview.py`
- Create: `tests/test_preview.py`

**Step 1: Write failing preview tests**

Create `tests/test_preview.py`:

```python
from pathlib import Path

from smartpatrol_kml.preview import preview_file, preview_path

FIXTURES = Path(__file__).parent / "fixtures"


def test_preview_file_reads_patrol_metadata() -> None:
    info = preview_file(FIXTURES / "minimal_patrol.xml")

    assert info.is_valid is True
    assert info.patrol_id == "PATROL-001"
    assert info.station == "Resort Teluk Terima"
    assert info.start_date == "2026-05-06"
    assert info.end_date == "2026-05-08"
    assert info.legs == 1
    assert info.tracks == 0
    assert info.waypoints == 1
    assert info.members == ["Budi Santoso [E001] (leader)"]
    assert info.error == ""


def test_preview_file_rejects_non_patrol_xml(tmp_path: Path) -> None:
    source = tmp_path / "not_patrol.xml"
    source.write_text("<root />", encoding="utf-8")

    info = preview_file(source)

    assert info.is_valid is False
    assert "not a SMART patrol XML file" in info.error


def test_preview_path_counts_folder_xml_files() -> None:
    batch = preview_path(FIXTURES, recursive=False)

    assert batch.source == FIXTURES
    assert batch.xml_files == 1
    assert batch.first_valid is not None
    assert batch.first_valid.patrol_id == "PATROL-001"
```

**Step 2: Run test to verify failure**

Run:

```bash
python -m pytest tests/test_preview.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'smartpatrol_kml.preview'`.

**Step 3: Implement preview parser**

Create `smartpatrol_kml/preview.py`:

```python
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from smartpatrol_kml.converter import children, find_xml_files, first_text, local_name


@dataclass
class PreviewInfo:
    source: Path
    is_valid: bool
    patrol_id: str = ""
    station: str = ""
    start_date: str = ""
    end_date: str = ""
    legs: int = 0
    tracks: int = 0
    waypoints: int = 0
    members: list[str] = field(default_factory=list)
    error: str = ""
    warnings: list[str] = field(default_factory=list)


@dataclass
class PathPreview:
    source: Path
    is_file: bool
    xml_files: int = 0
    first_valid: PreviewInfo | None = None
    error: str = ""


def preview_file(source: Path) -> PreviewInfo:
    source = source.resolve()
    try:
        tree = ET.parse(source)
    except Exception as exc:  # noqa: BLE001 - user-facing preview should not crash
        return PreviewInfo(source=source, is_valid=False, error=f"invalid XML: {exc}")

    root = tree.getroot()
    if local_name(root.tag) != "patrol":
        return PreviewInfo(
            source=source,
            is_valid=False,
            error=f"not a SMART patrol XML file: root is <{local_name(root.tag)}>",
        )

    station = ""
    stations = children(root, "station")
    if stations:
        station = stations[0].attrib.get("value", "").strip()

    legs = children(root, "legs")
    members: list[str] = []
    tracks = 0
    waypoints = 0

    for leg in legs:
        for member in children(leg, "members"):
            member_text = _member_label(member)
            if member_text:
                members.append(member_text)
        for day in children(leg, "days"):
            tracks += len(children(day, "track"))
            waypoints += len(children(day, "waypoints"))

    return PreviewInfo(
        source=source,
        is_valid=True,
        patrol_id=root.attrib.get("id", "").strip() or source.stem,
        station=station,
        start_date=root.attrib.get("startDate", "").strip(),
        end_date=root.attrib.get("endDate", "").strip(),
        legs=len(legs),
        tracks=tracks,
        waypoints=waypoints,
        members=members,
    )


def preview_path(source: Path, recursive: bool = False) -> PathPreview:
    source = source.resolve()
    if source.is_file():
        info = preview_file(source)
        return PathPreview(source=source, is_file=True, xml_files=1 if source.suffix.lower() == ".xml" else 0, first_valid=info)

    if not source.exists():
        return PathPreview(source=source, is_file=False, error="source does not exist")

    xml_files = find_xml_files(source, recursive)
    first_valid = None
    for xml_file in xml_files:
        info = preview_file(xml_file)
        if info.is_valid:
            first_valid = info
            break

    return PathPreview(source=source, is_file=False, xml_files=len(xml_files), first_valid=first_valid)


def _member_label(member: ET.Element) -> str:
    name = " ".join(
        part.strip()
        for part in (member.attrib.get("givenName", ""), member.attrib.get("familyName", ""))
        if part.strip()
    )
    employee_id = member.attrib.get("employeeId", "").strip()
    roles = []
    if member.attrib.get("isLeader", "false").lower() == "true":
        roles.append("leader")
    if member.attrib.get("isPilot", "false").lower() == "true":
        roles.append("pilot")
    role_text = f" ({', '.join(roles)})" if roles else ""
    id_text = f" [{employee_id}]" if employee_id else ""
    return f"{name}{id_text}{role_text}".strip()
```

If `first_text` is unused, remove it from the import before committing.

**Step 4: Run preview tests**

Run:

```bash
python -m pytest tests/test_preview.py -v
```

Expected: PASS.

**Step 5: Run full test suite**

Run:

```bash
python -m pytest -v
```

Expected: all tests PASS.

**Step 6: Commit**

```bash
git add smartpatrol_kml/preview.py tests/test_preview.py
git commit -m "feat: add patrol preview parser"
```

---

## Task 4: Add Tkinter GUI shell and import smoke test

**Files:**

- Create: `smartpatrol_kml/gui.py`
- Create: `tests/test_gui_import.py`

**Step 1: Write GUI import test**

Create `tests/test_gui_import.py`:

```python
def test_gui_module_imports() -> None:
    import smartpatrol_kml.gui as gui

    assert gui.SmartPatrolApp is not None
    assert gui.main is not None
```

**Step 2: Run test to verify failure**

Run:

```bash
python -m pytest tests/test_gui_import.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

**Step 3: Implement first GUI shell**

Create `smartpatrol_kml/gui.py` with this working baseline:

```python
from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from smartpatrol_kml.converter import convert_file, find_xml_files
from smartpatrol_kml.preview import PathPreview, PreviewInfo, preview_path


class SmartPatrolApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("SMART Patrol XML → KML")
        self.geometry("920x680")
        self.minsize(820, 600)

        self.source_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.recursive = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="Select an XML file or folder.")
        self._source_is_folder = False
        self._can_convert = False
        self._events: queue.Queue[tuple[str, str]] = queue.Queue()
        self._worker: threading.Thread | None = None

        self._configure_style()
        self._build_ui()
        self.after(100, self._drain_events)

    def _configure_style(self) -> None:
        self.configure(bg="#111820")
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#111820")
        style.configure("Panel.TFrame", background="#18232d", bordercolor="#2c3d4d", relief="solid")
        style.configure("TLabel", background="#111820", foreground="#d8e2ea")
        style.configure("Muted.TLabel", background="#111820", foreground="#8ea0ad")
        style.configure("Panel.TLabel", background="#18232d", foreground="#d8e2ea")
        style.configure("Title.TLabel", background="#111820", foreground="#f0b45b", font=("Segoe UI", 18, "bold"))
        style.configure("TButton", padding=6)
        style.configure("Accent.TButton", background="#d28a32", foreground="#111820", padding=8)
        style.map("Accent.TButton", background=[("active", "#f0b45b"), ("disabled", "#5a6470")])
        style.configure("TEntry", fieldbackground="#0d141b", foreground="#e5edf3", insertcolor="#e5edf3")
        style.configure("TCheckbutton", background="#111820", foreground="#d8e2ea")

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=18)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(3, weight=1)

        ttk.Label(root, text="SMART Patrol XML → KML", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(root, textvariable=self.status, style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=(4, 14))

        controls = ttk.Frame(root)
        controls.grid(row=2, column=0, sticky="ew")
        controls.columnconfigure(1, weight=1)

        ttk.Label(controls, text="Source").grid(row=0, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.source_path).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(controls, text="Browse File", command=self._browse_file).grid(row=0, column=2, padx=(0, 6))
        ttk.Button(controls, text="Browse Folder", command=self._browse_folder).grid(row=0, column=3)

        self.recursive_check = ttk.Checkbutton(controls, text="Recursive", variable=self.recursive, command=self._refresh_preview)
        self.recursive_check.grid(row=1, column=1, sticky="w", padx=8, pady=(8, 0))
        self.recursive_check.state(["disabled"])

        ttk.Label(controls, text="Output").grid(row=2, column=0, sticky="w", pady=(12, 0))
        ttk.Entry(controls, textvariable=self.output_path).grid(row=2, column=1, sticky="ew", padx=8, pady=(12, 0))
        ttk.Button(controls, text="Choose Output Folder", command=self._choose_output).grid(row=2, column=2, columnspan=2, sticky="ew", pady=(12, 0))

        body = ttk.Frame(root)
        body.grid(row=3, column=0, sticky="nsew", pady=(18, 0))
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        preview_frame = ttk.Frame(body, style="Panel.TFrame", padding=14)
        preview_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 9))
        preview_frame.columnconfigure(1, weight=1)
        ttk.Label(preview_frame, text="Preview", style="Panel.TLabel", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        self.preview_labels: dict[str, tk.StringVar] = {}
        for index, key in enumerate(("Patrol ID", "Station", "Dates", "Legs", "Tracks", "Waypoints", "Members"), start=1):
            ttk.Label(preview_frame, text=f"{key}:", style="Panel.TLabel").grid(row=index, column=0, sticky="nw", pady=3)
            value = tk.StringVar(value="—")
            self.preview_labels[key] = value
            ttk.Label(preview_frame, textvariable=value, style="Panel.TLabel", wraplength=320).grid(row=index, column=1, sticky="w", pady=3)

        log_frame = ttk.Frame(body, style="Panel.TFrame", padding=14)
        log_frame.grid(row=0, column=1, sticky="nsew", padx=(9, 0))
        log_frame.rowconfigure(1, weight=1)
        log_frame.columnconfigure(0, weight=1)
        ttk.Label(log_frame, text="Log", style="Panel.TLabel", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 10))
        self.log = tk.Text(log_frame, height=16, bg="#0d141b", fg="#d8e2ea", insertbackground="#d8e2ea", relief="flat", wrap="word")
        self.log.grid(row=1, column=0, sticky="nsew")

        footer = ttk.Frame(root)
        footer.grid(row=4, column=0, sticky="ew", pady=(16, 0))
        footer.columnconfigure(0, weight=1)
        self.convert_button = ttk.Button(footer, text="Convert to KML", style="Accent.TButton", command=self._start_conversion)
        self.convert_button.grid(row=0, column=1, sticky="e")
        self.convert_button.state(["disabled"])

    def _browse_file(self) -> None:
        filename = filedialog.askopenfilename(title="Select SMART patrol XML", filetypes=[("XML files", "*.xml"), ("All files", "*.*")])
        if filename:
            self._source_is_folder = False
            self.source_path.set(filename)
            self.recursive_check.state(["disabled"])
            self._refresh_preview()

    def _browse_folder(self) -> None:
        dirname = filedialog.askdirectory(title="Select folder containing SMART patrol XML files")
        if dirname:
            self._source_is_folder = True
            self.source_path.set(dirname)
            self.recursive_check.state(["!disabled"])
            self._refresh_preview()

    def _choose_output(self) -> None:
        dirname = filedialog.askdirectory(title="Select output folder")
        if dirname:
            self.output_path.set(dirname)

    def _refresh_preview(self) -> None:
        source = self.source_path.get().strip()
        self._can_convert = False
        if not source:
            self._set_status("Select an XML file or folder.")
            self._set_preview_empty()
            self._update_convert_state()
            return

        info = preview_path(Path(source), recursive=self.recursive.get())
        self._render_path_preview(info)
        self._update_convert_state()

    def _render_path_preview(self, info: PathPreview) -> None:
        if info.error:
            self._set_status(info.error)
            self._set_preview_empty()
            return

        if info.is_file:
            if info.first_valid and info.first_valid.is_valid:
                self._render_file_preview(info.first_valid)
                self._can_convert = True
            else:
                self._set_status(info.first_valid.error if info.first_valid else "Invalid XML file.")
                self._set_preview_empty()
            return

        self._can_convert = info.xml_files > 0
        self._set_status(f"Folder selected: {info.xml_files} XML file(s) found.")
        if info.first_valid:
            self._render_file_preview(info.first_valid)
        else:
            self._set_preview_empty()
            self.preview_labels["Patrol ID"].set("Batch folder")

    def _render_file_preview(self, info: PreviewInfo) -> None:
        self._set_status("Ready to convert.")
        self.preview_labels["Patrol ID"].set(info.patrol_id or "—")
        self.preview_labels["Station"].set(info.station or "—")
        self.preview_labels["Dates"].set(" → ".join(part for part in (info.start_date, info.end_date) if part) or "—")
        self.preview_labels["Legs"].set(str(info.legs))
        self.preview_labels["Tracks"].set(str(info.tracks))
        self.preview_labels["Waypoints"].set(str(info.waypoints))
        self.preview_labels["Members"].set(", ".join(info.members) if info.members else "—")

    def _set_preview_empty(self) -> None:
        for value in self.preview_labels.values():
            value.set("—")

    def _set_status(self, message: str) -> None:
        self.status.set(message)

    def _update_convert_state(self) -> None:
        if self._can_convert and not self._worker:
            self.convert_button.state(["!disabled"])
        else:
            self.convert_button.state(["disabled"])

    def _start_conversion(self) -> None:
        source = Path(self.source_path.get().strip())
        output_text = self.output_path.get().strip()
        output_dir = Path(output_text) if output_text else None
        if output_dir is not None and not output_dir.exists():
            messagebox.showerror("Output folder not found", str(output_dir))
            return

        self.log.delete("1.0", "end")
        self._worker = threading.Thread(target=self._convert_worker, args=(source, output_dir, self.recursive.get()), daemon=True)
        self._worker.start()
        self._set_status("Converting...")
        self._update_convert_state()

    def _convert_worker(self, source: Path, output_dir: Path | None, recursive: bool) -> None:
        converted = 0
        failed = 0
        try:
            files = find_xml_files(source, recursive)
            if not files:
                self._events.put(("error", f"No XML files found in {source}"))
                return
            for xml_file in files:
                try:
                    output = None
                    if output_dir is not None:
                        output = output_dir / f"{xml_file.stem}.kml"
                    stats = convert_file(xml_file, output)
                except Exception as exc:  # noqa: BLE001 - batch continues after one bad file
                    failed += 1
                    self._events.put(("log", f"failed: {xml_file}: {exc}"))
                    continue
                converted += 1
                self._events.put(("log", f"converted: {stats.source} -> {stats.output} ({stats.tracks} tracks, {stats.waypoints} waypoints, {len(stats.warnings)} warnings)"))
                for warning in stats.warnings:
                    self._events.put(("log", f"warning: {stats.source.name}: {warning}"))
        finally:
            self._events.put(("done", f"Summary: {converted} converted, {failed} failed"))

    def _drain_events(self) -> None:
        while True:
            try:
                kind, message = self._events.get_nowait()
            except queue.Empty:
                break
            if kind == "log":
                self.log.insert("end", message + "\n")
                self.log.see("end")
            elif kind == "error":
                self.log.insert("end", "error: " + message + "\n")
                self.log.see("end")
                self._set_status(message)
            elif kind == "done":
                self.log.insert("end", message + "\n")
                self.log.see("end")
                self._set_status(message)
                self._worker = None
                self._update_convert_state()
        self.after(100, self._drain_events)


def main() -> None:
    app = SmartPatrolApp()
    app.mainloop()


if __name__ == "__main__":
    main()
```

**Step 4: Run GUI import test**

Run:

```bash
python -m pytest tests/test_gui_import.py -v
```

Expected: PASS.

**Step 5: Run full test suite**

Run:

```bash
python -m pytest -v
```

Expected: all tests PASS.

**Step 6: Manual GUI smoke check on Linux**

Run:

```bash
python -m smartpatrol_kml.gui
```

Expected:

- Window opens.
- Browse File can select `tests/fixtures/minimal_patrol.xml`.
- Preview shows `PATROL-001`, station, 0 tracks, 1 waypoint.
- Convert writes `.kml` and log summary.

If running in a headless environment, skip this manual step and note it in the final report.

**Step 7: Commit**

```bash
git add smartpatrol_kml/gui.py tests/test_gui_import.py
git commit -m "feat: add tkinter converter gui"
```

---

## Task 5: Add CLI entry conveniences for GUI

**Files:**

- Create: `run_gui.py`
- Modify: `README.md`
- Modify: `tests/test_gui_import.py`

**Step 1: Add root GUI launcher**

Create `run_gui.py`:

```python
#!/usr/bin/env python3
"""Launch the SMART Patrol XML to KML desktop GUI."""

from smartpatrol_kml.gui import main


if __name__ == "__main__":
    main()
```

This gives users and PyInstaller a simple stable entrypoint.

**Step 2: Add launcher import test**

Append to `tests/test_gui_import.py`:

```python
def test_run_gui_imports() -> None:
    import run_gui

    assert run_gui.main is not None
```

**Step 3: Run GUI tests**

Run:

```bash
python -m pytest tests/test_gui_import.py -v
```

Expected: PASS.

**Step 4: Update README GUI section**

Add after install section in `README.md`:

```markdown
## GUI

Launch the desktop interface:

```bash
python3 run_gui.py
```

The GUI can convert one XML file or a folder of XML files. Leave the output folder blank to write each `.kml` beside its source XML, matching the command-line behavior.
```

Add a Windows EXE section near the end:

```markdown
## Windows EXE

Windows builds are produced by GitHub Actions on a Windows runner. Run the `Build Windows EXE` workflow manually, or push a `v*` tag. Download `SMART-Patrol-XML-to-KML.exe` from the workflow artifacts.
```

**Step 5: Run tests**

Run:

```bash
python -m pytest -v
```

Expected: PASS.

**Step 6: Commit**

```bash
git add run_gui.py README.md tests/test_gui_import.py
git commit -m "docs: add gui launcher instructions"
```

---

## Task 6: Add Windows PyInstaller workflow

**Files:**

- Create: `.github/workflows/windows-exe.yml`

**Step 1: Create workflow**

Create `.github/workflows/windows-exe.yml`:

```yaml
name: Build Windows EXE

on:
  workflow_dispatch:
  push:
    tags:
      - "v*"

jobs:
  build-windows-exe:
    runs-on: windows-latest

    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: "pip"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          python -m pip install -r requirements.txt -r requirements-dev.txt

      - name: Run tests
        run: python -m pytest -v

      - name: Build GUI executable
        run: |
          pyinstaller --onefile --windowed --name SMART-Patrol-XML-to-KML run_gui.py

      - name: Smoke check artifact exists
        shell: pwsh
        run: |
          if (!(Test-Path "dist/SMART-Patrol-XML-to-KML.exe")) {
            throw "EXE artifact was not created"
          }

      - name: Upload EXE artifact
        uses: actions/upload-artifact@v4
        with:
          name: SMART-Patrol-XML-to-KML-windows
          path: dist/SMART-Patrol-XML-to-KML.exe
          if-no-files-found: error
```

**Step 2: Validate YAML file shape locally**

Run:

```bash
python - <<'PY'
from pathlib import Path
path = Path('.github/workflows/windows-exe.yml')
text = path.read_text(encoding='utf-8')
assert 'Build Windows EXE' in text
assert 'windows-latest' in text
assert 'pyinstaller --onefile --windowed' in text
assert 'actions/upload-artifact@v4' in text
print('workflow smoke ok')
PY
```

Expected:

```text
workflow smoke ok
```

**Step 3: Run tests**

Run:

```bash
python -m pytest -v
```

Expected: PASS.

**Step 4: Commit**

```bash
git add .github/workflows/windows-exe.yml
git commit -m "ci: build windows gui executable"
```

---

## Task 7: Polish README and release notes

**Files:**

- Modify: `README.md`
- Create: `docs/release-windows-exe.md`

**Step 1: Create Windows release doc**

Create `docs/release-windows-exe.md`:

```markdown
# Windows EXE Release Notes

## Build

The Windows executable is built by GitHub Actions.

Manual build:

1. Open the **Build Windows EXE** workflow in GitHub Actions.
2. Click **Run workflow**.
3. Download the `SMART-Patrol-XML-to-KML-windows` artifact.

Tag build:

```bash
git tag v0.1.0
git push origin v0.1.0
```

## Artifact

The workflow uploads:

```text
SMART-Patrol-XML-to-KML.exe
```

## Smoke Test on Windows

1. Double-click `SMART-Patrol-XML-to-KML.exe`.
2. Select a SMART patrol XML file.
3. Confirm preview metadata appears.
4. Click **Convert to KML**.
5. Confirm a `.kml` file is created beside the XML, or in the selected output folder.
6. Import the KML into ArcGIS Pro using **KML To Layer**.
```

**Step 2: Link release doc from README**

Add to README Windows EXE section:

```markdown
See `docs/release-windows-exe.md` for release and Windows smoke-test steps.
```

**Step 3: Run tests**

Run:

```bash
python -m pytest -v
```

Expected: PASS.

**Step 4: Commit**

```bash
git add README.md docs/release-windows-exe.md
git commit -m "docs: document windows exe release flow"
```

---

## Task 8: Final verification and cleanup

**Files:**

- No new files unless fixing issues.

**Step 1: Run full automated tests**

Run:

```bash
python -m pytest -v
```

Expected: all tests PASS.

**Step 2: Run CLI smoke test**

Run:

```bash
python smart_xml_to_kml.py tests/fixtures/minimal_patrol.xml -o /tmp/minimal-patrol.kml
```

Expected:

```text
converted: ...minimal_patrol.xml -> /tmp/minimal-patrol.kml (0 tracks, 1 waypoints, 0 warnings)
summary: 1 converted, 0 failed
```

**Step 3: Verify generated KML parses**

Run:

```bash
python - <<'PY'
from pathlib import Path
import xml.etree.ElementTree as ET
path = Path('/tmp/minimal-patrol.kml')
ET.parse(path)
print('kml parse ok')
PY
```

Expected:

```text
kml parse ok
```

**Step 4: Run GUI import smoke**

Run:

```bash
python - <<'PY'
import smartpatrol_kml.converter
import smartpatrol_kml.preview
import smartpatrol_kml.gui
import run_gui
print('imports ok')
PY
```

Expected:

```text
imports ok
```

**Step 5: Optional manual GUI launch**

Run only if a display server is available:

```bash
python run_gui.py
```

Expected: GUI launches and can preview/convert fixture.

**Step 6: Check git status**

Run:

```bash
git status --short
```

Expected: clean working tree.

**Step 7: Summarize**

Report:

- Tests run and pass/fail status.
- CLI smoke result.
- GUI smoke/import result.
- Whether manual GUI launch was done or skipped.
- Windows `.exe` build available via GitHub Actions after push/tag.

---

## Notes for Implementer

- Keep GUI callbacks small; conversion must stay in worker thread.
- Do not write KML during preview.
- Do not add map rendering in v1.
- Do not force an output directory; blank means beside XML.
- Preserve CLI behavior first; GUI depends on it.
- If PyInstaller cannot bundle Shapely on Windows, inspect the GitHub Actions log and add hidden imports or collect-binaries only as needed. Do not preemptively complicate the spec.
