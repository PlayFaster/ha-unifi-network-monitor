"""Shared helpers for the UniFi Network Monitor integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from .coordinator import UnifiNetworkDataUpdateCoordinator


class UnifiAboutEntity:
    """Mixin exposing a static, human-facing ``about`` note as an attribute.

    Set the text via ``_attr_about`` (class-level for single-instance entities)
    or an ``about`` field on the entity description (for description-driven
    entities). The note shows in Developer Tools / the More Info dialog but is
    listed in ``_unrecorded_attributes`` so the recorder never writes it to
    history — zero cost no matter how often the state changes.

    List this mixin FIRST in an entity's bases so its ``extra_state_attributes``
    wins over the platform default. Entities that define their own
    ``extra_state_attributes`` should route the result through ``_with_about``.
    """

    _unrecorded_attributes = frozenset({"about"})
    _attr_about: str | None = None

    @property
    def _about_text(self) -> str | None:
        """Resolve the note from ``_attr_about`` or the entity description."""
        if self._attr_about is not None:
            return self._attr_about
        description = getattr(self, "entity_description", None)
        return getattr(description, "about", None) if description is not None else None

    def _with_about(self, attrs: dict[str, Any] | None) -> dict[str, Any] | None:
        """Merge the ``about`` note into an entity's own attribute dict."""
        about = self._about_text
        if about is None:
            return attrs
        return {"about": about, **(attrs or {})}

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Default: expose only the ``about`` note when one is set."""
        return self._with_about(None)


def build_gateway_device_info(
    coordinator: UnifiNetworkDataUpdateCoordinator,
    entry: ConfigEntry,
) -> DeviceInfo:
    """Build DeviceInfo for the UDM Pro gateway device.

    Uses CONNECTION_NETWORK_MAC so HA merges this device with any existing
    entry registered by the native UniFi integration for the same hardware.
    """
    mac = coordinator.gateway_mac
    return DeviceInfo(
        connections={(CONNECTION_NETWORK_MAC, mac)},
        identifiers={(DOMAIN, mac)},
        name=f"{entry.title} Gateway",
        manufacturer="Ubiquiti",
        model=coordinator.gateway_model,
        sw_version=coordinator.sw_version,
        configuration_url=f"https://{entry.options.get('host', '')}",
    )


def build_network_device_info(
    coordinator: UnifiNetworkDataUpdateCoordinator,
    entry: ConfigEntry,
) -> DeviceInfo:
    """Build DeviceInfo for the virtual Network Health sub-device."""
    mac = coordinator.gateway_mac
    return DeviceInfo(
        identifiers={(DOMAIN, f"{mac}_network")},
        name=f"{entry.title} Network",
        manufacturer="Ubiquiti",
        via_device=(DOMAIN, mac),
    )


def build_sub_device_info(
    coordinator: UnifiNetworkDataUpdateCoordinator,
    entry: ConfigEntry,
    device_key: str,
) -> DeviceInfo:
    """Build DeviceInfo for a virtual sub-device under the gateway."""
    mac = coordinator.gateway_mac
    if device_key == "gateway":
        return build_gateway_device_info(coordinator, entry)

    suffixes = {
        "internet": "Internet",
        "system": "System",
        "speedtest": "Speedtest",
        "status": "Status",
        "security": "Security",
        "alerts": "Alerts",
    }
    suffix = suffixes.get(device_key, "System")

    return DeviceInfo(
        identifiers={(DOMAIN, f"{mac}_{device_key}")},
        name=f"{entry.title} {suffix}",
        manufacturer="Ubiquiti",
        via_device=(DOMAIN, mac),
    )


def build_unifi_device_info(
    coordinator: UnifiNetworkDataUpdateCoordinator,
    device_mac: str,
    device_name: str,
    device_model: str,
) -> DeviceInfo:
    """Build DeviceInfo for a dynamic UniFi device (AP or switch).

    Uses CONNECTION_NETWORK_MAC so HA merges with native integration entries
    for the same physical device where they already exist.
    """
    gateway_mac = coordinator.gateway_mac
    return DeviceInfo(
        connections={(CONNECTION_NETWORK_MAC, device_mac)},
        identifiers={(DOMAIN, device_mac)},
        name=device_name,
        manufacturer="Ubiquiti",
        model=device_model or None,
        via_device=(DOMAIN, gateway_mac),
    )
