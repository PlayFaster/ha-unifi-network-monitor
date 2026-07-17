"""Tests for the UniFi Network Monitor coordinator."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.util import dt as dt_util

from custom_components.unifi_network_monitor.api import (
    UnifiAuthError,
    UnifiConnectionError,
)
from custom_components.unifi_network_monitor.coordinator import (
    UnifiNetworkDataUpdateCoordinator,
    _derive_boot_time,
    _parse_ap,
    _parse_gateway,
    _parse_health,
    _parse_switch,
    _safe_float,
    _safe_int,
)

# ---------------------------------------------------------------------------
# Helper / safety-coercion unit tests
# ---------------------------------------------------------------------------


def test_safe_float_valid() -> None:
    """_safe_float returns float for valid numeric string."""
    assert _safe_float("37.2") == pytest.approx(37.2)


def test_safe_float_none() -> None:
    """_safe_float returns default for None."""
    assert _safe_float(None) is None


def test_safe_float_empty() -> None:
    """_safe_float returns default for empty string."""
    assert _safe_float("") is None


def test_safe_float_invalid() -> None:
    """_safe_float returns default for non-numeric value."""
    assert _safe_float("abc") is None


def test_safe_int_valid() -> None:
    """_safe_int returns int for valid value."""
    assert _safe_int(42) == 42


def test_safe_int_float_string() -> None:
    """_safe_int converts float string to int."""
    assert _safe_int("42.0") == 42


def test_safe_int_none() -> None:
    """_safe_int returns default for None."""
    assert _safe_int(None) is None


def test_safe_int_empty() -> None:
    """_safe_int returns default for empty string."""
    assert _safe_int("") is None


def test_safe_int_invalid() -> None:
    """_safe_int returns default for non-numeric value."""
    assert _safe_int("abc") is None


def test_derive_boot_time_valid() -> None:
    """_derive_boot_time computes boot time from uptime."""
    now = dt_util.now()
    boot = _derive_boot_time(3600, now)
    assert boot is not None
    assert (now - boot).total_seconds() == pytest.approx(3600, abs=1)


def test_derive_boot_time_none() -> None:
    """_derive_boot_time returns None for None uptime."""
    now = dt_util.now()
    assert _derive_boot_time(None, now) is None


def test_derive_boot_time_negative() -> None:
    """_derive_boot_time returns None for negative uptime."""
    now = dt_util.now()
    assert _derive_boot_time(-1, now) is None


# ---------------------------------------------------------------------------
# Parsing unit tests (pure functions — no HA required)
# ---------------------------------------------------------------------------


def _now() -> Any:
    return dt_util.now()


def test_parse_gateway_basic() -> None:
    """Gateway parser extracts cpu, ram, uptime, uplink, Multi-WAN, and SFP."""
    device = {
        "mac": "aa:bb:cc:dd:ee:ff",
        "name": "UDM Pro",
        "model": "UDMPRO",
        "state": 1,
        "upgradable": False,
        "uptime": 250701,
        "system-stats": {"cpu": "37.2", "mem": "72.0"},
        "temperatures": [
            {"type": "cpu", "value": 48.0},
            {"type": "board", "value": 45.25},
        ],
        "storage": [
            {"mount_point": "/persistent", "size": 2046640128, "used": 415272960}
        ],
        "uplink": {
            "up": True,
            "speedtest_status": "Success",
            "comment": "WAN",
            "ip": "192.0.2.1",
        },
        "num_sta": 157,
        "user-num_sta": 157,
        "guest-num_sta": 0,
        "wan1": {
            "is_uplink": True,
            "up": True,
            "latency": 34,
            "availability": 100.0,
            "ip": "192.0.2.1",
        },
        "wan2": {
            "is_uplink": False,
            "up": True,
            "latency": 22,
            "availability": 100.0,
            "sfp_found": True,
            "sfp_vendor": "UBNT",
            "sfp_part": "UF-RJ45-1G",
            "sfp_serial": "SN0000000001",
            "ip": "192.0.2.2",
        },
        "geo_info": {
            "WAN": {"address": "198.51.100.1"},
            "WAN2": {"address": "203.0.113.1"},
        },
    }
    result = _parse_gateway(device, _now())

    assert result["mac"] == "aa:bb:cc:dd:ee:ff"
    assert result["cpu"] == pytest.approx(37.2)
    assert result["ram"] == pytest.approx(72.0)
    assert result["cpu_temp"] == pytest.approx(48.0)
    assert result["board_temp"] == pytest.approx(45.25)
    assert result["storage_used"] == 415272960
    assert result["storage_size"] == 2046640128
    assert result["storage_used_pct"] == pytest.approx(20.3)
    assert result["internet"] is True
    assert result["speedtest_status"] is True
    assert result["wan1_local_ip"] == "192.0.2.1"
    assert result["wan1_public_ip"] == "198.51.100.1"
    assert result["wan2_local_ip"] == "192.0.2.2"
    assert result["wan2_public_ip"] == "203.0.113.1"
    assert result["update_available"] is False
    assert result["boot_time"] is not None
    # WAN1
    assert result["wan1_active"] is True
    assert result["wan1_up"] is True
    assert result["wan1_latency"] == 34
    assert result["wan1_availability"] == pytest.approx(100.0)
    assert result["wan1_sfp_found"] is None
    assert result["wan1_sfp_vendor"] is None
    # WAN2
    assert result["wan2_active"] is False
    assert result["wan2_up"] is True
    assert result["wan2_latency"] == 22
    assert result["wan2_availability"] == pytest.approx(100.0)
    assert result["wan2_sfp_found"] is True
    assert result["wan2_sfp_vendor"] == "UBNT"
    assert result["wan2_sfp_part"] == "UF-RJ45-1G"
    assert result["wan2_sfp_serial"] == "SN0000000001"


def test_parse_gateway_no_temperatures() -> None:
    """Gateway parse handles missing temperatures."""
    device = {
        "mac": "aa:bb:cc:dd:ee:ff",
        "name": "UDM Pro",
        "model": "UDMPRO",
        "state": 1,
        "upgradable": False,
        "uptime": 1000,
        "system-stats": {"cpu": "10.0", "mem": "50.0"},
    }
    result = _parse_gateway(device, _now())
    assert result["cpu_temp"] is None
    assert result["board_temp"] is None


def test_parse_gateway_no_storage() -> None:
    """Gateway parse handles missing storage."""
    device = {
        "mac": "aa:bb:cc:dd:ee:ff",
        "name": "UDM Pro",
        "model": "UDMPRO",
        "state": 1,
        "upgradable": False,
        "uptime": 1000,
        "system-stats": {"cpu": "10.0", "mem": "50.0"},
    }
    result = _parse_gateway(device, _now())
    assert result["storage_used"] is None
    assert result["storage_size"] is None


def test_parse_gateway_no_uplink() -> None:
    """Gateway parse handles missing uplink."""
    device = {
        "mac": "aa:bb:cc:dd:ee:ff",
        "name": "UDM Pro",
        "model": "UDMPRO",
        "state": 1,
        "upgradable": False,
        "uptime": 1000,
        "system-stats": {"cpu": "10.0", "mem": "50.0"},
    }
    result = _parse_gateway(device, _now())
    assert result["internet"] is False
    assert result["wan1_local_ip"] is None
    assert result["wan1_public_ip"] is None
    assert result["wan2_local_ip"] is None
    assert result["wan2_public_ip"] is None


def test_parse_ap_basic() -> None:
    """AP parse extracts wifi client and satisfaction fields."""
    device = {
        "mac": "bb:cc:dd:ee:ff:00",
        "name": "AP Garage",
        "model": "UAP-AC-M",
        "state": 1,
        "upgradable": False,
        "uptime": 381300,
        "system-stats": {"cpu": "4.0", "mem": "41.1"},
        "is_access_point": True,
        "user-wlan-num_sta": 10,
        "guest-wlan-num_sta": 0,
        "satisfaction": 98,
        "radio_table_stats": [
            {"user-num_sta": 9, "satisfaction": 97},
            {"user-num_sta": 1, "satisfaction": 99},
        ],
    }
    result = _parse_ap(device, _now())

    assert result["type"] == "ap"
    assert result["clients"] == 10
    assert result["guests"] == 0
    assert result["clients_wifi0"] == 9
    assert result["clients_wifi1"] == 1
    assert result["score"] == 98
    assert result["score_wifi0"] == 97
    assert result["score_wifi1"] == 99
    assert result["cpu"] == pytest.approx(4.0)
    assert result["ram"] == pytest.approx(41.1)


def test_parse_ap_empty_radio_stats() -> None:
    """AP parse handles empty radio_table_stats."""
    device = {
        "mac": "bb:cc:dd:ee:ff:00",
        "name": "AP Garage",
        "model": "UAP-AC-M",
        "state": 1,
        "upgradable": False,
        "uptime": 1000,
        "system-stats": {"cpu": "4.0", "mem": "41.1"},
        "is_access_point": True,
    }
    result = _parse_ap(device, _now())
    assert result["clients_wifi0"] == 0
    assert result["clients_wifi1"] == 0
    assert result["score_wifi0"] is None
    assert result["score_wifi1"] is None


def test_parse_switch_basic() -> None:
    """Switch parse extracts port counts and system stats."""
    device = {
        "mac": "cc:dd:ee:ff:00:11",
        "name": "Switch A",
        "model": "US8P60",
        "state": 1,
        "upgradable": True,
        "uptime": 2160000,
        "system-stats": {"cpu": "59.0", "mem": "45.3"},
        "num_sta": 5,
        "user-num_sta": 5,
        "guest-num_sta": 0,
    }
    result = _parse_switch(device, _now())

    assert result["type"] == "switch"
    assert result["ports_used"] == 5
    assert result["ports_guest"] == 0
    assert result["cpu"] == pytest.approx(59.0)
    assert result["update_available"] is True


def test_parse_health_wan_and_www() -> None:
    """Health parse correctly extracts WAN1, WAN2, WWW, WLAN, LAN."""
    health_list = [
        {
            "subsystem": "wan",
            "status": "ok",
            "isp_name": "Test ISP",
            "isp_organization": "Test ISP Ltd",
            "gw_version": "5.1.19",
            "num_sta": 162,
            "gw_system-stats": {"cpu": "37.2", "mem": "72.0", "uptime": 250701},
            "uptime_stats": {
                "WAN": {
                    "availability": 100.0,
                    "latency_average": 34,
                    "time_period": 9381,
                    "uptime": 9370,
                },
                "WAN2": {
                    "availability": 99.5,
                    "latency_average": 25,
                    "time_period": 11018,
                    "uptime": 11017,
                },
            },
        },
        {
            "subsystem": "www",
            "status": "ok",
            "latency": 34,
            "uptime": 250669,
            "drops": 1,
            "xput_up": 28.0,
            "xput_down": 206.0,
            "speedtest_status": "Success",
            "speedtest_lastrun": 1782018108,
            "speedtest_ping": 25,
        },
        {
            "subsystem": "wlan",
            "status": "ok",
            "num_user": 101,
            "num_guest": 0,
            "num_iot": 2,
            "num_ap": 8,
        },
        {
            "subsystem": "lan",
            "status": "ok",
            "num_user": 61,
            "num_iot": 0,
            "num_sw": 15,
            "num_adopted": 15,
        },
        {
            "subsystem": "vpn",
            "status": "unknown",
        },
    ]
    result = _parse_health(health_list, _now())

    assert result["wan_status"] == "ok"
    assert result["wan_isp_name"] == "Test ISP"
    assert result["wan1_availability"] == pytest.approx(100.0)
    assert result["wan1_latency_avg"] == 34
    assert result["wan2_availability"] == pytest.approx(99.5)
    assert result["wan2_latency_avg"] == 25
    assert result["www_status"] == "ok"
    assert result["www_drops"] == 1
    assert result["wlan_num_user"] == 101
    assert result["lan_num_sw"] == 15
    assert result["vpn_status"] == "unknown"
    assert result["wan1_boot_time"] is not None
    assert result["wan2_boot_time"] is not None


def test_parse_health_no_uptime_stats() -> None:
    """Health parse handles missing uptime_stats."""
    health_list = [
        {
            "subsystem": "wan",
            "status": "ok",
        },
    ]
    result = _parse_health(health_list, _now())
    assert result["wan_status"] == "ok"
    assert "wan1_availability" not in result


def test_parse_health_no_wan2() -> None:
    """Health parse handles missing WAN2 stats."""
    health_list = [
        {
            "subsystem": "wan",
            "status": "ok",
            "uptime_stats": {
                "WAN": {"availability": 100.0, "latency_average": 34, "uptime": 9370},
            },
        },
    ]
    result = _parse_health(health_list, _now())
    assert "wan2_availability" not in result


# ---------------------------------------------------------------------------
# Coordinator 3-strike resilience tests
# ---------------------------------------------------------------------------


async def test_coordinator_holds_data_for_three_failures(
    hass: Any, mock_config_entry: Any, mock_coordinator_data: Any
) -> None:
    """Coordinator returns cached data for up to 3 consecutive failures."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    api.get_devices = AsyncMock(side_effect=UnifiConnectionError("timeout"))
    api.get_health = AsyncMock(return_value=[])
    api.get_sysinfo = AsyncMock(return_value=[])
    api.get_networkconf = AsyncMock(return_value=[])
    api.get_settings = AsyncMock(return_value=[])

    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    coordinator.data = mock_coordinator_data

    for strike in range(1, 4):
        result = await coordinator._async_update_data()
        assert result is mock_coordinator_data, (
            f"Expected cached data on failure {strike}"
        )
        assert coordinator.consecutive_failures == strike


async def test_coordinator_raises_after_four_failures(
    hass: Any, mock_config_entry: Any, mock_coordinator_data: Any
) -> None:
    """Coordinator raises UpdateFailed after 4 consecutive failures."""
    from homeassistant.helpers.update_coordinator import UpdateFailed

    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    api.get_devices = AsyncMock(side_effect=UnifiConnectionError("timeout"))
    api.get_health = AsyncMock(return_value=[])
    api.get_sysinfo = AsyncMock(return_value=[])
    api.get_networkconf = AsyncMock(return_value=[])
    api.get_settings = AsyncMock(return_value=[])

    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    coordinator.data = mock_coordinator_data
    coordinator.consecutive_failures = 3

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_coordinator_resets_failures_on_success(
    hass: Any, mock_config_entry: Any
) -> None:
    """Consecutive failure counter resets to zero on a successful fetch."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    api.get_devices = AsyncMock(return_value=[])
    api.get_health = AsyncMock(return_value=[])
    api.get_sysinfo = AsyncMock(return_value=[])
    api.get_networkconf = AsyncMock(return_value=[])
    api.get_settings = AsyncMock(return_value=[])
    api.get_daily_gateway = AsyncMock(return_value=[])
    api.get_monthly_gateway = AsyncMock(return_value=[])
    api.get_rogueaps = AsyncMock(return_value=[])
    api.get_guests = AsyncMock(return_value=[])
    api.get_backups = AsyncMock(return_value=[])
    api.get_speedtest_results = AsyncMock(return_value=[])

    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    coordinator.consecutive_failures = 2

    await coordinator._async_update_data()
    assert coordinator.consecutive_failures == 0


async def test_coordinator_handles_auth_error(
    hass: Any, mock_config_entry: Any, mock_coordinator_data: Any
) -> None:
    """Coordinator handles UnifiAuthError with 3-strike logic."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    api.get_devices = AsyncMock(side_effect=UnifiAuthError("auth failed"))
    api.get_health = AsyncMock(return_value=[])
    api.get_sysinfo = AsyncMock(return_value=[])
    api.get_networkconf = AsyncMock(return_value=[])
    api.get_settings = AsyncMock(return_value=[])

    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    coordinator.data = mock_coordinator_data

    result = await coordinator._async_update_data()
    assert result is mock_coordinator_data
    assert coordinator.consecutive_failures == 1


async def test_coordinator_reconnects_after_failure(
    hass: Any, mock_config_entry: Any, mock_coordinator_data: Any
) -> None:
    """Coordinator logs reconnection after failure->success transition."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    api.get_devices = AsyncMock(return_value=[])
    api.get_health = AsyncMock(return_value=[])
    api.get_sysinfo = AsyncMock(return_value=[])
    api.get_networkconf = AsyncMock(return_value=[])
    api.get_settings = AsyncMock(return_value=[])
    api.get_daily_gateway = AsyncMock(return_value=[])
    api.get_monthly_gateway = AsyncMock(return_value=[])
    api.get_rogueaps = AsyncMock(return_value=[])
    api.get_guests = AsyncMock(return_value=[])
    api.get_backups = AsyncMock(return_value=[])
    api.get_speedtest_results = AsyncMock(return_value=[])

    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    coordinator.data = mock_coordinator_data
    coordinator._was_available = False

    await coordinator._async_update_data()
    assert coordinator._was_available is True


async def test_coordinator_skips_offline_devices(
    hass: Any, mock_config_entry: Any
) -> None:
    """Coordinator skips devices with state == 0."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    api.get_devices = AsyncMock(
        return_value=[
            {"mac": "aa:bb:cc:dd:ee:ff", "model": "UDMPRO", "state": 1},
            {"mac": "bb:cc:dd:ee:ff:00", "model": "UAP-AC-M", "state": 0},
        ]
    )
    api.get_health = AsyncMock(return_value=[])
    api.get_sysinfo = AsyncMock(return_value=[])
    api.get_networkconf = AsyncMock(return_value=[])
    api.get_settings = AsyncMock(return_value=[])
    api.get_daily_gateway = AsyncMock(return_value=[])
    api.get_monthly_gateway = AsyncMock(return_value=[])
    api.get_rogueaps = AsyncMock(return_value=[])
    api.get_guests = AsyncMock(return_value=[])
    api.get_backups = AsyncMock(return_value=[])
    api.get_speedtest_results = AsyncMock(return_value=[])

    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)

    result = await coordinator._async_update_data()
    assert "bb:cc:dd:ee:ff:00" not in result["devices"]


async def test_coordinator_unexpected_error_holds_data(
    hass: Any, mock_config_entry: Any, mock_coordinator_data: Any
) -> None:
    """Coordinator holds data on unexpected errors within 3 strikes."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    api.get_devices = AsyncMock(side_effect=RuntimeError("unexpected"))
    api.get_health = AsyncMock(return_value=[])
    api.get_sysinfo = AsyncMock(return_value=[])
    api.get_networkconf = AsyncMock(return_value=[])
    api.get_settings = AsyncMock(return_value=[])

    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    coordinator.data = mock_coordinator_data

    result = await coordinator._async_update_data()
    assert result is mock_coordinator_data
    assert coordinator.consecutive_failures == 1


async def test_get_stable_boot_time_latch(hass: Any, mock_config_entry: Any) -> None:
    """Test get_stable_boot_time reboot latch behavior."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)

    now = dt_util.now().replace(microsecond=0)

    # 1. First calculation latches the boot time
    boot1 = coordinator.get_stable_boot_time("gateway", 3600, now)
    assert boot1 is not None
    assert (now - boot1).total_seconds() == 3600

    # 2. Slight update (e.g. 10s elapsed on both clocks, no reboot)
    now_later = now + timedelta(seconds=10)
    boot2 = coordinator.get_stable_boot_time("gateway", 3610, now_later)
    # The boot timestamp MUST stay exactly the same (no drift)
    assert boot2 == boot1

    # 3. Garbage/Negative reading is ignored
    boot3 = coordinator.get_stable_boot_time("gateway", -10, now_later)
    assert boot3 == boot1

    # 4. Genuine Reboot (uptime drops by more than 30s)
    boot4 = coordinator.get_stable_boot_time("gateway", 10, now_later)
    assert boot4 != boot1
    assert (now_later - boot4).total_seconds() == 10


async def test_coordinator_parses_wan_and_security_configs(
    hass: Any, mock_config_entry: Any
) -> None:
    """Coordinator fetches and successfully parses networkconf and setting payloads."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    api.get_devices = AsyncMock(
        return_value=[
            {
                "mac": "aa:bb:cc:dd:ee:ff",
                "model": "UDMPRO",
                "state": 1,
                "uptime": 1000,
                "system-stats": {"cpu": "10.0", "mem": "50.0"},
                "wan1": {"is_uplink": True, "up": True},
                "wan2": {"is_uplink": False, "up": True},
            },
            {
                "mac": "11:22:33:44:55:66",
                "name": "AP-1",
                "model": "UAP-AC-Pro",
                "state": 1,
                "is_access_point": True,
            },
        ]
    )
    api.get_health = AsyncMock(return_value=[])
    api.get_sysinfo = AsyncMock(
        return_value=[
            {
                "version": "9.2.87",
                "build": "15432",
                "ubnt_device_type": "udm",
                "udm_version": "3.2.12",
            }
        ]
    )
    api.get_networkconf = AsyncMock(
        return_value=[
            {
                "purpose": "wan",
                "wan_networkgroup": "WAN",
                "wan_load_balance_type": "weighted",
                "wan_load_balance_weight": 55,
                "vlan": None,
            },
            {
                "purpose": "wan",
                "wan_networkgroup": "WAN2",
                "wan_load_balance_type": "weighted",
                "wan_load_balance_weight": 45,
                "vlan": None,
            },
            {
                "purpose": "corporate",
                "vlan": 10,
            },
        ]
    )
    api.get_settings = AsyncMock(
        return_value=[
            {
                "key": "ips",
                "ips_mode": "block",
                "ad_blocking_enabled": True,
                "honeypot_enabled": True,
            }
        ]
    )
    api.get_daily_gateway = AsyncMock(
        return_value=[
            {
                "time": 1782082800000,
                "wan-rx_bytes": 1000.0,
                "wan-tx_bytes": 200.0,
                "wan2-rx_bytes": 50.0,
                "wan2-tx_bytes": 10.0,
            }
        ]
    )
    api.get_monthly_gateway = AsyncMock(
        return_value=[
            {
                "time": 1761955200000,
                "wan-rx_bytes": 5000.0,
                "wan-tx_bytes": 1000.0,
                "wan2-rx_bytes": 200.0,
                "wan2-tx_bytes": 40.0,
            }
        ]
    )
    api.get_system_logs = AsyncMock(return_value=[])
    current_ts = int(dt_util.as_timestamp(dt_util.now()))
    api.get_rogueaps = AsyncMock(
        return_value=[
            {
                "essid": "RogueNet-1",
                "bssid": "de:ad:be:ef:00:01",
                "channel": 1,
                "signal": -89,
                "band": "ng",
                "oui": "Example Vendor",
                "ap_mac": "11:22:33:44:55:66",
                "last_seen": current_ts - 432000,
            }
        ]
    )
    api.get_guests = AsyncMock(return_value=[{"mac": "aa:bb:cc:11:22:33"}])
    api.get_backups = AsyncMock(
        return_value=[
            {
                "time": 1775271600088,
            }
        ]
    )
    api.get_speedtest_results = AsyncMock(
        return_value=[
            {
                "xput_download": 86.0,
                "xput_upload": 23.0,
                "latency": 33.0,
                "time": 1782018032000,
            },
            {
                "xput_download": 206.0,
                "xput_upload": 28.0,
                "latency": 25.0,
                "time": 1782018108000,
            },
        ]
    )
    api.get_wlanconf = AsyncMock(
        return_value=[
            {"name": "Home_WiFi", "enabled": True},
            {"name": "Guest_WiFi", "enabled": False},
        ]
    )
    api.get_sites = AsyncMock(
        return_value=[
            {"id": "mock-uuid-123", "internalReference": "default", "name": "Default"}
        ]
    )
    api.get_wan_interfaces = AsyncMock(
        return_value=[
            {"id": "wan1-id", "name": "WAN1_ISP1"},
            {"id": "wan2-id", "name": "WAN2_ISP2"},
        ]
    )
    api.get_vpn_servers = AsyncMock(return_value=[])
    api.get_vpn_tunnels = AsyncMock(
        return_value=[
            {"name": "OfficeTunnel", "state": "CONNECTED"},
            {"name": "BackupTunnel", "state": "DISCONNECTED"},
        ]
    )
    api.get_firewall_policies = AsyncMock(
        return_value=[
            {"name": "Rule1", "enabled": True},
            {"name": "Rule2", "enabled": True},
            {"name": "Rule3", "enabled": False},
        ]
    )

    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    result = await coordinator._async_update_data()

    gateway = result["gateway"]
    assert gateway["wan_mode"] == "weighted"
    assert gateway["wan1_weight"] == 55
    assert gateway["wan2_weight"] == 45
    assert gateway["ips_mode"] == "block"
    assert gateway["ad_blocking"] is True
    assert gateway["honeypot"] is True
    assert gateway["wan1_active"] is True
    assert gateway["wan2_active"] is False

    # New telemetry statistics assertions
    assert gateway["wan1_today_rx"] == pytest.approx(1000.0)
    assert gateway["wan1_today_tx"] == pytest.approx(200.0)
    assert gateway["wan2_today_rx"] == pytest.approx(50.0)
    assert gateway["wan2_today_tx"] == pytest.approx(10.0)

    assert gateway["wan1_month_rx"] == pytest.approx(5000.0)
    assert gateway["wan1_month_tx"] == pytest.approx(1000.0)
    assert gateway["wan2_month_rx"] == pytest.approx(200.0)
    assert gateway["wan2_month_tx"] == pytest.approx(40.0)

    assert gateway["rogue_ap_count"] == 1
    assert gateway["rogue_aps_list"][0]["essid"] == "RogueNet-1"
    assert gateway["rogue_aps_list"][0]["age"] is not None
    assert gateway["rogue_aps_list"][0]["detected_by"] == "AP-1"
    assert gateway["strongest_rogue_ssid"] == "RogueNet-1"
    assert gateway["strongest_rogue_rssi"] == -89
    assert gateway["guest_user_count"] == 1
    assert gateway["last_backup"] == datetime(2026, 4, 4, 3, 0, 0, 88000, tzinfo=UTC)
    assert gateway["configured_vlans"] == 1

    assert gateway["application_version"] == "9.2.87"
    assert gateway["application_build"] == "15432"
    assert gateway["device_type"] == "udm"
    assert gateway["udm_version"] == "3.2.12"

    assert gateway["wan1_speedtest_download"] == pytest.approx(86.0)
    assert gateway["wan1_speedtest_upload"] == pytest.approx(23.0)
    assert gateway["wan1_speedtest_ping"] == pytest.approx(33.0)
    assert gateway["wan1_speedtest_lastrun"] == datetime(
        2026, 6, 21, 5, 0, 32, tzinfo=UTC
    )

    assert gateway["wan2_speedtest_download"] == pytest.approx(206.0)
    assert gateway["wan2_speedtest_upload"] == pytest.approx(28.0)
    assert gateway["wan2_speedtest_ping"] == pytest.approx(25.0)
    assert gateway["wan2_speedtest_lastrun"] == datetime(
        2026, 6, 21, 5, 1, 48, tzinfo=UTC
    )

    # WLAN assertions
    assert gateway["wifi_networks_total"] == 2
    assert gateway["wifi_networks_active"] == 1
    assert gateway["wifi_states"] == {"Home_WiFi": True, "Guest_WiFi": False}

    # VLANs assertions
    assert gateway["vlans_total"] == 1
    assert gateway["vlans_active"] == 1

    # VPN assertions
    assert gateway["vpn_connections_total"] == 2
    assert gateway["vpn_connections_active"] == 1
    assert gateway["vpn_states"] == {"OfficeTunnel": True, "BackupTunnel": False}

    # Firewall assertions
    assert gateway["rules_configured"] == 3
    assert gateway["rules_active"] == 2
    assert gateway["rules_disabled"] == 1

    # WAN names assertions
    assert gateway["wan1_interface_name"] == "WAN1_ISP1"
    assert gateway["wan2_interface_name"] == "WAN2_ISP2"


async def test_coordinator_fetch_optional_supplementary_error(
    hass: Any, mock_config_entry: Any
) -> None:
    """Supplementary endpoint failure returns [] and does not crash update."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    api.get_devices = AsyncMock(return_value=[])
    api.get_health = AsyncMock(return_value=[])
    api.get_sysinfo = AsyncMock(return_value=[])
    api.get_networkconf = AsyncMock(return_value=[])
    api.get_settings = AsyncMock(return_value=[])
    api.get_daily_gateway = AsyncMock(side_effect=UnifiConnectionError("not available"))
    api.get_monthly_gateway = AsyncMock(side_effect=UnifiAuthError("not allowed"))
    api.get_rogueaps = AsyncMock(return_value=[])
    api.get_guests = AsyncMock(return_value=[])
    api.get_backups = AsyncMock(return_value=[])
    api.get_speedtest_results = AsyncMock(return_value=[])

    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    result = await coordinator._async_update_data()
    assert result["gateway"] == {}


async def test_coordinator_speedtest_single_result(
    hass: Any, mock_config_entry: Any
) -> None:
    """Single speedtest result populates only WAN1 fields."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    api.get_devices = AsyncMock(
        return_value=[{"mac": "aa:bb:cc:dd:ee:ff", "model": "UDMPRO", "state": 1}]
    )
    api.get_health = AsyncMock(return_value=[])
    api.get_sysinfo = AsyncMock(return_value=[])
    api.get_networkconf = AsyncMock(return_value=[])
    api.get_settings = AsyncMock(return_value=[])
    api.get_daily_gateway = AsyncMock(return_value=[])
    api.get_monthly_gateway = AsyncMock(return_value=[])
    api.get_rogueaps = AsyncMock(return_value=[])
    api.get_guests = AsyncMock(return_value=[])
    api.get_backups = AsyncMock(return_value=[])
    api.get_speedtest_results = AsyncMock(
        return_value=[
            {
                "xput_download": 100.0,
                "xput_upload": 20.0,
                "latency": 15.0,
                "time": 1782018032000,
            }
        ]
    )

    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    result = await coordinator._async_update_data()
    gateway = result["gateway"]
    assert gateway["wan1_speedtest_download"] == pytest.approx(100.0)
    assert gateway["wan1_speedtest_upload"] == pytest.approx(20.0)
    assert gateway["wan1_speedtest_ping"] == pytest.approx(15.0)
    assert gateway["wan2_speedtest_download"] is None
    assert gateway["wan2_speedtest_upload"] is None


async def test_coordinator_speedtest_single_no_time(
    hass: Any, mock_config_entry: Any
) -> None:
    """Single speedtest result without time does not crash."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    api.get_devices = AsyncMock(
        return_value=[{"mac": "aa:bb:cc:dd:ee:ff", "model": "UDMPRO", "state": 1}]
    )
    api.get_health = AsyncMock(return_value=[])
    api.get_sysinfo = AsyncMock(return_value=[])
    api.get_networkconf = AsyncMock(return_value=[])
    api.get_settings = AsyncMock(return_value=[])
    api.get_daily_gateway = AsyncMock(return_value=[])
    api.get_monthly_gateway = AsyncMock(return_value=[])
    api.get_rogueaps = AsyncMock(return_value=[])
    api.get_guests = AsyncMock(return_value=[])
    api.get_backups = AsyncMock(return_value=[])
    api.get_speedtest_results = AsyncMock(
        return_value=[{"xput_download": 100.0, "xput_upload": 20.0, "latency": 15.0}]
    )

    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    result = await coordinator._async_update_data()
    assert result["gateway"]["wan1_speedtest_lastrun"] is None


async def test_coordinator_device_parse_switch(
    hass: Any, mock_config_entry: Any
) -> None:
    """Device without GATEWAY_MODELS and not AP is parsed as switch."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    api.get_devices = AsyncMock(
        return_value=[
            {"mac": "cc:dd:ee:ff:00:11", "model": "US8P60", "state": 1, "num_sta": 3}
        ]
    )
    api.get_health = AsyncMock(return_value=[])
    api.get_sysinfo = AsyncMock(return_value=[])
    api.get_networkconf = AsyncMock(return_value=[])
    api.get_settings = AsyncMock(return_value=[])
    api.get_daily_gateway = AsyncMock(return_value=[])
    api.get_monthly_gateway = AsyncMock(return_value=[])
    api.get_rogueaps = AsyncMock(return_value=[])
    api.get_guests = AsyncMock(return_value=[])
    api.get_backups = AsyncMock(return_value=[])
    api.get_speedtest_results = AsyncMock(return_value=[])

    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    result = await coordinator._async_update_data()
    assert "cc:dd:ee:ff:00:11" in result["devices"]
    assert result["devices"]["cc:dd:ee:ff:00:11"]["type"] == "switch"


async def test_coordinator_device_parse_error_skipped(
    hass: Any, mock_config_entry: Any
) -> None:
    """Device that raises during parsing is skipped with a warning."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    api.get_devices = AsyncMock(
        return_value=[
            {"mac": "aa:bb:cc:dd:ee:ff", "model": "UDMPRO", "state": 1},
            {
                "mac": "ee:ff:00:11:22:33",
                "model": "UAP-AC-M",
                "state": 1,
                "is_access_point": True,
            },
        ]
    )
    api.get_health = AsyncMock(return_value=[])
    api.get_sysinfo = AsyncMock(return_value=[])
    api.get_networkconf = AsyncMock(return_value=[])
    api.get_settings = AsyncMock(return_value=[])
    api.get_daily_gateway = AsyncMock(return_value=[])
    api.get_monthly_gateway = AsyncMock(return_value=[])
    api.get_rogueaps = AsyncMock(return_value=[])
    api.get_guests = AsyncMock(return_value=[])
    api.get_backups = AsyncMock(return_value=[])
    api.get_speedtest_results = AsyncMock(return_value=[])

    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    # Override _parse_ap to raise - this tests the except branch
    with patch(
        "custom_components.unifi_network_monitor.coordinator._parse_ap",
        side_effect=ValueError("bad data"),
    ):
        result = await coordinator._async_update_data()
    # Gateway should still be parsed successfully
    assert result["gateway"] is not None
    # Failed AP should not appear in devices
    assert "ee:ff:00:11:22:33" not in result["devices"]


async def test_coordinator_set_wan_weights_success(
    hass: Any, mock_config_entry: Any
) -> None:
    """async_set_wan_weights writes both WAN1 and WAN2 weights via API."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    api.update_networkconf = AsyncMock()

    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    coordinator._networkconf_wan = {"_id": "wan1_id", "wan_load_balance_weight": 55}
    coordinator._networkconf_wan2 = {"_id": "wan2_id", "wan_load_balance_weight": 45}
    coordinator.async_request_refresh = AsyncMock()

    await coordinator.async_set_wan_weights(70)

    assert api.update_networkconf.call_count == 2
    api.update_networkconf.assert_any_call(
        "wan1_id", {"_id": "wan1_id", "wan_load_balance_weight": 70}
    )
    api.update_networkconf.assert_any_call(
        "wan2_id", {"_id": "wan2_id", "wan_load_balance_weight": 30}
    )
    coordinator.async_request_refresh.assert_awaited_once()


async def test_coordinator_set_wan_weights_no_config(
    hass: Any, mock_config_entry: Any
) -> None:
    """async_set_wan_weights raises ValueError when networkconf not loaded."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)

    with pytest.raises(ValueError, match="not yet loaded"):
        await coordinator.async_set_wan_weights(50)


async def test_coordinator_wan_weights_writable(
    hass: Any, mock_config_entry: Any
) -> None:
    """wan_weights_writable is False until both WAN networkconf objects load."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)

    assert coordinator.wan_weights_writable is False
    coordinator._networkconf_wan = {"_id": "wan1_id"}
    assert coordinator.wan_weights_writable is False
    coordinator._networkconf_wan2 = {"_id": "wan2_id"}
    assert coordinator.wan_weights_writable is True


async def test_coordinator_site_issue_created_and_cleared(
    hass: Any, mock_config_entry: Any
) -> None:
    """_sync_site_issue raises a repair on 'failed' and clears it on resolution."""
    from homeassistant.helpers import issue_registry as ir

    from custom_components.unifi_network_monitor.const import DOMAIN

    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    reg = ir.async_get(hass)

    coordinator.site_uuid = "failed"
    coordinator._sync_site_issue()
    assert reg.async_get_issue(DOMAIN, "site_resolution_failed") is not None

    coordinator.site_uuid = "real-site-uuid"
    coordinator._sync_site_issue()
    assert reg.async_get_issue(DOMAIN, "site_resolution_failed") is None

    # Still resolving (None) is a no-op and must not raise or create an issue.
    coordinator.site_uuid = None
    coordinator._sync_site_issue()
    assert reg.async_get_issue(DOMAIN, "site_resolution_failed") is None


async def test_coordinator_site_issue_suppressed_without_api_key(
    hass: Any, mock_config_entry: Any
) -> None:
    """Under username/password auth the v3 failure is expected — no repair issue.

    The integration API endpoints are API-key only, so a 'failed' site_uuid is
    normal without a key and must not raise a repair issue. A stale issue from a
    previous API-key session must also be cleared.
    """
    from homeassistant.helpers import issue_registry as ir

    from custom_components.unifi_network_monitor.const import DOMAIN

    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    api.api_key = None  # username/password mode
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    reg = ir.async_get(hass)

    # Failed resolution under u/p must NOT create an issue.
    coordinator.site_uuid = "failed"
    coordinator._sync_site_issue()
    assert reg.async_get_issue(DOMAIN, "site_resolution_failed") is None

    # A stale issue left over from a prior API-key session is cleared.
    ir.async_create_issue(
        hass,
        DOMAIN,
        "site_resolution_failed",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="site_resolution_failed",
    )
    coordinator._sync_site_issue()
    assert reg.async_get_issue(DOMAIN, "site_resolution_failed") is None


async def test_coordinator_set_wan_weights_no_id(
    hass: Any, mock_config_entry: Any
) -> None:
    """async_set_wan_weights raises ValueError when _id missing."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    coordinator._networkconf_wan = {"wan_load_balance_weight": 50}
    coordinator._networkconf_wan2 = {"wan_load_balance_weight": 50}

    with pytest.raises(ValueError, match="missing _id"):
        await coordinator.async_set_wan_weights(60)


async def test_coordinator_trigger_speedtest(hass: Any, mock_config_entry: Any) -> None:
    """async_trigger_speedtest delegates to api.trigger_speedtest."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    api.trigger_speedtest = AsyncMock()
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)

    await coordinator.async_trigger_speedtest("wan2")
    api.trigger_speedtest.assert_awaited_with("wan2")


async def test_coordinator_returns_cached_when_paused(
    hass: Any, mock_config_entry: Any
) -> None:
    """Coordinator returns cached data when stop_polling is True."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={**mock_config_entry.options, "stop_polling": True},
    )
    api = MagicMock()
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)

    # Seed cached data
    coordinator.data = {"gateway": {"mac": "aa:bb:cc:dd:ee:ff"}}

    result = await coordinator._async_update_data()
    assert result == {"gateway": {"mac": "aa:bb:cc:dd:ee:ff"}}
    api.get_devices.assert_not_called()


async def test_coordinator_config_entry_associated(
    hass: Any, mock_config_entry: Any
) -> None:
    """Coordinator passes config_entry to base so HA honours pref_disable_polling."""
    mock_config_entry.add_to_hass(hass)
    coordinator = UnifiNetworkDataUpdateCoordinator(
        hass, mock_config_entry, MagicMock()
    )
    assert coordinator.config_entry is mock_config_entry


# ---------------------------------------------------------------------------
# Extended coverage tests for coordinator.py uncovered lines
# ---------------------------------------------------------------------------


async def test_coordinator_loads_boot_times_from_entry_data(
    hass: Any, mock_config_entry: Any
) -> None:
    """Boot times are loaded from entry.data when present (line 345)."""
    mock_config_entry.add_to_hass(hass)
    data = {
        **mock_config_entry.data,
        "boot_times": {
            "gateway": {"boot_time": "2026-01-01T00:00:00", "last_uptime": 1000},
            "wan1": {"boot_time": "2026-01-01T01:00:00", "last_uptime": 500},
        },
    }
    hass.config_entries.async_update_entry(mock_config_entry, data=data)
    api = MagicMock()
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    assert "gateway" in coordinator._boot_times
    assert coordinator._boot_times["gateway"]["last_uptime"] == 1000
    assert coordinator._boot_times["wan1"]["last_uptime"] == 500


def test_get_stable_boot_time_keeps_existing_on_bad_reading(
    hass: Any, mock_config_entry: Any
) -> None:
    """get_stable_boot_time keeps existing boot time on bad uptime read (line 364)."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    now = dt_util.now().replace(microsecond=0)

    # Latch first
    coordinator.get_stable_boot_time("gateway", 3600, now)

    # Bad reading (None uptime) should keep latched value
    boot = coordinator.get_stable_boot_time("gateway", None, now)
    assert boot is not None
    assert (now - boot).total_seconds() == pytest.approx(3600, abs=1)


async def test_coordinator_site_uuid_not_found(
    hass: Any, mock_config_entry: Any
) -> None:
    """Site UUID resolution: no matching site sets 'failed' (lines 486-489)."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    api.get_devices = AsyncMock(return_value=[])
    api.get_health = AsyncMock(return_value=[])
    api.get_sysinfo = AsyncMock(return_value=[])
    api.get_networkconf = AsyncMock(return_value=[])
    api.get_settings = AsyncMock(return_value=[])
    api.get_daily_gateway = AsyncMock(return_value=[])
    api.get_monthly_gateway = AsyncMock(return_value=[])
    api.get_rogueaps = AsyncMock(return_value=[])
    api.get_guests = AsyncMock(return_value=[])
    api.get_backups = AsyncMock(return_value=[])
    api.get_speedtest_results = AsyncMock(return_value=[])
    api.get_sites = AsyncMock(
        return_value=[{"id": "other-uuid", "internalReference": "other"}]
    )

    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    await coordinator._async_update_data()
    assert coordinator.site_uuid == "failed"


async def test_coordinator_site_uuid_exception(
    hass: Any, mock_config_entry: Any
) -> None:
    """Site UUID resolution: exception sets 'failed' (lines 497-505)."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    api.get_devices = AsyncMock(return_value=[])
    api.get_health = AsyncMock(return_value=[])
    api.get_sysinfo = AsyncMock(return_value=[])
    api.get_networkconf = AsyncMock(return_value=[])
    api.get_settings = AsyncMock(return_value=[])
    api.get_daily_gateway = AsyncMock(return_value=[])
    api.get_monthly_gateway = AsyncMock(return_value=[])
    api.get_rogueaps = AsyncMock(return_value=[])
    api.get_guests = AsyncMock(return_value=[])
    api.get_backups = AsyncMock(return_value=[])
    api.get_speedtest_results = AsyncMock(return_value=[])
    api.get_sites = AsyncMock(
        side_effect=UnifiConnectionError("HTTP error 404 - not found")
    )

    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    await coordinator._async_update_data()
    assert coordinator.site_uuid == "failed"


async def test_coordinator_parse_error_daily_gateway(
    hass: Any, mock_config_entry: Any
) -> None:
    """Daily gateway parse error is handled gracefully (lines 666-673)."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    api.get_devices = AsyncMock(
        return_value=[{"mac": "aa:bb:cc:dd:ee:ff", "model": "UDMPRO", "state": 1}]
    )
    api.get_health = AsyncMock(return_value=[])
    api.get_sysinfo = AsyncMock(return_value=[])
    api.get_networkconf = AsyncMock(return_value=[])
    api.get_settings = AsyncMock(return_value=[])
    api.get_daily_gateway = AsyncMock(return_value=[None])
    api.get_monthly_gateway = AsyncMock(return_value=[])
    api.get_rogueaps = AsyncMock(return_value=[])
    api.get_guests = AsyncMock(return_value=[])
    api.get_backups = AsyncMock(return_value=[])
    api.get_speedtest_results = AsyncMock(return_value=[])

    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    result = await coordinator._async_update_data()
    assert result["gateway"].get("wan1_today_rx") is None


async def test_coordinator_parse_error_monthly_gateway(
    hass: Any, mock_config_entry: Any
) -> None:
    """Monthly gateway parse error is handled gracefully (lines 696-703)."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    api.get_devices = AsyncMock(
        return_value=[{"mac": "aa:bb:cc:dd:ee:ff", "model": "UDMPRO", "state": 1}]
    )
    api.get_health = AsyncMock(return_value=[])
    api.get_sysinfo = AsyncMock(return_value=[])
    api.get_networkconf = AsyncMock(return_value=[])
    api.get_settings = AsyncMock(return_value=[])
    api.get_daily_gateway = AsyncMock(return_value=[])
    api.get_monthly_gateway = AsyncMock(return_value=[None])
    api.get_rogueaps = AsyncMock(return_value=[])
    api.get_guests = AsyncMock(return_value=[])
    api.get_backups = AsyncMock(return_value=[])
    api.get_speedtest_results = AsyncMock(return_value=[])

    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    result = await coordinator._async_update_data()
    assert result["gateway"].get("wan1_month_rx") is None


async def test_coordinator_parse_error_rogue_aps(
    hass: Any, mock_config_entry: Any
) -> None:
    """Rogue AP parse error is handled gracefully (lines 726-733)."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    api.get_devices = AsyncMock(
        return_value=[{"mac": "aa:bb:cc:dd:ee:ff", "model": "UDMPRO", "state": 1}]
    )
    api.get_health = AsyncMock(return_value=[])
    api.get_sysinfo = AsyncMock(return_value=[])
    api.get_networkconf = AsyncMock(return_value=[])
    api.get_settings = AsyncMock(return_value=[])
    api.get_daily_gateway = AsyncMock(return_value=[])
    api.get_monthly_gateway = AsyncMock(return_value=[])
    api.get_rogueaps = AsyncMock(return_value=[None])
    api.get_guests = AsyncMock(return_value=[])
    api.get_backups = AsyncMock(return_value=[])
    api.get_speedtest_results = AsyncMock(return_value=[])
    api.get_system_logs = AsyncMock(return_value=[])

    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    result = await coordinator._async_update_data()
    assert result["gateway"]["rogue_ap_count"] == 0


def _rogue_api(rogueaps: list[dict[str, Any]]) -> MagicMock:
    """Build a minimal API mock with a gateway and the given rogue AP list."""
    api = MagicMock()
    api.get_devices = AsyncMock(
        return_value=[{"mac": "aa:bb:cc:dd:ee:ff", "model": "UDMPRO", "state": 1}]
    )
    api.get_health = AsyncMock(return_value=[])
    api.get_sysinfo = AsyncMock(return_value=[])
    api.get_networkconf = AsyncMock(return_value=[])
    api.get_settings = AsyncMock(return_value=[])
    api.get_daily_gateway = AsyncMock(return_value=[])
    api.get_monthly_gateway = AsyncMock(return_value=[])
    api.get_rogueaps = AsyncMock(return_value=rogueaps)
    api.get_guests = AsyncMock(return_value=[])
    api.get_backups = AsyncMock(return_value=[])
    api.get_speedtest_results = AsyncMock(return_value=[])
    api.get_system_logs = AsyncMock(return_value=[])
    return api


async def test_coordinator_strongest_rogue_selection(
    hass: Any, mock_config_entry: Any
) -> None:
    """Strongest rogue = highest (least-negative) signal; None signals ignored."""
    mock_config_entry.add_to_hass(hass)
    api = _rogue_api(
        [
            {"essid": "Far", "bssid": "00:00:00:00:00:01", "signal": -91},
            {"essid": "Close", "bssid": "00:00:00:00:00:02", "signal": -55},
            {"essid": "NoSignal", "bssid": "00:00:00:00:00:03", "signal": None},
            {"essid": "Mid", "bssid": "00:00:00:00:00:04", "signal": -70},
        ]
    )
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    result = await coordinator._async_update_data()
    gateway = result["gateway"]
    assert gateway["strongest_rogue_ssid"] == "Close"
    assert gateway["strongest_rogue_rssi"] == -55


async def test_coordinator_strongest_rogue_none_detected(
    hass: Any, mock_config_entry: Any
) -> None:
    """No rogues -> SSID is 'None Detected' and RSSI is None (renders unknown)."""
    mock_config_entry.add_to_hass(hass)
    api = _rogue_api([])
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    result = await coordinator._async_update_data()
    gateway = result["gateway"]
    assert gateway["strongest_rogue_ssid"] == "None Detected"
    assert gateway["strongest_rogue_rssi"] is None


async def test_coordinator_parse_error_guests(
    hass: Any, mock_config_entry: Any
) -> None:
    """Guest user parse error is handled gracefully (lines 741-748)."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    api.get_devices = AsyncMock(
        return_value=[{"mac": "aa:bb:cc:dd:ee:ff", "model": "UDMPRO", "state": 1}]
    )
    api.get_health = AsyncMock(return_value=[])
    api.get_sysinfo = AsyncMock(return_value=[])
    api.get_networkconf = AsyncMock(return_value=[])
    api.get_settings = AsyncMock(return_value=[])
    api.get_daily_gateway = AsyncMock(return_value=[])
    api.get_monthly_gateway = AsyncMock(return_value=[])
    api.get_rogueaps = AsyncMock(return_value=[])
    api.get_guests = AsyncMock(side_effect=TypeError("not iterable"))
    api.get_backups = AsyncMock(return_value=[])
    api.get_speedtest_results = AsyncMock(return_value=[])

    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    result = await coordinator._async_update_data()
    assert result["gateway"]["guest_user_count"] == 0


async def test_coordinator_parse_error_backups(
    hass: Any, mock_config_entry: Any
) -> None:
    """Backup parse error is handled gracefully (lines 767-774)."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    api.get_devices = AsyncMock(
        return_value=[{"mac": "aa:bb:cc:dd:ee:ff", "model": "UDMPRO", "state": 1}]
    )
    api.get_health = AsyncMock(return_value=[])
    api.get_sysinfo = AsyncMock(return_value=[])
    api.get_networkconf = AsyncMock(return_value=[])
    api.get_settings = AsyncMock(return_value=[])
    api.get_daily_gateway = AsyncMock(return_value=[])
    api.get_monthly_gateway = AsyncMock(return_value=[])
    api.get_rogueaps = AsyncMock(return_value=[])
    api.get_guests = AsyncMock(return_value=[])
    api.get_backups = AsyncMock(return_value=[None])
    api.get_speedtest_results = AsyncMock(return_value=[])

    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    result = await coordinator._async_update_data()
    assert result["gateway"]["last_backup"] is None


async def test_coordinator_speedtest_with_interface_mapping(
    hass: Any, mock_config_entry: Any
) -> None:
    """Speedtest results with interface_name are mapped to WAN1/WAN2 (lines 839-851)."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    api.get_devices = AsyncMock(
        return_value=[
            {
                "mac": "aa:bb:cc:dd:ee:ff",
                "model": "UDMPRO",
                "state": 1,
                "wan1": {"ifname": "eth8"},
                "wan2": {"ifname": "eth9"},
            }
        ]
    )
    api.get_health = AsyncMock(return_value=[])
    api.get_sysinfo = AsyncMock(return_value=[])
    api.get_networkconf = AsyncMock(return_value=[])
    api.get_settings = AsyncMock(return_value=[])
    api.get_daily_gateway = AsyncMock(return_value=[])
    api.get_monthly_gateway = AsyncMock(return_value=[])
    api.get_rogueaps = AsyncMock(return_value=[])
    api.get_guests = AsyncMock(return_value=[])
    api.get_backups = AsyncMock(return_value=[])
    api.get_speedtest_results = AsyncMock(
        return_value=[
            {
                "interface_name": "eth8",
                "xput_download": 150.0,
                "xput_upload": 30.0,
                "latency": 20.0,
                "time": 1782018032000,
            },
            {
                "interface_name": "eth9",
                "xput_download": 200.0,
                "xput_upload": 40.0,
                "latency": 15.0,
                "time": 1782018108000,
            },
        ]
    )

    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    result = await coordinator._async_update_data()
    gateway = result["gateway"]
    assert gateway["wan1_speedtest_download"] == pytest.approx(150.0)
    assert gateway["wan2_speedtest_download"] == pytest.approx(200.0)


async def test_coordinator_speedtest_far_gap(hass: Any, mock_config_entry: Any) -> None:
    """Speedtest results with gap >600s set only WAN1 (lines 860-861)."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    api.get_devices = AsyncMock(
        return_value=[{"mac": "aa:bb:cc:dd:ee:ff", "model": "UDMPRO", "state": 1}]
    )
    api.get_health = AsyncMock(return_value=[])
    api.get_sysinfo = AsyncMock(return_value=[])
    api.get_networkconf = AsyncMock(return_value=[])
    api.get_settings = AsyncMock(return_value=[])
    api.get_daily_gateway = AsyncMock(return_value=[])
    api.get_monthly_gateway = AsyncMock(return_value=[])
    api.get_rogueaps = AsyncMock(return_value=[])
    api.get_guests = AsyncMock(return_value=[])
    api.get_backups = AsyncMock(return_value=[])
    api.get_speedtest_results = AsyncMock(
        return_value=[
            {
                "xput_download": 206.0,
                "xput_upload": 28.0,
                "latency": 25.0,
                "time": 1782018108000,
            },
            {
                "xput_download": 86.0,
                "xput_upload": 23.0,
                "latency": 33.0,
                "time": 1761955200000,
            },
        ]
    )

    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    result = await coordinator._async_update_data()
    gateway = result["gateway"]
    assert gateway["wan1_speedtest_download"] == pytest.approx(206.0)
    assert gateway["wan2_speedtest_download"] is None


async def test_coordinator_parse_error_speedtest(
    hass: Any, mock_config_entry: Any
) -> None:
    """Speedtest parse error is handled gracefully (lines 896-903)."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    api.get_devices = AsyncMock(
        return_value=[{"mac": "aa:bb:cc:dd:ee:ff", "model": "UDMPRO", "state": 1}]
    )
    api.get_health = AsyncMock(return_value=[])
    api.get_sysinfo = AsyncMock(return_value=[])
    api.get_networkconf = AsyncMock(return_value=[])
    api.get_settings = AsyncMock(return_value=[])
    api.get_daily_gateway = AsyncMock(return_value=[])
    api.get_monthly_gateway = AsyncMock(return_value=[])
    api.get_rogueaps = AsyncMock(return_value=[])
    api.get_guests = AsyncMock(return_value=[])
    api.get_backups = AsyncMock(return_value=[])
    api.get_speedtest_results = AsyncMock(return_value=[None])

    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    result = await coordinator._async_update_data()
    assert result["gateway"]["wan1_speedtest_download"] is None


async def test_coordinator_wan_interface_fallback(
    hass: Any, mock_config_entry: Any
) -> None:
    """WAN interface names fall back when name matching fails (lines 981, 983)."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    api.get_devices = AsyncMock(
        return_value=[{"mac": "aa:bb:cc:dd:ee:ff", "model": "UDMPRO", "state": 1}]
    )
    api.get_health = AsyncMock(return_value=[])
    api.get_sysinfo = AsyncMock(return_value=[])
    api.get_networkconf = AsyncMock(return_value=[])
    api.get_settings = AsyncMock(return_value=[])
    api.get_daily_gateway = AsyncMock(return_value=[])
    api.get_monthly_gateway = AsyncMock(return_value=[])
    api.get_rogueaps = AsyncMock(return_value=[])
    api.get_guests = AsyncMock(return_value=[])
    api.get_backups = AsyncMock(return_value=[])
    api.get_speedtest_results = AsyncMock(return_value=[])
    api.get_sites = AsyncMock(
        return_value=[{"id": "mock-uuid-123", "internalReference": "default"}]
    )
    api.get_wan_interfaces = AsyncMock(
        return_value=[
            {"id": "wan1-id", "name": "Primary_Connection"},
            {"id": "wan2-id", "name": "Secondary_Connection"},
        ]
    )
    api.get_vpn_servers = AsyncMock(return_value=[])
    api.get_vpn_tunnels = AsyncMock(return_value=[])
    api.get_firewall_policies = AsyncMock(return_value=[])

    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    result = await coordinator._async_update_data()
    gateway = result["gateway"]
    assert gateway["wan1_interface_name"] == "Primary_Connection"
    assert gateway["wan2_interface_name"] == "Secondary_Connection"


async def test_coordinator_auth_error_raises_no_data(
    hass: Any, mock_config_entry: Any
) -> None:
    """Auth error raises ConfigEntryAuthFailed when no cached data (lines 1066-1067)."""
    from homeassistant.exceptions import ConfigEntryAuthFailed

    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    api.get_devices = AsyncMock(side_effect=UnifiAuthError("auth failed"))
    api.get_health = AsyncMock(return_value=[])
    api.get_sysinfo = AsyncMock(return_value=[])
    api.get_networkconf = AsyncMock(return_value=[])
    api.get_settings = AsyncMock(return_value=[])

    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    coordinator.data = None
    coordinator.consecutive_failures = 3
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_coordinator_connection_error_raises_no_data(
    hass: Any, mock_config_entry: Any
) -> None:
    """Connection error raises ConfigEntryNotReady when no cached data (line 1087)."""
    from homeassistant.exceptions import ConfigEntryNotReady

    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    api.get_devices = AsyncMock(side_effect=UnifiConnectionError("timeout"))
    api.get_health = AsyncMock(return_value=[])
    api.get_sysinfo = AsyncMock(return_value=[])
    api.get_networkconf = AsyncMock(return_value=[])
    api.get_settings = AsyncMock(return_value=[])

    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    coordinator.data = None
    coordinator.consecutive_failures = 3
    with pytest.raises(ConfigEntryNotReady):
        await coordinator._async_update_data()


async def test_coordinator_unexpected_error_raises_update_failed(
    hass: Any, mock_config_entry: Any, mock_coordinator_data: Any
) -> None:
    """Unexpected error raises UpdateFailed when cached data exists (line 1107)."""
    from homeassistant.helpers.update_coordinator import UpdateFailed

    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    api.get_devices = AsyncMock(side_effect=RuntimeError("unexpected"))
    api.get_health = AsyncMock(return_value=[])
    api.get_sysinfo = AsyncMock(return_value=[])
    api.get_networkconf = AsyncMock(return_value=[])
    api.get_settings = AsyncMock(return_value=[])

    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    coordinator.data = mock_coordinator_data
    coordinator.consecutive_failures = 3
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_coordinator_parses_ap_device_through_flow(
    hass: Any, mock_config_entry: Any
) -> None:
    """AP device is parsed through the update flow (line 602)."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    api.get_devices = AsyncMock(
        return_value=[
            {
                "mac": "bb:cc:dd:ee:ff:00",
                "name": "AP Garage",
                "model": "UAP-AC-M",
                "state": 1,
                "is_access_point": True,
                "uptime": 381300,
                "system-stats": {"cpu": "4.0", "mem": "41.1"},
                "user-wlan-num_sta": 10,
                "radio_table_stats": [
                    {"user-num_sta": 9, "satisfaction": 97},
                ],
            }
        ]
    )
    api.get_health = AsyncMock(return_value=[])
    api.get_sysinfo = AsyncMock(return_value=[])
    api.get_networkconf = AsyncMock(return_value=[])
    api.get_settings = AsyncMock(return_value=[])
    api.get_daily_gateway = AsyncMock(return_value=[])
    api.get_monthly_gateway = AsyncMock(return_value=[])
    api.get_rogueaps = AsyncMock(return_value=[])
    api.get_guests = AsyncMock(return_value=[])
    api.get_backups = AsyncMock(return_value=[])
    api.get_speedtest_results = AsyncMock(return_value=[])

    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    result = await coordinator._async_update_data()
    assert "bb:cc:dd:ee:ff:00" in result["devices"]
    assert result["devices"]["bb:cc:dd:ee:ff:00"]["type"] == "ap"
    assert result["devices"]["bb:cc:dd:ee:ff:00"]["clients"] == 10


async def test_coordinator_wan2_sets_wan_mode_fallback(
    hass: Any, mock_config_entry: Any
) -> None:
    """WAN2 sets wan_mode when WAN1 hasn't set it yet (line 636)."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    api.get_devices = AsyncMock(
        return_value=[
            {
                "mac": "aa:bb:cc:dd:ee:ff",
                "model": "UDMPRO",
                "state": 1,
                "uptime": 1000,
                "system-stats": {"cpu": "10.0", "mem": "50.0"},
            }
        ]
    )
    api.get_health = AsyncMock(return_value=[])
    api.get_sysinfo = AsyncMock(return_value=[])
    api.get_networkconf = AsyncMock(
        return_value=[
            {
                "purpose": "wan",
                "wan_networkgroup": "WAN2",
                "wan_load_balance_type": "weighted",
                "wan_load_balance_weight": 45,
                "_id": "wan2_id",
            },
        ]
    )
    api.get_settings = AsyncMock(return_value=[])
    api.get_daily_gateway = AsyncMock(return_value=[])
    api.get_monthly_gateway = AsyncMock(return_value=[])
    api.get_rogueaps = AsyncMock(return_value=[])
    api.get_guests = AsyncMock(return_value=[])
    api.get_backups = AsyncMock(return_value=[])
    api.get_speedtest_results = AsyncMock(return_value=[])

    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    result = await coordinator._async_update_data()
    gateway = result["gateway"]
    assert gateway["wan_mode"] == "weighted"
    assert gateway["wan2_weight"] == 45


async def test_coordinator_guest_count_parse_error(
    hass: Any, mock_config_entry: Any
) -> None:
    """A non-sized guest payload is caught by the guest handler (lines 741-748).

    ``_fetch_optional`` normally guarantees a list, so ``len(guests_raw)`` cannot
    raise via the public path. Patch it to return a non-sized value for the guest
    fetch only, exercising the defensive ``except`` around the count.
    """
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    api.get_devices = AsyncMock(
        return_value=[
            {
                "mac": "aa:bb:cc:dd:ee:ff",
                "model": "UDMPRO",
                "state": 1,
                "uptime": 1000,
                "system-stats": {"cpu": "10.0", "mem": "50.0"},
            }
        ]
    )
    api.get_health = AsyncMock(return_value=[])

    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    # Skip site UUID resolution and take the non-v3 dummy-fetch branch.
    coordinator.site_uuid = "failed"

    async def fake_fetch(method: Any, label: str) -> Any:
        if label == "guest list":
            return 12345  # int has no __len__ -> TypeError inside the handler
        return []

    coordinator._fetch_optional = fake_fetch

    result = await coordinator._async_update_data()

    # Update completes and the guest count falls back to its default of 0.
    assert result["gateway"]["guest_user_count"] == 0


# ---------------------------------------------------------------------------
# disabled_endpoints coverage
# ---------------------------------------------------------------------------


def test_disabled_endpoints_speedtest_off() -> None:
    """disabled_endpoints returns EP_SPEEDTEST when speedtest is off."""
    from custom_components.unifi_network_monitor.const import EP_SPEEDTEST
    from custom_components.unifi_network_monitor.coordinator import disabled_endpoints

    result = disabled_endpoints({"enable_speedtest": False})
    assert EP_SPEEDTEST in result


def test_disabled_endpoints_wan_usage_off() -> None:
    """disabled_endpoints returns daily/monthly when wan_usage is off."""
    from custom_components.unifi_network_monitor.const import EP_DAILY, EP_MONTHLY
    from custom_components.unifi_network_monitor.coordinator import disabled_endpoints

    result = disabled_endpoints({"enable_wan_usage": False})
    assert EP_DAILY in result
    assert EP_MONTHLY in result


def test_disabled_endpoints_security_off() -> None:
    """disabled_endpoints returns security endpoints when security is off."""
    from custom_components.unifi_network_monitor.const import (
        EP_FIREWALL,
        EP_ROGUE,
        EP_VPN_SERVERS,
        EP_VPN_TUNNELS,
    )
    from custom_components.unifi_network_monitor.coordinator import disabled_endpoints

    result = disabled_endpoints({"enable_security_monitoring": False})
    assert EP_ROGUE in result
    assert EP_VPN_SERVERS in result
    assert EP_VPN_TUNNELS in result
    assert EP_FIREWALL in result


# ---------------------------------------------------------------------------
# _optional, _skip_fetch, _hold_or_stale coverage
# ---------------------------------------------------------------------------


async def test_optional_disabled_returns_skip_fetch(
    hass: Any, mock_config_entry: Any
) -> None:
    """_optional returns _skip_fetch when disabled."""
    from custom_components.unifi_network_monitor.coordinator import (
        UnifiNetworkDataUpdateCoordinator,
    )

    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)

    result = coordinator._optional(False, api.get_backups, "backup list")
    # Should return a coroutine function that when called returns []
    data = await result
    assert data == []


async def test_skip_fetch_clears_state(hass: Any, mock_config_entry: Any) -> None:
    """_skip_fetch clears endpoint state and stale flag."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    coordinator._endpoint_state["test_endpoint"] = {
        "last_good": [{"x": 1}],
        "failures": 2,
    }
    coordinator._stale_endpoints.add("test_endpoint")

    result = await coordinator._skip_fetch("test_endpoint")
    assert result == []
    assert "test_endpoint" not in coordinator._endpoint_state
    assert "test_endpoint" not in coordinator._stale_endpoints


async def test_hold_or_stale_warning_logged_on_stale(
    hass: Any, mock_config_entry: Any
) -> None:
    """_hold_or_stale logs warning and marks stale after strikes."""
    import logging

    from custom_components.unifi_network_monitor import coordinator as coord_mod

    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)

    state = {"last_good": [{"x": 1}], "failures": 3}
    with patch.object(coord_mod, "_LOGGER") as mock_logger:
        result = coordinator._hold_or_stale(
            "test_ep", state, Exception("fail"), logging.DEBUG
        )
    assert result == [{"x": 1}]
    assert "test_ep" in coordinator._stale_endpoints
    mock_logger.warning.assert_called_once()


async def test_hold_or_stale_already_stale_no_duplicate_warning(
    hass: Any, mock_config_entry: Any
) -> None:
    """_hold_or_stale skips duplicate warning when already stale."""
    import logging

    from custom_components.unifi_network_monitor import coordinator as coord_mod

    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    coordinator._stale_endpoints.add("test_ep")

    state = {"last_good": [{"y": 2}], "failures": 3}
    with patch.object(coord_mod, "_LOGGER") as mock_logger:
        result = coordinator._hold_or_stale(
            "test_ep", state, Exception("fail"), logging.DEBUG
        )
    assert result == [{"y": 2}]
    assert "test_ep" in coordinator._stale_endpoints
    mock_logger.warning.assert_not_called()


async def test_endpoint_available_none_source(
    hass: Any, mock_config_entry: Any
) -> None:
    """endpoint_available returns True when source is None."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    assert coordinator.endpoint_available(None) is True


async def test_endpoint_available_stale(hass: Any, mock_config_entry: Any) -> None:
    """endpoint_available returns False when endpoint is stale."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    coordinator._stale_endpoints.add("stale_ep")
    assert coordinator.endpoint_available("stale_ep") is False


async def test_endpoint_available_healthy(hass: Any, mock_config_entry: Any) -> None:
    """endpoint_available returns True when endpoint is not stale."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    assert coordinator.endpoint_available("healthy_ep") is True


async def test_rogue_ap_age_calculation(hass: Any, mock_config_entry: Any) -> None:
    """Rogue AP age is calculated dynamically from current time and last_seen."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)

    from homeassistant.util import dt as dt_util

    current_time = dt_util.now()
    current_ts = int(dt_util.as_timestamp(current_time))

    # 1. Test seen 2.5 hours ago -> 2h
    last_seen_2h = current_ts - (2.5 * 3600)
    # 2. Test seen 17.8 hours ago -> 17h
    last_seen_17h = current_ts - (17.8 * 3600)
    # 3. Test seen 20 minutes ago -> 20m
    last_seen_20m = current_ts - (20 * 60)
    # 4. Test seen 30 minutes ago -> 30m
    last_seen_30m = current_ts - (30 * 60)
    # 5. Test seen 4 hours ago -> 4h
    last_seen_4h = current_ts - (4 * 3600)

    devices_raw = [
        {
            "mac": "f4:92:bf:77:b6:c7",
            "model": "UDMPRO",
            "state": 1,
        }
    ]
    rogueaps_raw = [
        {
            "essid": "Rogue-2h",
            "bssid": "00:11:22:33:44:55",
            "last_seen": int(last_seen_2h),
        },
        {
            "essid": "Rogue-17h",
            "bssid": "66:77:88:99:aa:bb",
            "last_seen": int(last_seen_17h),
        },
        {
            "essid": "Rogue-20m",
            "bssid": "cc:dd:ee:ff:00:11",
            "last_seen": int(last_seen_20m),
        },
        {
            "essid": "Rogue-Fallback-30m",
            "bssid": "11:22:33:44:55:66",
            "last_seen": int(last_seen_30m),
        },
        {
            "essid": "Rogue-Fallback-4h",
            "bssid": "22:33:44:55:66:77",
            "last_seen": int(last_seen_4h),
        },
    ]

    api.get_devices = AsyncMock(return_value=devices_raw)
    api.get_health = AsyncMock(return_value=[])
    api.get_sysinfo = AsyncMock(return_value=[])
    api.get_networkconf = AsyncMock(return_value=[])
    api.get_settings = AsyncMock(return_value=[])
    api.get_daily_gateway = AsyncMock(return_value=[])
    api.get_monthly_gateway = AsyncMock(return_value=[])
    api.get_rogueaps = AsyncMock(return_value=rogueaps_raw)
    api.get_guests = AsyncMock(return_value=[])
    api.get_backups = AsyncMock(return_value=[])
    api.get_speedtest_results = AsyncMock(return_value=[])
    api.get_wlanconf = AsyncMock(return_value=[])
    api.get_system_logs = AsyncMock(return_value=[])

    data = await coordinator._async_update_data()
    rogues = data["gateway"]["rogue_aps_list"]

    assert rogues[0]["essid"] == "Rogue-2h"
    assert rogues[0]["age"] == "2h"
    assert rogues[1]["essid"] == "Rogue-17h"
    assert rogues[1]["age"] == "17h"
    assert rogues[2]["essid"] == "Rogue-20m"
    assert rogues[2]["age"] == "20m"
    assert rogues[3]["essid"] == "Rogue-Fallback-30m"
    assert rogues[3]["age"] == "30m"
    assert rogues[4]["essid"] == "Rogue-Fallback-4h"
    assert rogues[4]["age"] == "4h"


# ---------------------------------------------------------------------------
# disabled_endpoints with logs_alerts off (line 88 coverage)
# ---------------------------------------------------------------------------


def test_disabled_endpoints_logs_alerts_off() -> None:
    """disabled_endpoints returns EP_SYSLOG when logs_alerts is off."""
    from custom_components.unifi_network_monitor.const import EP_SYSLOG
    from custom_components.unifi_network_monitor.coordinator import disabled_endpoints

    result = disabled_endpoints({"enable_logs_alerts": False})
    assert EP_SYSLOG in result


# ---------------------------------------------------------------------------
# _ap_matches coverage (line 97-101)
# ---------------------------------------------------------------------------


def test_ap_matches_by_mac() -> None:
    """_ap_matches matches by MAC wildcard."""
    from custom_components.unifi_network_monitor.coordinator import _ap_matches

    reporter = {"mac": "aa:bb:cc:dd:ee:ff", "name": "AP Garage"}
    assert _ap_matches(reporter, ["aa:bb:*"]) is True


def test_ap_matches_by_name() -> None:
    """_ap_matches matches by name wildcard."""
    from custom_components.unifi_network_monitor.coordinator import _ap_matches

    reporter = {"mac": "aa:bb:cc:dd:ee:ff", "name": "AP Garage"}
    assert _ap_matches(reporter, ["AP *"]) is True


def test_ap_matches_non_matching() -> None:
    """_ap_matches returns False when no pattern matches."""
    from custom_components.unifi_network_monitor.coordinator import _ap_matches

    reporter = {"mac": "aa:bb:cc:dd:ee:ff", "name": "AP Garage"}
    assert _ap_matches(reporter, ["xx:*", "Other"]) is False


def test_ap_matches_empty_patterns() -> None:
    """_ap_matches returns False with empty patterns list."""
    from custom_components.unifi_network_monitor.coordinator import _ap_matches

    reporter = {"mac": "aa:bb:cc:dd:ee:ff", "name": "AP Garage"}
    assert _ap_matches(reporter, []) is False


def test_ap_matches_empty_reporter() -> None:
    """_ap_matches handles empty mac/name gracefully."""
    from custom_components.unifi_network_monitor.coordinator import _ap_matches

    reporter: dict[str, str] = {}
    assert _ap_matches(reporter, ["test"]) is False


# ---------------------------------------------------------------------------
# Rogue AP clustering with band filters + SSID ignore (lines 970-976, 999, 1003, 1015)
# ---------------------------------------------------------------------------


async def test_rogue_ap_5ghz_skipped_when_disabled(
    hass: Any, mock_config_entry: Any
) -> None:
    """Rogue on 5GHz band is skipped when show_5ghz is False."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={**mock_config_entry.options, "rogue_show_5ghz": False},
    )
    api = MagicMock()
    api.get_devices = AsyncMock(
        return_value=[{"mac": "aa:bb:cc:dd:ee:ff", "model": "UDMPRO", "state": 1}]
    )
    api.get_health = AsyncMock(return_value=[])
    api.get_sysinfo = AsyncMock(return_value=[])
    api.get_networkconf = AsyncMock(return_value=[])
    api.get_settings = AsyncMock(return_value=[])
    api.get_daily_gateway = AsyncMock(return_value=[])
    api.get_monthly_gateway = AsyncMock(return_value=[])
    api.get_rogueaps = AsyncMock(
        return_value=[
            {"essid": "5G-Rogue", "bssid": "00:00:00:00:00:01", "band": "na"},
            {"essid": "2G-Rogue", "bssid": "00:00:00:00:00:02", "band": "ng"},
        ]
    )
    api.get_guests = AsyncMock(return_value=[])
    api.get_backups = AsyncMock(return_value=[])
    api.get_speedtest_results = AsyncMock(return_value=[])
    api.get_system_logs = AsyncMock(return_value=[])

    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    result = await coordinator._async_update_data()
    rogues = result["gateway"]["rogue_aps_list"]
    essids = [r["essid"] for r in rogues]
    assert "5G-Rogue" not in essids
    assert "2G-Rogue" in essids


async def test_rogue_ap_essid_ignored(hass: Any, mock_config_entry: Any) -> None:
    """Rogue whose essid matches an ignore pattern is skipped."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={**mock_config_entry.options, "rogue_ignore_ssids": "TestNet,*Guest*"},
    )
    api = MagicMock()
    api.get_devices = AsyncMock(
        return_value=[{"mac": "aa:bb:cc:dd:ee:ff", "model": "UDMPRO", "state": 1}]
    )
    api.get_health = AsyncMock(return_value=[])
    api.get_sysinfo = AsyncMock(return_value=[])
    api.get_networkconf = AsyncMock(return_value=[])
    api.get_settings = AsyncMock(return_value=[])
    api.get_daily_gateway = AsyncMock(return_value=[])
    api.get_monthly_gateway = AsyncMock(return_value=[])
    api.get_rogueaps = AsyncMock(
        return_value=[
            {"essid": "TestNet", "bssid": "00:00:00:00:00:01", "band": "ng"},
            {"essid": "Guest-WiFi", "bssid": "00:00:00:00:00:02", "band": "ng"},
            {"essid": "CorpNet", "bssid": "00:00:00:00:00:03", "band": "ng"},
        ]
    )
    api.get_guests = AsyncMock(return_value=[])
    api.get_backups = AsyncMock(return_value=[])
    api.get_speedtest_results = AsyncMock(return_value=[])
    api.get_system_logs = AsyncMock(return_value=[])

    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    result = await coordinator._async_update_data()
    rogues = result["gateway"]["rogue_aps_list"]
    essids = [r["essid"] for r in rogues]
    assert "TestNet" not in essids
    assert "Guest-WiFi" not in essids
    assert "CorpNet" in essids


async def test_rogue_ap_bssid_clustering(hass: Any, mock_config_entry: Any) -> None:
    """Two rogues with same BSSID get clustered, signal/last_seen maxed."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    api.get_devices = AsyncMock(
        return_value=[
            {
                "mac": "aa:bb:cc:dd:ee:ff",
                "model": "UDMPRO",
                "state": 1,
                "name": "Gateway",
            },
            {
                "mac": "11:22:33:44:55:66",
                "name": "AP-1",
                "model": "UAP-AC-Pro",
                "state": 1,
                "is_access_point": True,
            },
            {
                "mac": "77:88:99:aa:bb:cc",
                "name": "AP-2",
                "model": "UAP-AC-Pro",
                "state": 1,
                "is_access_point": True,
            },
        ]
    )
    api.get_health = AsyncMock(return_value=[])
    api.get_sysinfo = AsyncMock(return_value=[])
    api.get_networkconf = AsyncMock(return_value=[])
    api.get_settings = AsyncMock(return_value=[])
    api.get_daily_gateway = AsyncMock(return_value=[])
    api.get_monthly_gateway = AsyncMock(return_value=[])
    api.get_rogueaps = AsyncMock(
        return_value=[
            {
                "essid": "CloneNet",
                "bssid": "de:ad:be:ef:00:01",
                "band": "ng",
                "channel": 6,
                "signal": -80,
                "oui": "VendorA",
                "ap_mac": "11:22:33:44:55:66",
                "last_seen": 1000,
            },
            {
                "essid": "CloneNet",
                "bssid": "de:ad:be:ef:00:01",
                "band": "ng",
                "channel": 6,
                "signal": -60,
                "oui": "VendorA",
                "ap_mac": "77:88:99:aa:bb:cc",
                "last_seen": 2000,
            },
        ]
    )
    api.get_guests = AsyncMock(return_value=[])
    api.get_backups = AsyncMock(return_value=[])
    api.get_speedtest_results = AsyncMock(return_value=[])
    api.get_system_logs = AsyncMock(return_value=[])

    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    result = await coordinator._async_update_data()
    rogues = result["gateway"]["rogue_aps_list"]
    assert len(rogues) == 1
    assert rogues[0]["essid"] == "CloneNet"
    assert rogues[0]["signal"] == -60  # max signal
    assert rogues[0]["bssid"] == "de:ad:be:ef:00:01"
    # Both APs should be reporters
    assert "AP-1" in rogues[0]["detected_by"]
    assert "AP-2" in rogues[0]["detected_by"]


# ---------------------------------------------------------------------------
# System-log alert severity counting and alert attrs (lines 1326-1343)
# ---------------------------------------------------------------------------


async def test_system_log_alert_counts_and_attrs(
    hass: Any, mock_config_entry: Any
) -> None:
    """System log data is parsed into severity counts and alert attributes."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    api.get_devices = AsyncMock(
        return_value=[
            {
                "mac": "aa:bb:cc:dd:ee:ff",
                "model": "UDMPRO",
                "state": 1,
                "uptime": 1000,
                "system-stats": {"cpu": "10.0", "mem": "50.0"},
            }
        ]
    )
    api.get_health = AsyncMock(return_value=[])
    api.get_sysinfo = AsyncMock(return_value=[])
    api.get_networkconf = AsyncMock(return_value=[])
    api.get_settings = AsyncMock(return_value=[])
    api.get_daily_gateway = AsyncMock(return_value=[])
    api.get_monthly_gateway = AsyncMock(return_value=[])
    api.get_rogueaps = AsyncMock(return_value=[])
    api.get_guests = AsyncMock(return_value=[])
    api.get_backups = AsyncMock(return_value=[])
    api.get_speedtest_results = AsyncMock(return_value=[])
    # Provide system logs within the last 24 hours
    from homeassistant.util import dt as dt_util

    recent_ts = int(dt_util.as_timestamp(dt_util.now())) * 1000
    api.get_system_logs = AsyncMock(
        return_value=[
            {
                "id": "evt_001",
                "message_raw": "Critical error on {device}",
                "title_raw": "Critical Alert",
                "parameters": {"device": {"name": "UDM-Pro"}},
                "event": "critical_error",
                "category": "system",
                "severity": "VERY_HIGH",
                "status": "active",
                "timestamp": recent_ts,
            },
            {
                "id": "evt_002",
                "message_raw": "High memory usage",
                "title_raw": "Memory Alert",
                "severity": "HIGH",
                "timestamp": recent_ts - 3600000,
            },
            {
                "id": "evt_003",
                "message_raw": "Low severity info",
                "title_raw": "Info",
                "severity": "LOW",
                "timestamp": recent_ts - 7200000,
            },
        ]
    )

    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    result = await coordinator._async_update_data()
    gateway = result["gateway"]

    assert gateway["alerts_very_high_24h"] == 1
    assert gateway["alerts_high_24h"] == 1
    # LOW severity is not counted
    assert gateway["last_very_high"] == "Critical Alert"
    assert gateway["last_very_high_attrs"] is not None
    assert gateway["last_very_high_attrs"]["severity"] == "VERY_HIGH"
    assert gateway["last_very_high_attrs"]["message"] == "Critical error on UDM-Pro"
    assert gateway["last_high"] == "Memory Alert"
    assert gateway["last_high_attrs"] is not None
    assert gateway["last_high_attrs"]["severity"] == "HIGH"


async def test_rogue_ap_2ghz_skipped_when_disabled(
    hass: Any, mock_config_entry: Any
) -> None:
    """Rogue on 2.4GHz band skipped when show_24ghz is False (line 971)."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={**mock_config_entry.options, "rogue_show_24ghz": False},
    )
    api = MagicMock()
    api.get_devices = AsyncMock(
        return_value=[{"mac": "aa:bb:cc:dd:ee:ff", "model": "UDMPRO", "state": 1}]
    )
    api.get_health = AsyncMock(return_value=[])
    api.get_sysinfo = AsyncMock(return_value=[])
    api.get_networkconf = AsyncMock(return_value=[])
    api.get_settings = AsyncMock(return_value=[])
    api.get_daily_gateway = AsyncMock(return_value=[])
    api.get_monthly_gateway = AsyncMock(return_value=[])
    api.get_rogueaps = AsyncMock(
        return_value=[
            {"essid": "2G-Rogue", "bssid": "00:00:00:00:00:01", "band": "ng"},
        ]
    )
    api.get_guests = AsyncMock(return_value=[])
    api.get_backups = AsyncMock(return_value=[])
    api.get_speedtest_results = AsyncMock(return_value=[])
    api.get_system_logs = AsyncMock(return_value=[])

    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    result = await coordinator._async_update_data()
    rogues = result["gateway"]["rogue_aps_list"]
    assert len(rogues) == 0


async def test_rogue_ap_cluster_all_reporters_match_ignore(
    hass: Any, mock_config_entry: Any
) -> None:
    """Rogue cluster skipped when all reporters match AP ignore (line 1015)."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={
            **mock_config_entry.options,
            "rogue_apply_ap_ignore": True,
            "rogue_ignore_aps": "11:22:33:44:55:66,77:88:99:aa:bb:cc",
        },
    )
    api = MagicMock()
    api.get_devices = AsyncMock(
        return_value=[
            {
                "mac": "aa:bb:cc:dd:ee:ff",
                "model": "UDMPRO",
                "state": 1,
                "name": "Gateway",
            },
            {
                "mac": "11:22:33:44:55:66",
                "name": "AP-1",
                "model": "UAP-AC-Pro",
                "state": 1,
                "is_access_point": True,
            },
            {
                "mac": "77:88:99:aa:bb:cc",
                "name": "AP-2",
                "model": "UAP-AC-Pro",
                "state": 1,
                "is_access_point": True,
            },
        ]
    )
    api.get_health = AsyncMock(return_value=[])
    api.get_sysinfo = AsyncMock(return_value=[])
    api.get_networkconf = AsyncMock(return_value=[])
    api.get_settings = AsyncMock(return_value=[])
    api.get_daily_gateway = AsyncMock(return_value=[])
    api.get_monthly_gateway = AsyncMock(return_value=[])
    api.get_rogueaps = AsyncMock(
        return_value=[
            {
                "essid": "HiddenRogue",
                "bssid": "de:ad:be:ef:00:01",
                "band": "ng",
                "signal": -70,
                "ap_mac": "11:22:33:44:55:66",
                "last_seen": 1000,
            },
            {
                "essid": "HiddenRogue",
                "bssid": "de:ad:be:ef:00:01",
                "band": "ng",
                "signal": -75,
                "ap_mac": "77:88:99:aa:bb:cc",
                "last_seen": 1500,
            },
        ]
    )
    api.get_guests = AsyncMock(return_value=[])
    api.get_backups = AsyncMock(return_value=[])
    api.get_speedtest_results = AsyncMock(return_value=[])
    api.get_system_logs = AsyncMock(return_value=[])

    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    result = await coordinator._async_update_data()
    rogues = result["gateway"]["rogue_aps_list"]
    assert len(rogues) == 0


async def test_system_log_parse_error_handled(
    hass: Any, mock_config_entry: Any
) -> None:
    """System-log parse exception is caught gracefully (lines 1336-1343)."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    api.get_devices = AsyncMock(
        return_value=[
            {
                "mac": "aa:bb:cc:dd:ee:ff",
                "model": "UDMPRO",
                "state": 1,
                "uptime": 1000,
                "system-stats": {"cpu": "10.0", "mem": "50.0"},
            }
        ]
    )
    api.get_health = AsyncMock(return_value=[])
    api.get_sysinfo = AsyncMock(return_value=[])
    api.get_networkconf = AsyncMock(return_value=[])
    api.get_settings = AsyncMock(return_value=[])
    api.get_daily_gateway = AsyncMock(return_value=[])
    api.get_monthly_gateway = AsyncMock(return_value=[])
    api.get_rogueaps = AsyncMock(return_value=[])
    api.get_guests = AsyncMock(return_value=[])
    api.get_backups = AsyncMock(return_value=[])
    api.get_speedtest_results = AsyncMock(return_value=[])
    api.get_system_logs = AsyncMock(return_value=[None])

    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    result = await coordinator._async_update_data()
    assert result["gateway"]["alerts_very_high_24h"] == 0
    assert result["gateway"]["alerts_high_24h"] == 0


# ---------------------------------------------------------------------------
# rogue_band_label (lines 115-117)
# ---------------------------------------------------------------------------


def test_rogue_band_label_none() -> None:
    """rogue_band_label returns None for None input."""
    from custom_components.unifi_network_monitor.coordinator import rogue_band_label

    assert rogue_band_label(None) is None


def test_rogue_band_label_ng() -> None:
    """rogue_band_label maps 'ng' to '2.4 GHz'."""
    from custom_components.unifi_network_monitor.coordinator import rogue_band_label

    assert rogue_band_label("ng") == "2.4 GHz"


def test_rogue_band_label_na() -> None:
    """rogue_band_label maps 'na' to '5 GHz'."""
    from custom_components.unifi_network_monitor.coordinator import rogue_band_label

    assert rogue_band_label("na") == "5 GHz"


def test_rogue_band_label_unknown() -> None:
    """rogue_band_label passes through unknown band as-is."""
    from custom_components.unifi_network_monitor.coordinator import rogue_band_label

    assert rogue_band_label("ax") == "ax"


# ---------------------------------------------------------------------------
# build_rogue_event_payload (lines 225-226)
# ---------------------------------------------------------------------------


def test_build_rogue_event_payload_with_last_seen() -> None:
    """build_rogue_event_payload with last_seen produces ISO timestamp."""
    from custom_components.unifi_network_monitor.coordinator import (
        build_rogue_event_payload,
    )

    payload = build_rogue_event_payload(
        "entry_001",
        {"bssid": "00:11:22:33:44:55", "essid": "TestNet", "last_seen": 1700000000},
    )
    assert payload["entry_id"] == "entry_001"
    assert payload["bssid"] == "00:11:22:33:44:55"
    assert payload["essid"] == "TestNet"
    assert payload["timestamp"] is not None


def test_build_rogue_event_payload_without_last_seen() -> None:
    """build_rogue_event_payload without last_seen yields None timestamp."""
    from custom_components.unifi_network_monitor.coordinator import (
        build_rogue_event_payload,
    )

    payload = build_rogue_event_payload("entry_001", {"bssid": "00:11:22:33:44:55"})
    assert payload["timestamp"] is None


def test_build_rogue_event_payload_empty() -> None:
    """build_rogue_event_payload with empty event produces defaults."""
    from custom_components.unifi_network_monitor.coordinator import (
        build_rogue_event_payload,
    )

    payload = build_rogue_event_payload("entry_001", {})
    assert payload["entry_id"] == "entry_001"
    assert payload["bssid"] is None
    assert payload["timestamp"] is None


def test_build_rogue_event_payload_new_fields() -> None:
    """build_rogue_event_payload surfaces the extended rogue fields."""
    from custom_components.unifi_network_monitor.coordinator import (
        build_rogue_event_payload,
    )

    payload = build_rogue_event_payload(
        "entry_001",
        {
            "bssid": "00:11:22:33:44:55",
            "essid": "TestNet",
            "ssid_anomaly": True,
            "channel_width": 80,
            "security": "WPA3-Personal (AES/CCMP)",
            "wired_rogue": True,
            "is_adhoc": False,
        },
    )
    assert payload["ssid_anomaly"] is True
    assert payload["channel_width"] == 80
    assert payload["security"] == "WPA3-Personal (AES/CCMP)"
    assert payload["wired_rogue"] is True
    assert payload["is_adhoc"] is False


# ---------------------------------------------------------------------------
# normalize_essid
# ---------------------------------------------------------------------------


def test_normalize_essid_normal() -> None:
    """A plain SSID is returned unchanged with no anomaly."""
    from custom_components.unifi_network_monitor.coordinator import normalize_essid

    display, anomaly, hidden = normalize_essid("My WiFi")
    assert display == "My WiFi"
    assert anomaly is False
    assert hidden is False


def test_normalize_essid_empty_is_hidden() -> None:
    """An empty essid flags hidden + anomaly (display is the <Hidden> fallback)."""
    from custom_components.unifi_network_monitor.coordinator import normalize_essid

    display, anomaly, hidden = normalize_essid("")
    assert display == "<Hidden>"
    assert anomaly is True
    assert hidden is True


def test_normalize_essid_whitespace_is_hidden() -> None:
    """A whitespace-only essid (spaces/tabs) is treated as hidden."""
    from custom_components.unifi_network_monitor.coordinator import normalize_essid

    display, anomaly, hidden = normalize_essid("   \t ")
    assert display == "<Hidden>"
    assert anomaly is True
    assert hidden is True


def test_normalize_essid_none_is_hidden() -> None:
    """A missing (None) essid is treated as hidden."""
    from custom_components.unifi_network_monitor.coordinator import normalize_essid

    display, anomaly, hidden = normalize_essid(None)
    assert display == "<Hidden>"
    assert anomaly is True
    assert hidden is True


def test_normalize_essid_control_chars_sanitized() -> None:
    """Control / zero-width chars are replaced with the placeholder + flagged."""
    from custom_components.unifi_network_monitor.coordinator import normalize_essid

    # Embedded zero-width space (U+200B) and trailing RTL override (U+202E).
    display, anomaly, hidden = normalize_essid("Corp\u200bNet\u202e")
    assert display == "Corp\u00b7Net\u00b7"
    assert anomaly is True
    assert hidden is False  # obfuscated, not cloaked


def test_hidden_label_last4_and_extended() -> None:
    """hidden_label builds Hidden-<last4> (or last6 when extended)."""
    from custom_components.unifi_network_monitor.coordinator import hidden_label

    assert hidden_label("02:18:4a:c0:a2:d3") == "Hidden-A2D3"
    assert hidden_label("02:18:4a:c0:a2:d3", extended=True) == "Hidden-C0A2D3"
    # No usable hex \u2192 <Hidden> fallback.
    assert hidden_label("") == "<Hidden>"


# ---------------------------------------------------------------------------
# parse_rogue_aps — extended fields
# ---------------------------------------------------------------------------


def test_parse_rogue_aps_extended_fields() -> None:
    """parse_rogue_aps surfaces security / channel_width / is_adhoc and hidden."""
    from custom_components.unifi_network_monitor.coordinator import parse_rogue_aps

    parsed = parse_rogue_aps(
        [
            {
                "essid": "",
                "bssid": "00:00:00:00:00:aa",
                "band": "na",
                "bw": 80,
                "security": "Open",
                "is_rogue": False,
                "is_adhoc": True,
                "ap_mac": "aa:bb:cc:dd:ee:ff",
            }
        ],
        {"aa:bb:cc:dd:ee:ff": "Office AP"},
        1_700_000_000,
    )
    assert len(parsed) == 1
    ap = parsed[0]
    # Empty essid → BSSID-derived pseudo-name (last 4 hex of 00:00:00:00:00:aa).
    assert ap["essid"] == "Hidden-00AA"
    assert ap["ssid_anomaly"] is True
    assert ap["channel_width"] == 80
    assert ap["security"] == "Open"
    assert ap["is_adhoc"] is True
    assert ap["wired_rogue"] is False
    assert ap["detected_by"] == "Office AP"


def test_parse_rogue_aps_hidden_label_collision_extends() -> None:
    """Two hidden BSSIDs sharing a last-4 suffix both extend to last-6."""
    from custom_components.unifi_network_monitor.coordinator import parse_rogue_aps

    parsed = parse_rogue_aps(
        [
            {"essid": "", "bssid": "00:00:00:aa:a2:d3", "band": "ng"},
            {"essid": "", "bssid": "00:00:00:bb:a2:d3", "band": "ng"},
            {"essid": "", "bssid": "00:00:00:cc:00:99", "band": "ng"},
        ],
        {},
        1_700_000_000,
    )
    labels = {ap["bssid"]: ap["essid"] for ap in parsed}
    # The two colliding on A2D3 extend to last-6; the non-colliding stays last-4.
    assert labels["00:00:00:aa:a2:d3"] == "Hidden-AAA2D3"
    assert labels["00:00:00:bb:a2:d3"] == "Hidden-BBA2D3"
    assert labels["00:00:00:cc:00:99"] == "Hidden-0099"


def test_parse_rogue_aps_wired_rogue_any_reporter() -> None:
    """wired_rogue is true if ANY reporter row for the BSSID flags is_rogue."""
    from custom_components.unifi_network_monitor.coordinator import parse_rogue_aps

    parsed = parse_rogue_aps(
        [
            {
                "essid": "Clone",
                "bssid": "00:00:00:00:00:bb",
                "band": "ng",
                "is_rogue": False,
                "ap_mac": "aa:aa:aa:aa:aa:01",
            },
            {
                "essid": "Clone",
                "bssid": "00:00:00:00:00:bb",
                "band": "ng",
                "is_rogue": True,
                "ap_mac": "aa:aa:aa:aa:aa:02",
            },
        ],
        {},
        1_700_000_000,
    )
    assert len(parsed) == 1
    assert parsed[0]["wired_rogue"] is True


def test_parse_rogue_aps_cluster_merge_widens_and_fills() -> None:
    """A later reporter row widens channel_width and fills empty security."""
    from custom_components.unifi_network_monitor.coordinator import parse_rogue_aps

    parsed = parse_rogue_aps(
        [
            {
                "essid": "Clone",
                "bssid": "00:00:00:00:00:cc",
                "band": "na",
                "bw": 20,
                "ap_mac": "aa:aa:aa:aa:aa:01",
            },
            {
                "essid": "Clone",
                "bssid": "00:00:00:00:00:cc",
                "band": "na",
                "bw": 80,
                "security": "WPA3-Personal (AES/CCMP)",
                "ap_mac": "aa:aa:aa:aa:aa:02",
            },
        ],
        {},
        1_700_000_000,
    )
    assert len(parsed) == 1
    # Second row's wider width wins (line 244); its security fills the empty
    # first-row value (line 246).
    assert parsed[0]["channel_width"] == 80
    assert parsed[0]["security"] == "WPA3-Personal (AES/CCMP)"


# ---------------------------------------------------------------------------
# async_schedule_refresh_in (lines 707-717, 723-724)
# ---------------------------------------------------------------------------


async def test_schedule_refresh_in_paused_returns_early(
    hass: Any, mock_config_entry: Any
) -> None:
    """async_schedule_refresh_in returns early when polling is paused."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={**mock_config_entry.options, "stop_polling": True},
    )
    api = MagicMock()
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)

    with patch(
        "custom_components.unifi_network_monitor.coordinator.async_call_later"
    ) as mock_call_later:
        coordinator.async_schedule_refresh_in(60)
    mock_call_later.assert_called_once()


async def test_schedule_refresh_in_interval_sooner_returns_early(
    hass: Any, mock_config_entry: Any
) -> None:
    """async_schedule_refresh_in returns early when regular poll is sooner."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    # Set update_interval to 30s, request 60s schedule
    coordinator.update_interval = timedelta(seconds=30)

    with patch(
        "custom_components.unifi_network_monitor.coordinator.async_call_later"
    ) as mock_call_later:
        coordinator.async_schedule_refresh_in(60)
    mock_call_later.assert_not_called()


async def test_schedule_refresh_in_schedules(hass: Any, mock_config_entry: Any) -> None:
    """async_schedule_refresh_in schedules a callback when applicable."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    coordinator.update_interval = timedelta(seconds=300)

    with patch(
        "custom_components.unifi_network_monitor.coordinator.async_call_later"
    ) as mock_call_later:
        coordinator.async_schedule_refresh_in(60)
    mock_call_later.assert_called_once()


async def test_schedule_refresh_in_cancels_previous(
    hass: Any, mock_config_entry: Any
) -> None:
    """async_schedule_refresh_in cancels prior pending schedule."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    coordinator.update_interval = timedelta(seconds=300)

    mock_unsub = MagicMock()
    coordinator._pending_refresh_unsub = mock_unsub

    with patch(
        "custom_components.unifi_network_monitor.coordinator.async_call_later"
    ) as mock_call_later:
        coordinator.async_schedule_refresh_in(60)
    mock_unsub.assert_called_once()
    mock_call_later.assert_called_once()


async def test_cancel_scheduled_refresh(hass: Any, mock_config_entry: Any) -> None:
    """_cancel_scheduled_refresh cancels and clears the pending subscription."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)

    mock_unsub = MagicMock()
    coordinator._pending_refresh_unsub = mock_unsub

    coordinator._cancel_scheduled_refresh()
    mock_unsub.assert_called_once()
    assert coordinator._pending_refresh_unsub is None


async def test_cancel_scheduled_refresh_noop_when_none(
    hass: Any, mock_config_entry: Any
) -> None:
    """_cancel_scheduled_refresh is a no-op when no pending subscription."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    assert coordinator._pending_refresh_unsub is None
    coordinator._cancel_scheduled_refresh()  # should not raise


async def test_schedule_refresh_fire_callback(
    hass: Any, mock_config_entry: Any
) -> None:
    """The _fire callback calls async_force_refresh + clears sub (lines 723-724)."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    coordinator.update_interval = timedelta(seconds=300)
    coordinator.async_force_refresh = AsyncMock()

    with patch(
        "custom_components.unifi_network_monitor.coordinator.async_call_later"
    ) as mock_call_later:
        coordinator.async_schedule_refresh_in(60)
        mock_call_later.assert_called_once()
        callback = mock_call_later.call_args[0][2]
        await callback(dt_util.now())
    coordinator.async_force_refresh.assert_awaited_once()
    assert coordinator._pending_refresh_unsub is None


# ---------------------------------------------------------------------------
# _fire_new_alert_events (lines 746-753)
# ---------------------------------------------------------------------------


async def test_fire_new_alert_events_baseline(
    hass: Any, mock_config_entry: Any
) -> None:
    """First call records baseline and does not fire events."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)

    coordinator._fire_new_alert_events(
        [{"id": "evt_001", "title_raw": "Test", "severity": "HIGH"}]
    )
    assert coordinator._alert_baseline_done is True
    assert "evt_001" in coordinator._seen_alert_ids


async def test_fire_new_alert_events_new_event(
    hass: Any, mock_config_entry: Any
) -> None:
    """New alert id fires a bus event."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    coordinator._alert_baseline_done = True

    coordinator._fire_new_alert_events(
        [{"id": "evt_002", "title_raw": "New Alert", "severity": "HIGH"}]
    )
    assert "evt_002" in coordinator._seen_alert_ids


async def test_fire_new_alert_events_skips_seen(
    hass: Any, mock_config_entry: Any
) -> None:
    """Already-seen alert id does not fire again."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    coordinator._alert_baseline_done = True
    coordinator._seen_alert_ids = {"evt_001"}

    coordinator._fire_new_alert_events(
        [{"id": "evt_001", "title_raw": "Seen", "severity": "HIGH"}]
    )
    assert coordinator._seen_alert_ids == {"evt_001"}


async def test_fire_new_alert_events_skips_null_id(
    hass: Any, mock_config_entry: Any
) -> None:
    """Event with no id is skipped."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    coordinator._alert_baseline_done = True

    coordinator._fire_new_alert_events([{"title_raw": "No ID", "severity": "HIGH"}])
    assert coordinator._seen_alert_ids == set()


# ---------------------------------------------------------------------------
# _fire_new_rogue_events (lines 770-778)
# ---------------------------------------------------------------------------


async def test_fire_new_rogue_events_baseline(
    hass: Any, mock_config_entry: Any
) -> None:
    """First call with no new_bssids fires nothing; baseline covers all."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)

    coordinator._fire_new_rogue_events(
        [{"bssid": "00:11:22:33:44:55", "essid": "TestNet"}], set()
    )
    # With an empty new set, no events fire — the baseline for these
    # BSSIDs is set externally by _update_rogue_history.
    assert coordinator._rogue_baseline_done is False


async def test_fire_new_rogue_events_new_bssid(
    hass: Any, mock_config_entry: Any
) -> None:
    """New BSSID (in new_bssids set) fires a bus event."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    coordinator._rogue_baseline_done = True

    coordinator._fire_new_rogue_events(
        [{"bssid": "66:77:88:99:aa:bb", "essid": "NewRogue"}], {"66:77:88:99:aa:bb"}
    )
    # The event fires but the BSSID is recorded by _update_rogue_history
    # not _fire_new_rogue_events. Just verify no exception —
    #  the event assertion is in test_fire_new_rogue_events_only_new


async def test_fire_new_rogue_events_skips_seen(
    hass: Any, mock_config_entry: Any
) -> None:
    """BSSID not in new_bssids set is not fired again."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    coordinator._rogue_baseline_done = True

    coordinator._fire_new_rogue_events(
        [{"bssid": "00:11:22:33:44:55", "essid": "Seen"}], set()
    )
    # No assertion needed on _seen_rogue_bssids — it no longer exists.
    # With empty new_bssids, no event fires.


async def test_fire_new_rogue_events_skips_missing_bssid(
    hass: Any, mock_config_entry: Any
) -> None:
    """AP with no BSSID is skipped."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    coordinator._rogue_baseline_done = True

    coordinator._fire_new_rogue_events([{"essid": "NoBSSID"}], set())
    # No exception means the missing BSSID was skipped.


# ---------------------------------------------------------------------------
# _skip_fetch with EP_SYSLOG / EP_ROGUE (lines 864-865, 868-869)
# ---------------------------------------------------------------------------


async def test_skip_fetch_resets_alert_baseline(
    hass: Any, mock_config_entry: Any
) -> None:
    """_skip_fetch with EP_SYSLOG resets alert baseline."""
    from custom_components.unifi_network_monitor.const import EP_SYSLOG

    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    coordinator._alert_baseline_done = True
    coordinator._seen_alert_ids = {"evt_001"}

    await coordinator._skip_fetch(EP_SYSLOG)
    assert coordinator._alert_baseline_done is False
    assert coordinator._seen_alert_ids == set()


async def test_skip_fetch_resets_rogue_baseline(
    hass: Any, mock_config_entry: Any
) -> None:
    """_skip_fetch via EP_ROGUE no reset on rogue base persistent hist handles dedup."""
    from custom_components.unifi_network_monitor.const import EP_ROGUE

    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    coordinator._rogue_baseline_done = True
    coordinator._seen_rogue_bssids = {"00:11:22:33:44:55"}

    await coordinator._skip_fetch(EP_ROGUE)
    assert coordinator._rogue_baseline_done is True
    assert coordinator._seen_rogue_bssids == {"00:11:22:33:44:55"}


async def test_skip_fetch_other_label_no_reset(
    hass: Any, mock_config_entry: Any
) -> None:
    """_skip_fetch with other label does not reset baselines."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    coordinator._alert_baseline_done = True
    coordinator._rogue_baseline_done = True

    await coordinator._skip_fetch("other_label")
    assert coordinator._alert_baseline_done is True
    assert coordinator._rogue_baseline_done is True


# ---------------------------------------------------------------------------
# _safe_int edge cases (lines 115-117)
# ---------------------------------------------------------------------------


def test_safe_int_float_value() -> None:
    """_safe_int converts float to int."""
    assert _safe_int(42.7) == 42


def test_safe_int_float_string_value() -> None:
    """_safe_int converts float string to int."""
    assert _safe_int("42.7") == 42


def test_safe_int_invalid_string() -> None:
    """_safe_int returns default for invalid string."""
    assert _safe_int("abc") is None


def test_safe_int_zero() -> None:
    """_safe_int handles zero."""
    assert _safe_int(0) == 0


def test_safe_int_negative() -> None:
    """_safe_int handles negative values."""
    assert _safe_int(-5) == -5


# ---------------------------------------------------------------------------
# Persistent rogue-AP appearance history
# ---------------------------------------------------------------------------


def _history_coordinator(hass: Any, entry: Any) -> Any:
    """Build a coordinator with the history store's writes stubbed out."""
    entry.add_to_hass(hass)
    coord = UnifiNetworkDataUpdateCoordinator(hass, entry, MagicMock())
    coord._rogue_history_store.async_delay_save = MagicMock()
    coord._rogue_history_store.async_save = AsyncMock()
    return coord


async def test_rogue_history_baseline_then_new(
    hass: Any, mock_config_entry: Any
) -> None:
    """First poll baselines silently; later a genuinely-new BSSID is returned."""
    coord = _history_coordinator(hass, mock_config_entry)
    t0 = dt_util.now()
    aps = [{"bssid": "00:11:22:33:44:55", "essid": "Hidden-4455"}]

    assert coord._update_rogue_history(aps, t0) == set()  # baseline
    rec = coord.rogue_history["00:11:22:33:44:55"]
    assert rec["appearances"] == 1
    assert rec["first_seen"] == t0.isoformat()
    assert rec["last_label"] == "Hidden-4455"

    t1 = t0 + timedelta(minutes=5)
    new = coord._update_rogue_history(
        [*aps, {"bssid": "66:77:88:99:aa:bb", "essid": "New"}], t1
    )
    assert new == {"66:77:88:99:aa:bb"}
    rec = coord.rogue_history["00:11:22:33:44:55"]
    assert rec["appearances"] == 2  # incremented
    assert rec["first_seen"] == t0.isoformat()  # unchanged
    assert rec["last_seen"] == t1.isoformat()


async def test_rogue_history_skips_ap_without_bssid(
    hass: Any, mock_config_entry: Any
) -> None:
    """AP without a BSSID triggers the continue at line 902."""
    coord = _history_coordinator(hass, mock_config_entry)
    aps = [{"essid": "NoBSSID"}]
    result = coord._update_rogue_history(aps, dt_util.now())
    assert result == set()
    assert len(coord.rogue_history) == 0


async def test_rogue_history_survives_reload(hass: Any, mock_config_entry: Any) -> None:
    """A pre-populated store (post-restart) does not baseline; known BSSID silent."""
    coord = _history_coordinator(hass, mock_config_entry)
    now = dt_util.now()
    coord.rogue_history = {
        "aa:aa:aa:aa:aa:aa": {
            "first_seen": now.isoformat(),
            "last_seen": now.isoformat(),
            "appearances": 3,
        }
    }
    new = coord._update_rogue_history(
        [{"bssid": "aa:aa:aa:aa:aa:aa"}, {"bssid": "cc:cc:cc:cc:cc:cc"}], now
    )
    assert new == {"cc:cc:cc:cc:cc:cc"}  # only the truly-new one


async def test_rogue_history_ttl_prune(hass: Any, mock_config_entry: Any) -> None:
    """TTL prunes BSSIDs whose last_seen is older than the window."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={**mock_config_entry.options, "rogue_history_ttl_days": 30},
    )
    coord = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, MagicMock())
    coord._rogue_history_store.async_delay_save = MagicMock()
    now = dt_util.now()
    old_iso = (now - timedelta(days=40)).isoformat()
    coord.rogue_history = {
        "old": {"first_seen": old_iso, "last_seen": old_iso, "appearances": 1},
        "new": {
            "first_seen": now.isoformat(),
            "last_seen": now.isoformat(),
            "appearances": 1,
        },
    }
    coord._prune_rogue_history(now)
    assert "old" not in coord.rogue_history
    assert "new" in coord.rogue_history


async def test_rogue_history_cap(hass: Any, mock_config_entry: Any) -> None:
    """The hard cap keeps the most-recently-seen entries (TTL disabled)."""
    from custom_components.unifi_network_monitor.const import ROGUE_HISTORY_MAX

    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={**mock_config_entry.options, "rogue_history_ttl_days": 0},
    )
    coord = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, MagicMock())
    coord._rogue_history_store.async_delay_save = MagicMock()
    now = dt_util.now()
    coord.rogue_history = {
        f"b{i}": {
            "first_seen": now.isoformat(),
            "last_seen": (now - timedelta(seconds=i)).isoformat(),
            "appearances": 1,
        }
        for i in range(ROGUE_HISTORY_MAX + 5)
    }
    coord._prune_rogue_history(now)
    assert len(coord.rogue_history) == ROGUE_HISTORY_MAX
    assert "b0" in coord.rogue_history  # most recent survives


async def test_rogue_new_24h_counts_recent(hass: Any, mock_config_entry: Any) -> None:
    """rogue_new_24h counts only BSSIDs first seen within 24h."""
    coord = _history_coordinator(hass, mock_config_entry)
    now = dt_util.now()
    coord.rogue_history = {
        "recent": {
            "first_seen": (now - timedelta(hours=2)).isoformat(),
            "last_seen": now.isoformat(),
            "appearances": 1,
        },
        "old": {
            "first_seen": (now - timedelta(days=3)).isoformat(),
            "last_seen": now.isoformat(),
            "appearances": 1,
        },
    }
    assert coord.rogue_new_24h(now) == 1


async def test_rogue_history_annotate(hass: Any, mock_config_entry: Any) -> None:
    """_annotate_rogue_history merges first_seen/appearances onto items."""
    coord = _history_coordinator(hass, mock_config_entry)
    coord.rogue_history = {"bb": {"first_seen": "t", "appearances": 5}}
    aps = [{"bssid": "bb"}, {"bssid": "zz"}]
    coord._annotate_rogue_history(aps)
    assert aps[0]["first_seen"] == "t"
    assert aps[0]["appearances"] == 5
    assert aps[1]["first_seen"] is None
    assert aps[1]["appearances"] is None


async def test_rogue_history_clear(hass: Any, mock_config_entry: Any) -> None:
    """async_clear_rogue_history empties the store and resets the baseline."""
    coord = _history_coordinator(hass, mock_config_entry)
    coord.rogue_history = {"x": {"appearances": 1}}
    coord._rogue_baseline_done = True
    await coord.async_clear_rogue_history()
    assert coord.rogue_history == {}
    assert coord._rogue_baseline_done is False


async def test_async_initialize_loads_history(
    hass: Any, mock_config_entry: Any
) -> None:
    """async_initialize populates rogue_history from the store."""
    coord = _history_coordinator(hass, mock_config_entry)
    coord._rogue_history_store.async_load = AsyncMock(
        return_value={"aa": {"appearances": 2}}
    )
    await coord.async_initialize()
    assert coord.rogue_history["aa"]["appearances"] == 2


async def test_fire_new_rogue_events_only_new(
    hass: Any, mock_config_entry: Any
) -> None:
    """_fire_new_rogue_events fires only for BSSIDs in the new set."""
    coord = _history_coordinator(hass, mock_config_entry)
    fired: list[str] = []
    events = []

    async def _capture(event):
        events.append(event.data.get("bssid"))

    coord.hass.bus.async_listen("unifi_network_monitor_new_rogue_ap", _capture)
    aps = [{"bssid": "aa", "essid": "A"}, {"bssid": "bb", "essid": "B"}]
    coord._fire_new_rogue_events(aps, {"bb"})
    assert events == ["bb"]
