from __future__ import annotations

from typing import TYPE_CHECKING

from textual.screen import Screen

if TYPE_CHECKING:
    from ...core.adb import ADBClient
    from ...core.backup import BackupManager
    from ...core.config import Config
    from ...core.device import FireTVDevice


class FirestripScreen(Screen):
    """Base class for firestrip screens. Provides typed access to shared state."""

    @property
    def adb(self) -> "ADBClient | None":
        return self.app.adb_client  # type: ignore[attr-defined]

    @property
    def device(self) -> "FireTVDevice | None":
        return self.app.device  # type: ignore[attr-defined]

    @property
    def backup(self) -> "BackupManager":
        return self.app.backup_manager  # type: ignore[attr-defined]

    @property
    def fs_config(self) -> "Config":
        return self.app.config  # type: ignore[attr-defined]
