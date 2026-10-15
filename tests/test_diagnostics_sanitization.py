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
    coord.uptime_state = {}
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


async def test_ssid_and_tunnel_keys_are_tokenised(hass: Any) -> None:
    """SSIDs and tunnel names used as keys survive nowhere; the states are kept."""
    from custom_components.unifi_network_monitor.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    entry = _make_entry()
    gateway = entry.runtime_data.data["gateway"]
    gateway["wifi_states"] = {"Attic-Mesh": True, "Garden Guest": False}
    gateway["vpn_states"] = {"Branch-Tunnel": True}
    gateway["last_very_high_attrs"]["message"] += " Clients left Attic-Mesh."

    result = await async_get_config_entry_diagnostics(hass, entry)
    text = json.dumps(result)
    for name in ("Attic-Mesh", "Garden Guest", "Branch-Tunnel"):
        assert name.lower() not in text.lower()
    out = result["data"]["gateway"]
    assert out["wifi_states"] == {"wlan-1": True, "wlan-2": False}
    assert out["vpn_states"] == {"vpn-1": True}
    assert "Clients left wlan-1." in out["last_very_high_attrs"]["message"]


def _alert_with(parameters: dict[str, Any], message: str = "") -> MagicMock:
    """Return an entry whose gateway carries one high alert with these blocks."""
    entry = _make_entry()
    entry.runtime_data.data["gateway"]["last_high_attrs"] = {
        "title": "Alert",
        "message": message,
        "parameters": parameters,
    }
    return entry


async def test_nested_client_and_network_blocks_are_redacted(hass: Any) -> None:
    """A ``CLIENTS`` list and a ``NETWORK`` block, as in issue #23, leak nothing."""
    from custom_components.unifi_network_monitor.diagnostics import (
        REDACTED,
        async_get_config_entry_diagnostics,
    )

    entry = _alert_with(
        {
            "CLIENTS": {
                "clients": [
                    {
                        "name": "Kitchen Tablet",
                        "hostname": "kitchen-tab",
                        "ip": "203.0.113.40",
                        "mac": "aa:bb:cc:33:00:01",
                    }
                ]
            },
            "NETWORK": {"name": "Upstairs LAN", "subnet": "198.51.100.0/24"},
            "LEARN_MORE": {"url": "https://help.example.com/alerts"},
        },
        message="Kitchen Tablet on Upstairs LAN is offline.",
    )
    result = await async_get_config_entry_diagnostics(hass, entry)
    text = json.dumps(result)
    for value in ("Kitchen Tablet", "kitchen-tab", "Upstairs LAN", "198.51.100.0"):
        assert value not in text
    params = result["data"]["gateway"]["last_high_attrs"]["parameters"]
    assert params["CLIENTS"]["clients"][0]["hostname"] == REDACTED
    assert params["LEARN_MORE"]["url"] == "https://help.example.com/alerts"


async def test_wlan_and_unseen_blocks_are_redacted_and_devices_tokenised(
    hass: Any,
) -> None:
    """An SSID block and a block on no list are redacted; a device keeps a token."""
    from custom_components.unifi_network_monitor.diagnostics import (
        REDACTED,
        async_get_config_entry_diagnostics,
    )

    entry = _alert_with(
        {
            "WLAN": {"id": "64f0c0ffee", "name": "Attic-Mesh"},
            "SRC_DEVICE": {
                "id": FAKE_AP_MAC,
                "ip": FAKE_LAN_IP,
                "name": FAKE_AP_NAME,
                "model": "U6-LR",
            },
            "NEVER_SEEN_BLOCK": {"label": "Something Personal"},
            "SIGNAL_STRENGTH": {"name": "-67"},
        }
    )
    result = await async_get_config_entry_diagnostics(hass, entry)
    params = result["data"]["gateway"]["last_high_attrs"]["parameters"]
    assert params["WLAN"] == {"id": REDACTED, "name": REDACTED}
    assert params["NEVER_SEEN_BLOCK"] == {"label": REDACTED}
    assert params["SRC_DEVICE"]["id"].startswith("device-")
    assert params["SRC_DEVICE"]["ip"] == REDACTED
    assert params["SRC_DEVICE"]["name"] == params["SRC_DEVICE"]["id"]
    assert params["SRC_DEVICE"]["model"] == "U6-LR"
    assert params["SIGNAL_STRENGTH"] == {"name": "-67"}


def test_substitution_never_enters_the_marker_or_a_longer_word() -> None:
    """A rogue SSID ``RED`` leaves ``**REDACTED**`` and ``Redmond`` alone."""
    from custom_components.unifi_network_monitor.diagnostics import REDACTED, _Scrubber

    scrub = _Scrubber()
    token = scrub.rogue_token("RED")
    assert scrub.text(REDACTED) == REDACTED
    assert scrub.text("Office in Redmond") == "Office in Redmond"
    assert scrub.text(f"{REDACTED} near red.") == f"{REDACTED} near {token}."


def test_literals_with_punctuation_edges_are_replaced() -> None:
    """Names beginning or ending in punctuation match between spaces or punctuation."""
    from custom_components.unifi_network_monitor.diagnostics import _Scrubber

    scrub = _Scrubber()
    first = scrub.named_token("IoT-Guest.5G", "wlan")
    second = scrub.named_token("[Guest] WiFi", "wlan")
    assert scrub.text("Join IoT-Guest.5G, not [Guest] WiFi.") == (
        f"Join {first}, not {second}."
    )
    assert scrub.text("(IoT-Guest.5G)") == f"({first})"


def test_backstop_redacts_public_ipv4_ipv6_and_dash_macs() -> None:
    """Public and IPv6 addresses and dash-form MACs go; versions and ids stay."""
    from custom_components.unifi_network_monitor.diagnostics import REDACTED, _Scrubber

    scrub = _Scrubber()
    out = scrub.text(
        "from 203.0.113.7 and 2001:db8::1 via [2001:db8::1]:8443 and fe80::1%eth8, "
        "client AA-BB-CC-DD-EE-FF on 4.0.21, alert 64f0c0ffee0123456789abcd, "
        "at 12:30:45, resolver 1.1.1.1"
    )
    for address in ("203.0.113.7", "2001:db8::1", "fe80::1", "AA-BB-CC-DD-EE-FF"):
        assert address not in out
    assert f"[{REDACTED}]:8443" in out
    for kept in ("4.0.21", "64f0c0ffee0123456789abcd", "12:30:45", "1.1.1.1"):
        assert kept in out


async def test_a_dash_form_mac_key_is_tokenised(hass: Any) -> None:
    """``_is_mac`` uses the dash-aware pattern, so a dash-form key becomes a token."""
    from custom_components.unifi_network_monitor.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    entry = _make_entry()
    entry.data = {**entry.data, "boot_times": {"AA-BB-CC-00-00-07": {"t": 1}}}
    result = await async_get_config_entry_diagnostics(hass, entry)
    (key,) = result["entry"]["data"]["boot_times"]
    assert key.startswith("device-")


def test_an_empty_name_has_no_token() -> None:
    """A blank SSID or tunnel name is redacted rather than given a token."""
    from custom_components.unifi_network_monitor.diagnostics import REDACTED, _Scrubber

    assert _Scrubber().named_token("  ", "wlan") == REDACTED


def test_an_address_ending_a_sentence_is_redacted() -> None:
    """A trailing full stop does not shield an address; a suffixed version stays."""
    from custom_components.unifi_network_monitor.diagnostics import REDACTED, _Scrubber

    out = _Scrubber().text("Changed to 203.0.113.7. Then 10.0.0.1. Build 4.1.2.3.rc1")
    assert out == f"Changed to {REDACTED}. Then {REDACTED}. Build 4.1.2.3.rc1"


async def test_state_map_keys_keep_their_count(hass: Any) -> None:
    """Names differing only in case, or blank, keep separate keys and states."""
    from custom_components.unifi_network_monitor.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    entry = _make_entry()
    gateway = entry.runtime_data.data["gateway"]
    gateway["wifi_states"] = {"Attic-Mesh": True, "attic-mesh": False, "": True}
    result = await async_get_config_entry_diagnostics(hass, entry)
    states = result["data"]["gateway"]["wifi_states"]
    assert len(states) == 3
    assert sorted(states.values()) == [False, True, True]


async def test_a_name_in_one_alert_leaves_the_other_alerts_prose(hass: Any) -> None:
    """A client named only in the very-high alert's blocks leaves the high alert's text."""
    from custom_components.unifi_network_monitor.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    entry = _make_entry()
    gateway = entry.runtime_data.data["gateway"]
    gateway["last_high_attrs"] = {
        "title": "Alert",
        "message": "Kitchen Tablet disconnected.",
        "parameters": {},
    }
    gateway["last_very_high_attrs"]["parameters"]["CLIENT"] = {"name": "Kitchen Tablet"}
    result = await async_get_config_entry_diagnostics(hass, entry)
    assert "Kitchen Tablet" not in json.dumps(result)
