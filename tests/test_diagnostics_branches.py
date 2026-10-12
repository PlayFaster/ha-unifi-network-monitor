"""The untaken half of every defensive branch in ``diagnostics.py``.

Phase 2 item 21 of the August 2026 plan (§M). `diagnostics.py` was the module
the plan named to start with, and not because it had the most partials —
`coordinator.py` has more. It is the module whose failure mode is **silent**:
it held ``diagnostics: done`` across two full IQS scans while leaking device
MACs, user-assigned names, internal IPs, the subscriber's ISP and third-party
SSIDs, and every one of those was found by reading real output rather than by
any check. Least-verified plus silent-failing is the worst pair in the
component.

Every branch here is a guard against a payload the controller *can* send: a
missing name, a numeric field where a string was expected, a device record that
is not a dict. The taken half is covered by the existing tests. The untaken
half is what these add, and the standing rule applies — **treat each as a
missing test until proved otherwise**. Not one turned out to be a dead guard,
which is now 13 of 13 on this module against 12-of-12 on WiFi and 11-of-11 on
ZTE.

The assertions are on the scrubbing outcome, never merely on "it did not
raise": a guard that silently stopped scrubbing would satisfy the weaker form.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from custom_components.unifi_network_monitor.diagnostics import (
    REDACTED,
    _is_mac,
    _learn,
    _scrub_alert,
    _scrub_alert_block,
    _scrub_device,
    _scrub_rogue_entry,
    _Scrubber,
    async_get_config_entry_diagnostics,
)

from .conftest import MOCK_MAC

_SECRET_NAME = "Michaels-Study-AP"
_OTHER_SSID = "Neighbour-Wifi-5G"


# ---------------------------------------------------------------------------
# _Scrubber — alias / literal / _remember guards
# ---------------------------------------------------------------------------


def test_alias_ignores_an_empty_identifier() -> None:
    """An absent device name must not alias the empty string to a token.

    If it did, ``text()`` would later substitute on ``""`` — which matches
    everywhere — and the scrubbed output would be shredded.
    """
    scrub = _Scrubber()
    token = scrub.device_token(MOCK_MAC)

    scrub.alias(None, token)
    scrub.alias("", token)
    scrub.alias("   ", token)

    assert scrub.text("nothing identifying here") == "nothing identifying here"


def test_alias_never_repoints_an_existing_token() -> None:
    """First writer wins: a name already mapped keeps its original device."""
    scrub = _Scrubber()
    first = scrub.device_token(MOCK_MAC)
    second = scrub.device_token("11:22:33:44:55:66")

    scrub.alias(_SECRET_NAME, first)
    scrub.alias(_SECRET_NAME, second)

    assert scrub.text(_SECRET_NAME) == first


def test_literal_ignores_an_empty_value() -> None:
    """A blank literal would match every position in every string."""
    scrub = _Scrubber()

    scrub.literal(None)
    scrub.literal("")

    assert scrub.text("plain text") == "plain text"


def test_a_short_literal_is_not_remembered() -> None:
    """A very short identifier is too collision-prone to substitute on.

    Scrubbing every occurrence of a two-character device name would corrupt
    ordinary words throughout the capture, which destroys the diagnostic value
    the file exists for — and does so invisibly.
    """
    scrub = _Scrubber()
    scrub.literal("ap")

    assert scrub.text("the ap is happy") == "the ap is happy"


def test_a_long_enough_literal_is_remembered() -> None:
    """The other side of the same boundary — a real name is scrubbed."""
    scrub = _Scrubber()
    scrub.literal(_SECRET_NAME)

    assert _SECRET_NAME not in scrub.text(f"client roamed to {_SECRET_NAME}")


# ---------------------------------------------------------------------------
# _is_mac / _learn
# ---------------------------------------------------------------------------


def test_is_mac_rejects_a_plain_label() -> None:
    """``boot_times`` mixes MAC keys with labels like ``wan1``.

    Tokenising ``wan1`` would protect nothing and would corrupt every alert
    mentioning WAN1 — so the negative answer matters as much as the positive.
    """
    assert _is_mac(MOCK_MAC) is True
    assert _is_mac("wan1") is False
    assert _is_mac(None) is False


def test_learn_ignores_a_non_mapping() -> None:
    """A degraded endpoint can leave ``None`` where a dict was expected."""
    scrub = _Scrubber()

    _learn(scrub, None)
    _learn(scrub, ["not", "a", "mapping"])

    assert scrub.text("unchanged") == "unchanged"


# ---------------------------------------------------------------------------
# _scrub_device
# ---------------------------------------------------------------------------


def test_scrub_device_leaves_a_record_with_no_mac() -> None:
    """A record with no MAC gets no token rather than a token for ``None``."""
    out = _scrub_device(_Scrubber(), {"model": "U6-Pro"})
    assert "mac" not in out


def test_scrub_device_skips_a_blank_or_non_string_name() -> None:
    """An empty name needs no scrubbing, and a numeric one must not crash."""
    out = _scrub_device(_Scrubber(), {"mac": MOCK_MAC, "name": "", "hostname": 42})
    assert out["name"] == ""
    assert out["hostname"] == 42
    assert out["mac"] != MOCK_MAC


# ---------------------------------------------------------------------------
# _scrub_rogue_entry
# ---------------------------------------------------------------------------


def test_scrub_rogue_entry_leaves_an_entry_with_no_essid() -> None:
    """A cloaked rogue reports no SSID; there is nothing to tokenise."""
    out = _scrub_rogue_entry(_Scrubber(), {"bssid": "aa:bb:cc:00:11:22"})
    assert "essid" not in out


def test_scrub_rogue_entry_skips_a_blank_detected_by() -> None:
    """``detected_by`` is a list of the user's own AP names — blank means none."""
    out = _scrub_rogue_entry(
        _Scrubber(), {"essid": _OTHER_SSID, "detected_by": "", "signal": -70}
    )
    assert out["detected_by"] == ""
    assert out["essid"] != _OTHER_SSID


# ---------------------------------------------------------------------------
# _scrub_alert_block — the backstop matters most here
# ---------------------------------------------------------------------------


def test_scrub_alert_block_scrubs_a_bare_string() -> None:
    """A parameters entry can be a string rather than a block."""
    scrub = _Scrubber()
    scrub.literal(_SECRET_NAME)
    assert _SECRET_NAME not in _scrub_alert_block(scrub, "anything", _SECRET_NAME)


def test_scrub_alert_block_passes_through_a_non_string_scalar() -> None:
    """A numeric parameter is not text and must survive intact."""
    assert _scrub_alert_block(_Scrubber(), "anything", 42) == 42


def test_scrub_alert_block_device_block_without_id_or_ip() -> None:
    """A device block can arrive with neither field populated."""
    out = _scrub_alert_block(_Scrubber(), "ap", {"model": "U6-Pro"})
    assert out == {"model": "U6-Pro"}


def test_scrub_alert_block_blank_block_skips_non_string_fields() -> None:
    """A blanked field that is not a string is left rather than coerced."""
    out = _scrub_alert_block(_Scrubber(), "unmapped_type", {"id": 7})
    assert out["id"] == 7


def test_unmapped_alert_block_still_goes_through_the_backstop() -> None:
    """UniFi adds parameter types; an unmapped one must not leak.

    This is the branch that matters: the block matches neither known category,
    so only the shape-based backstop stands between a new UniFi payload and the
    user's device names appearing in a file they email to a stranger.
    """
    scrub = _Scrubber()
    scrub.literal(_SECRET_NAME)
    out = _scrub_alert_block(scrub, "a_type_we_have_never_seen", {"who": _SECRET_NAME})
    assert _SECRET_NAME not in out["who"]


# ---------------------------------------------------------------------------
# _scrub_alert
# ---------------------------------------------------------------------------


def test_scrub_alert_ignores_non_dict_parameters() -> None:
    """``parameters`` is not always a mapping."""
    out = _scrub_alert(_Scrubber(), {"parameters": "unexpected", "key": "ALERT"})
    assert out["parameters"] == "unexpected"


def test_scrub_alert_skips_a_non_string_text_field() -> None:
    """A text key holding a number must pass through, not raise."""
    out = _scrub_alert(_Scrubber(), {"message": 12345})
    assert out["message"] == 12345


# ---------------------------------------------------------------------------
# The whole capture, on a payload built entirely from the untaken branches
# ---------------------------------------------------------------------------


def _entry(title: str = "UniFi Network") -> MagicMock:
    entry = MagicMock()
    entry.unique_id = MOCK_MAC
    entry.title = title
    entry.data = {"mac": MOCK_MAC, "model": "UDMPRO"}
    entry.options = {"host": "192.168.1.1", "site": "default"}
    return entry


def _coordinator(data: Any, rogue_history: Any = None) -> MagicMock:
    coord = MagicMock()
    coord.data = data
    coord.rogue_history = rogue_history or {}
    coord.consecutive_failures = 0
    coord.last_update_success = True
    coord.last_update_success_time = None
    coord.async_add_listener = MagicMock()
    return coord


async def test_diagnostics_survives_a_wholly_degraded_payload(hass: Any) -> None:
    """Every optional structure absent or the wrong type still yields a capture.

    A diagnostics download is most wanted when the integration is broken, so
    the one payload it must not choke on is the degraded one.
    """
    entry = _entry()
    entry.runtime_data = _coordinator({"gateway": None, "devices": "not a dict"})

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["entry"]["title"] == "UniFi Network"
    assert "coordinator" in result


async def test_diagnostics_keeps_plain_boot_time_labels(hass: Any) -> None:
    """``boot_times`` MAC keys are tokenised; ``wan1`` is left alone."""
    entry = _entry()
    entry.data = {"mac": MOCK_MAC, "boot_times": {MOCK_MAC: {}, "wan1": {}}}
    entry.runtime_data = _coordinator({})

    result = await async_get_config_entry_diagnostics(hass, entry)

    boot = result["entry"]["data"]["boot_times"]
    assert "wan1" in boot
    assert MOCK_MAC not in boot


async def test_diagnostics_leaves_an_empty_ignore_list_alone(hass: Any) -> None:
    """An empty ignore list is summarised as nothing, not as "0 entries"."""
    entry = _entry()
    entry.options = {
        "host": "1.1.1.1",
        "rogue_ignore_ssids": "",
        "rogue_ignore_aps": None,
    }
    entry.runtime_data = _coordinator({})

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["entry"]["options"]["rogue_ignore_ssids"] == ""


async def test_diagnostics_summarises_a_populated_ignore_list(hass: Any) -> None:
    """The other side: a populated list is counted, never quoted."""
    entry = _entry()
    entry.options = {"host": "1.1.1.1", "rogue_ignore_ssids": "Guest_*, Neighbour, "}
    entry.runtime_data = _coordinator({})

    result = await async_get_config_entry_diagnostics(hass, entry)

    summary = result["entry"]["options"]["rogue_ignore_ssids"]
    assert summary == f"{REDACTED} (2 entries)"
    assert "Neighbour" not in summary


async def test_diagnostics_scrubs_a_renamed_entry_title(hass: Any) -> None:
    """A user who renamed the entry after themselves must not be published."""
    entry = _entry(title=_SECRET_NAME)
    entry.runtime_data = _coordinator(
        {"devices": {MOCK_MAC: {"name": _SECRET_NAME, "mac": MOCK_MAC}}}
    )

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert _SECRET_NAME not in result["entry"]["title"]


async def test_diagnostics_scrubs_a_rogue_history_label(hass: Any) -> None:
    """A neighbour's SSID is the more identifying half of the BSSID pair."""
    entry = _entry()
    entry.runtime_data = _coordinator(
        {}, rogue_history={"aa:bb:cc:11:22:33": {"last_label": _OTHER_SSID}}
    )

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert _OTHER_SSID not in str(result["rogue_history"])


async def test_diagnostics_handles_a_history_record_that_is_not_a_dict(
    hass: Any,
) -> None:
    """A corrupted store entry must not take the whole capture down."""
    entry = _entry()
    entry.runtime_data = _coordinator(
        {}, rogue_history={"aa:bb:cc:11:22:33": "corrupt"}
    )

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert len(result["rogue_history"]) == 1


async def test_diagnostics_skips_a_gateway_without_a_name_or_mac(hass: Any) -> None:
    """A gateway dict can be present and still carry neither field."""
    entry = _entry()
    entry.data = {"model": "UDMPRO"}
    entry.runtime_data = _coordinator({"gateway": {"model": "UDMPRO", "name": ""}})

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["data"]["gateway"]["name"] == ""


async def test_diagnostics_ignores_a_non_list_rogue_list(hass: Any) -> None:
    """Schema drift can put a scalar where the rogue list belongs."""
    entry = _entry()
    entry.runtime_data = _coordinator(
        {"gateway": {"mac": MOCK_MAC, "rogue_aps_list": "unexpected"}}
    )

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["data"]["gateway"]["rogue_aps_list"] == "unexpected"


async def test_diagnostics_scrubs_rogue_entries_that_are_not_dicts(hass: Any) -> None:
    """A malformed member of a good list is passed through, not dropped."""
    entry = _entry()
    entry.runtime_data = _coordinator(
        {"gateway": {"mac": MOCK_MAC, "rogue_aps_list": ["not a dict"]}}
    )

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["data"]["gateway"]["rogue_aps_list"] == ["not a dict"]


async def test_diagnostics_handles_a_device_record_that_is_not_a_dict(
    hass: Any,
) -> None:
    """A device whose record is a scalar still gets its MAC tokenised."""
    entry = _entry()
    entry.runtime_data = _coordinator({"devices": {MOCK_MAC: "corrupt"}})

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert MOCK_MAC not in result["data"]["devices"]


def test_device_alert_block_without_id_or_ip() -> None:
    """A DEVICE block can genuinely arrive with neither field populated.

    "ap" is not a device block name — ``_ALERT_DEVICE_BLOCKS`` holds ``DEVICE``
    and ``DEVICE_WITH_PORT`` — so the earlier test exercised the backstop, not
    this branch. Naming the real one is the difference between covering the
    guard and covering something that looks like it.
    """
    out = _scrub_alert_block(_Scrubber(), "DEVICE", {"model": "U6-Pro"})
    assert out == {"model": "U6-Pro"}


def test_device_alert_block_with_an_id_but_no_ip() -> None:
    """The half-populated shape: an id to tokenise and no address to redact."""
    out = _scrub_alert_block(_Scrubber(), "DEVICE", {"id": MOCK_MAC})
    assert out["id"] != MOCK_MAC
    assert "ip" not in out


def test_device_alert_block_redacts_the_ip() -> None:
    """The other half — an internal address is removed, not tokenised."""
    out = _scrub_alert_block(
        _Scrubber(), "DEVICE_WITH_PORT", {"id": MOCK_MAC, "ip": "192.168.1.50"}
    )
    assert out["ip"] == REDACTED


async def test_the_learning_pass_skips_past_unusable_rogue_records(hass: Any) -> None:
    """A cloaked or malformed rogue is stepped over, and the next one still learns.

    Three records, deliberately ordered so the two unusable ones sit *before* a
    real SSID: a guard that stopped the loop instead of continuing it would
    leave the neighbour's network name unlearned and therefore unscrubbed, and
    a single-element list could never show the difference.
    """
    entry = _entry()
    entry.runtime_data = _coordinator(
        {
            "gateway": {
                "mac": MOCK_MAC,
                "rogue_aps_list": [
                    "not a dict",
                    {"bssid": "aa:bb:cc:11:22:33"},
                    {"bssid": "dd:ee:ff:44:55:66", "essid": _OTHER_SSID},
                ],
            }
        }
    )

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert _OTHER_SSID not in str(result["data"]["gateway"]["rogue_aps_list"])


async def test_diagnostics_leaves_an_empty_title_alone(hass: Any) -> None:
    """An entry with no title has nothing to scrub and must not become REDACTED."""
    entry = _entry(title="")
    entry.runtime_data = _coordinator({})

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["entry"]["title"] == ""
