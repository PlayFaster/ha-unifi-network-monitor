"""Redaction tests for the UniFi Network Monitor diagnostics.

Every identifier used here is invented. These tests assert against the
*rendered* diagnostics output rather than against individual fields, so a
future change that reintroduces a leak fails regardless of where it appears
in the structure.
"""

from __future__ import annotations

import json
import re
from typing import Any
from unittest.mock import MagicMock

# Synthetic identifiers - none of these correspond to real hardware.
FAKE_GATEWAY_MAC = "aa:bb:cc:00:00:01"
FAKE_AP_MAC = "aa:bb:cc:00:00:02"
FAKE_SWITCH_MAC = "aa:bb:cc:00:00:03"
FAKE_ALERT_MAC = "aa:bb:cc:00:00:04"

FAKE_GATEWAY_NAME = "Gateway-Alpha"
FAKE_AP_NAME = "AP-Bravo"
FAKE_SWITCH_NAME = "Switch-Charlie"

FAKE_ISP = "Example Telecom"
FAKE_WAN_NAME = "WAN1_Example_Link"
FAKE_LAN_IP = "192.168.244.17"
FAKE_LAN_IP_2 = "10.244.0.1"
FAKE_WAN_SUBNET = "10.244.119.0/27"

FAKE_ROGUE_LABELS = ("Neighbour-Net", "SomePhone-1234", "Vehicle-Hotspot")
FAKE_WAN1_IFACE = "WAN1_ExampleCo_5G"
FAKE_WAN2_IFACE = "WAN2_OtherCo"

_MAC_RE = re.compile(r"\b[0-9a-f]{2}(?::[0-9a-f]{2}){5}\b", re.IGNORECASE)
_PRIVATE_IP_RE = re.compile(
    r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|192\.168\.\d{1,3}\.\d{1,3}"
    r"|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b"
)


def _coordinator_data() -> dict[str, Any]:
    """Build coordinator data shaped like a real payload, with fake values."""
    return {
        "gateway": {
            "mac": FAKE_GATEWAY_MAC,
            "name": FAKE_GATEWAY_NAME,
            "model": "UDMPRO",
            "cpu": 37.2,
            "uptime_secs": 250701,
            "wan1_interface_name": FAKE_WAN1_IFACE,
            "wan2_interface_name": FAKE_WAN2_IFACE,
            "wan1_ifname": "eth8",
            "wan2_sfp_serial": "X00000000000",
            "wan2_sfp_vendor": "UBNT",
            "wan2_sfp_part": "UF-RJ45-1G",
            "strongest_rogue_ssid": FAKE_ROGUE_LABELS[0],
            "rogue_aps_list": [
                {
                    "essid": FAKE_ROGUE_LABELS[0],
                    "bssid": "aa:bb:cc:22:00:01",
                    "signal": -58,
                    "band": "5",
                    "oui": "ExampleVendor",
                    "detected_by": f"{FAKE_AP_NAME}, {FAKE_SWITCH_NAME}",
                },
                {
                    "essid": FAKE_ROGUE_LABELS[1],
                    "bssid": "aa:bb:cc:22:00:02",
                    "signal": -71,
                    "band": "2.4",
                    "oui": "ExampleVendor",
                    "detected_by": FAKE_AP_NAME,
                },
            ],
            "last_very_high_attrs": {
                "title": "WAN1 Multiple Internet Disconnections",
                "message": (
                    f"Internet connection WAN1 {FAKE_ISP} on port 9 went down "
                    f"multiple times, affecting {FAKE_SWITCH_NAME}."
                ),
                "severity": "VERY_HIGH",
                "parameters": {
                    "DEVICE": {
                        "id": FAKE_ALERT_MAC,
                        "ip": FAKE_LAN_IP,
                        "model": "UDM-Pro",
                        "name": FAKE_GATEWAY_NAME,
                        "version": "5.1.19",
                    },
                    "ISP_NAME": {"name": FAKE_ISP, "not_actionable": True},
                    "WAN_NAME": {"id": "WAN", "name": FAKE_WAN_NAME},
                    "WAN_SUBNET": {"name": FAKE_WAN_SUBNET},
                    "COUNT": {"name": "3", "not_actionable": True},
                    # A block this integration has never seen - the shape-based
                    # backstop has to catch it.
                    "FUTURE_BLOCK": {"name": f"host {FAKE_LAN_IP_2} unreachable"},
                },
            },
        },
        "health": {
            "wan_isp_name": FAKE_ISP,
            "wan_isp_org": FAKE_ISP,
            "wlan_num_user": 103,
            "wan_status": "ok",
        },
        "devices": {
            FAKE_AP_MAC: {
                "mac": FAKE_AP_MAC,
                "name": FAKE_AP_NAME,
                "model": "U6-LR",
                "version": "7.4.1",
                "cpu": 12.0,
            },
            FAKE_SWITCH_MAC: {
                "mac": FAKE_SWITCH_MAC,
                "name": FAKE_SWITCH_NAME,
                "model": "US-8-150W",
                "version": "7.4.1",
                "cpu": 5.0,
            },
        },
        "integration_health": {"problem": False, "auth_mode": "api_key"},
    }


def _make_coordinator() -> MagicMock:
    coord = MagicMock()
    coord.data = _coordinator_data()
    coord.gateway_mac = FAKE_GATEWAY_MAC
    coord.gateway_model = "UDMPRO"
    coord.sw_version = "5.1.19.33549"
    coord.consecutive_failures = 0
    coord.last_update_success = True
    coord.last_update_success_time = None
    coord.rogue_history = {
        f"aa:bb:cc:11:00:0{i}": {
            "first_seen": "2026-07-17T16:27:42+00:00",
            "appearances": 23,
            "last_label": label,
        }
        for i, label in enumerate(FAKE_ROGUE_LABELS)
    }
    return coord


def _make_entry() -> MagicMock:
    entry = MagicMock()
    entry.title = "UniFi Network"
    entry.data = {
        "mac": FAKE_GATEWAY_MAC,
        "model": "UDMPRO",
        "sw_version": "5.1.19.33549",
        "boot_times": {
            FAKE_GATEWAY_MAC: {"boot_time": "2026-07-01T15:13:04+00:00"},
            FAKE_AP_MAC: {"boot_time": "2026-07-17T04:37:53+00:00"},
            FAKE_SWITCH_MAC: {"boot_time": "2026-07-17T04:34:46+00:00"},
            # Not a device - an interface uptime tracker.
            "wan1": {"boot_time": "2026-07-18T16:26:58+00:00"},
        },
    }
    entry.options = {
        "host": "192.168.1.1",
        "api_key": "test-api-key-abc123",
        "site": "default",
        "rogue_ignore_ssids": "Neighbour-Net, SomePhone-1234",
        "rogue_ignore_aps": "",
    }
    entry.runtime_data = _make_coordinator()
    return entry


async def _render(hass: Any) -> str:
    """Return the diagnostics payload serialised to JSON."""
    from custom_components.unifi_network_monitor.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    result = await async_get_config_entry_diagnostics(hass, _make_entry())
    return json.dumps(result)


async def test_no_mac_address_survives(hass: Any) -> None:
    """No MAC-shaped string appears anywhere in the output."""
    rendered = await _render(hass)
    assert _MAC_RE.search(rendered) is None


async def test_no_private_ip_survives(hass: Any) -> None:
    """No RFC1918 address appears anywhere in the output."""
    rendered = await _render(hass)
    assert _PRIVATE_IP_RE.search(rendered) is None


async def test_no_device_name_survives(hass: Any) -> None:
    """User-assigned device names are pseudonymised everywhere they appear."""
    rendered = await _render(hass)
    for name in (FAKE_GATEWAY_NAME, FAKE_AP_NAME, FAKE_SWITCH_NAME):
        assert name not in rendered


async def test_no_rogue_label_survives(hass: Any) -> None:
    """Nearby-network labels - third-party SSIDs - never appear."""
    rendered = await _render(hass)
    for label in FAKE_ROGUE_LABELS:
        assert label not in rendered


async def test_no_isp_or_wan_identity_survives(hass: Any) -> None:
    """ISP name, WAN interface name and WAN subnet are all removed."""
    rendered = await _render(hass)
    assert FAKE_ISP not in rendered
    assert FAKE_WAN_NAME not in rendered
    assert FAKE_WAN_SUBNET not in rendered


async def test_wan_interface_names_are_blanked(hass: Any) -> None:
    """User-assigned WAN interface names routinely name the ISP."""
    from custom_components.unifi_network_monitor.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    result = await async_get_config_entry_diagnostics(hass, _make_entry())
    gateway = result["data"]["gateway"]
    assert gateway["wan1_interface_name"] == "**REDACTED**"
    assert gateway["wan2_interface_name"] == "**REDACTED**"
    # The hardware interface is not identifying and stays.
    assert gateway["wan1_ifname"] == "eth8"


async def test_non_mac_boot_time_keys_are_left_alone(hass: Any) -> None:
    """Interface labels in boot_times are not devices and must not be tokenised.

    Tokenising "wan1" would protect nothing and would corrupt any alert text
    that mentions WAN1.
    """
    from custom_components.unifi_network_monitor.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    result = await async_get_config_entry_diagnostics(hass, _make_entry())
    boot_times = result["entry"]["data"]["boot_times"]
    assert "wan1" in boot_times
    message = result["data"]["gateway"]["last_very_high_attrs"]["message"]
    assert "WAN1" in message


async def test_renamed_entry_title_is_scrubbed(hass: Any) -> None:
    """A user-renamed config entry title must not leak identifiers."""
    from custom_components.unifi_network_monitor.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    entry = _make_entry()
    entry.title = f"UniFi at {FAKE_GATEWAY_NAME}"

    result = await async_get_config_entry_diagnostics(hass, entry)
    assert FAKE_GATEWAY_NAME not in result["entry"]["title"]


async def test_default_entry_title_is_untouched(hass: Any) -> None:
    """The stock title contains nothing identifying and is left alone."""
    from custom_components.unifi_network_monitor.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    result = await async_get_config_entry_diagnostics(hass, _make_entry())
    assert result["entry"]["title"] == "UniFi Network"


async def test_sfp_serial_is_blanked(hass: Any) -> None:
    """SFP serials are unique hardware identifiers; vendor and part survive."""
    from custom_components.unifi_network_monitor.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    result = await async_get_config_entry_diagnostics(hass, _make_entry())
    gateway = result["data"]["gateway"]
    assert gateway["wan2_sfp_serial"] == "**REDACTED**"
    assert gateway["wan2_sfp_vendor"] == "UBNT"
    assert gateway["wan2_sfp_part"] == "UF-RJ45-1G"


async def test_rogue_ap_list_is_scrubbed(hass: Any) -> None:
    """Nearby networks and the APs that spotted them are both pseudonymised."""
    from custom_components.unifi_network_monitor.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    result = await async_get_config_entry_diagnostics(hass, _make_entry())
    rogues = result["data"]["gateway"]["rogue_aps_list"]
    assert rogues
    for record in rogues:
        assert record["essid"].startswith("rogue-")
        assert FAKE_AP_NAME not in record["detected_by"]
        assert FAKE_SWITCH_NAME not in record["detected_by"]
    # Signal and band are the diagnostic substance and must survive.
    assert rogues[0]["signal"] == -58
    assert rogues[0]["band"] == "5"


async def test_strongest_rogue_ssid_matches_list_token(hass: Any) -> None:
    """The headline SSID uses the same token as its entry in the rogue list.

    Membership, not position - ``rogue_aps_list`` is not sorted by signal, so
    asserting against index 0 would encode an invariant that does not hold.
    """
    from custom_components.unifi_network_monitor.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    result = await async_get_config_entry_diagnostics(hass, _make_entry())
    gateway = result["data"]["gateway"]
    essids = [record["essid"] for record in gateway["rogue_aps_list"]]
    assert gateway["strongest_rogue_ssid"] in essids


async def test_sentinel_rogue_ssid_passes_through(hass: Any) -> None:
    """A sentinel such as "None Detected" is not mistaken for an SSID."""
    from custom_components.unifi_network_monitor.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    entry = _make_entry()
    entry.runtime_data.data["gateway"]["strongest_rogue_ssid"] = "None Detected"
    entry.runtime_data.data["gateway"]["rogue_aps_list"] = []

    result = await async_get_config_entry_diagnostics(hass, entry)
    assert result["data"]["gateway"]["strongest_rogue_ssid"] == "None Detected"


async def test_alert_free_text_is_scrubbed(hass: Any) -> None:
    """The ISP and device names embedded in an alert message are removed."""
    from custom_components.unifi_network_monitor.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    result = await async_get_config_entry_diagnostics(hass, _make_entry())
    message = result["data"]["gateway"]["last_very_high_attrs"]["message"]
    assert FAKE_ISP not in message
    assert FAKE_SWITCH_NAME not in message
    # The diagnostic substance of the message survives.
    assert "went down" in message


async def test_unmapped_alert_block_is_caught_by_backstop(hass: Any) -> None:
    """A parameters block we have never seen still has its IP scrubbed."""
    from custom_components.unifi_network_monitor.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    result = await async_get_config_entry_diagnostics(hass, _make_entry())
    params = result["data"]["gateway"]["last_very_high_attrs"]["parameters"]
    assert FAKE_LAN_IP_2 not in params["FUTURE_BLOCK"]["name"]


async def test_device_tokens_are_stable_across_sections(hass: Any) -> None:
    """The same MAC yields the same token in boot_times and devices."""
    from custom_components.unifi_network_monitor.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    result = await async_get_config_entry_diagnostics(hass, _make_entry())
    boot_keys = set(result["entry"]["data"]["boot_times"])
    device_keys = set(result["data"]["devices"])
    # Every device also has a boot time, so its token must appear in both.
    assert device_keys
    assert device_keys.issubset(boot_keys)
    assert "gateway" in boot_keys


async def test_ignore_lists_become_counts(hass: Any) -> None:
    """Configured ignore lists are reduced to a count, never listed."""
    from custom_components.unifi_network_monitor.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    result = await async_get_config_entry_diagnostics(hass, _make_entry())
    ssids = result["entry"]["options"]["rogue_ignore_ssids"]
    assert "2 entries" in ssids
    assert "Neighbour-Net" not in ssids
    # An empty list is left alone rather than reported as "0 entries".
    assert result["entry"]["options"]["rogue_ignore_aps"] == ""


async def test_diagnostic_substance_is_preserved(hass: Any) -> None:
    """Non-identifying data a maintainer needs is not stripped."""
    from custom_components.unifi_network_monitor.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    result = await async_get_config_entry_diagnostics(hass, _make_entry())
    gateway = result["data"]["gateway"]
    assert gateway["model"] == "UDMPRO"
    assert gateway["cpu"] == 37.2
    assert gateway["uptime_secs"] == 250701
    assert result["data"]["health"]["wlan_num_user"] == 103
    assert result["data"]["integration_health"]["auth_mode"] == "api_key"
    device = next(iter(result["data"]["devices"].values()))
    assert device["model"] in {"U6-LR", "US-8-150W"}
    assert device["version"] == "7.4.1"
    history = result["rogue_history"]
    assert history and history[0]["appearances"] == 23


async def test_live_coordinator_data_is_not_mutated(hass: Any) -> None:
    """Generating diagnostics must not alter the coordinator's own data."""
    from custom_components.unifi_network_monitor.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    entry = _make_entry()
    coordinator = entry.runtime_data
    before = json.dumps(coordinator.data, sort_keys=True)

    await async_get_config_entry_diagnostics(hass, entry)

    assert json.dumps(coordinator.data, sort_keys=True) == before
    assert coordinator.data["devices"][FAKE_AP_MAC]["name"] == FAKE_AP_NAME
