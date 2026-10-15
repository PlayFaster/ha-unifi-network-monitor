"""The comparison, block and leak checks of ``scripts/diag_check.py``.

The script runs against hardware in the devcontainer; these tests pin its
decisions on fixed downloads, so a check that silently stops checking fails here.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from scripts import diag_check
from scripts.diag_check import block_problems, leak_hits, structure_drift


def _healthy() -> dict[str, Any]:
    return {
        "data": {"gateway": {"name": "gateway"}},
        "endpoints": {
            "outcomes": {"guest list": {"outcome": "answered"}},
            "routes": {},
        },
        "gateway": {
            "selection_reason": "wan_signature",
            "startup_timestamp": 1,
            "controller_timezone": "WET",
            "published_boot_time": "2026-01-01T00:00:00+00:00",
        },
        "last_rejection": None,
        "login": None,
    }


def test_structure_drift_ignores_list_length_and_volatile_sections() -> None:
    """List lengths and a newly arrived alert are not drift; a new key is."""
    first = _healthy()
    second = _healthy()
    second["data"]["gateway"]["last_high_attrs"] = {"message": "x"}
    second["endpoints"]["outcomes"]["backup list"] = {"outcome": "answered"}
    drift = structure_drift(first, second)
    assert drift == [
        "endpoints.outcomes.backup list",
        "endpoints.outcomes.backup list.outcome",
    ]


def test_structure_drift_collapses_list_positions() -> None:
    """Two lists of different length with the same item shape do not drift."""
    first = {"rows": [{"a": 1}]}
    second = {"rows": [{"a": 1}, {"a": 2}, {"a": 3}]}
    assert structure_drift(first, second) == []


def test_a_healthy_download_has_no_block_problems() -> None:
    """A healthy API-key download passes: null rejection, empty login."""
    assert block_problems(_healthy(), api_key_mode=True) == []


def test_block_problems_are_named() -> None:
    """Each missing or wrong block is reported."""
    bad = _healthy()
    del bad["login"]
    bad["endpoints"]["outcomes"] = {}
    bad["gateway"]["selection_reason"] = None
    del bad["gateway"]["controller_timezone"]
    bad["last_rejection"] = {"verdict": "http_error"}
    problems = block_problems(bad, api_key_mode=True)
    assert "missing block: login" in problems
    assert "endpoints.outcomes is empty" in problems
    assert "gateway.selection_reason is not set" in problems
    assert "gateway.controller_timezone is missing" in problems
    assert "last_rejection is set on a healthy run" in problems


def test_an_outcome_without_a_value_and_an_api_key_login_are_problems() -> None:
    """An outcome record with no outcome, and login data in API-key mode, fail."""
    bad = _healthy()
    bad["endpoints"]["outcomes"]["x"] = {}
    bad["login"] = {"outcome": "ok"}
    problems = block_problems(bad, api_key_mode=True)
    assert "endpoints.outcomes.x has no outcome" in problems
    assert "login is set although API-key mode never logs in" in problems
    assert "login is set although API-key mode never logs in" not in block_problems(
        bad, api_key_mode=False
    )


def test_leak_scan_finds_a_seeded_value_as_a_word() -> None:
    """A listed value found as a whole word is reported with its path."""
    download = _healthy()
    download["data"]["gateway"]["note"] = "seen at Garage Switch today"
    hits = leak_hits(download, {"device_name": {"Garage Switch"}})
    assert hits == {"device_name": ["data.gateway.note"]}


def test_leak_scan_ignores_substrings_short_values_and_routes() -> None:
    """``Port 1`` is not in ``port 10``; short values and route fields are skipped."""
    download = _healthy()
    download["data"]["gateway"]["message"] = "Link on port 10 is down"
    download["endpoints"]["routes"] = {"r": {"route": "/api/s/<site>/stat/guest"}}
    secrets = {"port_name": {"Port 1"}, "network_name": {"Guest"}, "x": {"abc"}}
    assert leak_hits(download, secrets) == {}


def test_sabotage_is_not_applicable_and_never_says_skipped(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--sabotage`` prints a not-applicable line, exits 0, and avoids ``Skipped``.

    The validation summary treats any report containing ``Skipped`` as skipped
    before it looks for a failure, so the word must never appear.
    """
    with patch("sys.argv", ["diag_check.py", "--sabotage"]):
        assert diag_check.main() == 0
    out = capsys.readouterr().out
    assert "not applicable" in out
    assert "Skipped" not in out


async def test_an_unreachable_controller_fails_with_the_summary_message(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A controller that stops answering prints ``router stopped answering``."""
    from custom_components.unifi_network_monitor.api import UnifiConnectionError

    with (
        patch.object(
            diag_check, "_load_options", return_value={"api_key": "k", "host": "h"}
        ),
        patch.object(diag_check, "_TOKEN") as token,
        patch.object(diag_check, "_download", AsyncMock(return_value=_healthy())),
        patch.object(
            diag_check,
            "_controller_values",
            AsyncMock(side_effect=UnifiConnectionError("down")),
        ),
    ):
        token.read_text.return_value = "t"
        assert await diag_check._main() == 1
    out = capsys.readouterr().out
    assert "router stopped answering" in out
    assert "Diagnostics check: FAILED" in out
    assert "Skipped" not in out


async def test_a_clean_run_passes_and_a_leak_fails(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The banner reads PASSED on a clean pair and FAILED on a leak."""
    leaky = _healthy()
    leaky["data"]["gateway"]["note"] = "Garage Switch"
    for download, banner, code in ((_healthy(), "PASSED", 0), (leaky, "FAILED", 1)):
        with (
            patch.object(
                diag_check, "_load_options", return_value={"api_key": "k", "host": "h"}
            ),
            patch.object(diag_check, "_TOKEN") as token,
            patch.object(diag_check, "_download", AsyncMock(return_value=download)),
            patch.object(
                diag_check,
                "_controller_values",
                AsyncMock(return_value={"device_name": {"Garage Switch"}}),
            ),
        ):
            token.read_text.return_value = "t"
            assert await diag_check._main() == code
        assert f"Diagnostics check: {banner}" in capsys.readouterr().out


def test_shape_scan_finds_mac_forms_and_ipv6() -> None:
    """MACs in colon, dash and dotted forms, and an IPv6 address, are reported."""
    from scripts.diag_check import shape_hits

    download = {
        "a": "seen aa:bb:cc:dd:ee:01",
        "b": "seen AA-BB-CC-DD-EE-02",
        "c": "seen aabb.ccdd.ee03",
        "d": "via 2001:db8:85a3::8a2e:370:7334",
        "e": "2026-10-12T21:12:09+00:00 at 6.18.33.2",
    }
    hits = shape_hits(download)
    assert sorted(hits["mac_shape"]) == ["a", "b", "c"]
    assert hits["ipv6_shape"] == ["d"]


def test_leak_scan_matches_a_mac_in_another_separator_form() -> None:
    """A controller MAC published dashed or bare is still found."""
    download = {"x": "AA-BB-CC-DD-EE-FF", "y": "aabbccddeeff"}
    secrets = {"client_mac": {"aa:bb:cc:dd:ee:ff", "aa-bb-cc-dd-ee-ff", "aabbccddeeff"}}
    hits = leak_hits(download, secrets)
    assert sorted(hits["client_mac"]) == ["x", "y"]


def test_leak_scan_finds_an_identifier_used_as_a_key() -> None:
    """An SSID published as a ``wifi_states`` key is found, and never printed."""
    download = _healthy()
    download["data"]["gateway"]["wifi_states"] = {"Attic Mesh": True}
    hits = leak_hits(download, {"ssid": {"Attic Mesh"}})
    assert hits == {"ssid": ["data.gateway.wifi_states.<value> (key)"]}


def test_a_dotted_key_is_masked_whole() -> None:
    """An SSID key containing a dot is masked, not split at the dot."""
    hits = leak_hits({"data": {"IoT-Guest.5G": True}}, {"ssid": {"IoT-Guest.5G"}})
    assert hits == {"ssid": ["data.<value> (key)"]}


def test_own_names_leave_out_docstrings() -> None:
    """A docstring names nothing, so it does not exempt a key from the scan."""
    from scripts.diag_check import _OWN_NAMES

    assert "Diagnostics support for UniFi Network Monitor." not in _OWN_NAMES
    assert "guest list" in _OWN_NAMES


def test_leak_scan_skips_the_integrations_own_names_and_route_keys() -> None:
    """``data``, an endpoint label and a route key are not identifiers."""
    download = _healthy()
    download["endpoints"]["routes"] = {"GET /stat/guest": {"calls": 1}}
    secrets = {"port_name": {"data"}, "network_name": {"guest list", "guest"}}
    assert leak_hits(download, secrets) == {}


def test_shape_scan_masks_an_address_used_as_a_key() -> None:
    """A MAC-shaped key is reported with the address masked in its path."""
    from scripts.diag_check import shape_hits

    hits = shape_hits({"clients": {"aa:bb:cc:dd:ee:01": True}})
    assert hits == {"mac_shape": ["clients.<mac> (key)"]}


async def test_tunnel_names_are_read_as_a_category() -> None:
    """Site-to-site tunnel names join the scanned values as ``vpn_tunnel``."""
    api = AsyncMock()
    api.host = "h"
    for method in (
        "get_devices",
        "get_wlanconf",
        "get_networkconf",
        "get_rogueaps",
        "get_health",
        "get_sysinfo",
        "get_wan_interfaces",
        "get_clients",
    ):
        getattr(api, method).return_value = []
    api.get_sites.return_value = [{"id": "site-1"}]
    api.get_vpn_tunnels.return_value = [{"name": "Branch Link"}]
    values = await diag_check._controller_values(api, "default")
    assert values["vpn_tunnel"] == {"Branch Link"}
    api.get_vpn_tunnels.assert_awaited_once_with("site-1")


def test_banners_are_coloured_unless_no_color(monkeypatch: pytest.MonkeyPatch) -> None:
    """Both scripts colour their banners, and print plain text under NO_COLOR."""
    from scripts import hardware_check

    for module in (diag_check, hardware_check):
        monkeypatch.setattr(module, "_COLOUR", True)
        assert module._green("ok") == "\033[1;32mok\033[0m"
        assert module._red("no") == "\033[1;31mno\033[0m"
        monkeypatch.setattr(module, "_COLOUR", False)
        assert module._green("ok") == "ok"
    monkeypatch.setattr(hardware_check, "_COLOUR", True)
    assert hardware_check._yellow("skip") == "\033[1;33mskip\033[0m"


def test_no_color_turns_the_colour_off_at_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Setting ``NO_COLOR`` before import leaves every banner helper plain."""
    import importlib

    from scripts import hardware_check

    monkeypatch.setenv("NO_COLOR", "1")
    try:
        for module in (diag_check, hardware_check):
            reloaded = importlib.reload(module)
            assert reloaded._COLOUR is False
            assert reloaded._red("no") == "no"
    finally:
        monkeypatch.delenv("NO_COLOR")
        importlib.reload(diag_check)
        importlib.reload(hardware_check)
