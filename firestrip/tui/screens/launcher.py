from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Button, Footer, Header, Input, Label, ListItem, ListView
from textual import work

from ...core.exceptions import LauncherSwapError
from ...core.launcher import LauncherInfo, LauncherManager, load_launchers
from . import FirestripScreen
from .confirm import ConfirmModal


class LauncherScreen(FirestripScreen):
    BINDINGS = [("escape", "app.pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="content"):
            yield Label("Available launchers (select one):")
            yield ListView(id="launcher-list")
            yield Label("APK path (required if launcher not installed):")
            yield Input(placeholder="/path/to/launcher.apk", id="apk-input")
            yield Label("Current default: …", id="current-default")
            yield Button("Apply Selected", id="btn-apply", variant="error")
            yield Button("Restore Amazon Launcher", id="btn-restore", variant="warning")
        yield Footer()

    def on_mount(self) -> None:
        self._launchers = load_launchers()
        self._selected_idx: int | None = None
        view = self.query_one("#launcher-list", ListView)
        view.clear()
        for l in self._launchers:
            oss = " [FOSS]" if l.open_source else ""
            view.append(ListItem(Label(f"{l.name}{oss}\n  {l.description}")))
        self.refresh_default()

    @work(thread=True)
    def refresh_default(self) -> None:
        if self.adb is None:
            return
        current = LauncherManager(self.adb).get_current_default()
        self.app.call_from_thread(
            lambda: self.query_one("#current-default", Label).update(
                f"Current default: {current or '(unknown)'}"
            )
        )

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        self._selected_idx = event.list_view.index

    def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "btn-apply":
                self._apply()
            case "btn-restore":
                self._restore()

    def _apply(self) -> None:
        if self._selected_idx is None:
            self.notify("Select a launcher first", severity="warning")
            return
        launcher = self._launchers[self._selected_idx]
        apk_text = self.query_one("#apk-input", Input).value.strip()
        apk = Path(apk_text) if apk_text else None
        self.app.push_screen(
            ConfirmModal(
                f"Swap to {launcher.name}?",
                [f"Install {launcher.package}" if apk else f"Use installed {launcher.package}",
                 "Set as default HOME",
                 "Verify HOME handler",
                 "Freeze Amazon launcher"],
                "Swap",
            ),
            lambda confirmed: self._on_confirm(launcher, apk, confirmed),
        )

    def _on_confirm(self, launcher: LauncherInfo, apk: Path | None, confirmed: bool | None) -> None:
        if not confirmed:
            return
        self.run_swap(launcher, apk)

    @work(thread=True, exclusive=True)
    def run_swap(self, launcher: LauncherInfo, apk: Path | None) -> None:
        if self.adb is None:
            return
        try:
            results = LauncherManager(self.adb).swap(launcher, apk_path=apk, dry_run=False)
            self.app.call_from_thread(self._done, results, None)
        except LauncherSwapError as exc:
            self.app.call_from_thread(self._done, [], str(exc))

    def _done(self, results: list, error: str | None) -> None:
        if error:
            self.notify(f"Swap failed: {error}", severity="error")
        else:
            ok = sum(1 for r in results if r.success)
            self.notify(f"Swap complete ({ok}/{len(results)} steps)")
        self.refresh_default()

    def _restore(self) -> None:
        self.app.push_screen(
            ConfirmModal("Restore Amazon launcher?", ["Re-enable Amazon launcher", "Set as default HOME"], "Restore"),
            self._on_restore_confirm,
        )

    def _on_restore_confirm(self, confirmed: bool | None) -> None:
        if not confirmed:
            return
        self.run_restore()

    @work(thread=True, exclusive=True)
    def run_restore(self) -> None:
        if self.adb is None:
            return
        ok = LauncherManager(self.adb).restore_amazon_launcher()
        self.app.call_from_thread(
            self.notify,
            "Amazon launcher restored" if ok else "Restoration may need manual confirmation",
        )
        self.app.call_from_thread(self.refresh_default)
