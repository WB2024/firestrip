from __future__ import annotations

from firestrip.core.telemetry import (
    TELEMETRY_SERVICES,
    TELEMETRY_SETTINGS,
    strip_services,
    strip_settings,
)


def test_strip_settings_dry_run(mock_adb) -> None:
    results = strip_settings(mock_adb, dry_run=True)
    assert len(results) == len(TELEMETRY_SETTINGS)
    assert all(r.action == "dry_run" for r in results)
    assert mock_adb.settings == {}


def test_strip_settings_apply(mock_adb) -> None:
    results = strip_settings(mock_adb, dry_run=False)
    assert all(r.success for r in results)
    assert mock_adb.settings["global/amazon:device_metrics_opt_in"] == "0"
    assert mock_adb.settings["secure/usage_stats"] == "0"


def test_strip_services_skips_absent(mock_adb) -> None:
    mock_adb.installed_packages = ["com.amazon.device.metrics"]
    results = strip_services(mock_adb, dry_run=False)
    actions = {r.package: r.action for r in results}
    assert actions["com.amazon.device.metrics"] == "disabled"
    for svc in TELEMETRY_SERVICES:
        if svc != "com.amazon.device.metrics":
            assert actions[svc] == "skipped"


def test_strip_services_dry_run(mock_adb) -> None:
    results = strip_services(mock_adb, dry_run=True)
    actions = {r.action for r in results}
    assert "dry_run" in actions
    assert mock_adb.disabled == set()
