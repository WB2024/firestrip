from __future__ import annotations

import re
import warnings
from dataclasses import dataclass

from .adb import ADBClient
from .exceptions import DeviceWarning, UnknownDeviceError

GENERIC_PROFILE_KEY = "common"

MODEL_MAP: dict[str, tuple[str, str]] = {
    "AFTBOXE1": ("Fire TV Box (4K)", "firetv_box"),
    "AFTT": ("Fire TV Stick (2nd Gen)", "firetv_stick_2g"),
    "AFTMM": ("Fire TV Stick 4K", "firetv_stick_4k"),
    "AFTR": ("Fire TV Cube (1st Gen)", "firetv_cube"),
    "AFTRS": ("Fire TV Cube (2nd Gen)", "firetv_cube"),
    "AFTE": ("Fire TV Stick (3rd Gen)", "firetv_stick_3g"),
    "AFTKA": ("Fire TV Stick 4K Max", "firetv_stick_4k_max"),
    "AFTS": ("Fire TV Stick Lite", "firetv_stick_lite"),
}

FIREOS_VERSION_RE = re.compile(r"(\d+\.\d+\.\d+\.\d+)")


@dataclass
class FireTVDevice:
    serial: str
    model: str
    model_name: str
    fireos_version: str
    android_version: str
    profile_key: str


def detect_device(adb: ADBClient) -> FireTVDevice:
    model = adb.get_prop("ro.product.model").strip()
    android_version = adb.get_prop("ro.build.version.release").strip()
    description = adb.get_prop("ro.build.description").strip()
    serial = adb.get_prop("ro.serialno").strip()

    match = FIREOS_VERSION_RE.search(description)
    fireos_version = match.group(1) if match else "unknown"

    try:
        if model not in MODEL_MAP:
            raise UnknownDeviceError(model)
        model_name, profile_key = MODEL_MAP[model]
    except UnknownDeviceError:
        warnings.warn(f"Unrecognised model: {model}", DeviceWarning, stacklevel=2)
        model_name = f"Unknown Fire TV ({model})"
        profile_key = GENERIC_PROFILE_KEY

    return FireTVDevice(
        serial=serial,
        model=model,
        model_name=model_name,
        fireos_version=fireos_version,
        android_version=android_version,
        profile_key=profile_key,
    )
