from __future__ import annotations

import subprocess
from pathlib import Path

from .exceptions import (
    ADBBinaryNotFoundError,
    ADBCommandError,
    ADBConnectionError,
    ADBTimeoutError,
)

_ADB_NOT_FOUND_MSG = (
    "adb binary not found. Install android-tools-adb (Debian/Ubuntu/MX) "
    "or android-tools (Arch)."
)


class ADBClient:
    def __init__(
        self,
        host: str | None = None,
        port: int = 5555,
        serial: str | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._serial = serial

        if host:
            self._target: list[str] = ["-s", f"{host}:{port}"]
        elif serial:
            self._target = ["-s", serial]
        else:
            self._target = []

    @property
    def host(self) -> str | None:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    @property
    def serial(self) -> str | None:
        return self._serial

    def connect(self) -> bool:
        if self._host:
            return self._connect_tcp()
        return self._connect_usb()

    def _connect_tcp(self) -> bool:
        target = f"{self._host}:{self._port}"
        # Fast path: already listed as connected by a running adb server
        try:
            check = subprocess.run(
                ["adb", "devices"], capture_output=True, text=True, timeout=5
            )
            if target in (check.stdout or ""):
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        cmd = ["adb", "connect", target]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        except FileNotFoundError as exc:
            raise ADBBinaryNotFoundError(_ADB_NOT_FOUND_MSG) from exc
        except subprocess.TimeoutExpired as exc:
            raise ADBTimeoutError(f"connect timed out: {' '.join(cmd)}") from exc

        out = (result.stdout or "") + (result.stderr or "")
        low = out.lower()
        if "already connected" in low or "connected to" in low:
            return True
        if low.strip().startswith("failed") or "cannot connect" in low or "unable" in low:
            raise ADBConnectionError(f"Failed to connect to {self._host}:{self._port}: {out.strip()}")
        # Empty output typically means success on some adb versions
        if result.returncode == 0 and not out.strip():
            return True
        raise ADBConnectionError(f"Could not connect to {self._host}:{self._port}: {out.strip()}")

    def _connect_usb(self) -> bool:
        try:
            result = subprocess.run(
                ["adb", "devices"], capture_output=True, text=True, timeout=15
            )
        except FileNotFoundError as exc:
            raise ADBBinaryNotFoundError(_ADB_NOT_FOUND_MSG) from exc
        except subprocess.TimeoutExpired as exc:
            raise ADBTimeoutError("adb devices timed out") from exc

        devices = self._parse_devices(result.stdout or "")
        if not devices:
            # Try start-server once
            try:
                subprocess.run(["adb", "start-server"], capture_output=True, text=True, timeout=15)
            except FileNotFoundError as exc:
                raise ADBBinaryNotFoundError(_ADB_NOT_FOUND_MSG) from exc
            except subprocess.TimeoutExpired:
                pass
            result = subprocess.run(
                ["adb", "devices"], capture_output=True, text=True, timeout=15
            )
            devices = self._parse_devices(result.stdout or "")

        # Check unauthorized
        for line in (result.stdout or "").splitlines()[1:]:
            if "\t" in line:
                state = line.split("\t")[1].strip()
                if state == "unauthorized":
                    raise ADBConnectionError(
                        "Device is unauthorized. Accept the ADB debugging prompt on your Fire TV."
                    )

        if not devices:
            raise ADBConnectionError("No USB device detected. Connect Fire TV and enable ADB.")

        if self._serial:
            if self._serial in devices:
                return True
            raise ADBConnectionError(
                f"Device with serial {self._serial} not found. Available: {', '.join(devices)}"
            )

        if len(devices) > 1:
            raise ADBConnectionError(
                "Multiple devices connected. Use --serial to choose one. "
                f"Found: {', '.join(devices)}"
            )
        return True

    @staticmethod
    def _parse_devices(raw: str) -> list[str]:
        lines = raw.strip().splitlines()
        if lines and lines[0].lower().startswith("list of devices"):
            lines = lines[1:]
        out: list[str] = []
        for line in lines:
            if "\t" in line:
                serial, state = line.split("\t", 1)
                if state.strip() == "device":
                    out.append(serial.strip())
        return out

    def disconnect(self) -> None:
        if not self._host:
            return
        try:
            subprocess.run(
                ["adb", "disconnect", f"{self._host}:{self._port}"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    def _run(self, args: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
        cmd = ["adb"] + self._target + args
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        except FileNotFoundError as exc:
            raise ADBBinaryNotFoundError(_ADB_NOT_FOUND_MSG) from exc
        except subprocess.TimeoutExpired as exc:
            raise ADBTimeoutError(f"Command timed out: {' '.join(cmd)}") from exc

    def shell(self, cmd: str, timeout: int = 30) -> str:
        result = self._run(["shell", cmd], timeout=timeout)
        if result.returncode != 0:
            raise ADBCommandError(cmd, result.returncode, result.stderr or "")
        out = (result.stdout or "").strip()
        if "Exception occurred while executing" in out:
            raise ADBCommandError(cmd, 0, out)
        return out

    def install(self, apk_path: str | Path) -> bool:
        result = self._run(["install", "-r", str(apk_path)], timeout=120)
        out = (result.stdout or "") + (result.stderr or "")
        if result.returncode == 0 and "Success" in out:
            return True
        raise ADBCommandError(f"install {apk_path}", result.returncode, out)

    def push(self, local: str | Path, remote: str) -> bool:
        result = self._run(["push", str(local), remote], timeout=120)
        return result.returncode == 0

    def pull(self, remote: str, local: str | Path) -> bool:
        result = self._run(["pull", remote, str(local)], timeout=120)
        return result.returncode == 0

    def pm_disable(self, package: str) -> bool:
        try:
            out = self.shell(f"pm disable-user --user 0 {package}")
        except ADBCommandError as exc:
            text = (exc.stderr or "") + str(exc)
            if "already disabled" in text.lower():
                return True
            raise
        low = out.lower()
        if "disabled" in low or "already disabled" in low:
            return True
        return False

    def pm_enable(self, package: str) -> bool:
        out = self.shell(f"pm enable --user 0 {package}")
        return "enabled" in out.lower()

    def pm_uninstall(self, package: str, keep_data: bool = True) -> bool:
        flag = "--keep-data " if keep_data else ""
        out = self.shell(f"pm uninstall {flag}--user 0 {package}")
        return out.strip() == "Success"

    def pm_list_packages(self) -> list[str]:
        out = self.shell("pm list packages")
        result: list[str] = []
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("package:"):
                result.append(line.split("package:", 1)[1])
        return result

    def settings_put(self, namespace: str, key: str, value: str) -> bool:
        result = self._run(["shell", f"settings put {namespace} {key} {value}"])
        return result.returncode == 0

    def settings_get(self, namespace: str, key: str) -> str:
        out = self.shell(f"settings get {namespace} {key}")
        if out.strip().lower() == "null":
            return ""
        return out

    def get_prop(self, key: str) -> str:
        return self.shell(f"getprop {key}")
