from __future__ import annotations

from pathlib import Path

import pytest

from firestrip.core.backup import BackupManager
from firestrip.core.device import FireTVDevice

MOCK_INSTALLED_PACKAGES = [
    "com.amazon.cloud9",
    "com.amazon.bueller.music",
    "com.amazon.bueller.photos",
    "com.audible.application.firetv",
    "com.amazon.venezia",
    "com.amazon.storm.lightning.tutorial",
    "com.amazon.gamehub",
    "com.amazon.ftv.screensaver",
    "com.amazon.device.metrics",
    "com.amazon.client.metrics",
    "com.amazon.client.metrics.api",
    "com.amazon.tv.fw.metrics",
    "com.amazon.wirelessmetrics.service",
    "com.amazon.adep",
    "com.amazon.tv.acr",
    "com.amazon.ftvads.deeplinking",
    "com.amazon.hybridadidservice",
    "com.amazon.sneakpeek",
    "com.amazon.tv.csapp",
    "com.amazon.shoptv.client",
    "com.amazon.whisperlink.core.android",
    "com.amazon.whisperjoin.middleware.np",
    "com.amazon.whisperplay.service.install",
    "com.amazon.tv.ottssocompanionapp",
    "com.amazon.perfcollection",
    "com.amazon.tv.launcher",
    "com.amazon.firehomestarter",
    "amazon.fireos",
    "android",
    "com.android.systemui",
    "com.android.settings",
    "com.android.shell",
    "com.amazon.platform",
    "com.amazon.tv.channelscan",
    "com.amazon.tv.livetv",
    "com.amazon.tv.conditionalaccess",
    "com.mediatek.tvinput",
]


class MockADBClient:
    def __init__(self) -> None:
        self.disabled: set[str] = set()
        self.settings: dict[str, str] = {}
        self.commands_run: list[str] = []
        self.installed_packages: list[str] = list(MOCK_INSTALLED_PACKAGES)
        self.connected: bool = True
        self.current_home = "com.amazon.tv.launcher"

    def connect(self) -> bool:
        return self.connected

    def disconnect(self) -> None:
        pass

    def shell(self, cmd: str, timeout: int = 30) -> str:
        self.commands_run.append(cmd)
        if "resolve-activity" in cmd:
            return f"{self.current_home}/.ui.HomeActivity"
        if cmd.startswith("dumpsys package"):
            return ""
        return ""

    def install(self, apk_path) -> bool:
        return True

    def push(self, local, remote) -> bool:
        return True

    def pull(self, remote, local) -> bool:
        return True

    def pm_disable(self, package: str) -> bool:
        self.disabled.add(package)
        return True

    def pm_enable(self, package: str) -> bool:
        self.disabled.discard(package)
        return True

    def pm_uninstall(self, package: str, keep_data: bool = True) -> bool:
        return True

    def pm_list_packages(self) -> list[str]:
        return list(self.installed_packages)

    def settings_put(self, namespace: str, key: str, value: str) -> bool:
        self.settings[f"{namespace}/{key}"] = value
        return True

    def settings_get(self, namespace: str, key: str) -> str:
        return self.settings.get(f"{namespace}/{key}", "")

    def get_prop(self, key: str) -> str:
        props = {
            "ro.product.model": "AFTBOXE1",
            "ro.build.version.release": "9",
            "ro.build.description": "juliana-user 9 PS7712.5370N 0035199973888 amz-p,release-keys",
            "ro.serialno": "G4H3W100426600GM",
        }
        return props.get(key, "")


@pytest.fixture
def mock_adb() -> MockADBClient:
    return MockADBClient()


@pytest.fixture
def mock_device() -> FireTVDevice:
    return FireTVDevice(
        serial="G4H3W100426600GM",
        model="AFTBOXE1",
        model_name="Fire TV Box (4K)",
        fireos_version="PS7712.5370N",
        android_version="9",
        profile_key="firetv_box",
    )


@pytest.fixture
def backup_manager() -> BackupManager:
    return BackupManager()


@pytest.fixture
def tmp_backup_dir(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setattr(BackupManager, "DEFAULT_DIR", tmp_path / "backups")
    return tmp_path / "backups"
