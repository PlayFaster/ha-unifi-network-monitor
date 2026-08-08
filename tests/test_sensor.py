"""Tests for the UniFi Network Monitor sensor platform."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.util import dt as dt_util

from custom_components.unifi_network_monitor.const import (
    CONF_ENABLE_SECURITY_MONITORING,
    CONF_ENABLE_SPEEDTEST,
    CONF_ENABLE_WAN_USAGE,
    CONF_UNIFI_DEVICE_MODE,
)
from custom_components.unifi_network_monitor.sensor import (
    AP_SENSORS,
    GATEWAY_SENSORS,
    HEALTH_SENSORS,
    SWITCH_SENSORS,
    UnifiDeviceSensor,
    UnifiGatewaySensor,
    UnifiHealthSensor,
    UnifiSensorEntityDescription,
    _device_descs,
)

from .conftest import MOCK_COORDINATOR_DATA, MOCK_MAC

# ---------------------------------------------------------------------------
# Helper — build a minimal coordinator mock
# ---------------------------------------------------------------------------


def _make_coordinator(data: dict[str, Any] | None) -> MagicMock:
    coord = MagicMock()
    coord.data = data
    coord.gateway_mac = MOCK_MAC
    coord.gateway_model = "UDMPRO"
    coord.sw_version = "5.1.19.33549"
    coord.async_add_listener = MagicMock()
    return coord


def _make_entry(unique_id: str = MOCK_MAC) -> MagicMock:
    entry = MagicMock()
    entry.unique_id = unique_id
    entry.title = "UniFi Network"
    entry.options = {
        "host": "192.168.1.1",
        CONF_UNIFI_DEVICE_MODE: "all",
        CONF_ENABLE_SPEEDTEST: True,
        CONF_ENABLE_WAN_USAGE: True,
        CONF_ENABLE_SECURITY_MONITORING: True,
    }
    return entry


# ---------------------------------------------------------------------------
# Guard band tests (pure logic — no HA)
# ---------------------------------------------------------------------------


def _make_desc(
    key: str,
    value_fn: Any,
    min_limit: float | None = None,
    max_limit: float | None = None,
) -> UnifiSensorEntityDescription:
    return UnifiSensorEntityDescription(
        key=key,
        translation_key=key,
        value_fn=value_fn,
        min_limit=min_limit,
        max_limit=max_limit,
    )


def test_guard_band_below_min_returns_none() -> None:
    """Value below min_limit should be replaced by None."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    desc = _make_desc("cpu", lambda d: -1.0, min_limit=0.0, max_limit=100.0)
    sensor = UnifiGatewaySensor(coordinator, entry, desc, "cpu")

    with patch.object(sensor, "_get_value", return_value=-1.0):
        assert sensor.native_value is None


def test_guard_band_above_max_returns_none() -> None:
    """Value above max_limit should be replaced by None."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    desc = _make_desc("cpu", lambda d: 200.0, min_limit=0.0, max_limit=100.0)
    sensor = UnifiGatewaySensor(coordinator, entry, desc, "cpu")

    with patch.object(sensor, "_get_value", return_value=200.0):
        assert sensor.native_value is None


def test_guard_band_within_range_passes_through() -> None:
    """Value within guard band range should pass through unchanged."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    desc = _make_desc("cpu", lambda d: 37.2, min_limit=0.0, max_limit=100.0)
    sensor = UnifiGatewaySensor(coordinator, entry, desc, "cpu")

    with patch.object(sensor, "_get_value", return_value=37.2):
        assert sensor.native_value == pytest.approx(37.2)


def test_guard_band_none_value_passes_through() -> None:
    """None value should pass through (not crash on comparison)."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    desc = _make_desc("cpu", lambda d: None, min_limit=0.0, max_limit=100.0)
    sensor = UnifiGatewaySensor(coordinator, entry, desc, "cpu")

    with patch.object(sensor, "_get_value", return_value=None):
        assert sensor.native_value is None


def test_guard_band_non_numeric_ignored() -> None:
    """Non-numeric values (strings) skip guard band comparisons."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    desc = _make_desc("status", lambda d: "ok", min_limit=0.0, max_limit=100.0)
    sensor = UnifiGatewaySensor(coordinator, entry, desc, "status")

    with patch.object(sensor, "_get_value", return_value="ok"):
        assert sensor.native_value == "ok"


# ---------------------------------------------------------------------------
# Gateway sensor value extraction
# ---------------------------------------------------------------------------


def test_gateway_sensor_reads_cpu() -> None:
    """UnifiGatewaySensor reads cpu from coordinator.data['gateway']."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    cpu_desc = next(d for d in GATEWAY_SENSORS if d.key == "cpu")
    sensor = UnifiGatewaySensor(coordinator, entry, cpu_desc, "cpu")
    assert sensor.native_value == pytest.approx(37.2)


def test_gateway_sensor_reads_wan_ips() -> None:
    """UnifiGatewaySensor reads all four WAN IP address fields."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()

    wan1_local_desc = next(d for d in GATEWAY_SENSORS if d.key == "wan1_local_ip")
    sensor = UnifiGatewaySensor(coordinator, entry, wan1_local_desc, "wan1_local_ip")
    assert sensor.native_value == "192.0.2.1"

    wan1_public_desc = next(d for d in GATEWAY_SENSORS if d.key == "wan1_public_ip")
    sensor = UnifiGatewaySensor(coordinator, entry, wan1_public_desc, "wan1_public_ip")
    assert sensor.native_value == "198.51.100.1"

    wan2_local_desc = next(d for d in GATEWAY_SENSORS if d.key == "wan2_local_ip")
    sensor = UnifiGatewaySensor(coordinator, entry, wan2_local_desc, "wan2_local_ip")
    assert sensor.native_value == "192.0.2.2"

    wan2_public_desc = next(d for d in GATEWAY_SENSORS if d.key == "wan2_public_ip")
    sensor = UnifiGatewaySensor(coordinator, entry, wan2_public_desc, "wan2_public_ip")
    assert sensor.native_value == "203.0.113.1"


def test_gateway_sensor_returns_none_when_no_data() -> None:
    """UnifiGatewaySensor returns None when coordinator.data is falsy."""
    coordinator = _make_coordinator(None)
    entry = _make_entry()
    cpu_desc = next(d for d in GATEWAY_SENSORS if d.key == "cpu")
    sensor = UnifiGatewaySensor(coordinator, entry, cpu_desc, "cpu")
    assert sensor.native_value is None


def test_gateway_sensor_reads_ram() -> None:
    """UnifiGatewaySensor reads ram percentage."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    ram_desc = next(d for d in GATEWAY_SENSORS if d.key == "ram")
    sensor = UnifiGatewaySensor(coordinator, entry, ram_desc, "ram")
    assert sensor.native_value == pytest.approx(72.0)


def test_gateway_sensor_reads_boot_time() -> None:
    """UnifiGatewaySensor reads boot_time (None when no uptime set in mock)."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    uptime_desc = next(d for d in GATEWAY_SENSORS if d.key == "uptime")
    sensor = UnifiGatewaySensor(coordinator, entry, uptime_desc, "uptime")
    assert sensor.native_value is None


def test_gateway_sensor_reads_last_updated() -> None:
    """UnifiGatewaySensor reads last_updated from coordinator success time."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    now = dt_util.now()
    coordinator.last_update_success_time = now
    entry = _make_entry()
    desc = next(d for d in GATEWAY_SENSORS if d.key == "last_updated")
    sensor = UnifiGatewaySensor(coordinator, entry, desc, "last_updated")
    assert sensor.native_value == now


# ---------------------------------------------------------------------------
# Health sensor value extraction
# ---------------------------------------------------------------------------


def test_health_sensor_reads_wan_isp_name() -> None:
    """UnifiHealthSensor reads wan_isp_name from health sub-dict."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    desc = next(d for d in HEALTH_SENSORS if d.key == "wan_isp_name")
    sensor = UnifiHealthSensor(coordinator, entry, desc, "health_wan_isp_name")
    assert sensor.native_value == "Test ISP"


def test_health_sensor_reads_wlan_num_user() -> None:
    """UnifiHealthSensor reads wlan_num_user."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    desc = next(d for d in HEALTH_SENSORS if d.key == "wlan_num_user")
    sensor = UnifiHealthSensor(coordinator, entry, desc, "health_wlan_num_user")
    assert sensor.native_value == 101


def test_health_sensor_reads_wan2_availability() -> None:
    """UnifiHealthSensor reads wan2_availability."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    desc = next(d for d in HEALTH_SENSORS if d.key == "wan2_availability")
    sensor = UnifiHealthSensor(coordinator, entry, desc, "health_wan2_availability")
    assert sensor.native_value == pytest.approx(100.0)


def test_health_sensor_reads_www_latency() -> None:
    """UnifiHealthSensor reads www_latency."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    desc = next(d for d in HEALTH_SENSORS if d.key == "www_latency")
    sensor = UnifiHealthSensor(coordinator, entry, desc, "health_www_latency")
    assert sensor.native_value == 34


def test_health_sensor_returns_none_on_no_data() -> None:
    """UnifiHealthSensor returns None when coordinator has no data."""
    coordinator = _make_coordinator(None)
    entry = _make_entry()
    desc = next(d for d in HEALTH_SENSORS if d.key == "wan_isp_name")
    sensor = UnifiHealthSensor(coordinator, entry, desc, "health_wan_isp_name")
    assert sensor.native_value is None


def test_health_sensor_reads_lan_num_user() -> None:
    """UnifiHealthSensor reads lan_num_user."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    desc = next(d for d in HEALTH_SENSORS if d.key == "lan_num_user")
    sensor = UnifiHealthSensor(coordinator, entry, desc, "health_lan_num_user")
    assert sensor.native_value == 61


# ---------------------------------------------------------------------------
# Device sensor value extraction
# ---------------------------------------------------------------------------


def test_device_sensor_reads_ap_clients() -> None:
    """UnifiDeviceSensor reads clients count from an AP entry."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    ap_mac = "bb:cc:dd:ee:ff:00"
    desc = next(d for d in AP_SENSORS if d.key == "clients")
    sensor = UnifiDeviceSensor(coordinator, entry, desc, ap_mac)
    assert sensor.native_value == 5


def test_device_sensor_reads_switch_ports_used() -> None:
    """UnifiDeviceSensor reads ports_used from a switch entry."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    sw_mac = "cc:dd:ee:ff:00:11"
    desc = next(d for d in SWITCH_SENSORS if d.key == "ports_used")
    sensor = UnifiDeviceSensor(coordinator, entry, desc, sw_mac)
    assert sensor.native_value == 5


def test_device_sensor_returns_none_for_missing_mac() -> None:
    """UnifiDeviceSensor returns None if the device MAC is not in coordinator data."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    desc = next(d for d in AP_SENSORS if d.key == "clients")
    sensor = UnifiDeviceSensor(coordinator, entry, desc, "ff:ff:ff:ff:ff:ff")
    assert sensor.native_value is None


def test_device_sensor_returns_none_on_no_data() -> None:
    """UnifiDeviceSensor returns None when coordinator has no data."""
    coordinator = _make_coordinator(None)
    entry = _make_entry()
    desc = next(d for d in AP_SENSORS if d.key == "clients")
    sensor = UnifiDeviceSensor(coordinator, entry, desc, "bb:cc:dd:ee:ff:00")
    assert sensor.native_value is None


def test_device_sensor_reads_ap_score() -> None:
    """UnifiDeviceSensor reads score from an AP entry."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    ap_mac = "bb:cc:dd:ee:ff:00"
    desc = next(d for d in AP_SENSORS if d.key == "score")
    sensor = UnifiDeviceSensor(coordinator, entry, desc, ap_mac)
    assert sensor.native_value == 98


def test_device_sensor_reads_switch_cpu() -> None:
    """UnifiDeviceSensor reads cpu from a switch entry."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    sw_mac = "cc:dd:ee:ff:00:11"
    desc = next(d for d in SWITCH_SENSORS if d.key == "cpu")
    sensor = UnifiDeviceSensor(coordinator, entry, desc, sw_mac)
    assert sensor.native_value == pytest.approx(59.0)


# ---------------------------------------------------------------------------
# Unique ID generation
# ---------------------------------------------------------------------------


def test_gateway_sensor_unique_id() -> None:
    """Gateway sensor unique_id is entry.unique_id + '_' + key."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry("aa:bb:cc:dd:ee:ff")
    desc = next(d for d in GATEWAY_SENSORS if d.key == "cpu")
    sensor = UnifiGatewaySensor(coordinator, entry, desc, "cpu")
    assert sensor.unique_id == "aa:bb:cc:dd:ee:ff_cpu"


def test_device_sensor_unique_id() -> None:
    """Device sensor unique_id includes MAC and key."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry("aa:bb:cc:dd:ee:ff")
    ap_mac = "bb:cc:dd:ee:ff:00"
    desc = next(d for d in AP_SENSORS if d.key == "clients")
    sensor = UnifiDeviceSensor(coordinator, entry, desc, ap_mac)
    assert sensor.unique_id == f"aa:bb:cc:dd:ee:ff_{ap_mac}_clients"


def test_health_sensor_unique_id() -> None:
    """Health sensor unique_id includes health_ prefix."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry("aa:bb:cc:dd:ee:ff")
    desc = next(d for d in HEALTH_SENSORS if d.key == "wan_isp_name")
    sensor = UnifiHealthSensor(coordinator, entry, desc, "health_wan_isp_name")
    assert sensor.unique_id == "aa:bb:cc:dd:ee:ff_health_wan_isp_name"


# ---------------------------------------------------------------------------
# Platform setup
# ---------------------------------------------------------------------------


async def test_async_setup_entry_creates_all_entities(hass: Any) -> None:
    """async_setup_entry creates gateway, health, and device sensors."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    entry.runtime_data = coordinator
    async_add_entities = MagicMock()

    from custom_components.unifi_network_monitor.sensor import async_setup_entry

    await async_setup_entry(hass, entry, async_add_entities)
    entities = async_add_entities.call_args[0][0]
    num_gateway = len(GATEWAY_SENSORS)
    num_health = len(HEALTH_SENSORS)
    num_ap = len(_device_descs("ap", "all"))
    num_switch = len(_device_descs("switch", "all"))
    expected = num_gateway + num_health + num_ap + num_switch
    assert len(entities) == expected, f"Expected {expected}, got {len(entities)}"


async def test_async_setup_entry_handles_no_data(hass: Any) -> None:
    """async_setup_entry handles coordinator with no data (no device sensors)."""
    coordinator = _make_coordinator(None)
    entry = _make_entry()
    entry.runtime_data = coordinator
    async_add_entities = MagicMock()

    from custom_components.unifi_network_monitor.sensor import async_setup_entry

    await async_setup_entry(hass, entry, async_add_entities)
    entities = async_add_entities.call_args[0][0]
    num_gateway = len(GATEWAY_SENSORS)
    num_health = len(HEALTH_SENSORS)
    assert len(entities) == num_gateway + num_health


def test_base_get_value_raises_not_implemented() -> None:
    """UnifiSensorBase._get_value raises NotImplementedError."""
    import pytest

    from custom_components.unifi_network_monitor.sensor import (
        GATEWAY_SENSORS,
        UnifiSensorBase,
    )

    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    desc = next(d for d in GATEWAY_SENSORS if d.key == "cpu")
    sensor = UnifiSensorBase(coordinator, entry, desc, "cpu")
    with pytest.raises(NotImplementedError):
        sensor._get_value()


async def test_async_setup_entry_dynamic_sensor_added_on_update(
    hass: Any,
) -> None:
    """Dynamic device sensors added when coordinator discovers new MACs."""
    coordinator = _make_coordinator(
        {
            **MOCK_COORDINATOR_DATA,
            "devices": {
                "bb:cc:dd:ee:ff:00": MOCK_COORDINATOR_DATA["devices"][
                    "bb:cc:dd:ee:ff:00"
                ],
            },
        }
    )
    entry = _make_entry()
    entry.runtime_data = coordinator
    async_add_entities = MagicMock()

    from custom_components.unifi_network_monitor.sensor import async_setup_entry

    await async_setup_entry(hass, entry, async_add_entities)
    async_add_entities.reset_mock()

    coordinator.data = MOCK_COORDINATOR_DATA
    for listener in coordinator.async_add_listener.call_args_list:
        listener_cb = listener[0][0]
        listener_cb()
        break

    async_add_entities.assert_called_once()
    new_entities = async_add_entities.call_args[0][0]
    assert len(new_entities) == 5


def test_gateway_new_sensors_values() -> None:
    """New gateway sensors successfully extract values from coordinator data."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()

    for key, expected_val in [
        ("storage_used_pct", 20.3),
        ("wan_mode", "weighted"),
        ("wan1_weight", 55),
        ("wan2_weight", 45),
        ("ips_mode", "block"),
        ("wan2_sfp_vendor", "UBNT"),
        ("wan2_sfp_part", "UF-RJ45-1G"),
        ("wan2_sfp_serial", "SN0000000001"),
    ]:
        desc = next(d for d in GATEWAY_SENSORS if d.key == key)
        sensor = UnifiGatewaySensor(coordinator, entry, desc, key)
        assert sensor.native_value == expected_val, f"Failed for sensor key {key}"


def test_gateway_sensor_extra_state_attributes_udm_version() -> None:
    """Gateway 'application_version' sensor returns firmware extra attrs."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    desc = next(d for d in GATEWAY_SENSORS if d.key == "application_version")
    sensor = UnifiGatewaySensor(coordinator, entry, desc, "application_version")
    attrs = sensor.extra_state_attributes
    assert attrs is not None
    assert attrs["application_version"] == "9.2.87"
    assert attrs["application_build"] == "15432"
    assert attrs["device_type"] == "udm"
    assert attrs["udm_version"] == "3.2.12"


def test_gateway_sensor_extra_state_attributes_strongest_rogue_ssid() -> None:
    """'strongest_rogue_ssid' sensor carries the rogue AP list as extra attributes."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    desc = next(d for d in GATEWAY_SENSORS if d.key == "strongest_rogue_ssid")
    sensor = UnifiGatewaySensor(coordinator, entry, desc, "strongest_rogue_ssid")
    attrs = sensor.extra_state_attributes
    assert attrs is not None
    assert len(attrs["rogue_aps"]) == 3
    assert attrs["rogue_aps"][0]["essid"] == "RogueNet-2"
    assert attrs["rogue_aps"][0]["signal"] == -87
    assert attrs["rogue_aps"][0]["detected_by"] == ""
    assert attrs["rogue_aps"][1]["essid"] == "RogueNet-1"
    assert attrs["rogue_aps"][1]["signal"] == -89


def _rogue_data(count: int, *, with_unsignalled: bool = False) -> dict[str, Any]:
    """Build gateway data carrying ``count`` rogue APs, weakest listed first."""
    rogues: list[dict[str, Any]] = [
        {"essid": f"Rogue-{i:02d}", "signal": -(50 + i), "detected_by": ""}
        for i in reversed(range(count))
    ]
    if with_unsignalled:
        rogues.insert(0, {"essid": "Rogue-NoSignal", "detected_by": ""})
    return {"gateway": {"rogue_aps_list": rogues}}


def test_rogue_ap_attribute_is_capped_sorted_and_flagged() -> None:
    """Over the cap: 25 strongest, strongest first, truncation flagged.

    Covers finding RETVAL.1 from recommendations_20260808.md. ``rogue_aps_truncated``
    had zero occurrences in the whole test suite and ``ROGUE_ATTR_MAX`` zero test
    references, leaving three behaviours unverified at once: the cap, the flag,
    and the ordering.

    Ordering is the one that matters most. The list is 25 of a possibly much
    larger set, so if the ``signal`` sort key inverted, the attribute would
    quietly publish the 25 **weakest** rogue APs while still being the right
    length and still flagging truncation correctly. The input is built
    weakest-first so a sort that does nothing at all fails too.

    The record with no ``signal`` pins the ``-9999`` default: it must sort last
    and therefore fall outside the cap.
    """
    coordinator = _make_coordinator(_rogue_data(26, with_unsignalled=True))
    entry = _make_entry()
    desc = next(d for d in GATEWAY_SENSORS if d.key == "strongest_rogue_ssid")
    sensor = UnifiGatewaySensor(coordinator, entry, desc, "strongest_rogue_ssid")

    attrs = sensor.extra_state_attributes
    assert attrs is not None
    rogues = attrs["rogue_aps"]

    assert len(rogues) == 25
    assert attrs["rogue_aps_truncated"] is True
    assert rogues[0]["essid"] == "Rogue-00"
    assert [r["signal"] for r in rogues] == sorted(
        (r["signal"] for r in rogues), reverse=True
    )
    assert "Rogue-NoSignal" not in {r["essid"] for r in rogues}


def test_rogue_ap_attribute_at_exactly_the_cap_is_not_flagged() -> None:
    """Exactly at the cap: every AP is kept and truncation reads False.

    Covers finding RETVAL.1 from recommendations_20260808.md — the boundary
    beside the flag, since ``len(rogues) > ROGUE_ATTR_MAX`` is the condition and
    only the far-over case was reachable before.
    """
    coordinator = _make_coordinator(_rogue_data(25))
    entry = _make_entry()
    desc = next(d for d in GATEWAY_SENSORS if d.key == "strongest_rogue_ssid")
    sensor = UnifiGatewaySensor(coordinator, entry, desc, "strongest_rogue_ssid")

    attrs = sensor.extra_state_attributes
    assert attrs is not None

    assert len(attrs["rogue_aps"]) == 25
    assert attrs["rogue_aps_truncated"] is False


def test_gateway_sensor_rogue_ap_count_has_no_attributes() -> None:
    """The rogue count sensor no longer exposes the rogue AP list (moved to SSID)."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    desc = next(d for d in GATEWAY_SENSORS if d.key == "rogue_ap_count")
    sensor = UnifiGatewaySensor(coordinator, entry, desc, "rogue_ap_count")
    attrs = sensor.extra_state_attributes
    assert attrs is not None
    assert "about" in attrs
    assert "rogue_aps" not in attrs


def test_gateway_strongest_rogue_sensors_values() -> None:
    """Strongest Rogue SSID/RSSI sensors return the strongest rogue's fields."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    ssid_desc = next(d for d in GATEWAY_SENSORS if d.key == "strongest_rogue_ssid")
    rssi_desc = next(d for d in GATEWAY_SENSORS if d.key == "strongest_rogue_rssi")
    ssid = UnifiGatewaySensor(coordinator, entry, ssid_desc, "strongest_rogue_ssid")
    rssi = UnifiGatewaySensor(coordinator, entry, rssi_desc, "strongest_rogue_rssi")
    assert ssid.native_value == "RogueNet-2"
    assert rssi.native_value == -87


def test_gateway_strongest_rogue_sensors_no_rogues() -> None:
    """With no rogues, SSID reads 'None Detected' and RSSI is None (unknown)."""
    data = {
        **MOCK_COORDINATOR_DATA,
        "gateway": {
            **MOCK_COORDINATOR_DATA["gateway"],
            "strongest_rogue_ssid": "None Detected",
            "strongest_rogue_rssi": None,
        },
    }
    coordinator = _make_coordinator(data)
    entry = _make_entry()
    ssid_desc = next(d for d in GATEWAY_SENSORS if d.key == "strongest_rogue_ssid")
    rssi_desc = next(d for d in GATEWAY_SENSORS if d.key == "strongest_rogue_rssi")
    ssid = UnifiGatewaySensor(coordinator, entry, ssid_desc, "strongest_rogue_ssid")
    rssi = UnifiGatewaySensor(coordinator, entry, rssi_desc, "strongest_rogue_rssi")
    assert ssid.native_value == "None Detected"
    # None -> HA renders "unknown" (not "unavailable", not 0).
    assert rssi.native_value is None


def test_gateway_sensor_extra_state_attributes_other() -> None:
    """Gateway sensor without special extra attributes returns None."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    desc = next(d for d in GATEWAY_SENSORS if d.key == "cpu")
    sensor = UnifiGatewaySensor(coordinator, entry, desc, "cpu")
    assert sensor.extra_state_attributes is None


def test_gateway_sensor_extra_state_attributes_no_data() -> None:
    """Gateway sensor extra_state_attributes is None when no coordinator data."""
    coordinator = _make_coordinator(None)
    entry = _make_entry()
    desc = next(d for d in GATEWAY_SENSORS if d.key == "application_version")
    sensor = UnifiGatewaySensor(coordinator, entry, desc, "application_version")
    assert sensor.extra_state_attributes is None


def test_device_sensor_device_info() -> None:
    """UnifiDeviceSensor device_info returns device info for the device."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    ap_mac = "bb:cc:dd:ee:ff:00"
    desc = next(d for d in AP_SENSORS if d.key == "clients")
    sensor = UnifiDeviceSensor(coordinator, entry, desc, ap_mac)
    info = sensor.device_info
    assert info is not None


def test_device_sensor_standalone_enabled_default() -> None:
    """Standalone sensor returns True for entity_registry_enabled_default."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    ap_mac = "bb:cc:dd:ee:ff:00"
    desc = next(d for d in AP_SENSORS if d.key == "clients")
    sensor = UnifiDeviceSensor(coordinator, entry, desc, ap_mac, standalone=True)
    assert sensor.entity_registry_enabled_default is True


def test_device_sensor_non_standalone_enabled_default() -> None:
    """UnifiDeviceSensor with standalone=False falls through to description default."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    ap_mac = "bb:cc:dd:ee:ff:00"
    desc = next(d for d in AP_SENSORS if d.key == "clients")
    sensor = UnifiDeviceSensor(coordinator, entry, desc, ap_mac)
    assert sensor.entity_registry_enabled_default is False


# ---------------------------------------------------------------------------
# _device_descs coverage
# ---------------------------------------------------------------------------


def test_device_descs_mode_none() -> None:
    """_device_descs returns empty tuple for mode='none'."""
    result = _device_descs("ap", "none")
    assert result == ()


def test_device_descs_ap_sensors() -> None:
    """_device_descs returns AP_SENSORS for ap type with mode='all'."""
    result = _device_descs("ap", "all")
    assert len(result) > 0
    keys = {d.key for d in result}
    assert "clients" in keys
    assert "cpu" in keys
    assert "score" in keys


def test_device_descs_switch_sensors() -> None:
    """_device_descs returns SWITCH_SENSORS for switch type with mode='all'."""
    result = _device_descs("switch", "all")
    assert len(result) > 0
    keys = {d.key for d in result}
    assert "ports_used" in keys
    assert "cpu" in keys


def test_device_descs_satisfaction_mode() -> None:
    """_device_descs returns only satisfaction keys for mode='satisfaction_only'."""
    from custom_components.unifi_network_monitor.sensor import _SATISFACTION_KEYS

    result = _device_descs("ap", "satisfaction_only")
    assert len(result) > 0
    keys = {d.key for d in result}
    for k in _SATISFACTION_KEYS:
        assert k in keys
    assert "clients" not in keys
    assert "cpu" not in keys


def test_device_descs_switch_satisfaction_no_keys() -> None:
    """_device_descs empty for switch when satisfaction only."""
    result = _device_descs("switch", "satisfaction_only")
    assert result == ()
