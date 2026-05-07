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

### From source (current recommended method)

```bash
git clone https://github.com/WB2024/firestrip.git
cd firestrip
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### pipx *(not yet published to PyPI)*

```bash
# coming once published:
pipx install firestrip
```

### AppImage *(not yet built)*

> AppImage packaging is planned for a future release. Track progress in [Releases](https://github.com/yourusername/firestrip/releases).

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
# Show connected device info
firestrip --host 192.168.1.138 device

# List all packages eligible for removal
firestrip --host 192.168.1.138 debloat list

# Preview what safe debloat would do (dry-run is the default — no --apply = no action)
firestrip --host 192.168.1.138 debloat run --preset safe

# Apply safe debloat
firestrip --host 192.168.1.138 debloat run --preset safe --apply

# Apply aggressive debloat (safe + risky + telemetry packages)
firestrip --host 192.168.1.138 debloat run --preset aggressive --apply

# Remove a single specific package
firestrip --host 192.168.1.138 debloat run --package com.amazon.bueller.music --apply

# Show current telemetry setting values
firestrip --host 192.168.1.138 telemetry status

# Strip all telemetry (settings + service packages)
firestrip --host 192.168.1.138 telemetry strip --apply

# List available launchers
firestrip --host 192.168.1.138 launcher list

# Set a replacement launcher (APK must be installed or passed with --apk)
firestrip --host 192.168.1.138 launcher set wolf --apply
firestrip --host 192.168.1.138 launcher set wolf --apk ~/Wolf.apk --apply

# Restore Amazon launcher
firestrip --host 192.168.1.138 launcher restore --apply

# Create a backup
firestrip --host 192.168.1.138 backup create --output ~/firetv-backup.json

# List saved backups
firestrip --host 192.168.1.138 backup list

# Restore from backup (dry-run preview)
firestrip --host 192.168.1.138 restore --input ~/firetv-backup.json

# Restore from backup (apply)
firestrip --host 192.168.1.138 restore --input ~/firetv-backup.json --apply

# Restore most recent backup including launcher
firestrip --host 192.168.1.138 restore --latest --launcher --apply

# USB variants
firestrip --usb debloat run --preset safe --apply
firestrip --usb telemetry strip --apply
```

---

## TUI Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  firestrip  v0.1.0                  Device: Fire TV Box (4K)    │
│  Connected: 192.168.1.138:5555 ✓    Android 9 / PS7712.5370N   │
├──────────────────┬──────────────────────────────────────────────┤
│                  │                                              │
│  [1] Debloat     │  Installed Bloat Packages  (34 found)        │
│  [2] Telemetry   │  ┌──────────────────────────────────────┐   │
│  [3] Launcher    │  │ [x] com.amazon.venezia       SAFE    │   │
│  [4] Settings    │  │ [x] com.amazon.bueller.music SAFE    │   │
│  [5] Backup      │  │ [x] com.amazon.cloud9        SAFE    │   │
│  [q] Quit        │  │ [ ] com.amazon.device.software.ota RISKY │
│                  │  │ [x] com.amazon.device.metrics  TEL.  │   │
│                  │  └──────────────────────────────────────┘   │
│                  │  [A]ll  [N]one  [S]afe only  [P]review      │
│                  │                      [ENTER] Apply Changes   │
└──────────────────┴──────────────────────────────────────────────┘
```

Navigate with arrow keys or mouse. All actions show a confirmation + dry-run preview before executing. The **Backup** screen handles both creating backups and restoring from previous ones.

---

## Package Classification

firestrip categorises every Fire TV package into one of four tiers:

| Tier | Colour | Description |
|---|---|---|
| `SAFE` | Green | Confirmed safe to remove. No system dependencies. |
| `RISKY` | Yellow | Removable but may affect some functionality. Warned before action. |
| `TELEMETRY` | Red | Data collection and reporting services. |
| `NEVER_TOUCH` | Muted | System-critical. firestrip will not touch these. Not shown in UI. |

Debloat presets:
- `safe` — only `SAFE` tier packages
- `telemetry` — only `TELEMETRY` tier packages
- `aggressive` — all of `SAFE` + `RISKY` + `TELEMETRY`

All actions use `pm disable-user --user 0` (reversible) rather than hard uninstall wherever possible. Your device will not brick.

---

## Supported Launchers

| Name | Package | Notes |
|---|---|---|
| **Wolf Launcher** | `eu.wolfgangstudios.launcher` | Polished, no ads, TMDB metadata |
| **FLauncher** | `me.efesser.flauncher` | Open source, minimal, keyboard-friendly |
| **Sideload Launcher** | `com.riverrock.sideload` | Lightweight, shows all sideloaded apps |

The launcher swap workflow: install the new launcher (or accept a local APK path via `--apk`), set it as the default HOME intent handler, then freeze (not remove) the Amazon launcher. The Amazon launcher is re-enabled automatically if you run `launcher restore`.

---

## Supported Devices

| Device | Model Code | Status |
|---|---|---|
| **Fire TV Box (4K)** | `AFTBOXE1` | ✅ **Primary reference device — fully tested** |
| Fire TV Stick (3rd Gen) | `AFTE` | ⚠️ Community tested |
| Fire TV Stick 4K | `AFTMM` | ⚠️ Community tested |
| Fire TV Stick 4K Max | `AFTKA` | ⚠️ Community tested |
| Fire TV Stick Lite | `AFTS` | ⚠️ Community tested |
| Fire TV Cube (1st Gen) | `AFTR` | ⚠️ Community tested |
| Fire TV Cube (2nd Gen) | `AFTRS` | ⚠️ Community tested |

> The **Fire TV Box (`AFTBOXE1`, codename `juliana`)** running FireOS `PS7712.5370N` (Android 9, SDK 28, MediaTek m7632) is the primary development and test device. All package lists, telemetry constants, and fixture data are sourced from this real hardware. If you have this exact model, firestrip works out of the box.

> **Fire TV Box users:** firestrip never touches the integrated live TV tuner packages (`com.amazon.tv.channelscan`, `com.amazon.tv.livetv`, `com.amazon.tv.conditionalaccess`, `com.mediatek.tvinput`). These are in the protected `NEVER_TOUCH` list.

Device fingerprinting loads the correct package list per model. Package names and safe/risky classification differ between FireOS versions. Unknown models fall back to the common package list with a warning.

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

Beyond package removal, firestrip applies ADB settings-level overrides. On the AFTBOXE1 (and likely all Fire TV devices) these settings are not explicitly stored — Amazon relies on opaque defaults. firestrip writes explicit opt-out values regardless.

| Setting | Effect |
|---|---|
| `global/amazon:device_metrics_opt_in = 0` | Opt out of device metrics reporting |
| `global/limit_ad_tracking = 1` | Disable advertising tracking identifier |
| `global/amazon:interest_based_ads = 0` | Disable interest-based ad profiling |
| `global/amazon:sidewalk_enabled = 0` | Disable Amazon Sidewalk mesh network |
| `secure/usage_stats = 0` | Disable usage statistics collection |
| `global/amazon:data_monitoring_consent = 0` | Revoke data monitoring consent |
| `global/amazon:acr_enabled = 0` | Disable ACR (Automatic Content Recognition) |

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
