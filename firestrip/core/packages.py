from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from importlib import resources
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

from .adb import ADBClient
from .device import GENERIC_PROFILE_KEY, FireTVDevice
from .exceptions import ADBError, DataLoadError


def _load_toml(package_subpath: str, filename: str) -> dict:
    ref = resources.files(f"firestrip.data.{package_subpath}").joinpath(filename)
    try:
        with ref.open("rb") as f:
            return tomllib.load(f)
    except Exception as exc:
        raise DataLoadError(Path(filename), str(exc)) from exc


class PackageTier(Enum):
    SAFE = "safe"
    RISKY = "risky"
    TELEMETRY = "telemetry"
    NEVER = "never"


@dataclass
class PackageEntry:
    package_name: str
    tier: PackageTier
    description: str
    installed: bool = False


@dataclass
class ActionResult:
    package: str
    success: bool
    action: str
    message: str = ""


NEVER_TOUCH: frozenset[str] = frozenset({
    "com.amazon.tv.launcher",
    "com.amazon.firelauncher",
    "com.amazon.firehomestarter",
    "android",
    "com.android.systemui",
    "com.android.settings",
    "com.android.providers.settings",
    "com.android.shell",
    "com.android.phone",
    "com.android.bluetooth",
    "com.amazon.platform",
    "amazon.fireos",
    "com.amazon.tv.channelscan",
    "com.amazon.tv.conditionalaccess",
    "com.amazon.tv.livetv",
    "com.mediatek.tvinput",
    "com.mediatek.tvinputservice.arbitratorservice",
})


PRESETS: dict[str, list[PackageTier]] = {
    "safe": [PackageTier.SAFE],
    "telemetry": [PackageTier.TELEMETRY],
    "aggressive": [PackageTier.SAFE, PackageTier.RISKY, PackageTier.TELEMETRY],
}


_TIER_SORT = {
    PackageTier.TELEMETRY: 0,
    PackageTier.SAFE: 1,
    PackageTier.RISKY: 2,
    PackageTier.NEVER: 3,
}


class PackageManager:
    def __init__(self, device: FireTVDevice, adb: ADBClient) -> None:
        self._device = device
        self._adb = adb
        self._entries: dict[str, PackageEntry] = {}

    def load(self) -> None:
        self._entries = {}
        common = _load_toml("packages", "common.toml")
        self._merge_entries(common.get("packages", []))

        if self._device.profile_key != GENERIC_PROFILE_KEY:
            try:
                specific = _load_toml("packages", f"{self._device.profile_key}.toml")
                self._merge_entries(specific.get("packages", []))
            except DataLoadError:
                pass

        for never in NEVER_TOUCH:
            self._entries.pop(never, None)

        try:
            installed = set(self._adb.pm_list_packages())
        except ADBError:
            installed = set()
        for entry in self._entries.values():
            entry.installed = entry.package_name in installed

    def _merge_entries(self, entries: list[dict]) -> None:
        for raw in entries:
            name = raw.get("name")
            if not name:
                continue
            try:
                tier = PackageTier(raw.get("tier", "safe"))
            except ValueError:
                tier = PackageTier.SAFE
            self._entries[name] = PackageEntry(
                package_name=name,
                tier=tier,
                description=raw.get("description", ""),
            )

    def get_packages(
        self,
        tiers: list[PackageTier] | None = None,
        installed_only: bool = True,
    ) -> list[PackageEntry]:
        result = []
        for entry in self._entries.values():
            if tiers is not None and entry.tier not in tiers:
                continue
            if installed_only and not entry.installed:
                continue
            result.append(entry)
        result.sort(key=lambda e: (_TIER_SORT.get(e.tier, 99), e.package_name))
        return result

    def disable(
        self,
        packages: list[str],
        dry_run: bool = True,
        backup_manager: object | None = None,
    ) -> list[ActionResult]:
        results: list[ActionResult] = []
        for pkg in packages:
            if pkg in NEVER_TOUCH:
                results.append(ActionResult(pkg, False, "skipped", "in NEVER_TOUCH list"))
                continue
            entry = self._entries.get(pkg)
            if entry is None or not entry.installed:
                results.append(ActionResult(pkg, False, "skipped", "not installed"))
                continue
            if dry_run:
                results.append(ActionResult(pkg, True, "dry_run"))
                continue
            try:
                ok = self._adb.pm_disable(pkg)
                if ok:
                    results.append(ActionResult(pkg, True, "disabled"))
                    if backup_manager is not None and hasattr(backup_manager, "record_disabled"):
                        backup_manager.record_disabled(pkg)
                else:
                    results.append(ActionResult(pkg, False, "error", "pm_disable returned False"))
            except ADBError as exc:
                results.append(ActionResult(pkg, False, "error", str(exc)))
        return results

    def enable(self, packages: list[str]) -> list[ActionResult]:
        results: list[ActionResult] = []
        for pkg in packages:
            if pkg in NEVER_TOUCH:
                results.append(ActionResult(pkg, False, "skipped", "in NEVER_TOUCH list"))
                continue
            try:
                ok = self._adb.pm_enable(pkg)
                results.append(
                    ActionResult(pkg, ok, "enabled" if ok else "error",
                                 "" if ok else "pm_enable returned False")
                )
            except ADBError as exc:
                results.append(ActionResult(pkg, False, "error", str(exc)))
        return results

    def check_dependencies(self, packages: list[str]) -> dict[str, list[str]]:
        deps: dict[str, list[str]] = {}
        targets = set(packages)
        for pkg in packages:
            try:
                out = self._adb.shell(f"dumpsys package {pkg}")
            except ADBError:
                continue
            uses: list[str] = []
            for line in out.splitlines():
                line = line.strip()
                if line.startswith("uses-library"):
                    parts = line.split()
                    for p in parts[1:]:
                        p = p.strip(":,=")
                        if p and p not in targets and p in self._entries:
                            uses.append(p)
            if uses:
                deps[pkg] = uses
        return deps
