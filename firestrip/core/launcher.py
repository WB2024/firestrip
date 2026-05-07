from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .adb import ADBClient
from .exceptions import ADBCommandError, ADBError, LauncherError, LauncherSwapError
from .packages import ActionResult, _load_toml

AMAZON_LAUNCHER_PKG = "com.amazon.tv.launcher"
AMAZON_LAUNCHER_ACTIVITIES = (
    "com.amazon.tv.launcher/.ui.HomeActivity_vNext",
    "com.amazon.tv.launcher/.ui.TvLauncherActivity",
)


@dataclass
class LauncherInfo:
    key: str
    name: str
    package: str
    main_activity: str
    description: str
    source_url: str
    open_source: bool


def load_launchers() -> list[LauncherInfo]:
    data = _load_toml("launchers", "launchers.toml")
    out: list[LauncherInfo] = []
    for raw in data.get("launchers", []):
        out.append(LauncherInfo(
            key=raw.get("key", ""),
            name=raw.get("name", ""),
            package=raw.get("package", ""),
            main_activity=raw.get("main_activity", ""),
            description=raw.get("description", ""),
            source_url=raw.get("source_url", ""),
            open_source=bool(raw.get("open_source", False)),
        ))
    return out


def _full_activity(package: str, main_activity: str) -> str:
    if main_activity.startswith("."):
        return f"{package}/{main_activity}"
    if "/" in main_activity:
        return main_activity
    return f"{package}/{main_activity}"


class LauncherManager:
    def __init__(self, adb: ADBClient) -> None:
        self._adb = adb

    def get_available(self) -> list[LauncherInfo]:
        return load_launchers()

    def get_installed(self) -> list[str]:
        try:
            installed = set(self._adb.pm_list_packages())
        except ADBError:
            return []
        return [l.package for l in self.get_available() if l.package in installed]

    def get_current_default(self) -> str:
        try:
            out = self._adb.shell(
                "cmd package resolve-activity --brief "
                "-a android.intent.action.MAIN -c android.intent.category.HOME"
            )
        except ADBError:
            return ""
        first = next((l for l in out.splitlines() if l.strip()), "")
        if "/" in first:
            return first.split("/", 1)[0].strip()
        return ""

    def install(self, apk_path: Path) -> bool:
        try:
            return self._adb.install(apk_path)
        except ADBError as exc:
            raise LauncherError(f"Failed to install {apk_path}: {exc}") from exc

    def set_default(self, launcher: LauncherInfo) -> bool:
        full = _full_activity(launcher.package, launcher.main_activity)
        try:
            self._adb.shell(f"cmd package set-home-activity {full}")
            return True
        except ADBCommandError:
            try:
                self._adb.shell(
                    f"am start -a android.intent.action.MAIN "
                    f"-c android.intent.category.HOME -n {full}"
                )
            except ADBError as exc:
                raise LauncherError(f"Failed to set launcher: {exc}") from exc
            return False

    def freeze_amazon_launcher(self) -> bool:
        return self._adb.pm_disable(AMAZON_LAUNCHER_PKG)

    def restore_amazon_launcher(self) -> bool:
        try:
            self._adb.pm_enable(AMAZON_LAUNCHER_PKG)
        except ADBError as exc:
            raise LauncherError(f"Failed to enable Amazon launcher: {exc}") from exc
        for activity in AMAZON_LAUNCHER_ACTIVITIES:
            try:
                self._adb.shell(f"cmd package set-home-activity {activity}")
                return True
            except ADBError:
                continue
        return False

    def swap(
        self,
        launcher: LauncherInfo,
        apk_path: Path | None = None,
        dry_run: bool = True,
    ) -> list[ActionResult]:
        results: list[ActionResult] = []
        if dry_run:
            results.append(ActionResult(launcher.package, True, "dry_run", "step 1: install/verify"))
            results.append(ActionResult(launcher.package, True, "dry_run", "step 2: set as default"))
            results.append(ActionResult(launcher.package, True, "dry_run", "step 3: verify"))
            results.append(ActionResult(AMAZON_LAUNCHER_PKG, True, "dry_run",
                                        "step 4: freeze Amazon launcher"))
            return results

        # Step 1
        try:
            installed = set(self._adb.pm_list_packages())
        except ADBError as exc:
            results.append(ActionResult(launcher.package, False, "error", str(exc)))
            return results

        if launcher.package in installed:
            results.append(ActionResult(launcher.package, True, "skipped", "already installed"))
        else:
            if apk_path is None:
                results.append(ActionResult(
                    launcher.package, False, "error",
                    "APK path required — launcher not installed",
                ))
                return results
            try:
                self.install(apk_path)
                results.append(ActionResult(launcher.package, True, "installed"))
            except LauncherError as exc:
                results.append(ActionResult(launcher.package, False, "error", str(exc)))
                return results

        # Step 2
        try:
            ok = self.set_default(launcher)
            results.append(ActionResult(
                launcher.package, True,
                "set_default" if ok else "set_default_fallback",
                "" if ok else "Used am start fallback. Manual confirmation may be needed.",
            ))
        except LauncherError as exc:
            err = ActionResult(launcher.package, False, "error", str(exc))
            results.append(err)
            raise LauncherSwapError(2, str(exc)) from exc

        # Step 3
        current = self.get_current_default()
        if current != launcher.package:
            detail = f"HOME handler is '{current}', expected '{launcher.package}'"
            results.append(ActionResult(launcher.package, False, "error", detail))
            raise LauncherSwapError(3, detail)
        results.append(ActionResult(launcher.package, True, "verified"))

        # Step 4
        try:
            ok = self.freeze_amazon_launcher()
            results.append(ActionResult(
                AMAZON_LAUNCHER_PKG, ok, "frozen" if ok else "error",
                "" if ok else "could not disable Amazon launcher",
            ))
        except ADBError as exc:
            results.append(ActionResult(AMAZON_LAUNCHER_PKG, False, "error", str(exc)))
        return results
