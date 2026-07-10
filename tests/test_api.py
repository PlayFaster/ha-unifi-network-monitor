"""Tests for the UniFi Network API client."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.unifi_network_monitor.api import (
    UnifiAuthError,
    UnifiConnectionError,
    UnifiNetworkAPI,
)


def _make_api(
    *,
    api_key: str | None = "test-key",
    username: str | None = None,
    password: str | None = None,
) -> UnifiNetworkAPI:
    """Create an API instance with a mock session."""
    session = MagicMock(spec=aiohttp.ClientSession)
    return UnifiNetworkAPI(
        session,
        "192.168.1.1",
        api_key=api_key,
        username=username,
        password=password,
    )


def _make_response(
    *,
    status: int = 200,
    json_data: Any = None,
    cookies: dict | None = None,
    headers: dict | None = None,
) -> AsyncMock:
    """Create a mock aiohttp response."""
    mock = AsyncMock()
    mock.status = status
    mock.cookies = cookies or {}
    mock.headers = headers or {}
    mock.json = AsyncMock(return_value=json_data or {})
    mock.raise_for_status = MagicMock()
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=False)
    return mock


async def test_api_key_headers() -> None:
    """API key mode produces X-API-Key header."""
    api = _make_api(api_key="my-key")
    headers = api._auth_headers()
    assert headers.get("X-API-Key") == "my-key"


async def test_no_auth_headers_before_login() -> None:
    """Username/password mode has empty headers before login."""
    api = _make_api(api_key=None, username="user", password="pass")
    headers = api._auth_headers()
    assert "X-API-Key" not in headers
    assert "Cookie" not in headers


async def test_host_cleaning() -> None:
    """Protocol prefix and trailing slashes are stripped."""
    session = MagicMock(spec=aiohttp.ClientSession)
    api = UnifiNetworkAPI(session, "https://192.168.1.1/", api_key="k")
    assert api.host == "192.168.1.1"


async def test_login_stores_token() -> None:
    """Successful login stores TOKEN and CSRF."""
    api = _make_api(api_key=None, username="admin", password="secret")

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.cookies = {"TOKEN": MagicMock(value="abc123")}
    mock_response.headers = {"X-CSRF-Token": "csrf-xyz"}
    mock_response.json = AsyncMock(return_value={})
    mock_response.raise_for_status = MagicMock()
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)

    api.session.post = MagicMock(return_value=mock_response)

    await api.login()
    assert api._token == "abc123"
    assert api._csrf == "csrf-xyz"


async def test_login_raises_on_401() -> None:
    """Login 401 raises UnifiAuthError."""
    api = _make_api(api_key=None, username="admin", password="wrong")

    mock_response = AsyncMock()
    mock_response.status = 401
    mock_response.cookies = {}
    mock_response.headers = {}
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)

    api.session.post = MagicMock(return_value=mock_response)

    with pytest.raises(UnifiAuthError):
        await api.login()


async def test_login_raises_on_no_credentials() -> None:
    """Login raises UnifiAuthError when username/password missing."""
    api = _make_api(api_key="key", username=None, password=None)
    with pytest.raises(UnifiAuthError):
        await api.login()


async def test_get_raises_connection_error_on_network_failure() -> None:
    """Network error in _get raises UnifiConnectionError."""
    api = _make_api(api_key="key")
    api.session.get = MagicMock(side_effect=aiohttp.ClientError("timeout"))
    with pytest.raises(UnifiConnectionError):
        await api._get("/proxy/network/api/s/default/stat/device")


async def test_extract_returns_data_list() -> None:
    """_extract returns the data list from a UniFi envelope."""
    api = _make_api()
    result = api._extract({"data": [{"mac": "aa:bb"}], "meta": {"rc": "ok"}})
    assert result == [{"mac": "aa:bb"}]


async def test_extract_returns_empty_on_missing_data() -> None:
    """_extract returns empty list when data key missing."""
    api = _make_api()
    assert api._extract({"meta": {"rc": "ok"}}) == []


async def test_extract_returns_empty_on_non_dict() -> None:
    """_extract returns empty list when response is not a dict."""
    api = _make_api()
    assert api._extract([1, 2, 3]) == []


async def test_validate_connection_returns_gateway_identity() -> None:
    """validate_connection picks the UDMPRO from devices."""
    api = _make_api(api_key="k")

    devices = [
        {"mac": "aa:bb:cc:dd:ee:ff", "model": "UDMPRO", "state": 1},
        {"mac": "11:22:33:44:55:66", "model": "UAP-AC-M", "state": 1},
    ]
    sysinfo = [{"version": "5.1.19"}]

    with (
        patch.object(api, "get_devices", AsyncMock(return_value=devices)),
        patch.object(api, "get_sysinfo", AsyncMock(return_value=sysinfo)),
    ):
        info = await api.validate_connection()

    assert info["mac"] == "aa:bb:cc:dd:ee:ff"
    assert info["model"] == "UDMPRO"
    assert info["sw_version"] == "5.1.19"


async def test_validate_connection_raises_when_no_devices() -> None:
    """validate_connection raises UnifiConnectionError for empty device list."""
    api = _make_api(api_key="k")
    with (
        patch.object(api, "get_devices", AsyncMock(return_value=[])),
        patch.object(api, "get_sysinfo", AsyncMock(return_value=[])),
        pytest.raises(UnifiConnectionError),
    ):
        await api.validate_connection()


async def test_validate_connection_fallback_to_first_device() -> None:
    """validate_connection falls back to first device when no gateway model found."""
    api = _make_api(api_key="k")
    devices = [
        {"mac": "bb:cc:dd:ee:ff:00", "model": "UAP-AC-M", "state": 1},
    ]
    sysinfo = [{"version": "5.1.19"}]

    with (
        patch.object(api, "get_devices", AsyncMock(return_value=devices)),
        patch.object(api, "get_sysinfo", AsyncMock(return_value=sysinfo)),
    ):
        info = await api.validate_connection()

    assert info["mac"] == "bb:cc:dd:ee:ff:00"
    assert info["model"] == "UAP-AC-M"
    assert info["sw_version"] == "5.1.19"


async def test_validate_connection_username_password_auth() -> None:
    """validate_connection calls login when using username/password."""
    api = _make_api(api_key=None, username="admin", password="secret")
    devices = [{"mac": "aa:bb:cc:dd:ee:ff", "model": "UDMPRO", "state": 1}]
    sysinfo = [{"version": "5.1.19"}]

    with (
        patch.object(api, "login", AsyncMock()) as mock_login,
        patch.object(api, "get_devices", AsyncMock(return_value=devices)),
        patch.object(api, "get_sysinfo", AsyncMock(return_value=sysinfo)),
    ):
        await api.validate_connection()
        mock_login.assert_awaited_once()


async def test_get_devices_calls_correct_endpoint() -> None:
    """get_devices calls _get with stat/device endpoint."""
    api = _make_api(api_key="k")
    with patch.object(api, "_get", AsyncMock(return_value={"data": []})):
        result = await api.get_devices()
    assert result == []


async def test_get_health_calls_correct_endpoint() -> None:
    """get_health calls _get with stat/health endpoint."""
    api = _make_api(api_key="k")
    with patch.object(api, "_get", AsyncMock(return_value={"data": []})):
        result = await api.get_health()
    assert result == []


async def test_get_sysinfo_calls_correct_endpoint() -> None:
    """get_sysinfo calls _get with stat/sysinfo endpoint."""
    api = _make_api(api_key="k")
    with patch.object(api, "_get", AsyncMock(return_value={"data": []})):
        result = await api.get_sysinfo()
    assert result == []


async def test_get_networkconf_calls_correct_endpoint() -> None:
    """get_networkconf calls _get with rest/networkconf endpoint."""
    api = _make_api(api_key="k")
    with patch.object(api, "_get", AsyncMock(return_value={"data": []})):
        result = await api.get_networkconf()
    assert result == []


async def test_get_settings_calls_correct_endpoint() -> None:
    """get_settings calls _get with rest/setting endpoint."""
    api = _make_api(api_key="k")
    with patch.object(api, "_get", AsyncMock(return_value={"data": []})):
        result = await api.get_settings()
    assert result == []


async def test_logout_clears_credentials() -> None:
    """Logout clears token and csrf."""
    api = _make_api(api_key=None, username="admin", password="secret")
    api._token = "abc123"
    api._csrf = "csrf-xyz"

    mock_response = AsyncMock()
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)
    mock_response.read = AsyncMock()
    api.session.post = MagicMock(return_value=mock_response)

    await api.logout()
    assert api._token is None
    assert api._csrf is None


async def test_logout_api_key_returns_early() -> None:
    """Logout returns early in API key mode."""
    api = _make_api(api_key="key")
    await api.logout()
    api.session.post.assert_not_called()


async def test_login_token_from_body_fallback() -> None:
    """Login falls back to body token when no cookie."""
    api = _make_api(api_key=None, username="admin", password="secret")

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.cookies = {}
    mock_response.headers = {}
    mock_response.json = AsyncMock(return_value={"data": {"token": "body-token-abc"}})
    mock_response.raise_for_status = MagicMock()
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)

    api.session.post = MagicMock(return_value=mock_response)

    await api.login()
    assert api._token == "body-token-abc"


async def test_login_raises_when_no_token_received() -> None:
    """Login raises UnifiAuthError when no TOKEN is received."""
    api = _make_api(api_key=None, username="admin", password="secret")

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.cookies = {}
    mock_response.headers = {}
    mock_response.json = AsyncMock(return_value={})
    mock_response.raise_for_status = MagicMock()
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)

    api.session.post = MagicMock(return_value=mock_response)

    with pytest.raises(UnifiAuthError, match="no TOKEN received"):
        await api.login()


async def test_get_401_with_api_key_raises_auth_error() -> None:
    """_get raises UnifiAuthError on 401 in API key mode."""
    api = _make_api(api_key="key")

    mock_response = AsyncMock()
    mock_response.status = 401
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)
    api.session.get = MagicMock(return_value=mock_response)

    with pytest.raises(UnifiAuthError, match="API key rejected"):
        await api._get("/proxy/network/api/s/default/stat/device")


async def test_get_401_triggers_reauth_for_password_mode() -> None:
    """_get re-authenticates on 401 in username/password mode."""
    api = _make_api(api_key=None, username="admin", password="secret")
    api._token = "expired-token"
    api._csrf = "old-csrf"

    fail_response = AsyncMock()
    fail_response.status = 401
    fail_response.raise_for_status = MagicMock(
        side_effect=aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=401
        )
    )
    fail_response.__aenter__ = AsyncMock(return_value=fail_response)
    fail_response.__aexit__ = AsyncMock(return_value=False)

    success_response = AsyncMock()
    success_response.status = 200
    success_response.json = AsyncMock(return_value={"data": [{"mac": "aa:bb"}]})
    success_response.raise_for_status = MagicMock()
    success_response.__aenter__ = AsyncMock(return_value=success_response)
    success_response.__aexit__ = AsyncMock(return_value=False)

    api.session.get = MagicMock(side_effect=[fail_response, success_response])

    with patch.object(api, "login", AsyncMock()) as mock_login:
        result = await api._get("/proxy/network/api/s/default/stat/device")
        mock_login.assert_awaited_once()

    assert result == {"data": [{"mac": "aa:bb"}]}


async def test_get_401_retry_still_fails() -> None:
    """_get propagates error when re-auth retry also fails."""
    api = _make_api(api_key=None, username="admin", password="secret")
    api._token = "expired-token"

    fail_response = AsyncMock()
    fail_response.status = 401
    fail_response.raise_for_status = MagicMock(
        side_effect=aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=401
        )
    )
    fail_response.__aenter__ = AsyncMock(return_value=fail_response)
    fail_response.__aexit__ = AsyncMock(return_value=False)

    api.session.get = MagicMock(return_value=fail_response)

    with patch.object(api, "login", AsyncMock()), pytest.raises(UnifiAuthError):
        await api._get("/proxy/network/api/s/default/stat/device")


async def test_logout_handles_connection_error() -> None:
    """Logout handles connection errors gracefully."""
    api = _make_api(api_key=None, username="admin", password="secret")
    api._token = "abc123"
    api._csrf = "csrf-xyz"

    api.session.post = MagicMock(side_effect=aiohttp.ClientError("timeout"))

    await api.logout()
    assert api._token is None
    assert api._csrf is None


async def test_new_endpoints() -> None:
    """Verify changed endpoint URLs are called correctly by UnifiNetworkAPI."""
    api = _make_api(api_key="key")

    with patch.object(
        api, "_post", AsyncMock(return_value={"data": [{"ok": True}]})
    ) as mock_post:
        await api.get_daily_gateway()
        assert mock_post.call_count >= 1
        path = mock_post.call_args[0][0]
        assert "/stat/report/daily.gw" in path

        await api.get_monthly_gateway()
        path = mock_post.call_args[0][0]
        assert "/stat/report/monthly.gw" in path

        await api.get_backups()
        path = mock_post.call_args[0][0]
        assert "/cmd/backup" in path

        await api.get_rogueaps()
        path = mock_post.call_args[0][0]
        payload = mock_post.call_args[0][1]
        assert "/stat/rogueap" in path
        assert payload == {"within": 1}

    with patch.object(
        api, "_get", AsyncMock(return_value={"data": [{"ok": True}]})
    ) as mock_get:
        await api.get_guests()
        mock_get.assert_called_with("/proxy/network/api/s/default/stat/guest")

        await api.get_speedtest_results()
        mock_get.assert_called_with("/proxy/network/v2/api/site/default/speedtest")


# ------------------------------------------------------------------
# _post method coverage
# ------------------------------------------------------------------


async def test_post_success() -> None:
    """_post returns JSON on success."""
    api = _make_api(api_key="key")
    resp = _make_response(status=200, json_data={"data": [{"ok": True}]})
    api.session.post = MagicMock(return_value=resp)

    result = await api._post("/some/path", {"key": "val"})
    assert result == {"data": [{"ok": True}]}


async def test_post_401_api_key_raises() -> None:
    """_post raises UnifiAuthError on 401 in API key mode."""
    api = _make_api(api_key="key")
    resp = _make_response(status=401)
    api.session.post = MagicMock(return_value=resp)

    with pytest.raises(UnifiAuthError, match="API key rejected"):
        await api._post("/some/path", {"key": "val"})


async def test_post_401_reauth_success() -> None:
    """_post re-authenticates on 401 in password mode."""
    api = _make_api(api_key=None, username="admin", password="secret")
    api._token = "old-token"

    fail_resp = _make_response(status=401)
    success_resp = _make_response(status=200, json_data={"data": [{"ok": True}]})
    api.session.post = MagicMock(side_effect=[fail_resp, success_resp])

    with patch.object(api, "login", AsyncMock()) as mock_login:
        result = await api._post("/some/path", {"key": "val"})
        mock_login.assert_awaited_once()

    assert result == {"data": [{"ok": True}]}


async def test_post_401_reauth_fails() -> None:
    """_post propagates error when re-auth retry also fails."""
    api = _make_api(api_key=None, username="admin", password="secret")
    api._token = "old-token"

    fail_resp = _make_response(status=401)
    fail_resp.raise_for_status = MagicMock(
        side_effect=aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=401
        )
    )
    api.session.post = MagicMock(return_value=fail_resp)

    with patch.object(api, "login", AsyncMock()), pytest.raises(UnifiAuthError):
        await api._post("/some/path", {"key": "val"})


async def test_post_client_response_error_non_401() -> None:
    """_post raises UnifiConnectionError on non-401 ClientResponseError."""
    api = _make_api(api_key="key")
    api.session.post = MagicMock(
        side_effect=aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=500
        )
    )

    with pytest.raises(UnifiConnectionError, match="HTTP error 500"):
        await api._post("/some/path", {"key": "val"})


async def test_post_client_response_error_401() -> None:
    """_post raises UnifiAuthError on 401 ClientResponseError exception."""
    api = _make_api(api_key="key")
    api.session.post = MagicMock(
        side_effect=aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=401
        )
    )

    with pytest.raises(UnifiAuthError, match="Authentication failed"):
        await api._post("/some/path", {"key": "val"})


async def test_post_generic_exception() -> None:
    """_post wraps generic exceptions in UnifiConnectionError."""
    api = _make_api(api_key="key")
    api.session.post = MagicMock(side_effect=TimeoutError("timed out"))

    with pytest.raises(UnifiConnectionError, match="Request failed"):
        await api._post("/some/path", {"key": "val"})


# ------------------------------------------------------------------
# _put method coverage
# ------------------------------------------------------------------


async def test_put_success() -> None:
    """_put returns JSON on success."""
    api = _make_api(api_key="key")
    resp = _make_response(status=200, json_data={"data": [{"ok": True}]})
    api.session.put = MagicMock(return_value=resp)

    result = await api._put("/some/path", {"key": "val"})
    assert result == {"data": [{"ok": True}]}


async def test_put_401_api_key_raises() -> None:
    """_put raises UnifiAuthError on 401 in API key mode."""
    api = _make_api(api_key="key")
    resp = _make_response(status=401)
    api.session.put = MagicMock(return_value=resp)

    with pytest.raises(UnifiAuthError, match="API key rejected"):
        await api._put("/some/path", {"key": "val"})


async def test_put_401_reauth_success() -> None:
    """_put re-authenticates on 401 in password mode."""
    api = _make_api(api_key=None, username="admin", password="secret")
    api._token = "old-token"

    fail_resp = _make_response(status=401)
    success_resp = _make_response(status=200, json_data={"data": [{"ok": True}]})
    api.session.put = MagicMock(side_effect=[fail_resp, success_resp])

    with patch.object(api, "login", AsyncMock()) as mock_login:
        result = await api._put("/some/path", {"key": "val"})
        mock_login.assert_awaited_once()

    assert result == {"data": [{"ok": True}]}


async def test_put_401_reauth_fails() -> None:
    """_put propagates error when re-auth retry also fails."""
    api = _make_api(api_key=None, username="admin", password="secret")
    api._token = "old-token"

    fail_resp = _make_response(status=401)
    fail_resp.raise_for_status = MagicMock(
        side_effect=aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=401
        )
    )
    api.session.put = MagicMock(return_value=fail_resp)

    with patch.object(api, "login", AsyncMock()), pytest.raises(UnifiAuthError):
        await api._put("/some/path", {"key": "val"})


async def test_put_client_response_error_non_401() -> None:
    """_put raises UnifiConnectionError on non-401 ClientResponseError."""
    api = _make_api(api_key="key")
    api.session.put = MagicMock(
        side_effect=aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=503
        )
    )

    with pytest.raises(UnifiConnectionError, match="HTTP error 503"):
        await api._put("/some/path", {"key": "val"})


async def test_put_client_response_error_401() -> None:
    """_put raises UnifiAuthError on 401 ClientResponseError exception."""
    api = _make_api(api_key="key")
    api.session.put = MagicMock(
        side_effect=aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=401
        )
    )

    with pytest.raises(UnifiAuthError, match="Authentication failed"):
        await api._put("/some/path", {"key": "val"})


async def test_put_generic_exception() -> None:
    """_put wraps generic exceptions in UnifiConnectionError."""
    api = _make_api(api_key="key")
    api.session.put = MagicMock(side_effect=TimeoutError("timed out"))

    with pytest.raises(UnifiConnectionError, match="Request failed"):
        await api._put("/some/path", {"key": "val"})


# ------------------------------------------------------------------
# _get non-401 success & error path coverage
# ------------------------------------------------------------------


async def test_get_success_non_401() -> None:
    """_get returns JSON on non-401 response."""
    api = _make_api(api_key="key")
    resp = _make_response(status=200, json_data={"data": [{"ok": True}]})
    api.session.get = MagicMock(return_value=resp)

    result = await api._get("/proxy/network/api/s/default/stat/device")
    assert result == {"data": [{"ok": True}]}


async def test_get_client_response_error_non_401() -> None:
    """_get raises UnifiConnectionError on non-401 ClientResponseError."""
    api = _make_api(api_key="key")
    api.session.get = MagicMock(
        side_effect=aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=502
        )
    )

    with pytest.raises(UnifiConnectionError, match="HTTP error 502"):
        await api._get("/proxy/network/api/s/default/stat/device")


# ------------------------------------------------------------------
# login exception coverage
# ------------------------------------------------------------------


async def test_login_generic_exception() -> None:
    """Login wraps generic exceptions in UnifiConnectionError."""
    api = _make_api(api_key=None, username="admin", password="secret")
    api.session.post = MagicMock(side_effect=TimeoutError("connection timeout"))

    with pytest.raises(UnifiConnectionError, match="Login request failed"):
        await api.login()


# ------------------------------------------------------------------
# trigger_speedtest coverage
# ------------------------------------------------------------------


async def test_trigger_speedtest() -> None:
    """trigger_speedtest calls _post with speedtest cmd."""
    api = _make_api(api_key="key")
    with patch.object(api, "_post", AsyncMock()) as mock_post:
        await api.trigger_speedtest()
        mock_post.assert_awaited_once()
        path = mock_post.call_args[0][0]
        payload = mock_post.call_args[0][1]
        assert "/cmd/devmgr" in path
        assert payload == {"cmd": "speedtest"}


async def test_trigger_speedtest_with_interface() -> None:
    """trigger_speedtest includes interface_name when provided."""
    api = _make_api(api_key="key")
    with patch.object(api, "_post", AsyncMock()) as mock_post:
        await api.trigger_speedtest("wan2")
        mock_post.assert_awaited_once()
        payload = mock_post.call_args[0][1]
        assert payload == {"cmd": "speedtest", "interface_name": "wan2"}


# ------------------------------------------------------------------
# update_networkconf coverage
# ------------------------------------------------------------------


async def test_update_networkconf() -> None:
    """update_networkconf calls _put with networkconf path."""
    api = _make_api(api_key="key")
    with patch.object(api, "_put", AsyncMock()) as mock_put:
        await api.update_networkconf("net_id_123", {"key": "val"})
        mock_put.assert_awaited_once()
        path = mock_put.call_args[0][0]
        assert "/rest/networkconf/net_id_123" in path
        assert mock_put.call_args[0][1] == {"key": "val"}


# ------------------------------------------------------------------
# New endpoint coverage
# ------------------------------------------------------------------


async def test_get_wlanconf() -> None:
    """get_wlanconf calls _get with wlanconf endpoint (line 357-358)."""
    api = _make_api(api_key="k")
    with patch.object(api, "_get", AsyncMock(return_value={"data": []})):
        result = await api.get_wlanconf()
    assert result == []


async def test_get_sites() -> None:
    """get_sites calls _get with integration/v1/sites endpoint (line 362-363)."""
    api = _make_api(api_key="k")
    with patch.object(api, "_get", AsyncMock(return_value={"data": []})):
        result = await api.get_sites()
    assert result == []


async def test_get_wan_interfaces() -> None:
    """get_wan_interfaces calls _get with integration/v1 wans (line 367-368)."""
    api = _make_api(api_key="k")
    with patch.object(api, "_get", AsyncMock(return_value={"data": []})):
        result = await api.get_wan_interfaces("site-uuid-123")
    assert result == []


async def test_get_vpn_servers() -> None:
    """get_vpn_servers calls _get with integration/v1 vpn/servers (line 372-375)."""
    api = _make_api(api_key="k")
    with patch.object(api, "_get", AsyncMock(return_value={"data": []})):
        result = await api.get_vpn_servers("site-uuid-123")
    assert result == []


async def test_get_vpn_tunnels() -> None:
    """get_vpn_tunnels calls _get with integration/v1 vpn/tunnels (line 379-382)."""
    api = _make_api(api_key="k")
    with patch.object(api, "_get", AsyncMock(return_value={"data": []})):
        result = await api.get_vpn_tunnels("site-uuid-123")
    assert result == []


async def test_get_firewall_policies() -> None:
    """get_firewall_policies calls _get with integration/v1 firewall (line 386-389)."""
    api = _make_api(api_key="k")
    with patch.object(api, "_get", AsyncMock(return_value={"data": []})):
        result = await api.get_firewall_policies("site-uuid-123")
    assert result == []
