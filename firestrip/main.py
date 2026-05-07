"""Entry point. Routes between TUI mode and CLI mode."""
import sys

CLI_SUBCOMMANDS = frozenset({
    "debloat", "telemetry", "launcher", "settings",
    "backup", "restore", "device", "setup-udev",
})


def run() -> None:
    args = sys.argv[1:]
    has_subcommand = bool(set(args) & CLI_SUBCOMMANDS)
    force_cli = "--no-tui" in args

    if has_subcommand or force_cli or not sys.stdin.isatty():
        from firestrip.cli.commands import app
        app()
    else:
        host = None
        for i, arg in enumerate(args):
            if arg == "--host" and i + 1 < len(args):
                host = args[i + 1]
        from firestrip.core.adb import ADBClient
        adb = ADBClient(host=host) if host else None
        from firestrip.tui.app import FirestripApp
        FirestripApp(adb_client=adb).run()


if __name__ == "__main__":
    run()
