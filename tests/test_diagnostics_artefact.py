"""Assertions on the produced diagnostics download, not on its producers.

A field the download does not copy is absent from the file while every test of
its producer passes (improve_diagnostics_on_bad_payload_data.md §2.4), so each
capture is asserted here in the value ``async_get_config_entry_diagnostics``
returns.
"""

from __future__ import annotations

from copy import deepcopy
import json
from typing import Any
from unittest.mock import MagicMock

import aiohttp

from custom_components.unifi_network_monitor import diagnostics
from custom_components.unifi_network_monitor.api import UnifiNetworkAPI
from custom_components.unifi_network_monitor.diagnostics import (
    DISCOVERY_METADATA_GATED,
    DISCOVERY_METADATA_PUBLISHED,
    REDACTED,
    async_get_config_entry_diagnostics,
)
from custom_components.unifi_network_monitor.gateway import GatewaySelection

from .conftest import MOCK_COORDINATOR_DATA, MOCK_MAC

SWITCH_MAC = "aa:00:00:00:00:21"


def _coordinator(data: dict[str, Any] | None = None) -> MagicMock:
    coord = MagicMock()
    coord.data = deepcopy(MOCK_COORDINATOR_DATA if data is None else data)
    coord.gateway_mac = MOCK_MAC
    coord.gateway_model = "UDMPRO"
    coord.sw_version = "5.1.19.33549"
    coord.consecutive_failures = 0
    coord.last_update_success = True
    coord.last_update_success_time = None
    coord.rogue_history = {}
    coord.api.last_rejection = None
    coord.api.login_metadata = None
    coord.api.routes = {}
    coord.endpoint_outcomes = {}
    coord.gateway_selection = None
    coord.stored_mac_absent = False
    coord.gateway_startup_timestamp = None
    coord.controller_timezone = None
    return coord


def _entry(coord: MagicMock, **options: Any) -> MagicMock:
    entry = MagicMock()
    entry.unique_id = MOCK_MAC
    entry.title = "UniFi Network"
    entry.data = {"mac": MOCK_MAC, "model": "UDMPRO", "sw_version": "5.1.19.33549"}
    entry.options = {
        "host": "192.168.1.1",
        "api_key": "test-api-key-abc123",
        "username": "admin-user",
        "password": "hunter2-secret",
        "site": "default",
        **options,
    }
    entry.runtime_data = coord
    return entry


async def test_rejection_and_login_reach_the_file(hass: Any) -> None:
    """Both captures are published as siblings of ``data``."""
    coord = _coordinator()
    coord.api.last_rejection = {
        "verdict": "http_error",
        "method": "GET",
        "route": "/proxy/network/api/s/<site>/stat/device",
        "status": 401,
        "rc": "error",
        "msg": "api.err.NoSiteContext",
        "keys": ["data", "meta"],
        "records": 0,
        "payload": {"meta": {"rc": "error"}, "data_keys": []},
        "recorded_at": "2026-10-12T15:00:00+00:00",
    }
    coord.api.login_metadata = {
        "outcome": "ok",
        "status": 200,
        "header_names": ["X-CSRF-Token"],
        "cookie_names": ["TOKEN"],
        "token_issued": True,
        "token_source": "cookie",
        "csrf_header": True,
        "recorded_at": "2026-10-12T15:00:00+00:00",
    }
    result = await async_get_config_entry_diagnostics(hass, _entry(coord))
    assert result["last_rejection"]["status"] == 401
    assert result["last_rejection"]["msg"] == "api.err.NoSiteContext"
    assert result["login"]["cookie_names"] == ["TOKEN"]
    assert result["login"]["token_issued"] is True


async def test_no_credential_value_appears_anywhere(hass: Any) -> None:
    """No API key, password, username, token or CSRF value is in the file."""
    api = UnifiNetworkAPI(
        MagicMock(spec=aiohttp.ClientSession),
        "192.168.1.1",
        api_key="test-api-key-abc123",
    )
    api._token = "session-token-value"
    api._csrf = "csrf-value"
    coord = _coordinator()
    coord.api = api
    api.login_metadata = {
        "outcome": "ok",
        "header_names": ["X-CSRF-Token"],
        "cookie_names": ["TOKEN"],
        "token_issued": True,
    }
    text = json.dumps(
        await async_get_config_entry_diagnostics(hass, _entry(coord)), default=str
    )
    for secret in (
        "test-api-key-abc123",
        "hunter2-secret",
        "admin-user",
        "session-token-value",
        "csrf-value",
    ):
        assert secret not in text


async def test_gated_capture_fields_pass_the_scrubber(hass: Any) -> None:
    """A preview naming a known device and a private IP is scrubbed."""
    coord = _coordinator()
    coord.api.last_rejection = {
        "verdict": "unparsable",
        "status": 502,
        "body_preview": "Bad gateway at 192.168.1.1 for Test AP",
        "msg": "aa:bb:cc:dd:ee:ff",
        "keys": ["data", "aa:bb:cc:dd:ee:ff"],
    }
    result = await async_get_config_entry_diagnostics(hass, _entry(coord))
    preview = result["last_rejection"]["body_preview"]
    assert "192.168.1.1" not in preview
    assert "Test AP" not in preview
    assert "aa:bb:cc:dd:ee:ff" not in json.dumps(result["last_rejection"])
    assert result["last_rejection"]["keys"][0] == "data"


async def test_endpoint_outcomes_and_routes_reach_the_file(hass: Any) -> None:
    """Each endpoint's outcome and each route's status and rc are published."""
    coord = _coordinator()
    coord.endpoint_outcomes = {
        "guest list": {"outcome": "answered", "records": 2, "populated": 1},
        "backup list": {"outcome": "failed", "error": "TimeoutError", "strikes": 2},
        "speedtest results": {"outcome": "not_asked", "reason": "disabled"},
    }
    coord.api.routes = {
        "GET /proxy/network/api/s/<site>/stat/device": {
            "method": "GET",
            "route": "/proxy/network/api/s/<site>/stat/device",
            "status": 200,
            "rc": "ok",
            "msg": None,
            "records": 0,
            "populated": 0,
        }
    }
    result = await async_get_config_entry_diagnostics(hass, _entry(coord))
    endpoints = result["endpoints"]
    assert endpoints["outcomes"]["guest list"]["populated"] == 1
    assert endpoints["outcomes"]["backup list"]["outcome"] == "failed"
    assert endpoints["outcomes"]["speedtest results"]["reason"] == "disabled"
    route = endpoints["routes"]["GET /proxy/network/api/s/<site>/stat/device"]
    assert route["status"] == 200
    assert route["rc"] == "ok"


async def test_gateway_context_reaches_the_file_without_identities(hass: Any) -> None:
    """Selection, uptime evidence and timezone are published; no MAC or name."""
    gateway = {"mac": MOCK_MAC, "model": "UDMPRO", "type": "udm", "state": 1}
    switch = {
        "mac": SWITCH_MAC,
        "model": "USM8P210",
        "type": "usw",
        "state": 1,
        "name": "Garage Switch",
    }
    coord = _coordinator()
    coord.gateway_selection = GatewaySelection(None, "ambiguous", (gateway, switch))
    coord.stored_mac_absent = True
    coord.gateway_startup_timestamp = 1789810718
    coord.controller_timezone = "WET"
    entry = _entry(coord)
    cache = {"boot_time": "2026-07-18T16:27:00+00:00", "last_uptime": 1992807}
    entry.data = {**entry.data, "boot_times": {"gateway": cache}}
    result = await async_get_config_entry_diagnostics(hass, entry)
    block = result["gateway"]
    assert block["boot_times_cache"] == cache
    assert block["selection_reason"] == "ambiguous"
    assert block["selected"] is None
    assert [c["model"] for c in block["candidates"]] == ["UDMPRO", "USM8P210"]
    assert block["candidates"][0]["device"] == "gateway"
    assert block["stored_mac_absent"] is True
    assert block["startup_timestamp"] == 1789810718
    assert block["startup_time"] == "2026-09-19T09:38:38+00:00"
    assert block["controller_timezone"] == "WET"
    text = json.dumps(block)
    assert SWITCH_MAC not in text
    assert "Garage Switch" not in text


async def test_selected_gateway_and_missing_startup(hass: Any) -> None:
    """A selected gateway is named by token; a missing startup time is null."""
    gateway = {"mac": MOCK_MAC, "model": "UDMPRO", "type": "udm", "state": 1}
    coord = _coordinator()
    coord.gateway_selection = GatewaySelection(gateway, "wan_signature", (gateway,))
    result = await async_get_config_entry_diagnostics(hass, _entry(coord))
    assert result["gateway"]["selected"] == "gateway"
    assert result["gateway"]["selection_reason"] == "wan_signature"
    assert result["gateway"]["startup_timestamp"] is None
    assert result["gateway"]["startup_time"] is None


async def test_alert_free_text_loses_the_blanked_wan_name(hass: Any) -> None:
    """The WAN and ISP names an alert's parameters carry are scrubbed from its text."""
    data = deepcopy(MOCK_COORDINATOR_DATA)
    data["gateway"]["last_very_high_attrs"] = {
        "message": "Internet connection WAN2 Example ISP Link on port 10 is down.",
        "title": "WAN2 Internet Down",
        "parameters": {
            "WAN_NAME": {"id": "WAN2", "name": "Example ISP Link"},
            "ISP_ASN": {"name": "64512", "not_actionable": True},
            "WAN_ID": {"id": "WAN2", "name": "WAN2"},
        },
    }
    result = await async_get_config_entry_diagnostics(hass, _entry(_coordinator(data)))
    alert = result["data"]["gateway"]["last_very_high_attrs"]
    assert "Example ISP Link" not in alert["message"]
    assert "WAN2" in alert["message"]
    assert alert["parameters"]["ISP_ASN"]["name"] == REDACTED
    assert alert["parameters"]["WAN_ID"]["name"] == "WAN2"


async def test_site_name_is_redacted_unless_default(hass: Any) -> None:
    """A user's own site name is redacted; UniFi's built-in ``default`` is kept."""
    kept = await async_get_config_entry_diagnostics(hass, _entry(_coordinator()))
    assert kept["entry"]["options"]["site"] == "default"
    renamed = await async_get_config_entry_diagnostics(
        hass, _entry(_coordinator(), site="smith-house")
    )
    assert renamed["entry"]["options"]["site"] == REDACTED


async def test_a_failing_section_is_recorded_not_raised(hass: Any) -> None:
    """A section that raises is recorded as a field; the download is still made."""
    coord = _coordinator()
    coord.endpoint_outcomes = {"x": {"outcome": "answered"}}
    original = diagnostics._endpoints_block

    def broken(scrub: Any, coordinator: Any) -> Any:
        raise RuntimeError("boom")

    diagnostics._endpoints_block = broken  # type: ignore[assignment]
    try:
        result = await async_get_config_entry_diagnostics(hass, _entry(coord))
    finally:
        diagnostics._endpoints_block = original  # type: ignore[assignment]
    assert result["endpoints"] == {"section_error": "RuntimeError"}
    assert "data" in result


async def test_every_section_and_rewrite_survives_the_decomposition(
    hass: Any,
) -> None:
    """Each section, and the rewrite each helper owns, is in the download.

    Characterization for the decomposition of the entry point
    (mccabe_complexity_reduction.md): written against the undivided function, it
    fails if a helper is dropped or its section goes missing.
    """
    from .test_diagnostics_sanitization import FAKE_AP_MAC, _make_entry

    result = await async_get_config_entry_diagnostics(hass, _make_entry())
    assert set(result) == {
        "entry",
        "rogue_history",
        "coordinator",
        "data",
        "last_rejection",
        "login",
        "endpoints",
        "gateway",
    }
    assert set(result["entry"]) == {"title", "data", "options"}
    assert set(result["coordinator"]) == {
        "consecutive_failures",
        "last_update_success",
        "last_update_success_time",
        "data_available",
        "gateway_mac",
        "gateway_model",
        "sw_version",
        "integration_health",
    }
    # Pass 1 and the entry rewrite: MAC keys tokenised, labels kept.
    boot_keys = set(result["entry"]["data"]["boot_times"])
    assert "wan1" in boot_keys
    assert FAKE_AP_MAC not in boot_keys
    assert result["entry"]["options"]["rogue_ignore_ssids"] == (
        f"{REDACTED} (2 entries)"
    )
    # Devices, gateway and rogue history rewrites.
    assert all(key.startswith("device-") for key in result["data"]["devices"])
    gateway = result["data"]["gateway"]
    assert gateway["wan1_interface_name"] == REDACTED
    assert gateway["last_very_high_attrs"]["parameters"]["ISP_NAME"]["name"] == (
        REDACTED
    )
    assert [r["last_label"] for r in result["rogue_history"]] == [
        "rogue-1",
        "rogue-2",
        "rogue-3",
    ]
    assert result["coordinator"]["gateway_mac"] == REDACTED


def _producer_fields() -> set[str]:
    """Every field the capture producers emit, collected from real producers."""
    api = UnifiNetworkAPI(MagicMock(spec=aiohttp.ClientSession), "h", api_key="k")
    fields: set[str] = set()
    api._record_verdict("GET", "/p", 404, {"meta": {"rc": "error"}, "data": []}, "x")
    fields |= set(api.last_rejection or {})
    api._record_unparsable("GET", "/p", 502, "text/html", "<html>")
    fields |= set(api.last_rejection or {})
    for record in api.routes.values():
        fields |= set(record)
    api._record_answer("GET", "/q", 200, {"meta": {"rc": "ok"}, "data": [{}]})
    for record in api.routes.values():
        fields |= set(record)
    resp = MagicMock()
    resp.headers = {}
    resp.cookies = {}
    resp.status = 200
    api._record_login_metadata(resp, "ok", None)
    fields |= set(api.login_metadata or {})
    # The coordinator's outcome records, taken from the real recorders.
    from custom_components.unifi_network_monitor.coordinator import (
        UnifiNetworkDataUpdateCoordinator,
    )

    coord = object.__new__(UnifiNetworkDataUpdateCoordinator)
    coord.endpoint_outcomes = {}
    coord._poll_fetch_failures = 0
    coord._record_fetch_answered("a", [{}])
    coord._record_fetch_failed("b", {"failures": 0}, ValueError())
    for record in coord.endpoint_outcomes.values():
        fields |= set(record)
    # The not-asked record is written inline (``_skip_fetch``, v3 unavailable).
    fields |= {"outcome", "reason"}
    return fields


def test_every_discovery_field_is_classified() -> None:
    """Every field the producers emit is either published or gated."""
    assert _producer_fields() == DISCOVERY_METADATA_PUBLISHED | DISCOVERY_METADATA_GATED


def test_discovery_field_sets_do_not_overlap() -> None:
    """No field is both published as is and gated through the scrubber."""
    assert not DISCOVERY_METADATA_PUBLISHED & DISCOVERY_METADATA_GATED


async def test_an_unclassified_field_and_a_malformed_candidate_are_dropped(
    hass: Any,
) -> None:
    """A capture field in neither set is not published; a non-dict candidate is skipped."""
    gateway = {"mac": MOCK_MAC, "model": "UDMPRO", "type": "udm", "state": 1}
    coord = _coordinator()
    coord.api.last_rejection = {"verdict": "http_error", "unclassified": "secret"}
    coord.gateway_selection = GatewaySelection(gateway, "type", (gateway, "junk"))
    result = await async_get_config_entry_diagnostics(hass, _entry(coord))
    assert result["last_rejection"] == {"verdict": "http_error"}
    assert [c["model"] for c in result["gateway"]["candidates"]] == ["UDMPRO"]
