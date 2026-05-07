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
        settings_ok = sum(1 for r in s_results if r.success)
        services_disabled = sum(1 for r in v_results if r.success and r.action == "disabled")
        services_absent = sum(1 for r in v_results if r.action == "skipped")
        services_failed = sum(1 for r in v_results if not r.success)
        self.app.call_from_thread(self._done, settings_ok, len(s_results),
                                  services_disabled, services_absent, services_failed)

    def _done(self, settings_ok: int, settings_total: int,
              services_disabled: int, services_absent: int, services_failed: int) -> None:
        parts = [f"{settings_ok}/{settings_total} settings applied",
                 f"{services_disabled} services disabled"]
        if services_absent:
            parts.append(f"{services_absent} already absent")
        if services_failed:
            parts.append(f"{services_failed} failed")
        self.notify("Strip complete — " + ", ".join(parts))
        self.refresh_data()
