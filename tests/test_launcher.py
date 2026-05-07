from __future__ import annotations

import pytest

from firestrip.core.exceptions import LauncherSwapError
from firestrip.core.launcher import (
    AMAZON_LAUNCHER_PKG,
    LauncherInfo,
    LauncherManager,
    load_launchers,
)


def _wolf_launcher() -> LauncherInfo:
    for l in load_launchers():
        if l.key == "wolf":
            return l
    return load_launchers()[0]


def test_load_launchers_has_entries() -> None:
    launchers = load_launchers()
    assert launchers
    keys = {l.key for l in launchers}
    assert "wolf" in keys or "flauncher" in keys


def test_swap_dry_run(mock_adb) -> None:
    mgr = LauncherManager(mock_adb)
    results = mgr.swap(_wolf_launcher(), dry_run=True)
    assert len(results) == 4
    assert all(r.action == "dry_run" for r in results)


def test_swap_step3_safety_gate(mock_adb) -> None:
    launcher = _wolf_launcher()
    mock_adb.installed_packages = list(mock_adb.installed_packages) + [launcher.package]
    # current_home stays as Amazon; step 3 now emits a warning instead of raising
    mgr = LauncherManager(mock_adb)
    results = mgr.swap(launcher, dry_run=False)
    # Should have completed all 4 steps (no exception)
    step3 = next((r for r in results if r.action == "warning"), None)
    assert step3 is not None, "Expected a step-3 warning result"
    assert launcher.package in step3.message or "HOME" in step3.message
    # Amazon launcher should still have been frozen (step 4 runs regardless)
    assert AMAZON_LAUNCHER_PKG in mock_adb.disabled


def test_swap_full_success(mock_adb) -> None:
    launcher = _wolf_launcher()
    mock_adb.installed_packages = list(mock_adb.installed_packages) + [launcher.package]

    # Make resolve-activity reflect new launcher after set_default
    original_shell = mock_adb.shell

    def shell(cmd: str, timeout: int = 30) -> str:
        if "set-home-activity" in cmd:
            mock_adb.current_home = launcher.package
        return original_shell(cmd, timeout)

    mock_adb.shell = shell  # type: ignore[method-assign]
    mgr = LauncherManager(mock_adb)
    results = mgr.swap(launcher, dry_run=False)
    assert any(r.action == "verified" for r in results)
    assert AMAZON_LAUNCHER_PKG in mock_adb.disabled


def test_freeze_and_restore_amazon(mock_adb) -> None:
    mgr = LauncherManager(mock_adb)
    assert mgr.freeze_amazon_launcher() is True
    assert AMAZON_LAUNCHER_PKG in mock_adb.disabled
    assert mgr.restore_amazon_launcher() is True
    assert AMAZON_LAUNCHER_PKG not in mock_adb.disabled
