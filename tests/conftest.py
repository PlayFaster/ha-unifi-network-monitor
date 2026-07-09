"""Shared test fixtures for UniFi Network Monitor."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.unifi_network_monitor.const import (
    CONF_API_KEY,
    CONF_ENABLE_SECURITY_MONITORING,
    CONF_ENABLE_SPEEDTEST,
    CONF_ENABLE_WAN_USAGE,
    CONF_SCAN_INTERVAL,
    CONF_SITE,
    CONF_UNIFI_DEVICE_MODE,
    DEFAULT_ENABLE_SECURITY_MONITORING,
    DEFAULT_ENABLE_SPEEDTEST,
    DEFAULT_ENABLE_WAN_USAGE,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SITE,
    DEVICE_MODE_ALL,
    DOMAIN,
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: Any) -> None:
    """Enable loading of custom integrations for all tests."""
    yield


# ---------------------------------------------------------------------------
# Shared fixture data
# ---------------------------------------------------------------------------

MOCK_HOST = "192.168.1.1"
MOCK_API_KEY = "test-api-key-abc123"
MOCK_MAC = "aa:bb:cc:dd:ee:ff"
MOCK_MODEL = "UDMPRO"
MOCK_SW_VERSION = "5.1.19.33549"

MOCK_ENTRY_DATA = {
    "mac": MOCK_MAC,
    "model": MOCK_MODEL,
    "sw_version": MOCK_SW_VERSION,
}

MOCK_ENTRY_OPTIONS = {
    "host": MOCK_HOST,
    CONF_API_KEY: MOCK_API_KEY,
    "username": "",
    "password": "",
    CONF_SITE: DEFAULT_SITE,
    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
    CONF_UNIFI_DEVICE_MODE: DEVICE_MODE_ALL,
    CONF_ENABLE_SPEEDTEST: DEFAULT_ENABLE_SPEEDTEST,
    CONF_ENABLE_WAN_USAGE: DEFAULT_ENABLE_WAN_USAGE,
    CONF_ENABLE_SECURITY_MONITORING: DEFAULT_ENABLE_SECURITY_MONITORING,
}

# Minimal realistic coordinator data
MOCK_COORDINATOR_DATA: dict[str, Any] = {
    "gateway": {
        "mac": MOCK_MAC,
        "name": "UDM Pro",
        "model": MOCK_MODEL,
        "cpu": 37.2,
        "ram": 72.0,
        "uptime_secs": 250701,
        "boot_time": None,
        "internet": True,
        "speedtest_status": True,
        "storage_used": 415272960,
        "storage_size": 2046640128,
        "cpu_temp": 48.0,
        "board_temp": 45.25,
        "wan1_local_ip": "192.0.2.1",
        "wan1_public_ip": "198.51.100.1",
        "wan2_local_ip": "192.0.2.2",
        "wan2_public_ip": "203.0.113.1",
        "update_available": False,
        "ports_used": 157,
        "ports_user": 157,
        "ports_guest": 0,
        "storage_used_pct": 20.3,
        "wan_mode": "weighted",
        "wan1_weight": 55,
        "wan2_weight": 45,
        "wan1_latency": 34,
        "wan2_latency": 22,
        "wan1_availability": 100.0,
        "wan2_availability": 100.0,
        "wan1_active": True,
        "wan2_active": False,
        "wan1_up": True,
        "wan2_up": True,
        "wan1_sfp_found": None,
        "wan1_sfp_vendor": None,
        "wan1_sfp_part": None,
        "wan1_sfp_serial": None,
        "wan2_sfp_found": True,
        "wan2_sfp_vendor": "UBNT",
        "wan2_sfp_part": "UF-RJ45-1G",
        "wan2_sfp_serial": "SN0000000001",
        "ips_mode": "block",
        "ad_blocking": True,
        "honeypot": True,
        "wan1_today_rx": 23111264016.0,
        "wan1_today_tx": 17844587939.0,
        "wan2_today_rx": 13954880357.0,
        "wan2_today_tx": 1573353319.0,
        "wan1_month_rx": 1240803294198.0,
        "wan1_month_tx": 366382323175.0,
        "wan2_month_rx": 1350250403084.0,
        "wan2_month_tx": 507108166710.0,
        "rogue_ap_count": 3,
        "rogue_aps_list": [
            {
                "essid": "RogueNet-1",
                "bssid": "de:ad:be:ef:00:01",
                "channel": 1,
                "signal": -89,
                "oui": "Example Vendor",
                "age": "120h",
                "detected_by": "AP-1",
            },
            {
                "essid": "RogueNet-2",
                "bssid": "de:ad:be:ef:00:02",
                "channel": 36,
                "signal": -87,
                "oui": "",
                "age": None,
                "detected_by": "",
            },
            {
                "essid": "RogueNet-3",
                "bssid": "de:ad:be:ef:00:03",
                "channel": 1,
                "signal": -91,
                "oui": "",
                "age": None,
                "detected_by": "",
            },
        ],
        "strongest_rogue_ssid": "RogueNet-2",
        "strongest_rogue_rssi": -87,
        "guest_user_count": 0,
        "last_backup": datetime(2026, 4, 4, 3, 0, 0, tzinfo=UTC),
        "configured_vlans": 5,
        "application_version": "9.2.87",
        "application_build": "15432",
        "device_type": "udm",
        "udm_version": "3.2.12",
        "wan1_speedtest_download": 86.0,
        "wan1_speedtest_upload": 23.0,
        "wan1_speedtest_ping": 33.0,
        "wan1_speedtest_lastrun": datetime(2026, 6, 21, 5, 0, 32, tzinfo=UTC),
        "wan2_speedtest_download": 206.0,
        "wan2_speedtest_upload": 28.0,
        "wan2_speedtest_ping": 25.0,
        "wan2_speedtest_lastrun": datetime(2026, 6, 21, 5, 1, 48, tzinfo=UTC),
    },
    "health": {
        "wan_status": "ok",
        "wan_isp_name": "Test ISP",
        "wan_isp_org": "Test ISP Ltd",
        "wan_gw_version": MOCK_SW_VERSION,
        "wan_num_sta": 162,
        "wan_cpu": 37.2,
        "wan_mem": 72.0,
        "wan_uptime": 250701,
        "wan1_availability": 100.0,
        "wan1_latency_avg": 34,
        "wan1_time_period": 9381,
        "wan1_uptime": 9370,
        "wan1_boot_time": None,
        "wan2_availability": 100.0,
        "wan2_latency_avg": 25,
        "wan2_time_period": 11018,
        "wan2_uptime": 11017,
        "wan2_boot_time": None,
        "www_status": "ok",
        "www_latency": 34,
        "www_uptime": 250669,
        "www_drops": 1,
        "www_xput_up": 28.0,
        "www_xput_down": 206.0,
        "www_speedtest_status": "Success",
        "www_speedtest_lastrun": 1782018108,
        "www_speedtest_ping": 25,
        "wlan_status": "ok",
        "wlan_num_user": 101,
        "wlan_num_guest": 0,
        "wlan_num_iot": 2,
        "wlan_num_ap": 8,
        "lan_status": "ok",
        "lan_num_user": 61,
        "lan_num_iot": 0,
        "lan_num_sw": 15,
        "lan_num_adopted": 15,
        "vpn_status": "unknown",
    },
    "devices": {
        "bb:cc:dd:ee:ff:00": {
            "mac": "bb:cc:dd:ee:ff:00",
            "name": "Test AP",
            "model": "UAP-AC-M",
            "type": "ap",
            "cpu": 4.0,
            "ram": 41.1,
            "uptime_secs": 381300,
            "boot_time": None,
            "update_available": False,
            "clients": 5,
            "guests": 0,
            "clients_wifi0": 3,
            "clients_wifi1": 2,
            "score": 98,
            "score_wifi0": 97,
            "score_wifi1": 99,
        },
        "cc:dd:ee:ff:00:11": {
            "mac": "cc:dd:ee:ff:00:11",
            "name": "Test Switch",
            "model": "US8P60",
            "type": "switch",
            "cpu": 59.0,
            "ram": 45.3,
            "uptime_secs": 2160840,
            "boot_time": None,
            "update_available": False,
            "ports_used": 5,
            "ports_user": 5,
            "ports_guest": 0,
        },
    },
    "sw_version": MOCK_SW_VERSION,
}


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="UniFi Network",
        unique_id=MOCK_MAC,
        data=MOCK_ENTRY_DATA,
        options=MOCK_ENTRY_OPTIONS,
    )


@pytest.fixture
def mock_api() -> MagicMock:
    """Return a mock UnifiNetworkAPI."""
    api = MagicMock()
    api.validate_connection = AsyncMock(
        return_value={
            "mac": MOCK_MAC,
            "model": MOCK_MODEL,
            "sw_version": MOCK_SW_VERSION,
        }
    )
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
    api.login = AsyncMock()
    api.logout = AsyncMock()
    return api


@pytest.fixture
def mock_coordinator_data() -> dict[str, Any]:
    """Return a copy of the mock coordinator data."""
    return dict(MOCK_COORDINATOR_DATA)
