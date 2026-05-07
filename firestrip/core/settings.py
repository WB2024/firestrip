from __future__ import annotations

from .adb import ADBClient
from .exceptions import ADBError
from .packages import ActionResult

DEVICE_SETTINGS: list[tuple[str, str, str, str]] = [
    ("system", "screen_brightness_mode", "0", "Disable auto-brightness (set manual)"),
    ("global", "transition_animation_scale", "0.5", "Speed up UI transition animations"),
    ("global", "window_animation_scale", "0.5", "Speed up window open/close animations"),
    ("global", "animator_duration_scale", "0.5", "Speed up general animator durations"),
    ("global", "stay_on_while_plugged_in", "3", "Keep screen on while charging"),
]


def apply_settings(
    adb: ADBClient,
    keys: list[str] | None = None,
    dry_run: bool = True,
) -> list[ActionResult]:
    results: list[ActionResult] = []
    for namespace, key, value, desc in DEVICE_SETTINGS:
        if keys is not None and not any(desc.startswith(k) for k in keys):
            continue
        label = f"{namespace}/{key}"
        if dry_run:
            results.append(ActionResult(label, True, "dry_run", f"would set {value}"))
            continue
        try:
            ok = adb.settings_put(namespace, key, value)
            results.append(
                ActionResult(label, ok, "set" if ok else "error",
                             "" if ok else "settings put returned non-zero")
            )
        except ADBError as exc:
            results.append(ActionResult(label, False, "error", str(exc)))
    return results


def read_current(adb: ADBClient) -> dict[str, str]:
    out: dict[str, str] = {}
    for namespace, key, _value, _desc in DEVICE_SETTINGS:
        label = f"{namespace}/{key}"
        try:
            out[label] = adb.settings_get(namespace, key)
        except ADBError:
            out[label] = ""
    return out
