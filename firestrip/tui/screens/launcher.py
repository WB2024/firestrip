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
            yield Label("Available launchers — select one (scanning device…):", id="lbl-title")
            yield ListView(id="launcher-list")
            yield Label("APK path (only needed if launcher is not installed):")
            yield Input(placeholder="/path/to/launcher.apk", id="apk-input")
            yield Label("Current default: …", id="current-default")
            yield Button("Apply Selected", id="btn-apply", variant="error")
            yield Button("Restore Amazon Launcher", id="btn-restore", variant="warning")
        yield Footer()

    def on_mount(self) -> None:
        self._predefined_pkgs: set[str] = set()
        self._launchers: list[LauncherInfo] = []
        for l in load_launchers():
            self._launchers.append(l)
            self._predefined_pkgs.add(l.package)
        self._selected_idx: int | None = None
        self._rebuild_list()
        self.refresh_default()
        self._load_device_launchers()

    def _rebuild_list(self) -> None:
        view = self.query_one("#launcher-list", ListView)
        view.clear()
        for l in self._launchers:
            if l.is_custom:
                tag = " [on device]"
            elif l.open_source:
                tag = " [FOSS]"
            else:
                tag = ""
            view.append(ListItem(Label(f"{l.name}{tag}\n  {l.description}")))

    @work(thread=True)
    def _load_device_launchers(self) -> None:
        """Query the device for all HOME-intent handlers and add any not in TOML."""
        if self.adb is None:
            return
        home_apps = LauncherManager(self.adb).query_home_activities()
        extras: list[LauncherInfo] = []
        for pkg, component in home_apps:
            if pkg not in self._predefined_pkgs:
                label = pkg.rsplit(".", 1)[-1]
                extras.append(LauncherInfo(
                    key=pkg,
                    name=label,
                    package=pkg,
                    main_activity=component,
                    description=pkg,
                    source_url="",
                    open_source=False,
                    is_custom=True,
                ))
        self.app.call_from_thread(self._merge_launchers, extras)

    def _merge_launchers(self, extras: list[LauncherInfo]) -> None:
        self._launchers.extend(extras)
        total = len(self._launchers)
        self.query_one("#lbl-title", Label).update(
            f"Available launchers — select one ({total} found):"
        )
        self._rebuild_list()

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

        if launcher.is_custom or apk is None:
            step1 = f"1. Confirm '{launcher.package}' is already installed"
        else:
            step1 = f"1. Install '{apk.name}' onto the device"

        steps = [
            step1,
            f"2. Set '{launcher.name}' as the default HOME app",
            "3. Verify the HOME activity changed",
            "4. Disable the Amazon launcher so it cannot override your choice",
        ]
        warning = (
            f"Swap launcher to {launcher.name}?\n"
            "All 4 steps run in sequence. You can restore the Amazon launcher at any time."
        )
        self.app.push_screen(
            ConfirmModal(warning, steps, "Swap"),
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
            warnings = [r for r in results if r.action == "warning"]
            root_required = any(r.message == "root_required" for r in warnings)
            if root_required:
                self.notify(
                    "HOME preference set — but Amazon launcher cannot be suppressed "
                    "without root on this firmware. On older FireOS it is removed "
                    "automatically.",
                    severity="warning",
                    timeout=12,
                )
            else:
                self.notify("Swap complete — press HOME on your remote to confirm the new launcher is active")
                for w in warnings:
                    if w.message:
                        self.notify(w.message, severity="warning", timeout=8)
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

