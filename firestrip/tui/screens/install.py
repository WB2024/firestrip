from __future__ import annotations

from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Log,
    Rule,
)

from ...core.exceptions import ADBCommandError
from . import FirestripScreen


class InstallScreen(FirestripScreen):
    """APK manager: install from local path or uninstall a package from the device."""

    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("r", "refresh_packages", "Refresh list"),
    ]

    # ── Sorting state ─────────────────────────────────────────────────────────
    _COLS: tuple[str, ...] = ("name", "package", "type")
    _sort_col: str = "name"
    _sort_reverse: bool = False
    # Cached after ADB load: list of (display_name, package, type_str)
    _cached_rows: list[tuple[str, str, str]]

    def compose(self) -> ComposeResult:
        yield Header()
        with ScrollableContainer(id="content"):
            # ── Install ──────────────────────────────────────────────────────
            yield Label("[bold]Install APK[/bold] — enter a local file path")
            yield Input(
                placeholder="/path/to/app.apk",
                id="apk-path",
                tooltip="Full path to the APK file on this machine",
            )
            yield Button("Install APK", id="btn-install", variant="primary")
            yield Label("", id="install-status")
            yield Log(id="install-log", auto_scroll=True, max_lines=6)

            yield Rule()

            # ── Uninstall ────────────────────────────────────────────────────
            yield Label("[bold]Uninstall package[/bold] — select from list or type a package name")
            yield Input(
                placeholder="com.example.app",
                id="pkg-name",
                tooltip="Package name to uninstall",
            )
            yield Checkbox("Keep app data after uninstall", id="chk-keep-data", value=False)
            with Horizontal(id="uninstall-buttons"):
                yield Button("Uninstall", id="btn-uninstall", variant="error")
                yield Button("↻ Refresh", id="btn-refresh", variant="default")
            yield Label("", id="uninstall-status")
            yield Checkbox("Hide system apps", id="chk-hide-system", value=False)
            yield DataTable(id="pkg-table")
        yield Footer()

    def on_mount(self) -> None:
        self._cached_rows = []
        table = self.query_one("#pkg-table", DataTable)
        table.add_column("App name", key="name")
        table.add_column("Package", key="package")
        table.add_column("Type", key="type")
        table.cursor_type = "row"
        self.query_one("#apk-path", Input).focus()
        self.load_packages()

    # ── Sorting / filtering ───────────────────────────────────────────────────

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        col = str(event.column_key.value)
        if col not in self._COLS:
            return
        if col == self._sort_col:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_col = col
            self._sort_reverse = False
        self._render_table()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id == "chk-hide-system":
            self._render_table()

    def _render_table(self) -> None:
        hide_system = self.query_one("#chk-hide-system", Checkbox).value
        rows = (
            [r for r in self._cached_rows if r[2] != "system"]
            if hide_system
            else list(self._cached_rows)
        )
        col_idx = self._COLS.index(self._sort_col)
        rows.sort(key=lambda r: r[col_idx].casefold(), reverse=self._sort_reverse)
        table = self.query_one("#pkg-table", DataTable)
        table.clear()
        for name, pkg, pkg_type in rows:
            table.add_row(name, pkg, pkg_type, key=pkg)

    # ── Install ───────────────────────────────────────────────────────────────

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "apk-path":
            self._start_install()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "btn-install":
                self._start_install()
            case "btn-uninstall":
                self._start_uninstall()
            case "btn-refresh":
                self.load_packages()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        key = event.row_key.value
        if key:
            self.query_one("#pkg-name", Input).value = key

    def _start_install(self) -> None:
        raw = self.query_one("#apk-path", Input).value.strip()
        if not raw:
            self.notify("Enter an APK path first", severity="warning")
            return
        apk = Path(raw).expanduser()
        if not apk.exists():
            self.notify(f"File not found: {apk}", severity="error")
            return
        if apk.suffix.lower() != ".apk":
            self.notify(f"{apk.name} doesn't have an .apk extension — proceeding anyway", severity="warning")
        if self.adb is None:
            self.notify("No device connected", severity="error")
            return
        log = self.query_one("#install-log", Log)
        log.clear()
        log.write_line(f"Installing {apk.name} …")
        self.query_one("#btn-install", Button).disabled = True
        self.query_one("#install-status", Label).update("")
        self.run_install(apk)

    @work(thread=True, exclusive=False)
    def run_install(self, apk: Path) -> None:
        try:
            self.adb.install(apk)
            self.app.call_from_thread(self._install_done, apk.name, None)
        except Exception as exc:
            self.app.call_from_thread(self._install_done, apk.name, str(exc))

    def _install_done(self, name: str, error: str | None) -> None:
        log = self.query_one("#install-log", Log)
        if error:
            log.write_line(f"✗ Installation failed: {error}")
            self.query_one("#install-status", Label).update("[red]✗ Installation failed[/red]")
            self.notify("Installation failed", severity="error")
        else:
            log.write_line(f"✓ {name} installed successfully")
            self.query_one("#install-status", Label).update(f"[green]✓ {name} installed[/green]")
            self.notify(f"{name} installed")
            self.load_packages()
        self.query_one("#btn-install", Button).disabled = False

    # ── Uninstall ─────────────────────────────────────────────────────────────

    def action_refresh_packages(self) -> None:
        self.load_packages()

    @work(thread=True, exclusive=True)
    def load_packages(self) -> None:
        if self.adb is None:
            return
        try:
            packages = self.adb.pm_list_packages()
        except Exception:
            return
        labels = self.adb.get_app_labels()
        system_pkgs = self.adb.pm_list_system_packages()
        rows: list[tuple[str, str, str]] = [
            (
                labels.get(pkg) or pkg.rsplit(".", 1)[-1],
                pkg,
                "system" if pkg in system_pkgs else "user",
            )
            for pkg in packages
        ]
        self.app.call_from_thread(self._store_and_render, rows)

    def _store_and_render(self, rows: list[tuple[str, str, str]]) -> None:
        self._cached_rows = rows
        self._render_table()

    def _start_uninstall(self) -> None:
        pkg = self.query_one("#pkg-name", Input).value.strip()
        if not pkg:
            self.notify("Select a package or type a package name", severity="warning")
            return
        if self.adb is None:
            self.notify("No device connected", severity="error")
            return
        keep_data = self.query_one("#chk-keep-data", Checkbox).value
        self.query_one("#btn-uninstall", Button).disabled = True
        self.query_one("#uninstall-status", Label).update(f"Uninstalling {pkg} …")
        self.run_uninstall(pkg, keep_data)

    @work(thread=True, exclusive=False)
    def run_uninstall(self, pkg: str, keep_data: bool = False) -> None:
        try:
            ok = self.adb.pm_uninstall(pkg, keep_data=keep_data)
            self.app.call_from_thread(self._uninstall_done, pkg, None if ok else "pm_uninstall returned failure")
        except Exception as exc:
            self.app.call_from_thread(self._uninstall_done, pkg, str(exc))

    def _uninstall_done(self, pkg: str, error: str | None) -> None:
        if error:
            self.query_one("#uninstall-status", Label).update(f"[red]✗ Uninstall failed: {error}[/red]")
            self.notify(f"Uninstall failed: {error}", severity="error")
        else:
            self.query_one("#uninstall-status", Label).update(f"[green]✓ {pkg} uninstalled[/green]")
            self.query_one("#pkg-name", Input).value = ""
            self.notify(f"{pkg} uninstalled")
            self.load_packages()
        self.query_one("#btn-uninstall", Button).disabled = False

