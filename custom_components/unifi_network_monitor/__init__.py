"""The UniFi Network Monitor integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import UnifiError, UnifiNetworkAPI
from .cleanup import apply_cleanup, plan_device_cleanup
from .const import (
    CONF_API_KEY,
    CONF_ROGUE_PROXIMITY_RSSI_THRESHOLD,
    CONF_SCAN_INTERVAL,
    CONF_SITE,
    CONF_STOP_POLLING,
    DEFAULT_SITE,
    DOMAIN,
)
from .coordinator import UnifiNetworkDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

SERVICE_CLEANUP = "cleanup_unused_entities"
CLEANUP_SCHEMA = vol.Schema({vol.Optional("dry_run", default=True): cv.boolean})

# Options changed live by control entities — updating these must NOT reload the
# entry (the controls apply them directly). Any other option change reloads so
# the setup/feature toggles take effect immediately on submit.
_LIVE_OPTION_KEYS = frozenset(
    {CONF_SCAN_INTERVAL, CONF_ROGUE_PROXIMITY_RSSI_THRESHOLD, CONF_STOP_POLLING}
)


def _reload_signature(options: Any) -> dict[str, Any]:
    """Options subset whose change requires a reload."""
    return {k: v for k, v in options.items() if k not in _LIVE_OPTION_KEYS}


async def _async_reload_on_settings_change(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Reload the entry when reconfigure/options change reload-worthy settings."""
    coordinator: UnifiNetworkDataUpdateCoordinator = entry.runtime_data
    signature = _reload_signature(entry.options)
    if signature != coordinator.reload_signature:
        coordinator.reload_signature = signature
        await hass.config_entries.async_reload(entry.entry_id)


PLATFORMS = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SWITCH,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the UniFi Network Monitor domain and register services."""

    async def _handle_cleanup(call: ServiceCall) -> dict[str, Any]:
        """Report (dry-run) or remove per-device entities no longer wanted."""
        dry_run: bool = call.data["dry_run"]
        report: dict[str, Any] = {}
        for entry in hass.config_entries.async_entries(DOMAIN):
            coordinator = getattr(entry, "runtime_data", None)
            if coordinator is None:
                continue
            plan = plan_device_cleanup(hass, entry, coordinator)
            report[entry.title] = {
                "entities": plan.entity_ids,
                "devices": plan.device_ids,
            }
            if not dry_run and not plan.is_empty:
                apply_cleanup(hass, entry, plan)
                hass.async_create_task(hass.config_entries.async_reload(entry.entry_id))
        return {"dry_run": dry_run, "entries": report}

    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEANUP,
        _handle_cleanup,
        schema=CLEANUP_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    return True


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    device_entry: dr.DeviceEntry,
) -> bool:
    """Allow deleting a device only once Monitor has no entities on it."""
    ent_reg = er.async_get(hass)
    for entity in er.async_entries_for_device(
        ent_reg, device_entry.id, include_disabled_entities=True
    ):
        if entity.config_entry_id == config_entry.entry_id:
            return False
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up UniFi Network Monitor from a config entry."""
    session = async_get_clientsession(hass)
    options = entry.options

    api = UnifiNetworkAPI(
        session,
        options.get(CONF_HOST, ""),
        api_key=(options.get(CONF_API_KEY) or "").strip() or None,
        username=(options.get("username") or "").strip() or None,
        password=(options.get("password") or "").strip() or None,
        site=options.get(CONF_SITE, DEFAULT_SITE),
    )

    coordinator = UnifiNetworkDataUpdateCoordinator(hass, entry, api)
    entry.runtime_data = coordinator
    coordinator.reload_signature = _reload_signature(entry.options)
    entry.async_on_unload(entry.add_update_listener(_async_reload_on_settings_change))

    # Register the gateway root device early so via_device links work when
    # platforms forward their sub-devices (Standard 3 — Early Root Registration)
    mac = coordinator.gateway_mac
    if mac:
        device_registry = dr.async_get(hass)
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            connections={(dr.CONNECTION_NETWORK_MAC, mac)},
            identifiers={(DOMAIN, mac)},
            name=f"{entry.title} Gateway",
            manufacturer="Ubiquiti",
            model=coordinator.gateway_model,
            sw_version=coordinator.sw_version,
            configuration_url=f"https://{options.get(CONF_HOST, '')}",
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def _background_setup() -> None:
        try:
            await coordinator.async_refresh()
            _LOGGER.info("%s: Background initialization complete.", entry.title)
        except UnifiError as err:
            _LOGGER.warning(
                "%s: Background initialization failed (will retry): %s",
                entry.title,
                err,
            )

    entry.async_create_background_task(hass, _background_setup(), "unifi-nm-setup")

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator: UnifiNetworkDataUpdateCoordinator = entry.runtime_data
    try:
        await coordinator.api.logout()
    except UnifiError as err:
        _LOGGER.debug("%s: Logout failed (non-fatal): %s", entry.title, err)

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
