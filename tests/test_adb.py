from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from firestrip.core.adb import ADBClient
from firestrip.core.exceptions import (
    ADBBinaryNotFoundError,
    ADBCommandError,
    ADBConnectionError,
)


def _completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    cp = MagicMock(spec=subprocess.CompletedProcess)
    cp.stdout = stdout
    cp.stderr = stderr
    cp.returncode = returncode
    return cp


def test_parse_devices() -> None:
    raw = (
        "List of devices attached\n"
        "192.168.1.138:5555\tdevice\n"
        "BADSERIAL\tunauthorized\n"
    )
    assert ADBClient._parse_devices(raw) == ["192.168.1.138:5555"]


def test_pm_list_packages_parses() -> None:
    client = ADBClient(host="127.0.0.1")
    raw = "package:com.amazon.cloud9\npackage:com.amazon.venezia\n"
    with patch.object(ADBClient, "_run", return_value=_completed(stdout=raw)):
        assert client.pm_list_packages() == ["com.amazon.cloud9", "com.amazon.venezia"]


def test_connect_tcp_success() -> None:
    client = ADBClient(host="192.168.1.138")
    with patch("subprocess.run", return_value=_completed(stdout="connected to 192.168.1.138:5555")):
        assert client.connect() is True


def test_connect_tcp_failure_raises() -> None:
    client = ADBClient(host="10.0.0.99")
    with patch("subprocess.run", return_value=_completed(stdout="failed to connect")):
        with pytest.raises(ADBConnectionError):
            client.connect()


def test_connect_binary_missing() -> None:
    client = ADBClient(host="192.168.1.138")
    with patch("subprocess.run", side_effect=FileNotFoundError()):
        with pytest.raises(ADBBinaryNotFoundError):
            client.connect()


def test_shell_exception_occurred_raises() -> None:
    client = ADBClient(host="127.0.0.1")
    with patch.object(
        ADBClient, "_run", return_value=_completed(stdout="Exception occurred while executing pm")
    ):
        with pytest.raises(ADBCommandError):
            client.shell("pm list packages")


def test_pm_disable_already_disabled() -> None:
    client = ADBClient(host="127.0.0.1")
    err = ADBCommandError("pm disable", 1, "already disabled")
    with patch.object(ADBClient, "shell", side_effect=err):
        assert client.pm_disable("com.example") is True


def test_settings_get_null_returns_empty() -> None:
    client = ADBClient(host="127.0.0.1")
    with patch.object(ADBClient, "shell", return_value="null"):
        assert client.settings_get("global", "k") == ""
