# firestrip

**A Linux-native TUI/CLI tool to debloat, strip telemetry, and reclaim your Amazon Fire TV via ADB — no Windows required.**

> Take back control of your Fire TV hardware. Remove Amazon's bloatware, silence telemetry, swap out the launcher, and tune device settings — all from your Linux terminal over ADB (USB or network).

---

## Why firestrip?

Amazon Fire TV hardware is excellent. The software is not. Out of the box you get:

- A launcher plastered with ads and "recommendations"
- Dozens of pre-installed apps you cannot remove through normal means
- Aggressive telemetry and data collection you never consented to
- Amazon Sidewalk (device mesh networking) running silently in the background
- A sluggish, locked-down UI that prioritises Amazon's revenue over your experience

Existing tools are either Windows-only, macOS-only, outdated shell scripts, or don't cover Fire TV sticks at all. **firestrip** is the tool that should have existed years ago — built for Linux, safe by default, and comprehensive.

---

## Features

| Feature | Status |
|---|---|
| ADB connection manager (USB + TCP/IP) | ✅ |
| Device auto-detection and model fingerprinting | ✅ |
| Bloatware removal (per-device safe/risky/telemetry classification) | ✅ |
| Telemetry stripping (packages + ADB settings layer) | ✅ |
| Amazon Sidewalk disablement | ✅ |
| Launcher replacement (Wolf Launcher, FLauncher, Sideload Launcher) | ✅ |
| Device settings tuning | ✅ |
| Pre-action backup (full package snapshot) | ✅ |
| One-command restore from backup | ✅ |
| Dry-run mode (preview before any action) | ✅ |
| Interactive TUI (Textual-based) | ✅ |
| Headless CLI mode (scriptable) | ✅ |
| No systemd dependency | ✅ |

---

## Requirements

- **Python 3.10+**
- **ADB** installed and on `$PATH` (`android-tools-adb` on Debian/MX, `android-tools` on Arch)
- An **Amazon Fire TV** device with **ADB debugging enabled** (Settings → My Fire TV → Developer Options → ADB Debugging)
- Connected via **USB** or **network (TCP/IP)**

### Enable ADB on your Fire TV

1. Settings → My Fire TV → About → click "Build" 7 times to unlock Developer Options
2. Settings → My Fire TV → Developer Options → ADB Debugging → ON
3. For network ADB: Settings → My Fire TV → Developer Options → Network Debugging → ON

---

## Installation

### pipx (recommended)

```bash
pipx install firestrip
```

### From source

```bash
git clone https://github.com/yourusername/firestrip.git
cd firestrip
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### AppImage (no install, no deps)

Download the latest `.AppImage` from [Releases](https://github.com/yourusername/firestrip/releases), mark it executable, and run it:

```bash
chmod +x firestrip-x86_64.AppImage
./firestrip-x86_64.AppImage
```

### USB udev rules (one-time setup for rootless USB ADB)

```bash
firestrip setup-udev
# or manually:
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="1949", MODE="0666", GROUP="plugdev"' \
  | sudo tee /etc/udev/rules.d/51-android.rules
sudo udevadm control --reload-rules && sudo udevadm trigger
```

---

## Usage

### TUI Mode (default)

```bash
# Auto-detect connected device
firestrip

# Connect to a specific network device
firestrip --host 192.168.1.42

# Connect via USB
firestrip --usb
```

### CLI / Headless Mode

```bash
# List all installed bloat packages (no action)
firestrip --host 192.168.1.42 debloat --list

# Preview what would be removed (dry-run, safe preset)
firestrip --host 192.168.1.42 debloat --preset safe --dry-run

# Apply safe debloat
firestrip --host 192.168.1.42 debloat --preset safe --apply

# Strip all telemetry
firestrip --host 192.168.1.42 telemetry strip

# Set a replacement launcher
firestrip --host 192.168.1.42 launcher set wolf

# Backup current package state
firestrip --host 192.168.1.42 backup --output ~/firetv-backup.json

# Restore from backup
firestrip --host 192.168.1.42 restore --input ~/firetv-backup.json

# USB variants
firestrip --usb debloat --preset safe --apply
firestrip --usb telemetry strip
```

---

## TUI Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  firestrip  v0.1.0                  Device: Fire TV Stick 4K    │
│  Connected: 192.168.1.42:5555 ✓     Android 9 / FireOS 7.x     │
├──────────────────┬──────────────────────────────────────────────┤
│                  │                                              │
│  [1] Debloat     │  Installed Bloat Packages  (34 found)        │
│  [2] Telemetry   │  ┌──────────────────────────────────────┐   │
│  [3] Launcher    │  │ [x] com.amazon.avod          SAFE    │   │
│  [4] Settings    │  │ [x] com.audible.application  SAFE    │   │
│  [5] Backup      │  │ [x] com.amazon.bueller       SAFE    │   │
│  [6] Restore     │  │ [ ] com.amazon.venezia       RISKY   │   │
│  [q] Quit        │  │ [x] com.amazon.device.metrics  TEL.  │   │
│                  │  └──────────────────────────────────────┘   │
│                  │  [A]ll  [N]one  [S]afe only  [P]review      │
│                  │                      [ENTER] Apply Changes   │
└──────────────────┴──────────────────────────────────────────────┘
```

Navigate with arrow keys or mouse. All actions show a confirmation + dry-run preview before executing.

---

## Package Classification

firestrip categorises every Fire TV package into one of four tiers:

| Tier | Colour | Description |
|---|---|---|
| `SAFE` | Green | Confirmed safe to remove. No system dependencies. |
| `RISKY` | Yellow | Removable but may affect some functionality. Warned before action. |
| `TELEMETRY` | Orange | Data collection and reporting services. |
| `NEVER_TOUCH` | Red | System-critical. firestrip will not touch these. |

All actions use `pm disable-user --user 0` (reversible) rather than hard uninstall wherever possible. Your device will not brick.

---

## Supported Launchers

| Name | Package | Notes |
|---|---|---|
| **Wolf Launcher** | `eu.wolfgangstudios.launcher` | Polished, no ads, TMDB metadata |
| **FLauncher** | `me.efesser.flauncher` | Open source, minimal, keyboard-friendly |
| **Sideload Launcher** | `com.riverrock.sideload` | Lightweight, shows all sideloaded apps |

The launcher swap workflow installs the new launcher first, sets it as the default HOME intent handler, then freezes (not removes) the Amazon launcher — so you always have a fallback.

---

## Supported Devices

| Device | Status |
|---|---|
| Fire TV Stick (3rd Gen) | ✅ Tested |
| Fire TV Stick 4K | ✅ Tested |
| Fire TV Stick 4K Max | ✅ Tested |
| Fire TV Stick Lite | ✅ Tested |
| Fire TV Cube (1st/2nd Gen) | ⚠️ Community tested |
| Fire TV (pendant/box) | ⚠️ Community tested |

Device fingerprinting loads the correct package list per model. Package names and safe/risky classification differ between FireOS versions.

---

## Safety Model

firestrip is designed to be **impossible to brick your device with**, assuming you have not already rooted it:

- **Dry-run by default** — nothing happens until you explicitly confirm
- **Backup first** — a full package snapshot is saved before any destructive action
- **Disable, don't delete** — `pm disable-user` keeps the package on disk, re-enabling is one command
- **Locked safe list** — `com.amazon.tv.launcher`, `android`, `com.android.systemui` and other critical packages cannot be selected
- **Model-aware lists** — package lists are per-device, no guessing across models
- **Restore command** — re-enable any package from any backup in one step

---

## Telemetry Stripped

Beyond package removal, firestrip applies ADB settings-level overrides:

| Setting | Effect |
|---|---|
| `amazon:device_metrics_opt_in = 0` | Opt out of device metrics |
| `limit_ad_tracking = 1` | Disable ad tracking identifier |
| `amazon:interest_based_ads = 0` | Disable interest-based ad profiling |
| `amazon:sidewalk_enabled = 0` | Disable Amazon Sidewalk mesh network |
| `usage_stats = 0` | Disable usage statistics collection |

---

## MX Linux / Systemdless Notes

firestrip was designed with **MX Linux** (and other systemdless distributions) as a first-class target:

- Zero `systemd` dependencies anywhere in the codebase
- Manages `adb start-server` / `adb kill-server` itself via subprocess
- Reconnects automatically when Fire TV wakes from sleep
- Distributed as AppImage for maximum portability (no install, no package manager)
- udev rules provided as a setup helper, no daemon required after

---

## Contributing

Contributions are very welcome — especially:

- **Package list updates** for new FireOS versions
- **New device profiles** (Cube, pendant Fire TV)
- **Launcher integrations**
- **Testing on non-4K hardware**

See [DESIGN.md](DESIGN.md) for the full architecture and developer reference before contributing.

---

## Disclaimer

This tool interacts with your device over ADB using only standard, documented Android commands. It does not exploit any vulnerabilities, does not require root, and does not modify system partitions. Use at your own risk. firestrip is not affiliated with Amazon in any way.

---

## License

[MIT](LICENSE)
