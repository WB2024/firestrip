from __future__ import annotations

from .adb import ADBClient
from .exceptions import ADBError
from .packages import ActionResult

TELEMETRY_SETTINGS: list[tuple[str, str, str, str]] = [
    ("global", "amazon:device_metrics_opt_in", "0", "Opt out of device metrics reporting"),
    ("global", "limit_ad_tracking", "1", "Disable advertising tracking identifier"),
    ("global", "amazon:interest_based_ads", "0", "Disable interest-based ad profiling"),
    ("global", "amazon:sidewalk_enabled", "0", "Disable Amazon Sidewalk mesh network"),
    ("secure", "usage_stats", "0", "Disable usage statistics collection"),
    ("global", "amazon:data_monitoring_consent", "0", "Revoke data monitoring consent"),
    ("global", "amazon:acr_enabled", "0", "Disable ACR (Automatic Content Recognition)"),
]

TELEMETRY_SERVICES: list[str] = [
    "com.amazon.device.metrics",
    "com.amazon.client.metrics",
    "com.amazon.client.metrics.api",
    "com.amazon.tv.fw.metrics",
    "com.amazon.wirelessmetrics.service",
    "com.amazon.adep",
    "com.amazon.whisperlink.core.android",
    "com.amazon.whisperjoin.middleware.np",
    "com.amazon.whisperplay.service.install",
    "com.amazon.tv.acr",
    "com.amazon.ftvads.deeplinking",
    "com.amazon.hybridadidservice",
    "com.amazon.sneakpeek",
    "com.amazon.tv.csapp",
    "com.amazon.shoptv.client",
    "com.amazon.zazu",
    "com.amazon.csapp",
    "com.amazon.ags",
    "com.amazon.advertisingidsystem",
    "com.amazon.compass",
]


def strip_settings(adb: ADBClient, dry_run: bool = True) -> list[ActionResult]:
    results: list[ActionResult] = []
    for namespace, key, value, _desc in TELEMETRY_SETTINGS:
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


def strip_services(adb: ADBClient, dry_run: bool = True) -> list[ActionResult]:
    results: list[ActionResult] = []
    try:
        installed = set(adb.pm_list_packages())
    except ADBError as exc:
        for svc in TELEMETRY_SERVICES:
            results.append(ActionResult(svc, False, "error", str(exc)))
        return results

    for svc in TELEMETRY_SERVICES:
        if svc not in installed:
            results.append(ActionResult(svc, False, "skipped", "not installed"))
            continue
        if dry_run:
            results.append(ActionResult(svc, True, "dry_run"))
            continue
        try:
            ok = adb.pm_disable(svc)
            results.append(
                ActionResult(svc, ok, "disabled" if ok else "error",
                             "" if ok else "pm_disable returned False")
            )
        except ADBError as exc:
            results.append(ActionResult(svc, False, "error", str(exc)))
    return results


def read_current_settings(adb: ADBClient) -> dict[str, str]:
    out: dict[str, str] = {}
    for namespace, key, _value, _desc in TELEMETRY_SETTINGS:
        label = f"{namespace}/{key}"
        try:
            out[label] = adb.settings_get(namespace, key)
        except ADBError:
            out[label] = ""
    return out
