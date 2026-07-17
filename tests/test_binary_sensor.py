"""Tests for the UniFi Network Monitor binary sensor platform."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from custom_components.unifi_network_monitor.binary_sensor import (
    DEVICE_BINARY_SENSORS,
    GATEWAY_BINARY_SENSORS,
    HEALTH_BINARY_SENSORS,
    UnifiDeviceBinarySensor,
    UnifiGatewayBinarySensor,
    UnifiHealthBinarySensor,
    UnifiRogueProximityBinarySensor,
    UnifiVpnBinarySensor,
    UnifiWifiBinarySensor,
)
from custom_components.unifi_network_monitor.const import (
    CONF_ENABLE_SECURITY_MONITORING,
    CONF_ENABLE_SPEEDTEST,
    CONF_ENABLE_WAN_USAGE,
    CONF_ROGUE_PROXIMITY_RSSI_THRESHOLD,
    CONF_UNIFI_DEVICE_MODE,
)

from .conftest import MOCK_COORDINATOR_DATA, MOCK_MAC

# ---------------------------------------------------------------------------
# Helpers
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
# Gateway binary sensors
# ---------------------------------------------------------------------------


def test_gateway_internet_is_on_when_true() -> None:
    """Internet binary sensor is on when coordinator reports True."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    desc = next(d for d in GATEWAY_BINARY_SENSORS if d.key == "internet")
    sensor = UnifiGatewayBinarySensor(coordinator, entry, desc, "internet")
    assert sensor.is_on is True


def test_gateway_internet_is_off_when_false() -> None:
    """Internet binary sensor is off when coordinator reports False."""
    data = {
        **MOCK_COORDINATOR_DATA,
        "gateway": {**MOCK_COORDINATOR_DATA["gateway"], "internet": False},
    }
    coordinator = _make_coordinator(data)
    entry = _make_entry()
    desc = next(d for d in GATEWAY_BINARY_SENSORS if d.key == "internet")
    sensor = UnifiGatewayBinarySensor(coordinator, entry, desc, "internet")
    assert sensor.is_on is False


def test_gateway_update_available_false() -> None:
    """update_available binary sensor is off when no update is pending."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    desc = next(d for d in GATEWAY_BINARY_SENSORS if d.key == "update_available")
    sensor = UnifiGatewayBinarySensor(coordinator, entry, desc, "update_available")
    assert sensor.is_on is False


def test_gateway_binary_sensor_returns_none_when_no_data() -> None:
    """Gateway binary sensor returns empty dict and is_on is None-ish when no data."""
    coordinator = _make_coordinator(None)
    entry = _make_entry()
    desc = next(d for d in GATEWAY_BINARY_SENSORS if d.key == "internet")
    sensor = UnifiGatewayBinarySensor(coordinator, entry, desc, "internet")
    assert sensor.is_on is None


def test_health_speedtest_pass_when_success() -> None:
    """speedtest_pass PROBLEM sensor is OFF when speedtest succeeded."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    desc = next(d for d in HEALTH_BINARY_SENSORS if d.key == "speedtest_pass")
    sensor = UnifiHealthBinarySensor(coordinator, entry, desc, "health_speedtest_pass")
    assert sensor.is_on is False


def test_health_speedtest_pass_when_failed() -> None:
    """speedtest_pass PROBLEM sensor is ON when speedtest failed."""
    data = {
        **MOCK_COORDINATOR_DATA,
        "health": {**MOCK_COORDINATOR_DATA["health"], "www_speedtest_status": "Failed"},
    }
    coordinator = _make_coordinator(data)
    entry = _make_entry()
    desc = next(d for d in HEALTH_BINARY_SENSORS if d.key == "speedtest_pass")
    sensor = UnifiHealthBinarySensor(coordinator, entry, desc, "health_speedtest_pass")
    assert sensor.is_on is True


def test_health_speedtest_pass_unknown_when_empty() -> None:
    """speedtest_pass is unknown (None), not a problem, when status is empty."""
    data = {
        **MOCK_COORDINATOR_DATA,
        "health": {**MOCK_COORDINATOR_DATA["health"], "www_speedtest_status": ""},
    }
    coordinator = _make_coordinator(data)
    entry = _make_entry()
    desc = next(d for d in HEALTH_BINARY_SENSORS if d.key == "speedtest_pass")
    sensor = UnifiHealthBinarySensor(coordinator, entry, desc, "health_speedtest_pass")
    assert sensor.is_on is None


# ---------------------------------------------------------------------------
# Health all_ok binary sensor — inverted PROBLEM logic
# ---------------------------------------------------------------------------


def test_health_all_ok_is_off_when_everything_healthy() -> None:
    """all_ok PROBLEM sensor is OFF (no problem) when all subsystems are ok."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    desc = next(d for d in HEALTH_BINARY_SENSORS if d.key == "all_ok")
    sensor = UnifiHealthBinarySensor(coordinator, entry, desc, "health_all_ok")
    assert sensor.is_on is False


def test_health_all_ok_is_on_when_wan_down() -> None:
    """all_ok PROBLEM sensor is ON (problem detected) when wan_status != ok."""
    health = {**MOCK_COORDINATOR_DATA["health"], "wan_status": "error"}
    data = {**MOCK_COORDINATOR_DATA, "health": health}
    coordinator = _make_coordinator(data)
    entry = _make_entry()
    desc = next(d for d in HEALTH_BINARY_SENSORS if d.key == "all_ok")
    sensor = UnifiHealthBinarySensor(coordinator, entry, desc, "health_all_ok")
    assert sensor.is_on is True


def test_health_all_ok_is_on_when_wlan_down() -> None:
    """all_ok PROBLEM sensor is ON when wlan_status is not ok."""
    health = {**MOCK_COORDINATOR_DATA["health"], "wlan_status": "alert"}
    data = {**MOCK_COORDINATOR_DATA, "health": health}
    coordinator = _make_coordinator(data)
    entry = _make_entry()
    desc = next(d for d in HEALTH_BINARY_SENSORS if d.key == "all_ok")
    sensor = UnifiHealthBinarySensor(coordinator, entry, desc, "health_all_ok")
    assert sensor.is_on is True


def test_health_wan_ok_reads_status() -> None:
    """wan_ok CONNECTIVITY sensor is on when wan_status == ok."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    desc = next(d for d in HEALTH_BINARY_SENSORS if d.key == "wan_ok")
    sensor = UnifiHealthBinarySensor(coordinator, entry, desc, "health_wan_ok")
    assert sensor.is_on is True


def test_health_www_ok_reads_status() -> None:
    """www_ok CONNECTIVITY sensor is on when www_status == ok."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    desc = next(d for d in HEALTH_BINARY_SENSORS if d.key == "www_ok")
    sensor = UnifiHealthBinarySensor(coordinator, entry, desc, "health_www_ok")
    assert sensor.is_on is True


def test_health_wlan_ok_reads_status() -> None:
    """wlan_ok CONNECTIVITY sensor is on when wlan_status == ok."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    desc = next(d for d in HEALTH_BINARY_SENSORS if d.key == "wlan_ok")
    sensor = UnifiHealthBinarySensor(coordinator, entry, desc, "health_wlan_ok")
    assert sensor.is_on is True


def test_health_lan_ok_reads_status() -> None:
    """lan_ok CONNECTIVITY sensor is on when lan_status == ok."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    desc = next(d for d in HEALTH_BINARY_SENSORS if d.key == "lan_ok")
    sensor = UnifiHealthBinarySensor(coordinator, entry, desc, "health_lan_ok")
    assert sensor.is_on is True


def test_health_sensors_return_none_on_no_data() -> None:
    """Health all_ok sensor is on (problem) when coordinator has no data."""
    coordinator = _make_coordinator(None)
    entry = _make_entry()
    desc = next(d for d in HEALTH_BINARY_SENSORS if d.key == "all_ok")
    sensor = UnifiHealthBinarySensor(coordinator, entry, desc, "health_all_ok")
    assert sensor.is_on is True


# ---------------------------------------------------------------------------
# Device binary sensors
# ---------------------------------------------------------------------------


def test_device_update_available_false() -> None:
    """AP update_available binary sensor is off when no update pending."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    ap_mac = "bb:cc:dd:ee:ff:00"
    desc = next(d for d in DEVICE_BINARY_SENSORS if d.key == "update_available")
    sensor = UnifiDeviceBinarySensor(coordinator, entry, desc, ap_mac)
    assert sensor.is_on is False


def test_device_update_available_true() -> None:
    """AP update_available binary sensor is on when update is pending."""
    ap = {
        **MOCK_COORDINATOR_DATA["devices"]["bb:cc:dd:ee:ff:00"],
        "update_available": True,
    }
    devices = {**MOCK_COORDINATOR_DATA["devices"], "bb:cc:dd:ee:ff:00": ap}
    data = {**MOCK_COORDINATOR_DATA, "devices": devices}
    coordinator = _make_coordinator(data)
    entry = _make_entry()
    ap_mac = "bb:cc:dd:ee:ff:00"
    desc = next(d for d in DEVICE_BINARY_SENSORS if d.key == "update_available")
    sensor = UnifiDeviceBinarySensor(coordinator, entry, desc, ap_mac)
    assert sensor.is_on is True


def test_device_binary_sensor_missing_mac_returns_none() -> None:
    """Device binary sensor returns None-valued result for unknown MAC."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    desc = next(d for d in DEVICE_BINARY_SENSORS if d.key == "update_available")
    sensor = UnifiDeviceBinarySensor(coordinator, entry, desc, "ff:ff:ff:ff:ff:ff")
    assert sensor.is_on is None


def test_device_binary_sensor_returns_none_when_no_data() -> None:
    """Device binary sensor returns None when coordinator has no data."""
    coordinator = _make_coordinator(None)
    entry = _make_entry()
    desc = next(d for d in DEVICE_BINARY_SENSORS if d.key == "update_available")
    sensor = UnifiDeviceBinarySensor(coordinator, entry, desc, "bb:cc:dd:ee:ff:00")
    assert sensor.is_on is None


# ---------------------------------------------------------------------------
# Unique ID generation
# ---------------------------------------------------------------------------


def test_gateway_binary_sensor_unique_id() -> None:
    """Gateway binary sensor unique_id is entry.unique_id + '_' + key."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry("aa:bb:cc:dd:ee:ff")
    desc = next(d for d in GATEWAY_BINARY_SENSORS if d.key == "internet")
    sensor = UnifiGatewayBinarySensor(coordinator, entry, desc, "internet")
    assert sensor.unique_id == "aa:bb:cc:dd:ee:ff_internet"


def test_device_binary_sensor_unique_id() -> None:
    """Device binary sensor unique_id includes MAC and key."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry("aa:bb:cc:dd:ee:ff")
    ap_mac = "bb:cc:dd:ee:ff:00"
    desc = next(d for d in DEVICE_BINARY_SENSORS if d.key == "update_available")
    sensor = UnifiDeviceBinarySensor(coordinator, entry, desc, ap_mac)
    assert sensor.unique_id == f"aa:bb:cc:dd:ee:ff_{ap_mac}_update_available"


def test_health_binary_sensor_unique_id() -> None:
    """Health binary sensor unique_id includes health_ prefix."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry("aa:bb:cc:dd:ee:ff")
    desc = next(d for d in HEALTH_BINARY_SENSORS if d.key == "all_ok")
    sensor = UnifiHealthBinarySensor(coordinator, entry, desc, "health_all_ok")
    assert sensor.unique_id == "aa:bb:cc:dd:ee:ff_health_all_ok"


# ---------------------------------------------------------------------------
# Platform setup
# ---------------------------------------------------------------------------


async def test_async_setup_entry_creates_entities(hass: Any) -> None:
    """async_setup_entry creates gateway, health, and device binary sensors."""
    data = {
        **MOCK_COORDINATOR_DATA,
        "gateway": {
            **MOCK_COORDINATOR_DATA["gateway"],
            "wifi_states": {"Home_WiFi": True, "Guest_WiFi": False},
            "vpn_states": {"OfficeTunnel": True, "BackupTunnel": False},
        },
    }
    coordinator = _make_coordinator(data)
    entry = _make_entry()
    entry.runtime_data = coordinator
    async_add_entities = MagicMock()

    from custom_components.unifi_network_monitor.binary_sensor import (
        async_setup_entry,
    )

    await async_setup_entry(hass, entry, async_add_entities)
    async_add_entities.assert_called_once()
    entities = async_add_entities.call_args[0][0]
    num_gateway = len(GATEWAY_BINARY_SENSORS)
    num_health = len(HEALTH_BINARY_SENSORS)
    num_device = len(MOCK_COORDINATOR_DATA["devices"]) * len(DEVICE_BINARY_SENSORS)
    num_wifi = 2
    num_vpn = 2
    num_proximity = 1  # static Rogue AP Proximity Alert
    num_integration_health = 1  # always-created Integration Health sensor
    assert len(entities) == (
        num_gateway
        + num_health
        + num_device
        + num_wifi
        + num_vpn
        + num_proximity
        + num_integration_health
    )


async def test_async_setup_entry_handles_no_data(hass: Any) -> None:
    """async_setup_entry handles coordinator with no data."""
    coordinator = _make_coordinator(None)
    entry = _make_entry()
    entry.runtime_data = coordinator
    async_add_entities = MagicMock()

    from custom_components.unifi_network_monitor.binary_sensor import (
        async_setup_entry,
    )

    await async_setup_entry(hass, entry, async_add_entities)
    entities = async_add_entities.call_args[0][0]
    num_gateway = len(GATEWAY_BINARY_SENSORS)
    num_health = len(HEALTH_BINARY_SENSORS)
    # +1 Rogue AP Proximity Alert, +1 Integration Health (both always created).
    assert len(entities) == num_gateway + num_health + 2


def test_base_raw_data_raises_not_implemented() -> None:
    """UnifiBinarySensorBase._raw_data raises NotImplementedError."""
    import pytest

    from custom_components.unifi_network_monitor.binary_sensor import (
        UnifiBinarySensorBase,
    )

    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    desc = next(d for d in GATEWAY_BINARY_SENSORS if d.key == "internet")
    sensor = UnifiBinarySensorBase(coordinator, entry, desc, "internet")
    with pytest.raises(NotImplementedError):
        sensor._raw_data()


async def test_async_setup_entry_dynamic_entity_added_on_update(
    hass: Any,
) -> None:
    """Dynamic device entities are added when coordinator update discovers new MACs."""
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

    from custom_components.unifi_network_monitor.binary_sensor import (
        async_setup_entry,
    )

    await async_setup_entry(hass, entry, async_add_entities)
    async_add_entities.reset_mock()

    coordinator.data = MOCK_COORDINATOR_DATA
    for listener in coordinator.async_add_listener.call_args_list:
        listener_cb = listener[0][0]
        listener_cb()
        break

    async_add_entities.assert_called_once()
    new_entities = async_add_entities.call_args[0][0]
    assert len(new_entities) == 1


def test_gateway_new_binary_sensors_values() -> None:
    """New gateway binary sensors successfully extract values from coordinator data."""
    from custom_components.unifi_network_monitor.binary_sensor import (
        UnifiGatewayBinarySensor,
    )

    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()

    for key, expected_val in [
        ("wan1_active", True),
        ("wan2_active", False),
        ("wan1_up", True),
        ("wan2_up", True),
        ("ad_blocking", True),
        ("honeypot", True),
    ]:
        desc = next(d for d in GATEWAY_BINARY_SENSORS if d.key == key)
        sensor = UnifiGatewayBinarySensor(coordinator, entry, desc, key)
        assert sensor.is_on == expected_val, f"Failed for binary sensor key {key}"


def test_device_binary_sensor_device_info_returns_info() -> None:
    """UnifiDeviceBinarySensor device_info returns device info."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    ap_mac = "bb:cc:dd:ee:ff:00"
    desc = next(d for d in DEVICE_BINARY_SENSORS if d.key == "update_available")
    sensor = UnifiDeviceBinarySensor(coordinator, entry, desc, ap_mac)
    info = sensor.device_info
    assert info is not None


def test_device_binary_sensor_device_info_no_data() -> None:
    """UnifiDeviceBinarySensor device_info handles missing coordinator data."""
    coordinator = _make_coordinator(None)
    entry = _make_entry()
    ap_mac = "bb:cc:dd:ee:ff:00"
    desc = next(d for d in DEVICE_BINARY_SENSORS if d.key == "update_available")
    sensor = UnifiDeviceBinarySensor(coordinator, entry, desc, ap_mac)
    info = sensor.device_info
    assert info is not None


def test_device_binary_sensor_standalone_enabled_default() -> None:
    """UnifiDeviceBinarySensor with standalone=True returns True."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    ap_mac = "bb:cc:dd:ee:ff:00"
    desc = next(d for d in DEVICE_BINARY_SENSORS if d.key == "update_available")
    sensor = UnifiDeviceBinarySensor(coordinator, entry, desc, ap_mac, standalone=True)
    assert sensor.entity_registry_enabled_default is True


def test_device_binary_sensor_non_standalone_enabled_default() -> None:
    """Non-standalone binary sensor uses description default."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    ap_mac = "bb:cc:dd:ee:ff:00"
    desc = next(d for d in DEVICE_BINARY_SENSORS if d.key == "update_available")
    sensor = UnifiDeviceBinarySensor(coordinator, entry, desc, ap_mac)
    assert sensor.entity_registry_enabled_default is False


# ---------------------------------------------------------------------------
# WiFi and VPN binary sensor tests
# ---------------------------------------------------------------------------


def test_wifi_binary_sensor_is_on() -> None:
    """UnifiWifiBinarySensor returns True for enabled SSID."""
    data = {
        **MOCK_COORDINATOR_DATA,
        "gateway": {
            **MOCK_COORDINATOR_DATA["gateway"],
            "wifi_states": {"Home_WiFi": True, "Guest_WiFi": False},
        },
    }
    coordinator = _make_coordinator(data)
    entry = _make_entry()
    sensor = UnifiWifiBinarySensor(coordinator, entry, "Home_WiFi")
    assert sensor.is_on is True
    assert sensor.unique_id == f"{MOCK_MAC}_wifi_home_wifi"


def test_wifi_binary_sensor_is_off() -> None:
    """UnifiWifiBinarySensor returns False for disabled SSID."""
    data = {
        **MOCK_COORDINATOR_DATA,
        "gateway": {
            **MOCK_COORDINATOR_DATA["gateway"],
            "wifi_states": {"Guest_WiFi": False},
        },
    }
    coordinator = _make_coordinator(data)
    entry = _make_entry()
    sensor = UnifiWifiBinarySensor(coordinator, entry, "Guest_WiFi")
    assert sensor.is_on is False


def test_wifi_binary_sensor_no_coordinator_data() -> None:
    """UnifiWifiBinarySensor returns None when coordinator has no data."""
    coordinator = _make_coordinator(None)
    entry = _make_entry()
    sensor = UnifiWifiBinarySensor(coordinator, entry, "Home_WiFi")
    assert sensor.is_on is None


def test_vpn_binary_sensor_is_on() -> None:
    """UnifiVpnBinarySensor returns True for connected tunnel."""
    data = {
        **MOCK_COORDINATOR_DATA,
        "gateway": {
            **MOCK_COORDINATOR_DATA["gateway"],
            "vpn_states": {"OfficeTunnel": True, "BackupTunnel": False},
        },
    }
    coordinator = _make_coordinator(data)
    entry = _make_entry()
    sensor = UnifiVpnBinarySensor(coordinator, entry, "OfficeTunnel")
    assert sensor.is_on is True
    assert sensor.unique_id == f"{MOCK_MAC}_vpn_officetunnel"


def test_vpn_binary_sensor_is_off() -> None:
    """UnifiVpnBinarySensor returns False for disconnected tunnel."""
    data = {
        **MOCK_COORDINATOR_DATA,
        "gateway": {
            **MOCK_COORDINATOR_DATA["gateway"],
            "vpn_states": {"BackupTunnel": False},
        },
    }
    coordinator = _make_coordinator(data)
    entry = _make_entry()
    sensor = UnifiVpnBinarySensor(coordinator, entry, "BackupTunnel")
    assert sensor.is_on is False


def test_vpn_binary_sensor_no_coordinator_data() -> None:
    """UnifiVpnBinarySensor returns None when coordinator has no data."""
    coordinator = _make_coordinator(None)
    entry = _make_entry()
    sensor = UnifiVpnBinarySensor(coordinator, entry, "OfficeTunnel")
    assert sensor.is_on is None


def test_wifi_binary_sensor_device_info() -> None:
    """UnifiWifiBinarySensor device_info returns Status sub-device info."""
    data = {
        **MOCK_COORDINATOR_DATA,
        "gateway": {
            **MOCK_COORDINATOR_DATA["gateway"],
            "wifi_states": {"Home_WiFi": True},
        },
    }
    coordinator = _make_coordinator(data)
    entry = _make_entry()
    sensor = UnifiWifiBinarySensor(coordinator, entry, "Home_WiFi")
    info = sensor.device_info
    assert info is not None


def test_vpn_binary_sensor_device_info() -> None:
    """UnifiVpnBinarySensor device_info returns Status sub-device info."""
    data = {
        **MOCK_COORDINATOR_DATA,
        "gateway": {
            **MOCK_COORDINATOR_DATA["gateway"],
            "vpn_states": {"OfficeTunnel": True},
        },
    }
    coordinator = _make_coordinator(data)
    entry = _make_entry()
    sensor = UnifiVpnBinarySensor(coordinator, entry, "OfficeTunnel")
    info = sensor.device_info
    assert info is not None


# ---------------------------------------------------------------------------
# Unique-id de-duplication for dynamic WiFi/VPN names
# ---------------------------------------------------------------------------


def test_dedup_suffix_appends_counter() -> None:
    """_dedup_suffix returns the base, then base_2, base_3 for repeats."""
    from custom_components.unifi_network_monitor.binary_sensor import _dedup_suffix

    used: set[str] = set()
    assert _dedup_suffix("wifi_home", used) == "wifi_home"
    assert _dedup_suffix("wifi_home", used) == "wifi_home_2"
    assert _dedup_suffix("wifi_home", used) == "wifi_home_3"


async def test_async_setup_entry_dedups_colliding_wifi_slugs(hass: Any) -> None:
    """Two SSIDs that slugify identically still get distinct unique_ids."""
    data = {
        **MOCK_COORDINATOR_DATA,
        "gateway": {
            **MOCK_COORDINATOR_DATA["gateway"],
            # "Guest WiFi" and "Guest-WiFi" both slugify to "guest_wifi".
            "wifi_states": {"Guest WiFi": True, "Guest-WiFi": False},
            "vpn_states": {},
        },
    }
    coordinator = _make_coordinator(data)
    entry = _make_entry()
    entry.runtime_data = coordinator
    async_add_entities = MagicMock()

    from custom_components.unifi_network_monitor.binary_sensor import async_setup_entry

    await async_setup_entry(hass, entry, async_add_entities)
    entities = async_add_entities.call_args[0][0]
    wifi_ids = [e.unique_id for e in entities if isinstance(e, UnifiWifiBinarySensor)]
    assert len(wifi_ids) == 2
    assert len(set(wifi_ids)) == 2  # both unique despite identical slugs
    assert f"{MOCK_MAC}_wifi_guest_wifi" in wifi_ids
    assert f"{MOCK_MAC}_wifi_guest_wifi_2" in wifi_ids


# ---------------------------------------------------------------------------
# Dynamic entity creation on coordinator update
# ---------------------------------------------------------------------------


async def test_async_setup_entry_dynamic_wifi_vpn_added_on_update(
    hass: Any,
) -> None:
    """Dynamic WiFi and VPN entities are added when new SSIDs/tunnels appear."""
    data = {
        **MOCK_COORDINATOR_DATA,
        "gateway": {
            **MOCK_COORDINATOR_DATA["gateway"],
            "wifi_states": {"Existing_WiFi": True},
            "vpn_states": {"Existing_Tunnel": True},
        },
    }
    coordinator = _make_coordinator(data)
    entry = _make_entry()
    entry.runtime_data = coordinator
    async_add_entities = MagicMock()

    from custom_components.unifi_network_monitor.binary_sensor import (
        async_setup_entry,
    )

    await async_setup_entry(hass, entry, async_add_entities)
    async_add_entities.reset_mock()

    # Update with new SSID and new tunnel
    coordinator.data = {
        **MOCK_COORDINATOR_DATA,
        "gateway": {
            **MOCK_COORDINATOR_DATA["gateway"],
            "wifi_states": {"Existing_WiFi": True, "New_WiFi": True},
            "vpn_states": {"Existing_Tunnel": True, "New_Tunnel": False},
        },
    }
    for listener in coordinator.async_add_listener.call_args_list:
        listener_cb = listener[0][0]
        listener_cb()
        break

    async_add_entities.assert_called_once()
    new_entities = async_add_entities.call_args[0][0]
    assert len(new_entities) == 2  # one WiFi, one VPN


async def test_async_setup_entry_update_with_no_data_skips(
    hass: Any,
) -> None:
    """Coordinator update callback returns early when data is None."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    entry.runtime_data = coordinator
    async_add_entities = MagicMock()

    from custom_components.unifi_network_monitor.binary_sensor import (
        async_setup_entry,
    )

    await async_setup_entry(hass, entry, async_add_entities)
    async_add_entities.reset_mock()

    coordinator.data = None
    for listener in coordinator.async_add_listener.call_args_list:
        listener_cb = listener[0][0]
        listener_cb()
        break

    async_add_entities.assert_not_called()


# ---------------------------------------------------------------------------
# Standalone mode tests
# ---------------------------------------------------------------------------


def test_gateway_binary_sensor_standalone_enables_update() -> None:
    """Gateway binary sensor in standalone enables update_available by default."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    desc = next(d for d in GATEWAY_BINARY_SENSORS if d.key == "update_available")
    sensor = UnifiGatewayBinarySensor(
        coordinator, entry, desc, "update_available", standalone=True
    )
    assert sensor.entity_registry_enabled_default is True


# ---------------------------------------------------------------------------
# Rogue AP Proximity Alert
# ---------------------------------------------------------------------------


def _rogue_data(rssi: int | None) -> dict[str, Any]:
    """Return coordinator data with a given strongest_rogue_rssi."""
    return {
        **MOCK_COORDINATOR_DATA,
        "gateway": {
            **MOCK_COORDINATOR_DATA["gateway"],
            "strongest_rogue_rssi": rssi,
        },
    }


def test_rogue_proximity_off_below_default_threshold() -> None:
    """Weak rogue (-87 dBm) stays below the default -60 threshold -> off."""
    coordinator = _make_coordinator(_rogue_data(-87))
    sensor = UnifiRogueProximityBinarySensor(coordinator, _make_entry())
    assert sensor.is_on is False


def test_rogue_proximity_on_above_default_threshold() -> None:
    """Strong rogue (-50 dBm) is at/above the default -60 threshold -> on."""
    coordinator = _make_coordinator(_rogue_data(-50))
    sensor = UnifiRogueProximityBinarySensor(coordinator, _make_entry())
    assert sensor.is_on is True


def test_rogue_proximity_off_when_no_rogue() -> None:
    """No rogue signal (None) never triggers the alert."""
    coordinator = _make_coordinator(_rogue_data(None))
    sensor = UnifiRogueProximityBinarySensor(coordinator, _make_entry())
    assert sensor.is_on is False


def test_rogue_proximity_respects_custom_threshold() -> None:
    """A configured threshold in options overrides the default."""
    coordinator = _make_coordinator(_rogue_data(-87))
    entry = _make_entry()
    entry.options = {"host": "192.168.1.1", CONF_ROGUE_PROXIMITY_RSSI_THRESHOLD: -90}
    sensor = UnifiRogueProximityBinarySensor(coordinator, entry)
    # -87 >= -90 -> on
    assert sensor.is_on is True


def test_rogue_proximity_attributes() -> None:
    """Attributes expose the strongest RSSI and the active threshold."""
    coordinator = _make_coordinator(_rogue_data(-87))
    sensor = UnifiRogueProximityBinarySensor(coordinator, _make_entry())
    attrs = sensor.extra_state_attributes
    assert attrs["strongest_rogue_rssi"] == -87
    assert attrs["threshold"] == -60


# ---------------------------------------------------------------------------
# _source_endpoint coverage
# ---------------------------------------------------------------------------


def test_wifi_binary_sensor_source_endpoint() -> None:
    """UnifiWifiBinarySensor._source_endpoint returns EP_WLAN."""
    from custom_components.unifi_network_monitor.const import EP_WLAN

    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    sensor = UnifiWifiBinarySensor(coordinator, entry, "TestWiFi")
    assert sensor._source_endpoint() == EP_WLAN


def test_vpn_binary_sensor_source_endpoint() -> None:
    """UnifiVpnBinarySensor._source_endpoint returns EP_VPN_TUNNELS."""
    from custom_components.unifi_network_monitor.const import EP_VPN_TUNNELS

    data = {
        **MOCK_COORDINATOR_DATA,
        "gateway": {
            **MOCK_COORDINATOR_DATA["gateway"],
            "vpn_states": {"TestTunnel": True},
        },
    }
    coordinator = _make_coordinator(data)
    entry = _make_entry()
    sensor = UnifiVpnBinarySensor(coordinator, entry, "TestTunnel")
    assert sensor._source_endpoint() == EP_VPN_TUNNELS


# ---------------------------------------------------------------------------
# Integration Health binary sensor
# ---------------------------------------------------------------------------


def test_integration_health_on_with_attributes() -> None:
    """Health sensor is on and exposes the issue detail when a problem exists."""
    from custom_components.unifi_network_monitor.binary_sensor import (
        UnifiIntegrationHealthBinarySensor,
    )

    health = {
        "problem": True,
        "severity": "serious",
        "issues": ["Rogue APs data looks malformed (possible controller update)"],
        "degraded_capabilities": [],
        "drift": ["Rogue APs"],
        "auth_mode": "api_key",
        "v3_available": True,
        "last_good_update": "2026-07-17T12:00:00+00:00",
    }
    coordinator = _make_coordinator({"integration_health": health})
    sensor = UnifiIntegrationHealthBinarySensor(coordinator, _make_entry())
    assert sensor.is_on is True
    attrs = sensor.extra_state_attributes or {}
    assert attrs["severity"] == "serious"
    assert attrs["drift"] == ["Rogue APs"]
    assert "about" in attrs  # About note included


def test_integration_health_off_when_healthy() -> None:
    """Health sensor is off when no problem is reported."""
    from custom_components.unifi_network_monitor.binary_sensor import (
        UnifiIntegrationHealthBinarySensor,
    )

    coordinator = _make_coordinator({"integration_health": {"problem": False}})
    sensor = UnifiIntegrationHealthBinarySensor(coordinator, _make_entry())
    assert sensor.is_on is False
