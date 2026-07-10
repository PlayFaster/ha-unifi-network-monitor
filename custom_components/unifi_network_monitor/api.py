"""UniFi Network API client."""

from __future__ import annotations

import logging
import time as _time
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

_API_TIMEOUT = aiohttp.ClientTimeout(total=15)


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

    async def _post(self, path: str, payload: dict[str, Any]) -> Any:
        """Perform a POST request with automatic re-auth on 401."""
        url = f"{self._base_url()}{path}"
        try:
            async with self.session.post(
                url,
                json=payload,
                headers=self._auth_headers(),
                timeout=_API_TIMEOUT,
                ssl=False,
            ) as resp:
                if resp.status == 401:
                    if self.api_key:
                        _raise_auth_error("API key rejected (401)")
                    await self.login()
                    async with self.session.post(
                        url,
                        json=payload,
                        headers=self._auth_headers(),
                        timeout=_API_TIMEOUT,
                        ssl=False,
                    ) as retry:
                        retry.raise_for_status()
                        return await retry.json()
                resp.raise_for_status()
                return await resp.json()
        except (UnifiAuthError, UnifiConnectionError):
            raise
        except aiohttp.ClientResponseError as err:
            if err.status == 401:
                raise UnifiAuthError(f"Authentication failed: {err}") from err
            raise UnifiConnectionError(f"HTTP error {err.status}: {err}") from err
        except Exception as err:
            raise UnifiConnectionError(f"Request failed: {err}") from err

    async def _put(self, path: str, payload: dict[str, Any]) -> Any:
        """Perform a PUT request with automatic re-auth on 401."""
        url = f"{self._base_url()}{path}"
        try:
            async with self.session.put(
                url,
                json=payload,
                headers=self._auth_headers(),
                timeout=_API_TIMEOUT,
                ssl=False,
            ) as resp:
                if resp.status == 401:
                    if self.api_key:
                        _raise_auth_error("API key rejected (401)")
                    await self.login()
                    async with self.session.put(
                        url,
                        json=payload,
                        headers=self._auth_headers(),
                        timeout=_API_TIMEOUT,
                        ssl=False,
                    ) as retry:
                        retry.raise_for_status()
                        return await retry.json()
                resp.raise_for_status()
                return await resp.json()
        except (UnifiAuthError, UnifiConnectionError):
            raise
        except aiohttp.ClientResponseError as err:
            if err.status == 401:
                raise UnifiAuthError(f"Authentication failed: {err}") from err
            raise UnifiConnectionError(f"HTTP error {err.status}: {err}") from err
        except Exception as err:
            raise UnifiConnectionError(f"Request failed: {err}") from err

    async def _get(self, path: str) -> Any:
        """Perform a GET request with automatic re-auth on 401."""
        url = f"{self._base_url()}{path}"
        try:
            async with self.session.get(
                url,
                headers=self._auth_headers(),
                timeout=_API_TIMEOUT,
                ssl=False,
            ) as resp:
                if resp.status == 401:
                    if self.api_key:
                        _raise_auth_error("API key rejected (401)")
                    # Re-authenticate once
                    await self.login()
                    async with self.session.get(
                        url,
                        headers=self._auth_headers(),
                        timeout=_API_TIMEOUT,
                        ssl=False,
                    ) as retry:
                        retry.raise_for_status()
                        return await retry.json()
                resp.raise_for_status()
                return await resp.json()
        except (UnifiAuthError, UnifiConnectionError):
            raise
        except aiohttp.ClientResponseError as err:
            if err.status == 401:
                raise UnifiAuthError(f"Authentication failed: {err}") from err
            raise UnifiConnectionError(f"HTTP error {err.status}: {err}") from err
        except Exception as err:
            raise UnifiConnectionError(f"Request failed: {err}") from err

    def _extract(self, response: Any) -> list[dict[str, Any]]:
        """Extract ``data`` list from a UniFi API response envelope."""
        if isinstance(response, dict):
            return list(response.get("data", []))
        return []

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    async def login(self) -> None:
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
                    _raise_auth_error("Invalid username or password")
                resp.raise_for_status()
                # Extract TOKEN cookie
                cookie = resp.cookies.get("TOKEN")
                if cookie:
                    self._token = cookie.value
                else:
                    # Some firmware versions embed token in body
                    body = await resp.json()
                    self._token = (
                        body.get("data", {}).get("token")
                        if isinstance(body, dict)
                        else None
                    )
                # Extract CSRF token from response header (UDM Pro 2.x+)
                self._csrf = resp.headers.get("X-CSRF-Token") or resp.headers.get(
                    "x-csrf-token"
                )
                if not self._token:
                    _raise_auth_error("Login succeeded but no TOKEN received")
                _LOGGER.debug("UniFi login successful, CSRF=%s", bool(self._csrf))
        except (UnifiAuthError, UnifiConnectionError):
            raise
        except Exception as err:
            raise UnifiConnectionError(f"Login request failed: {err}") from err

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

    async def get_wlanconf(self) -> list[dict[str, Any]]:
        """Fetch WLAN configuration details (SSID states)."""
        resp = await self._get(f"/proxy/network/api/s/{self.site}/rest/wlanconf")
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

        Returns a dict with ``mac``, ``model``, and ``sw_version``.
        Raises ``UnifiAuthError`` or ``UnifiConnectionError`` on failure.
        """
        if self.username and self.password and not self.api_key:
            await self.login()

        devices = await self.get_devices()
        sysinfo = await self.get_sysinfo()

        sw_version: str | None = None
        if sysinfo:
            sw_version = sysinfo[0].get("version")

        from .const import GATEWAY_MODELS

        for device in devices:
            if device.get("model") in GATEWAY_MODELS:
                return {
                    "mac": device.get("mac", "").lower(),
                    "model": device.get("model", "UDM Pro"),
                    "sw_version": sw_version or device.get("version"),
                }

        # Fallback: treat first device as gateway
        if devices:
            d = devices[0]
            return {
                "mac": d.get("mac", "").lower(),
                "model": d.get("model", "UniFi Gateway"),
                "sw_version": sw_version,
            }

        raise UnifiConnectionError(
            "No devices returned — check site ID and permissions"
        )
