"""Tests for the UniFi Network Monitor helpers."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

from custom_components.unifi_network_monitor.const import DOMAIN

from .conftest import MOCK_COORDINATOR_DATA, MOCK_MAC


def _make_coordinator(data: dict[str, Any] | None = None) -> MagicMock:
    coord = MagicMock()
    coord.data = data or MOCK_COORDINATOR_DATA
    coord.gateway_mac = MOCK_MAC
    coord.gateway_model = "UDMPRO"
    coord.sw_version = "5.1.19.33549"
    return coord


def _make_entry() -> MagicMock:
    entry = MagicMock()
    entry.unique_id = MOCK_MAC
    entry.title = "UniFi Network"
    entry.options = {"host": "192.168.1.1"}
    return entry


def test_build_gateway_device_info() -> None:
    """Gateway device info uses CONNECTION_NETWORK_MAC."""
    from custom_components.unifi_network_monitor.helpers import (
        build_gateway_device_info,
    )

    coordinator = _make_coordinator()
    entry = _make_entry()

    info = build_gateway_device_info(coordinator, entry)
    assert info["connections"] == {(CONNECTION_NETWORK_MAC, MOCK_MAC)}
    assert info["identifiers"] == {(DOMAIN, MOCK_MAC)}
    assert "Gateway" in info["name"]
    assert info["model"] == "UDMPRO"
    assert info["sw_version"] == "5.1.19.33549"


def test_build_network_device_info() -> None:
    """Network device info uses mac_network identifier."""
    from custom_components.unifi_network_monitor.helpers import (
        build_network_device_info,
    )

    coordinator = _make_coordinator()
    entry = _make_entry()

    info = build_network_device_info(coordinator, entry)
    assert info["identifiers"] == {(DOMAIN, f"{MOCK_MAC}_network")}
    assert "Network" in info["name"]
    assert info["via_device"] == (DOMAIN, MOCK_MAC)


def test_build_unifi_device_info_with_model() -> None:
    """Unifi device info includes model and via_device."""
    from custom_components.unifi_network_monitor.helpers import (
        build_unifi_device_info,
    )

    coordinator = _make_coordinator()
    device_mac = "bb:cc:dd:ee:ff:00"
    device_name = "Test AP"
    device_model = "UAP-AC-M"

    info = build_unifi_device_info(coordinator, device_mac, device_name, device_model)
    assert info["connections"] == {(CONNECTION_NETWORK_MAC, device_mac)}
    assert info["identifiers"] == {(DOMAIN, device_mac)}
    assert info["name"] == "Test AP"
    assert info["model"] == "UAP-AC-M"
    assert info["via_device"] == (DOMAIN, MOCK_MAC)


def test_build_unifi_device_info_none_model() -> None:
    """Unifi device info handles None model."""
    from custom_components.unifi_network_monitor.helpers import (
        build_unifi_device_info,
    )

    coordinator = _make_coordinator()
    device_mac = "bb:cc:dd:ee:ff:00"

    info = build_unifi_device_info(coordinator, device_mac, "Test AP", "")
    assert info["model"] is None
