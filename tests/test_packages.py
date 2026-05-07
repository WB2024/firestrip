from __future__ import annotations

from firestrip.core.packages import (
    NEVER_TOUCH,
    PRESETS,
    PackageManager,
    PackageTier,
)


def test_load_filters_never_touch(mock_adb, mock_device) -> None:
    pm = PackageManager(mock_device, mock_adb)
    pm.load()
    pkgs = {e.package_name for e in pm.get_packages(installed_only=False)}
    for never in NEVER_TOUCH:
        assert never not in pkgs


def test_get_packages_tier_filter(mock_adb, mock_device) -> None:
    pm = PackageManager(mock_device, mock_adb)
    pm.load()
    safe_only = pm.get_packages(tiers=[PackageTier.SAFE])
    assert safe_only
    assert all(e.tier == PackageTier.SAFE for e in safe_only)


def test_get_packages_installed_only(mock_adb, mock_device) -> None:
    pm = PackageManager(mock_device, mock_adb)
    pm.load()
    installed = pm.get_packages(installed_only=True)
    not_installed_filter = pm.get_packages(installed_only=False)
    assert len(not_installed_filter) >= len(installed)
    for entry in installed:
        assert entry.installed


def test_disable_dry_run(mock_adb, mock_device) -> None:
    pm = PackageManager(mock_device, mock_adb)
    pm.load()
    results = pm.disable(["com.amazon.cloud9"], dry_run=True)
    assert len(results) == 1
    assert results[0].action == "dry_run"
    assert "com.amazon.cloud9" not in mock_adb.disabled


def test_disable_apply_records_backup(mock_adb, mock_device) -> None:
    pm = PackageManager(mock_device, mock_adb)
    pm.load()

    class _FakeBackup:
        def __init__(self) -> None:
            self.recorded: list[str] = []

        def record_disabled(self, pkg: str) -> None:
            self.recorded.append(pkg)

    bm = _FakeBackup()
    results = pm.disable(["com.amazon.cloud9"], dry_run=False, backup_manager=bm)
    assert results[0].success
    assert results[0].action == "disabled"
    assert "com.amazon.cloud9" in mock_adb.disabled
    assert bm.recorded == ["com.amazon.cloud9"]


def test_disable_skips_never_touch(mock_adb, mock_device) -> None:
    pm = PackageManager(mock_device, mock_adb)
    pm.load()
    results = pm.disable(["com.amazon.tv.launcher"], dry_run=False)
    assert results[0].action == "skipped"
    assert "com.amazon.tv.launcher" not in mock_adb.disabled


def test_disable_skips_not_installed(mock_adb, mock_device) -> None:
    pm = PackageManager(mock_device, mock_adb)
    pm.load()
    results = pm.disable(["com.does.not.exist"], dry_run=False)
    assert results[0].action == "skipped"


def test_presets_safe_excludes_risky() -> None:
    assert PackageTier.SAFE in PRESETS["safe"]
    assert PackageTier.RISKY not in PRESETS["safe"]
    assert PackageTier.TELEMETRY in PRESETS["aggressive"]
