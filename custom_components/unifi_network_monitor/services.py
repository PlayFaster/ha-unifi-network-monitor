"""On-demand alert-query action for UniFi Network Monitor.

Registers the ``get_alerts`` response service — a fresh, capped query of the
system log that fills the history gap the passive sensors can't. The service is
domain-global (registered once for the integration) and stays available
regardless of the Alerts feature toggle; it does no polling, so a user who hid
the passive Alerts card can still query on demand.
"""

from __future__ import annotations

import logging
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
    DOMAIN,
    SERVICE_GET_ALERTS,
)
from .coordinator import UnifiNetworkDataUpdateCoordinator

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
    }
)


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
) -> list[dict[str, Any]]:
    """Page the system log (newest-first) and collect matching alerts.

    Bounded to ALERT_MAX_PAGES; stops early on quantity reached, a short page
    (end of log), or — with an age cutoff — the first older-than-cutoff record.
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
            if keyword:
                haystack = f"{record['title']} {record['message']}".lower()
                if keyword not in haystack:
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

    cutoff_ms: int | None = None
    age_days = call.data.get("age_days")
    if age_days:
        cutoff_ms = int((dt_util.as_timestamp(dt_util.now()) - age_days * 86400) * 1000)

    alerts = await _fetch_alerts(coordinator, severities, quantity, cutoff_ms, keyword)
    return cast(ServiceResponse, {"count": len(alerts), "alerts": alerts})


def async_register_services(hass: HomeAssistant) -> None:
    """Register the domain-global alert-query action (idempotent)."""
    if hass.services.has_service(DOMAIN, SERVICE_GET_ALERTS):
        return

    async def _get_alerts(call: ServiceCall) -> ServiceResponse:
        return await _handle_get_alerts(hass, call)

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_ALERTS,
        _get_alerts,
        schema=GET_ALERTS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
