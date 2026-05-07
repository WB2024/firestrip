from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Button, Footer, Header, Label, ListItem, ListView
from textual import work

from ...core.exceptions import BackupError
from . import FirestripScreen
from .confirm import ConfirmModal


class BackupScreen(FirestripScreen):
    BINDINGS = [("escape", "app.pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="content"):
            yield Label("Backups")
            yield Button("Create Backup Now", id="btn-create", variant="primary")
            yield Label("Existing backups:")
            yield ListView(id="backup-list")
            yield Button("Preview Restore", id="btn-preview", variant="warning")
            yield Button("Apply Restore", id="btn-apply", variant="error")
            yield Button("Restore Launcher Only", id="btn-launcher", variant="warning")
            yield Label("", id="status")
        yield Footer()

    def on_mount(self) -> None:
        self._selected: Path | None = None
        self.refresh_list()

    def refresh_list(self) -> None:
        view = self.query_one("#backup-list", ListView)
        view.clear()
        self._backups = self.backup.list_backups()
        for p in self._backups:
            view.append(ListItem(Label(str(p))))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        idx = event.list_view.index
        if idx is not None and 0 <= idx < len(self._backups):
            self._selected = self._backups[idx]

    def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "btn-create":
                self.run_create()
            case "btn-preview":
                self.run_restore(dry_run=True)
            case "btn-apply":
                if self._selected is None:
                    self.notify("Select a backup first", severity="warning")
                    return
                self.app.push_screen(
                    ConfirmModal("Apply restore?", [str(self._selected)], "Restore"),
                    lambda c: self.run_restore(dry_run=False) if c else None,
                )
            case "btn-launcher":
                self.run_restore_launcher()

    @work(thread=True, exclusive=True)
    def run_create(self) -> None:
        if self.adb is None or self.device is None:
            return
        try:
            path = self.backup.create(self.adb, self.device)
            self.app.call_from_thread(
                self.query_one("#status", Label).update, f"Created: {path}"
            )
            self.app.call_from_thread(self.refresh_list)
        except BackupError as exc:
            self.app.call_from_thread(self.notify, str(exc), severity="error")

    @work(thread=True, exclusive=True)
    def run_restore(self, dry_run: bool) -> None:
        if self.adb is None or self._selected is None:
            return
        try:
            results = self.backup.restore(self.adb, self._selected, dry_run=dry_run)
            ok = sum(1 for r in results if r.success)
            self.app.call_from_thread(
                self.query_one("#status", Label).update,
                f"{'Preview' if dry_run else 'Applied'}: {ok}/{len(results)}",
            )
        except BackupError as exc:
            self.app.call_from_thread(self.notify, str(exc), severity="error")

    @work(thread=True, exclusive=True)
    def run_restore_launcher(self) -> None:
        if self.adb is None or self._selected is None:
            return
        try:
            ok = self.backup.restore_launcher(self.adb, self._selected)
            self.app.call_from_thread(
                self.notify,
                "Launcher restored" if ok else "Launcher restoration unclear",
            )
        except BackupError as exc:
            self.app.call_from_thread(self.notify, str(exc), severity="error")
