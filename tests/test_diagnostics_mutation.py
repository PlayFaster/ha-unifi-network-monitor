"""Diagnostics tests that assert the scrubbed value, not merely its absence.

Phase 5 item 30 of the August 2026 plan (§M), written from the mutation run of
2026-08-08. `diagnostics.py` carried 87 surviving mutants — the largest cluster
in the project — and reading them found **one** systematic gap rather than 87
separate ones:

    the existing tests assert that the output carries no secret, and never
    that it carries the right token.

That is the same mistake the projection tests made, in a different costume:
asserting an answer is *plausible* rather than that it is *right*. A scrub that
is skipped, nulled, or written to the wrong key satisfies every absence-only
assertion, because ``None`` contains no MAC either.

Two mutation classes proved the point, and the second corrects a rule this
family had been applying too broadly:

* **A dict-key mutant on a key that is *read*** — ``out.get("XXipXX")`` — makes
  the branch fall through and the **real value survives into the output**. The
  shared guidance retires string/dict-key mutants as snapshot noise. That holds
  for keys being *written*, where the mutation only renames an output field. On
  a scrubber it is exactly inverted: a misread key is a leak.
* **The shape-based backstop hides some of them.** ``_scrub_alert_block``
  finishes by pushing every remaining string through ``text()``, which catches
  MACs and *private* IPs. So a test using ``192.168.x.x`` cannot tell a working
  ``ip`` branch from a dead one. The tests below use a **public** address,
  which only the explicit branch removes.

Every assertion here pins an exact token. Token *identity* is the product —
a diagnostics file is useful because the same device reads the same everywhere —
so asserting "some token" would repeat the original error one level up.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from custom_components.unifi_network_monitor.diagnostics import (
    REDACTED,
    _learn,
    _scrub_alert_block,
    _scrub_device,
    _Scrubber,
    async_get_config_entry_diagnostics,
)

_AP_MAC = "aa:bb:cc:dd:ee:01"
_GW_MAC = "aa:bb:cc:dd:ee:02"
_ROGUE_BSSID = "11:22:33:44:55:66"

# A routable address. The private-range backstop in ``text()`` does not match
# it, so it is removed only if the explicit ``ip`` branch runs.
_PUBLIC_IP = "203.0.113.9"


# ---------------------------------------------------------------------------
# _Scrubber — token identity
# ---------------------------------------------------------------------------


def test_each_new_device_takes_the_next_token_in_sequence() -> None:
    """Tokens must be distinct and consecutive, and stable on reuse.

    A counter that resets, decrements or double-steps still yields a
    MAC-free file, so nothing that checks only for absence can see it. What
    breaks is cross-referencing: with ``self._devices = 1`` every device in
    the capture reads ``device-1`` and two machines become indistinguishable.
    """
    scrub = _Scrubber()

    assert scrub.device_token(_AP_MAC) == "device-1"
    assert scrub.device_token(_GW_MAC) == "device-2"
    assert scrub.device_token("aa:bb:cc:dd:ee:03") == "device-3"
    assert scrub.device_token(_AP_MAC) == "device-1"


def test_each_new_nearby_network_takes_the_next_rogue_token() -> None:
    """The rogue counter is a separate sequence, with the same requirements."""
    scrub = _Scrubber()

    assert scrub.rogue_token("Alpha-Net") == "rogue-1"
    assert scrub.rogue_token("Beta-Net") == "rogue-2"
    assert scrub.rogue_token("Alpha-Net") == "rogue-1"


def test_a_longer_identifier_is_replaced_before_one_nested_inside_it() -> None:
    """Substitution runs longest-first, and the order is load-bearing.

    ``lounge-unifi-ap`` contains ``unifi-ap``. Replace the short one first and
    the long name is destroyed mid-string, leaving ``lounge-device-2`` — a
    corrupted capture that still contains no real identifier, so absence-only
    assertions pass. Sorting by name rather than by length fails the same way
    here, because ``unifi-ap`` sorts after ``lounge-unifi-ap``.
    """
    scrub = _Scrubber()
    outer = scrub.device_token(_AP_MAC)
    inner = scrub.device_token(_GW_MAC)
    scrub.alias("lounge-unifi-ap", outer)
    scrub.alias("unifi-ap", inner)

    assert scrub.text("lounge-unifi-ap rebooted") == f"{outer} rebooted"


def test_an_identifier_of_exactly_the_minimum_length_is_still_scrubbed() -> None:
    """The length floor is inclusive - three characters is short, not too short.

    The companion test proves a two-character name is ignored. Without this one
    the boundary is only ever approached from below, so relaxing ``>=`` to
    ``>`` silently stops scrubbing every three-character device name.
    """
    scrub = _Scrubber()
    token = scrub.device_token(_AP_MAC)
    scrub.alias("nas", token)

    assert scrub.text("nas went offline") == f"{token} went offline"


def test_a_numeric_field_teaches_the_scrubber_nothing() -> None:
    """``_learn`` takes strings only, and the type guard has to be a guard.

    Loosening ``isinstance(value, str) and value`` to ``or`` admits any truthy
    value, whose digits then get substituted out of unrelated free text - the
    scrubber starts corrupting the capture it exists to keep readable.
    """
    scrub = _Scrubber()
    _learn(scrub, {"name": 12345})

    assert scrub.text("uptime 12345 seconds") == "uptime 12345 seconds"


# ---------------------------------------------------------------------------
# _scrub_device / _scrub_alert_block — pseudonymised, not blanked
# ---------------------------------------------------------------------------


def test_a_device_record_is_pseudonymised_rather_than_blanked() -> None:
    """Every identifying field becomes the device's token, and ``None`` is wrong.

    ``out["mac"] = None`` leaks nothing and is still a defect: it discards the
    cross-reference that makes the file worth collecting. ``hostname`` is named
    explicitly because a mutation of that key leaves the real hostname in place.
    """
    scrub = _Scrubber()
    token = scrub.device_token(_AP_MAC)
    scrub.alias("Study-AP", token)

    out = _scrub_device(
        scrub,
        {"mac": _AP_MAC, "name": "Study-AP", "hostname": "Study-AP", "uptime": 42},
    )

    assert out == {
        "mac": token,
        "name": token,
        "hostname": token,
        "uptime": 42,
    }


def test_a_device_alert_block_tokenises_its_id_and_drops_a_public_ip() -> None:
    """The ``DEVICE`` branch must run - the backstop does not cover for it.

    ``text()`` catches MACs and private ranges, so a device block tested with a
    ``192.168.x.x`` address looks scrubbed whether or not the ``ip`` branch
    fires. With a routable address the difference is visible: only the explicit
    branch removes it. The exact-dict comparison also catches a scrub written
    to a renamed key, which would leave the original key untouched beside it.
    """
    scrub = _Scrubber()

    out = _scrub_alert_block(
        scrub,
        "DEVICE",
        {"id": "aa:bb:cc:dd:ee:ff", "ip": _PUBLIC_IP, "port": 5},
    )

    assert out == {"id": "device-1", "ip": REDACTED, "port": 5}


def test_a_named_alert_block_is_blanked_outright() -> None:
    """Blank blocks carry no cross-reference value, so they are erased.

    Erased means ``REDACTED``, not ``None``: a null is indistinguishable from a
    field UniFi never sent, and unmapped keys must survive untouched so the
    block stays diagnosable.
    """
    scrub = _Scrubber()

    out = _scrub_alert_block(
        scrub,
        "AP_NAME",
        {"id": "Study-AP", "name": "Study-AP", "state": "keep"},
    )

    assert out == {"id": REDACTED, "name": REDACTED, "state": "keep"}


# ---------------------------------------------------------------------------
# async_get_config_entry_diagnostics — the whole capture, by exact value
# ---------------------------------------------------------------------------


def _populated_entry() -> MagicMock:
    """Build a config entry and coordinator with every scrubbed path populated."""
    coordinator = MagicMock()
    coordinator.data = {
        "gateway": {
            "mac": _GW_MAC,
            "name": "Home-Console",
            "wan1_interface_name": "ISP Fibre 900",
            "strongest_rogue_ssid": "Beta-Net",
            "rogue_aps_list": [{"essid": "Beta-Net", "detected_by": "Study-AP"}],
        },
        "devices": {
            _AP_MAC: {"mac": _AP_MAC, "name": "Study-AP", "hostname": "Study-AP"},
        },
        "integration_health": {"state": "ok"},
    }
    coordinator.rogue_history = {_ROGUE_BSSID: {"last_label": "Alpha-Net"}}
    coordinator.gateway_mac = _GW_MAC
    coordinator.gateway_model = "UDMPRO"
    coordinator.sw_version = "5.1.19.33549"
    coordinator.consecutive_failures = 0
    coordinator.last_update_success = True
    coordinator.last_update_success_time = None

    entry = MagicMock()
    entry.unique_id = _GW_MAC
    entry.title = "UniFi Network"
    entry.data = {"mac": _GW_MAC, "boot_times": {_AP_MAC: 111, "wan1": 222}}
    entry.options = {
        "host": "192.168.1.1",
        "api_key": "test-api-key-abc123",
        "rogue_ignore_aps": "Study-AP, Lounge-AP",
    }
    entry.runtime_data = coordinator
    return entry


async def test_a_populated_capture_scrubs_to_exact_tokens(hass: Any) -> None:
    """Every identifier resolves to a named token, checked by value.

    The token *numbers* are part of the assertion, not incidental. Nearby
    networks are learned in a defined order - the rogue history before the
    gateway's scan list - and several mutations only reorder that learning.
    Reordering is not cosmetic: a name learned too late is no longer a known
    literal when ``strongest_rogue_ssid`` is scrubbed, and the neighbour's real
    SSID is written to the file. ``Alpha-Net`` and ``Beta-Net`` are distinct so
    the order is observable at all - with one name it is not.
    """
    entry = _populated_entry()

    result = await async_get_config_entry_diagnostics(hass, entry)

    gateway = result["data"]["gateway"]
    assert gateway["name"] == REDACTED
    assert gateway["wan1_interface_name"] == REDACTED
    assert gateway["strongest_rogue_ssid"] == "rogue-2"
    assert gateway["rogue_aps_list"] == [
        {"essid": "rogue-2", "detected_by": "device-1"}
    ]

    assert result["data"]["devices"]["device-1"]["name"] == "device-1"
    assert result["data"]["devices"]["device-1"]["hostname"] == "device-1"

    assert result["entry"]["data"]["boot_times"] == {"device-1": 111, "wan1": 222}
    assert result["entry"]["options"]["rogue_ignore_aps"] == f"{REDACTED} (2 entries)"

    assert result["rogue_history"] == [{"bssid": REDACTED, "last_label": "rogue-1"}]

    assert result["coordinator"]["gateway_mac"] == REDACTED
    assert result["coordinator"]["integration_health"] == {"state": "ok"}
    assert result["coordinator"]["last_update_success"] is True


async def test_the_console_mac_is_labelled_rather_than_numbered(hass: Any) -> None:
    """The gateway gets a named token, so a capture reads ``gateway`` not ``device-1``.

    Reached through the entry rather than the payload, because that is the path
    that survives when the coordinator holds no gateway block. The token is
    asserted through the entry title: ``entry.data["mac"]`` is redacted by key,
    so the label is invisible there and the mutation is invisible with it.
    """
    entry = MagicMock()
    entry.title = f"Console {_GW_MAC}"
    entry.data = {"mac": _GW_MAC, "model": "UDMPRO"}
    entry.options = {}
    coordinator = MagicMock()
    coordinator.data = {}
    coordinator.rogue_history = {}
    coordinator.gateway_mac = _GW_MAC
    coordinator.last_update_success_time = None
    entry.runtime_data = coordinator

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["entry"]["title"] == "Console gateway"


async def test_a_second_mac_on_a_device_record_shares_the_first_token(
    hass: Any,
) -> None:
    """A device known by two MACs must read as one device, not two.

    Checked through free text, which is the only place it shows: the ``mac``
    field is redacted by key, so the alias leaves no trace in the device block
    itself. Without the alias the second address is tokenised separately on its
    next appearance and the capture reports one machine as two.
    """
    second_mac = "99:88:77:66:55:44"
    entry = _populated_entry()
    entry.data["boot_times"] = {}
    entry.runtime_data.data["devices"] = {
        _AP_MAC: {"mac": second_mac, "name": "Study-AP"},
    }
    entry.title = f"Alert from {second_mac}"

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["entry"]["title"] == "Alert from device-1"


async def test_a_non_string_entry_title_passes_through_untouched(hass: Any) -> None:
    """The title guard is a type guard, and the untaken half must stay untaken.

    Loosened to ``or`` it would push a non-string into ``re.sub`` and take
    diagnostics down for a field that carries nothing.
    """
    entry = _populated_entry()
    entry.title = 12345

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["entry"]["title"] == 12345
