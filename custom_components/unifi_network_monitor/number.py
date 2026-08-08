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
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfTime,
)
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
    EP_NETWORKCONF,
    EP_ROGUE,
    dual_wan_enabled,
)
from .coordinator import UnifiNetworkDataUpdateCoordinator, disabled_endpoints
from .helpers import UnifiAboutEntity, build_sub_device_info

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
    native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
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
    ]
    # The load-balance control is meaningless with a single WAN.
    if dual_wan_enabled(entry.options):
        numbers.append(WanLoadBalanceNumber(coordinator, entry))
    # The proximity threshold only makes sense alongside the rogue-AP alert.
    if EP_ROGUE not in disabled_endpoints(entry.options):
        numbers.append(
            UnifiRogueProximityThresholdNumber(coordinator, entry, initial_threshold)
        )
    async_add_entities(numbers)


class _DebouncedWriteEntity:
    """A slider write buffered for two seconds, and **flushed** on removal.

    Both controls here debounce: a drag produces a stream of values and only the
    last one is worth writing. The subtlety is what happens when the entity goes
    away mid-window. Cancelling the buffer — which is what both did — discards
    the write silently: the UI shows the new number, the controller never hears
    about it, and nothing reports the discrepancy. **A reload is enough to
    trigger it, and an options change is enough to trigger a reload**, so this is
    an ordinary sequence rather than an edge case.

    So removal flushes instead. ``_pending_value`` is cleared the moment the
    apply starts, which is what makes the flush conditional: a value still
    pending has not been written and must be; a value already cleared is in
    flight and must not be started twice.
    """

    hass: HomeAssistant
    _error_message = "Failed to apply the pending change: %s"

    def __init__(self) -> None:
        """Initialize the debounce state."""
        self._debounce_task: asyncio.Task[None] | None = None
        self._pending_value: float | None = None

    async def _apply(self, value: float) -> None:
        """Perform the write. Implemented per entity."""
        raise NotImplementedError

    def _schedule_debounced_apply(self, value: float) -> None:
        """Replace any buffered write with this one."""
        if self._debounce_task:
            self._debounce_task.cancel()
        self._pending_value = value
        self._debounce_task = self.hass.async_create_task(
            self._apply_after_debounce(value)
        )

    async def _apply_after_debounce(self, value: float) -> None:
        """Apply the value 2 s after the last change.

        Runs as a detached task, so a failure here cannot propagate to the
        setter's caller — it is logged instead.
        """
        try:
            await asyncio.sleep(2)
            self._pending_value = None
            await self._apply(value)
        except asyncio.CancelledError:
            pass
        except (UnifiError, ValueError, HomeAssistantError) as err:
            _LOGGER.error(self._error_message, err)

    async def async_will_remove_from_hass(self) -> None:
        """Flush a buffered write rather than dropping it."""
        pending = self._pending_value
        if self._debounce_task and not self._debounce_task.done():
            self._debounce_task.cancel()
        if pending is None:
            return
        self._pending_value = None
        try:
            await self._apply(pending)
        except (UnifiError, ValueError, HomeAssistantError) as err:
            _LOGGER.error(self._error_message, err)


class UnifiScanIntervalNumber(
    _DebouncedWriteEntity,
    CoordinatorEntity[UnifiNetworkDataUpdateCoordinator],
    NumberEntity,
):
    """Number entity for adjusting the polling interval."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    entity_description = _SCAN_INTERVAL_DESCRIPTION
    _error_message = "Failed to apply new scan interval: %s"

    def __init__(
        self,
        coordinator: UnifiNetworkDataUpdateCoordinator,
        entry: ConfigEntry,
        initial_value: float,
    ) -> None:
        """Initialize."""
        CoordinatorEntity.__init__(self, coordinator)
        _DebouncedWriteEntity.__init__(self)
        self._entry = entry
        self._attr_unique_id = f"{entry.unique_id}_scan_interval"
        self._attr_native_value = initial_value

    async def async_set_native_value(self, value: float) -> None:
        """Handle slider change with debounce."""
        self._attr_native_value = value
        self.async_write_ha_state()
        self._schedule_debounced_apply(value)

    async def _apply(self, value: float) -> None:
        """Persist the new polling interval and re-poll at the new rate."""
        val_int = int(value)
        self.coordinator.update_interval = timedelta(seconds=val_int)
        new_options = {**self._entry.options, CONF_SCAN_INTERVAL: val_int}
        self.hass.config_entries.async_update_entry(self._entry, options=new_options)
        await self.coordinator.async_force_refresh()

    @property
    def device_info(self) -> DeviceInfo:
        """Return system device info."""
        return build_sub_device_info(self.coordinator, self._entry, "system")


class WanLoadBalanceNumber(
    _DebouncedWriteEntity,
    UnifiAboutEntity,
    CoordinatorEntity[UnifiNetworkDataUpdateCoordinator],
    NumberEntity,
):
    """Controls WAN1 load balance weight; WAN2 is always set to 100 - WAN1."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_mode = NumberMode.BOX
    entity_description = _WAN_LOAD_BALANCE_DESCRIPTION
    _attr_about = (
        "WAN1's share of load-balanced traffic; WAN2 automatically gets the "
        "remainder (both sum to 100)."
    )
    _error_message = "Failed to set WAN load balance weight: %s"

    def __init__(
        self,
        coordinator: UnifiNetworkDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        CoordinatorEntity.__init__(self, coordinator)
        _DebouncedWriteEntity.__init__(self)
        self._entry = entry
        self._attr_unique_id = f"{entry.unique_id}_wan1_load_balance_weight"

    @property
    def device_info(self) -> DeviceInfo:
        """Return system device info."""
        return build_sub_device_info(self.coordinator, self._entry, "system")

    @property
    def available(self) -> bool:
        """Unavailable when the network-config endpoint has gone stale.

        ``networkconf`` is a degradable endpoint, and this entity both reads and
        writes it — so it must carry the same ``source`` gate the switch and
        select platforms do, rather than offering a control fed by data that is
        no longer arriving.
        """
        if not super().available:
            return False
        return self.coordinator.endpoint_available(EP_NETWORKCONF)

    @property
    def native_value(self) -> float | None:
        """Return current WAN1 weight from coordinator data."""
        if not self.coordinator.data:
            return None
        val = self.coordinator.data.get("gateway", {}).get("wan1_weight")
        return float(val) if val is not None else None

    async def async_set_native_value(self, value: float) -> None:
        """Buffer rapid increments; apply 2 s after the last change."""
        if not self.coordinator.wan_weights_writable or not (
            self.coordinator.endpoint_available(EP_NETWORKCONF)
        ):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="wan_config_not_loaded",
            )
        self._attr_native_value = value
        self.async_write_ha_state()
        self._schedule_debounced_apply(value)

    async def _apply(self, value: float) -> None:
        """Write the weight pair and report the outcome.

        The three write outcomes are logged distinctly. **Unverified is not an
        error**: the pair was sent and only the read-back failed, so logging it
        at error level would send the user chasing a change that most likely
        applied. Cancellation is safe here — the coordinator shields the pair,
        so a cancel can never leave WAN1 and WAN2 disagreeing.
        """
        weight = int(value)
        outcome = await self.coordinator.async_set_wan_weights(weight)
        if outcome == "failed":
            _LOGGER.error(
                "WAN load balance weight %s was rejected by the controller", weight
            )
        elif outcome == "unverified":
            _LOGGER.warning(
                "WAN load balance weight %s was sent but could not be confirmed",
                weight,
            )


class UnifiRogueProximityThresholdNumber(
    UnifiAboutEntity,
    CoordinatorEntity[UnifiNetworkDataUpdateCoordinator],
    NumberEntity,
):
    """Number entity for the rogue-AP proximity alert RSSI threshold (dBm)."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    entity_description = _ROGUE_PROXIMITY_THRESHOLD_DESCRIPTION
    _attr_about = (
        "Signal cutoff (dBm) for 'nearby'. Always negative; closer to 0 = "
        "stronger/closer. Feeds the Rogue AP Proximity Alert."
    )

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
        # Nudge the coordinator so the proximity binary sensor recomputes promptly
        # (explicit user action: applies even if polling is paused).
        await self.coordinator.async_force_refresh()

    @property
    def device_info(self) -> DeviceInfo:
        """Return Security sub-device info."""
        return build_sub_device_info(self.coordinator, self._entry, "security")
