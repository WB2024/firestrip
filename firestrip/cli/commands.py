from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import typer

from ..core.adb import ADBClient
from ..core.backup import BackupManager
from ..core.device import detect_device
from ..core.exceptions import (
    ADBBinaryNotFoundError,
    ADBConnectionError,
    ADBTimeoutError,
    BackupError,
    FirestripError,
    LauncherSwapError,
)
from ..core.launcher import AMAZON_LAUNCHER_PKG, LauncherInfo, LauncherManager, load_launchers
from ..core.packages import PRESETS, ActionResult, PackageManager, PackageTier
from ..core.settings import DEVICE_SETTINGS, apply_settings, read_current
from ..core.telemetry import TELEMETRY_SERVICES, read_current_settings, strip_services, strip_settings

app = typer.Typer(
    name="firestrip",
    help="Fire TV debloat, telemetry stripper, and launcher manager.",
    no_args_is_help=False,
)

debloat_app = typer.Typer(help="Manage bloatware packages")
telemetry_app = typer.Typer(help="Strip telemetry settings and services")
launcher_app = typer.Typer(help="Manage Fire TV launcher")
settings_app = typer.Typer(help="Apply device settings tweaks")
backup_app = typer.Typer(help="Create a device state backup")
restore_app = typer.Typer(help="Restore from a backup file")
apk_app = typer.Typer(help="Install APK files onto the device")

app.add_typer(debloat_app, name="debloat")
app.add_typer(telemetry_app, name="telemetry")
app.add_typer(launcher_app, name="launcher")
app.add_typer(settings_app, name="settings")
app.add_typer(backup_app, name="backup")
app.add_typer(restore_app, name="restore")
app.add_typer(apk_app, name="apk")


@dataclass
class _State:
    adb: Optional[ADBClient] = None
    backup: Optional[BackupManager] = None


state = _State()


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    host: Optional[str] = typer.Option(None, "--host", help="Fire TV IP address"),
    port: int = typer.Option(5555, "--port", help="ADB port"),
    usb: bool = typer.Option(False, "--usb", help="Use USB connection"),
    serial: Optional[str] = typer.Option(None, "--serial", help="USB device serial"),
    no_tui: bool = typer.Option(False, "--no-tui", help="Force CLI mode"),
) -> None:
    if ctx.invoked_subcommand is None:
        return
    if usb or serial:
        state.adb = ADBClient(serial=serial)
    elif host:
        state.adb = ADBClient(host=host, port=port)
    else:
        state.adb = ADBClient()
    state.backup = BackupManager()
    try:
        state.adb.connect()
    except (ADBConnectionError, ADBBinaryNotFoundError, ADBTimeoutError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


def _require_adb() -> ADBClient:
    if state.adb is None:
        typer.echo("Error: not connected. Specify --host, --usb, or --serial.", err=True)
        raise typer.Exit(1)
    return state.adb


def _print_results(results: list[ActionResult]) -> None:
    for r in results:
        marker = "✓" if r.success else "✗"
        msg = f" — {r.message}" if r.message else ""
        typer.echo(f"  {marker} [{r.action}] {r.package}{msg}")


# ── device & udev ───────────────────────────────────────────────────────────

@app.command("device")
def cmd_device() -> None:
    """Show connected device information."""
    adb = _require_adb()
    device = detect_device(adb)
    typer.echo(f"Model:       {device.model_name} ({device.model})")
    typer.echo(f"FireOS:      {device.fireos_version}")
    typer.echo(f"Android:     {device.android_version}")
    typer.echo(f"Serial:      {device.serial}")
    typer.echo(f"Profile:     {device.profile_key}")


UDEV_RULE = 'SUBSYSTEM=="usb", ATTR{idVendor}=="1949", MODE="0666", GROUP="plugdev"\n'
UDEV_PATH = Path("/etc/udev/rules.d/51-firestrip-android.rules")


@app.command("setup-udev")
def cmd_setup_udev() -> None:
    """Install udev rules for rootless USB ADB access (requires root)."""
    if UDEV_PATH.exists():
        typer.echo(f"udev rule already exists at {UDEV_PATH}")
        return
    try:
        UDEV_PATH.write_text(UDEV_RULE)
        subprocess.run(["udevadm", "control", "--reload-rules"], check=True)
        subprocess.run(["udevadm", "trigger"], check=True)
        typer.echo(f"✓ udev rule written to {UDEV_PATH}")
        typer.echo("Add yourself to 'plugdev' if needed: sudo usermod -aG plugdev $USER")
    except PermissionError:
        typer.echo("Error: root required. Run: sudo firestrip setup-udev", err=True)
        raise typer.Exit(1)


# ── debloat ──────────────────────────────────────────────────────────────────

@debloat_app.command("list")
def debloat_list() -> None:
    """List all packages eligible for removal."""
    adb = _require_adb()
    device = detect_device(adb)
    pm = PackageManager(device, adb)
    pm.load()
    for entry in pm.get_packages(installed_only=True):
        typer.echo(f"  [{entry.tier.value:9}] {entry.package_name}  — {entry.description}")


@debloat_app.command("run")
def debloat_run(
    preset: str = typer.Option("safe", "--preset", help="safe|telemetry|aggressive"),
    apply: bool = typer.Option(False, "--apply", help="Execute (default is dry-run)"),
    package: Optional[str] = typer.Option(None, "--package", help="Single package name"),
) -> None:
    """Remove bloatware packages."""
    adb = _require_adb()
    device = detect_device(adb)
    pm = PackageManager(device, adb)
    pm.load()

    if package:
        targets = [package]
    else:
        if preset not in PRESETS:
            typer.echo(f"Unknown preset: {preset}. Use safe|telemetry|aggressive.", err=True)
            raise typer.Exit(1)
        entries = pm.get_packages(tiers=PRESETS[preset], installed_only=True)
        targets = [e.package_name for e in entries]

    if not targets:
        typer.echo("Nothing to do.")
        return

    typer.echo(f"{'Applying' if apply else 'Dry-run for'} {len(targets)} package(s):")
    results = pm.disable(targets, dry_run=not apply, backup_manager=state.backup)
    _print_results(results)


# ── telemetry ────────────────────────────────────────────────────────────────

@telemetry_app.command("status")
def telemetry_status() -> None:
    """Show current telemetry setting values."""
    adb = _require_adb()
    current = read_current_settings(adb)
    for label, value in current.items():
        typer.echo(f"  {label} = {value or '(unset)'}")


@telemetry_app.command("strip")
def telemetry_strip(
    apply: bool = typer.Option(False, "--apply"),
) -> None:
    """Strip telemetry settings and disable telemetry services."""
    adb = _require_adb()
    typer.echo("Settings layer:")
    _print_results(strip_settings(adb, dry_run=not apply))
    typer.echo("Services layer:")
    _print_results(strip_services(adb, dry_run=not apply))


# ── launcher ─────────────────────────────────────────────────────────────────

@launcher_app.command("list")
def launcher_list() -> None:
    """List known replacement launchers (from built-in catalogue)."""
    for l in load_launchers():
        oss = "FOSS" if l.open_source else "proprietary"
        typer.echo(f"  {l.key:10}  {l.name}  ({l.package})  [{oss}]")
        typer.echo(f"             {l.description}")


@launcher_app.command("scan")
def launcher_scan() -> None:
    """Query the connected device for all installed HOME-intent handlers."""
    adb = _require_adb()
    predefined = {l.package for l in load_launchers()}
    home_apps = LauncherManager(adb).query_home_activities()
    if not home_apps:
        typer.echo("No HOME-intent handlers found (or device unreachable).")
        return
    for pkg, component in home_apps:
        tag = " [in catalogue]" if pkg in predefined else " [custom]"
        typer.echo(f"  {component}{tag}")


@launcher_app.command("status")
def launcher_status() -> None:
    """Show current default launcher."""
    adb = _require_adb()
    lm = LauncherManager(adb)
    typer.echo(f"Current default: {lm.get_current_default() or '(unknown)'}")
    typer.echo(f"Installed: {', '.join(lm.get_installed()) or 'none'}")


@launcher_app.command("set")
def launcher_set(
    key: str = typer.Argument(..., help="Launcher key (e.g. wolf) or package name"),
    apk: Optional[Path] = typer.Option(None, "--apk", help="Local APK path"),
    apply: bool = typer.Option(False, "--apply"),
) -> None:
    """Set a replacement launcher by key, or by package name if already on device."""
    adb = _require_adb()
    # Try catalogue first
    matches = [l for l in load_launchers() if l.key == key]
    if not matches:
        # Fall back: treat key as a package name and look it up on device
        home_apps = LauncherManager(adb).query_home_activities()
        pkg_map = {pkg: comp for pkg, comp in home_apps}
        if key in pkg_map:
            label = key.rsplit(".", 1)[-1]
            matches = [LauncherInfo(
                key=key,
                name=label,
                package=key,
                main_activity=pkg_map[key],
                description=key,
                source_url="",
                open_source=False,
                is_custom=True,
            )]
        else:
            typer.echo(
                f"Unknown launcher key or package: {key}\n"
                "Run 'firestrip launcher list' for catalogue keys or "
                "'firestrip launcher scan' for on-device packages.",
                err=True,
            )
            raise typer.Exit(1)
    lm = LauncherManager(adb)
    try:
        results = lm.swap(matches[0], apk_path=apk, dry_run=not apply)
    except LauncherSwapError as exc:
        typer.echo(f"Swap failed: {exc}", err=True)
        raise typer.Exit(1)
    _print_results(results)


@launcher_app.command("restore")
def launcher_restore(
    apply: bool = typer.Option(False, "--apply"),
) -> None:
    """Restore Amazon launcher."""
    adb = _require_adb()
    if not apply:
        typer.echo("[dry-run] would re-enable Amazon launcher and set as default")
        return
    ok = LauncherManager(adb).restore_amazon_launcher()
    typer.echo("✓ restored" if ok else "✗ restoration may need manual confirmation")


# ── settings ─────────────────────────────────────────────────────────────────

@settings_app.command("status")
def settings_status() -> None:
    """Show current device setting values."""
    adb = _require_adb()
    current = read_current(adb)
    for label, value in current.items():
        typer.echo(f"  {label} = {value or '(unset)'}")


@settings_app.command("apply")
def settings_apply(
    apply: bool = typer.Option(False, "--apply"),
) -> None:
    """Apply firestrip's recommended device settings."""
    adb = _require_adb()
    _print_results(apply_settings(adb, dry_run=not apply))


# ── backup / restore ─────────────────────────────────────────────────────────

@backup_app.command("create")
def backup_create(
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    """Create a device state backup."""
    adb = _require_adb()
    device = detect_device(adb)
    bm = state.backup or BackupManager()
    try:
        path = bm.create(adb, device, output_path=output)
    except BackupError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(f"✓ backup written to {path}")


@backup_app.command("list")
def backup_list() -> None:
    """List existing backups."""
    bm = state.backup or BackupManager()
    backups = bm.list_backups()
    if not backups:
        typer.echo("No backups found.")
        return
    for p in backups:
        typer.echo(f"  {p}")


@restore_app.callback(invoke_without_command=True)
def restore_run(
    ctx: typer.Context,
    input_path: Optional[Path] = typer.Option(None, "--input"),
    latest: bool = typer.Option(False, "--latest"),
    apply: bool = typer.Option(False, "--apply"),
    launcher: bool = typer.Option(False, "--launcher", help="Also restore launcher"),
) -> None:
    """Restore from a backup file."""
    if ctx.invoked_subcommand is not None:
        return
    adb = _require_adb()
    bm = state.backup or BackupManager()

    if latest:
        backups = bm.list_backups()
        if not backups:
            typer.echo("No backups found.", err=True)
            raise typer.Exit(1)
        input_path = backups[0]

    if input_path is None:
        typer.echo("Specify --input PATH or --latest.", err=True)
        raise typer.Exit(1)

    try:
        results = bm.restore(adb, input_path, dry_run=not apply)
    except BackupError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    _print_results(results)

    if launcher and apply:
        ok = bm.restore_launcher(adb, input_path)
        typer.echo("✓ launcher restored" if ok else "✗ launcher restoration unclear")


# ── apk install ──────────────────────────────────────────────────────────────

@apk_app.command("install")
def apk_install(
    apk_path: Path = typer.Argument(..., help="Path to the local APK file"),
) -> None:
    """Install an APK file onto the connected Fire TV device."""
    adb = _require_adb()
    if not apk_path.exists():
        typer.echo(f"Error: file not found: {apk_path}", err=True)
        raise typer.Exit(1)
    if apk_path.suffix.lower() != ".apk":
        typer.echo(f"Warning: {apk_path.name} does not have an .apk extension", err=True)
    typer.echo(f"Installing {apk_path.name} …")
    try:
        adb.install(apk_path)
        typer.echo(f"✓ installed {apk_path.name}")
    except Exception as exc:
        typer.echo(f"✗ installation failed: {exc}", err=True)
        raise typer.Exit(1)


@apk_app.command("uninstall")
def apk_uninstall(
    package: str = typer.Argument(..., help="Package name, e.g. com.example.app"),
    keep_data: bool = typer.Option(True, "--keep-data/--remove-data",
                                   help="Keep app data and cache after uninstall (default: yes)"),
) -> None:
    """Uninstall a package from the connected Fire TV device."""
    adb = _require_adb()
    typer.echo(f"Uninstalling {package} …")
    try:
        ok = adb.pm_uninstall(package, keep_data=keep_data)
        if ok:
            typer.echo(f"✓ uninstalled {package}")
        else:
            typer.echo(f"✗ uninstall failed (package may not be installed or is a system app)", err=True)
            raise typer.Exit(1)
    except Exception as exc:
        typer.echo(f"✗ uninstall failed: {exc}", err=True)
        raise typer.Exit(1)
