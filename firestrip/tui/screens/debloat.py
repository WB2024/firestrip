from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Label, ProgressBar
from textual import work

from ...core.packages import PRESETS, ActionResult, PackageManager, PackageTier
from . import FirestripScreen
from .confirm import ConfirmModal


class DebloatScreen(FirestripScreen):
    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("a", "select_all", "Select All"),
        ("n", "deselect_all", "None"),
        ("s", "filter_safe", "Safe Only"),
        ("p", "preview", "Preview"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(id="sidebar"):
                yield Button("All", id="filter-all")
                yield Button("Safe", id="filter-safe")
                yield Button("Risky", id="filter-risky")
                yield Button("Telemetry", id="filter-telemetry")
                yield Label("")
                yield Button("Preview", id="btn-preview", variant="warning")
                yield Button("Apply Selected", id="btn-apply", variant="error")
            with Vertical(id="content"):
                yield Label("Loading packages…", id="status-label")
                yield DataTable(id="package-list")
                yield ProgressBar(id="progress", show_eta=False, total=100)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#package-list", DataTable)
        table.add_columns("✓", "Tier", "Package", "Description")
        table.cursor_type = "row"
        self._tier_filter: list[PackageTier] | None = None
        self._selected: set[str] = set()
        self._entries: list = []
        self.load_packages()

    @work(thread=True, exclusive=True)
    def load_packages(self) -> None:
        if self.adb is None or self.device is None:
            return
        pm = PackageManager(self.device, self.adb)
        pm.load()
        self._pm = pm
        entries = pm.get_packages(installed_only=True)
        self.app.call_from_thread(self._populate, entries)

    def _populate(self, entries: list) -> None:
        self._entries = entries
        table = self.query_one("#package-list", DataTable)
        table.clear()
        for e in entries:
            if self._tier_filter is not None and e.tier not in self._tier_filter:
                continue
            mark = "x" if e.package_name in self._selected else " "
            table.add_row(mark, e.tier.value, e.package_name, e.description, key=e.package_name)
        self.query_one("#status-label", Label).update(f"{len(entries)} packages loaded")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        key = event.row_key.value
        if key is None:
            return
        if key in self._selected:
            self._selected.discard(key)
        else:
            self._selected.add(key)
        self._populate(self._entries)

    def _visible_entries(self) -> list:
        """Return only the entries currently shown given the active tier filter."""
        if self._tier_filter is None:
            return list(self._entries)
        return [e for e in self._entries if e.tier in self._tier_filter]

    def action_select_all(self) -> None:
        self._selected.update(e.package_name for e in self._visible_entries())
        self._populate(self._entries)

    def action_deselect_all(self) -> None:
        visible_pkgs = {e.package_name for e in self._visible_entries()}
        self._selected -= visible_pkgs
        self._populate(self._entries)

    def action_filter_safe(self) -> None:
        self._tier_filter = [PackageTier.SAFE]
        self._populate(self._entries)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "filter-all":
                self._tier_filter = None
            case "filter-safe":
                self._tier_filter = [PackageTier.SAFE]
            case "filter-risky":
                self._tier_filter = [PackageTier.RISKY]
            case "filter-telemetry":
                self._tier_filter = [PackageTier.TELEMETRY]
            case "btn-preview":
                self.action_preview()
                return
            case "btn-apply":
                self.action_preview()
                return
            case _:
                return
        self._populate(self._entries)

    def action_preview(self) -> None:
        if not self._selected:
            self.notify("No packages selected", severity="warning")
            return
        items = sorted(self._selected)
        self.app.push_screen(
            ConfirmModal(f"Disable {len(items)} package(s)?", items, "Disable"),
            self._on_confirm,
        )

    def _on_confirm(self, confirmed: bool | None) -> None:
        if not confirmed:
            return
        self.run_disable(list(self._selected))

    @work(thread=True, exclusive=True)
    def run_disable(self, packages: list[str]) -> None:
        if not hasattr(self, "_pm"):
            return
        results = self._pm.disable(packages, dry_run=False, backup_manager=self.backup)
        self.app.call_from_thread(self._on_disable_complete, results)

    def _on_disable_complete(self, results: list[ActionResult]) -> None:
        ok = sum(1 for r in results if r.success and r.action == "disabled")
        self.notify(f"Disabled {ok}/{len(results)} packages")
        self._selected.clear()
        self.load_packages()
