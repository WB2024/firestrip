from __future__ import annotations

from textual.app import App
from textual.binding import Binding
from textual import work

from ..core.adb import ADBClient
from ..core.backup import BackupManager
from ..core.config import Config, load_config
from ..core.device import FireTVDevice, detect_device
from ..core.exceptions import ADBBinaryNotFoundError, ADBConnectionError


class FirestripApp(App):
    TITLE = "firestrip"
    CSS_PATH = "app.tcss"
    BINDINGS = [
        Binding("q", "quit", "Quit"),
    ]

    adb_client: ADBClient | None
    device: FireTVDevice | None
    backup_manager: BackupManager
    config: Config

    def __init__(self, adb_client: ADBClient | None = None) -> None:
        super().__init__()
        self.adb_client = adb_client
        self.device = None
        self.backup_manager = BackupManager()
        self.config = load_config()

    def on_mount(self) -> None:
        from .screens.backup import BackupScreen
        from .screens.debloat import DebloatScreen
        from .screens.home import HomeScreen
        from .screens.launcher import LauncherScreen
        from .screens.settings import SettingsScreen
        from .screens.telemetry import TelemetryScreen

        self.install_screen(HomeScreen, name="home")
        self.install_screen(DebloatScreen, name="debloat")
        self.install_screen(TelemetryScreen, name="telemetry")
        self.install_screen(LauncherScreen, name="launcher")
        self.install_screen(SettingsScreen, name="settings")
        self.install_screen(BackupScreen, name="backup")

        self.push_screen("home")

        if self.adb_client is not None:
            self.connect_device()

    @work(thread=True)
    def connect_device(self) -> None:
        if self.adb_client is None:
            return
        try:
            self.adb_client.connect()
            self.device = detect_device(self.adb_client)
        except (ADBConnectionError, ADBBinaryNotFoundError) as exc:
            self.call_from_thread(self.notify, f"Connection error: {exc}", severity="error")
            return
        self.call_from_thread(self._refresh_home)

    def _refresh_home(self) -> None:
        screen = self.screen
        if hasattr(screen, "refresh_status"):
            screen.refresh_status()
