"""Binary sensor platform for UniFi Network Monitor."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import (
    CONF_ROGUE_PROXIMITY_RSSI_THRESHOLD,
    CONF_UNIFI_DEVICE_MODE,
    DEFAULT_ROGUE_PROXIMITY_RSSI_THRESHOLD,
    DEFAULT_UNIFI_DEVICE_MODE,
    DEVICE_MODE_ALL,
    EP_ROGUE,
    EP_SETTINGS,
    EP_VPN_TUNNELS,
    EP_WLAN,
    dual_wan_enabled,
    single_wan_excluded_keys,
)
from .coordinator import (
    UnifiNetworkDataUpdateCoordinator,
    disabled_endpoints,
)
from .helpers import (
    build_sub_device_info,
    build_unifi_device_info,
)

PARALLEL_UPDATES = 0

# Maps a binary sensor's key to the optional endpoint it depends on. A stale
# endpoint makes those sensors report "unavailable". Keys absent here come from
# the mandatory get_devices()/get_health() calls (global 3-strike).
_BINARY_ENDPOINT_BY_KEY: dict[str, str] = {
    "ad_blocking": EP_SETTINGS,
    "honeypot": EP_SETTINGS,
}


@dataclass(frozen=True, kw_only=True)
class UnifiBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Extends BinarySensorEntityDescription with value extraction."""

    value_fn: Callable[[dict[str, Any]], bool | None]
    device_key: str = "gateway"
    enable_in_standalone: bool = False


# ---------------------------------------------------------------------------
# Gateway binary sensors
# ---------------------------------------------------------------------------

GATEWAY_BINARY_SENSORS: Final[tuple[UnifiBinarySensorEntityDescription, ...]] = (
    UnifiBinarySensorEntityDescription(
        key="internet",
        translation_key="gateway_internet",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("internet"),
        device_key="internet",
    ),
    UnifiBinarySensorEntityDescription(
        key="update_available",
        translation_key="gateway_update_available",
        device_class=BinarySensorDeviceClass.UPDATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        enable_in_standalone=True,
        value_fn=lambda d: d.get("update_available"),
        device_key="gateway",
    ),
    UnifiBinarySensorEntityDescription(
        key="wan1_active",
        translation_key="gateway_wan1_active",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("wan1_active"),
        device_key="internet",
    ),
    UnifiBinarySensorEntityDescription(
        key="wan2_active",
        translation_key="gateway_wan2_active",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("wan2_active"),
        device_key="internet",
    ),
    UnifiBinarySensorEntityDescription(
        key="wan1_up",
        translation_key="gateway_wan1_up",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("wan1_up"),
        device_key="internet",
    ),
    UnifiBinarySensorEntityDescription(
        key="wan2_up",
        translation_key="gateway_wan2_up",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("wan2_up"),
        device_key="internet",
    ),
    UnifiBinarySensorEntityDescription(
        key="ad_blocking",
        translation_key="gateway_ad_blocking",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("ad_blocking"),
        device_key="security",
    ),
    UnifiBinarySensorEntityDescription(
        key="honeypot",
        translation_key="gateway_honeypot",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("honeypot"),
        device_key="security",
    ),
)

# ---------------------------------------------------------------------------
# Network health binary sensors
# ---------------------------------------------------------------------------

HEALTH_BINARY_SENSORS: Final[tuple[UnifiBinarySensorEntityDescription, ...]] = (
    UnifiBinarySensorEntityDescription(
        key="all_ok",
        translation_key="health_all_ok",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: (
            not (
                d.get("wan_status") == "ok"
                and d.get("www_status") == "ok"
                and d.get("wlan_status") == "ok"
                and d.get("lan_status") == "ok"
            )
        ),
        device_key="status",
    ),
    UnifiBinarySensorEntityDescription(
        key="wan_ok",
        translation_key="health_wan_ok",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.get("wan_status") == "ok",
        device_key="status",
    ),
    UnifiBinarySensorEntityDescription(
        key="www_ok",
        translation_key="health_www_ok",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.get("www_status") == "ok",
        device_key="internet",
    ),
    UnifiBinarySensorEntityDescription(
        key="wlan_ok",
        translation_key="health_wlan_ok",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.get("wlan_status") == "ok",
        device_key="status",
    ),
    UnifiBinarySensorEntityDescription(
        key="lan_ok",
        translation_key="health_lan_ok",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.get("lan_status") == "ok",
        device_key="status",
    ),
    UnifiBinarySensorEntityDescription(
        key="speedtest_pass",
        translation_key="health_speedtest_pass",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: (
            None
            if not d.get("www_speedtest_status")
            else d.get("www_speedtest_status") != "Success"
        ),
        device_key="speedtest",
    ),
)

# ---------------------------------------------------------------------------
# Per-device binary sensors
# ---------------------------------------------------------------------------

DEVICE_BINARY_SENSORS: Final[tuple[UnifiBinarySensorEntityDescription, ...]] = (
    UnifiBinarySensorEntityDescription(
        key="update_available",
        translation_key="gateway_update_available",
        device_class=BinarySensorDeviceClass.UPDATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.get("update_available"),
    ),
)


# ---------------------------------------------------------------------------
# Entity classes
# ---------------------------------------------------------------------------


def _dedup_suffix(base: str, used: set[str]) -> str:
    """Return a unique-id suffix, appending _2/_3… when ``base`` is already taken.

    Dynamic WiFi/VPN names are slugified for the entity id; two distinct names
    can slugify to the same value, so this guarantees a unique id per entity.
    The chosen suffix is recorded in ``used``.
    """
    suffix = base
    counter = 2
    while suffix in used:
        suffix = f"{base}_{counter}"
        counter += 1
    used.add(suffix)
    return suffix


class UnifiBinarySensorBase(
    CoordinatorEntity[UnifiNetworkDataUpdateCoordinator],
    BinarySensorEntity,
):
    """Base binary sensor."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    entity_description: UnifiBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: UnifiNetworkDataUpdateCoordinator,
        entry: ConfigEntry,
        description: UnifiBinarySensorEntityDescription,
        unique_id_suffix: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._attr_unique_id = f"{entry.unique_id}_{unique_id_suffix}"

    def _raw_data(self) -> dict[str, Any]:
        """Return the sub-dict relevant to this sensor."""
        raise NotImplementedError

    def _source_endpoint(self) -> str | None:
        """Return the optional endpoint this sensor depends on (None = mandatory)."""
        return _BINARY_ENDPOINT_BY_KEY.get(self.entity_description.key)

    @property
    def available(self) -> bool:
        """Unavailable when this sensor's source endpoint has gone stale."""
        if not super().available:
            return False
        return self.coordinator.endpoint_available(self._source_endpoint())

    @property
    def is_on(self) -> bool | None:
        """Return True/False/None based on value_fn."""
        return self.entity_description.value_fn(self._raw_data())


class UnifiGatewayBinarySensor(UnifiBinarySensorBase):
    """Binary sensor for the gateway device."""

    def __init__(
        self,
        coordinator: UnifiNetworkDataUpdateCoordinator,
        entry: ConfigEntry,
        description: UnifiBinarySensorEntityDescription,
        unique_id_suffix: str,
        standalone: bool = False,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, entry, description, unique_id_suffix)
        self._standalone = standalone

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Enable select gateway binary sensors in standalone mode."""
        if self._standalone and self.entity_description.enable_in_standalone:
            return True
        return self.entity_description.entity_registry_enabled_default

    @property
    def device_info(self) -> DeviceInfo:
        """Return gateway device info."""
        return build_sub_device_info(
            self.coordinator, self._entry, self.entity_description.device_key
        )

    def _raw_data(self) -> dict[str, Any]:
        if not self.coordinator.data:
            return {}
        return self.coordinator.data.get("gateway") or {}


class UnifiHealthBinarySensor(UnifiBinarySensorBase):
    """Binary sensor for the Network Health sub-device."""

    @property
    def device_info(self) -> DeviceInfo:
        """Return network device info."""
        return build_sub_device_info(
            self.coordinator, self._entry, self.entity_description.device_key
        )

    def _raw_data(self) -> dict[str, Any]:
        if not self.coordinator.data:
            return {}
        return self.coordinator.data.get("health") or {}


class UnifiDeviceBinarySensor(UnifiBinarySensorBase):
    """Binary sensor for a dynamic AP or switch."""

    def __init__(
        self,
        coordinator: UnifiNetworkDataUpdateCoordinator,
        entry: ConfigEntry,
        description: UnifiBinarySensorEntityDescription,
        device_mac: str,
        standalone: bool = False,
    ) -> None:
        """Initialize."""
        super().__init__(
            coordinator, entry, description, f"{device_mac}_{description.key}"
        )
        self._device_mac = device_mac
        self._standalone = standalone

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Enable all device binary sensors in standalone mode."""
        if self._standalone:
            return True
        return self.entity_description.entity_registry_enabled_default

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        devices = (self.coordinator.data or {}).get("devices", {})
        dev = devices.get(self._device_mac) or {}
        return build_unifi_device_info(
            self.coordinator,
            self._device_mac,
            dev.get("name", self._device_mac),
            dev.get("model", ""),
        )

    def _raw_data(self) -> dict[str, Any]:
        if not self.coordinator.data:
            return {}
        return self.coordinator.data.get("devices", {}).get(self._device_mac) or {}


class UnifiWifiBinarySensor(UnifiBinarySensorBase):
    """Binary sensor for an individual WiFi SSID broadcast state."""

    def __init__(
        self,
        coordinator: UnifiNetworkDataUpdateCoordinator,
        entry: ConfigEntry,
        ssid: str,
        unique_id_suffix: str | None = None,
    ) -> None:
        """Initialize."""
        suffix = unique_id_suffix or f"wifi_{slugify(ssid)}"
        description = UnifiBinarySensorEntityDescription(
            key=f"wifi_{ssid}",
            translation_key="gateway_wifi_ssid_status",
            device_class=BinarySensorDeviceClass.RUNNING,
            entity_category=EntityCategory.DIAGNOSTIC,
            value_fn=lambda d: d.get("wifi_states", {}).get(ssid),
            device_key="status",
        )
        super().__init__(coordinator, entry, description, suffix)
        self._ssid = ssid
        self._attr_name = f"{ssid} WiFi Status"

    def _raw_data(self) -> dict[str, Any]:
        if not self.coordinator.data:
            return {}
        return self.coordinator.data.get("gateway") or {}

    def _source_endpoint(self) -> str | None:
        return EP_WLAN

    @property
    def device_info(self) -> DeviceInfo:
        """Return Status sub-device info."""
        return build_sub_device_info(self.coordinator, self._entry, "status")


class UnifiRogueProximityBinarySensor(
    CoordinatorEntity[UnifiNetworkDataUpdateCoordinator],
    BinarySensorEntity,
):
    """Problem sensor: a rogue AP is close by (signal at/above the threshold)."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "gateway_rogue_proximity_alert"

    def __init__(
        self,
        coordinator: UnifiNetworkDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.unique_id}_rogue_proximity_alert"

    def _threshold(self) -> int:
        """Return the configured proximity RSSI threshold (dBm, negative)."""
        threshold: int = self._entry.options.get(
            CONF_ROGUE_PROXIMITY_RSSI_THRESHOLD,
            DEFAULT_ROGUE_PROXIMITY_RSSI_THRESHOLD,
        )
        return threshold

    @property
    def is_on(self) -> bool:
        """Return True when the strongest rogue signal is at/above the threshold."""
        if not self.coordinator.data:
            return False
        gw = self.coordinator.data.get("gateway") or {}
        rssi: int | None = gw.get("strongest_rogue_rssi")
        if rssi is None:
            return False
        return rssi >= self._threshold()

    @property
    def available(self) -> bool:
        """Unavailable when the rogue AP endpoint has gone stale."""
        if not super().available:
            return False
        return self.coordinator.endpoint_available(EP_ROGUE)

    @property
    def extra_state_attributes(self) -> dict[str, int | None]:
        """Expose the strongest rogue RSSI and the configured threshold."""
        gw = (self.coordinator.data or {}).get("gateway") or {}
        return {
            "strongest_rogue_rssi": gw.get("strongest_rogue_rssi"),
            "threshold": self._threshold(),
        }

    @property
    def device_info(self) -> DeviceInfo:
        """Return Security sub-device info."""
        return build_sub_device_info(self.coordinator, self._entry, "security")


class UnifiVpnBinarySensor(UnifiBinarySensorBase):
    """Binary sensor for an individual Site-to-Site VPN Tunnel status."""

    def __init__(
        self,
        coordinator: UnifiNetworkDataUpdateCoordinator,
        entry: ConfigEntry,
        tunnel_name: str,
        unique_id_suffix: str | None = None,
    ) -> None:
        """Initialize."""
        suffix = unique_id_suffix or f"vpn_{slugify(tunnel_name)}"
        description = UnifiBinarySensorEntityDescription(
            key=f"vpn_{tunnel_name}",
            translation_key="gateway_vpn_tunnel_status",
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
            entity_category=EntityCategory.DIAGNOSTIC,
            value_fn=lambda d: d.get("vpn_states", {}).get(tunnel_name),
            device_key="status",
        )
        super().__init__(coordinator, entry, description, suffix)
        self._tunnel_name = tunnel_name
        self._attr_name = f"{tunnel_name} VPN Tunnel Status"

    def _raw_data(self) -> dict[str, Any]:
        if not self.coordinator.data:
            return {}
        return self.coordinator.data.get("gateway") or {}

    def _source_endpoint(self) -> str | None:
        return EP_VPN_TUNNELS

    @property
    def device_info(self) -> DeviceInfo:
        """Return Status sub-device info."""
        return build_sub_device_info(self.coordinator, self._entry, "status")


# ---------------------------------------------------------------------------
# Platform setup
# ---------------------------------------------------------------------------


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensor entities."""
    coordinator: UnifiNetworkDataUpdateCoordinator = entry.runtime_data
    standalone = "unifi" not in hass.config_entries.async_domains()
    # Per-physical-device binary sensors duplicate core; only the "all" mode
    # creates them. WiFi/VPN sensors below are gateway-level, not gated here.
    want_device = (
        entry.options.get(CONF_UNIFI_DEVICE_MODE, DEFAULT_UNIFI_DEVICE_MODE)
        == DEVICE_MODE_ALL
    )
    disabled_eps = disabled_endpoints(entry.options)
    excluded = (
        set() if dual_wan_enabled(entry.options) else single_wan_excluded_keys()
    )

    entities: list[BinarySensorEntity] = []

    entities.extend(
        UnifiGatewayBinarySensor(coordinator, entry, desc, desc.key, standalone)
        for desc in GATEWAY_BINARY_SENSORS
        if desc.key not in excluded
    )
    entities.extend(
        UnifiHealthBinarySensor(coordinator, entry, desc, f"health_{desc.key}")
        for desc in HEALTH_BINARY_SENSORS
        if f"health_{desc.key}" not in excluded
    )
    if EP_ROGUE not in disabled_eps:
        entities.append(UnifiRogueProximityBinarySensor(coordinator, entry))

    known_macs: set[str] = set()
    known_ssids: set[str] = set()
    known_vpn_tunnels: set[str] = set()
    # Reserved unique-id suffixes for the dynamic WiFi/VPN entities, shared with
    # the discovery listener below so a later-appearing name can't collide.
    used_suffixes: set[str] = set()

    if coordinator.data:
        # Dynamic APs/switches
        for mac in coordinator.data.get("devices", {}):
            known_macs.add(mac)
            if want_device:
                entities.extend(
                    UnifiDeviceBinarySensor(coordinator, entry, desc, mac, standalone)
                    for desc in DEVICE_BINARY_SENSORS
                )
        # Dynamic WiFis and VPNs
        gw = coordinator.data.get("gateway") or {}
        for ssid in gw.get("wifi_states", {}):
            known_ssids.add(ssid)
            entities.append(
                UnifiWifiBinarySensor(
                    coordinator,
                    entry,
                    ssid,
                    _dedup_suffix(f"wifi_{slugify(ssid)}", used_suffixes),
                )
            )
        for tunnel in gw.get("vpn_states", {}):
            known_vpn_tunnels.add(tunnel)
            if EP_VPN_TUNNELS not in disabled_eps:
                entities.append(
                    UnifiVpnBinarySensor(
                        coordinator,
                        entry,
                        tunnel,
                        _dedup_suffix(f"vpn_{slugify(tunnel)}", used_suffixes),
                    )
                )

    async_add_entities(entities)

    @callback
    def _handle_coordinator_update() -> None:
        if not coordinator.data:
            return
        new_entities: list[BinarySensorEntity] = []

        # Check devices
        for mac in coordinator.data.get("devices", {}):
            if mac in known_macs:
                continue
            known_macs.add(mac)
            if want_device:
                new_entities.extend(
                    UnifiDeviceBinarySensor(coordinator, entry, desc, mac, standalone)
                    for desc in DEVICE_BINARY_SENSORS
                )

        # Check WiFis and VPNs
        gw = coordinator.data.get("gateway") or {}
        for ssid in gw.get("wifi_states", {}):
            if ssid in known_ssids:
                continue
            known_ssids.add(ssid)
            new_entities.append(
                UnifiWifiBinarySensor(
                    coordinator,
                    entry,
                    ssid,
                    _dedup_suffix(f"wifi_{slugify(ssid)}", used_suffixes),
                )
            )
        for tunnel in gw.get("vpn_states", {}):
            if tunnel in known_vpn_tunnels:
                continue
            known_vpn_tunnels.add(tunnel)
            if EP_VPN_TUNNELS not in disabled_eps:
                new_entities.append(
                    UnifiVpnBinarySensor(
                        coordinator,
                        entry,
                        tunnel,
                        _dedup_suffix(f"vpn_{slugify(tunnel)}", used_suffixes),
                    )
                )

        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_handle_coordinator_update))
