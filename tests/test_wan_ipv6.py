"""WAN1 and WAN2 Public IPv6 Address (1.1.2-dev4).

Each WAN's ``ipv6`` list in ``stat/device`` holds a link-local address on every
IPv6-capable interface and, when the ISP assigns one, a global address. Only a
global address is published; a WAN without one reads unknown.
"""

from __future__ import annotations

from copy import deepcopy
import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from custom_components.unifi_network_monitor.const import WAN2_KEYS
from custom_components.unifi_network_monitor.coordinator import (
    UnifiNetworkDataUpdateCoordinator,
)
from custom_components.unifi_network_monitor.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.unifi_network_monitor.sensor import (
    GATEWAY_SENSORS,
    UnifiGatewaySensor,
)

from .conftest import MOCK_COORDINATOR_DATA, MOCK_MAC
from .transport import GATEWAY, ControllerFake, real_api

GLOBAL = "2001:db8::10"
LINK_LOCAL = "fe80::1"
UNIQUE_LOCAL = "fd00::1"


@pytest.mark.parametrize(
    ("wan2_ipv6", "expected"),
    [
        # IPv6 enabled on the WAN: the global address, after the link-local one.
        ([LINK_LOCAL, GLOBAL], GLOBAL),
        # A zone index or prefix length on the entry is ignored for the test.
        ([f"{GLOBAL}/64"], GLOBAL),
        # IPv6 off: only the link-local address.
        ([LINK_LOCAL], None),
        # A unique-local address from an upstream router is not public.
        ([UNIQUE_LOCAL, f"{LINK_LOCAL}%eth9"], None),
        # Junk and non-string entries are skipped.
        (["not-an-address", 42, None], None),
        ([], None),
        ("not a list", None),
    ],
)
async def test_wan_public_ipv6_is_the_first_global_address(
    hass: Any,
    mock_config_entry: Any,
    aioclient_mock: Any,
    wan2_ipv6: Any,
    expected: str | None,
) -> None:
    """HTTP-seam: each WAN's IPv6 entity reads its first global address only."""
    device = deepcopy(GATEWAY)
    device["wan1"] = {**device["wan1"], "ipv6": [LINK_LOCAL]}
    device["wan2"] = {"ifname": "eth9", "up": True, "ipv6": wan2_ipv6}
    mock_config_entry.add_to_hass(hass)
    ControllerFake(aioclient_mock).serve(device)
    coordinator = UnifiNetworkDataUpdateCoordinator(
        hass, mock_config_entry, real_api(hass)
    )
    gateway = (await coordinator._async_update_data())["gateway"]
    assert gateway["wan1_public_ipv6"] is None
    assert gateway["wan2_public_ipv6"] == expected


async def test_a_wan_without_an_ipv6_list_reads_unknown(
    hass: Any, mock_config_entry: Any, aioclient_mock: Any
) -> None:
    """HTTP-seam: a WAN object with no ipv6 field, or no WAN2 at all, reads None."""
    mock_config_entry.add_to_hass(hass)
    ControllerFake(aioclient_mock).serve()
    coordinator = UnifiNetworkDataUpdateCoordinator(
        hass, mock_config_entry, real_api(hass)
    )
    gateway = (await coordinator._async_update_data())["gateway"]
    assert gateway["wan1_public_ipv6"] is None
    assert gateway["wan2_public_ipv6"] is None


def test_ipv6_sensors_read_the_value_and_carry_the_about_note() -> None:
    """The sensors publish the coordinator value; WAN2's is a single-WAN exclusion."""
    coordinator = MagicMock()
    coordinator.data = {
        **MOCK_COORDINATOR_DATA,
        "gateway": {"wan1_public_ipv6": None, "wan2_public_ipv6": GLOBAL},
    }
    coordinator.endpoint_available.return_value = True
    entry = MagicMock()
    entry.unique_id = MOCK_MAC
    entry.options = {}
    for key, expected in (("wan1_public_ipv6", None), ("wan2_public_ipv6", GLOBAL)):
        desc = next(d for d in GATEWAY_SENSORS if d.key == key)
        sensor = UnifiGatewaySensor(coordinator, entry, desc, key)
        assert sensor.native_value == expected
        assert desc.about is not None
        assert "global IPv6 address" in desc.about
    assert "wan2_public_ipv6" in WAN2_KEYS
    assert "wan1_public_ipv6" not in WAN2_KEYS


async def test_ipv6_addresses_never_reach_the_diagnostics_download(hass: Any) -> None:
    """Both IPv6 values are redacted in the download."""
    coord = MagicMock()
    data = deepcopy(MOCK_COORDINATOR_DATA)
    data["gateway"].update({"wan1_public_ipv6": GLOBAL, "wan2_public_ipv6": GLOBAL})
    coord.data = data
    coord.gateway_mac = MOCK_MAC
    coord.gateway_model = "UDMPRO"
    coord.sw_version = "5.1.19.33549"
    coord.consecutive_failures = 0
    coord.last_update_success = True
    coord.last_update_success_time = None
    coord.rogue_history = {}
    coord.api.last_rejection = None
    coord.api.login_metadata = None
    coord.api.routes = {}
    coord.endpoint_outcomes = {}
    coord.gateway_selection = None
    coord.stored_mac_absent = False
    coord.gateway_startup_timestamp = None
    coord.controller_timezone = None
    entry = MagicMock()
    entry.unique_id = MOCK_MAC
    entry.title = "UniFi Network"
    entry.data = {"mac": MOCK_MAC, "model": "UDMPRO"}
    entry.options = {"host": "192.168.1.1", "site": "default"}
    entry.runtime_data = coord
    result = await async_get_config_entry_diagnostics(hass, entry)
    assert GLOBAL not in json.dumps(result, default=str)
