"""Shared helpers for the UniFi Network Monitor integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from .coordinator import UnifiNetworkDataUpdateCoordinator


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
