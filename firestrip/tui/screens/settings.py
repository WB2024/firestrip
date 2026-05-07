from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Button, DataTable, Footer, Header, Label
from textual import work

from ...core.settings import DEVICE_SETTINGS, apply_settings, read_current
from . import FirestripScreen
from .confirm import ConfirmModal


class SettingsScreen(FirestripScreen):
    BINDINGS = [("escape", "app.pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="content"):
            yield Label("Device settings tweaks")
            yield DataTable(id="settings-table")
            yield Button("Apply All", id="btn-apply", variant="error")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#settings-table", DataTable)
        table.add_columns("Setting", "Description", "Current", "Target")
        for ns, key, value, desc in DEVICE_SETTINGS:
            table.add_row(f"{ns}/{key}", desc, "(reading)", value)
        self.refresh_data()

    @work(thread=True)
    def refresh_data(self) -> None:
        if self.adb is None:
            return
        current = read_current(self.adb)
        self.app.call_from_thread(self._populate, current)

    def _populate(self, current: dict[str, str]) -> None:
        table = self.query_one("#settings-table", DataTable)
        table.clear()
        for ns, key, value, desc in DEVICE_SETTINGS:
            label = f"{ns}/{key}"
            table.add_row(label, desc, current.get(label, "") or "(unset)", value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "btn-apply":
            return
        items = [f"{ns}/{k} → {v}" for ns, k, v, _ in DEVICE_SETTINGS]
        self.app.push_screen(
            ConfirmModal("Apply settings?", items, "Apply"),
            self._on_confirm,
        )

    def _on_confirm(self, confirmed: bool | None) -> None:
        if not confirmed:
            return
        self.run_apply()

    @work(thread=True, exclusive=True)
    def run_apply(self) -> None:
        if self.adb is None:
            return
        results = apply_settings(self.adb, dry_run=False)
        ok = sum(1 for r in results if r.success)
        self.app.call_from_thread(self.notify, f"Settings applied ({ok}/{len(results)})")
        self.app.call_from_thread(self.refresh_data)
