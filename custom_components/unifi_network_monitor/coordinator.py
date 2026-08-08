"""DataUpdateCoordinator for UniFi Network Monitor."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from fnmatch import fnmatchcase
from typing import Any, Literal

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .alerts import alert_title, build_alert_attrs, build_event_payload
from .api import UnifiAuthError, UnifiConnectionError, UnifiNetworkAPI
from .const import (
    CONF_ENABLE_LOGS_ALERTS,
    CONF_ENABLE_SECURITY_MONITORING,
    CONF_ENABLE_SPEEDTEST,
    CONF_ENABLE_WAN_USAGE,
    CONF_ROGUE_APPLY_AP_IGNORE,
    CONF_ROGUE_APPLY_SSID_IGNORE,
    CONF_ROGUE_HISTORY_TTL_DAYS,
    CONF_ROGUE_IGNORE_APS,
    CONF_ROGUE_IGNORE_SSIDS,
    CONF_ROGUE_PERIOD,
    CONF_ROGUE_SHOW_5GHZ,
    CONF_ROGUE_SHOW_24GHZ,
    CONF_SCAN_INTERVAL,
    CONF_STOP_POLLING,
    DEFAULT_ENABLE_LOGS_ALERTS,
    DEFAULT_ENABLE_SECURITY_MONITORING,
    DEFAULT_ENABLE_SPEEDTEST,
    DEFAULT_ENABLE_WAN_USAGE,
    DEFAULT_ROGUE_APPLY_AP_IGNORE,
    DEFAULT_ROGUE_APPLY_SSID_IGNORE,
    DEFAULT_ROGUE_HISTORY_TTL_DAYS,
    DEFAULT_ROGUE_IGNORE_APS,
    DEFAULT_ROGUE_IGNORE_SSIDS,
    DEFAULT_ROGUE_PERIOD,
    DEFAULT_ROGUE_SHOW_5GHZ,
    DEFAULT_ROGUE_SHOW_24GHZ,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EP_BACKUPS,
    EP_DAILY,
    EP_FIREWALL,
    EP_GUESTS,
    EP_MONTHLY,
    EP_NETWORKCONF,
    EP_ROGUE,
    EP_ROGUE_RAW,
    EP_SETTINGS,
    EP_SPEEDTEST,
    EP_SYSINFO,
    EP_SYSLOG,
    EP_VPN_SERVERS,
    EP_VPN_TUNNELS,
    EP_WAN_IF,
    EP_WLAN,
    EVENT_NEW_ALERT,
    EVENT_NEW_ROGUE_AP,
    FETCH_STRIKE_LIMIT,
    GATEWAY_MODELS,
    HEALTH_DRIFT_STRIKE_LIMIT,
    PROJECTION_CONFIDENCE_LOW,
    PROJECTION_CONFIDENCE_MEDIUM,
    PROJECTION_CREDIBILITY_DAYS,
    ROGUE_ESSID_PLACEHOLDER,
    ROGUE_HIDDEN_PREFIX,
    ROGUE_HIDDEN_SSID,
    ROGUE_HISTORY_MAX,
    ROGUE_HISTORY_SAVE_DELAY,
    ROGUE_HISTORY_STORAGE_VERSION,
    ROGUE_PERIOD_HOURS,
    ROGUE_RAW_WINDOW_HOURS,
    USAGE_WATERMARK_SAVE_DELAY,
    USAGE_WATERMARK_STORAGE_VERSION,
    repair_issue_id,
    rogue_history_storage_key,
    usage_watermark_storage_key,
)
from .helpers import calendar_cycle_bounds, project_cycle_usage

_LOGGER = logging.getLogger(__name__)

#: How a device write ended. ``"unverified"`` is deliberately **not**
#: ``"failed"`` — it means the read-back could not be taken, so the write may
#: well have landed (dev_standards.md §22).
WriteOutcome = Literal["confirmed", "unverified", "failed"]


def disabled_endpoints(options: Mapping[str, Any]) -> frozenset[str]:
    """Return endpoints whose feature toggle is off.

    Used by the platforms to skip creating those entities, and mirrors the
    fetch-skip in ``_async_update_data`` so a disabled feature costs no polls
    and shows no entities.
    """
    disabled: set[str] = set()
    if not options.get(CONF_ENABLE_SPEEDTEST, DEFAULT_ENABLE_SPEEDTEST):
        disabled.add(EP_SPEEDTEST)
    if not options.get(CONF_ENABLE_WAN_USAGE, DEFAULT_ENABLE_WAN_USAGE):
        disabled.update({EP_DAILY, EP_MONTHLY})
    if not options.get(
        CONF_ENABLE_SECURITY_MONITORING, DEFAULT_ENABLE_SECURITY_MONITORING
    ):
        disabled.update(
            {
                EP_ROGUE,
                EP_ROGUE_RAW,
                EP_VPN_SERVERS,
                EP_VPN_TUNNELS,
                EP_FIREWALL,
                EP_SETTINGS,
            }
        )
    if not options.get(CONF_ENABLE_LOGS_ALERTS, DEFAULT_ENABLE_LOGS_ALERTS):
        disabled.add(EP_SYSLOG)
    return frozenset(disabled)


# Self-diagnosis maps. A stale endpoint (not user-disabled) is reported on the
# Integration Health sensor under a friendly capability name.
_ENDPOINT_CAPABILITY: dict[str, str] = {
    EP_ROGUE: "Security / Rogue APs",
    EP_ROGUE_RAW: "Security / Rogue APs",
    EP_SYSLOG: "Alerts",
    EP_SPEEDTEST: "Speedtest",
    EP_DAILY: "WAN Usage",
    EP_MONTHLY: "WAN Usage",
    EP_VPN_SERVERS: "Security (VPN / Firewall)",
    EP_VPN_TUNNELS: "Security (VPN / Firewall)",
    EP_FIREWALL: "Security (VPN / Firewall)",
    EP_SETTINGS: "Security (Threat Management)",
    EP_WAN_IF: "WAN interface names",
}

# v3-only endpoints — unreachable under username/password auth (expected, not a
# fault), so they are excluded from health when no API key is configured.
_V3_ENDPOINTS: frozenset[str] = frozenset(
    {EP_WAN_IF, EP_VPN_SERVERS, EP_VPN_TUNNELS, EP_FIREWALL}
)

# Friendly names for the schema-drift checks.
_DRIFT_CAPABILITY: dict[str, str] = {
    "gateway": "Gateway telemetry",
    "rogue": "Rogue APs",
    "alerts": "Alerts",
}


def _split_patterns(raw: str) -> list[str]:
    """Split a comma-separated ignore-list option into stripped, non-empty patterns."""
    return [p.strip() for p in (raw or "").split(",") if p.strip()]


def _ap_matches(reporter: dict[str, str], patterns: list[str]) -> bool:
    """Check if a reporting AP's MAC or friendly name matches any wildcard pattern."""
    mac = reporter.get("mac") or ""
    name = reporter.get("name") or ""
    return any(fnmatchcase(mac, pat) or fnmatchcase(name, pat) for pat in patterns)


_ROGUE_BAND_LABELS = {"ng": "2.4 GHz", "na": "5 GHz"}


def rogue_band_label(band: str | None) -> str | None:
    """Map the UniFi band code (ng/na) to a readable label for events/actions."""
    if band is None:
        return None
    return _ROGUE_BAND_LABELS.get(band, band)


def build_ap_name_map(devices_raw: list[dict[str, Any]] | None) -> dict[str, str]:
    """Map lowercased AP MAC -> friendly name (falls back to model, then MAC)."""
    ap_name_map: dict[str, str] = {}
    for device in devices_raw or []:
        mac = device.get("mac")
        if mac:
            ap_name_map[mac.lower()] = device.get("name") or device.get("model") or mac
    return ap_name_map


def normalize_essid(raw: Any) -> tuple[str, bool, bool]:
    """Return ``(display, anomaly, hidden)`` for a raw SSID.

    - Empty or whitespace-only essid (the controller's cloaked-network case)
      returns ``hidden=True``; ``display`` is the ``<Hidden>`` fallback, which the
      caller replaces with a BSSID-derived ``Hidden-<suffix>`` name.
    - Otherwise, any control / zero-width / non-printable characters are
      replaced with a visible placeholder so a spoofed name renders safely and
      the tampering stays visible (``hidden=False``).

    ``anomaly`` is ``True`` for either case, so an automation can trigger on a
    cloaked *or* obfuscated SSID via a single ``ssid_anomaly`` field.
    """
    text = raw if isinstance(raw, str) else ("" if raw is None else str(raw))
    if not text.strip():
        return ROGUE_HIDDEN_SSID, True, True

    # str.isprintable() keeps normal spaces but rejects control, tab/newline,
    # zero-width, and RTL-override characters — exactly the deceptive set.
    cleaned_chars: list[str] = []
    tampered = False
    for ch in text:
        if ch.isprintable():
            cleaned_chars.append(ch)
        else:
            cleaned_chars.append(ROGUE_ESSID_PLACEHOLDER)
            tampered = True
    return "".join(cleaned_chars), tampered, False


def hidden_label(bssid: str, *, extended: bool = False) -> str:
    """Return the BSSID-derived pseudo-name for a cloaked SSID.

    ``Hidden-`` + the last 4 hex of the BSSID (uppercase), or the last 6 when
    ``extended`` (used to disambiguate a last-4 collision within one response).
    Falls back to ``<Hidden>`` when the BSSID has no usable hex.
    """
    hexonly = "".join(c for c in bssid if c in "0123456789abcdefABCDEF").upper()
    if not hexonly:
        return ROGUE_HIDDEN_SSID
    return (
        ROGUE_HIDDEN_PREFIX + hexonly[-6:]
        if extended
        else (ROGUE_HIDDEN_PREFIX + hexonly[-4:])
    )


def parse_rogue_aps(
    rogueaps_raw: list[dict[str, Any]] | None,
    ap_name_map: dict[str, str],
    now_ts: int,
    *,
    show_24ghz: bool = True,
    show_5ghz: bool = True,
    ignore_ssids: list[str] | None = None,
    apply_ssid_ignore: bool = False,
    ignore_aps: list[str] | None = None,
    apply_ap_ignore: bool = False,
) -> list[dict[str, Any]]:
    """Band-filter, optionally SSID/AP-ignore, and BSSID-cluster raw rogue APs.

    Shared by the coordinator (curated sensor view, Security options applied) and
    the ``get_rogue_aps`` action (self-contained, ignore-lists off). Each item
    carries ``last_seen`` (epoch seconds) plus a derived human-readable ``age``.
    """
    ignore_ssids = ignore_ssids or []
    ignore_aps = ignore_aps or []

    # Band filter + SSID ignore, then group reporters by BSSID.
    clusters: dict[str, dict[str, Any]] = {}
    for r in rogueaps_raw or []:
        band = r.get("band")  # "ng"=2.4GHz, "na"=5GHz
        if band == "ng" and not show_24ghz:
            continue
        if band == "na" and not show_5ghz:
            continue
        essid, ssid_anomaly, hidden = normalize_essid(r.get("essid"))
        bssid = r.get("bssid", "")
        # A cloaked SSID is named from its BSSID (Hidden-A2D3) so distinct hidden
        # APs stay distinguishable; a collision pass below extends colliding ones.
        if hidden:
            essid = hidden_label(bssid)
        # Ignore-globs match the display SSID, so a rule like ``Hidden-*`` or
        # ``*·*`` can target cloaked / obfuscated names.
        if apply_ssid_ignore and any(fnmatchcase(essid, pat) for pat in ignore_ssids):
            continue
        ap_mac = r.get("ap_mac", "")
        detected_by = ap_name_map.get(ap_mac.lower()) or ap_mac
        signal = _safe_int(r.get("signal"))
        last_seen = _safe_int(r.get("last_seen"))
        channel_width = _safe_int(r.get("bw"))
        cl = clusters.setdefault(
            bssid,
            {
                "essid": essid,
                "ssid_anomaly": ssid_anomaly,
                "hidden": hidden,
                "bssid": bssid,
                "band": band,
                "channel": _safe_int(r.get("channel")),
                "channel_width": channel_width,
                "signal": signal,
                "security": r.get("security") or "",
                "oui": r.get("oui", ""),
                "wired_rogue": bool(r.get("is_rogue")),
                "is_adhoc": bool(r.get("is_adhoc")),
                "reporters": [],
                "last_seen": last_seen,
            },
        )
        cl["reporters"].append({"mac": ap_mac, "name": detected_by})
        if signal is not None and (cl["signal"] is None or signal > cl["signal"]):
            cl["signal"] = signal
        if last_seen is not None and (
            cl["last_seen"] is None or last_seen > cl["last_seen"]
        ):
            cl["last_seen"] = last_seen
        # A BSSID is a wired rogue / ad-hoc if ANY reporter flags it as such;
        # take the widest observed channel width and first non-empty security.
        if r.get("is_rogue"):
            cl["wired_rogue"] = True
        if r.get("is_adhoc"):
            cl["is_adhoc"] = True
        if channel_width is not None and (
            cl["channel_width"] is None or channel_width > cl["channel_width"]
        ):
            cl["channel_width"] = channel_width
        if not cl["security"] and r.get("security"):
            cl["security"] = r["security"]

    # Disambiguate hidden labels that collide on the last-4 suffix: if two or
    # more distinct BSSIDs map to the same Hidden-XXXX, extend all of them to
    # the last-6 form. The stable identity is the BSSID; the label is cosmetic.
    hidden_by_label: dict[str, list[dict[str, Any]]] = {}
    for cl in clusters.values():
        if cl.get("hidden") and cl["bssid"]:
            hidden_by_label.setdefault(cl["essid"], []).append(cl)
    for group in hidden_by_label.values():
        if len({cl["bssid"] for cl in group}) > 1:
            for cl in group:
                cl["essid"] = hidden_label(cl["bssid"], extended=True)

    rogue_aps_list: list[dict[str, Any]] = []
    for cl in clusters.values():
        # AP ignore: drop only if EVERY reporting AP matches the list.
        if (
            apply_ap_ignore
            and ignore_aps
            and cl["reporters"]
            and all(_ap_matches(rep, ignore_aps) for rep in cl["reporters"])
        ):
            continue
        last_seen = cl.get("last_seen")
        if last_seen is not None:
            true_age = max(0, now_ts - last_seen)
            age_str = (
                f"{true_age // 60}m" if true_age < 3600 else f"{true_age // 3600}h"
            )
        else:
            age_str = None
        names = list(dict.fromkeys(rep["name"] for rep in cl["reporters"]))
        rogue_aps_list.append(
            {
                "essid": cl["essid"],
                "ssid_anomaly": cl["ssid_anomaly"],
                "bssid": cl["bssid"],
                "band": cl["band"],
                "channel": cl["channel"],
                "channel_width": cl["channel_width"],
                "signal": cl["signal"],
                "security": cl["security"],
                "oui": cl["oui"],
                "wired_rogue": cl["wired_rogue"],
                "is_adhoc": cl["is_adhoc"],
                "last_seen": last_seen,
                "age": age_str,
                "detected_by": ", ".join(names),
            }
        )
    return rogue_aps_list


def build_rogue_event_payload(entry_id: str, ap: dict[str, Any]) -> dict[str, Any]:
    """Build the ``unifi_network_monitor_new_rogue_ap`` bus-event payload."""
    last_seen = ap.get("last_seen")
    return {
        "entry_id": entry_id,
        "essid": ap.get("essid"),
        "ssid_anomaly": ap.get("ssid_anomaly"),
        "bssid": ap.get("bssid"),
        "band": rogue_band_label(ap.get("band")),
        "channel": ap.get("channel"),
        "channel_width": ap.get("channel_width"),
        "signal": ap.get("signal"),
        "security": ap.get("security"),
        "oui": ap.get("oui"),
        "wired_rogue": ap.get("wired_rogue"),
        "is_adhoc": ap.get("is_adhoc"),
        "detected_by": ap.get("detected_by"),
        "timestamp": (
            datetime.fromtimestamp(last_seen, tz=UTC).isoformat() if last_seen else None
        ),
    }


def _safe_float(val: Any, default: float | None = None) -> float | None:
    """Safely coerce to float, curtailed to 3 decimals.

    Controller telemetry (e.g. WAN availability) can arrive with a dozen
    decimals; capping to 3 keeps stored/history values clean. Per-sensor
    ``suggested_display_precision`` controls how many are *shown*.
    """
    if val in (None, ""):
        return default
    try:
        return round(float(val), 3)
    except (TypeError, ValueError):
        return default


def _safe_int(val: Any, default: int | None = None) -> int | None:
    """Safely coerce to int."""
    if val in (None, ""):
        return default
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return default


def _extract_wan_networkconf(
    raw: list[dict[str, Any]] | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Pick the WAN1 and WAN2 network-configuration objects out of ``networkconf``.

    One place rather than two: the poll parses these for the weight/mode sensors
    and the write path re-reads them immediately before composing its PUT, and
    the two must agree on what counts as a WAN object.
    """
    wan1: dict[str, Any] | None = None
    wan2: dict[str, Any] | None = None
    for net in raw or []:
        if net.get("purpose") != "wan":
            continue
        group = net.get("wan_networkgroup")
        if group == "WAN":
            wan1 = net
        elif group == "WAN2":
            wan2 = net
    return wan1, wan2


def _sum_optional(rx: float | None, tx: float | None) -> float | None:
    """Total two byte counters, or None when neither side reported.

    A missing direction counts as zero rather than voiding the total — the same
    rule the wan*_month_total sensors already use, so the projection cannot
    disagree with the figure it projects from.
    """
    if rx is None and tx is None:
        return None
    return (rx or 0) + (tx or 0)


def build_usage_projection(
    used: float | None, now: datetime
) -> tuple[int | None, dict[str, Any]]:
    """Project this calendar month's WAN usage to its end, with its context.

    Returns ``(projected_bytes, attributes)``. ``used`` of ``None`` — no monthly
    counter yet — yields ``(None, {})`` rather than an invented zero; that is the
    one case where there is genuinely nothing to forecast from.

    Everything else produces a figure, **including the first hour of a new
    month**. A projection on day one is weak, but an ``unknown`` that clears
    itself a day later reads as a broken sensor, and users treat it as one. The
    caveat is published as ``confidence`` alongside the number instead, which is
    the same call ZTE made and for the same reason.
    """
    if used is None:
        return None, {}

    start, _end, length = calendar_cycle_bounds(now)
    elapsed = (now - start).total_seconds() / 86400.0
    # No stored previous-cycle total yet, so the blend has no prior to work
    # from; the one-day denominator floor inside project_cycle_usage carries the
    # early-cycle bound on its own.
    prior_rate: float | None = None

    projected = project_cycle_usage(
        used=used,
        elapsed_days=elapsed,
        cycle_length_days=length,
        prior_rate=prior_rate,
        credibility_days=PROJECTION_CREDIBILITY_DAYS,
    )
    weight = elapsed / (elapsed + PROJECTION_CREDIBILITY_DAYS)
    if weight < PROJECTION_CONFIDENCE_LOW:
        confidence = "low"
    elif weight < PROJECTION_CONFIDENCE_MEDIUM:
        confidence = "medium"
    else:
        confidence = "high"

    return int(projected), {
        "confidence": confidence,
        "basis": "run_rate_only" if prior_rate is None else "blended",
        "cycle_day": f"{int(elapsed) + 1} of {length}",
        "cycle_start": start.date().isoformat(),
    }


def _derive_boot_time(uptime_secs: int | None, reference: datetime) -> datetime | None:
    """Derive a boot timestamp from uptime seconds, anchored to reference time."""
    if uptime_secs is None or uptime_secs < 0:
        return None
    return (reference - timedelta(seconds=uptime_secs)).replace(microsecond=0)


def _parse_gateway(
    device: dict[str, Any],
    update_time: datetime,
    coordinator: UnifiNetworkDataUpdateCoordinator | None = None,
) -> dict[str, Any]:
    """Extract gateway-specific data from a stat/device entry."""
    system_stats = device.get("system-stats") or {}
    cpu = _safe_float(system_stats.get("cpu"))
    ram = _safe_float(system_stats.get("mem"))
    uptime_secs = _safe_int(device.get("uptime"))

    # Temperatures
    cpu_temp: float | None = None
    board_temp: float | None = None
    for t in device.get("temperatures") or []:
        if t.get("type") == "cpu":
            cpu_temp = _safe_float(t.get("value"))
        elif t.get("type") == "board":
            board_temp = _safe_float(t.get("value"))

    # Storage (/persistent mount point)
    storage_used: int | None = None
    storage_size: int | None = None
    storage_used_pct: float | None = None
    for s in device.get("storage") or []:
        if s.get("mount_point") == "/persistent":
            storage_used = _safe_int(s.get("used"))
            storage_size = _safe_int(s.get("size"))
            if storage_used is not None and storage_size and storage_size > 0:
                storage_used_pct = round((storage_used / storage_size) * 100.0, 1)

    # Uplink
    uplink = device.get("uplink") or {}
    uplink_ip: str | None = None
    internet: bool = False
    speedtest_status: bool | None = None

    if uplink:
        internet = bool(uplink.get("up"))
        speedtest_status = uplink.get("speedtest_status") == "Success"
        if uplink.get("comment") == "WAN":
            uplink_ip = uplink.get("ip")

    # WAN1 / WAN2 real-time interface telemetry
    wan1_data = device.get("wan1") or {}
    wan2_data = device.get("wan2") or {}

    geo_info = device.get("geo_info") or {}
    active_geo_info = device.get("active_geo_info") or {}

    wan1_geo = geo_info.get("WAN") or {}
    wan1_active_geo = active_geo_info.get("WAN") or {}
    wan1_public_ip = wan1_geo.get("address") or wan1_active_geo.get("address")

    wan2_geo = geo_info.get("WAN2") or {}
    wan2_active_geo = active_geo_info.get("WAN2") or {}
    wan2_public_ip = wan2_geo.get("address") or wan2_active_geo.get("address")

    return {
        "mac": device.get("mac", "").lower(),
        "name": device.get("name", "UDM Pro"),
        "model": device.get("model", "UDM Pro"),
        "cpu": cpu,
        "ram": ram,
        "uptime_secs": uptime_secs,
        "boot_time": (
            coordinator.get_stable_boot_time("gateway", uptime_secs, update_time)
            if coordinator
            else _derive_boot_time(uptime_secs, update_time)
        ),
        "internet": internet,
        "speedtest_status": speedtest_status,
        "storage_used": storage_used,
        "storage_size": storage_size,
        "storage_used_pct": storage_used_pct,
        "cpu_temp": cpu_temp,
        "board_temp": board_temp,
        "wan1_local_ip": wan1_data.get("ip") or uplink_ip,
        "wan1_public_ip": wan1_public_ip,
        "wan2_local_ip": wan2_data.get("ip"),
        "wan2_public_ip": wan2_public_ip,
        "update_available": bool(device.get("upgradable")),
        # WAN1
        "wan1_ifname": wan1_data.get("ifname") or "eth8",
        "wan1_active": bool(wan1_data.get("is_uplink")),
        "wan1_up": bool(wan1_data.get("up")),
        "wan1_latency": _safe_int(wan1_data.get("latency")),
        "wan1_availability": _safe_float(wan1_data.get("availability")),
        "wan1_sfp_found": (
            bool(wan1_data.get("sfp_found")) if "sfp_found" in wan1_data else None
        ),
        "wan1_sfp_vendor": wan1_data.get("sfp_vendor"),
        "wan1_sfp_part": wan1_data.get("sfp_part"),
        "wan1_sfp_serial": wan1_data.get("sfp_serial"),
        # WAN2
        "wan2_ifname": wan2_data.get("ifname") or "eth9",
        "wan2_active": bool(wan2_data.get("is_uplink")),
        "wan2_up": bool(wan2_data.get("up")),
        "wan2_latency": _safe_int(wan2_data.get("latency")),
        "wan2_availability": _safe_float(wan2_data.get("availability")),
        "wan2_sfp_found": (
            bool(wan2_data.get("sfp_found")) if "sfp_found" in wan2_data else None
        ),
        "wan2_sfp_vendor": wan2_data.get("sfp_vendor"),
        "wan2_sfp_part": wan2_data.get("sfp_part"),
        "wan2_sfp_serial": wan2_data.get("sfp_serial"),
    }


def _parse_ap(
    device: dict[str, Any],
    update_time: datetime,
    coordinator: UnifiNetworkDataUpdateCoordinator | None = None,
) -> dict[str, Any]:
    """Extract AP-specific data from a stat/device entry."""
    system_stats = device.get("system-stats") or {}
    uptime_secs = _safe_int(device.get("uptime"))
    radio_stats = device.get("radio_table_stats") or []
    wifi0 = radio_stats[0] if len(radio_stats) > 0 else {}
    wifi1 = radio_stats[1] if len(radio_stats) > 1 else {}

    mac = device.get("mac", "").lower()

    return {
        "mac": mac,
        "name": device.get("name", "UniFi AP"),
        "model": device.get("model", ""),
        "type": "ap",
        "cpu": _safe_float(system_stats.get("cpu")),
        "ram": _safe_float(system_stats.get("mem")),
        "uptime_secs": uptime_secs,
        "boot_time": (
            coordinator.get_stable_boot_time(mac, uptime_secs, update_time)
            if coordinator
            else _derive_boot_time(uptime_secs, update_time)
        ),
        "update_available": bool(device.get("upgradable")),
        "clients": _safe_int(device.get("user-wlan-num_sta"), 0),
        "guests": _safe_int(device.get("guest-wlan-num_sta"), 0),
        "clients_wifi0": _safe_int(wifi0.get("user-num_sta"), 0),
        "clients_wifi1": _safe_int(wifi1.get("user-num_sta"), 0),
        "score": _safe_int(device.get("satisfaction")),
        "score_wifi0": _safe_int(wifi0.get("satisfaction")),
        "score_wifi1": _safe_int(wifi1.get("satisfaction")),
    }


def _parse_switch(
    device: dict[str, Any],
    update_time: datetime,
    coordinator: UnifiNetworkDataUpdateCoordinator | None = None,
) -> dict[str, Any]:
    """Extract switch-specific data from a stat/device entry."""
    system_stats = device.get("system-stats") or {}
    uptime_secs = _safe_int(device.get("uptime"))

    mac = device.get("mac", "").lower()

    return {
        "mac": mac,
        "name": device.get("name", "UniFi Switch"),
        "model": device.get("model", ""),
        "type": "switch",
        "cpu": _safe_float(system_stats.get("cpu")),
        "ram": _safe_float(system_stats.get("mem")),
        "uptime_secs": uptime_secs,
        "boot_time": (
            coordinator.get_stable_boot_time(mac, uptime_secs, update_time)
            if coordinator
            else _derive_boot_time(uptime_secs, update_time)
        ),
        "update_available": bool(device.get("upgradable")),
        "ports_used": _safe_int(device.get("num_sta"), 0),
        "ports_user": _safe_int(device.get("user-num_sta"), 0),
        "ports_guest": _safe_int(device.get("guest-num_sta"), 0),
    }


def _parse_health(
    health_list: list[dict[str, Any]],
    update_time: datetime,
    coordinator: UnifiNetworkDataUpdateCoordinator | None = None,
) -> dict[str, Any]:
    """Build the health data dict from the stat/health response."""
    health: dict[str, Any] = {}

    for h in health_list:
        subsystem = h.get("subsystem", "")

        if subsystem == "wan":
            health["wan_status"] = h.get("status", "unknown")
            # None (→ HA "unknown") when absent, rather than a blank "" state.
            health["wan_isp_name"] = h.get("isp_name") or None
            health["wan_isp_org"] = h.get("isp_organization") or None
            health["wan_gw_version"] = h.get("gw_version", "")
            health["wan_num_sta"] = _safe_int(h.get("num_sta"), 0)
            gw_stats = h.get("gw_system-stats") or {}
            health["wan_cpu"] = _safe_float(gw_stats.get("cpu"))
            health["wan_mem"] = _safe_float(gw_stats.get("mem"))
            health["wan_uptime"] = _safe_int(gw_stats.get("uptime"), 0)

            uptime_stats = h.get("uptime_stats") or {}

            wan1 = uptime_stats.get("WAN") or {}
            if wan1:
                wan1_uptime = _safe_int(wan1.get("uptime"), 0)
                health["wan1_availability"] = _safe_float(
                    wan1.get("availability"), 100.0
                )
                health["wan1_latency_avg"] = _safe_int(wan1.get("latency_average"), 0)
                health["wan1_time_period"] = _safe_int(wan1.get("time_period"), 0)
                health["wan1_uptime"] = wan1_uptime
                health["wan1_boot_time"] = (
                    coordinator.get_stable_boot_time("wan1", wan1_uptime, update_time)
                    if coordinator
                    else _derive_boot_time(wan1_uptime, update_time)
                )

            wan2 = uptime_stats.get("WAN2") or {}
            if wan2:
                wan2_uptime = _safe_int(wan2.get("uptime"), 0)
                health["wan2_availability"] = _safe_float(
                    wan2.get("availability"), 100.0
                )
                health["wan2_latency_avg"] = _safe_int(wan2.get("latency_average"), 0)
                health["wan2_time_period"] = _safe_int(wan2.get("time_period"), 0)
                health["wan2_uptime"] = wan2_uptime
                health["wan2_boot_time"] = (
                    coordinator.get_stable_boot_time("wan2", wan2_uptime, update_time)
                    if coordinator
                    else _derive_boot_time(wan2_uptime, update_time)
                )

        elif subsystem == "www":
            health["www_status"] = h.get("status", "unknown")
            health["www_latency"] = _safe_int(h.get("latency"), 0)
            www_uptime = _safe_int(h.get("uptime"), 0)
            health["www_uptime"] = www_uptime
            health["www_boot_time"] = (
                coordinator.get_stable_boot_time("www", www_uptime, update_time)
                if coordinator
                else _derive_boot_time(www_uptime, update_time)
            )
            health["www_drops"] = _safe_int(h.get("drops"), 0)
            health["www_speedtest_status"] = h.get("speedtest_status") or None

        elif subsystem == "wlan":
            health["wlan_status"] = h.get("status", "unknown")
            health["wlan_num_user"] = _safe_int(h.get("num_user"), 0)
            health["wlan_num_guest"] = _safe_int(h.get("num_guest"), 0)
            health["wlan_num_iot"] = _safe_int(h.get("num_iot"), 0)
            health["wlan_num_ap"] = _safe_int(h.get("num_ap"), 0)

        elif subsystem == "lan":
            health["lan_status"] = h.get("status", "unknown")
            health["lan_num_user"] = _safe_int(h.get("num_user"), 0)
            health["lan_num_iot"] = _safe_int(h.get("num_iot"), 0)
            health["lan_num_sw"] = _safe_int(h.get("num_sw"), 0)
            health["lan_num_adopted"] = _safe_int(h.get("num_adopted"), 0)

        elif subsystem == "vpn":
            health["vpn_status"] = h.get("status", "unknown")

    return health


class UnifiNetworkDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that fetches and structures all UniFi Network data."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: UnifiNetworkAPI,
    ) -> None:
        """Initialize the coordinator."""
        self.api = api
        self.entry = entry
        self.consecutive_failures = 0
        self.last_update_success_time: datetime | None = None
        self._was_available = True
        # Integration Health lives OUTSIDE ``self.data`` on purpose. ``data`` is
        # the fetched payload — it is None before the first success and frozen at
        # the last good values during an outage, so a health verdict stored in it
        # cannot report the outage that stopped it being updated. Keeping the
        # snapshot here lets the health sensor stay available and truthful when
        # every other entity has correctly gone unavailable (§19).
        self.health_snapshot: dict[str, Any] = {
            "problem": False,
            "severity": None,
            "issues": [],
            "degraded_capabilities": [],
            "drift": [],
            "auth_mode": None,
            "v3_available": False,
            "last_good_update": None,
        }
        # Snapshot of the options that require a full reload when changed (set in
        # async_setup_entry). Live-tunable options (scan interval, proximity
        # threshold, pause) are excluded so their controls don't force a reload.
        self.reload_signature: dict[str, Any] = {}

        # Per-endpoint resilience: each optional endpoint holds its last-good
        # payload for up to FETCH_STRIKE_LIMIT consecutive failures, then is
        # flagged stale so its entities report "unavailable" while the rest of
        # the update continues. See endpoint_available().
        self._endpoint_state: dict[str, dict[str, Any]] = {}
        self._stale_endpoints: set[str] = set()

        # Self-diagnosis: per-source consecutive schema-drift counters. A drift
        # signal must persist HEALTH_DRIFT_STRIKE_LIMIT cycles before it flags.
        self._drift_strikes: dict[str, int] = {}

        # Explicit user actions (Refresh Now, speedtest run, weight change,
        # scan-interval change) set this so the next update fetches even when
        # polling is paused. Scheduled polls still respect the pause.
        self._force_refresh_once = False
        self._pending_refresh_unsub: Callable[[], None] | None = None

        # New-alert event dedup. Seen ids are refreshed to the current log window
        # each poll (dismissal changes an alert's status, not its id, so a fired
        # alert won't re-fire; memory stays bounded to the fetched window). The
        # first fetch after startup — or after Alerts is re-enabled — records the
        # backlog silently so a restart/re-enable doesn't spam the bus.
        self._seen_alert_ids: set[str] = set()
        self._alert_baseline_done = False

        # New-rogue-AP event dedup + persistent appearance history, both keyed on
        # BSSID. ``rogue_history`` maps BSSID -> {first_seen, last_seen,
        # appearances, last_label}, persisted across restarts so the event fires
        # only for genuinely-new BSSIDs (not the whole set after a reload).
        self._rogue_baseline_done = False
        self.rogue_history: dict[str, dict[str, Any]] = {}
        self._rogue_history_store: Store[dict[str, dict[str, Any]]] = Store(
            hass,
            ROGUE_HISTORY_STORAGE_VERSION,
            rogue_history_storage_key(entry.entry_id),
        )

        # Per-counter usage high-water mark: {counter_key: {"period": int,
        # "value": int}}. See _clamp_usage. Persisted across restarts.
        self.usage_watermark: dict[str, dict[str, int]] = {}
        self._usage_store: Store[dict[str, dict[str, int]]] = Store(
            hass,
            USAGE_WATERMARK_STORAGE_VERSION,
            usage_watermark_storage_key(entry.entry_id),
        )

        # "Flat Identity" — loaded from entry.data, stable without a network call
        # Canonicalised once here (lowercase, colon-separated) so every consumer
        # — root registration, the device_info helpers, unique_ids — gets a MAC
        # that matches what HA Core's UniFi integration registers. Without this,
        # an upper-case or colon-free MAC from the controller silently breaks the
        # device-card merge (dev_standards §3).
        self.gateway_mac: str = format_mac(entry.data.get("mac", ""))
        self.gateway_model: str = entry.data.get("model", "UDM Pro")
        self.sw_version: str | None = entry.data.get("sw_version")
        self.site_uuid: str | None = None

        # Full networkconf objects for WAN/WAN2 — needed for PUT writes
        self._networkconf_wan: dict[str, Any] | None = None
        self._networkconf_wan2: dict[str, Any] | None = None

        # Load persisted boot times for reboot-detection latch
        self._boot_times: dict[str, dict[str, Any]] = {}
        boot_times_raw = entry.data.get("boot_times")
        if isinstance(boot_times_raw, dict):
            self._boot_times = {
                k: dict(v) for k, v in boot_times_raw.items() if isinstance(v, dict)
            }

        scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{entry.title} Data",
            update_interval=timedelta(seconds=scan_interval),
        )

    def get_stable_boot_time(
        self, key: str, uptime_secs: int | None, reference: datetime
    ) -> datetime | None:
        """Derive and stabilize a boot timestamp using a reboot-detection latch."""
        if uptime_secs is None or uptime_secs < 0:
            # Bad-reading guard: keep the existing boot time if there is one
            if key in self._boot_times:
                boot_time_str = self._boot_times[key].get("boot_time")
                if boot_time_str:
                    with contextlib.suppress(Exception):
                        return dt_util.parse_datetime(boot_time_str)
            return None

        # Retrieve cached boot time and last uptime
        cached = self._boot_times.get(key) or {}
        cached_boot_time: datetime | None = None
        cached_boot_time_str = cached.get("boot_time")
        if cached_boot_time_str:
            with contextlib.suppress(Exception):
                cached_boot_time = dt_util.parse_datetime(cached_boot_time_str)
        cached_last_uptime = cached.get("last_uptime")

        # Check if we need to (re-)latch
        is_reboot = cached_boot_time is None or (
            cached_last_uptime is not None and uptime_secs < cached_last_uptime - 30
        )

        if is_reboot:
            calc_time = reference - timedelta(seconds=uptime_secs)
            stable_boot = calc_time.replace(microsecond=0)
            self._boot_times[key] = {
                "boot_time": stable_boot.isoformat(),
                "last_uptime": uptime_secs,
            }
            # Copy and persist
            new_data = {
                **self.entry.data,
                "boot_times": {k: dict(v) for k, v in self._boot_times.items()},
            }
            self.hass.config_entries.async_update_entry(self.entry, data=new_data)
            return stable_boot

        # Update last_uptime in-memory only (avoid config entry write on every poll)
        if key in self._boot_times:
            self._boot_times[key]["last_uptime"] = uptime_secs
        else:  # pragma: no cover - defensive; unreachable while cached_boot_time is set
            self._boot_times[key] = {
                "boot_time": (
                    cached_boot_time.isoformat()
                    if cached_boot_time
                    else reference.isoformat()
                ),
                "last_uptime": uptime_secs,
            }
        return cached_boot_time

    @property
    def wan_weights_writable(self) -> bool:
        """True once both WAN networkconf objects are loaded (weights writable)."""
        return self._networkconf_wan is not None and self._networkconf_wan2 is not None

    async def async_set_wan_weights(self, wan1_weight: int) -> WriteOutcome:
        """Write the WAN1/WAN2 load-balance weights as a pair; always sums to 100.

        Three properties this deliberately holds, each one a defect it replaces:

        - **Composed from a fresh read, never from held state.** ``networkconf``
          is a *degradable* endpoint, so the held object can be minutes old; a
          PUT of the whole object built from it would silently revert every
          other controller-side change made since. The GET happens immediately
          before the PUT and also refreshes the held copies.
        - **The pair is non-interruptible once the first PUT has gone out.** The
          caller is a debounce task that cancels itself on the next slider move,
          and the cancellation lands wherever the task is suspended — which,
          after the debounce sleep, is *between* the two writes. Cancelling
          there used to write WAN1 and not WAN2, leaving a pair that no longer
          summed to 100 with nothing reporting it. ``asyncio.shield`` lets the
          caller be cancelled while the pair still completes.
        - **The write is read back, and the three outcomes stay distinct.**
          Returns ``"confirmed"``, ``"unverified"`` or ``"failed"``.
          **Unverified is not failed** — a read-back that could not be taken
          says nothing about whether the write landed, and reporting it as a
          failure sends the user chasing a change that already applied.
        """
        wan2_weight = 100 - wan1_weight
        wan1_net, wan2_net = _extract_wan_networkconf(await self.api.get_networkconf())
        if wan1_net is None or wan2_net is None:
            raise ValueError("WAN network configuration not yet loaded")
        self._networkconf_wan = wan1_net
        self._networkconf_wan2 = wan2_net
        wan1_id = wan1_net.get("_id")
        wan2_id = wan2_net.get("_id")
        if not wan1_id or not wan2_id:
            raise ValueError("WAN network configuration missing _id")

        await asyncio.shield(
            self._write_wan_pair(
                (wan1_id, wan1_net, wan1_weight), (wan2_id, wan2_net, wan2_weight)
            )
        )

        # Brief pause to let the UDM Pro commit the change before reading back.
        await asyncio.sleep(1.5)
        outcome = await self._confirm_wan_weights(wan1_weight, wan2_weight)
        await self.async_force_refresh()
        return outcome

    async def _write_wan_pair(
        self,
        wan1: tuple[str, dict[str, Any], int],
        wan2: tuple[str, dict[str, Any], int],
    ) -> None:
        """PUT both weights. Shielded by the caller — must not be split."""
        for net_id, net, weight in (wan1, wan2):
            await self.api.update_networkconf(
                net_id, {**net, "wan_load_balance_weight": weight}
            )

    async def _confirm_wan_weights(
        self, wan1_weight: int, wan2_weight: int
    ) -> WriteOutcome:
        """Read the weights back and classify the write.

        ``"unverified"`` covers both a read-back that could not be taken and one
        that came back without the WAN objects — in neither case is there any
        evidence about the write, which is exactly what distinguishes it from
        ``"failed"``.
        """
        try:
            fresh = await self.api.get_networkconf()
        except (UnifiConnectionError, UnifiAuthError) as err:
            _LOGGER.info(
                "%s: WAN weights were sent but could not be read back: %s",
                self.entry.title,
                err,
            )
            return "unverified"
        wan1_net, wan2_net = _extract_wan_networkconf(fresh)
        if wan1_net is None or wan2_net is None:
            _LOGGER.info(
                "%s: WAN weights were sent but the read-back carried no WAN config",
                self.entry.title,
            )
            return "unverified"
        got1 = _safe_int(wan1_net.get("wan_load_balance_weight"))
        got2 = _safe_int(wan2_net.get("wan_load_balance_weight"))
        if got1 == wan1_weight and got2 == wan2_weight:
            return "confirmed"
        _LOGGER.warning(
            "%s: WAN weights did not take — sent %s/%s, controller reports %s/%s",
            self.entry.title,
            wan1_weight,
            wan2_weight,
            got1,
            got2,
        )
        return "failed"

    async def async_force_refresh(self) -> None:
        """Refresh now, bypassing the pause guard (explicit user action).

        Debounced: the fetch may not have run by the time this returns, so the
        outcome is not knowable here. Callers that must report failure want
        ``async_force_refresh_now`` instead.
        """
        self._force_refresh_once = True
        await self.async_request_refresh()

    async def async_force_refresh_now(self) -> None:
        """Refresh immediately, bypassing both the pause guard and the debouncer.

        For a control that has to tell the caller whether it worked. ``async_refresh``
        runs the update inline and records the outcome on ``last_update_success``
        rather than raising, so the caller checks that flag afterwards - which it
        can only do if the fetch has actually happened, hence not the debounced
        path.

        ``_force_refresh_once`` is still consumed on **attempt**, inside
        ``_async_update_data``, not on success. A failed forced refresh therefore
        does not bypass the pause again on the next scheduled poll. That is
        deliberate: the alternative re-arms the bypass until a fetch succeeds,
        which turns a paused integration into a polling one for as long as the
        gateway stays unreachable.
        """
        self._force_refresh_once = True
        await self.async_refresh()

    @callback
    def async_schedule_refresh_in(self, seconds: float) -> None:
        """Schedule a one-shot forced refresh after ``seconds``.

        Used after a manual speedtest so the result shows without waiting for the
        next scheduled poll. Skips scheduling when a normal poll will arrive
        sooner anyway (and polling isn't paused). Reschedules on repeat calls.
        """
        paused = bool(self.entry.options.get(CONF_STOP_POLLING, False))
        interval_s = self.update_interval.total_seconds() if self.update_interval else 0
        if not paused and interval_s <= seconds:
            return  # the regular poll will pick it up soon enough
        self.cancel_scheduled_refresh()

        async def _fire(_now: datetime) -> None:
            self._pending_refresh_unsub = None
            await self.async_force_refresh()

        self._pending_refresh_unsub = async_call_later(self.hass, seconds, _fire)

    @callback
    def cancel_scheduled_refresh(self) -> None:
        """Cancel any pending scheduled refresh (on reschedule or unload)."""
        if self._pending_refresh_unsub is not None:
            self._pending_refresh_unsub()
            self._pending_refresh_unsub = None

    async def async_trigger_speedtest(self, interface_name: str | None = None) -> None:
        """Trigger a manual speedtest on the gateway."""
        await self.api.trigger_speedtest(interface_name)

    @callback
    def _fire_new_alert_events(self, logs: list[dict[str, Any]]) -> None:
        """Fire ``EVENT_NEW_ALERT`` once per newly-seen alert id.

        ``logs`` is newest-first. The first fetch after startup (or after Alerts
        is re-enabled) only records the backlog as a baseline — no events — so a
        restart doesn't replay history. Seen ids are then reset to the current
        window each poll, keeping memory bounded; a dismissed alert keeps its id
        so it never re-fires.
        """
        current_ids = {str(ev.get("id")) for ev in logs if ev.get("id") is not None}
        if not self._alert_baseline_done:
            self._alert_baseline_done = True
            self._seen_alert_ids = current_ids
            return
        # Fire oldest-first so listeners receive events in chronological order.
        for ev in reversed(logs):
            ev_id = ev.get("id")
            if ev_id is None or str(ev_id) in self._seen_alert_ids:
                continue
            self.hass.bus.async_fire(
                EVENT_NEW_ALERT, build_event_payload(self.entry.entry_id, ev)
            )
        self._seen_alert_ids = current_ids

    @callback
    async def async_initialize(self) -> None:
        """Load persisted rogue-AP history and usage watermarks from storage."""
        stored = await self._rogue_history_store.async_load()
        if isinstance(stored, dict):
            self.rogue_history = {
                b: dict(v) for b, v in stored.items() if isinstance(v, dict)
            }

        usage = await self._usage_store.async_load()
        if isinstance(usage, dict):
            self.usage_watermark = {
                k: {"period": int(v["period"]), "value": int(v["value"])}
                for k, v in usage.items()
                if isinstance(v, dict) and "period" in v and "value" in v
            }

    async def async_flush_stores(self) -> None:
        """Write any pending delayed store saves immediately.

        Called on unload. A coalesced ``async_delay_save`` is flushed by the
        HOMEASSISTANT_STOP event on a restart, but a config-entry reload fires no
        such event — so without this, the most recent usage watermark could be
        lost across a reload and re-emit the very counter step it prevents.
        """
        await self._usage_store.async_save(self.usage_watermark)
        await self._rogue_history_store.async_save(self.rogue_history)

    def _clamp_usage(
        self, key: str, period: int | None, raw: float | None
    ) -> int | None:
        """Clamp a cumulative usage counter to its running maximum.

        UniFi apportions the open daily/monthly bucket and recomputes it every
        poll, so ``raw`` can dip slightly below the previous reading within a
        period — which trips the ``total_increasing`` state class. We hold the
        running maximum per counter and only let the value fall when the bucket's
        ``period`` timestamp moves **forward** (a genuine day/month rollover,
        where the new bucket legitimately restarts near zero).

        Reset detection keys on ``period`` alone, never on the value — a forward
        period move is the only real reset, and requiring *forward* (not merely
        *different*) means a controller re-stamping the current bucket cannot be
        mistaken for one. Bytes are rounded to whole numbers: the source is a
        byte counter, and sub-byte apportionment noise is meaningless.
        """
        if raw is None or period is None:
            return None if raw is None else round(raw)
        raw_i = round(raw)
        prev = self.usage_watermark.get(key)
        if prev is None or period > prev["period"]:
            # First sight, or a real rollover — adopt the new value verbatim.
            self.usage_watermark[key] = {"period": period, "value": raw_i}
            return raw_i
        if period == prev["period"]:
            # Same period — never step backwards.
            value = max(raw_i, prev["value"])
            self.usage_watermark[key] = {"period": period, "value": value}
            return value
        # period < prev["period"]: a stale/out-of-order bucket — hold last good.
        return prev["value"]

    def _update_rogue_history(
        self, rogue_aps: list[dict[str, Any]], now: datetime
    ) -> set[str]:
        """Update the persistent BSSID history; return newly-first-seen BSSIDs.

        A baseline (empty store on the first poll of this coordinator instance)
        records everything silently and returns an empty set. Otherwise a BSSID
        not previously in the store is "new" — this survives restarts, so the
        event won't re-fire for BSSIDs already tracked before a reload.
        """
        now_iso = now.isoformat()
        prev_keys = set(self.rogue_history)
        is_first_poll = not self._rogue_baseline_done
        self._rogue_baseline_done = True

        current_bssids: set[str] = set()
        for ap in rogue_aps:
            bssid = ap.get("bssid")
            if not bssid:
                continue
            current_bssids.add(bssid)
            rec = self.rogue_history.get(bssid)
            if rec is None:
                self.rogue_history[bssid] = {
                    "first_seen": now_iso,
                    "last_seen": now_iso,
                    "appearances": 1,
                    "last_label": ap.get("essid"),
                }
            else:
                rec["last_seen"] = now_iso
                rec["appearances"] = int(rec.get("appearances", 0)) + 1
                rec["last_label"] = ap.get("essid")

        self._prune_rogue_history(now)
        # Coalesce writes so a fast poll cadence doesn't hammer .storage.
        self._rogue_history_store.async_delay_save(
            lambda: self.rogue_history, ROGUE_HISTORY_SAVE_DELAY
        )

        if is_first_poll and not prev_keys:
            return set()
        return current_bssids - prev_keys

    def _prune_rogue_history(self, now: datetime) -> None:
        """Apply the TTL window and the hard max-entries cap to the history."""
        ttl_days = self.entry.options.get(
            CONF_ROGUE_HISTORY_TTL_DAYS, DEFAULT_ROGUE_HISTORY_TTL_DAYS
        )
        if ttl_days > 0:
            cutoff = now - timedelta(days=ttl_days)
            self.rogue_history = {
                b: r
                for b, r in self.rogue_history.items()
                if (last := dt_util.parse_datetime(r.get("last_seen") or "")) is None
                or last > cutoff
            }
        # Hard cap regardless of TTL — MAC randomization can spray many one-off
        # BSSIDs; keep the most-recently-seen entries. ISO strings sort by time.
        if len(self.rogue_history) > ROGUE_HISTORY_MAX:
            ordered = sorted(
                self.rogue_history.items(),
                key=lambda kv: kv[1].get("last_seen") or "",
                reverse=True,
            )
            self.rogue_history = dict(ordered[:ROGUE_HISTORY_MAX])

    def _annotate_rogue_history(self, rogue_aps: list[dict[str, Any]]) -> None:
        """Merge first_seen / appearances from history onto each rogue item."""
        for ap in rogue_aps:
            rec = self.rogue_history.get(ap.get("bssid") or "")
            ap["first_seen"] = rec.get("first_seen") if rec else None
            ap["appearances"] = rec.get("appearances") if rec else None

    def rogue_new_24h(self, now: datetime) -> int:
        """Count history BSSIDs first seen within the last 24 hours."""
        cutoff = now - timedelta(hours=24)
        count = 0
        for rec in self.rogue_history.values():
            first = dt_util.parse_datetime(rec.get("first_seen") or "")
            if first is not None and first > cutoff:
                count += 1
        return count

    async def async_clear_rogue_history(self) -> None:
        """Empty the persistent rogue-AP history and its store."""
        self.rogue_history = {}
        self._rogue_baseline_done = False
        await self._rogue_history_store.async_save({})

    def _fire_new_rogue_events(
        self, rogue_aps: list[dict[str, Any]], new_bssids: set[str]
    ) -> None:
        """Fire ``EVENT_NEW_ROGUE_AP`` once per genuinely-new BSSID."""
        for ap in rogue_aps:
            if ap.get("bssid") in new_bssids:
                self.hass.bus.async_fire(
                    EVENT_NEW_ROGUE_AP,
                    build_rogue_event_payload(self.entry.entry_id, ap),
                )

    @callback
    def _sync_site_issue(self) -> None:
        """Raise or clear a repair issue based on v3 site resolution.

        A ``site_uuid`` of ``"failed"`` means the v3 API could not be reached —
        usually an API key lacking full site permissions — which silently
        disables the VPN, firewall, and WAN-interface-name sensors. Surface it
        in the Repairs panel so the user can act; clear it once resolved.

        The v3 (integration) endpoints are only reachable with an API key, so
        under username/password auth this failure is *expected* and not
        actionable — suppress the repair issue entirely in that mode.
        """
        issue_id = repair_issue_id(self.entry.entry_id, "site_resolution_failed")
        if self.site_uuid == "failed" and self.api.api_key:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="site_resolution_failed",
            )
        elif self.site_uuid is not None:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)

    def _record_fetch_failure_health(self, err: Exception) -> None:
        """Flag Integration Health when the whole fetch fails.

        Every other entity is either holding last-known values or has gone
        unavailable, so this sensor is the only one able to say *why*. It reports:

        * **Cold start** (``self.data`` is None — nothing has ever been fetched):
          on the **first** failure. There are no values to hold, so waiting three
          cycles would leave the user with a silent, wholly-unavailable
          integration for up to three poll intervals.
        * **Runtime**: on the **third** consecutive failure, matching the §8
          3-strike rule that governs everything else, so a single blip does not
          raise an alarm.

        Cleared immediately by the next successful fetch.
        """
        cold_start = self.data is None
        if not cold_start and self.consecutive_failures < FETCH_STRIKE_LIMIT:
            return

        reason = (
            "UniFi gateway unreachable since startup — no data has been fetched"
            if cold_start
            else f"UniFi gateway unreachable ({self.consecutive_failures} "
            "consecutive failed updates)"
        )
        self.health_snapshot = {
            **self.health_snapshot,
            "problem": True,
            "severity": "serious",
            "issues": [f"{reason}: {err}"],
            "degraded_capabilities": ["All — gateway unreachable"],
            "auth_mode": "api_key" if self.api.api_key else "password",
        }

    def _compute_integration_health(
        self, opts: Mapping[str, Any], raw_drift: dict[str, bool]
    ) -> dict[str, Any]:
        """Build the Integration Health snapshot from current internal state.

        ``raw_drift`` carries this cycle's per-source drift signal, but only for
        sources that were *freshly fetched* (a stale/held or user-disabled source
        is absent and its strike counter decays). A drift flags only after it has
        persisted HEALTH_DRIFT_STRIKE_LIMIT cycles.
        """
        persistent: list[str] = []
        for key in ("gateway", "rogue", "alerts"):
            signal = raw_drift.get(key)
            if signal is None:  # not evaluated this cycle — reset
                self._drift_strikes.pop(key, None)
                continue
            if signal:
                self._drift_strikes[key] = self._drift_strikes.get(key, 0) + 1
                if self._drift_strikes[key] >= HEALTH_DRIFT_STRIKE_LIMIT:
                    persistent.append(key)
            else:
                self._drift_strikes.pop(key, None)

        # Degraded = failed endpoints the user did NOT disable; v3 endpoints are
        # expected to be down under password auth, so exclude them there.
        degraded = set(self._stale_endpoints) - disabled_endpoints(opts)
        if not self.api.api_key:
            degraded -= _V3_ENDPOINTS
        degraded_caps = sorted({_ENDPOINT_CAPABILITY.get(ep, ep) for ep in degraded})

        site_failed = self.site_uuid == "failed" and bool(self.api.api_key)
        drift_caps = [_DRIFT_CAPABILITY[k] for k in persistent]

        issues: list[str] = [
            f"{cap} data looks malformed (possible controller update)"
            for cap in drift_caps
        ]
        issues.extend(f"{cap} data unavailable" for cap in degraded_caps)
        if site_failed:
            issues.append(
                "UniFi v3 site could not be resolved "
                "(VPN, firewall and WAN-name sensors unavailable)"
            )

        serious = bool(drift_caps) or site_failed
        severity = "serious" if serious else ("moderate" if degraded_caps else None)

        return {
            "problem": severity is not None,
            "severity": severity,
            "issues": issues,
            "degraded_capabilities": degraded_caps,
            "drift": drift_caps,
            "auth_mode": "api_key" if self.api.api_key else "password",
            "v3_available": self.site_uuid not in (None, "failed"),
            "last_good_update": (
                self.last_update_success_time.isoformat()
                if self.last_update_success_time
                else None
            ),
        }

    def _sync_health_issues(self, health: dict[str, Any]) -> None:
        """Raise/clear the schema-drift repair issue based on the health snapshot.

        (The v3 ``site_resolution_failed`` repair is owned by ``_sync_site_issue``;
        it is reflected in the health sensor's attributes, not double-raised here.)
        """
        issue_id = repair_issue_id(self.entry.entry_id, "schema_drift_detected")
        if health.get("drift"):
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="schema_drift_detected",
                translation_placeholders={"capabilities": ", ".join(health["drift"])},
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)

    def endpoint_available(self, source: str | None) -> bool:
        """Return False when an optional endpoint has exhausted its retry strikes.

        Entities tag themselves with the endpoint `source` they depend on; a
        stale endpoint makes those entities report "unavailable" while endpoints
        that are still succeeding keep serving data.
        """
        if source is None:
            return True
        return source not in self._stale_endpoints

    def _hold_or_stale(
        self,
        label: str,
        state: dict[str, Any],
        err: Exception,
        level: int,
    ) -> list[dict[str, Any]]:
        """Apply the per-endpoint strike rule on a failed optional fetch.

        Holds the last-good payload for the first FETCH_STRIKE_LIMIT failures,
        then flags the endpoint stale (entities go unavailable). The held
        payload is still returned so the rest of the update proceeds.
        """
        state["failures"] += 1
        if state["failures"] <= FETCH_STRIKE_LIMIT:
            _LOGGER.log(
                level,
                "%s: %s fetch failed (%d/%d), holding last values: %s",
                self.entry.title,
                label,
                state["failures"],
                FETCH_STRIKE_LIMIT,
                err,
            )
        else:
            if label not in self._stale_endpoints:
                _LOGGER.warning(
                    "%s: %s unavailable after %d consecutive failures: %s",
                    self.entry.title,
                    label,
                    state["failures"],
                    err,
                )
            self._stale_endpoints.add(label)
        last_good: list[dict[str, Any]] = state["last_good"]
        return last_good

    async def _skip_fetch(self, label: str) -> list[dict[str, Any]]:
        """No-op stand-in for a disabled endpoint — no network call.

        Keeps the gather list's positional layout intact while clearing any
        prior state so a re-enabled endpoint starts fresh.
        """
        self._endpoint_state.pop(label, None)
        self._stale_endpoints.discard(label)
        if label == EP_SYSLOG:
            # Alerts is off — force the next fetch (on re-enable) to re-baseline
            # so the backlog doesn't flood the bus with events.
            self._alert_baseline_done = False
            self._seen_alert_ids.clear()
        # Security (EP_ROGUE) needs no reset: the persistent BSSID history
        # already suppresses re-fires for BSSIDs tracked before it was disabled.
        return []

    def _optional(
        self,
        enabled: bool,
        method: Any,
        label: str,
    ) -> Any:
        """Return a real fetch coroutine, or a no-op skip when disabled."""
        if enabled:
            return self._fetch_optional(method, label)
        return self._skip_fetch(label)

    async def _fetch_optional(
        self,
        method: Any,
        label: str,
    ) -> list[dict[str, Any]]:
        """Fetch a supplementary endpoint with per-endpoint resilience.

        On success: cache and return the fresh payload, clearing any stale flag.
        On failure: hold the last-good payload (strikes 1..FETCH_STRIKE_LIMIT),
        then mark the endpoint stale. A broad ``except`` is intentional so a
        changed/unexpected API response degrades this one endpoint rather than
        tripping the global failure path.
        """
        state = self._endpoint_state.setdefault(label, {"last_good": [], "failures": 0})
        try:
            data = list(await method())
        except (UnifiConnectionError, UnifiAuthError, TimeoutError) as err:
            return self._hold_or_stale(label, state, err, logging.DEBUG)
        except Exception as err:  # noqa: BLE001 - tolerate API drift per-endpoint
            return self._hold_or_stale(label, state, err, logging.WARNING)
        state["last_good"] = data
        state["failures"] = 0
        self._stale_endpoints.discard(label)
        return data

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch all data with 3-strike resilience."""
        is_paused = self.entry.options.get(CONF_STOP_POLLING, False)
        # An explicit user action (Refresh Now, speedtest, weight/interval
        # change) sets _force_refresh_once so pause is bypassed exactly once.
        force = self._force_refresh_once
        if is_paused and not force and self.data is not None:
            _LOGGER.debug(
                "%s: Polling is paused; returning cached data.", self.entry.title
            )
            return self.data
        # Consume the one-shot flag now that we're committing to a fetch.
        self._force_refresh_once = False

        try:
            # Resolve Site UUID if using API Key and not resolved yet
            if self.site_uuid is None:
                try:
                    sites = await self.api.get_sites()
                    target_site = (
                        self.api.site
                        if hasattr(self.api, "site") and isinstance(self.api.site, str)
                        else "default"
                    )
                    for s in sites:
                        if s.get("internalReference") == target_site:
                            self.site_uuid = s.get("id")
                            break
                    if not self.site_uuid:
                        _LOGGER.warning(
                            "Could not find site UUID for site %s", target_site
                        )
                        self.site_uuid = "failed"
                except TypeError as err:
                    _LOGGER.debug(
                        "TypeError during site UUID resolution "
                        "(likely unmocked in test): %s",
                        err,
                    )
                    self.site_uuid = "failed"
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug("Failed to fetch sites for UUID resolution: %s", err)
                    if (
                        "HTTP error 404" in str(err)
                        or "HTTP error 400" in str(err)
                        or "API key rejected" in str(err)
                        or isinstance(err, UnifiAuthError)
                    ):
                        self.site_uuid = "failed"
                self._sync_site_issue()

            async with asyncio.timeout(30):
                update_time = dt_util.now()

                # Feature toggles — a disabled category skips its network call(s)
                # while keeping the gather list's positional layout intact.
                opts = self.entry.options
                want_speedtest = opts.get(
                    CONF_ENABLE_SPEEDTEST, DEFAULT_ENABLE_SPEEDTEST
                )
                want_wan_usage = opts.get(
                    CONF_ENABLE_WAN_USAGE, DEFAULT_ENABLE_WAN_USAGE
                )
                want_security = opts.get(
                    CONF_ENABLE_SECURITY_MONITORING, DEFAULT_ENABLE_SECURITY_MONITORING
                )
                want_logs = opts.get(
                    CONF_ENABLE_LOGS_ALERTS, DEFAULT_ENABLE_LOGS_ALERTS
                )
                rogue_period = opts.get(CONF_ROGUE_PERIOD, DEFAULT_ROGUE_PERIOD)
                rogue_within = ROGUE_PERIOD_HOURS.get(rogue_period, 1)

                # Define concurrent tasks
                tasks = [
                    self.api.get_devices(),
                    self.api.get_health(),
                    self._fetch_optional(self.api.get_sysinfo, EP_SYSINFO),
                    self._fetch_optional(self.api.get_networkconf, EP_NETWORKCONF),
                    self._optional(want_security, self.api.get_settings, EP_SETTINGS),
                    self._optional(
                        want_wan_usage, self.api.get_daily_gateway, EP_DAILY
                    ),
                    self._optional(
                        want_wan_usage, self.api.get_monthly_gateway, EP_MONTHLY
                    ),
                    self._optional(
                        want_security,
                        lambda: self.api.get_rogueaps(within_hours=rogue_within),
                        EP_ROGUE,
                    ),
                    self._fetch_optional(self.api.get_guests, EP_GUESTS),
                    self._fetch_optional(self.api.get_backups, EP_BACKUPS),
                    self._optional(
                        want_speedtest, self.api.get_speedtest_results, EP_SPEEDTEST
                    ),
                    self._fetch_optional(self.api.get_wlanconf, EP_WLAN),
                    self._optional(
                        want_logs,
                        lambda: self.api.get_system_logs(
                            severities=["HIGH", "VERY_HIGH"]
                        ),
                        EP_SYSLOG,
                    ),
                    self._optional(
                        want_security,
                        lambda: self.api.get_rogueaps(
                            within_hours=ROGUE_RAW_WINDOW_HOURS
                        ),
                        EP_ROGUE_RAW,
                    ),
                ]

                # Conditional v3 endpoint fetches
                if self.site_uuid and self.site_uuid != "failed":
                    tasks.extend(
                        [
                            self._fetch_optional(
                                lambda: self.api.get_wan_interfaces(self.site_uuid),
                                EP_WAN_IF,
                            ),
                            self._optional(
                                want_security,
                                lambda: self.api.get_vpn_servers(self.site_uuid),
                                EP_VPN_SERVERS,
                            ),
                            self._optional(
                                want_security,
                                lambda: self.api.get_vpn_tunnels(self.site_uuid),
                                EP_VPN_TUNNELS,
                            ),
                            self._optional(
                                want_security,
                                lambda: self.api.get_firewall_policies(self.site_uuid),
                                EP_FIREWALL,
                            ),
                        ]
                    )
                else:

                    async def dummy_fetch() -> list[Any]:
                        return []

                    tasks.extend(
                        [dummy_fetch(), dummy_fetch(), dummy_fetch(), dummy_fetch()]
                    )

                results = await asyncio.gather(*tasks)

                (
                    devices_raw,
                    health_raw,
                    sysinfo_raw,
                    networkconf_raw,
                    settings_raw,
                    daily_gateway_raw,
                    monthly_gateway_raw,
                    rogueaps_raw,
                    guests_raw,
                    backups_raw,
                    speedtest_raw,
                    wlanconf_raw,
                    system_logs_raw,
                    rogueaps_raw_24h,
                    wan_interfaces_raw,
                    _vpn_servers_raw,
                    vpn_tunnels_raw,
                    firewall_policies_raw,
                ) = results

                sw_version: str | None = None
                if sysinfo_raw:
                    sw_version = sysinfo_raw[0].get("version")

                # Separate gateway from APs/switches
                gateway_device: dict[str, Any] | None = None
                gateway_data: dict[str, Any] | None = None
                devices: dict[str, dict[str, Any]] = {}

                for device in devices_raw:
                    if device.get("state", 0) == 0:
                        continue  # Offline — skip
                    try:
                        if device.get("model") in GATEWAY_MODELS:
                            gateway_device = device
                            gateway_data = _parse_gateway(device, update_time, self)
                        elif device.get("is_access_point"):
                            parsed = _parse_ap(device, update_time, self)
                            devices[parsed["mac"]] = parsed
                        else:
                            parsed = _parse_switch(device, update_time, self)
                            devices[parsed["mac"]] = parsed
                    except (
                        AttributeError,
                        KeyError,
                        TypeError,
                        ValueError,
                        IndexError,
                    ) as err:
                        _LOGGER.warning(
                            "%s: Failed to parse device %s, skipping: %s",
                            self.entry.title,
                            device.get("mac", "unknown"),
                            err,
                        )

                health = _parse_health(health_raw, update_time, self)

                # Parse load-balancing configs from networkconf
                wan_mode: str | None = None
                wan1_weight: int | None = None
                wan2_weight: int | None = None
                wan1_net, wan2_net = _extract_wan_networkconf(networkconf_raw)
                if wan1_net is not None:
                    wan1_weight = _safe_int(wan1_net.get("wan_load_balance_weight"))
                    wan_mode = wan1_net.get("wan_load_balance_type")
                    self._networkconf_wan = wan1_net
                if wan2_net is not None:
                    wan2_weight = _safe_int(wan2_net.get("wan_load_balance_weight"))
                    if not wan_mode:
                        wan_mode = wan2_net.get("wan_load_balance_type")
                    self._networkconf_wan2 = wan2_net

                # Parse threat management settings
                ips_mode: str | None = None
                ad_blocking: bool | None = None
                honeypot: bool | None = None
                for setting in settings_raw or []:
                    if setting.get("key") == "ips":
                        ips_mode = setting.get("ips_mode")
                        ad_blocking = bool(setting.get("ad_blocking_enabled"))
                        honeypot = bool(setting.get("honeypot_enabled"))

                # Today's Internet Usage
                wan1_today_rx = None
                wan1_today_tx = None
                wan2_today_rx = None
                wan2_today_tx = None
                try:
                    if daily_gateway_raw:
                        sorted_daily = sorted(
                            daily_gateway_raw,
                            key=lambda x: x.get("time") or 0,
                            reverse=True,
                        )
                        latest_daily = sorted_daily[0]
                        day = latest_daily.get("time")
                        day = int(day) if isinstance(day, (int, float)) else None
                        wan1_today_rx = self._clamp_usage(
                            "wan1_today_rx",
                            day,
                            _safe_float(latest_daily.get("wan-rx_bytes")),
                        )
                        wan1_today_tx = self._clamp_usage(
                            "wan1_today_tx",
                            day,
                            _safe_float(latest_daily.get("wan-tx_bytes")),
                        )
                        wan2_today_rx = self._clamp_usage(
                            "wan2_today_rx",
                            day,
                            _safe_float(latest_daily.get("wan2-rx_bytes")),
                        )
                        wan2_today_tx = self._clamp_usage(
                            "wan2_today_tx",
                            day,
                            _safe_float(latest_daily.get("wan2-tx_bytes")),
                        )
                except (
                    AttributeError,
                    KeyError,
                    TypeError,
                    ValueError,
                    IndexError,
                ) as err:
                    _LOGGER.debug(
                        "%s: Failed to parse daily gateway data: %s",
                        self.entry.title,
                        err,
                    )

                # Monthly Internet Usage
                wan1_month_rx = None
                wan1_month_tx = None
                wan2_month_rx = None
                wan2_month_tx = None
                try:
                    if monthly_gateway_raw:
                        sorted_monthly = sorted(
                            monthly_gateway_raw,
                            key=lambda x: x.get("time") or 0,
                            reverse=True,
                        )
                        latest_monthly = sorted_monthly[0]
                        month = latest_monthly.get("time")
                        month = int(month) if isinstance(month, (int, float)) else None
                        wan1_month_rx = self._clamp_usage(
                            "wan1_month_rx",
                            month,
                            _safe_float(latest_monthly.get("wan-rx_bytes")),
                        )
                        wan1_month_tx = self._clamp_usage(
                            "wan1_month_tx",
                            month,
                            _safe_float(latest_monthly.get("wan-tx_bytes")),
                        )
                        wan2_month_rx = self._clamp_usage(
                            "wan2_month_rx",
                            month,
                            _safe_float(latest_monthly.get("wan2-rx_bytes")),
                        )
                        wan2_month_tx = self._clamp_usage(
                            "wan2_month_tx",
                            month,
                            _safe_float(latest_monthly.get("wan2-tx_bytes")),
                        )
                except (
                    AttributeError,
                    KeyError,
                    TypeError,
                    ValueError,
                    IndexError,
                ) as err:
                    _LOGGER.debug(
                        "%s: Failed to parse monthly gateway data: %s",
                        self.entry.title,
                        err,
                    )

                # End-of-month usage projections. Derived from the monthly
                # counters above rather than fetched, so they cost nothing and
                # degrade with EP_MONTHLY exactly as their inputs do.
                wan1_month_projected, wan1_month_projected_attrs = (
                    build_usage_projection(
                        _sum_optional(wan1_month_rx, wan1_month_tx), update_time
                    )
                )
                wan2_month_projected, wan2_month_projected_attrs = (
                    build_usage_projection(
                        _sum_optional(wan2_month_rx, wan2_month_tx), update_time
                    )
                )

                # Persist the watermarks the two blocks above just updated, so a
                # restart does not re-emit a downward step against stored history.
                if self.usage_watermark:
                    self._usage_store.async_delay_save(
                        lambda: self.usage_watermark, USAGE_WATERMARK_SAVE_DELAY
                    )

                # Rogue Access Points — curated view (Security options applied).
                rogue_ap_count = 0
                rogue_new_24h = 0
                rogue_aps_list: list[dict[str, Any]] = []
                # "None Detected" (not unknown) is preferred for the text sensor
                # when no rogues are present; the RSSI counterpart stays None so
                # its numeric sensor reports "unknown" rather than a fake 0.
                strongest_rogue_ssid: str = "None Detected"
                strongest_rogue_rssi: int | None = None
                try:
                    rogue_aps_list = parse_rogue_aps(
                        rogueaps_raw,
                        build_ap_name_map(devices_raw),
                        int(dt_util.as_timestamp(update_time)),
                        show_24ghz=opts.get(
                            CONF_ROGUE_SHOW_24GHZ, DEFAULT_ROGUE_SHOW_24GHZ
                        ),
                        show_5ghz=opts.get(
                            CONF_ROGUE_SHOW_5GHZ, DEFAULT_ROGUE_SHOW_5GHZ
                        ),
                        ignore_ssids=_split_patterns(
                            opts.get(
                                CONF_ROGUE_IGNORE_SSIDS, DEFAULT_ROGUE_IGNORE_SSIDS
                            )
                        ),
                        apply_ssid_ignore=opts.get(
                            CONF_ROGUE_APPLY_SSID_IGNORE,
                            DEFAULT_ROGUE_APPLY_SSID_IGNORE,
                        ),
                        ignore_aps=_split_patterns(
                            opts.get(CONF_ROGUE_IGNORE_APS, DEFAULT_ROGUE_IGNORE_APS)
                        ),
                        apply_ap_ignore=opts.get(
                            CONF_ROGUE_APPLY_AP_IGNORE, DEFAULT_ROGUE_APPLY_AP_IGNORE
                        ),
                    )
                    rogue_ap_count = len(rogue_aps_list)
                    # Strongest rogue = highest (least-negative) signal in dBm.
                    signalled = [
                        ap for ap in rogue_aps_list if ap.get("signal") is not None
                    ]
                    if signalled:
                        strongest = max(signalled, key=lambda ap: ap["signal"])
                        strongest_rogue_ssid = strongest.get("essid") or "None Detected"
                        strongest_rogue_rssi = strongest.get("signal")
                    if want_security:
                        # Persistent history: update first (captures "new" vs the
                        # store), then fire events and annotate the items with
                        # first_seen / appearances for the sensor attr + action.
                        new_bssids = self._update_rogue_history(
                            rogue_aps_list, update_time
                        )
                        self._fire_new_rogue_events(rogue_aps_list, new_bssids)
                        self._annotate_rogue_history(rogue_aps_list)
                        rogue_new_24h = self.rogue_new_24h(update_time)
                except (
                    AttributeError,
                    KeyError,
                    TypeError,
                    ValueError,
                    IndexError,
                ) as err:
                    _LOGGER.debug(
                        "%s: Failed to parse rogue AP data: %s", self.entry.title, err
                    )

                # Raw rogue-detection volume over a fixed 24h window — a
                # diagnostic long-term-trend metric, distinct from the clustered
                # current count. Counts raw per-(BSSID x reporter) rows with no
                # band/SSID/AP filtering, so a rogue seen by N APs counts N.
                rogue_raw_24h = len(rogueaps_raw_24h) if rogueaps_raw_24h else 0

                # Guest User Count
                guest_user_count = 0
                try:
                    guest_user_count = len(guests_raw) if guests_raw is not None else 0
                except (
                    AttributeError,
                    KeyError,
                    TypeError,
                    ValueError,
                    IndexError,
                ) as err:
                    _LOGGER.debug(
                        "%s: Failed to parse guest data: %s", self.entry.title, err
                    )

                # Auto Backups
                last_backup = None
                try:
                    if backups_raw:
                        sorted_backups = sorted(
                            backups_raw,
                            key=lambda x: x.get("time") or 0,
                            reverse=True,
                        )
                        latest_backup = sorted_backups[0]
                        backup_time_ms = latest_backup.get("time")
                        if backup_time_ms:
                            last_backup = datetime.fromtimestamp(
                                backup_time_ms / 1000.0, tz=UTC
                            )
                except (
                    AttributeError,
                    KeyError,
                    TypeError,
                    ValueError,
                    IndexError,
                ) as err:
                    _LOGGER.debug(
                        "%s: Failed to parse backup data: %s", self.entry.title, err
                    )

                # Configured VLANs Count
                configured_vlans = 0
                for net in networkconf_raw or []:
                    if net.get("vlan") is not None:
                        configured_vlans += 1

                # Firmware Details
                application_version = None
                application_build = None
                device_type = None
                udm_version = None
                if sysinfo_raw:
                    sys_item = sysinfo_raw[0]
                    application_version = sys_item.get("version")
                    application_build = sys_item.get("build")
                    device_type = sys_item.get("ubnt_device_type")
                    udm_version = sys_item.get("udm_version") or sys_item.get(
                        "sw_version"
                    )

                # WAN1 & WAN2 Speedtests
                wan1_speedtest_download = None
                wan1_speedtest_upload = None
                wan1_speedtest_ping = None
                wan1_speedtest_lastrun = None

                wan2_speedtest_download = None
                wan2_speedtest_upload = None
                wan2_speedtest_ping = None
                wan2_speedtest_lastrun = None

                try:
                    if speedtest_raw:
                        # Sort descending to get newest speedtests first
                        sorted_speedtest = sorted(
                            speedtest_raw,
                            key=lambda x: x.get("time") or 0,
                            reverse=True,
                        )

                        # Get configured physical interfaces for WAN1/WAN2
                        wan1_ifname = "eth8"
                        wan2_ifname = "eth9"
                        if gateway_device:
                            wan1_ifname = (
                                gateway_device.get("wan1", {}).get("ifname") or "eth8"
                            )
                            wan2_ifname = (
                                gateway_device.get("wan2", {}).get("ifname") or "eth9"
                            )

                        # Check if results have interface metadata
                        has_interface = any(
                            "interface_name" in x for x in sorted_speedtest
                        )

                        w1 = None
                        w2 = None

                        if has_interface:
                            # 1. Map by interface name or network group (preferred)
                            for item in sorted_speedtest:
                                if w1 is None and (
                                    item.get("interface_name") == wan1_ifname
                                    or item.get("wan_networkgroup") == "WAN"
                                ):
                                    w1 = item
                                if w2 is None and (
                                    item.get("interface_name") == wan2_ifname
                                    or item.get("wan_networkgroup") == "WAN2"
                                ):
                                    w2 = item
                                if w1 is not None and w2 is not None:
                                    break
                        # 2. Fallback to proximity-based ordering for compatibility
                        elif len(sorted_speedtest) >= 2:
                            t0 = sorted_speedtest[0].get("time") or 0
                            t1 = sorted_speedtest[1].get("time") or 0
                            if abs(t0 - t1) <= 600 * 1000:
                                w1 = sorted_speedtest[1]
                                w2 = sorted_speedtest[0]
                            else:
                                w1 = sorted_speedtest[0]
                                w2 = None
                        else:
                            # Exactly one result: the enclosing `if
                            # speedtest_raw:` guarantees at least one and the
                            # branch above took >= 2.
                            w1 = sorted_speedtest[0]
                            w2 = None

                        # Map variables to gateway fields
                        if w1:
                            download = w1.get("download_mbps") or w1.get(
                                "xput_download"
                            )
                            upload = w1.get("upload_mbps") or w1.get("xput_upload")
                            ping = w1.get("latency_ms") or w1.get("latency")
                            wan1_speedtest_download = _safe_float(download)
                            wan1_speedtest_upload = _safe_float(upload)
                            wan1_speedtest_ping = _safe_float(ping)
                            w1_time = w1.get("time")
                            if w1_time:
                                wan1_speedtest_lastrun = datetime.fromtimestamp(
                                    w1_time / 1000.0, tz=UTC
                                )

                        if w2:
                            download = w2.get("download_mbps") or w2.get(
                                "xput_download"
                            )
                            upload = w2.get("upload_mbps") or w2.get("xput_upload")
                            ping = w2.get("latency_ms") or w2.get("latency")
                            wan2_speedtest_download = _safe_float(download)
                            wan2_speedtest_upload = _safe_float(upload)
                            wan2_speedtest_ping = _safe_float(ping)
                            w2_time = w2.get("time")
                            if w2_time:
                                wan2_speedtest_lastrun = datetime.fromtimestamp(
                                    w2_time / 1000.0, tz=UTC
                                )
                except (
                    AttributeError,
                    KeyError,
                    TypeError,
                    ValueError,
                    IndexError,
                ) as err:
                    _LOGGER.debug(
                        "%s: Failed to parse speedtest data: %s", self.entry.title, err
                    )

                # Parse WLAN Configurations (WiFi SSIDs)
                wifi_networks_total = None
                wifi_networks_active = None
                wifi_states = {}
                wifi_networks_total = len(wlanconf_raw)
                wifi_networks_active = sum(1 for w in wlanconf_raw if w.get("enabled"))
                wifi_states = {
                    w.get("name"): bool(w.get("enabled"))
                    for w in wlanconf_raw
                    if w.get("name")
                }

                # Parse VLANs configurations
                vlans_total = None
                vlans_active = None
                vlans_total = sum(
                    1 for net in networkconf_raw if net.get("vlan") is not None
                )
                vlans_active = sum(
                    1
                    for net in networkconf_raw
                    if net.get("vlan") is not None and net.get("enabled", True)
                )

                # Parse VPN site-to-site tunnels and servers
                vpn_connections_total = None
                vpn_connections_active = None
                vpn_states = {}
                if self.site_uuid and self.site_uuid != "failed":
                    vpn_connections_total = len(vpn_tunnels_raw)
                    vpn_connections_active = sum(
                        1 for t in vpn_tunnels_raw if t.get("state") == "CONNECTED"
                    )
                    vpn_states = {
                        t.get("name"): (t.get("state") == "CONNECTED")
                        for t in vpn_tunnels_raw
                        if t.get("name")
                    }

                # Parse Firewall Policies
                rules_configured = None
                rules_active = None
                rules_disabled = None
                if self.site_uuid and self.site_uuid != "failed":
                    rules_configured = len(firewall_policies_raw)
                    rules_active = sum(
                        1 for p in firewall_policies_raw if p.get("enabled")
                    )
                    rules_disabled = sum(
                        1 for p in firewall_policies_raw if not p.get("enabled")
                    )

                # Parse WAN interface custom names (aliases)
                wan1_interface_name = None
                wan2_interface_name = None
                if (
                    self.site_uuid
                    and self.site_uuid != "failed"
                    and isinstance(wan_interfaces_raw, list)
                ):
                    for wan in wan_interfaces_raw:
                        name = wan.get("name", "")
                        if "wan1" in name.lower():
                            wan1_interface_name = name
                        elif "wan2" in name.lower():
                            wan2_interface_name = name
                    # Fallbacks if string match doesn't hit
                    if not wan1_interface_name and len(wan_interfaces_raw) > 0:
                        wan1_interface_name = wan_interfaces_raw[0].get("name")
                    if not wan2_interface_name and len(wan_interfaces_raw) > 1:
                        wan2_interface_name = wan_interfaces_raw[1].get("name")

                # System-log alerts (HIGH / VERY_HIGH) — newest first. Split the
                # newest per severity for the "Last High/Very High" title
                # sensors, keep 24h counts, and fire an event per newly-seen id.
                # "None Detected" (not unknown) confirms the good steady-state of
                # no alerts of that severity; see alerts_expanded.md.
                last_high: str = "None Detected"
                last_high_attrs: dict[str, Any] | None = None
                last_very_high: str = "None Detected"
                last_very_high_attrs: dict[str, Any] | None = None
                alerts_high_24h = 0
                alerts_very_high_24h = 0
                try:
                    logs = sorted(
                        system_logs_raw or [],
                        key=lambda x: x.get("timestamp") or 0,
                        reverse=True,
                    )
                    cutoff_ms = (
                        int(dt_util.as_timestamp(update_time) - 24 * 3600) * 1000
                    )
                    for ev in logs:
                        sev = ev.get("severity")
                        within_24h = (ev.get("timestamp") or 0) >= cutoff_ms
                        if sev == "VERY_HIGH":
                            if within_24h:
                                alerts_very_high_24h += 1
                            if last_very_high_attrs is None:
                                last_very_high = alert_title(ev)
                                last_very_high_attrs = build_alert_attrs(ev)
                        elif sev == "HIGH":
                            if within_24h:
                                alerts_high_24h += 1
                            if last_high_attrs is None:
                                last_high = alert_title(ev)
                                last_high_attrs = build_alert_attrs(ev)
                    if want_logs:
                        self._fire_new_alert_events(logs)
                except (
                    AttributeError,
                    KeyError,
                    TypeError,
                    ValueError,
                    IndexError,
                ) as err:
                    _LOGGER.debug(
                        "%s: Failed to parse system logs: %s", self.entry.title, err
                    )

                # Inject parsed configuration into gateway data if gateway is present
                if gateway_data is not None:
                    gateway_data.update(
                        {
                            "wan_mode": wan_mode,
                            "last_high": last_high,
                            "last_high_attrs": last_high_attrs,
                            "last_very_high": last_very_high,
                            "last_very_high_attrs": last_very_high_attrs,
                            "alerts_high_24h": alerts_high_24h,
                            "alerts_very_high_24h": alerts_very_high_24h,
                            "wan1_weight": wan1_weight,
                            "wan2_weight": wan2_weight,
                            "ips_mode": ips_mode,
                            "ad_blocking": ad_blocking,
                            "honeypot": honeypot,
                            "wan1_today_rx": wan1_today_rx,
                            "wan1_today_tx": wan1_today_tx,
                            "wan2_today_rx": wan2_today_rx,
                            "wan2_today_tx": wan2_today_tx,
                            "wan1_month_rx": wan1_month_rx,
                            "wan1_month_tx": wan1_month_tx,
                            "wan1_month_projected": wan1_month_projected,
                            "wan1_month_projected_attrs": wan1_month_projected_attrs,
                            "wan2_month_projected": wan2_month_projected,
                            "wan2_month_projected_attrs": wan2_month_projected_attrs,
                            "wan2_month_rx": wan2_month_rx,
                            "wan2_month_tx": wan2_month_tx,
                            "rogue_ap_count": rogue_ap_count,
                            "rogue_new_24h": rogue_new_24h,
                            "rogue_aps_list": rogue_aps_list,
                            "strongest_rogue_ssid": strongest_rogue_ssid,
                            "strongest_rogue_rssi": strongest_rogue_rssi,
                            "rogue_raw_24h": rogue_raw_24h,
                            "guest_user_count": guest_user_count,
                            "last_backup": last_backup,
                            "configured_vlans": configured_vlans,
                            "application_version": application_version,
                            "application_build": application_build,
                            "device_type": device_type,
                            "udm_version": udm_version,
                            "wan1_speedtest_download": wan1_speedtest_download,
                            "wan1_speedtest_upload": wan1_speedtest_upload,
                            "wan1_speedtest_ping": wan1_speedtest_ping,
                            "wan1_speedtest_lastrun": wan1_speedtest_lastrun,
                            "wan2_speedtest_download": wan2_speedtest_download,
                            "wan2_speedtest_upload": wan2_speedtest_upload,
                            "wan2_speedtest_ping": wan2_speedtest_ping,
                            "wan2_speedtest_lastrun": wan2_speedtest_lastrun,
                            "wifi_networks_total": wifi_networks_total,
                            "wifi_networks_active": wifi_networks_active,
                            "wifi_states": wifi_states,
                            "vlans_total": vlans_total,
                            "vlans_active": vlans_active,
                            "vpn_connections_total": vpn_connections_total,
                            "vpn_connections_active": vpn_connections_active,
                            "vpn_states": vpn_states,
                            "rules_configured": rules_configured,
                            "rules_active": rules_active,
                            "rules_disabled": rules_disabled,
                            "wan1_interface_name": wan1_interface_name,
                            "wan2_interface_name": wan2_interface_name,
                        }
                    )

                # Update sw_version on coordinator if changed
                if sw_version and sw_version != self.sw_version:
                    self.sw_version = sw_version

                self.consecutive_failures = 0
                self.last_update_success_time = update_time
                if not self._was_available:
                    self._was_available = True
                    _LOGGER.info("%s: Reconnected successfully.", self.entry.title)

                # Self-diagnosis: per-source schema-drift signals — a non-empty
                # raw response that parsed to nothing meaningful. Only evaluated
                # for sources freshly fetched this cycle. Wrapped so a malformed
                # payload can never break the update it's diagnosing.
                integration_health: dict[str, Any] = {
                    "problem": False,
                    "severity": None,
                }
                try:
                    raw_drift: dict[str, bool] = {}
                    if gateway_data:
                        raw_drift["gateway"] = not any(
                            gateway_data.get(k) is not None
                            for k in ("cpu", "ram", "uptime_secs")
                        )
                    if (
                        want_security
                        and self.endpoint_available(EP_ROGUE)
                        and rogueaps_raw
                    ):
                        raw_drift["rogue"] = (not rogue_aps_list) or all(
                            not (isinstance(ap, dict) and ap.get("bssid"))
                            for ap in rogue_aps_list
                        )
                    if (
                        want_logs
                        and self.endpoint_available(EP_SYSLOG)
                        and system_logs_raw
                    ):
                        raw_drift["alerts"] = not any(
                            isinstance(ev, dict) and ev.get("severity")
                            for ev in system_logs_raw
                        )
                    integration_health = self._compute_integration_health(
                        opts, raw_drift
                    )
                    # A successful fetch clears any outage verdict immediately —
                    # the sensor must not stay on until some later cycle.
                    self.health_snapshot = integration_health
                    self._sync_health_issues(integration_health)
                except (AttributeError, KeyError, TypeError, ValueError) as err:
                    _LOGGER.debug(
                        "%s: integration-health computation skipped: %s",
                        self.entry.title,
                        err,
                    )

                return {
                    "gateway": gateway_data or {},
                    "health": health,
                    "devices": devices,
                    "sw_version": sw_version,
                    "integration_health": integration_health,
                }

        except UnifiAuthError as err:
            self.consecutive_failures += 1
            self._record_fetch_failure_health(err)
            if (
                self.data is not None
                and self.consecutive_failures <= FETCH_STRIKE_LIMIT
            ):
                log = (
                    _LOGGER.warning if self.consecutive_failures == 1 else _LOGGER.debug
                )
                log(
                    "%s: Authentication error fetching UniFi data (failure %d/3), holding last values: %s",
                    self.entry.title,
                    self.consecutive_failures,
                    err,
                )
                return self.data
            _LOGGER.error("%s: Authentication failed: %s", self.entry.title, err)
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err

        except (UnifiConnectionError, TimeoutError) as err:
            self.consecutive_failures += 1
            self._record_fetch_failure_health(err)
            if (
                self.data is not None
                and self.consecutive_failures <= FETCH_STRIKE_LIMIT
            ):
                log = (
                    _LOGGER.warning if self.consecutive_failures == 1 else _LOGGER.debug
                )
                log(
                    "%s: Error fetching UniFi data (failure %d/3), holding last values: %s",
                    self.entry.title,
                    self.consecutive_failures,
                    err,
                )
                return self.data
            self._was_available = False
            _LOGGER.error(
                "%s: Communication lost after 3 failures: %s", self.entry.title, err
            )
            if not self.data:
                raise ConfigEntryNotReady(f"Communication error: {err}") from err
            raise UpdateFailed(f"Communication error: {err}") from err

        except Exception as err:
            self.consecutive_failures += 1
            self._record_fetch_failure_health(err)
            if (
                self.data is not None
                and self.consecutive_failures <= FETCH_STRIKE_LIMIT
            ):
                log = (
                    _LOGGER.warning if self.consecutive_failures == 1 else _LOGGER.debug
                )
                log(
                    "%s: Unexpected error (failure %d/3), holding last values: %s",
                    self.entry.title,
                    self.consecutive_failures,
                    err,
                )
                return self.data
            self._was_available = False
            _LOGGER.error("%s: Unexpected error: %s", self.entry.title, err)
            if not self.data:
                raise ConfigEntryNotReady(f"Unexpected error: {err}") from err
            raise UpdateFailed(f"Unexpected error: {err}") from err
