"""ISP per WAN, Uplink ISP and the retired site-level ISP entities (1.1.2-dev4).

The site-level ``stat/health`` ISP fields always described WAN1, so WAN1 ISP,
WAN2 ISP and Uplink ISP read the gateway's per-WAN ``geo_info`` blocks instead.
Location fields in those blocks identify the subscriber and are never read.
"""

from __future__ import annotations

from copy import deepcopy
import json
from typing import Any
from unittest.mock import MagicMock, patch

from custom_components.unifi_network_monitor.binary_sensor import GATEWAY_BINARY_SENSORS
from custom_components.unifi_network_monitor.cleanup import plan_device_cleanup
from custom_components.unifi_network_monitor.const import RETIRED_KEYS, WAN2_KEYS
from custom_components.unifi_network_monitor.coordinator import (
    UnifiNetworkDataUpdateCoordinator,
)
from custom_components.unifi_network_monitor.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.unifi_network_monitor.sensor import (
    GATEWAY_SENSORS,
    HEALTH_SENSORS,
    UnifiGatewaySensor,
)

from .conftest import MOCK_COORDINATOR_DATA, MOCK_MAC
from .transport import GATEWAY, ControllerFake, real_api

ISP_ONE = "Example Fibre"
ISP_TWO = "Sample Wireless"
ORG_ONE = "Example Holdings"
LOCATION = {
    "address": "203.0.113.7",
    "latitude": 51.5,
    "longitude": -0.12,
    "city": "Exampletown",
    "accuracy": 1000,
}


def _gateway(
    *,
    wan1_uplink: bool,
    wan2_uplink: bool,
    geo: dict[str, Any] | None = None,
    active_geo: dict[str, Any] | None = None,
    last_geo: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """The test gateway with two WANs and the given geo blocks."""
    device = deepcopy(GATEWAY)
    device["wan1"] = {**device["wan1"], "is_uplink": wan1_uplink}
    device["wan2"] = {"ifname": "eth9", "is_uplink": wan2_uplink, "up": True}
    for key, block in (
        ("geo_info", geo),
        ("active_geo_info", active_geo),
        ("last_geo_info", last_geo),
    ):
        if block is not None:
            device[key] = block
    return device


async def _poll(
    hass: Any, entry: Any, aioclient_mock: Any, gateway: dict[str, Any]
) -> dict[str, Any]:
    entry.add_to_hass(hass)
    ControllerFake(aioclient_mock).serve(gateway)
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, entry, real_api(hass))
    return dict((await coordinator._async_update_data())["gateway"])


async def test_each_wan_reads_its_own_provider(
    hass: Any, mock_config_entry: Any, aioclient_mock: Any
) -> None:
    """HTTP-seam: WAN1 and WAN2 ISP come from their own geo_info entries."""
    gateway = await _poll(
        hass,
        mock_config_entry,
        aioclient_mock,
        _gateway(
            wan1_uplink=True,
            wan2_uplink=False,
            geo={
                "WAN": {"isp_name": ISP_ONE, "isp_organization": ORG_ONE, "asn": 64500},
                "WAN2": {"isp_name": ISP_TWO, "asn": 64501, **LOCATION},
            },
        ),
    )
    assert gateway["wan1_isp"] == ISP_ONE
    assert gateway["wan1_isp_attrs"] == {"isp_organization": ORG_ONE, "asn": 64500}
    assert gateway["wan2_isp"] == ISP_TWO
    assert gateway["wan2_isp_attrs"] == {"isp_organization": None, "asn": 64501}


async def test_later_blocks_fill_gaps_but_never_overwrite(
    hass: Any, mock_config_entry: Any, aioclient_mock: Any
) -> None:
    """HTTP-seam: active_geo_info and last_geo_info fill only what geo_info lacks."""
    gateway = await _poll(
        hass,
        mock_config_entry,
        aioclient_mock,
        _gateway(
            wan1_uplink=True,
            wan2_uplink=False,
            geo={"WAN": {"isp_name": ISP_ONE, "isp_organization": "  "}},
            active_geo={
                "WAN": {"isp_name": "Overwritten", "isp_organization": ORG_ONE},
                "WAN2": "not a block",
            },
            last_geo={"WAN": {"asn": 64500}, "WAN2": {"isp_name": ISP_TWO}},
        ),
    )
    assert gateway["wan1_isp"] == ISP_ONE
    assert gateway["wan1_isp_attrs"] == {"isp_organization": ORG_ONE, "asn": 64500}
    assert gateway["wan2_isp"] == ISP_TWO


async def test_a_wan_with_no_geo_info_reads_unknown(
    hass: Any, mock_config_entry: Any, aioclient_mock: Any
) -> None:
    """HTTP-seam: no geo blocks, or a non-dict block, gives None, never ''."""
    device = _gateway(
        wan1_uplink=True, wan2_uplink=False, geo={"WAN": {"isp_name": ""}}
    )
    device["active_geo_info"] = ["not", "a", "dict"]
    gateway = await _poll(hass, mock_config_entry, aioclient_mock, device)
    assert gateway["wan1_isp"] is None
    assert gateway["wan2_isp"] is None
    assert gateway["wan2_isp_attrs"] == {"isp_organization": None, "asn": None}
    assert gateway["uplink_isp"] is None


async def test_uplink_isp_follows_the_uplink_wan(
    hass: Any, mock_config_entry: Any, aioclient_mock: Any
) -> None:
    """HTTP-seam: Uplink ISP is the provider of the WAN flagged as uplink."""
    geo = {
        "WAN": {"isp_name": ISP_ONE},
        "WAN2": {"isp_name": ISP_TWO, "asn": 64501},
    }
    on_wan2 = await _poll(
        hass,
        mock_config_entry,
        aioclient_mock,
        _gateway(wan1_uplink=False, wan2_uplink=True, geo=geo),
    )
    assert on_wan2["uplink_isp"] == ISP_TWO
    assert on_wan2["uplink_isp_attrs"] == {"isp_organization": None, "asn": 64501}


async def test_uplink_isp_on_wan1_and_from_the_uplink_comment(
    hass: Any, mock_config_entry: Any, aioclient_mock: Any
) -> None:
    """HTTP-seam: WAN1 flagged gives WAN1; with no flag the uplink comment decides."""
    geo = {"WAN": {"isp_name": ISP_ONE}, "WAN2": {"isp_name": ISP_TWO}}
    on_wan1 = await _poll(
        hass,
        mock_config_entry,
        aioclient_mock,
        _gateway(wan1_uplink=True, wan2_uplink=True, geo=geo),
    )
    assert on_wan1["uplink_isp"] == ISP_ONE

    by_comment = _gateway(wan1_uplink=False, wan2_uplink=False, geo=geo)
    by_comment["uplink"] = {"up": True, "comment": "WAN2"}
    ControllerFake(aioclient_mock).serve(by_comment)
    coordinator = UnifiNetworkDataUpdateCoordinator(
        hass, mock_config_entry, real_api(hass)
    )
    data = await coordinator._async_update_data()
    assert data["gateway"]["uplink_isp"] == ISP_TWO

    by_comment["uplink"] = {"up": True, "comment": "LAN"}
    ControllerFake(aioclient_mock).serve(by_comment)
    data = await coordinator._async_update_data()
    assert data["gateway"]["uplink_isp"] is None


async def test_no_location_field_is_published(
    hass: Any, mock_config_entry: Any, aioclient_mock: Any
) -> None:
    """HTTP-seam: location fields of the geo blocks never reach coordinator data."""
    gateway = await _poll(
        hass,
        mock_config_entry,
        aioclient_mock,
        _gateway(
            wan1_uplink=True,
            wan2_uplink=False,
            geo={"WAN": {"isp_name": ISP_ONE, **LOCATION}},
        ),
    )
    text = json.dumps({k: v for k, v in gateway.items() if "isp" in k}, default=str)
    for field_name in ("latitude", "longitude", "city", "accuracy", "Exampletown"):
        assert field_name not in text


def _sensor(key: str, gateway: dict[str, Any]) -> UnifiGatewaySensor:
    coordinator = MagicMock()
    coordinator.data = {**MOCK_COORDINATOR_DATA, "gateway": gateway}
    coordinator.endpoint_available.return_value = True
    entry = MagicMock()
    entry.unique_id = MOCK_MAC
    entry.options = {}
    desc = next(d for d in GATEWAY_SENSORS if d.key == key)
    return UnifiGatewaySensor(coordinator, entry, desc, key)


def test_isp_sensors_publish_state_attributes_and_about() -> None:
    """Each ISP sensor publishes its state, organization and ASN, and an about note."""
    attrs = {"isp_organization": ORG_ONE, "asn": 64500}
    gateway = {
        "wan1_isp": ISP_ONE,
        "wan1_isp_attrs": attrs,
        "wan2_isp": None,
        "wan2_isp_attrs": {"isp_organization": None, "asn": None},
        "uplink_isp": ISP_ONE,
        "uplink_isp_attrs": attrs,
    }
    wan1 = _sensor("wan1_isp", gateway)
    assert wan1.native_value == ISP_ONE
    published = wan1.extra_state_attributes
    assert published is not None
    assert published["isp_organization"] == ORG_ONE
    assert published["asn"] == 64500
    assert published["about"].startswith("The provider of WAN1")
    assert _sensor("wan2_isp", gateway).native_value is None
    uplink = _sensor("uplink_isp", gateway).extra_state_attributes
    assert uplink is not None
    assert "priority-1 WAN" in uplink["about"]
    assert {"isp_organization", "asn"} <= UnifiGatewaySensor._unrecorded_attributes


def test_isp_sensors_without_attrs_publish_only_about() -> None:
    """With no attribute record the sensor publishes its about note alone."""
    published = _sensor("wan2_isp", {"wan2_isp": None}).extra_state_attributes
    assert published is not None
    assert set(published) == {"about"}


def test_active_uplink_sensors_carry_their_about_note() -> None:
    """WAN1 and WAN2 Active Uplink explain both modes."""
    for key in ("wan1_active", "wan2_active"):
        desc = next(d for d in GATEWAY_BINARY_SENSORS if d.key == key)
        assert desc.about is not None
        assert "failover mode" in desc.about
        assert "load balancing" in desc.about


def test_retired_entities_are_no_longer_created() -> None:
    """ISP Name and ISP Organization have no description, and WAN2 ISP is a WAN2 key."""
    keys = {d.key for d in HEALTH_SENSORS}
    assert "wan_isp_name" not in keys
    assert "wan_isp_org" not in keys
    assert {"health_wan_isp_name", "health_wan_isp_org"} == RETIRED_KEYS
    assert "wan2_isp" in WAN2_KEYS
    assert "wan1_isp" not in WAN2_KEYS


def test_cleanup_removes_the_retired_entities() -> None:
    """Upgrade sequence: entities registered by 1.1.2-dev3 are planned for removal."""
    entry = MagicMock()
    entry.unique_id = MOCK_MAC
    entry.entry_id = "entry123"
    entry.options = {"host": "192.168.1.1", "enable_dual_wan": True}
    coordinator = MagicMock()
    coordinator.data = MOCK_COORDINATOR_DATA
    coordinator.gateway_mac = None

    def reg(entity_id: str, suffix: str) -> MagicMock:
        item = MagicMock()
        item.entity_id = entity_id
        item.unique_id = f"{MOCK_MAC}_{suffix}"
        return item

    registered = [
        reg("sensor.isp_name", "health_wan_isp_name"),
        reg("sensor.isp_organization", "health_wan_isp_org"),
        reg("sensor.wan1_isp", "wan1_isp"),
        reg("sensor.other_entry", "health_wan_isp_name_extra"),
    ]
    stranger = MagicMock()
    stranger.entity_id = "sensor.foreign"
    stranger.unique_id = "someone_else_health_wan_isp_name"
    with (
        patch("custom_components.unifi_network_monitor.cleanup.er.async_get"),
        patch("custom_components.unifi_network_monitor.cleanup.dr.async_get"),
        patch(
            "custom_components.unifi_network_monitor.cleanup.er.async_entries_for_config_entry",
            return_value=[*registered, stranger],
        ),
    ):
        plan = plan_device_cleanup(MagicMock(), entry, coordinator)
    assert sorted(plan.entity_ids) == ["sensor.isp_name", "sensor.isp_organization"]


async def test_isp_values_never_reach_the_diagnostics_download(hass: Any) -> None:
    """The ISP names and organization are redacted in the download."""
    coord = MagicMock()
    data = deepcopy(MOCK_COORDINATOR_DATA)
    data["gateway"].update(
        {
            "wan1_isp": ISP_ONE,
            "wan1_isp_attrs": {"isp_organization": ORG_ONE, "asn": 64500},
            "wan2_isp": ISP_TWO,
            "uplink_isp": ISP_ONE,
        }
    )
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
    text = json.dumps(
        await async_get_config_entry_diagnostics(hass, entry), default=str
    )
    for value in (ISP_ONE, ISP_TWO, ORG_ONE):
        assert value not in text


async def test_location_fields_are_redacted_in_the_diagnostics_download(
    hass: Any,
) -> None:
    """A raw geo block reaching the download has every location field redacted."""
    from custom_components.unifi_network_monitor.diagnostics import REDACTED

    coord = MagicMock()
    data = deepcopy(MOCK_COORDINATOR_DATA)
    data["gateway"]["geo_info"] = {"WAN": {"isp_name": ISP_ONE, **LOCATION}}
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
    block = result["data"]["gateway"]["geo_info"]["WAN"]
    for field_name in LOCATION:
        assert block[field_name] == REDACTED
    text = json.dumps(result, default=str)
    assert "Exampletown" not in text
    assert "51.5" not in text
