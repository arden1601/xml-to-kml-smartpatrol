from __future__ import annotations

import queue
import threading
from pathlib import Path
from typing import Any

from smartpatrol_kml.converter import convert_file, find_xml_files
from smartpatrol_kml.preview import PathPreview, PreviewInfo, preview_path


def _load_tkinter() -> tuple[Any, Any, Any, Any]:
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
    except ImportError as exc:  # pragma: no cover - depends on local Python build
        raise RuntimeError(
            "Tkinter is not available in this Python installation. "
            "Use a Python build with Tk support, or run the Windows EXE built by GitHub Actions."
        ) from exc
    return tk, filedialog, messagebox, ttk


class SmartPatrolApp:
    def __init__(self) -> None:
        self.tk, self.filedialog, self.messagebox, self.ttk = _load_tkinter()
        self.root = self.tk.Tk()
        self.root.title("SMART Patrol XML → KML")
        self.root.geometry("920x680")
        self.root.minsize(820, 600)

        self.source_path = self.tk.StringVar(master=self.root)
        self.output_path = self.tk.StringVar(master=self.root)
        self.recursive = self.tk.BooleanVar(master=self.root, value=False)
        self.status = self.tk.StringVar(master=self.root, value="Select an XML file or folder.")
        self._can_convert = False
        self._events: queue.Queue[tuple[str, str]] = queue.Queue()
        self._worker: threading.Thread | None = None

        self._configure_style()
        self._build_ui()
        self.root.after(100, self._drain_events)

    def mainloop(self) -> None:
        self.root.mainloop()

    def _configure_style(self) -> None:
        self.root.configure(bg="#111820")
        style = self.ttk.Style(self.root)
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
        ttk = self.ttk
        root = ttk.Frame(self.root, padding=18)
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
        self.preview_labels: dict[str, Any] = {}
        for index, key in enumerate(("Patrol ID", "Station", "Dates", "Legs", "Tracks", "Waypoints", "Members"), start=1):
            ttk.Label(preview_frame, text=f"{key}:", style="Panel.TLabel").grid(row=index, column=0, sticky="nw", pady=3)
            value = self.tk.StringVar(master=self.root, value="—")
            self.preview_labels[key] = value
            ttk.Label(preview_frame, textvariable=value, style="Panel.TLabel", wraplength=320).grid(row=index, column=1, sticky="w", pady=3)

        log_frame = ttk.Frame(body, style="Panel.TFrame", padding=14)
        log_frame.grid(row=0, column=1, sticky="nsew", padx=(9, 0))
        log_frame.rowconfigure(1, weight=1)
        log_frame.columnconfigure(0, weight=1)
        ttk.Label(log_frame, text="Log", style="Panel.TLabel", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 10))
        self.log = self.tk.Text(log_frame, height=16, bg="#0d141b", fg="#d8e2ea", insertbackground="#d8e2ea", relief="flat", wrap="word")
        self.log.grid(row=1, column=0, sticky="nsew")

        footer = ttk.Frame(root)
        footer.grid(row=4, column=0, sticky="ew", pady=(16, 0))
        footer.columnconfigure(0, weight=1)
        self.convert_button = ttk.Button(footer, text="Convert to KML", style="Accent.TButton", command=self._start_conversion)
        self.convert_button.grid(row=0, column=1, sticky="e")
        self.convert_button.state(["disabled"])

    def _browse_file(self) -> None:
        filename = self.filedialog.askopenfilename(title="Select SMART patrol XML", filetypes=[("XML files", "*.xml"), ("All files", "*.*")])
        if filename:
            self.source_path.set(filename)
            self.recursive_check.state(["disabled"])
            self._refresh_preview()

    def _browse_folder(self) -> None:
        dirname = self.filedialog.askdirectory(title="Select folder containing SMART patrol XML files")
        if dirname:
            self.source_path.set(dirname)
            self.recursive_check.state(["!disabled"])
            self._refresh_preview()

    def _choose_output(self) -> None:
        dirname = self.filedialog.askdirectory(title="Select output folder")
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
            self.messagebox.showerror("Output folder not found", str(output_dir))
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
        self.root.after(100, self._drain_events)


def main() -> None:
    app = SmartPatrolApp()
    app.mainloop()


if __name__ == "__main__":
    main()
