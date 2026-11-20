"""Raw key inventory per answered route in the diagnostics download (1.1.2-dev4).

The download shows which field names each route answered with, so a second
gateway model's spellings can be read from any user's download. Names only:
no value, and identifier-shaped names tokenized by the scrubber.
"""

from __future__ import annotations

from copy import deepcopy
import json
from typing import Any
from unittest.mock import MagicMock

from custom_components.unifi_network_monitor.api import UnifiNetworkAPI
from custom_components.unifi_network_monitor.coordinator import (
    UnifiNetworkDataUpdateCoordinator,
)
from custom_components.unifi_network_monitor.diagnostics import (
    async_get_config_entry_diagnostics,
)
from scripts.diag_check import block_problems

from .conftest import MOCK_COORDINATOR_DATA, MOCK_MAC
from .transport import GATEWAY, ControllerFake, real_api

CLIENT_MAC = "11:22:33:44:55:66"
SECRET_VALUE = "value-that-must-not-appear"


def test_inventory_lists_record_and_nested_names_without_values() -> None:
    """Record keys, nested-object keys and nested-list keys; never a value."""
    data = [
        {
            "mac": SECRET_VALUE,
            "system-stats": {"cpu": SECRET_VALUE, "mem": "40"},
            "port_table": [{"name": SECRET_VALUE, "speed": 1000}, "not a dict"],
            "tags": ["a", "b"],
        },
        {"mac": "other", "uptime": 5},
        "not a record",
    ]
    names = UnifiNetworkAPI._key_inventory(data)
    assert names == [
        "mac",
        "port_table",
        "port_table[].name",
        "port_table[].speed",
        "system-stats",
        "system-stats.cpu",
        "system-stats.mem",
        "tags",
        "uptime",
    ]
    assert SECRET_VALUE not in json.dumps(names)
    assert UnifiNetworkAPI._key_inventory({"data": []}) is None
    assert UnifiNetworkAPI._key_inventory(None) is None


async def test_answered_route_carries_its_inventory(
    hass: Any, mock_config_entry: Any, aioclient_mock: Any
) -> None:
    """HTTP-seam: a real poll records the stat/device inventory on its route."""
    mock_config_entry.add_to_hass(hass)
    ControllerFake(aioclient_mock).serve()
    api = real_api(hass)
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    await coordinator._async_update_data()
    device_route = next(r for k, r in api.routes.items() if k.endswith("/stat/device"))
    assert "system-stats" in device_route["keys"]
    assert "system-stats.cpu" in device_route["keys"]
    assert "wan1.is_uplink" in device_route["keys"]
    assert set(GATEWAY) <= set(device_route["keys"])


def _coordinator_with_routes(routes: dict[str, Any]) -> MagicMock:
    coord = MagicMock()
    coord.data = deepcopy(MOCK_COORDINATOR_DATA)
    coord.gateway_mac = MOCK_MAC
    coord.gateway_model = "UDMPRO"
    coord.sw_version = "5.1.19.33549"
    coord.consecutive_failures = 0
    coord.last_update_success = True
    coord.last_update_success_time = None
    coord.rogue_history = {}
    coord.api.last_rejection = None
    coord.api.login_metadata = None
    coord.api.routes = routes
    coord.endpoint_outcomes = {}
    coord.gateway_selection = None
    coord.stored_mac_absent = False
    coord.gateway_startup_timestamp = None
    coord.controller_timezone = None
    return coord


async def test_download_publishes_the_inventory_with_identifiers_tokenized(
    hass: Any,
) -> None:
    """The inventory reaches the file; a MAC-shaped key name is tokenized."""
    route = "GET /proxy/network/api/s/<site>/stat/device"
    coord = _coordinator_with_routes(
        {
            route: {
                "method": "GET",
                "route": "/proxy/network/api/s/<site>/stat/device",
                "status": 200,
                "keys": ["mac", "system-stats", f"mac_table.{CLIENT_MAC}"],
            }
        }
    )
    entry = MagicMock()
    entry.unique_id = MOCK_MAC
    entry.title = "UniFi Network"
    entry.data = {"mac": MOCK_MAC, "model": "UDMPRO"}
    entry.options = {"host": "192.168.1.1", "site": "default"}
    entry.runtime_data = coord
    result = await async_get_config_entry_diagnostics(hass, entry)
    keys = result["endpoints"]["routes"][route]["keys"]
    assert "system-stats" in keys
    assert "mac" in keys
    assert CLIENT_MAC not in json.dumps(result, default=str)
    assert any(k.startswith("mac_table.") for k in keys)


def test_diag_check_requires_the_device_inventory() -> None:
    """A healthy download's stat/device route must list its key names."""
    route = "GET /proxy/network/api/s/<site>/stat/device"
    download: dict[str, Any] = {
        "endpoints": {
            "outcomes": {"devices": {"outcome": "answered"}},
            "routes": {route: {"keys": ["mac", "system-stats"]}},
        },
        "gateway": {
            "selection_reason": "wan_signature",
            "startup_timestamp": 1,
            "controller_timezone": "WET",
            "published_boot_time": None,
        },
        "last_rejection": None,
        "login": None,
    }
    assert block_problems(download, api_key_mode=True) == []
    download["endpoints"]["routes"][route] = {"keys": ["mac"]}
    assert block_problems(download, api_key_mode=True) == [
        f"endpoints.routes.{route} has no key inventory"
    ]
    download["endpoints"]["routes"][route] = "not a record"
    assert len(block_problems(download, api_key_mode=True)) == 1
    download["endpoints"]["routes"] = {"GET /other": {}}
    assert block_problems(download, api_key_mode=True) == []


def test_leak_scan_reads_the_key_inventory_case_sensitively() -> None:
    """A network named like a field is no leak there; the exact name still is."""
    from scripts.diag_check import leak_hits

    route = "GET /proxy/network/api/s/<site>/stat/device"
    download: dict[str, Any] = {
        "endpoints": {"routes": {route: {"keys": ["guest-num_sta", "uplink.guest"]}}},
        "data": {"note": "the Guest network"},
    }
    secrets = {"network_name": {"Guest"}}
    assert leak_hits(download, secrets) == {"network_name": ["data.note"]}
    download["endpoints"]["routes"][route]["keys"].append("vpn_states.Guest")
    hits = leak_hits(download, secrets)
    assert sorted(hits["network_name"]) == [
        "data.note",
        f"endpoints.routes.{route}.keys[]",
    ]
