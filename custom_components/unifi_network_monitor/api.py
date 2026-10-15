"""UniFi Network API client."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import json
import logging
import re
import time as _time
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

_API_TIMEOUT = aiohttp.ClientTimeout(total=15)

# A body kept for the diagnostics download is cut to this many characters, so a
# large HTML error page cannot bloat the file.
BODY_PREVIEW_LIMIT = 500

# The site name and site UUID in a request path identify the install; routes in
# the diagnostics record carry placeholders instead.
_ROUTE_SUBS = (
    (re.compile(r"/api/s/[^/]+/"), "/api/s/<site>/"),
    (re.compile(r"/api/site/[^/]+/"), "/api/site/<site>/"),
    (re.compile(r"/sites/[^/]+/"), "/sites/<site_uuid>/"),
)


def route_of(path: str) -> str:
    """Return a request path with its site name and site UUID replaced."""
    for pattern, placeholder in _ROUTE_SUBS:
        path = pattern.sub(placeholder, path)
    return path


def _now() -> str:
    """Return the current UTC time, to the second, for a capture record."""
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _meta(body: Any) -> tuple[Any, Any]:
    """Return the ``meta.rc`` and ``meta.msg`` of a UniFi response envelope."""
    meta = body.get("meta") if isinstance(body, dict) else None
    if not isinstance(meta, dict):
        return None, None
    return meta.get("rc"), meta.get("msg")


class UnifiError(Exception):
    """Base class for UniFi exceptions."""


class UnifiConnectionError(UnifiError):
    """Raised when the UDM Pro cannot be reached."""


class UnifiAuthError(UnifiError):
    """Raised when authentication credentials are rejected."""


def _raise_auth_error(message: str) -> None:
    """Raise UnifiAuthError helper to satisfy TRY301."""
    raise UnifiAuthError(message)


class UnifiNetworkAPI:
    """Async client for the UniFi Network local API.

    Supports two authentication modes (in preference order):
      1. API key — ``X-API-Key`` header; no session management required.
      2. Username / password — POST to ``/api/auth/login``; manages TOKEN cookie
         and X-CSRF-Token header for subsequent requests.
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        *,
        api_key: str | None = None,
        username: str | None = None,
        password: str | None = None,
        site: str = "default",
    ) -> None:
        """Initialize the API."""
        clean = host
        if "://" in clean:
            clean = clean.split("://", 1)[1]
        self.host = clean.rstrip("/")
        self.session = session
        self.api_key = api_key
        self.username = username
        self.password = password
        self.site = site
        self._token: str | None = None
        self._csrf: str | None = None
        # Serializes logins, as zte_router_5g does: concurrent endpoints on an
        # expired password-mode session log in one at a time.
        self._login_lock = asyncio.Lock()
        # Diagnostics captures (improve_diagnostics_on_bad_payload_data.md §2):
        # the most recent rejected response, the shape of the last login
        # response, and the last outcome of every route. Names and counts only,
        # except the rejected body, which the download scrubs before publishing.
        self.last_rejection: dict[str, Any] | None = None
        # Incremented on every retained rejection, so a poll can tell whether
        # one arrived during it, whichever request recorded it.
        self.rejection_serial = 0
        self.login_metadata: dict[str, Any] | None = None
        self.routes: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _base_url(self) -> str:
        return f"https://{self.host}"

    def _auth_headers(self) -> dict[str, str]:
        """Return auth headers for the current auth mode."""
        if self.api_key:
            return {"X-API-Key": self.api_key}
        headers: dict[str, str] = {}
        if self._token:
            headers["Cookie"] = f"TOKEN={self._token}"
        if self._csrf:
            headers["X-CSRF-Token"] = self._csrf
        return headers

    # ------------------------------------------------------------------
    # Diagnostics captures
    # ------------------------------------------------------------------

    @staticmethod
    async def _body_text(resp: Any) -> str | None:
        """Read a response body as text, or None where it cannot be read."""
        try:
            text = await resp.text()
        except (aiohttp.ClientError, UnicodeDecodeError, ValueError):
            return None
        return text if isinstance(text, str) else None

    def _record_route(self, method: str, path: str, **fields: Any) -> None:
        """Record the latest outcome of one route, names and counts only."""
        route = route_of(path)
        self.routes[f"{method} {route}"] = {
            "method": method,
            "route": route,
            "recorded_at": _now(),
            **fields,
        }

    def _record_answer(self, method: str, path: str, status: Any, body: Any) -> None:
        """Record a parsed answer; a ``meta.rc`` of error is also a rejection."""
        rc, msg = _meta(body)
        data = body.get("data") if isinstance(body, dict) else None
        records = len(data) if isinstance(data, list) else None
        populated = (
            sum(1 for item in data if isinstance(item, dict) and item)
            if isinstance(data, list)
            else None
        )
        self._record_route(
            method,
            path,
            status=status if isinstance(status, int) else None,
            rc=rc,
            msg=msg,
            records=records,
            populated=populated,
        )
        if rc == "error":
            self._record_verdict(method, path, status, body, "rc_error")

    def _record_verdict(
        self, method: str, path: str, status: Any, body: Any, verdict: str
    ) -> None:
        """Retain a rejected, parsed response with the reason it was rejected."""
        rc, msg = _meta(body)
        data = body.get("data") if isinstance(body, dict) else None
        self.rejection_serial += 1
        self.last_rejection = {
            "verdict": verdict,
            "method": method,
            "route": route_of(path),
            "status": status if isinstance(status, int) else None,
            "rc": rc,
            "msg": msg,
            "keys": sorted(body) if isinstance(body, dict) else None,
            "records": len(data) if isinstance(data, list) else None,
            # The envelope's ``meta`` and the key names of its records, never the
            # record values: a rejected record may name a device or client the
            # scrubber has not learned from the poll.
            "payload": {
                "meta": body.get("meta") if isinstance(body, dict) else None,
                "data_keys": sorted(
                    {str(k) for item in data if isinstance(item, dict) for k in item}
                )
                if isinstance(data, list)
                else None,
            },
            "recorded_at": _now(),
        }

    def _record_unparsable(
        self, method: str, path: str, status: Any, content_type: Any, text: str | None
    ) -> None:
        """Retain a response that could not be parsed, as a capped preview."""
        self.rejection_serial += 1
        self.last_rejection = {
            "verdict": "unparsable",
            "method": method,
            "route": route_of(path),
            "status": status if isinstance(status, int) else None,
            "content_type": content_type if isinstance(content_type, str) else None,
            "text_length": len(text) if text is not None else None,
            "body_preview": text[:BODY_PREVIEW_LIMIT] if text is not None else None,
            "recorded_at": _now(),
        }
        self._record_route(
            method,
            path,
            status=self.last_rejection["status"],
            rc=None,
            msg=None,
            records=None,
            populated=None,
        )

    async def _record_failed_status(self, method: str, path: str, resp: Any) -> None:
        """Read and retain the body of a non-2xx response before it is raised."""
        status = resp.status
        text = await self._body_text(resp)
        body: Any = None
        if text is not None:
            try:
                body = json.loads(text)
            except ValueError:
                body = None
        if body is None:
            self._record_unparsable(
                method, path, status, getattr(resp, "content_type", None), text
            )
            return
        self._record_verdict(method, path, status, body, "http_error")
        rc, msg = _meta(body)
        self._record_route(
            method,
            path,
            status=status if isinstance(status, int) else None,
            rc=rc,
            msg=msg,
            records=None,
            populated=None,
        )

    async def _read(self, method: str, path: str, resp: Any) -> Any:
        """Check a response's status, parse it, and record the outcome."""
        status = resp.status
        if isinstance(status, int) and status >= 400:
            await self._record_failed_status(method, path, resp)
        resp.raise_for_status()
        try:
            body = await resp.json()
        except (aiohttp.ContentTypeError, ValueError) as err:
            text = await self._body_text(resp)
            self._record_unparsable(
                method, path, status, getattr(resp, "content_type", None), text
            )
            raise UnifiConnectionError(
                f"Unparsable response ({status}) from {route_of(path)}"
            ) from err
        self._record_answer(method, path, status, body)
        return body

    async def _request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> Any:
        """Perform a request with automatic re-auth on 401, recording the outcome."""
        url = f"{self._base_url()}{path}"
        call = getattr(self.session, method.lower())
        kwargs: dict[str, Any] = {"timeout": _API_TIMEOUT, "ssl": False}
        if payload is not None:
            kwargs["json"] = payload
        try:
            async with call(url, headers=self._auth_headers(), **kwargs) as resp:
                if resp.status == 401:
                    await self._record_failed_status(method, path, resp)
                    if self.api_key:
                        _raise_auth_error("API key rejected (401)")
                    # Re-authenticate once
                    await self.login()
                    async with call(
                        url, headers=self._auth_headers(), **kwargs
                    ) as retry:
                        return await self._read(method, path, retry)
                return await self._read(method, path, resp)
        except (UnifiAuthError, UnifiConnectionError):
            raise
        except aiohttp.ClientResponseError as err:
            if err.status == 401:
                raise UnifiAuthError(f"Authentication failed: {err}") from err
            raise UnifiConnectionError(f"HTTP error {err.status}: {err}") from err
        except Exception as err:
            raise UnifiConnectionError(
                f"Request failed: {str(err) or type(err).__name__}"
            ) from err

    async def _post(self, path: str, payload: dict[str, Any]) -> Any:
        """Perform a POST request with automatic re-auth on 401."""
        return await self._request("POST", path, payload)

    async def _put(self, path: str, payload: dict[str, Any]) -> Any:
        """Perform a PUT request with automatic re-auth on 401."""
        return await self._request("PUT", path, payload)

    async def _get(self, path: str) -> Any:
        """Perform a GET request with automatic re-auth on 401."""
        return await self._request("GET", path)

    def _extract(self, response: Any) -> list[dict[str, Any]]:
        """Extract ``data`` list from a UniFi API response envelope."""
        if isinstance(response, dict):
            return list(response.get("data", []))
        return []

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    async def login(self) -> None:
        """Authenticate with username / password, one login at a time.

        A caller that waited logs in again rather than reusing the session just
        made, as in zte_router_5g; whether the controller refuses or rate-limits
        concurrent logins is unmeasured (docs/DEVELOPMENT.md).
        """
        async with self._login_lock:
            await self._login_unlocked()

    async def _login_unlocked(self) -> None:
        """Authenticate with username / password and store TOKEN + CSRF."""
        if not self.username or not self.password:
            raise UnifiAuthError("Username and password are required for session auth")
        url = f"{self._base_url()}/api/auth/login"
        try:
            async with self.session.post(
                url,
                json={"username": self.username, "password": self.password},
                timeout=_API_TIMEOUT,
                ssl=False,
            ) as resp:
                if resp.status == 401:
                    self._record_login_metadata(resp, "rejected", None)
                    _raise_auth_error("Invalid username or password")
                resp.raise_for_status()
                # Extract TOKEN cookie
                cookie = resp.cookies.get("TOKEN")
                source: str | None = None
                if cookie:
                    self._token = cookie.value
                    source = "cookie"
                else:
                    # Some firmware versions embed token in body
                    body = await resp.json()
                    self._token = (
                        body.get("data", {}).get("token")
                        if isinstance(body, dict)
                        else None
                    )
                    source = "body" if self._token else None
                # Extract CSRF token from response header (UDM Pro 2.x+)
                self._csrf = resp.headers.get("X-CSRF-Token") or resp.headers.get(
                    "x-csrf-token"
                )
                if not self._token:
                    self._record_login_metadata(resp, "no_token", None)
                    _raise_auth_error("Login succeeded but no TOKEN received")
                self._record_login_metadata(resp, "ok", source)
                _LOGGER.debug("UniFi login successful, CSRF=%s", bool(self._csrf))
        except (UnifiAuthError, UnifiConnectionError):
            raise
        except Exception as err:
            self.login_metadata = {
                "outcome": "error",
                "error": type(err).__name__,
                "recorded_at": _now(),
            }
            raise UnifiConnectionError(f"Login request failed: {err}") from err

    def _record_login_metadata(
        self, resp: Any, outcome: str, source: str | None
    ) -> None:
        """Record the login response's shape: names and flags, never a value."""
        headers = getattr(resp, "headers", None)
        cookies = getattr(resp, "cookies", None)
        status = getattr(resp, "status", None)
        self.login_metadata = {
            "outcome": outcome,
            "status": status if isinstance(status, int) else None,
            "header_names": sorted(str(k) for k in headers) if headers else [],
            "cookie_names": sorted(str(k) for k in cookies) if cookies else [],
            "token_issued": self._token is not None and outcome == "ok",
            "token_source": source,
            "csrf_header": bool(self._csrf) if outcome == "ok" else False,
            "recorded_at": _now(),
        }

    async def logout(self) -> None:
        """Log out of the UniFi session (username/password mode only)."""
        if self.api_key or not self._token:
            return
        try:
            url = f"{self._base_url()}/api/auth/logout"
            async with self.session.post(
                url,
                headers=self._auth_headers(),
                timeout=_API_TIMEOUT,
                ssl=False,
            ) as resp:
                await resp.read()
        except (UnifiError, aiohttp.ClientError, OSError) as err:
            _LOGGER.debug("Logout request failed (non-fatal): %s", err)
        finally:
            self._token = None
            self._csrf = None

    # ------------------------------------------------------------------
    # Data endpoints
    # ------------------------------------------------------------------

    async def get_devices(self) -> list[dict[str, Any]]:
        """Fetch all network device stats."""
        resp = await self._get(f"/proxy/network/api/s/{self.site}/stat/device")
        return self._extract(resp)

    async def get_health(self) -> list[dict[str, Any]]:
        """Fetch network subsystem health."""
        resp = await self._get(f"/proxy/network/api/s/{self.site}/stat/health")
        return self._extract(resp)

    async def get_sysinfo(self) -> list[dict[str, Any]]:
        """Fetch system information."""
        resp = await self._get(f"/proxy/network/api/s/{self.site}/stat/sysinfo")
        return self._extract(resp)

    async def get_networkconf(self) -> list[dict[str, Any]]:
        """Fetch network configurations (e.g. WAN load balance settings)."""
        resp = await self._get(f"/proxy/network/api/s/{self.site}/rest/networkconf")
        return self._extract(resp)

    async def get_settings(self) -> list[dict[str, Any]]:
        """Fetch global controller/site settings (e.g. Threat Management)."""
        resp = await self._get(f"/proxy/network/api/s/{self.site}/rest/setting")
        return self._extract(resp)

    async def get_daily_gateway(self) -> list[dict[str, Any]]:
        """Fetch daily gateway usage statistics.

        This is a POST endpoint that requires a time-range and attrs payload.
        Defaults to the past 30 days.
        """
        end_ms = int(_time.time()) * 1000
        start_ms = end_ms - (30 * 24 * 3600 * 1000)
        payload: dict[str, Any] = {
            "attrs": [
                "wan-rx_bytes",
                "wan-tx_bytes",
                "wan2-rx_bytes",
                "wan2-tx_bytes",
                "time",
            ],
            "start": start_ms,
            "end": end_ms,
        }
        path = f"/proxy/network/api/s/{self.site}/stat/report/daily.gw"
        resp = await self._post(path, payload)
        return self._extract(resp)

    async def get_monthly_gateway(self) -> list[dict[str, Any]]:
        """Fetch monthly gateway usage statistics.

        This is a POST endpoint that requires a time-range and attrs payload.
        Defaults to the past 13 months.
        """
        end_ms = int(_time.time()) * 1000
        start_ms = end_ms - (13 * 30 * 24 * 3600 * 1000)
        payload: dict[str, Any] = {
            "attrs": [
                "wan-rx_bytes",
                "wan-tx_bytes",
                "wan2-rx_bytes",
                "wan2-tx_bytes",
                "time",
            ],
            "start": start_ms,
            "end": end_ms,
        }
        path = f"/proxy/network/api/s/{self.site}/stat/report/monthly.gw"
        resp = await self._post(path, payload)
        return self._extract(resp)

    async def get_rogueaps(self, within_hours: int = 1) -> list[dict[str, Any]]:
        """Fetch rogue access points statistics within a specific number of hours."""
        payload = {"within": within_hours}
        resp = await self._post(
            f"/proxy/network/api/s/{self.site}/stat/rogueap", payload
        )
        return self._extract(resp)

    async def get_guests(self) -> list[dict[str, Any]]:
        """Fetch active guest clients statistics."""
        resp = await self._get(f"/proxy/network/api/s/{self.site}/stat/guest")
        return self._extract(resp)

    async def get_backups(self) -> list[dict[str, Any]]:
        """Fetch the list of available system backups.

        Uses the cmd/backup endpoint with the list-backups command.
        """
        payload: dict[str, Any] = {"cmd": "list-backups"}
        resp = await self._post(f"/proxy/network/api/s/{self.site}/cmd/backup", payload)
        return self._extract(resp)

    async def get_speedtest_results(self) -> list[dict[str, Any]]:
        """Fetch historical speedtest results from the v2 API."""
        path = f"/proxy/network/v2/api/site/{self.site}/speedtest"
        resp = await self._get(path)
        return self._extract(resp)

    async def get_clients(self) -> list[dict[str, Any]]:
        """Fetch connected clients (read-only).

        Not polled by the integration; ``scripts/diag_check.py`` reads it to scan
        the diagnostics download for client names, hostnames, MACs and IPs.
        """
        resp = await self._get(f"/proxy/network/api/s/{self.site}/stat/sta")
        return self._extract(resp)

    async def get_wlanconf(self) -> list[dict[str, Any]]:
        """Fetch WLAN configuration details (SSID states)."""
        resp = await self._get(f"/proxy/network/api/s/{self.site}/rest/wlanconf")
        return self._extract(resp)

    async def get_system_logs(
        self,
        severities: list[str] | None = None,
        page_number: int = 0,
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        """Fetch system logs / alerts from the v2 API (newest first)."""
        payload: dict[str, Any] = {
            "pageNumber": page_number,
            "pageSize": page_size,
        }
        if severities:
            payload["severities"] = severities
        path = f"/proxy/network/v2/api/site/{self.site}/system-log/all"
        resp = await self._post(path, payload)
        return self._extract(resp)

    async def get_sites(self) -> list[dict[str, Any]]:
        """Fetch all sites managed by the controller (official integration API)."""
        resp = await self._get("/proxy/network/integration/v1/sites")
        return self._extract(resp)

    async def get_wan_interfaces(self, site_uuid: str) -> list[dict[str, Any]]:
        """Fetch WAN interface definitions for a site (official integration API)."""
        resp = await self._get(f"/proxy/network/integration/v1/sites/{site_uuid}/wans")
        return self._extract(resp)

    async def get_vpn_servers(self, site_uuid: str) -> list[dict[str, Any]]:
        """Fetch VPN servers configured on a site (official integration API)."""
        resp = await self._get(
            f"/proxy/network/integration/v1/sites/{site_uuid}/vpn/servers"
        )
        return self._extract(resp)

    async def get_vpn_tunnels(self, site_uuid: str) -> list[dict[str, Any]]:
        """Fetch site-to-site VPN tunnels on a site (official integration API)."""
        resp = await self._get(
            f"/proxy/network/integration/v1/sites/{site_uuid}/vpn/site-to-site-tunnels"
        )
        return self._extract(resp)

    async def get_firewall_policies(self, site_uuid: str) -> list[dict[str, Any]]:
        """Fetch firewall policies configured on a site (official integration API)."""
        resp = await self._get(
            f"/proxy/network/integration/v1/sites/{site_uuid}/firewall/policies"
        )
        return self._extract(resp)

    async def trigger_speedtest(self, interface_name: str | None = None) -> None:
        """Trigger a manual speedtest on the gateway."""
        payload: dict[str, Any] = {"cmd": "speedtest"}
        if interface_name:
            payload["interface_name"] = interface_name
        await self._post(f"/proxy/network/api/s/{self.site}/cmd/devmgr", payload)

    async def update_networkconf(self, net_id: str, payload: dict[str, Any]) -> None:
        """Update a network configuration object by ID."""
        await self._put(
            f"/proxy/network/api/s/{self.site}/rest/networkconf/{net_id}", payload
        )

    async def validate_connection(self) -> dict[str, Any]:
        """Validate credentials and return gateway identity.

        Returns a dict with ``mac``, ``model`` and ``sw_version``; with no gateway
        selected, ``mac`` is empty and ``model`` is omitted.
        Raises ``UnifiAuthError`` or ``UnifiConnectionError`` on failure.
        """
        if self.username and self.password and not self.api_key:
            await self.login()

        devices = await self.get_devices()
        sysinfo = await self.get_sysinfo()

        sw_version: str | None = None
        if sysinfo:
            sw_version = sysinfo[0].get("version")

        if not devices:
            raise UnifiConnectionError(
                "No devices returned — check site ID and permissions"
            )

        from .gateway import select_gateway

        selection = select_gateway(devices)
        gateway = selection.device
        if gateway is None:
            # No gateway selected (ambiguous or none): the entry falls back to
            # the host as its unique_id and the coordinator raises the repair.
            return {"mac": "", "sw_version": sw_version}
        return {
            "mac": gateway.get("mac", "").lower(),
            "model": gateway.get("model", "UDM Pro"),
            "sw_version": sw_version or gateway.get("version"),
        }
