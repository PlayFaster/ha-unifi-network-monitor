"""Switch platform for UniFi Network Monitor."""

from __future__ import annotations

import logging
from typing import Any, cast

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_STOP_POLLING
from .coordinator import UnifiNetworkDataUpdateCoordinator
from .helpers import build_sub_device_info

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

_PAUSE_POLLING_DESCRIPTION = SwitchEntityDescription(
    key="pause_polling",
    translation_key="pause_polling",
    entity_category=EntityCategory.CONFIG,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switch platform."""
    coordinator: UnifiNetworkDataUpdateCoordinator = entry.runtime_data
    async_add_entities([UnifiPausePollingSwitch(coordinator, entry)])


class UnifiPausePollingSwitch(
    CoordinatorEntity[UnifiNetworkDataUpdateCoordinator],
    SwitchEntity,
):
    """Switch to pause/resume coordinator polling with persistence."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    entity_description = _PAUSE_POLLING_DESCRIPTION

    def __init__(
        self,
        coordinator: UnifiNetworkDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.unique_id}_pause_polling"

    @property
    def is_on(self) -> bool:
        """Return true if polling is paused."""
        return cast(bool, self._entry.options.get(CONF_STOP_POLLING, False))

    @property
    def device_info(self) -> DeviceInfo:
        """Return system device info."""
        return build_sub_device_info(self.coordinator, self._entry, "system")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Pause polling."""
        _LOGGER.debug("%s: Pausing polling", self._entry.title)
        await self._set_state(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Resume polling."""
        _LOGGER.debug("%s: Resuming polling", self._entry.title)
        await self._set_state(False)

    async def _set_state(self, state: bool) -> None:
        new_options = {**self._entry.options, CONF_STOP_POLLING: state}
        self.hass.config_entries.async_update_entry(self._entry, options=new_options)
        self.async_write_ha_state()
        if not state:
            await self.coordinator.async_request_refresh()
