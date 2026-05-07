from __future__ import annotations

from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.widgets import (
    Button,
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

    def compose(self) -> ComposeResult:
        yield Header()
        with ScrollableContainer(id="content"):
            # ── Install ──────────────────────────────────────────────────────
            yield Label("[bold]Install APK[/bold] — enter a local file path")
            with Horizontal(id="input-row"):
                yield Input(
                    placeholder="/path/to/app.apk",
                    id="apk-path",
                    tooltip="Full path to the APK file on this machine",
                )
                yield Button("Install", id="btn-install", variant="primary")
            yield Label("", id="install-status")
            yield Log(id="install-log", auto_scroll=True, max_lines=6)

            yield Rule()

            # ── Uninstall ────────────────────────────────────────────────────
            yield Label("[bold]Uninstall package[/bold] — select from list or type a name")
            with Horizontal(id="uninstall-row"):
                yield Input(
                    placeholder="com.example.app",
                    id="pkg-name",
                    tooltip="Package name to uninstall",
                )
                yield Button("Uninstall", id="btn-uninstall", variant="error")
                yield Button("↻ Refresh", id="btn-refresh", variant="default")
            yield Label("", id="uninstall-status")
            yield DataTable(id="pkg-table")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#pkg-table", DataTable)
        table.add_columns("App name", "Package")
        table.cursor_type = "row"
        self.query_one("#apk-path", Input).focus()
        self.load_packages()

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
        """Clicking a row populates the package name input."""
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
            self.load_packages()  # refresh list so new package appears
        self.query_one("#btn-install", Button).disabled = False

    # ── Uninstall ─────────────────────────────────────────────────────────────

    def action_refresh_packages(self) -> None:
        self.load_packages()

    @work(thread=True, exclusive=True)
    def load_packages(self) -> None:
        if self.adb is None:
            return
        try:
            packages = sorted(self.adb.pm_list_packages())
        except Exception:
            return
        # Fetch friendly labels; empty dict is fine — table degrades gracefully
        labels = self.adb.get_app_labels()
        self.app.call_from_thread(self._populate_table, packages, labels)

    def _populate_table(self, packages: list[str], labels: dict[str, str]) -> None:
        table = self.query_one("#pkg-table", DataTable)
        table.clear()
        for pkg in packages:
            # Use label if available; fall back to the last dotted segment
            name = labels.get(pkg) or pkg.rsplit(".", 1)[-1]
            table.add_row(name, pkg, key=pkg)

    def _start_uninstall(self) -> None:
        pkg = self.query_one("#pkg-name", Input).value.strip()
        if not pkg:
            self.notify("Select a package or type a package name", severity="warning")
            return
        if self.adb is None:
            self.notify("No device connected", severity="error")
            return
        self.query_one("#btn-uninstall", Button).disabled = True
        self.query_one("#uninstall-status", Label).update(f"Uninstalling {pkg} …")
        self.run_uninstall(pkg)

    @work(thread=True, exclusive=False)
    def run_uninstall(self, pkg: str) -> None:
        try:
            ok = self.adb.pm_uninstall(pkg, keep_data=True)
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
            self.load_packages()  # refresh to remove it from the list
        self.query_one("#btn-uninstall", Button).disabled = False

