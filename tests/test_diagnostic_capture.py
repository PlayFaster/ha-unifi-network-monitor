"""Tests for the diagnostics captures on the API client and the coordinator.

The captures follow ``improve_diagnostics_on_bad_payload_data.md`` §2: the most
recent rejected response, the login response's shape, and each route's and
endpoint's latest outcome. Every request here goes through the real
``_get``, ``_post`` and ``_put``; only the HTTP session is faked.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from custom_components.unifi_network_monitor.api import (
    BODY_PREVIEW_LIMIT,
    UnifiAuthError,
    UnifiConnectionError,
    UnifiNetworkAPI,
    route_of,
)

SITE_PATH = "/proxy/network/api/s/office/stat/device"


def _api(**kwargs: Any) -> UnifiNetworkAPI:
    session = MagicMock(spec=aiohttp.ClientSession)
    kwargs.setdefault("api_key", "test-key")
    return UnifiNetworkAPI(session, "192.168.1.1", **kwargs)


def _response(
    status: int,
    *,
    body: Any = None,
    text: str | None = None,
    content_type: str = "application/json",
    headers: dict[str, str] | None = None,
    cookies: dict[str, Any] | None = None,
) -> AsyncMock:
    """A fake aiohttp response whose body reads as JSON and as text."""
    raw = text if text is not None else json.dumps(body)
    resp = AsyncMock()
    resp.status = status
    resp.content_type = content_type
    resp.headers = headers or {}
    resp.cookies = cookies or {}
    resp.text = AsyncMock(return_value=raw)
    if text is not None and body is None:
        resp.json = AsyncMock(
            side_effect=aiohttp.ContentTypeError(MagicMock(), (), message="html")
        )
    else:
        resp.json = AsyncMock(return_value=body)
    if status >= 400:
        resp.raise_for_status = MagicMock(
            side_effect=aiohttp.ClientResponseError(
                request_info=MagicMock(), history=(), status=status
            )
        )
    else:
        resp.raise_for_status = MagicMock()
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=False)
    return resp


def test_route_hides_site_and_site_uuid() -> None:
    """Routes carry placeholders, never the site name or site UUID."""
    assert route_of(SITE_PATH) == "/proxy/network/api/s/<site>/stat/device"
    assert (
        route_of("/proxy/network/v2/api/site/office/speedtest")
        == "/proxy/network/v2/api/site/<site>/speedtest"
    )
    assert (
        route_of("/proxy/network/integration/v1/sites/0123-abcd/wans")
        == "/proxy/network/integration/v1/sites/<site_uuid>/wans"
    )


async def test_404_json_error_is_retained_with_its_reason() -> None:
    """A 404 carrying a JSON error body is retained with status, rc and msg."""
    api = _api()
    api.session.get = MagicMock(
        return_value=_response(
            404, body={"meta": {"rc": "error", "msg": "api.err.NotFound"}, "data": []}
        )
    )
    with pytest.raises(UnifiConnectionError):
        await api._get(SITE_PATH)
    rec = api.last_rejection
    assert rec is not None
    assert rec["verdict"] == "http_error"
    assert rec["status"] == 404
    assert rec["rc"] == "error"
    assert rec["msg"] == "api.err.NotFound"
    assert rec["route"] == "/proxy/network/api/s/<site>/stat/device"
    assert rec["payload"] == {
        "meta": {"rc": "error", "msg": "api.err.NotFound"},
        "data_keys": [],
    }
    route = api.routes["GET /proxy/network/api/s/<site>/stat/device"]
    assert route["status"] == 404
    assert route["rc"] == "error"


async def test_401_with_api_key_is_retained_before_raising() -> None:
    """An API-key 401 is captured at the point of rejection, then raised."""
    api = _api()
    api.session.get = MagicMock(
        return_value=_response(
            401, body={"meta": {"rc": "error", "msg": "api.err.NoSiteContext"}}
        )
    )
    with pytest.raises(UnifiAuthError):
        await api._get(SITE_PATH)
    assert api.last_rejection is not None
    assert api.last_rejection["status"] == 401
    assert api.last_rejection["msg"] == "api.err.NoSiteContext"


async def test_html_404_is_retained_as_a_capped_preview() -> None:
    """A non-JSON error page is retained as an unparsable preview, capped."""
    api = _api()
    page = "<html>" + "x" * (BODY_PREVIEW_LIMIT * 2) + "</html>"
    api.session.post = MagicMock(
        return_value=_response(404, text=page, content_type="text/html")
    )
    with pytest.raises(UnifiConnectionError):
        await api._post("/proxy/network/v2/api/site/office/system-log/all", {})
    rec = api.last_rejection
    assert rec is not None
    assert rec["verdict"] == "unparsable"
    assert rec["status"] == 404
    assert rec["content_type"] == "text/html"
    assert rec["text_length"] == len(page)
    assert len(rec["body_preview"]) == BODY_PREVIEW_LIMIT


async def test_unparsable_200_is_retained() -> None:
    """A 200 whose body fails to parse is retained and raised as a connection error."""
    api = _api()
    api.session.put = MagicMock(
        return_value=_response(200, text="not json", content_type="text/plain")
    )
    with pytest.raises(UnifiConnectionError, match="Unparsable response"):
        await api._put("/proxy/network/api/s/office/rest/networkconf/1", {})
    assert api.last_rejection is not None
    assert api.last_rejection["verdict"] == "unparsable"
    assert api.last_rejection["body_preview"] == "not json"


async def test_200_with_rc_error_is_a_rejection() -> None:
    """A 200 whose envelope says rc=error is retained, though it parsed."""
    api = _api()
    body = {"meta": {"rc": "error", "msg": "api.err.Invalid"}, "data": [{"x": 1}]}
    api.session.get = MagicMock(return_value=_response(200, body=body))
    assert await api._get(SITE_PATH) == body
    assert api.last_rejection is not None
    assert api.last_rejection["verdict"] == "rc_error"
    assert api.last_rejection["payload"]["data_keys"] == ["x"]


async def test_rejected_record_values_are_never_retained() -> None:
    """Only key names of a rejected body's records are kept, never values."""
    api = _api()
    body = {"meta": {"rc": "error"}, "data": [{"name": "Kitchen Switch"}]}
    api.session.get = MagicMock(return_value=_response(400, body=body))
    with pytest.raises(UnifiConnectionError):
        await api._get(SITE_PATH)
    assert "Kitchen Switch" not in json.dumps(api.last_rejection)


async def test_answer_records_counts_per_route() -> None:
    """A good answer records status, rc, records and populated counts."""
    api = _api()
    body = {"meta": {"rc": "ok"}, "data": [{"a": 1}, {}]}
    api.session.get = MagicMock(return_value=_response(200, body=body))
    await api._get(SITE_PATH)
    route = api.routes["GET /proxy/network/api/s/<site>/stat/device"]
    assert route["status"] == 200
    assert route["rc"] == "ok"
    assert route["records"] == 2
    assert route["populated"] == 1
    assert api.last_rejection is None


async def test_unreadable_body_records_no_text() -> None:
    """A body that cannot be read leaves the preview empty, not an error."""
    api = _api()
    resp = _response(500, text="x")
    resp.text = AsyncMock(side_effect=aiohttp.ClientPayloadError("cut"))
    api.session.get = MagicMock(return_value=resp)
    with pytest.raises(UnifiConnectionError):
        await api._get(SITE_PATH)
    assert api.last_rejection is not None
    assert api.last_rejection["body_preview"] is None
    assert api.last_rejection["text_length"] is None


async def test_login_metadata_records_names_never_values() -> None:
    """Login records header and cookie names and flags, never a value."""
    api = _api(api_key=None, username="admin", password="secret-pass")
    cookie = MagicMock()
    cookie.value = "session-token-value"
    api.session.post = MagicMock(
        return_value=_response(
            200,
            body={},
            headers={"X-CSRF-Token": "csrf-value", "Content-Type": "application/json"},
            cookies={"TOKEN": cookie},
        )
    )
    await api.login()
    meta = api.login_metadata
    assert meta is not None
    assert meta["outcome"] == "ok"
    assert meta["token_issued"] is True
    assert meta["token_source"] == "cookie"
    assert meta["csrf_header"] is True
    assert meta["cookie_names"] == ["TOKEN"]
    assert "X-CSRF-Token" in meta["header_names"]
    text = json.dumps(meta)
    for secret in ("session-token-value", "csrf-value", "secret-pass", "admin"):
        assert secret not in text


async def test_login_metadata_records_token_from_body_and_rejection() -> None:
    """A token found in the body, a rejected login and a missing token are recorded."""
    api = _api(api_key=None, username="admin", password="secret-pass")
    api.session.post = MagicMock(
        return_value=_response(200, body={"data": {"token": "body-token"}})
    )
    await api.login()
    assert api.login_metadata is not None
    assert api.login_metadata["token_source"] == "body"

    api.session.post = MagicMock(return_value=_response(401, body={}))
    with pytest.raises(UnifiAuthError):
        await api.login()
    assert api.login_metadata["outcome"] == "rejected"
    assert api.login_metadata["token_issued"] is False

    api._token = None
    api.session.post = MagicMock(return_value=_response(200, body={}))
    with pytest.raises(UnifiAuthError):
        await api.login()
    assert api.login_metadata["outcome"] == "no_token"


async def test_login_metadata_records_a_failed_request() -> None:
    """A login that never got an answer records its error class."""
    api = _api(api_key=None, username="admin", password="secret-pass")
    api.session.post = MagicMock(side_effect=aiohttp.ClientConnectionError())
    with pytest.raises(UnifiConnectionError):
        await api.login()
    assert api.login_metadata is not None
    assert api.login_metadata["outcome"] == "error"
    assert api.login_metadata["error"] == "ClientConnectionError"


async def test_empty_exception_message_names_its_class() -> None:
    """A request failure with an empty message still says what failed."""
    api = _api()
    api.session.get = MagicMock(side_effect=TimeoutError())
    with pytest.raises(UnifiConnectionError, match="TimeoutError"):
        await api._get(SITE_PATH)


# ---------------------------------------------------------------------------
# Coordinator: endpoint outcomes, uptime and timezone context, clear rule
# ---------------------------------------------------------------------------

_FETCHES = (
    "get_devices",
    "get_health",
    "get_sysinfo",
    "get_networkconf",
    "get_settings",
    "get_daily_gateway",
    "get_monthly_gateway",
    "get_rogueaps",
    "get_guests",
    "get_backups",
    "get_speedtest_results",
    "get_wlanconf",
    "get_system_logs",
    "get_sites",
)


def _poll_api(**overrides: Any) -> MagicMock:
    api = MagicMock()
    for name in _FETCHES:
        setattr(api, name, AsyncMock(return_value=overrides.get(name, [])))
    api.last_rejection = {"verdict": "http_error"}
    return api


async def test_endpoint_outcomes_answered_failed_and_not_asked(
    hass: Any, mock_config_entry: Any
) -> None:
    """One poll records answered, failed and not-asked endpoints, with counts."""
    from custom_components.unifi_network_monitor.const import (
        CONF_ENABLE_SPEEDTEST,
        EP_BACKUPS,
        EP_GUESTS,
        EP_SPEEDTEST,
        EP_WAN_IF,
    )
    from custom_components.unifi_network_monitor.coordinator import (
        UnifiNetworkDataUpdateCoordinator,
    )

    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={**mock_config_entry.options, CONF_ENABLE_SPEEDTEST: False},
    )
    api = _poll_api(get_guests=[{"name": "g"}, {}])
    api.get_backups = AsyncMock(side_effect=UnifiConnectionError("down"))
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    await coordinator._async_update_data()

    out = coordinator.endpoint_outcomes
    assert out[EP_GUESTS] == {"outcome": "answered", "records": 2, "populated": 1}
    assert out[EP_BACKUPS]["outcome"] == "failed"
    assert out[EP_BACKUPS]["error"] == "UnifiConnectionError"
    assert out[EP_BACKUPS]["strikes"] == 1
    assert out[EP_SPEEDTEST] == {"outcome": "not_asked", "reason": "disabled"}
    assert out[EP_WAN_IF] == {"outcome": "not_asked", "reason": "v3_unavailable"}
    assert out["devices"]["outcome"] == "answered"
    # A poll on which an endpoint failed keeps the retained rejection.
    assert api.last_rejection == {"verdict": "http_error"}


async def test_clean_poll_clears_the_retained_rejection(
    hass: Any, mock_config_entry: Any
) -> None:
    """A poll on which nothing failed clears the retained rejection."""
    from custom_components.unifi_network_monitor.coordinator import (
        UnifiNetworkDataUpdateCoordinator,
    )

    mock_config_entry.add_to_hass(hass)
    api = _poll_api()
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    coordinator.site_uuid = "failed"
    await coordinator._async_update_data()
    assert api.last_rejection is None


async def test_gateway_startup_timestamp_and_timezone_are_kept(
    hass: Any, mock_config_entry: Any
) -> None:
    """The gateway's startup_timestamp and the controller timezone are kept."""
    from custom_components.unifi_network_monitor.coordinator import (
        UnifiNetworkDataUpdateCoordinator,
    )

    from .conftest import MOCK_MAC

    mock_config_entry.add_to_hass(hass)
    gateway = {
        "mac": MOCK_MAC,
        "model": "UDMPRO",
        "type": "udm",
        "state": 1,
        "startup_timestamp": 1789810718,
        "wan1": {"ifname": "eth8"},
    }
    api = _poll_api(
        get_devices=[gateway],
        get_sysinfo=[{"version": "1", "timezone": "WET"}],
    )
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    coordinator.site_uuid = "failed"
    await coordinator._async_update_data()
    assert coordinator.gateway_startup_timestamp == 1789810718
    assert coordinator.controller_timezone == "WET"

    del gateway["startup_timestamp"]
    api.get_sysinfo = AsyncMock(return_value=[{"version": "1", "timezone": 5}])
    await coordinator._async_update_data()
    assert coordinator.gateway_startup_timestamp is None
    assert coordinator.controller_timezone is None


async def test_a_rejection_from_the_site_lookup_survives_the_poll(
    hass: Any, mock_config_entry: Any
) -> None:
    """A rejection recorded outside the optional fetches is not cleared that poll."""
    from custom_components.unifi_network_monitor.coordinator import (
        UnifiNetworkDataUpdateCoordinator,
    )

    mock_config_entry.add_to_hass(hass)
    api = _poll_api()
    api.last_rejection = None
    api.rejection_serial = 0

    async def refused_sites() -> list[Any]:
        api.last_rejection = {"verdict": "http_error", "status": 404}
        api.rejection_serial += 1
        raise UnifiConnectionError("HTTP error 404")

    api.get_sites = AsyncMock(side_effect=refused_sites)
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    await coordinator._async_update_data()
    assert api.last_rejection == {"verdict": "http_error", "status": 404}

    # The next poll records nothing new and fails nothing, so it clears.
    await coordinator._async_update_data()
    assert api.last_rejection is None


async def test_a_failed_required_endpoint_is_recorded(
    hass: Any, mock_config_entry: Any
) -> None:
    """A failing devices fetch is recorded as failed, not left as last poll's answer."""
    from custom_components.unifi_network_monitor.coordinator import (
        UnifiNetworkDataUpdateCoordinator,
    )

    mock_config_entry.add_to_hass(hass)
    api = _poll_api()
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    coordinator.site_uuid = "failed"
    coordinator.data = await coordinator._async_update_data()
    assert coordinator.endpoint_outcomes["devices"]["outcome"] == "answered"

    api.get_devices = AsyncMock(side_effect=UnifiConnectionError("HTTP error 500"))
    await coordinator._async_update_data()
    assert coordinator.endpoint_outcomes["devices"] == {
        "outcome": "failed",
        "error": "UnifiConnectionError",
        "strikes": 1,
    }


async def test_get_clients_reads_the_station_list() -> None:
    """``get_clients`` reads ``stat/sta`` read-only and returns its records."""
    api = _api()
    api.site = "office"
    get = MagicMock(
        return_value=_response(200, body={"meta": {"rc": "ok"}, "data": [{"x": 1}]})
    )
    api.session.get = get
    assert await api.get_clients() == [{"x": 1}]
    assert get.call_args.args[0].endswith("/proxy/network/api/s/office/stat/sta")
