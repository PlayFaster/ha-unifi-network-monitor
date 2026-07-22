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
from homeassistant.config_entries import ConfigEntry
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

from ._compat import owning_entry_ids
from .alerts import build_alert_response
from .const import (
    ALERT_MAX_PAGES,
    ALERT_PAGE_SIZE,
    ALERT_QUANTITY_DEFAULT,
    ALERT_QUANTITY_MAX,
    ALERT_SEVERITIES,
    CONF_ROGUE_IGNORE_APS,
    CONF_ROGUE_IGNORE_SSIDS,
    DEFAULT_ALERT_SEVERITIES,
    DEFAULT_ROGUE_ACTION_BAND,
    DEFAULT_ROGUE_ACTION_PERIOD,
    DOMAIN,
    ROGUE_ACTION_BANDS,
    ROGUE_ACTION_PERIOD_HOURS,
    ROGUE_IGNORE_TARGET_SSIDS,
    ROGUE_IGNORE_TARGETS,
    ROGUE_QUANTITY_DEFAULT,
    ROGUE_QUANTITY_MAX,
    SERVICE_ADD_ROGUE_IGNORE,
    SERVICE_CLEAR_ROGUE_HISTORY,
    SERVICE_GET_ALERTS,
    SERVICE_GET_ROGUE_APS,
    SERVICE_REMOVE_ROGUE_IGNORE,
    SERVICE_SET_ROGUE_IGNORE,
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
        vol.Optional("count_total", default=False): cv.boolean,
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
    """Return True if any exclude term is a substring of the (lowercased) haystack."""
    return any(term in haystack for term in terms)


def _included(haystack: str, terms: list[str]) -> bool:
    """Return True if the haystack matches the keyword filter.

    An empty term list means "no keyword filter" (include everything); otherwise
    any single term matching as a substring includes the record (comma-list OR).
    """
    return not terms or any(term in haystack for term in terms)


def _resolve_coordinator(
    hass: HomeAssistant, call: ServiceCall
) -> UnifiNetworkDataUpdateCoordinator:
    """Resolve the target coordinator from a device id, or the sole entry.

    Mirrors the ZTE/Huawei SMS actions: a device target is optional and defaults
    to the only configured entry when there is exactly one.
    """
    entry = _resolve_entry(hass, call)
    return cast(UnifiNetworkDataUpdateCoordinator, entry.runtime_data)


async def _fetch_alerts(
    coordinator: UnifiNetworkDataUpdateCoordinator,
    severities: list[str],
    quantity: int,
    cutoff_ms: int | None,
    keyword_terms: list[str],
    exclude: list[str],
    count_total: bool = False,
) -> tuple[list[dict[str, Any]], int | None, bool]:
    """Page the system log (newest-first) and collect matching alerts.

    Returns ``(collected, total_matched, truncated)``.

    Bounded to ALERT_MAX_PAGES; ``keyword_terms`` (any-term include) and
    ``exclude`` (any-term drop) both match the title+message text.

    - Default (``count_total`` False): stops early once ``quantity`` is reached —
      the cheap path — and returns ``total_matched=None``, ``truncated=False``.
    - ``count_total`` True: keeps scanning past ``quantity`` (still only
      collecting up to it) to count every match within the scan, and reports
      ``truncated=True`` if the ALERT_MAX_PAGES scan cap was hit before the log
      or age cutoff was exhausted (i.e. more matches may exist beyond the scan).
    """
    collected: list[dict[str, Any]] = []
    total = 0
    truncated = False
    for page in range(ALERT_MAX_PAGES):
        batch = await coordinator.api.get_system_logs(
            severities=severities,
            page_number=page,
            page_size=ALERT_PAGE_SIZE,
        )
        if not batch:
            break  # end of log — total is exact
        reached_cutoff = False
        for ev in batch:
            if cutoff_ms is not None and (ev.get("timestamp") or 0) < cutoff_ms:
                reached_cutoff = True
                break
            record = build_alert_response(ev)
            haystack = f"{record['title']} {record['message']}".lower()
            if not _included(haystack, keyword_terms):
                continue
            if _excluded(haystack, exclude):
                continue
            total += 1
            if len(collected) < quantity:
                collected.append(record)
            if not count_total and len(collected) >= quantity:
                return collected, None, False  # cheap path — stop early
        if reached_cutoff:
            break  # counted everything within the age window — not truncated
        if len(batch) < ALERT_PAGE_SIZE:
            break  # end of log — not truncated
    else:
        # Loop ran all ALERT_MAX_PAGES without an early break: the scan cap was
        # hit on full pages, so matching records may exist beyond what we saw.
        truncated = True

    if not count_total:
        return collected, None, False
    return collected, total, truncated


async def _handle_get_alerts(hass: HomeAssistant, call: ServiceCall) -> ServiceResponse:
    """Return a capped, human-readable slice of the system log on demand."""
    coordinator = _resolve_coordinator(hass, call)
    severities = list(call.data.get("severity") or DEFAULT_ALERT_SEVERITIES)
    quantity = call.data["quantity"]
    keyword_terms = _split_terms(call.data.get("keyword"))
    exclude = _split_terms(call.data.get("exclude"))
    count_total = call.data.get("count_total", False)

    cutoff_ms: int | None = None
    age_days = call.data.get("age_days")
    if age_days:
        cutoff_ms = int((dt_util.as_timestamp(dt_util.now()) - age_days * 86400) * 1000)

    alerts, total_matched, truncated = await _fetch_alerts(
        coordinator,
        severities,
        quantity,
        cutoff_ms,
        keyword_terms,
        exclude,
        count_total,
    )
    response: dict[str, Any] = {"count": len(alerts), "alerts": alerts}
    if count_total:
        response["total_matched"] = total_matched
        response["truncated"] = truncated
    return cast(ServiceResponse, response)


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


def _rogue_response_item(
    ap: dict[str, Any], history: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Shape one clustered rogue AP into a human-readable response record.

    ``first_seen`` / ``appearances`` are read (never written) from the coordinator's
    persistent history; they are ``None`` for a BSSID Home Assistant hasn't tracked
    (e.g. seen only via a wide action period, or while Security polling was off).
    """
    last_seen = ap.get("last_seen")
    rec = history.get(ap.get("bssid") or "")
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
        "first_seen": rec.get("first_seen") if rec else None,
        "appearances": rec.get("appearances") if rec else None,
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
    keyword_terms = _split_terms(call.data.get("keyword"))
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
        if keyword_terms or exclude:
            haystack = (
                f"{ap.get('essid') or ''} {ap.get('oui') or ''} "
                f"{ap.get('security') or ''}"
            ).lower()
            if not _included(haystack, keyword_terms):
                continue
            if _excluded(haystack, exclude):
                continue
        matched.append(ap)

    # Strongest (least-negative) first; unknown-signal entries sort last.
    matched.sort(
        key=lambda a: a["signal"] if a.get("signal") is not None else -9999,
        reverse=True,
    )
    # total_matched is the full filtered count; count/rogue_aps are quantity-capped.
    history = coordinator.rogue_history
    results = [_rogue_response_item(ap, history) for ap in matched[:quantity]]
    return cast(
        ServiceResponse,
        {
            "count": len(results),
            "total_matched": len(matched),
            "rogue_aps": results,
        },
    )


CLEAR_ROGUE_HISTORY_SCHEMA = vol.Schema({vol.Optional("device_id"): cv.string})

ADD_REMOVE_ROGUE_IGNORE_SCHEMA = vol.Schema(
    {
        vol.Optional("device_id"): cv.string,
        vol.Required("target"): vol.In(ROGUE_IGNORE_TARGETS),
        vol.Required("value"): cv.string,
    }
)

SET_ROGUE_IGNORE_SCHEMA = vol.Schema(
    {
        vol.Optional("device_id"): cv.string,
        vol.Required("target"): vol.In(ROGUE_IGNORE_TARGETS),
        vol.Optional("values", default=""): cv.string,
    }
)


def _resolve_entry(hass: HomeAssistant, call: ServiceCall) -> ConfigEntry:
    """Resolve the target config entry from a device id, or the sole entry."""
    entries = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if getattr(entry, "runtime_data", None) is not None
    ]
    device_id = call.data.get("device_id")
    if device_id:
        device = dr.async_get(hass).async_get(device_id)
        if device is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unknown_device",
                translation_placeholders={"device_id": device_id},
            )
        for entry_id in owning_entry_ids(device):
            entry = hass.config_entries.async_get_entry(entry_id)
            if (
                entry is not None
                and entry.domain == DOMAIN
                and getattr(entry, "runtime_data", None) is not None
            ):
                return entry
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="not_a_monitor_device",
            translation_placeholders={"device_id": device_id},
        )
    if not entries:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_entries_loaded",
        )
    if len(entries) > 1:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="multiple_entries",
        )
    return entries[0]


def _ignore_option_key(target: str) -> str:
    """Map an ignore-list target to its config-entry option key."""
    return (
        CONF_ROGUE_IGNORE_SSIDS
        if target == ROGUE_IGNORE_TARGET_SSIDS
        else CONF_ROGUE_IGNORE_APS
    )


def _parse_ignore_list(value: str | None) -> list[str]:
    """Split a comma-separated ignore-list option into stripped, non-empty items."""
    return [part.strip() for part in (value or "").split(",") if part.strip()]


def _write_ignore_list(
    hass: HomeAssistant, entry: ConfigEntry, key: str, items: list[str]
) -> None:
    """Persist an ignore list to entry options (the reload listener applies it)."""
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, key: ", ".join(items)}
    )


async def _handle_clear_rogue_history(
    hass: HomeAssistant, call: ServiceCall
) -> ServiceResponse:
    """Empty the persistent rogue-AP appearance history."""
    coordinator = _resolve_coordinator(hass, call)
    await coordinator.async_clear_rogue_history()
    return None


async def _handle_add_rogue_ignore(
    hass: HomeAssistant, call: ServiceCall
) -> ServiceResponse:
    """Append a pattern to a rogue ignore list (SSIDs or detecting APs)."""
    entry = _resolve_entry(hass, call)
    target = call.data["target"]
    key = _ignore_option_key(target)
    items = _parse_ignore_list(entry.options.get(key, ""))
    value = call.data["value"].strip()
    if value and value not in items:
        items.append(value)
    _write_ignore_list(hass, entry, key, items)
    return cast(ServiceResponse, {"target": target, "entries": items})


async def _handle_remove_rogue_ignore(
    hass: HomeAssistant, call: ServiceCall
) -> ServiceResponse:
    """Remove a pattern from a rogue ignore list (exact match; silent if absent)."""
    entry = _resolve_entry(hass, call)
    target = call.data["target"]
    key = _ignore_option_key(target)
    value = call.data["value"].strip()
    items = [i for i in _parse_ignore_list(entry.options.get(key, "")) if i != value]
    _write_ignore_list(hass, entry, key, items)
    return cast(ServiceResponse, {"target": target, "entries": items})


async def _handle_set_rogue_ignore(
    hass: HomeAssistant, call: ServiceCall
) -> ServiceResponse:
    """Replace a rogue ignore list wholesale; return the old and new lists."""
    entry = _resolve_entry(hass, call)
    target = call.data["target"]
    key = _ignore_option_key(target)
    old = _parse_ignore_list(entry.options.get(key, ""))
    new = _parse_ignore_list(call.data.get("values"))
    _write_ignore_list(hass, entry, key, new)
    return cast(ServiceResponse, {"target": target, "old": old, "new": new})


def async_register_services(hass: HomeAssistant) -> None:
    """Register the domain-global on-demand query actions (idempotent)."""
    if hass.services.has_service(DOMAIN, SERVICE_GET_ALERTS):
        return

    async def _get_alerts(call: ServiceCall) -> ServiceResponse:
        return await _handle_get_alerts(hass, call)

    async def _get_rogue_aps(call: ServiceCall) -> ServiceResponse:
        return await _handle_get_rogue_aps(hass, call)

    async def _clear_rogue_history(call: ServiceCall) -> ServiceResponse:
        return await _handle_clear_rogue_history(hass, call)

    async def _add_rogue_ignore(call: ServiceCall) -> ServiceResponse:
        return await _handle_add_rogue_ignore(hass, call)

    async def _remove_rogue_ignore(call: ServiceCall) -> ServiceResponse:
        return await _handle_remove_rogue_ignore(hass, call)

    async def _set_rogue_ignore(call: ServiceCall) -> ServiceResponse:
        return await _handle_set_rogue_ignore(hass, call)

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
    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_ROGUE_HISTORY,
        _clear_rogue_history,
        schema=CLEAR_ROGUE_HISTORY_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_ROGUE_IGNORE,
        _add_rogue_ignore,
        schema=ADD_REMOVE_ROGUE_IGNORE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_ROGUE_IGNORE,
        _remove_rogue_ignore,
        schema=ADD_REMOVE_ROGUE_IGNORE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_ROGUE_IGNORE,
        _set_rogue_ignore,
        schema=SET_ROGUE_IGNORE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
