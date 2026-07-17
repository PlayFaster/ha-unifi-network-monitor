"""Diagnostics support for UniFi Network Monitor."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .coordinator import UnifiNetworkDataUpdateCoordinator

TO_REDACT = {
    "api_key",
    "password",
    "username",
    "host",
    "wan_isp_name",
    "wan_isp_org",
    "mac",
    "wan1_local_ip",
    "wan1_public_ip",
    "wan2_local_ip",
    "wan2_public_ip",
    "bssid",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: UnifiNetworkDataUpdateCoordinator = entry.runtime_data

    # Emit history as a list of records (not a BSSID-keyed dict) so the ``bssid``
    # entry in TO_REDACT masks the MAC — async_redact_data redacts values, not keys.
    rogue_history = [
        {"bssid": bssid, **rec} for bssid, rec in coordinator.rogue_history.items()
    ]

    return {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        },
        "rogue_history": async_redact_data(rogue_history, TO_REDACT),
        "coordinator": {
            "consecutive_failures": coordinator.consecutive_failures,
            "last_update_success": coordinator.last_update_success,
            "last_update_success_time": (
                coordinator.last_update_success_time.isoformat()
                if coordinator.last_update_success_time
                else None
            ),
            "data_available": coordinator.data is not None,
            "gateway_mac": async_redact_data(
                {"mac": coordinator.gateway_mac}, TO_REDACT
            ).get("mac"),
            "gateway_model": coordinator.gateway_model,
            "sw_version": coordinator.sw_version,
        },
        "data": async_redact_data(coordinator.data or {}, TO_REDACT),
    }
