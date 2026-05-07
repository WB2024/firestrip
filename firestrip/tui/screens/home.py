from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Label, Static

from . import FirestripScreen


class HomeScreen(FirestripScreen):
    BINDINGS = [
        ("1", "app.push_screen('debloat')", "Debloat"),
        ("2", "app.push_screen('telemetry')", "Telemetry"),
        ("3", "app.push_screen('launcher')", "Launcher"),
        ("4", "app.push_screen('settings')", "Settings"),
        ("5", "app.push_screen('backup')", "Backup"),
        ("6", "app.push_screen('install')", "Install / Uninstall"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="content"):
            yield Static(id="device-panel")
            with Horizontal(id="stats-row"):
                yield Static("Connection: pending…", classes="stat-card", id="stat-connection")
                yield Static("Device: —", classes="stat-card", id="stat-device")
                yield Static("Profile: —", classes="stat-card", id="stat-profile")
            yield Label("Quick actions:")
            yield Button("Safe Debloat", id="btn-debloat", variant="primary")
            yield Button("Strip Telemetry", id="btn-telemetry", variant="primary")
            yield Button("Manage Launcher", id="btn-launcher", variant="primary")
            yield Button("Install / Uninstall", id="btn-install", variant="default")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_status()

    def refresh_status(self) -> None:
        device = self.device
        adb = self.adb
        panel = self.query_one("#device-panel", Static)
        if device is None:
            panel.update("[bold]firestrip[/bold]\nNo device connected. Use --host or --usb on launch.")
        else:
            panel.update(
                f"[bold]{device.model_name}[/bold] ({device.model})\n"
                f"FireOS: {device.fireos_version}    Android: {device.android_version}\n"
                f"Serial: {device.serial}"
            )
        conn = self.query_one("#stat-connection", Static)
        if adb is None:
            conn.update("Connection: [red]disconnected[/red]")
            conn.set_class(True, "status-disconnected")
        elif device is None:
            conn.update("Connection: [yellow]connecting…[/yellow]")
            conn.set_class(True, "status-reconnecting")
        else:
            conn.update("Connection: [green]connected[/green]")
            conn.set_class(True, "status-connected")
        self.query_one("#stat-device", Static).update(
            f"Device: {device.model_name if device else '—'}"
        )
        self.query_one("#stat-profile", Static).update(
            f"Profile: {device.profile_key if device else '—'}"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "btn-debloat":
                self.app.push_screen("debloat")
            case "btn-telemetry":
                self.app.push_screen("telemetry")
            case "btn-launcher":
                self.app.push_screen("launcher")
            case "btn-install":
                self.app.push_screen("install")
