"""Switch platform for UniFi Network Monitor."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, cast

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_ROGUE_APPLY_AP_IGNORE,
    CONF_ROGUE_SHOW_5GHZ,
    CONF_ROGUE_SHOW_24GHZ,
    CONF_STOP_POLLING,
    DEFAULT_ROGUE_APPLY_AP_IGNORE,
    DEFAULT_ROGUE_SHOW_5GHZ,
    DEFAULT_ROGUE_SHOW_24GHZ,
    EP_ROGUE,
)
from .coordinator import UnifiNetworkDataUpdateCoordinator, disabled_endpoints
from .helpers import build_sub_device_info

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

_PAUSE_POLLING_DESCRIPTION = SwitchEntityDescription(
    key="pause_polling",
    translation_key="pause_polling",
    entity_category=EntityCategory.CONFIG,
)


@dataclass(frozen=True, kw_only=True)
class RogueSwitchDescription(SwitchEntityDescription):
    """A Security-sub-device switch backed by a config-entry option."""

    option_key: str
    option_default: bool


_ROGUE_SWITCHES: tuple[RogueSwitchDescription, ...] = (
    RogueSwitchDescription(
        key="rogue_show_24ghz",
        translation_key="rogue_show_24ghz",
        entity_category=EntityCategory.CONFIG,
        option_key=CONF_ROGUE_SHOW_24GHZ,
        option_default=DEFAULT_ROGUE_SHOW_24GHZ,
    ),
    RogueSwitchDescription(
        key="rogue_show_5ghz",
        translation_key="rogue_show_5ghz",
        entity_category=EntityCategory.CONFIG,
        option_key=CONF_ROGUE_SHOW_5GHZ,
        option_default=DEFAULT_ROGUE_SHOW_5GHZ,
    ),
    RogueSwitchDescription(
        key="rogue_apply_ap_ignore",
        translation_key="rogue_apply_ap_ignore",
        entity_category=EntityCategory.CONFIG,
        option_key=CONF_ROGUE_APPLY_AP_IGNORE,
        option_default=DEFAULT_ROGUE_APPLY_AP_IGNORE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switch platform."""
    coordinator: UnifiNetworkDataUpdateCoordinator = entry.runtime_data
    entities: list[SwitchEntity] = [UnifiPausePollingSwitch(coordinator, entry)]

    # Rogue control switches live on the Security sub-device; only created when
    # security monitoring is on (EP_ROGUE not disabled).
    if EP_ROGUE not in disabled_endpoints(entry.options):
        entities.extend(
            UnifiRogueControlSwitch(coordinator, entry, desc)
            for desc in _ROGUE_SWITCHES
        )

    async_add_entities(entities)


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


class UnifiRogueControlSwitch(
    CoordinatorEntity[UnifiNetworkDataUpdateCoordinator],
    SwitchEntity,
):
    """Option-backed rogue-AP control switch on the Security sub-device.

    Applies live: writes its option and requests a coordinator refresh (the
    parse reads the option each poll). Its option key is a live key, so a
    change does not reload the entry.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False
    entity_description: RogueSwitchDescription

    def __init__(
        self,
        coordinator: UnifiNetworkDataUpdateCoordinator,
        entry: ConfigEntry,
        description: RogueSwitchDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"

    @property
    def is_on(self) -> bool:
        """Return the stored option value."""
        return cast(
            bool,
            self._entry.options.get(
                self.entity_description.option_key,
                self.entity_description.option_default,
            ),
        )

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

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the option."""
        await self._set_state(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the option."""
        await self._set_state(False)

    async def _set_state(self, state: bool) -> None:
        new_options = {
            **self._entry.options,
            self.entity_description.option_key: state,
        }
        self.hass.config_entries.async_update_entry(self._entry, options=new_options)
        self.async_write_ha_state()
        # Explicit user action: re-parse rogues with the new filter even if paused
        # (the band/ignore filters apply in the coordinator parse path).
        await self.coordinator.async_force_refresh()
