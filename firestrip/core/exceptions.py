from pathlib import Path


class FirestripError(Exception):
    """Base class for all firestrip exceptions."""


class ADBError(FirestripError):
    """Base class for ADB-related errors."""


class ADBBinaryNotFoundError(ADBError):
    """The `adb` binary is not on PATH."""


class ADBConnectionError(ADBError):
    """Could not connect to the device."""


class ADBCommandError(ADBError):
    """An adb command returned a non-zero exit code."""

    def __init__(self, cmd: str, returncode: int, stderr: str) -> None:
        self.cmd = cmd
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(f"Command failed (exit {returncode}): {cmd!r}\n{stderr}")


class ADBTimeoutError(ADBError):
    """An adb command exceeded its timeout."""


class DeviceError(FirestripError):
    """Base class for device-related errors."""


class UnknownDeviceError(DeviceError):
    """Model code not found in MODEL_MAP."""


class DataError(FirestripError):
    """Base class for data loading errors."""


class DataLoadError(DataError):
    """A TOML data file could not be parsed."""

    def __init__(self, path: Path, detail: str) -> None:
        self.path = path
        super().__init__(f"Failed to load {path}: {detail}")


class BackupError(FirestripError):
    """Backup creation or restore failed."""


class LauncherError(FirestripError):
    """Base class for launcher errors."""


class LauncherSwapError(LauncherError):
    """The launcher swap workflow failed at a specific step."""

    def __init__(self, step: int, detail: str) -> None:
        self.step = step
        super().__init__(f"Launcher swap failed at step {step}: {detail}")


class DeviceWarning(UserWarning):
    """Emitted when a device model is unrecognised; execution continues."""
