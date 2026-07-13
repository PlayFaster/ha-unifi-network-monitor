"""Select platform for UniFi Network Monitor — rogue-AP detection period."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_ROGUE_PERIOD,
    DEFAULT_ROGUE_PERIOD,
    EP_ROGUE,
    ROGUE_PERIOD_HOURS,
)
from .coordinator import UnifiNetworkDataUpdateCoordinator, disabled_endpoints
from .helpers import build_sub_device_info

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the select platform (Security sub-device rogue period)."""
    coordinator: UnifiNetworkDataUpdateCoordinator = entry.runtime_data
    if EP_ROGUE not in disabled_endpoints(entry.options):
        async_add_entities([UnifiRoguePeriodSelect(coordinator, entry)])


class UnifiRoguePeriodSelect(
    CoordinatorEntity[UnifiNetworkDataUpdateCoordinator],
    SelectEntity,
):
    """Select the look-back window used when fetching rogue APs."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "rogue_period"
    _attr_options = list(ROGUE_PERIOD_HOURS)

    def __init__(
        self,
        coordinator: UnifiNetworkDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.unique_id}_rogue_period"

    @property
    def current_option(self) -> str:
        """Return the stored period (defaulting when unset/invalid)."""
        value = self._entry.options.get(CONF_ROGUE_PERIOD, DEFAULT_ROGUE_PERIOD)
        return value if value in ROGUE_PERIOD_HOURS else DEFAULT_ROGUE_PERIOD

    @property
    def available(self) -> bool:
        """Unavailable when the rogue AP endpoint has gone stale."""
        if not super().available:
            return False
        return self.coordinator.endpoint_available(EP_ROGUE)

    @property
    def device_info(self) -> DeviceInfo:
        """Return Security sub-device info."""
        return build_sub_device_info(self.coordinator, self._entry, "security")

    async def async_select_option(self, option: str) -> None:
        """Persist the new period and re-fetch with the new window."""
        if option not in ROGUE_PERIOD_HOURS:
            return
        new_options = {**self._entry.options, CONF_ROGUE_PERIOD: option}
        self.hass.config_entries.async_update_entry(self._entry, options=new_options)
        self.async_write_ha_state()
        # Explicit user action: re-fetch with the new window even if paused.
        await self.coordinator.async_force_refresh()
