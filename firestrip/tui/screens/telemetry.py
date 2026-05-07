from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Button, DataTable, Footer, Header, Label, ListItem, ListView
from textual import work

from ...core.telemetry import (
    TELEMETRY_SERVICES,
    TELEMETRY_SETTINGS,
    read_current_settings,
    strip_services,
    strip_settings,
)
from . import FirestripScreen
from .confirm import ConfirmModal


class TelemetryScreen(FirestripScreen):
    BINDINGS = [("escape", "app.pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="content"):
            yield Label("Telemetry — Settings Layer")
            yield DataTable(id="settings-table")
            yield Label("Telemetry — Services Layer")
            yield ListView(id="services-list")
            yield Button("Strip All", id="btn-strip", variant="error")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#settings-table", DataTable)
        table.add_columns("Setting", "Current", "Target")
        for namespace, key, value, _desc in TELEMETRY_SETTINGS:
            table.add_row(f"{namespace}/{key}", "(reading)", value)
        self.refresh_data()

    @work(thread=True)
    def refresh_data(self) -> None:
        if self.adb is None:
            return
        current = read_current_settings(self.adb)
        try:
            installed = set(self.adb.pm_list_packages())
        except Exception:
            installed = set()
        self.app.call_from_thread(self._populate, current, installed)

    def _populate(self, current: dict[str, str], installed: set[str]) -> None:
        table = self.query_one("#settings-table", DataTable)
        table.clear()
        for namespace, key, value, _desc in TELEMETRY_SETTINGS:
            label = f"{namespace}/{key}"
            table.add_row(label, current.get(label, "") or "(unset)", value)

        services = self.query_one("#services-list", ListView)
        services.clear()
        for svc in TELEMETRY_SERVICES:
            mark = "✓" if svc in installed else "·"
            services.append(ListItem(Label(f"{mark}  {svc}")))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "btn-strip":
            return
        items = [f"{ns}/{k} → {v}" for ns, k, v, _ in TELEMETRY_SETTINGS]
        items += [f"disable {svc}" for svc in TELEMETRY_SERVICES]
        self.app.push_screen(
            ConfirmModal("Strip telemetry?", items, "Strip"),
            self._on_confirm,
        )

    def _on_confirm(self, confirmed: bool | None) -> None:
        if not confirmed:
            return
        self.run_strip()

    @work(thread=True, exclusive=True)
    def run_strip(self) -> None:
        if self.adb is None:
            return
        s_results = strip_settings(self.adb, dry_run=False)
        v_results = strip_services(self.adb, dry_run=False)
        ok = sum(1 for r in s_results + v_results if r.success)
        total = len(s_results) + len(v_results)
        self.app.call_from_thread(self._done, ok, total)

    def _done(self, ok: int, total: int) -> None:
        self.notify(f"Telemetry strip complete ({ok}/{total})")
        self.refresh_data()
