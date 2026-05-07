from __future__ import annotations

from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Input, Label, Log

from ...core.exceptions import ADBCommandError
from . import FirestripScreen


class InstallScreen(FirestripScreen):
    """Simple APK installer — enter a local path and push it to the device."""

    BINDINGS = [("escape", "app.pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="content"):
            yield Label("Install APK onto connected Fire TV")
            with Horizontal(id="input-row"):
                yield Input(
                    placeholder="/path/to/app.apk",
                    id="apk-path",
                    tooltip="Full path to the APK file on this machine",
                )
                yield Button("Install", id="btn-install", variant="primary")
            yield Label("", id="status")
            yield Log(id="install-log", auto_scroll=True)
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#apk-path", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-install":
            self._start_install()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._start_install()

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
        self.query_one("#status", Label).update("")
        self.run_install(apk)

    @work(thread=True, exclusive=True)
    def run_install(self, apk: Path) -> None:
        log_line = self.app.call_from_thread
        try:
            self.adb.install(apk)
            log_line(self._on_success, apk.name)
        except ADBCommandError as exc:
            log_line(self._on_failure, str(exc))
        except Exception as exc:
            log_line(self._on_failure, str(exc))

    def _on_success(self, name: str) -> None:
        log = self.query_one("#install-log", Log)
        log.write_line(f"✓ {name} installed successfully")
        self.query_one("#status", Label).update(f"[green]✓ {name} installed[/green]")
        self.query_one("#btn-install", Button).disabled = False
        self.notify(f"{name} installed", severity="information")

    def _on_failure(self, error: str) -> None:
        log = self.query_one("#install-log", Log)
        log.write_line(f"✗ Installation failed: {error}")
        self.query_one("#status", Label).update("[red]✗ Installation failed[/red]")
        self.query_one("#btn-install", Button).disabled = False
        self.notify("Installation failed", severity="error")
