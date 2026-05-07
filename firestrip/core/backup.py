from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .adb import ADBClient
from .device import FireTVDevice
from .exceptions import ADBError, BackupError
from .packages import ActionResult


class BackupManager:
    DEFAULT_DIR = Path.home() / ".local" / "share" / "firestrip" / "backups"

    def __init__(self) -> None:
        self._disabled_this_session: list[str] = []

    def record_disabled(self, package: str) -> None:
        if package not in self._disabled_this_session:
            self._disabled_this_session.append(package)

    @property
    def disabled_this_session(self) -> list[str]:
        return list(self._disabled_this_session)

    def create(
        self,
        adb: ADBClient,
        device: FireTVDevice,
        output_path: Path | None = None,
    ) -> Path:
        from .launcher import LauncherManager
        from .settings import read_current
        from .telemetry import read_current_settings

        try:
            installed = adb.pm_list_packages()
        except ADBError as exc:
            raise BackupError(f"Failed to list packages: {exc}") from exc

        settings: dict[str, str] = {}
        settings.update(read_current_settings(adb))
        settings.update(read_current(adb))

        try:
            default_launcher = LauncherManager(adb).get_current_default()
        except ADBError:
            default_launcher = ""

        payload = {
            "version": 1,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "device": asdict(device),
            "packages": {
                "all_installed": installed,
                "disabled_by_firestrip": list(self._disabled_this_session),
            },
            "settings": settings,
            "launcher": {"default_before": default_launcher},
        }

        if output_path is None:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
            output_path = self.DEFAULT_DIR / f"{stamp}_{device.model}.json"

        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(payload, indent=2))
        except OSError as exc:
            raise BackupError(f"Could not write backup to {output_path}: {exc}") from exc
        return output_path

    def list_backups(self) -> list[Path]:
        if not self.DEFAULT_DIR.exists():
            return []
        files = [p for p in self.DEFAULT_DIR.iterdir() if p.is_file() and p.suffix == ".json"]
        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return files

    def restore(
        self,
        adb: ADBClient,
        backup_path: Path,
        dry_run: bool = True,
    ) -> list[ActionResult]:
        try:
            data = json.loads(backup_path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise BackupError(f"Could not read backup {backup_path}: {exc}") from exc

        results: list[ActionResult] = []
        packages = data.get("packages", {}).get("disabled_by_firestrip", [])
        for pkg in packages:
            if dry_run:
                results.append(ActionResult(pkg, True, "dry_run", "would re-enable"))
                continue
            try:
                ok = adb.pm_enable(pkg)
                results.append(
                    ActionResult(pkg, ok, "enabled" if ok else "error",
                                 "" if ok else "pm_enable returned False")
                )
            except ADBError as exc:
                results.append(ActionResult(pkg, False, "error", str(exc)))

        settings = data.get("settings", {})
        for label, value in settings.items():
            if not value:
                continue
            if "/" not in label:
                continue
            namespace, key = label.split("/", 1)
            if dry_run:
                results.append(ActionResult(label, True, "dry_run", f"would restore {value}"))
                continue
            try:
                ok = adb.settings_put(namespace, key, value)
                results.append(
                    ActionResult(label, ok, "set" if ok else "error",
                                 "" if ok else "settings put failed")
                )
            except ADBError as exc:
                results.append(ActionResult(label, False, "error", str(exc)))
        return results

    def restore_launcher(self, adb: ADBClient, backup_path: Path) -> bool:
        from .launcher import LauncherManager
        try:
            json.loads(backup_path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise BackupError(f"Could not read backup {backup_path}: {exc}") from exc
        return LauncherManager(adb).restore_amazon_launcher()
