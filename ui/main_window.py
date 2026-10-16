"""PyForge main application window: navigation + all screens."""
from __future__ import annotations

import os
import queue
import subprocess
import threading
from datetime import datetime
from pathlib import Path

import customtkinter as ctk
from PIL import Image

from core.asset_detector import AssetDetector
from core.build_manager import BuildManager, CompletedEvent, LogEvent, StageEvent
from core.build_report import BuildHistoryStore
from core.compatibility_analyzer import CompatibilityAnalyzer
from core.dependency_analyzer import DependencyAnalyzer
from core.entry_point_detector import EntryPointDetector
from core.environment_manager import EnvironmentManager
from core.project_scanner import ProjectScanner
from models.analysis_result import CompatibilityAnalysis, DependencyAnalysis
from models.build_result import BuildConfig, BuildStatus, ConsoleMode, OutputMode
from models.project import ScannedProject
from ui import theme
from ui.components.analysis_panel import AnalysisPanel
from ui.components.build_settings import BuildSettingsPanel
from ui.components.dialogs import AlertDialog, ConfirmDialog
from ui.components.log_panel import LogPanel
from ui.components.project_panel import ProjectPanel
from ui.components.sidebar import Sidebar
from utils.app_settings import AppSettings, load_settings, save_settings
from utils.filesystem import DEFAULT_SCAN_EXCLUDES, resource_path
from utils.logging_config import get_logger

logger = get_logger("main_window")

ASSETS_DIR = resource_path("assets", "icons")


class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        theme.apply_appearance()
        self.configure(fg_color=theme.BG_APP)

        self.title("PyForge — Python to Windows EXE | Rivan Security")
        self.geometry("1280x820")
        self.minsize(1040, 680)

        icon_path = ASSETS_DIR / "app.ico"
        if icon_path.exists():
            try:
                self.iconbitmap(str(icon_path))
            except Exception:  # noqa: BLE001 - icon failures must never block startup
                logger.warning("Could not set window icon from %s", icon_path)

        self.settings: AppSettings = load_settings()

        self.scanner = ProjectScanner(excludes=frozenset(self.settings.scanner_excludes))
        self.entry_detector = EntryPointDetector()
        self.dep_analyzer = DependencyAnalyzer()
        self.compat_analyzer = CompatibilityAnalyzer()
        self.asset_detector = AssetDetector()
        self.env_manager = EnvironmentManager()
        self.build_manager = BuildManager()
        self.history_store = BuildHistoryStore()

        self.current_project: ScannedProject | None = None
        self.current_deps: DependencyAnalysis | None = None
        self.current_compat: CompatibilityAnalysis | None = None
        self.last_build_result = None

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.content = ctk.CTkFrame(self, fg_color=theme.BG_APP, corner_radius=0)
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        # Views must exist before the sidebar is built: building the sidebar
        # triggers an initial on_navigate("Builder") callback synchronously.
        self._views: dict[str, ctk.CTkFrame] = {}
        self._build_builder_view()
        self._build_history_view()
        self._build_settings_view()
        self._build_about_view()

        self.sidebar = Sidebar(self, on_navigate=self._navigate)
        self.sidebar.grid(row=0, column=0, sticky="nsw")

        self._navigate("Builder")

        self._check_environment()

    # -- navigation -----------------------------------------------------------

    def _navigate(self, name: str) -> None:
        for view_name, frame in self._views.items():
            if view_name == name:
                frame.grid(row=0, column=0, sticky="nsew")
            else:
                frame.grid_forget()
        if name == "Build History":
            self._refresh_history()

    # -- Builder view -----------------------------------------------------------

    def _build_builder_view(self) -> None:
        view = ctk.CTkFrame(self.content, fg_color="transparent")
        view.grid_columnconfigure(0, weight=1, uniform="col")
        view.grid_columnconfigure(1, weight=1, uniform="col")
        view.grid_rowconfigure(0, weight=0)
        view.grid_rowconfigure(1, weight=1)
        view.grid_rowconfigure(2, weight=1)
        self._views["Builder"] = view

        self.env_banner = ctk.CTkLabel(
            view, text="", font=theme.font(11), text_color=theme.TEXT_MUTED, anchor="w"
        )
        self.env_banner.grid(row=0, column=0, columnspan=2, sticky="ew", padx=theme.SPACING_LG, pady=(theme.SPACING_LG, 0))

        pad = theme.SPACING_MD
        self.project_panel = ProjectPanel(
            view, on_browse=self._browse_project, on_rescan=self._rescan_project, on_clear=self._clear_project
        )
        self.project_panel.grid(row=1, column=0, sticky="nsew", padx=(theme.SPACING_LG, pad), pady=pad)

        self.analysis_panel = AnalysisPanel(view)
        self.analysis_panel.grid(row=1, column=1, sticky="nsew", padx=(pad, theme.SPACING_LG), pady=pad)
        self.analysis_panel.show_empty()

        left_bottom = ctk.CTkFrame(view, fg_color="transparent")
        left_bottom.grid(row=2, column=0, sticky="nsew", padx=(theme.SPACING_LG, pad), pady=(0, theme.SPACING_LG))
        left_bottom.grid_rowconfigure(1, weight=1)
        left_bottom.grid_columnconfigure(0, weight=1)

        self._build_controls_row(left_bottom)
        self.build_settings = BuildSettingsPanel(left_bottom)
        self.build_settings.grid(row=1, column=0, sticky="nsew", pady=(theme.SPACING_SM, 0))

        self.log_panel = LogPanel(view)
        self.log_panel.grid(row=2, column=1, sticky="nsew", padx=(pad, theme.SPACING_LG), pady=(0, theme.SPACING_LG))

    def _build_controls_row(self, parent) -> None:
        row = ctk.CTkFrame(parent, fg_color=theme.BG_PANEL, corner_radius=theme.RADIUS)
        row.grid(row=0, column=0, sticky="ew")

        self.analyze_btn = ctk.CTkButton(
            row, text="Analyze Project", font=theme.font(12, "bold"), fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_HOVER, text_color=theme.TEXT_ON_ACCENT, command=self._analyze_project,
        )
        self.analyze_btn.pack(side="left", padx=theme.SPACING_SM, pady=theme.SPACING_SM)

        self.build_btn = ctk.CTkButton(
            row, text="Build Executable", font=theme.font(12, "bold"), fg_color=theme.SUCCESS,
            hover_color="#3BBF6C", text_color=theme.NAVY_DEEP, command=self._start_build,
        )
        self.build_btn.pack(side="left", padx=(0, theme.SPACING_SM), pady=theme.SPACING_SM)

        self.cancel_btn = ctk.CTkButton(
            row, text="Cancel Build", font=theme.font(12), fg_color="transparent", border_width=1,
            border_color=theme.ERROR, text_color=theme.ERROR, hover_color=theme.ERROR_BG,
            state="disabled", command=self._cancel_build,
        )
        self.cancel_btn.pack(side="left", padx=(0, theme.SPACING_SM), pady=theme.SPACING_SM)

        self.open_output_btn = ctk.CTkButton(
            row, text="Open Output Folder", font=theme.font(12), fg_color="transparent", border_width=1,
            border_color=theme.BORDER, text_color=theme.TEXT_SECONDARY, hover_color=theme.BG_PANEL_RAISED,
            state="disabled", command=self._open_output_folder,
        )
        self.open_output_btn.pack(side="left", padx=(0, theme.SPACING_SM), pady=theme.SPACING_SM)

        self.view_report_btn = ctk.CTkButton(
            row, text="View Build Report", font=theme.font(12), fg_color="transparent", border_width=1,
            border_color=theme.BORDER, text_color=theme.TEXT_SECONDARY, hover_color=theme.BG_PANEL_RAISED,
            state="disabled", command=self._view_build_report,
        )
        self.view_report_btn.pack(side="left", padx=(0, theme.SPACING_SM), pady=theme.SPACING_SM)

        self.run_exe_btn = ctk.CTkButton(
            row, text="Run Executable", font=theme.font(12), fg_color="transparent", border_width=1,
            border_color=theme.WARNING, text_color=theme.WARNING, hover_color=theme.WARNING_BG,
            state="disabled", command=self._run_executable,
        )
        self.run_exe_btn.pack(side="left", padx=(0, theme.SPACING_SM), pady=theme.SPACING_SM)

    # -- environment check ------------------------------------------------------

    def _check_environment(self) -> None:
        def work():
            interpreter = self.env_manager.default_interpreter()
            if self.settings.custom_interpreter:
                interpreter = Path(self.settings.custom_interpreter)
            info = self.env_manager.inspect(interpreter)
            self.after(0, lambda: self._show_environment_info(info))

        threading.Thread(target=work, daemon=True).start()

    def _show_environment_info(self, info) -> None:
        if info.has_pyinstaller:
            self.env_banner.configure(
                text=f"Build environment: {info.path} ({info.version}) · PyInstaller {info.pyinstaller_version}",
                text_color=theme.TEXT_MUTED,
            )
        else:
            self.env_banner.configure(
                text=f"PyInstaller was not found for {info.path} ({info.version}). "
                     "Go to Settings to install it before building.",
                text_color=theme.WARNING,
            )

    # -- project scanning ------------------------------------------------------

    def _browse_project(self, path: Path) -> None:
        self._run_scan(path)

    def _rescan_project(self) -> None:
        if self.current_project is not None:
            self._run_scan(self.current_project.root)

    def _clear_project(self) -> None:
        self.current_project = None
        self.current_deps = None
        self.current_compat = None
        self.analysis_panel.show_empty()

    def _run_scan(self, path: Path) -> None:
        self.project_panel.show_scanning(path)
        self.analyze_btn.configure(state="disabled")
        result_queue: "queue.Queue" = queue.Queue()

        def work():
            try:
                project = self.scanner.scan(path)
                project.entry_point_candidates = self.entry_detector.detect(project.python_files)
                result_queue.put(("done", project))
            except Exception as exc:  # noqa: BLE001
                logger.exception("Scan failed")
                result_queue.put(("error", str(exc)))

        threading.Thread(target=work, daemon=True).start()
        self._poll_scan(result_queue)

    def _poll_scan(self, result_queue) -> None:
        try:
            status, payload = result_queue.get_nowait()
        except queue.Empty:
            self.after(100, lambda: self._poll_scan(result_queue))
            return

        self.analyze_btn.configure(state="normal")

        if status == "error":
            AlertDialog.show(self, "Scan Failed", payload, kind="error")
            return

        project: ScannedProject = payload
        self.current_project = project
        self.current_deps = None
        self.current_compat = None

        self.project_panel.set_project(project, datetime.now().strftime("%H:%M:%S"))
        self.build_settings.set_project_root(project.root)
        self.build_settings.set_entry_candidates(project.entry_point_candidates, project.root)
        self.analysis_panel.show_empty()

        if project.scan_errors:
            AlertDialog.show(
                self, "Scan Completed With Warnings",
                "Some items could not be scanned:\n\n" + "\n".join(project.scan_errors[:10]),
                kind="warning",
            )

    # -- analysis ---------------------------------------------------------------

    def _analyze_project(self) -> None:
        if self.current_project is None:
            AlertDialog.show(self, "No Project Selected", "Select and scan a project folder first.", kind="warning")
            return

        project = self.current_project
        result_queue: "queue.Queue" = queue.Queue()

        def work():
            try:
                deps = self.dep_analyzer.analyze(project.root, project.python_files, project.manifests)
                compat = self.compat_analyzer.analyze(project)
                mappings = self.asset_detector.suggest_mappings(project.root, project.assets)
                result_queue.put(("done", deps, compat, mappings))
            except Exception as exc:  # noqa: BLE001
                logger.exception("Analysis failed")
                result_queue.put(("error", str(exc), None, None))

        self.analyze_btn.configure(state="disabled", text="Analyzing…")
        threading.Thread(target=work, daemon=True).start()
        self._poll_analysis(result_queue)

    def _poll_analysis(self, result_queue) -> None:
        try:
            item = result_queue.get_nowait()
        except queue.Empty:
            self.after(100, lambda: self._poll_analysis(result_queue))
            return

        self.analyze_btn.configure(state="normal", text="Analyze Project")
        status = item[0]
        if status == "error":
            AlertDialog.show(self, "Analysis Failed", item[1], kind="error")
            return

        _, deps, compat, mappings = item
        self.current_deps = deps
        self.current_compat = compat
        self.analysis_panel.show_analysis(compat, deps, mappings=mappings, on_add_mapping=self._add_suggested_mapping)

    def _add_suggested_mapping(self, mapping) -> None:
        self.build_settings.add_data_mapping(mapping.source, mapping.dest_in_bundle)

    # -- build --------------------------------------------------------------

    def _start_build(self) -> None:
        if self.current_project is None:
            AlertDialog.show(self, "No Project Selected", "Select and scan a project folder first.", kind="warning")
            return
        if self.build_manager.is_running:
            AlertDialog.show(self, "Build In Progress", "A build is already running.", kind="warning")
            return

        entry_point = self.build_settings.get_entry_point_path()
        if entry_point is None:
            AlertDialog.show(self, "Entry Point Required", "Select a valid entry-point Python file.", kind="warning")
            return

        app_name = self.build_settings.get_app_name()
        output_dir = self.build_settings.get_output_dir()
        if output_dir is None:
            AlertDialog.show(self, "Output Directory Required", "Choose an output directory.", kind="warning")
            return

        icon_path = self.build_settings.get_icon_path()

        config = BuildConfig(
            project_root=self.current_project.root,
            entry_point=entry_point,
            app_name=app_name,
            output_dir=output_dir,
            output_mode=OutputMode.ONE_FILE if self.build_settings.output_mode_var.get() == "one_file" else OutputMode.ONE_FOLDER,
            console_mode=ConsoleMode.CONSOLE if self.build_settings.console_mode_var.get() == "console" else ConsoleMode.WINDOWED,
            icon_path=icon_path,
            additional_data=list(self.build_settings.additional_data),
            hidden_imports=list(self.build_settings.hidden_imports),
            clean_build=self.build_settings.clean_build_var.get(),
            use_upx=self.build_settings.upx_var.get(),
            debug_logging=self.build_settings.debug_var.get(),
            interpreter=Path(self.settings.custom_interpreter) if self.settings.custom_interpreter else None,
        )

        existing_exe = (
            output_dir / f"{app_name}.exe" if config.output_mode == OutputMode.ONE_FILE
            else output_dir / app_name / f"{app_name}.exe"
        )
        if existing_exe.exists():
            if not ConfirmDialog.ask(
                self, "Overwrite Existing Output?",
                f"{existing_exe} already exists and will be overwritten by this build.",
                confirm_text="Overwrite", danger=True,
            ):
                return

        errors = self.build_manager.start(config)
        if errors:
            AlertDialog.show(self, "Cannot Start Build", "\n".join(errors), kind="error")
            return

        self.log_panel.reset()
        self.build_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.open_output_btn.configure(state="disabled")
        self.view_report_btn.configure(state="disabled")
        self.run_exe_btn.configure(state="disabled")

        self.after(100, self._poll_build_events)

    def _poll_build_events(self) -> None:
        while True:
            try:
                event = self.build_manager.event_queue.get_nowait()
            except queue.Empty:
                break
            if isinstance(event, StageEvent):
                self.log_panel.set_stage(event.stage)
            elif isinstance(event, LogEvent):
                self.log_panel.append_log(event.stream, event.text)
            elif isinstance(event, CompletedEvent):
                self._on_build_completed(event.result)

        self.log_panel.tick_elapsed()
        if self.build_manager.is_running:
            self.after(150, self._poll_build_events)

    def _on_build_completed(self, result) -> None:
        self.last_build_result = result
        self.log_panel.show_result(result)
        self.build_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
        self.view_report_btn.configure(state="normal")
        if result.status == BuildStatus.SUCCESS:
            self.open_output_btn.configure(state="normal")
            self.run_exe_btn.configure(state="normal")

    def _cancel_build(self) -> None:
        self.build_manager.cancel()
        self.cancel_btn.configure(state="disabled")

    def _open_output_folder(self) -> None:
        if self.last_build_result is None or self.last_build_result.output_path is None:
            return
        target = self.last_build_result.output_path
        folder = target if target.is_dir() else target.parent
        if folder.exists():
            os.startfile(str(folder))  # noqa: S606 - opening a user-chosen local folder

    def _view_build_report(self) -> None:
        if self.last_build_result is None:
            return
        from core.build_report import generate_report
        import json as _json
        report = generate_report(self.last_build_result)
        AlertDialog.show(self, "Build Report", _json.dumps(report, indent=2), kind="info")

    def _run_executable(self) -> None:
        if self.last_build_result is None or self.last_build_result.output_path is None:
            return
        exe_path = self.last_build_result.output_path
        if exe_path.is_dir():
            exe_path = exe_path / f"{self.last_build_result.config.app_name}.exe"
        if not exe_path.exists():
            AlertDialog.show(self, "Executable Not Found", f"{exe_path} does not exist.", kind="error")
            return

        confirmed = ConfirmDialog.ask(
            self, "Run This Executable?",
            f"This will run {exe_path.name}, which executes code built from your project. "
            "Only do this if you trust the project's source code.",
            confirm_text="Run", danger=True,
        )
        if confirmed:
            try:
                subprocess.Popen([str(exe_path)], cwd=str(exe_path.parent))
            except OSError as exc:
                AlertDialog.show(self, "Could Not Launch", str(exc), kind="error")

    # -- Build History view -----------------------------------------------------

    def _build_history_view(self) -> None:
        view = ctk.CTkFrame(self.content, fg_color="transparent")
        self._views["Build History"] = view

        header = ctk.CTkFrame(view, fg_color="transparent")
        header.pack(fill="x", padx=theme.SPACING_LG, pady=(theme.SPACING_LG, theme.SPACING_SM))
        ctk.CTkLabel(header, text="Build History", font=theme.font(20, "bold"), text_color=theme.TEXT_PRIMARY).pack(side="left")
        ctk.CTkButton(
            header, text="Refresh", width=90, fg_color="transparent", border_width=1,
            border_color=theme.BORDER, text_color=theme.TEXT_SECONDARY, hover_color=theme.BG_PANEL_RAISED,
            command=self._refresh_history,
        ).pack(side="right")

        self.history_scroll = ctk.CTkScrollableFrame(view, fg_color="transparent")
        self.history_scroll.pack(fill="both", expand=True, padx=theme.SPACING_LG, pady=(0, theme.SPACING_LG))

    def _refresh_history(self) -> None:
        for child in self.history_scroll.winfo_children():
            child.destroy()

        rows = self.history_store.list_builds()
        if not rows:
            ctk.CTkLabel(
                self.history_scroll, text="No builds yet. Completed builds will appear here.",
                font=theme.font(13), text_color=theme.TEXT_MUTED,
            ).pack(pady=theme.SPACING_LG)
            return

        for row in rows:
            self._add_history_row(row)

    def _add_history_row(self, row) -> None:
        status = row["status"]
        color, _bg = theme.SEVERITY_COLORS.get(
            {"success": "success", "failed": "error", "cancelled": "warning", "running": "info", "pending": "info"}.get(status, "info"),
            (theme.TEXT_MUTED, theme.BG_PANEL),
        )

        card = ctk.CTkFrame(self.history_scroll, fg_color=theme.BG_PANEL, corner_radius=theme.RADIUS)
        card.pack(fill="x", pady=4)

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=theme.SPACING_MD, pady=(theme.SPACING_SM, 0))
        ctk.CTkLabel(top, text=row["app_name"], font=theme.font(14, "bold"), text_color=theme.TEXT_PRIMARY).pack(side="left")
        ctk.CTkLabel(top, text=status.upper(), font=theme.font(11, "bold"), text_color=color).pack(side="right")

        ctk.CTkLabel(
            card, text=f"{row['project_path']}", font=theme.font(11), text_color=theme.TEXT_SECONDARY, anchor="w",
        ).pack(fill="x", padx=theme.SPACING_MD)

        meta = (
            f"{row['started_at']}  ·  {row['duration_seconds']:.1f}s  ·  "
            f"{row['output_mode']}, {row['console_mode']}  ·  Python {row['python_version'] or '?'}  ·  "
            f"PyInstaller {row['pyinstaller_version'] or '?'}"
        )
        ctk.CTkLabel(card, text=meta, font=theme.font(10), text_color=theme.TEXT_MUTED, anchor="w").pack(
            fill="x", padx=theme.SPACING_MD, pady=(0, theme.SPACING_SM)
        )

        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="x", padx=theme.SPACING_MD, pady=(0, theme.SPACING_SM))

        def make_button(text, cmd, enabled=True):
            ctk.CTkButton(
                actions, text=text, width=120, height=26, font=theme.font(11), fg_color="transparent",
                border_width=1, border_color=theme.BORDER, text_color=theme.TEXT_SECONDARY,
                hover_color=theme.BG_PANEL_RAISED, state="normal" if enabled else "disabled", command=cmd,
            ).pack(side="left", padx=(0, theme.SPACING_SM))

        output_path = Path(row["output_path"]) if row["output_path"] else None
        log_path = Path(row["log_path"]) if row["log_path"] else None
        report_path = Path(row["report_path"]) if row["report_path"] else None

        make_button("Open Output", lambda p=output_path: self._open_path(p), enabled=bool(output_path and output_path.exists()))
        make_button("Open Log", lambda p=log_path: self._open_path(p), enabled=bool(log_path and log_path.exists()))
        make_button("View Report", lambda p=report_path: self._open_path(p), enabled=bool(report_path and report_path.exists()))
        make_button("Remove Entry", lambda rid=row["id"]: self._remove_history_entry(rid))

    def _open_path(self, path: Path | None) -> None:
        if path is None:
            return
        target = path if path.is_dir() else path
        try:
            os.startfile(str(target))  # noqa: S606
        except OSError as exc:
            AlertDialog.show(self, "Could Not Open", str(exc), kind="error")

    def _remove_history_entry(self, build_id: str) -> None:
        if ConfirmDialog.ask(
            self, "Remove History Entry?",
            "This removes the entry from Build History only. Build artifacts and logs on disk "
            "are not deleted.",
            confirm_text="Remove",
        ):
            self.history_store.remove_build(build_id)
            self._refresh_history()

    # -- Settings view -----------------------------------------------------------

    def _build_settings_view(self) -> None:
        view = ctk.CTkFrame(self.content, fg_color="transparent")
        self._views["Settings"] = view

        ctk.CTkLabel(view, text="Settings", font=theme.font(20, "bold"), text_color=theme.TEXT_PRIMARY).pack(
            anchor="w", padx=theme.SPACING_LG, pady=(theme.SPACING_LG, theme.SPACING_MD)
        )

        panel = ctk.CTkFrame(view, fg_color=theme.BG_PANEL, corner_radius=theme.RADIUS)
        panel.pack(fill="both", expand=True, padx=theme.SPACING_LG, pady=(0, theme.SPACING_LG))

        scroll = ctk.CTkScrollableFrame(panel, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=theme.SPACING_MD, pady=theme.SPACING_MD)

        def section(text):
            ctk.CTkLabel(scroll, text=text, font=theme.font(12, "bold"), text_color=theme.TEXT_SECONDARY, anchor="w").pack(
                fill="x", pady=(theme.SPACING_MD, 4)
            )

        section("Appearance")
        self.appearance_var = ctk.StringVar(value=self.settings.appearance)
        ctk.CTkOptionMenu(
            scroll, variable=self.appearance_var, values=["dark", "light"],
            command=self._on_appearance_change, fg_color=theme.BG_INPUT, button_color=theme.ACCENT_MUTED,
            button_hover_color=theme.ACCENT, text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w")

        section("Default Output Mode")
        self.default_mode_var = ctk.StringVar(value=self.settings.default_output_mode)
        ctk.CTkOptionMenu(
            scroll, variable=self.default_mode_var, values=["one_file", "one_folder"],
            fg_color=theme.BG_INPUT, button_color=theme.ACCENT_MUTED, button_hover_color=theme.ACCENT,
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w")

        section("Default Console Mode")
        self.default_console_var = ctk.StringVar(value=self.settings.default_console_mode)
        ctk.CTkOptionMenu(
            scroll, variable=self.default_console_var, values=["console", "windowed"],
            fg_color=theme.BG_INPUT, button_color=theme.ACCENT_MUTED, button_hover_color=theme.ACCENT,
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w")

        section("Build Log Verbosity")
        self.log_verbosity_var = ctk.StringVar(value=self.settings.log_verbosity)
        ctk.CTkOptionMenu(
            scroll, variable=self.log_verbosity_var, values=["info", "debug"],
            fg_color=theme.BG_INPUT, button_color=theme.ACCENT_MUTED, button_hover_color=theme.ACCENT,
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w")

        section("Scanner Exclusions (comma-separated directory names)")
        self.excludes_entry = ctk.CTkEntry(scroll, fg_color=theme.BG_INPUT, text_color=theme.TEXT_PRIMARY, border_color=theme.BORDER)
        self.excludes_entry.pack(fill="x")
        self.excludes_entry.insert(0, ", ".join(self.settings.scanner_excludes))

        section("Custom Python Interpreter (optional — blank uses PyForge's own)")
        self.interpreter_entry = ctk.CTkEntry(scroll, fg_color=theme.BG_INPUT, text_color=theme.TEXT_PRIMARY, border_color=theme.BORDER)
        self.interpreter_entry.pack(fill="x")
        self.interpreter_entry.insert(0, self.settings.custom_interpreter)

        section("Build Environment")
        env_row = ctk.CTkFrame(scroll, fg_color="transparent")
        env_row.pack(fill="x")
        self.settings_env_label = ctk.CTkLabel(env_row, text="Checking…", font=theme.font(11), text_color=theme.TEXT_MUTED)
        self.settings_env_label.pack(side="left")
        ctk.CTkButton(
            env_row, text="Install / Upgrade PyInstaller", fg_color=theme.ACCENT_MUTED, text_color=theme.ACCENT,
            hover_color=theme.ACCENT, command=self._install_pyinstaller,
        ).pack(side="right")
        self._refresh_settings_env_label()

        section("Build History")
        ctk.CTkButton(
            scroll, text="Clear All Build History", fg_color="transparent", border_width=1,
            border_color=theme.ERROR, text_color=theme.ERROR, hover_color=theme.ERROR_BG,
            command=self._clear_all_history,
        ).pack(anchor="w")

        button_row = ctk.CTkFrame(view, fg_color="transparent")
        button_row.pack(fill="x", padx=theme.SPACING_LG, pady=(0, theme.SPACING_LG))
        ctk.CTkButton(
            button_row, text="Save Settings", fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
            text_color=theme.TEXT_ON_ACCENT, command=self._save_settings,
        ).pack(side="left")
        ctk.CTkButton(
            button_row, text="Reset to Defaults", fg_color="transparent", border_width=1,
            border_color=theme.BORDER, text_color=theme.TEXT_SECONDARY, hover_color=theme.BG_PANEL_RAISED,
            command=self._reset_settings,
        ).pack(side="left", padx=(theme.SPACING_SM, 0))

    def _refresh_settings_env_label(self) -> None:
        def work():
            interpreter = Path(self.interpreter_entry.get().strip()) if self.interpreter_entry.get().strip() else self.env_manager.default_interpreter()
            try:
                info = self.env_manager.inspect(interpreter)
            except Exception as exc:  # noqa: BLE001
                self.after(0, lambda: self.settings_env_label.configure(text=f"Could not inspect interpreter: {exc}", text_color=theme.ERROR))
                return
            if info.has_pyinstaller:
                text = f"{info.path} ({info.version}) · PyInstaller {info.pyinstaller_version} installed"
                color = theme.SUCCESS
            else:
                text = f"{info.path} ({info.version}) · PyInstaller not installed"
                color = theme.WARNING
            self.after(0, lambda: self.settings_env_label.configure(text=text, text_color=color))

        threading.Thread(target=work, daemon=True).start()

    def _install_pyinstaller(self) -> None:
        interpreter = Path(self.interpreter_entry.get().strip()) if self.interpreter_entry.get().strip() else self.env_manager.default_interpreter()
        if not ConfirmDialog.ask(
            self, "Install PyInstaller?",
            f"This runs pip to install PyInstaller into {interpreter}. Package installation can "
            "execute code from that package's build process. Continue?",
            confirm_text="Install", danger=True,
        ):
            return
        self.settings_env_label.configure(text="Installing…", text_color=theme.ACCENT)

        def work():
            ok, output = self.env_manager.ensure_pyinstaller(interpreter)
            def done():
                self._refresh_settings_env_label()
                if not ok:
                    AlertDialog.show(self, "Install Failed", output[-1500:], kind="error")
            self.after(0, done)

        threading.Thread(target=work, daemon=True).start()

    def _on_appearance_change(self, value: str) -> None:
        ctk.set_appearance_mode(value)

    def _save_settings(self) -> None:
        excludes = [e.strip() for e in self.excludes_entry.get().split(",") if e.strip()]
        self.settings = AppSettings(
            appearance=self.appearance_var.get(),
            default_output_dir=self.settings.default_output_dir,
            default_output_mode=self.default_mode_var.get(),
            default_console_mode=self.default_console_var.get(),
            log_verbosity=self.log_verbosity_var.get(),
            scanner_excludes=excludes or sorted(DEFAULT_SCAN_EXCLUDES),
            custom_interpreter=self.interpreter_entry.get().strip(),
        )
        save_settings(self.settings)
        self.scanner = ProjectScanner(excludes=frozenset(self.settings.scanner_excludes))
        AlertDialog.show(self, "Settings Saved", "Your settings have been saved.", kind="success")

    def _reset_settings(self) -> None:
        if not ConfirmDialog.ask(self, "Reset Settings?", "This restores all settings to their defaults.", confirm_text="Reset", danger=True):
            return
        self.settings = AppSettings()
        save_settings(self.settings)
        for child in self._views["Settings"].winfo_children():
            child.destroy()
        self._build_settings_view()
        self._navigate("Settings")

    def _clear_all_history(self) -> None:
        if not ConfirmDialog.ask(
            self, "Clear Build History?",
            "This removes all history entries. Build artifacts and logs on disk are not deleted.",
            confirm_text="Clear All", danger=True,
        ):
            return
        for row in self.history_store.list_builds(limit=10_000):
            self.history_store.remove_build(row["id"])
        AlertDialog.show(self, "History Cleared", "Build history has been cleared.", kind="success")

    # -- About view -----------------------------------------------------------

    def _build_about_view(self) -> None:
        view = ctk.CTkFrame(self.content, fg_color="transparent")
        self._views["About"] = view

        panel = ctk.CTkFrame(view, fg_color=theme.BG_PANEL, corner_radius=theme.RADIUS)
        panel.pack(fill="both", expand=True, padx=theme.SPACING_LG, pady=theme.SPACING_LG)

        center = ctk.CTkFrame(panel, fg_color="transparent")
        center.pack(expand=True)

        logo_path = ASSETS_DIR / "rivan_logo.png"
        if logo_path.exists():
            img = Image.open(logo_path)
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(96, 96))
            ctk.CTkLabel(center, image=ctk_img, text="").pack(pady=(0, theme.SPACING_MD))

        ctk.CTkLabel(center, text="PyForge", font=theme.font(28, "bold"), text_color=theme.TEXT_PRIMARY).pack()
        ctk.CTkLabel(center, text="Python-to-Windows-EXE Builder", font=theme.font(14), text_color=theme.TEXT_SECONDARY).pack(pady=(0, theme.SPACING_MD))
        ctk.CTkLabel(center, text="Built and maintained by Rivan Security Inc", font=theme.font(12, "bold"), text_color=theme.ACCENT).pack()
        ctk.CTkLabel(center, text="Version 1.0.0", font=theme.font(11), text_color=theme.TEXT_MUTED).pack(pady=(2, theme.SPACING_LG))

        body = (
            "PyForge scans a Python project folder, flags likely packaging concerns, and "
            "builds a Windows executable using PyInstaller — without executing your project's "
            "source code during analysis.\n\n"
            "A static scan and a successful build are not a guarantee of correct runtime "
            "behavior. Review the Compatibility Analysis findings and test the built "
            "executable before distributing it."
        )
        ctk.CTkLabel(
            center, text=body, font=theme.font(12), text_color=theme.TEXT_SECONDARY,
            wraplength=560, justify="center",
        ).pack()
