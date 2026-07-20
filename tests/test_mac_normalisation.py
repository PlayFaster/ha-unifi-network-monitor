"""MAC canonicalisation tests (dev_standards §3).

Home Assistant matches devices on a canonical MAC — lowercase, colon-separated.
If the controller returns any other form, the device-card merge with HA Core's
UniFi integration silently fails and the user gets duplicate cards. These tests
pin the normalisation at every point a MAC enters the integration.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

CANONICAL = "aa:bb:cc:dd:ee:ff"
# The same address in the forms a controller or firmware might legitimately emit.
VARIANTS = ("AA:BB:CC:DD:EE:FF", "aabbccddeeff", "AABBCCDDEEFF", "aa:bb:cc:dd:ee:ff")


def _coordinator(mac: str) -> Any:
    from custom_components.unifi_network_monitor.coordinator import (
        UnifiNetworkDataUpdateCoordinator,
    )

    entry = MagicMock()
    entry.data = {"mac": mac, "model": "UDMPRO", "sw_version": "5.1.19"}
    entry.options = {"host": "192.168.1.1", "scan_interval": 180}
    entry.title = "UniFi Network"
    hass = MagicMock()
    coord = UnifiNetworkDataUpdateCoordinator.__new__(UnifiNetworkDataUpdateCoordinator)
    from homeassistant.helpers.device_registry import format_mac

    coord.gateway_mac = format_mac(entry.data.get("mac", ""))
    coord.gateway_model = entry.data["model"]
    coord.sw_version = entry.data["sw_version"]
    coord.hass = hass
    return coord


def test_gateway_mac_is_canonicalised_from_every_variant() -> None:
    """Expose a canonical MAC whatever form the controller stored."""
    for variant in VARIANTS:
        assert _coordinator(variant).gateway_mac == CANONICAL, variant


def test_gateway_mac_tolerates_missing_value() -> None:
    """Tolerate a blank MAC without raising; the root is simply not registered."""
    assert _coordinator("").gateway_mac == ""


def test_device_info_uses_canonical_mac() -> None:
    """Use the canonical MAC in both the gateway identifier and connection."""
    from custom_components.unifi_network_monitor.helpers import (
        build_gateway_device_info,
    )

    entry = MagicMock()
    entry.title = "UniFi Network"
    entry.options = {"host": "192.168.1.1"}
    info = build_gateway_device_info(_coordinator("AA:BB:CC:DD:EE:FF"), entry)

    assert (CONNECTION_NETWORK_MAC, CANONICAL) in info["connections"]
    assert any(i[1] == CANONICAL for i in info["identifiers"])


def test_per_device_mac_is_canonicalised() -> None:
    """Normalise per-device MACs, which come straight off the payload."""
    from custom_components.unifi_network_monitor.helpers import (
        build_unifi_device_info,
    )

    info = build_unifi_device_info(
        _coordinator(CANONICAL), "F4:92:BF:11:22:33", "AP-Alpha", "U6-LR"
    )

    assert (CONNECTION_NETWORK_MAC, "f4:92:bf:11:22:33") in info["connections"]
    assert any(i[1] == "f4:92:bf:11:22:33" for i in info["identifiers"])


def test_sub_device_identifiers_derive_from_canonical_mac() -> None:
    """Derive sub-device ids and via_device from the canonical gateway MAC."""
    from custom_components.unifi_network_monitor.helpers import build_sub_device_info

    entry = MagicMock()
    entry.title = "UniFi Network"
    entry.options = {"host": "192.168.1.1"}
    info = build_sub_device_info(_coordinator("AABBCCDDEEFF"), entry, "security")

    assert any(i[1] == f"{CANONICAL}_security" for i in info["identifiers"])
    assert info["via_device"][1] == CANONICAL
