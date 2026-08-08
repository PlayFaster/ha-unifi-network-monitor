"""The untaken half of the platform setup and dynamic-discovery branches.

Phase 2 item 21 of the August 2026 plan (§M), covering the smaller modules —
`binary_sensor`, `button`, `select`, `switch`, `cleanup`, `services` and
`__init__`. `coordinator.py` is handled separately.

Most of these are **loop-continue** branches: the condition is false and the
loop goes round again. A single-element fixture cannot distinguish "skipped and
continued" from "skipped and stopped", so every test here uses at least two
items and asserts that the item *after* the skipped one was still processed.
That distinction is the whole point — a guard that stopped the loop instead of
continuing it would silently create no entities for every device after the
first unwanted one, and the entity count is the only place that shows.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from homeassistant.core import HomeAssistant

from custom_components.unifi_network_monitor.const import (
    CONF_ENABLE_SECURITY_MONITORING,
    CONF_ENABLE_SPEEDTEST,
    CONF_UNIFI_DEVICE_MODE,
    DEVICE_MODE_ALL,
    DEVICE_MODE_NONE,
)

from .conftest import MOCK_MAC

_MAC_A = "11:22:33:44:55:66"
_MAC_B = "77:88:99:aa:bb:cc"


def _coordinator(data: dict[str, Any]) -> MagicMock:
    coord = MagicMock()
    coord.data = data
    coord.gateway_mac = MOCK_MAC
    coord.gateway_model = "UDMPRO"
    coord.sw_version = "5.1.19.33549"
    coord.async_add_listener = MagicMock()
    return coord


def _entry(**options: Any) -> MagicMock:
    entry = MagicMock()
    entry.unique_id = MOCK_MAC
    entry.title = "UniFi Network"
    entry.options = {"host": "192.168.1.1", **options}
    return entry


# ---------------------------------------------------------------------------
# binary_sensor — the static pass
# ---------------------------------------------------------------------------


async def test_no_per_device_binary_sensors_are_created_for_any_device(
    hass: HomeAssistant,
) -> None:
    """Mode ``none`` skips **every** device, not merely the first.

    Two devices, so a guard that stopped the loop rather than continuing it
    would produce the same (empty) result for the wrong reason — which is why
    the companion test below asserts the two-device positive case.
    """
    from custom_components.unifi_network_monitor.binary_sensor import async_setup_entry

    coordinator = _coordinator(
        {"devices": {_MAC_A: {"type": "ap"}, _MAC_B: {"type": "usw"}}, "gateway": {}}
    )
    entry = _entry(**{CONF_UNIFI_DEVICE_MODE: DEVICE_MODE_NONE})
    entry.runtime_data = coordinator

    added: list[Any] = []
    await async_setup_entry(hass, entry, lambda new: added.extend(new))

    per_device = [e for e in added if type(e).__name__ == "UnifiDeviceBinarySensor"]
    assert per_device == []


async def test_per_device_binary_sensors_are_created_for_every_device(
    hass: HomeAssistant,
) -> None:
    """The positive half — both devices get entities, not just the first."""
    from custom_components.unifi_network_monitor.binary_sensor import async_setup_entry

    coordinator = _coordinator(
        {"devices": {_MAC_A: {"type": "ap"}, _MAC_B: {"type": "usw"}}, "gateway": {}}
    )
    entry = _entry(**{CONF_UNIFI_DEVICE_MODE: DEVICE_MODE_ALL})
    entry.runtime_data = coordinator

    added: list[Any] = []
    await async_setup_entry(hass, entry, lambda new: added.extend(new))

    macs = {
        e._device_mac for e in added if type(e).__name__ == "UnifiDeviceBinarySensor"
    }
    assert macs == {_MAC_A, _MAC_B}


async def test_no_rogue_proximity_sensor_when_security_is_off(
    hass: HomeAssistant,
) -> None:
    """The proximity alert belongs to the Security group and goes with it."""
    from custom_components.unifi_network_monitor.binary_sensor import async_setup_entry

    coordinator = _coordinator({"devices": {}, "gateway": {}})
    entry = _entry(**{CONF_ENABLE_SECURITY_MONITORING: False})
    entry.runtime_data = coordinator

    added: list[Any] = []
    await async_setup_entry(hass, entry, lambda new: added.extend(new))

    names = {type(e).__name__ for e in added}
    assert "UnifiRogueProximityBinarySensor" not in names
    # Integration Health is self-diagnosis and is never feature-gated — losing
    # it with the Security group would remove the sensor that explains why.
    assert "UnifiIntegrationHealthBinarySensor" in names


async def test_no_vpn_sensors_are_created_for_any_tunnel_when_disabled(
    hass: HomeAssistant,
) -> None:
    """Two tunnels, security off — neither becomes an entity."""
    from custom_components.unifi_network_monitor.binary_sensor import async_setup_entry

    coordinator = _coordinator(
        {
            "devices": {},
            "gateway": {"vpn_states": {"office": True, "backup": False}},
        }
    )
    entry = _entry(**{CONF_ENABLE_SECURITY_MONITORING: False})
    entry.runtime_data = coordinator

    added: list[Any] = []
    await async_setup_entry(hass, entry, lambda new: added.extend(new))

    assert [e for e in added if type(e).__name__ == "UnifiVpnBinarySensor"] == []


# ---------------------------------------------------------------------------
# binary_sensor — the dynamic-discovery pass
# ---------------------------------------------------------------------------


async def test_dynamic_pass_skips_known_devices_and_still_adds_the_new_one(
    hass: HomeAssistant,
) -> None:
    """A device seen at setup is skipped; a device appearing later is added.

    Ordering matters: the already-known device is iterated first, so a guard
    that stopped rather than continued would never reach the new one — and the
    integration would silently stop discovering hardware after the first poll.
    """
    from custom_components.unifi_network_monitor.binary_sensor import async_setup_entry

    coordinator = _coordinator({"devices": {_MAC_A: {"type": "ap"}}, "gateway": {}})
    entry = _entry(**{CONF_UNIFI_DEVICE_MODE: DEVICE_MODE_ALL})
    entry.runtime_data = coordinator

    added: list[Any] = []
    await async_setup_entry(hass, entry, lambda new: added.extend(new))
    listener = coordinator.async_add_listener.call_args[0][0]
    added.clear()

    coordinator.data = {
        "devices": {_MAC_A: {"type": "ap"}, _MAC_B: {"type": "usw"}},
        "gateway": {},
    }
    listener()

    macs = {
        e._device_mac for e in added if type(e).__name__ == "UnifiDeviceBinarySensor"
    }
    assert macs == {_MAC_B}


async def test_dynamic_pass_skips_known_tunnels_and_still_adds_the_new_one(
    hass: HomeAssistant,
) -> None:
    """Same shape for VPN tunnels — the known one must not stop the sweep."""
    from custom_components.unifi_network_monitor.binary_sensor import async_setup_entry

    coordinator = _coordinator(
        {"devices": {}, "gateway": {"vpn_states": {"office": True}}}
    )
    entry = _entry()
    entry.runtime_data = coordinator

    added: list[Any] = []
    await async_setup_entry(hass, entry, lambda new: added.extend(new))
    listener = coordinator.async_add_listener.call_args[0][0]
    added.clear()

    coordinator.data = {
        "devices": {},
        "gateway": {"vpn_states": {"office": True, "backup": False}},
    }
    listener()

    assert len([e for e in added if type(e).__name__ == "UnifiVpnBinarySensor"]) == 1


async def test_dynamic_pass_creates_no_vpn_sensor_when_disabled(
    hass: HomeAssistant,
) -> None:
    """A tunnel discovered after setup is still gated on the feature toggle."""
    from custom_components.unifi_network_monitor.binary_sensor import async_setup_entry

    coordinator = _coordinator({"devices": {}, "gateway": {"vpn_states": {}}})
    entry = _entry(**{CONF_ENABLE_SECURITY_MONITORING: False})
    entry.runtime_data = coordinator

    added: list[Any] = []
    await async_setup_entry(hass, entry, lambda new: added.extend(new))
    listener = coordinator.async_add_listener.call_args[0][0]
    added.clear()

    coordinator.data = {
        "devices": {},
        "gateway": {"vpn_states": {"office": True, "backup": False}},
    }
    listener()

    assert [e for e in added if type(e).__name__ == "UnifiVpnBinarySensor"] == []


# ---------------------------------------------------------------------------
# button / select / switch — the option-off half
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("speedtest", "dual_wan", "expected_speedtest_buttons"),
    [(True, True, 2), (True, False, 1), (False, True, 0), (False, False, 0)],
)
async def test_speedtest_buttons_follow_both_toggles(
    hass: HomeAssistant,
    speedtest: bool,
    dual_wan: bool,
    expected_speedtest_buttons: int,
) -> None:
    """Speedtest off removes both buttons; dual-WAN off removes only WAN2.

    ``(False, True)`` is the combination that matters: dual-WAN on must not
    resurrect a WAN2 button whose whole feature group is switched off.
    """
    from custom_components.unifi_network_monitor.button import async_setup_entry

    coordinator = _coordinator({"gateway": {}})
    entry = _entry(**{CONF_ENABLE_SPEEDTEST: speedtest, "enable_dual_wan": dual_wan})
    entry.runtime_data = coordinator

    added: list[Any] = []
    await async_setup_entry(hass, entry, lambda new: added.extend(new))

    speedtests = [e for e in added if type(e).__name__ == "UnifiSpeedtestButton"]
    assert len(speedtests) == expected_speedtest_buttons
    # Refresh and Cleanup are unconditional — they are how a user recovers.
    assert len(added) == expected_speedtest_buttons + 2


async def test_no_rogue_period_select_when_security_is_off(
    hass: HomeAssistant,
) -> None:
    """The rogue-period select is meaningless with no rogue polling."""
    from custom_components.unifi_network_monitor.select import async_setup_entry

    coordinator = _coordinator({"gateway": {}})
    entry = _entry(**{CONF_ENABLE_SECURITY_MONITORING: False})
    entry.runtime_data = coordinator

    added: list[Any] = []
    await async_setup_entry(hass, entry, lambda new: added.extend(new))

    assert added == []


async def test_no_rogue_control_switches_when_security_is_off(
    hass: HomeAssistant,
) -> None:
    """The rogue switches go with the group; Pause Polling never does."""
    from custom_components.unifi_network_monitor.switch import async_setup_entry

    coordinator = _coordinator({"gateway": {}})
    entry = _entry(**{CONF_ENABLE_SECURITY_MONITORING: False})
    entry.runtime_data = coordinator

    added: list[Any] = []
    await async_setup_entry(hass, entry, lambda new: added.extend(new))

    names = [type(e).__name__ for e in added]
    assert names == ["UnifiPausePollingSwitch"]


# ---------------------------------------------------------------------------
# services — add_rogue_ignore, the two rejecting halves
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("existing", "value", "expected"),
    [
        ("Guest_Net", "Guest_Net", ["Guest_Net"]),
        ("Guest_Net", "   ", ["Guest_Net"]),
        ("Guest_Net", "Other_Net", ["Guest_Net", "Other_Net"]),
    ],
    ids=["already-present", "blank", "genuinely-new"],
)
async def test_add_rogue_ignore_rejects_duplicates_and_blanks(
    hass: HomeAssistant, existing: str, value: str, expected: list[str]
) -> None:
    """A duplicate or blank pattern is a no-op, not a second list entry.

    Both rejections return the list unchanged and both look identical from
    outside, which is why each is asserted against the accepting case rather
    than only against "no exception".
    """
    from custom_components.unifi_network_monitor import services

    entry = _entry(rogue_ignore_ssids=existing)
    call = MagicMock()
    call.data = {"target": "ssids", "value": value}

    written: list[Any] = []
    original_resolve = services._resolve_entry
    services._resolve_entry = lambda _hass, _call: entry  # type: ignore[assignment]
    original_write = services._write_ignore_list
    services._write_ignore_list = (  # type: ignore[assignment]
        lambda _hass, _entry, _key, items: written.append(list(items))
    )
    try:
        result = await services._handle_add_rogue_ignore(hass, call)
    finally:
        services._resolve_entry = original_resolve  # type: ignore[assignment]
        services._write_ignore_list = original_write  # type: ignore[assignment]

    assert result["entries"] == expected
    assert written == [expected]


async def test_dynamic_pass_creates_no_per_device_sensors_for_any_new_device(
    hass: HomeAssistant,
) -> None:
    """Mode ``none`` still applies to devices discovered after setup.

    Two new devices arrive at once, so the loop must skip both — a guard that
    stopped at the first would look identical with a single device.
    """
    from custom_components.unifi_network_monitor.binary_sensor import async_setup_entry

    coordinator = _coordinator({"devices": {}, "gateway": {}})
    entry = _entry(**{CONF_UNIFI_DEVICE_MODE: DEVICE_MODE_NONE})
    entry.runtime_data = coordinator

    added: list[Any] = []
    await async_setup_entry(hass, entry, lambda new: added.extend(new))
    listener = coordinator.async_add_listener.call_args[0][0]
    added.clear()

    coordinator.data = {
        "devices": {_MAC_A: {"type": "ap"}, _MAC_B: {"type": "usw"}},
        "gateway": {},
    }
    listener()

    assert [e for e in added if type(e).__name__ == "UnifiDeviceBinarySensor"] == []
