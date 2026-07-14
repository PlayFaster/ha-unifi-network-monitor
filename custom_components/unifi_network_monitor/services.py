"""On-demand alert-query action for UniFi Network Monitor.

Registers the ``get_alerts`` response service — a fresh, capped query of the
system log that fills the history gap the passive sensors can't. The service is
domain-global (registered once for the integration) and stays available
regardless of the Alerts feature toggle; it does no polling, so a user who hid
the passive Alerts card can still query on demand.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, cast

import voluptuous as vol
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util

from .alerts import build_alert_response
from .const import (
    ALERT_MAX_PAGES,
    ALERT_PAGE_SIZE,
    ALERT_QUANTITY_DEFAULT,
    ALERT_QUANTITY_MAX,
    ALERT_SEVERITIES,
    DEFAULT_ALERT_SEVERITIES,
    DEFAULT_ROGUE_ACTION_BAND,
    DEFAULT_ROGUE_ACTION_PERIOD,
    DOMAIN,
    ROGUE_ACTION_BANDS,
    ROGUE_ACTION_PERIOD_HOURS,
    ROGUE_QUANTITY_DEFAULT,
    ROGUE_QUANTITY_MAX,
    SERVICE_GET_ALERTS,
    SERVICE_GET_ROGUE_APS,
)
from .coordinator import (
    UnifiNetworkDataUpdateCoordinator,
    build_ap_name_map,
    parse_rogue_aps,
    rogue_band_label,
)

_LOGGER = logging.getLogger(__name__)

GET_ALERTS_SCHEMA = vol.Schema(
    {
        vol.Optional("device_id"): cv.string,
        vol.Optional("severity"): vol.All(cv.ensure_list, [vol.In(ALERT_SEVERITIES)]),
        vol.Optional("quantity", default=ALERT_QUANTITY_DEFAULT): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=ALERT_QUANTITY_MAX)
        ),
        vol.Optional("age_days"): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Optional("keyword"): cv.string,
        vol.Optional("exclude"): cv.string,
    }
)

GET_ROGUE_APS_SCHEMA = vol.Schema(
    {
        vol.Optional("device_id"): cv.string,
        vol.Optional("period", default=DEFAULT_ROGUE_ACTION_PERIOD): vol.In(
            ROGUE_ACTION_PERIOD_HOURS
        ),
        vol.Optional("band", default=DEFAULT_ROGUE_ACTION_BAND): vol.In(
            ROGUE_ACTION_BANDS
        ),
        vol.Optional("min_signal"): vol.All(
            vol.Coerce(int), vol.Range(min=-100, max=0)
        ),
        vol.Optional("quantity", default=ROGUE_QUANTITY_DEFAULT): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=ROGUE_QUANTITY_MAX)
        ),
        vol.Optional("keyword"): cv.string,
        vol.Optional("exclude"): cv.string,
    }
)


def _split_terms(value: str | None) -> list[str]:
    """Split a comma-separated filter string into lowercased, non-empty terms."""
    if not value:
        return []
    return [t for t in (part.strip().lower() for part in value.split(",")) if t]


def _excluded(haystack: str, terms: list[str]) -> bool:
    """True if any exclude term is a substring of the (lowercased) haystack."""
    return any(term in haystack for term in terms)


def _resolve_coordinator(
    hass: HomeAssistant, call: ServiceCall
) -> UnifiNetworkDataUpdateCoordinator:
    """Resolve the target coordinator from a device id, or the sole entry.

    Mirrors the ZTE/Huawei SMS actions: a device target is optional and defaults
    to the only configured entry when there is exactly one.
    """
    entries = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if getattr(entry, "runtime_data", None) is not None
    ]
    device_id = call.data.get("device_id")

    if device_id:
        device = dr.async_get(hass).async_get(device_id)
        if device is None:
            raise ServiceValidationError(f"Unknown device id: {device_id}")
        for entry_id in device.config_entries:
            entry = hass.config_entries.async_get_entry(entry_id)
            if (
                entry is not None
                and entry.domain == DOMAIN
                and getattr(entry, "runtime_data", None) is not None
            ):
                return cast(UnifiNetworkDataUpdateCoordinator, entry.runtime_data)
        raise ServiceValidationError(
            f"Device {device_id} is not a UniFi Network Monitor device"
        )

    if not entries:
        raise ServiceValidationError("No UniFi Network Monitor entries are loaded")
    if len(entries) > 1:
        raise ServiceValidationError(
            "Multiple UniFi Network Monitor entries configured; specify a device"
        )
    return cast(UnifiNetworkDataUpdateCoordinator, entries[0].runtime_data)


async def _fetch_alerts(
    coordinator: UnifiNetworkDataUpdateCoordinator,
    severities: list[str],
    quantity: int,
    cutoff_ms: int | None,
    keyword: str,
    exclude: list[str],
) -> list[dict[str, Any]]:
    """Page the system log (newest-first) and collect matching alerts.

    Bounded to ALERT_MAX_PAGES; stops early on quantity reached, a short page
    (end of log), or — with an age cutoff — the first older-than-cutoff record.
    ``keyword`` (include) and ``exclude`` (any-term drop) both match the
    title+message text.
    """
    collected: list[dict[str, Any]] = []
    for page in range(ALERT_MAX_PAGES):
        batch = await coordinator.api.get_system_logs(
            severities=severities,
            page_number=page,
            page_size=ALERT_PAGE_SIZE,
        )
        if not batch:
            break
        for ev in batch:
            if cutoff_ms is not None and (ev.get("timestamp") or 0) < cutoff_ms:
                return collected
            record = build_alert_response(ev)
            if keyword or exclude:
                haystack = f"{record['title']} {record['message']}".lower()
                if keyword and keyword not in haystack:
                    continue
                if _excluded(haystack, exclude):
                    continue
            collected.append(record)
            if len(collected) >= quantity:
                return collected
        if len(batch) < ALERT_PAGE_SIZE:
            break
    return collected


async def _handle_get_alerts(hass: HomeAssistant, call: ServiceCall) -> ServiceResponse:
    """Return a capped, human-readable slice of the system log on demand."""
    coordinator = _resolve_coordinator(hass, call)
    severities = list(call.data.get("severity") or DEFAULT_ALERT_SEVERITIES)
    quantity = call.data["quantity"]
    keyword = (call.data.get("keyword") or "").strip().lower()
    exclude = _split_terms(call.data.get("exclude"))

    cutoff_ms: int | None = None
    age_days = call.data.get("age_days")
    if age_days:
        cutoff_ms = int((dt_util.as_timestamp(dt_util.now()) - age_days * 86400) * 1000)

    alerts = await _fetch_alerts(
        coordinator, severities, quantity, cutoff_ms, keyword, exclude
    )
    return cast(ServiceResponse, {"count": len(alerts), "alerts": alerts})


def _cached_ap_name_map(
    coordinator: UnifiNetworkDataUpdateCoordinator,
) -> dict[str, str]:
    """Build the AP MAC -> name map from the coordinator's cached device data.

    Avoids an extra device fetch: names change rarely, and the mandatory
    devices/health fetch keeps this populated even when Security is off.
    """
    data = coordinator.data or {}
    devices = list((data.get("devices") or {}).values())
    gateway = data.get("gateway")
    if gateway:
        devices = [gateway, *devices]
    return build_ap_name_map(devices)


def _rogue_response_item(ap: dict[str, Any]) -> dict[str, Any]:
    """Shape one clustered rogue AP into a human-readable response record."""
    last_seen = ap.get("last_seen")
    return {
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
        "age": ap.get("age"),
        "last_seen": (
            datetime.fromtimestamp(last_seen, tz=UTC).isoformat() if last_seen else None
        ),
        "detected_by": ap.get("detected_by"),
    }


async def _handle_get_rogue_aps(
    hass: HomeAssistant, call: ServiceCall
) -> ServiceResponse:
    """Return the current rogue-AP set on demand (fresh fetch, self-contained).

    Fetches its own data so it works regardless of the Security toggle, and
    applies only the caller's band/signal/keyword filters — the Security
    sub-device's ignore-lists are deliberately not applied, so the action can
    surface an AP the user chose to hide from the passive view.
    """
    coordinator = _resolve_coordinator(hass, call)
    within_hours = ROGUE_ACTION_PERIOD_HOURS[call.data["period"]]
    band = call.data["band"]
    show_24 = band in ("2.4", "both")
    show_5 = band in ("5", "both")
    min_signal = call.data.get("min_signal")
    keyword = (call.data.get("keyword") or "").strip().lower()
    exclude = _split_terms(call.data.get("exclude"))
    quantity = call.data["quantity"]

    rogueaps_raw = await coordinator.api.get_rogueaps(within_hours=within_hours)
    now_ts = int(dt_util.as_timestamp(dt_util.now()))
    parsed = parse_rogue_aps(
        rogueaps_raw,
        _cached_ap_name_map(coordinator),
        now_ts,
        show_24ghz=show_24,
        show_5ghz=show_5,
    )

    matched: list[dict[str, Any]] = []
    for ap in parsed:
        signal = ap.get("signal")
        if min_signal is not None and (signal is None or signal < min_signal):
            continue
        if keyword or exclude:
            haystack = (
                f"{ap.get('essid') or ''} {ap.get('oui') or ''} "
                f"{ap.get('security') or ''}"
            ).lower()
            if keyword and keyword not in haystack:
                continue
            if _excluded(haystack, exclude):
                continue
        matched.append(ap)

    # Strongest (least-negative) first; unknown-signal entries sort last.
    matched.sort(
        key=lambda a: a["signal"] if a.get("signal") is not None else -9999,
        reverse=True,
    )
    results = [_rogue_response_item(ap) for ap in matched[:quantity]]
    return cast(ServiceResponse, {"count": len(results), "rogue_aps": results})


def async_register_services(hass: HomeAssistant) -> None:
    """Register the domain-global on-demand query actions (idempotent)."""
    if hass.services.has_service(DOMAIN, SERVICE_GET_ALERTS):
        return

    async def _get_alerts(call: ServiceCall) -> ServiceResponse:
        return await _handle_get_alerts(hass, call)

    async def _get_rogue_aps(call: ServiceCall) -> ServiceResponse:
        return await _handle_get_rogue_aps(hass, call)

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_ALERTS,
        _get_alerts,
        schema=GET_ALERTS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_ROGUE_APS,
        _get_rogue_aps,
        schema=GET_ROGUE_APS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
