"""Number platform for UniFi Network Monitor — scan interval control."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import UnifiError
from .const import (
    CONF_ROGUE_PROXIMITY_RSSI_THRESHOLD,
    CONF_SCAN_INTERVAL,
    DEFAULT_ROGUE_PROXIMITY_RSSI_THRESHOLD,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EP_ROGUE,
)
from .coordinator import UnifiNetworkDataUpdateCoordinator, disabled_endpoints
from .helpers import build_sub_device_info

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

_WAN_LOAD_BALANCE_DESCRIPTION = NumberEntityDescription(
    key="wan1_load_balance_weight",
    translation_key="wan1_load_balance_weight",
    native_min_value=0,
    native_max_value=100,
    native_step=1,
    native_unit_of_measurement=PERCENTAGE,
    entity_category=EntityCategory.CONFIG,
)

_SCAN_INTERVAL_DESCRIPTION = NumberEntityDescription(
    key="scan_interval",
    translation_key="gateway_scan_interval",
    native_min_value=10,
    native_max_value=3600,
    native_step=10,
    native_unit_of_measurement=UnitOfTime.SECONDS,
    entity_category=EntityCategory.CONFIG,
)

_ROGUE_PROXIMITY_THRESHOLD_DESCRIPTION = NumberEntityDescription(
    key="rogue_proximity_rssi_threshold",
    translation_key="gateway_rogue_proximity_threshold",
    native_min_value=-100,
    native_max_value=-30,
    native_step=1,
    native_unit_of_measurement="dBm",
    mode=NumberMode.BOX,
    entity_category=EntityCategory.CONFIG,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the number platform."""
    coordinator: UnifiNetworkDataUpdateCoordinator = entry.runtime_data
    initial = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    initial_threshold = entry.options.get(
        CONF_ROGUE_PROXIMITY_RSSI_THRESHOLD, DEFAULT_ROGUE_PROXIMITY_RSSI_THRESHOLD
    )
    numbers: list[NumberEntity] = [
        UnifiScanIntervalNumber(coordinator, entry, initial),
        WanLoadBalanceNumber(coordinator, entry),
    ]
    # The proximity threshold only makes sense alongside the rogue-AP alert.
    if EP_ROGUE not in disabled_endpoints(entry.options):
        numbers.append(
            UnifiRogueProximityThresholdNumber(coordinator, entry, initial_threshold)
        )
    async_add_entities(numbers)


class UnifiScanIntervalNumber(
    CoordinatorEntity[UnifiNetworkDataUpdateCoordinator],
    NumberEntity,
):
    """Number entity for adjusting the polling interval."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    entity_description = _SCAN_INTERVAL_DESCRIPTION

    def __init__(
        self,
        coordinator: UnifiNetworkDataUpdateCoordinator,
        entry: ConfigEntry,
        initial_value: float,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.unique_id}_scan_interval"
        self._attr_native_value = initial_value
        self._debounce_task: asyncio.Task[None] | None = None

    async def async_will_remove_from_hass(self) -> None:
        """Cancel pending debounce on removal."""
        if self._debounce_task and not self._debounce_task.done():
            self._debounce_task.cancel()

    async def async_set_native_value(self, value: float) -> None:
        """Handle slider change with debounce."""
        self._attr_native_value = value
        self.async_write_ha_state()
        if self._debounce_task:
            self._debounce_task.cancel()
        self._debounce_task = self.hass.async_create_task(
            self._apply_after_debounce(value)
        )

    async def _apply_after_debounce(self, value: float) -> None:
        """Apply new interval 2 s after last slider move."""
        try:
            await asyncio.sleep(2)
            val_int = int(value)
            self.coordinator.update_interval = timedelta(seconds=val_int)
            new_options = {**self._entry.options, CONF_SCAN_INTERVAL: val_int}
            self.hass.config_entries.async_update_entry(
                self._entry, options=new_options
            )
            await self.coordinator.async_request_refresh()
        except asyncio.CancelledError:
            pass
        except (UnifiError, ValueError, HomeAssistantError) as err:
            _LOGGER.error("Failed to apply new scan interval: %s", err)

    @property
    def device_info(self) -> DeviceInfo:
        """Return system device info."""
        return build_sub_device_info(self.coordinator, self._entry, "system")


class WanLoadBalanceNumber(
    CoordinatorEntity[UnifiNetworkDataUpdateCoordinator],
    NumberEntity,
):
    """Controls WAN1 load balance weight; WAN2 is always set to 100 - WAN1."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_mode = NumberMode.BOX
    entity_description = _WAN_LOAD_BALANCE_DESCRIPTION

    def __init__(
        self,
        coordinator: UnifiNetworkDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.unique_id}_wan1_load_balance_weight"
        self._debounce_task: asyncio.Task[None] | None = None

    async def async_will_remove_from_hass(self) -> None:
        """Cancel pending debounce on removal."""
        if self._debounce_task and not self._debounce_task.done():
            self._debounce_task.cancel()

    @property
    def device_info(self) -> DeviceInfo:
        """Return system device info."""
        return build_sub_device_info(self.coordinator, self._entry, "system")

    @property
    def native_value(self) -> float | None:
        """Return current WAN1 weight from coordinator data."""
        if not self.coordinator.data:
            return None
        val = self.coordinator.data.get("gateway", {}).get("wan1_weight")
        return float(val) if val is not None else None

    async def async_set_native_value(self, value: float) -> None:
        """Buffer rapid increments; apply 2 s after the last change."""
        if not self.coordinator.wan_weights_writable:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="wan_config_not_loaded",
            )
        self._attr_native_value = value
        self.async_write_ha_state()
        if self._debounce_task:
            self._debounce_task.cancel()
        self._debounce_task = self.hass.async_create_task(
            self._apply_after_debounce(int(value))
        )

    async def _apply_after_debounce(self, value: int) -> None:
        """Apply the weight change after 2 s of inactivity.

        Runs as a detached task, so a failure here cannot propagate to the
        setter's caller — it is logged. The common "config not loaded" case is
        rejected up front in ``async_set_native_value`` where it can raise.
        """
        try:
            await asyncio.sleep(2)
            await self.coordinator.async_set_wan_weights(value)
        except asyncio.CancelledError:
            pass
        except (UnifiError, ValueError) as err:
            _LOGGER.error("Failed to set WAN load balance weight: %s", err)


class UnifiRogueProximityThresholdNumber(
    CoordinatorEntity[UnifiNetworkDataUpdateCoordinator],
    NumberEntity,
):
    """Number entity for the rogue-AP proximity alert RSSI threshold (dBm)."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    entity_description = _ROGUE_PROXIMITY_THRESHOLD_DESCRIPTION

    def __init__(
        self,
        coordinator: UnifiNetworkDataUpdateCoordinator,
        entry: ConfigEntry,
        initial_value: float,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.unique_id}_rogue_proximity_rssi_threshold"
        self._attr_native_value = initial_value

    async def async_set_native_value(self, value: float) -> None:
        """Persist the new threshold and re-evaluate the proximity alert."""
        val_int = int(value)
        self._attr_native_value = val_int
        self.async_write_ha_state()
        new_options = {
            **self._entry.options,
            CONF_ROGUE_PROXIMITY_RSSI_THRESHOLD: val_int,
        }
        self.hass.config_entries.async_update_entry(self._entry, options=new_options)
        # Nudge the coordinator so the proximity binary sensor recomputes promptly.
        await self.coordinator.async_request_refresh()

    @property
    def device_info(self) -> DeviceInfo:
        """Return Status sub-device info."""
        return build_sub_device_info(self.coordinator, self._entry, "status")
