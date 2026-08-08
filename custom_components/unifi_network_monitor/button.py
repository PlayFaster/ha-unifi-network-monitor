"""Button platform for UniFi Network Monitor."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import UnifiError
from .cleanup import apply_cleanup, plan_device_cleanup
from .const import (
    CONF_ENABLE_SPEEDTEST,
    DEFAULT_ENABLE_SPEEDTEST,
    DOMAIN,
    dual_wan_enabled,
)
from .coordinator import UnifiNetworkDataUpdateCoordinator
from .helpers import UnifiAboutEntity, build_sub_device_info

PARALLEL_UPDATES = 0

_REFRESH_DESCRIPTION = ButtonEntityDescription(
    key="refresh",
    translation_key="gateway_refresh",
    entity_category=EntityCategory.CONFIG,
)

_WAN1_SPEEDTEST_DESCRIPTION = ButtonEntityDescription(
    key="wan1_speedtest",
    translation_key="gateway_wan1_speedtest",
    entity_category=None,
)

_WAN2_SPEEDTEST_DESCRIPTION = ButtonEntityDescription(
    key="wan2_speedtest",
    translation_key="gateway_wan2_speedtest",
    entity_category=None,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the button platform."""
    coordinator: UnifiNetworkDataUpdateCoordinator = entry.runtime_data
    buttons: list[ButtonEntity] = [
        UnifiRefreshButton(coordinator, entry),
        UnifiCleanupButton(coordinator, entry),
    ]
    if entry.options.get(CONF_ENABLE_SPEEDTEST, DEFAULT_ENABLE_SPEEDTEST):
        buttons.append(
            UnifiSpeedtestButton(
                coordinator, entry, _WAN1_SPEEDTEST_DESCRIPTION, "wan1"
            )
        )
        if dual_wan_enabled(entry.options):
            buttons.append(
                UnifiSpeedtestButton(
                    coordinator, entry, _WAN2_SPEEDTEST_DESCRIPTION, "wan2"
                )
            )
    async_add_entities(buttons)


class UnifiRefreshButton(
    UnifiAboutEntity,
    CoordinatorEntity[UnifiNetworkDataUpdateCoordinator],
    ButtonEntity,
):
    """Button that triggers an immediate coordinator refresh."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    entity_description = _REFRESH_DESCRIPTION
    _attr_about = "Forces an immediate poll, even while Pause Polling is on."

    def __init__(
        self,
        coordinator: UnifiNetworkDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.unique_id}_refresh"

    async def async_press(self) -> None:
        """Trigger an immediate data refresh (overrides Pause Polling).

        Raises rather than returning quietly on failure, so an automation or
        script pressing this button can tell that it did not work. The
        debounced ``async_force_refresh`` cannot support that - it may return
        before the fetch has run - so the non-debounced variant is used and its
        outcome read from ``last_update_success``.
        """
        await self.coordinator.async_force_refresh_now()
        if not self.coordinator.last_update_success:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="refresh_failed",
            )

    @property
    def device_info(self) -> DeviceInfo:
        """Return system device info."""
        return build_sub_device_info(self.coordinator, self._entry, "system")


class UnifiCleanupButton(
    CoordinatorEntity[UnifiNetworkDataUpdateCoordinator],
    ButtonEntity,
):
    """Commit-only button that removes unused per-UniFi-device entities/devices."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "cleanup_unused_entities"

    def __init__(
        self,
        coordinator: UnifiNetworkDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.unique_id}_cleanup_unused_entities"

    async def async_press(self) -> None:
        """Remove per-device entities the current device mode no longer wants."""
        plan = plan_device_cleanup(self.hass, self._entry, self.coordinator)
        if plan.is_empty:
            return
        apply_cleanup(self.hass, self._entry, plan)
        # Reload out-of-band so we don't await our own teardown.
        self.hass.async_create_task(
            self.hass.config_entries.async_reload(self._entry.entry_id)
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return system device info."""
        return build_sub_device_info(self.coordinator, self._entry, "system")


class UnifiSpeedtestButton(
    UnifiAboutEntity,
    CoordinatorEntity[UnifiNetworkDataUpdateCoordinator],
    ButtonEntity,
):
    """Button that triggers a gateway speedtest on a specific WAN interface."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_about = (
        "Press to run an immediate speedtest on this WAN. Takes ~1 minute; "
        "results refresh shortly after."
    )

    def __init__(
        self,
        coordinator: UnifiNetworkDataUpdateCoordinator,
        entry: ConfigEntry,
        description: ButtonEntityDescription,
        interface_key: str,  # "wan1" or "wan2"
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._interface_key = interface_key
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"

    async def async_press(self) -> None:
        """Trigger a speedtest."""
        gateway_data = (self.coordinator.data or {}).get("gateway") or {}
        ifname = gateway_data.get(f"{self._interface_key}_ifname")
        try:
            await self.coordinator.async_trigger_speedtest(ifname)
        except UnifiError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="speedtest_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        # The test runs on the gateway (~<1 min); poll once shortly after so the
        # result shows without waiting for a possibly-distant scheduled poll.
        # The helper self-guards on pause/interval.
        self.coordinator.async_schedule_refresh_in(75)

    @property
    def device_info(self) -> DeviceInfo:
        """Return internet device info."""
        return build_sub_device_info(self.coordinator, self._entry, "speedtest")
