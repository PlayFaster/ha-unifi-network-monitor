"""DataUpdateCoordinator for UniFi Network Monitor."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import UnifiAuthError, UnifiConnectionError, UnifiNetworkAPI
from .const import (
    CONF_ENABLE_SECURITY_MONITORING,
    CONF_ENABLE_SPEEDTEST,
    CONF_ENABLE_WAN_USAGE,
    CONF_SCAN_INTERVAL,
    DEFAULT_ENABLE_SECURITY_MONITORING,
    DEFAULT_ENABLE_SPEEDTEST,
    DEFAULT_ENABLE_WAN_USAGE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EP_BACKUPS,
    EP_DAILY,
    EP_FIREWALL,
    EP_GUESTS,
    EP_MONTHLY,
    EP_NETWORKCONF,
    EP_ROGUE,
    EP_SETTINGS,
    EP_SPEEDTEST,
    EP_SYSINFO,
    EP_VPN_SERVERS,
    EP_VPN_TUNNELS,
    EP_WAN_IF,
    EP_WLAN,
    FETCH_STRIKE_LIMIT,
    GATEWAY_MODELS,
)

_LOGGER = logging.getLogger(__name__)


def disabled_endpoints(options: Mapping[str, Any]) -> frozenset[str]:
    """Return endpoints whose feature toggle is off.

    Used by the platforms to skip creating those entities, and mirrors the
    fetch-skip in ``_async_update_data`` so a disabled feature costs no polls
    and shows no entities.
    """
    disabled: set[str] = set()
    if not options.get(CONF_ENABLE_SPEEDTEST, DEFAULT_ENABLE_SPEEDTEST):
        disabled.add(EP_SPEEDTEST)
    if not options.get(CONF_ENABLE_WAN_USAGE, DEFAULT_ENABLE_WAN_USAGE):
        disabled.update({EP_DAILY, EP_MONTHLY})
    if not options.get(
        CONF_ENABLE_SECURITY_MONITORING, DEFAULT_ENABLE_SECURITY_MONITORING
    ):
        disabled.update({EP_ROGUE, EP_VPN_SERVERS, EP_VPN_TUNNELS, EP_FIREWALL})
    return frozenset(disabled)


def _safe_float(val: Any, default: float | None = None) -> float | None:
    """Safely coerce to float."""
    if val in (None, ""):
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _safe_int(val: Any, default: int | None = None) -> int | None:
    """Safely coerce to int."""
    if val in (None, ""):
        return default
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return default


def _derive_boot_time(uptime_secs: int | None, reference: datetime) -> datetime | None:
    """Derive a boot timestamp from uptime seconds, anchored to reference time."""
    if uptime_secs is None or uptime_secs < 0:
        return None
    return (reference - timedelta(seconds=uptime_secs)).replace(microsecond=0)


def _parse_gateway(
    device: dict[str, Any],
    update_time: datetime,
    coordinator: UnifiNetworkDataUpdateCoordinator | None = None,
) -> dict[str, Any]:
    """Extract gateway-specific data from a stat/device entry."""
    system_stats = device.get("system-stats") or {}
    cpu = _safe_float(system_stats.get("cpu"))
    ram = _safe_float(system_stats.get("mem"))
    uptime_secs = _safe_int(device.get("uptime"))

    # Temperatures
    cpu_temp: float | None = None
    board_temp: float | None = None
    for t in device.get("temperatures") or []:
        if t.get("type") == "cpu":
            cpu_temp = _safe_float(t.get("value"))
        elif t.get("type") == "board":
            board_temp = _safe_float(t.get("value"))

    # Storage (/persistent mount point)
    storage_used: int | None = None
    storage_size: int | None = None
    storage_used_pct: float | None = None
    for s in device.get("storage") or []:
        if s.get("mount_point") == "/persistent":
            storage_used = _safe_int(s.get("used"))
            storage_size = _safe_int(s.get("size"))
            if storage_used is not None and storage_size and storage_size > 0:
                storage_used_pct = round((storage_used / storage_size) * 100.0, 1)

    # Uplink
    uplink = device.get("uplink") or {}
    uplink_ip: str | None = None
    internet: bool = False
    speedtest_status: bool | None = None

    if uplink:
        internet = bool(uplink.get("up"))
        speedtest_status = uplink.get("speedtest_status") == "Success"
        if uplink.get("comment") == "WAN":
            uplink_ip = uplink.get("ip")

    # WAN1 / WAN2 real-time interface telemetry
    wan1_data = device.get("wan1") or {}
    wan2_data = device.get("wan2") or {}

    geo_info = device.get("geo_info") or {}
    active_geo_info = device.get("active_geo_info") or {}

    wan1_geo = geo_info.get("WAN") or {}
    wan1_active_geo = active_geo_info.get("WAN") or {}
    wan1_public_ip = wan1_geo.get("address") or wan1_active_geo.get("address")

    wan2_geo = geo_info.get("WAN2") or {}
    wan2_active_geo = active_geo_info.get("WAN2") or {}
    wan2_public_ip = wan2_geo.get("address") or wan2_active_geo.get("address")

    return {
        "mac": device.get("mac", "").lower(),
        "name": device.get("name", "UDM Pro"),
        "model": device.get("model", "UDM Pro"),
        "cpu": cpu,
        "ram": ram,
        "uptime_secs": uptime_secs,
        "boot_time": (
            coordinator.get_stable_boot_time("gateway", uptime_secs, update_time)
            if coordinator
            else _derive_boot_time(uptime_secs, update_time)
        ),
        "internet": internet,
        "speedtest_status": speedtest_status,
        "storage_used": storage_used,
        "storage_size": storage_size,
        "storage_used_pct": storage_used_pct,
        "cpu_temp": cpu_temp,
        "board_temp": board_temp,
        "wan1_local_ip": wan1_data.get("ip") or uplink_ip,
        "wan1_public_ip": wan1_public_ip,
        "wan2_local_ip": wan2_data.get("ip"),
        "wan2_public_ip": wan2_public_ip,
        "update_available": bool(device.get("upgradable")),
        # WAN1
        "wan1_ifname": wan1_data.get("ifname") or "eth8",
        "wan1_active": bool(wan1_data.get("is_uplink")),
        "wan1_up": bool(wan1_data.get("up")),
        "wan1_latency": _safe_int(wan1_data.get("latency")),
        "wan1_availability": _safe_float(wan1_data.get("availability")),
        "wan1_sfp_found": (
            bool(wan1_data.get("sfp_found")) if "sfp_found" in wan1_data else None
        ),
        "wan1_sfp_vendor": wan1_data.get("sfp_vendor"),
        "wan1_sfp_part": wan1_data.get("sfp_part"),
        "wan1_sfp_serial": wan1_data.get("sfp_serial"),
        # WAN2
        "wan2_ifname": wan2_data.get("ifname") or "eth9",
        "wan2_active": bool(wan2_data.get("is_uplink")),
        "wan2_up": bool(wan2_data.get("up")),
        "wan2_latency": _safe_int(wan2_data.get("latency")),
        "wan2_availability": _safe_float(wan2_data.get("availability")),
        "wan2_sfp_found": (
            bool(wan2_data.get("sfp_found")) if "sfp_found" in wan2_data else None
        ),
        "wan2_sfp_vendor": wan2_data.get("sfp_vendor"),
        "wan2_sfp_part": wan2_data.get("sfp_part"),
        "wan2_sfp_serial": wan2_data.get("sfp_serial"),
    }


def _parse_ap(
    device: dict[str, Any],
    update_time: datetime,
    coordinator: UnifiNetworkDataUpdateCoordinator | None = None,
) -> dict[str, Any]:
    """Extract AP-specific data from a stat/device entry."""
    system_stats = device.get("system-stats") or {}
    uptime_secs = _safe_int(device.get("uptime"))
    radio_stats = device.get("radio_table_stats") or []
    wifi0 = radio_stats[0] if len(radio_stats) > 0 else {}
    wifi1 = radio_stats[1] if len(radio_stats) > 1 else {}

    mac = device.get("mac", "").lower()

    return {
        "mac": mac,
        "name": device.get("name", "UniFi AP"),
        "model": device.get("model", ""),
        "type": "ap",
        "cpu": _safe_float(system_stats.get("cpu")),
        "ram": _safe_float(system_stats.get("mem")),
        "uptime_secs": uptime_secs,
        "boot_time": (
            coordinator.get_stable_boot_time(mac, uptime_secs, update_time)
            if coordinator
            else _derive_boot_time(uptime_secs, update_time)
        ),
        "update_available": bool(device.get("upgradable")),
        "clients": _safe_int(device.get("user-wlan-num_sta"), 0),
        "guests": _safe_int(device.get("guest-wlan-num_sta"), 0),
        "clients_wifi0": _safe_int(wifi0.get("user-num_sta"), 0),
        "clients_wifi1": _safe_int(wifi1.get("user-num_sta"), 0),
        "score": _safe_int(device.get("satisfaction")),
        "score_wifi0": _safe_int(wifi0.get("satisfaction")),
        "score_wifi1": _safe_int(wifi1.get("satisfaction")),
    }


def _parse_switch(
    device: dict[str, Any],
    update_time: datetime,
    coordinator: UnifiNetworkDataUpdateCoordinator | None = None,
) -> dict[str, Any]:
    """Extract switch-specific data from a stat/device entry."""
    system_stats = device.get("system-stats") or {}
    uptime_secs = _safe_int(device.get("uptime"))

    mac = device.get("mac", "").lower()

    return {
        "mac": mac,
        "name": device.get("name", "UniFi Switch"),
        "model": device.get("model", ""),
        "type": "switch",
        "cpu": _safe_float(system_stats.get("cpu")),
        "ram": _safe_float(system_stats.get("mem")),
        "uptime_secs": uptime_secs,
        "boot_time": (
            coordinator.get_stable_boot_time(mac, uptime_secs, update_time)
            if coordinator
            else _derive_boot_time(uptime_secs, update_time)
        ),
        "update_available": bool(device.get("upgradable")),
        "ports_used": _safe_int(device.get("num_sta"), 0),
        "ports_user": _safe_int(device.get("user-num_sta"), 0),
        "ports_guest": _safe_int(device.get("guest-num_sta"), 0),
    }


def _parse_health(
    health_list: list[dict[str, Any]],
    update_time: datetime,
    coordinator: UnifiNetworkDataUpdateCoordinator | None = None,
) -> dict[str, Any]:
    """Build the health data dict from the stat/health response."""
    health: dict[str, Any] = {}

    for h in health_list:
        subsystem = h.get("subsystem", "")

        if subsystem == "wan":
            health["wan_status"] = h.get("status", "unknown")
            health["wan_isp_name"] = h.get("isp_name", "")
            health["wan_isp_org"] = h.get("isp_organization", "")
            health["wan_gw_version"] = h.get("gw_version", "")
            health["wan_num_sta"] = _safe_int(h.get("num_sta"), 0)
            gw_stats = h.get("gw_system-stats") or {}
            health["wan_cpu"] = _safe_float(gw_stats.get("cpu"))
            health["wan_mem"] = _safe_float(gw_stats.get("mem"))
            health["wan_uptime"] = _safe_int(gw_stats.get("uptime"), 0)

            uptime_stats = h.get("uptime_stats") or {}

            wan1 = uptime_stats.get("WAN") or {}
            if wan1:
                wan1_uptime = _safe_int(wan1.get("uptime"), 0)
                health["wan1_availability"] = _safe_float(
                    wan1.get("availability"), 100.0
                )
                health["wan1_latency_avg"] = _safe_int(wan1.get("latency_average"), 0)
                health["wan1_time_period"] = _safe_int(wan1.get("time_period"), 0)
                health["wan1_uptime"] = wan1_uptime
                health["wan1_boot_time"] = (
                    coordinator.get_stable_boot_time("wan1", wan1_uptime, update_time)
                    if coordinator
                    else _derive_boot_time(wan1_uptime, update_time)
                )

            wan2 = uptime_stats.get("WAN2") or {}
            if wan2:
                wan2_uptime = _safe_int(wan2.get("uptime"), 0)
                health["wan2_availability"] = _safe_float(
                    wan2.get("availability"), 100.0
                )
                health["wan2_latency_avg"] = _safe_int(wan2.get("latency_average"), 0)
                health["wan2_time_period"] = _safe_int(wan2.get("time_period"), 0)
                health["wan2_uptime"] = wan2_uptime
                health["wan2_boot_time"] = (
                    coordinator.get_stable_boot_time("wan2", wan2_uptime, update_time)
                    if coordinator
                    else _derive_boot_time(wan2_uptime, update_time)
                )

        elif subsystem == "www":
            health["www_status"] = h.get("status", "unknown")
            health["www_latency"] = _safe_int(h.get("latency"), 0)
            www_uptime = _safe_int(h.get("uptime"), 0)
            health["www_uptime"] = www_uptime
            health["www_boot_time"] = (
                coordinator.get_stable_boot_time("www", www_uptime, update_time)
                if coordinator
                else _derive_boot_time(www_uptime, update_time)
            )
            health["www_drops"] = _safe_int(h.get("drops"), 0)
            health["www_speedtest_status"] = h.get("speedtest_status", "")

        elif subsystem == "wlan":
            health["wlan_status"] = h.get("status", "unknown")
            health["wlan_num_user"] = _safe_int(h.get("num_user"), 0)
            health["wlan_num_guest"] = _safe_int(h.get("num_guest"), 0)
            health["wlan_num_iot"] = _safe_int(h.get("num_iot"), 0)
            health["wlan_num_ap"] = _safe_int(h.get("num_ap"), 0)

        elif subsystem == "lan":
            health["lan_status"] = h.get("status", "unknown")
            health["lan_num_user"] = _safe_int(h.get("num_user"), 0)
            health["lan_num_iot"] = _safe_int(h.get("num_iot"), 0)
            health["lan_num_sw"] = _safe_int(h.get("num_sw"), 0)
            health["lan_num_adopted"] = _safe_int(h.get("num_adopted"), 0)

        elif subsystem == "vpn":
            health["vpn_status"] = h.get("status", "unknown")

    return health


class UnifiNetworkDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that fetches and structures all UniFi Network data."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: UnifiNetworkAPI,
    ) -> None:
        """Initialize the coordinator."""
        self.api = api
        self.entry = entry
        self.consecutive_failures = 0
        self.last_update_success_time: datetime | None = None
        self._was_available = True
        # Snapshot of the options that require a full reload when changed (set in
        # async_setup_entry). Live-tunable options (scan interval, proximity
        # threshold, pause) are excluded so their controls don't force a reload.
        self.reload_signature: dict[str, Any] = {}

        # Per-endpoint resilience: each optional endpoint holds its last-good
        # payload for up to FETCH_STRIKE_LIMIT consecutive failures, then is
        # flagged stale so its entities report "unavailable" while the rest of
        # the update continues. See endpoint_available().
        self._endpoint_state: dict[str, dict[str, Any]] = {}
        self._stale_endpoints: set[str] = set()

        # "Flat Identity" — loaded from entry.data, stable without a network call
        self.gateway_mac: str = entry.data.get("mac", "")
        self.gateway_model: str = entry.data.get("model", "UDM Pro")
        self.sw_version: str | None = entry.data.get("sw_version")
        self.site_uuid: str | None = None

        # Full networkconf objects for WAN/WAN2 — needed for PUT writes
        self._networkconf_wan: dict[str, Any] | None = None
        self._networkconf_wan2: dict[str, Any] | None = None

        # Load persisted boot times for reboot-detection latch
        self._boot_times: dict[str, dict[str, Any]] = {}
        boot_times_raw = entry.data.get("boot_times")
        if isinstance(boot_times_raw, dict):
            self._boot_times = {
                k: dict(v) for k, v in boot_times_raw.items() if isinstance(v, dict)
            }

        scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{entry.title} Data",
            update_interval=timedelta(seconds=scan_interval),
        )

    def get_stable_boot_time(
        self, key: str, uptime_secs: int | None, reference: datetime
    ) -> datetime | None:
        """Derive and stabilize a boot timestamp using a reboot-detection latch."""
        if uptime_secs is None or uptime_secs < 0:
            # Bad-reading guard: keep the existing boot time if there is one
            if key in self._boot_times:
                boot_time_str = self._boot_times[key].get("boot_time")
                if boot_time_str:
                    with contextlib.suppress(Exception):
                        return dt_util.parse_datetime(boot_time_str)
            return None

        # Retrieve cached boot time and last uptime
        cached = self._boot_times.get(key) or {}
        cached_boot_time: datetime | None = None
        cached_boot_time_str = cached.get("boot_time")
        if cached_boot_time_str:
            with contextlib.suppress(Exception):
                cached_boot_time = dt_util.parse_datetime(cached_boot_time_str)
        cached_last_uptime = cached.get("last_uptime")

        # Check if we need to (re-)latch
        is_reboot = cached_boot_time is None or (
            cached_last_uptime is not None and uptime_secs < cached_last_uptime - 30
        )

        if is_reboot:
            calc_time = reference - timedelta(seconds=uptime_secs)
            stable_boot = calc_time.replace(microsecond=0)
            self._boot_times[key] = {
                "boot_time": stable_boot.isoformat(),
                "last_uptime": uptime_secs,
            }
            # Copy and persist
            new_data = {
                **self.entry.data,
                "boot_times": {k: dict(v) for k, v in self._boot_times.items()},
            }
            self.hass.config_entries.async_update_entry(self.entry, data=new_data)
            return stable_boot

        # Update last_uptime in-memory only (avoid config entry write on every poll)
        if key in self._boot_times:
            self._boot_times[key]["last_uptime"] = uptime_secs
        else:  # pragma: no cover - defensive; unreachable while cached_boot_time is set
            self._boot_times[key] = {
                "boot_time": (
                    cached_boot_time.isoformat()
                    if cached_boot_time
                    else reference.isoformat()
                ),
                "last_uptime": uptime_secs,
            }
        return cached_boot_time

    @property
    def wan_weights_writable(self) -> bool:
        """True once both WAN networkconf objects are loaded (weights writable)."""
        return self._networkconf_wan is not None and self._networkconf_wan2 is not None

    async def async_set_wan_weights(self, wan1_weight: int) -> None:
        """Write WAN1/WAN2 load balance weights — always sums to 100."""
        wan2_weight = 100 - wan1_weight
        if self._networkconf_wan is None or self._networkconf_wan2 is None:
            raise ValueError("WAN network configuration not yet loaded")
        wan1_id = self._networkconf_wan.get("_id")
        wan2_id = self._networkconf_wan2.get("_id")
        if not wan1_id or not wan2_id:
            raise ValueError("WAN network configuration missing _id")
        await self.api.update_networkconf(
            wan1_id,
            {**self._networkconf_wan, "wan_load_balance_weight": wan1_weight},
        )
        await self.api.update_networkconf(
            wan2_id,
            {**self._networkconf_wan2, "wan_load_balance_weight": wan2_weight},
        )
        # Brief pause to let the UDM Pro commit the change before re-polling
        await asyncio.sleep(1.5)
        await self.async_request_refresh()

    async def async_trigger_speedtest(self, interface_name: str | None = None) -> None:
        """Trigger a manual speedtest on the gateway."""
        await self.api.trigger_speedtest(interface_name)

    @callback
    def _sync_site_issue(self) -> None:
        """Raise or clear a repair issue based on v3 site resolution.

        A ``site_uuid`` of ``"failed"`` means the v3 API could not be reached —
        usually an API key lacking full site permissions — which silently
        disables the VPN, firewall, and WAN-interface-name sensors. Surface it
        in the Repairs panel so the user can act; clear it once resolved.

        The v3 (integration) endpoints are only reachable with an API key, so
        under username/password auth this failure is *expected* and not
        actionable — suppress the repair issue entirely in that mode.
        """
        if self.site_uuid == "failed" and self.api.api_key:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                "site_resolution_failed",
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="site_resolution_failed",
            )
        elif self.site_uuid is not None:
            ir.async_delete_issue(self.hass, DOMAIN, "site_resolution_failed")

    def endpoint_available(self, source: str | None) -> bool:
        """Return False when an optional endpoint has exhausted its retry strikes.

        Entities tag themselves with the endpoint `source` they depend on; a
        stale endpoint makes those entities report "unavailable" while endpoints
        that are still succeeding keep serving data.
        """
        if source is None:
            return True
        return source not in self._stale_endpoints

    def _hold_or_stale(
        self,
        label: str,
        state: dict[str, Any],
        err: Exception,
        level: int,
    ) -> list[dict[str, Any]]:
        """Apply the per-endpoint strike rule on a failed optional fetch.

        Holds the last-good payload for the first FETCH_STRIKE_LIMIT failures,
        then flags the endpoint stale (entities go unavailable). The held
        payload is still returned so the rest of the update proceeds.
        """
        state["failures"] += 1
        if state["failures"] <= FETCH_STRIKE_LIMIT:
            _LOGGER.log(
                level,
                "%s: %s fetch failed (%d/%d), holding last values: %s",
                self.entry.title,
                label,
                state["failures"],
                FETCH_STRIKE_LIMIT,
                err,
            )
        else:
            if label not in self._stale_endpoints:
                _LOGGER.warning(
                    "%s: %s unavailable after %d consecutive failures: %s",
                    self.entry.title,
                    label,
                    state["failures"],
                    err,
                )
            self._stale_endpoints.add(label)
        last_good: list[dict[str, Any]] = state["last_good"]
        return last_good

    async def _skip_fetch(self, label: str) -> list[dict[str, Any]]:
        """No-op stand-in for a disabled endpoint — no network call.

        Keeps the gather list's positional layout intact while clearing any
        prior state so a re-enabled endpoint starts fresh.
        """
        self._endpoint_state.pop(label, None)
        self._stale_endpoints.discard(label)
        return []

    def _optional(
        self,
        enabled: bool,
        method: Any,
        label: str,
    ) -> Any:
        """Return a real fetch coroutine, or a no-op skip when disabled."""
        if enabled:
            return self._fetch_optional(method, label)
        return self._skip_fetch(label)

    async def _fetch_optional(
        self,
        method: Any,
        label: str,
    ) -> list[dict[str, Any]]:
        """Fetch a supplementary endpoint with per-endpoint resilience.

        On success: cache and return the fresh payload, clearing any stale flag.
        On failure: hold the last-good payload (strikes 1..FETCH_STRIKE_LIMIT),
        then mark the endpoint stale. A broad ``except`` is intentional so a
        changed/unexpected API response degrades this one endpoint rather than
        tripping the global failure path.
        """
        state = self._endpoint_state.setdefault(label, {"last_good": [], "failures": 0})
        try:
            data = list(await method())
        except (UnifiConnectionError, UnifiAuthError, TimeoutError) as err:
            return self._hold_or_stale(label, state, err, logging.DEBUG)
        except Exception as err:  # noqa: BLE001 - tolerate API drift per-endpoint
            return self._hold_or_stale(label, state, err, logging.WARNING)
        state["last_good"] = data
        state["failures"] = 0
        self._stale_endpoints.discard(label)
        return data

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch all data with 3-strike resilience."""
        is_paused = self.entry.options.get("stop_polling", False)
        if is_paused and self.data is not None:
            _LOGGER.debug(
                "%s: Polling is paused; returning cached data.", self.entry.title
            )
            return self.data

        try:
            # Resolve Site UUID if using API Key and not resolved yet
            if self.site_uuid is None:
                try:
                    sites = await self.api.get_sites()
                    target_site = (
                        self.api.site
                        if hasattr(self.api, "site") and isinstance(self.api.site, str)
                        else "default"
                    )
                    for s in sites:
                        if s.get("internalReference") == target_site:
                            self.site_uuid = s.get("id")
                            break
                    if not self.site_uuid:
                        _LOGGER.warning(
                            "Could not find site UUID for site %s", target_site
                        )
                        self.site_uuid = "failed"
                except TypeError as err:
                    _LOGGER.debug(
                        "TypeError during site UUID resolution "
                        "(likely unmocked in test): %s",
                        err,
                    )
                    self.site_uuid = "failed"
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug("Failed to fetch sites for UUID resolution: %s", err)
                    if (
                        "HTTP error 404" in str(err)
                        or "HTTP error 400" in str(err)
                        or "API key rejected" in str(err)
                        or isinstance(err, UnifiAuthError)
                    ):
                        self.site_uuid = "failed"
                self._sync_site_issue()

            async with asyncio.timeout(30):
                update_time = dt_util.now()

                # Feature toggles — a disabled category skips its network call(s)
                # while keeping the gather list's positional layout intact.
                opts = self.entry.options
                want_speedtest = opts.get(
                    CONF_ENABLE_SPEEDTEST, DEFAULT_ENABLE_SPEEDTEST
                )
                want_wan_usage = opts.get(
                    CONF_ENABLE_WAN_USAGE, DEFAULT_ENABLE_WAN_USAGE
                )
                want_security = opts.get(
                    CONF_ENABLE_SECURITY_MONITORING, DEFAULT_ENABLE_SECURITY_MONITORING
                )

                # Define concurrent tasks
                tasks = [
                    self.api.get_devices(),
                    self.api.get_health(),
                    self._fetch_optional(self.api.get_sysinfo, EP_SYSINFO),
                    self._fetch_optional(self.api.get_networkconf, EP_NETWORKCONF),
                    self._fetch_optional(self.api.get_settings, EP_SETTINGS),
                    self._optional(
                        want_wan_usage, self.api.get_daily_gateway, EP_DAILY
                    ),
                    self._optional(
                        want_wan_usage, self.api.get_monthly_gateway, EP_MONTHLY
                    ),
                    self._optional(want_security, self.api.get_rogueaps, EP_ROGUE),
                    self._fetch_optional(self.api.get_guests, EP_GUESTS),
                    self._fetch_optional(self.api.get_backups, EP_BACKUPS),
                    self._optional(
                        want_speedtest, self.api.get_speedtest_results, EP_SPEEDTEST
                    ),
                    self._fetch_optional(self.api.get_wlanconf, EP_WLAN),
                ]

                # Conditional v3 endpoint fetches
                if self.site_uuid and self.site_uuid != "failed":
                    tasks.extend(
                        [
                            self._fetch_optional(
                                lambda: self.api.get_wan_interfaces(self.site_uuid),
                                EP_WAN_IF,
                            ),
                            self._optional(
                                want_security,
                                lambda: self.api.get_vpn_servers(self.site_uuid),
                                EP_VPN_SERVERS,
                            ),
                            self._optional(
                                want_security,
                                lambda: self.api.get_vpn_tunnels(self.site_uuid),
                                EP_VPN_TUNNELS,
                            ),
                            self._optional(
                                want_security,
                                lambda: self.api.get_firewall_policies(self.site_uuid),
                                EP_FIREWALL,
                            ),
                        ]
                    )
                else:

                    async def dummy_fetch() -> list[Any]:
                        return []

                    tasks.extend(
                        [dummy_fetch(), dummy_fetch(), dummy_fetch(), dummy_fetch()]
                    )

                results = await asyncio.gather(*tasks)

                (
                    devices_raw,
                    health_raw,
                    sysinfo_raw,
                    networkconf_raw,
                    settings_raw,
                    daily_gateway_raw,
                    monthly_gateway_raw,
                    rogueaps_raw,
                    guests_raw,
                    backups_raw,
                    speedtest_raw,
                    wlanconf_raw,
                    wan_interfaces_raw,
                    _vpn_servers_raw,
                    vpn_tunnels_raw,
                    firewall_policies_raw,
                ) = results

                sw_version: str | None = None
                if sysinfo_raw:
                    sw_version = sysinfo_raw[0].get("version")

                # Separate gateway from APs/switches
                gateway_device: dict[str, Any] | None = None
                gateway_data: dict[str, Any] | None = None
                devices: dict[str, dict[str, Any]] = {}

                for device in devices_raw:
                    if device.get("state", 0) == 0:
                        continue  # Offline — skip
                    try:
                        if device.get("model") in GATEWAY_MODELS:
                            gateway_device = device
                            gateway_data = _parse_gateway(device, update_time, self)
                        elif device.get("is_access_point"):
                            parsed = _parse_ap(device, update_time, self)
                            devices[parsed["mac"]] = parsed
                        else:
                            parsed = _parse_switch(device, update_time, self)
                            devices[parsed["mac"]] = parsed
                    except (
                        AttributeError,
                        KeyError,
                        TypeError,
                        ValueError,
                        IndexError,
                    ) as err:
                        _LOGGER.warning(
                            "%s: Failed to parse device %s, skipping: %s",
                            self.entry.title,
                            device.get("mac", "unknown"),
                            err,
                        )

                health = _parse_health(health_raw, update_time, self)

                # Parse load-balancing configs from networkconf
                wan_mode: str | None = None
                wan1_weight: int | None = None
                wan2_weight: int | None = None
                for net in networkconf_raw or []:
                    if net.get("purpose") == "wan":
                        net_group = net.get("wan_networkgroup")
                        if net_group == "WAN":
                            wan1_weight = _safe_int(net.get("wan_load_balance_weight"))
                            wan_mode = net.get("wan_load_balance_type")
                            self._networkconf_wan = net
                        elif net_group == "WAN2":
                            wan2_weight = _safe_int(net.get("wan_load_balance_weight"))
                            if not wan_mode:
                                wan_mode = net.get("wan_load_balance_type")
                            self._networkconf_wan2 = net

                # Parse threat management settings
                ips_mode: str | None = None
                ad_blocking: bool | None = None
                honeypot: bool | None = None
                for setting in settings_raw or []:
                    if setting.get("key") == "ips":
                        ips_mode = setting.get("ips_mode")
                        ad_blocking = bool(setting.get("ad_blocking_enabled"))
                        honeypot = bool(setting.get("honeypot_enabled"))

                # Today's Internet Usage
                wan1_today_rx = None
                wan1_today_tx = None
                wan2_today_rx = None
                wan2_today_tx = None
                try:
                    if daily_gateway_raw:
                        sorted_daily = sorted(
                            daily_gateway_raw,
                            key=lambda x: x.get("time") or 0,
                            reverse=True,
                        )
                        latest_daily = sorted_daily[0]
                        wan1_today_rx = _safe_float(latest_daily.get("wan-rx_bytes"))
                        wan1_today_tx = _safe_float(latest_daily.get("wan-tx_bytes"))
                        wan2_today_rx = _safe_float(latest_daily.get("wan2-rx_bytes"))
                        wan2_today_tx = _safe_float(latest_daily.get("wan2-tx_bytes"))
                except (
                    AttributeError,
                    KeyError,
                    TypeError,
                    ValueError,
                    IndexError,
                ) as err:
                    _LOGGER.debug(
                        "%s: Failed to parse daily gateway data: %s",
                        self.entry.title,
                        err,
                    )

                # Monthly Internet Usage
                wan1_month_rx = None
                wan1_month_tx = None
                wan2_month_rx = None
                wan2_month_tx = None
                try:
                    if monthly_gateway_raw:
                        sorted_monthly = sorted(
                            monthly_gateway_raw,
                            key=lambda x: x.get("time") or 0,
                            reverse=True,
                        )
                        latest_monthly = sorted_monthly[0]
                        wan1_month_rx = _safe_float(latest_monthly.get("wan-rx_bytes"))
                        wan1_month_tx = _safe_float(latest_monthly.get("wan-tx_bytes"))
                        wan2_month_rx = _safe_float(latest_monthly.get("wan2-rx_bytes"))
                        wan2_month_tx = _safe_float(latest_monthly.get("wan2-tx_bytes"))
                except (
                    AttributeError,
                    KeyError,
                    TypeError,
                    ValueError,
                    IndexError,
                ) as err:
                    _LOGGER.debug(
                        "%s: Failed to parse monthly gateway data: %s",
                        self.entry.title,
                        err,
                    )

                # Rogue Access Points
                rogue_ap_count = 0
                rogue_aps_list: list[dict[str, Any]] = []
                # "None Detected" (not unknown) is preferred for the text sensor
                # when no rogues are present; the RSSI counterpart stays None so
                # its numeric sensor reports "unknown" rather than a fake 0.
                strongest_rogue_ssid: str = "None Detected"
                strongest_rogue_rssi: int | None = None
                try:
                    ap_name_map = {}
                    for device in devices_raw or []:
                        mac = device.get("mac")
                        if mac:
                            ap_name_map[mac.lower()] = (
                                device.get("name") or device.get("model") or mac
                            )

                    rogue_ap_count = (
                        len(rogueaps_raw) if rogueaps_raw is not None else 0
                    )
                    for r in rogueaps_raw or []:
                        ap_mac = r.get("ap_mac", "")
                        detected_by = ap_name_map.get(ap_mac.lower()) or ap_mac
                        age_val = _safe_int(r.get("age"))
                        age_str = f"{age_val}h" if age_val is not None else None
                        rogue_aps_list.append(
                            {
                                "essid": r.get("essid", ""),
                                "bssid": r.get("bssid", ""),
                                "channel": _safe_int(r.get("channel")),
                                "signal": _safe_int(r.get("signal")),
                                "oui": r.get("oui", ""),
                                "age": age_str,
                                "detected_by": detected_by,
                            }
                        )

                    # Strongest rogue = highest (least-negative) signal in dBm.
                    signalled = [
                        ap for ap in rogue_aps_list if ap.get("signal") is not None
                    ]
                    if signalled:
                        strongest = max(signalled, key=lambda ap: ap["signal"])
                        strongest_rogue_ssid = strongest.get("essid") or "None Detected"
                        strongest_rogue_rssi = strongest.get("signal")
                except (
                    AttributeError,
                    KeyError,
                    TypeError,
                    ValueError,
                    IndexError,
                ) as err:
                    _LOGGER.debug(
                        "%s: Failed to parse rogue AP data: %s", self.entry.title, err
                    )

                # Guest User Count
                guest_user_count = 0
                try:
                    guest_user_count = len(guests_raw) if guests_raw is not None else 0
                except (
                    AttributeError,
                    KeyError,
                    TypeError,
                    ValueError,
                    IndexError,
                ) as err:
                    _LOGGER.debug(
                        "%s: Failed to parse guest data: %s", self.entry.title, err
                    )

                # Auto Backups
                last_backup = None
                try:
                    if backups_raw:
                        sorted_backups = sorted(
                            backups_raw,
                            key=lambda x: x.get("time") or 0,
                            reverse=True,
                        )
                        latest_backup = sorted_backups[0]
                        backup_time_ms = latest_backup.get("time")
                        if backup_time_ms:
                            last_backup = datetime.fromtimestamp(
                                backup_time_ms / 1000.0, tz=UTC
                            )
                except (
                    AttributeError,
                    KeyError,
                    TypeError,
                    ValueError,
                    IndexError,
                ) as err:
                    _LOGGER.debug(
                        "%s: Failed to parse backup data: %s", self.entry.title, err
                    )

                # Configured VLANs Count
                configured_vlans = 0
                for net in networkconf_raw or []:
                    if net.get("vlan") is not None:
                        configured_vlans += 1

                # Firmware Details
                application_version = None
                application_build = None
                device_type = None
                udm_version = None
                if sysinfo_raw:
                    sys_item = sysinfo_raw[0]
                    application_version = sys_item.get("version")
                    application_build = sys_item.get("build")
                    device_type = sys_item.get("ubnt_device_type")
                    udm_version = sys_item.get("udm_version") or sys_item.get(
                        "sw_version"
                    )

                # WAN1 & WAN2 Speedtests
                wan1_speedtest_download = None
                wan1_speedtest_upload = None
                wan1_speedtest_ping = None
                wan1_speedtest_lastrun = None

                wan2_speedtest_download = None
                wan2_speedtest_upload = None
                wan2_speedtest_ping = None
                wan2_speedtest_lastrun = None

                try:
                    if speedtest_raw:
                        # Sort descending to get newest speedtests first
                        sorted_speedtest = sorted(
                            speedtest_raw,
                            key=lambda x: x.get("time") or 0,
                            reverse=True,
                        )

                        # Get configured physical interfaces for WAN1/WAN2
                        wan1_ifname = "eth8"
                        wan2_ifname = "eth9"
                        if gateway_device:
                            wan1_ifname = (
                                gateway_device.get("wan1", {}).get("ifname") or "eth8"
                            )
                            wan2_ifname = (
                                gateway_device.get("wan2", {}).get("ifname") or "eth9"
                            )

                        # Check if results have interface metadata
                        has_interface = any(
                            "interface_name" in x for x in sorted_speedtest
                        )

                        w1 = None
                        w2 = None

                        if has_interface:
                            # 1. Map by interface name or network group (preferred)
                            for item in sorted_speedtest:
                                if w1 is None and (
                                    item.get("interface_name") == wan1_ifname
                                    or item.get("wan_networkgroup") == "WAN"
                                ):
                                    w1 = item
                                if w2 is None and (
                                    item.get("interface_name") == wan2_ifname
                                    or item.get("wan_networkgroup") == "WAN2"
                                ):
                                    w2 = item
                                if w1 is not None and w2 is not None:
                                    break
                        # 2. Fallback to proximity-based ordering for compatibility
                        elif len(sorted_speedtest) >= 2:
                            t0 = sorted_speedtest[0].get("time") or 0
                            t1 = sorted_speedtest[1].get("time") or 0
                            if abs(t0 - t1) <= 600 * 1000:
                                w1 = sorted_speedtest[1]
                                w2 = sorted_speedtest[0]
                            else:
                                w1 = sorted_speedtest[0]
                                w2 = None
                        elif len(sorted_speedtest) == 1:
                            w1 = sorted_speedtest[0]
                            w2 = None

                        # Map variables to gateway fields
                        if w1:
                            download = w1.get("download_mbps") or w1.get(
                                "xput_download"
                            )
                            upload = w1.get("upload_mbps") or w1.get("xput_upload")
                            ping = w1.get("latency_ms") or w1.get("latency")
                            wan1_speedtest_download = _safe_float(download)
                            wan1_speedtest_upload = _safe_float(upload)
                            wan1_speedtest_ping = _safe_float(ping)
                            w1_time = w1.get("time")
                            if w1_time:
                                wan1_speedtest_lastrun = datetime.fromtimestamp(
                                    w1_time / 1000.0, tz=UTC
                                )

                        if w2:
                            download = w2.get("download_mbps") or w2.get(
                                "xput_download"
                            )
                            upload = w2.get("upload_mbps") or w2.get("xput_upload")
                            ping = w2.get("latency_ms") or w2.get("latency")
                            wan2_speedtest_download = _safe_float(download)
                            wan2_speedtest_upload = _safe_float(upload)
                            wan2_speedtest_ping = _safe_float(ping)
                            w2_time = w2.get("time")
                            if w2_time:
                                wan2_speedtest_lastrun = datetime.fromtimestamp(
                                    w2_time / 1000.0, tz=UTC
                                )
                except (
                    AttributeError,
                    KeyError,
                    TypeError,
                    ValueError,
                    IndexError,
                ) as err:
                    _LOGGER.debug(
                        "%s: Failed to parse speedtest data: %s", self.entry.title, err
                    )

                # Parse WLAN Configurations (WiFi SSIDs)
                wifi_networks_total = None
                wifi_networks_active = None
                wifi_states = {}
                if isinstance(wlanconf_raw, list):
                    wifi_networks_total = len(wlanconf_raw)
                    wifi_networks_active = sum(
                        1 for w in wlanconf_raw if w.get("enabled")
                    )
                    wifi_states = {
                        w.get("name"): bool(w.get("enabled"))
                        for w in wlanconf_raw
                        if w.get("name")
                    }

                # Parse VLANs configurations
                vlans_total = None
                vlans_active = None
                if isinstance(networkconf_raw, list):
                    vlans_total = sum(
                        1 for net in networkconf_raw if net.get("vlan") is not None
                    )
                    vlans_active = sum(
                        1
                        for net in networkconf_raw
                        if net.get("vlan") is not None and net.get("enabled", True)
                    )

                # Parse VPN site-to-site tunnels and servers
                vpn_connections_total = None
                vpn_connections_active = None
                vpn_states = {}
                if self.site_uuid and self.site_uuid != "failed":
                    if isinstance(vpn_tunnels_raw, list):
                        vpn_connections_total = len(vpn_tunnels_raw)
                        vpn_connections_active = sum(
                            1 for t in vpn_tunnels_raw if t.get("state") == "CONNECTED"
                        )
                        vpn_states = {
                            t.get("name"): (t.get("state") == "CONNECTED")
                            for t in vpn_tunnels_raw
                            if t.get("name")
                        }

                # Parse Firewall Policies
                rules_configured = None
                rules_active = None
                rules_disabled = None
                if self.site_uuid and self.site_uuid != "failed":
                    if isinstance(firewall_policies_raw, list):
                        rules_configured = len(firewall_policies_raw)
                        rules_active = sum(
                            1 for p in firewall_policies_raw if p.get("enabled")
                        )
                        rules_disabled = sum(
                            1 for p in firewall_policies_raw if not p.get("enabled")
                        )

                # Parse WAN interface custom names (aliases)
                wan1_interface_name = None
                wan2_interface_name = None
                if (
                    self.site_uuid
                    and self.site_uuid != "failed"
                    and isinstance(wan_interfaces_raw, list)
                ):
                    for wan in wan_interfaces_raw:
                        name = wan.get("name", "")
                        if "wan1" in name.lower():
                            wan1_interface_name = name
                        elif "wan2" in name.lower():
                            wan2_interface_name = name
                    # Fallbacks if string match doesn't hit
                    if not wan1_interface_name and len(wan_interfaces_raw) > 0:
                        wan1_interface_name = wan_interfaces_raw[0].get("name")
                    if not wan2_interface_name and len(wan_interfaces_raw) > 1:
                        wan2_interface_name = wan_interfaces_raw[1].get("name")

                # Inject parsed configuration into gateway data if gateway is present
                if gateway_data is not None:
                    gateway_data.update(
                        {
                            "wan_mode": wan_mode,
                            "wan1_weight": wan1_weight,
                            "wan2_weight": wan2_weight,
                            "ips_mode": ips_mode,
                            "ad_blocking": ad_blocking,
                            "honeypot": honeypot,
                            "wan1_today_rx": wan1_today_rx,
                            "wan1_today_tx": wan1_today_tx,
                            "wan2_today_rx": wan2_today_rx,
                            "wan2_today_tx": wan2_today_tx,
                            "wan1_month_rx": wan1_month_rx,
                            "wan1_month_tx": wan1_month_tx,
                            "wan2_month_rx": wan2_month_rx,
                            "wan2_month_tx": wan2_month_tx,
                            "rogue_ap_count": rogue_ap_count,
                            "rogue_aps_list": rogue_aps_list,
                            "strongest_rogue_ssid": strongest_rogue_ssid,
                            "strongest_rogue_rssi": strongest_rogue_rssi,
                            "guest_user_count": guest_user_count,
                            "last_backup": last_backup,
                            "configured_vlans": configured_vlans,
                            "application_version": application_version,
                            "application_build": application_build,
                            "device_type": device_type,
                            "udm_version": udm_version,
                            "wan1_speedtest_download": wan1_speedtest_download,
                            "wan1_speedtest_upload": wan1_speedtest_upload,
                            "wan1_speedtest_ping": wan1_speedtest_ping,
                            "wan1_speedtest_lastrun": wan1_speedtest_lastrun,
                            "wan2_speedtest_download": wan2_speedtest_download,
                            "wan2_speedtest_upload": wan2_speedtest_upload,
                            "wan2_speedtest_ping": wan2_speedtest_ping,
                            "wan2_speedtest_lastrun": wan2_speedtest_lastrun,
                            "wifi_networks_total": wifi_networks_total,
                            "wifi_networks_active": wifi_networks_active,
                            "wifi_states": wifi_states,
                            "vlans_total": vlans_total,
                            "vlans_active": vlans_active,
                            "vpn_connections_total": vpn_connections_total,
                            "vpn_connections_active": vpn_connections_active,
                            "vpn_states": vpn_states,
                            "rules_configured": rules_configured,
                            "rules_active": rules_active,
                            "rules_disabled": rules_disabled,
                            "wan1_interface_name": wan1_interface_name,
                            "wan2_interface_name": wan2_interface_name,
                        }
                    )

                # Update sw_version on coordinator if changed
                if sw_version and sw_version != self.sw_version:
                    self.sw_version = sw_version

                self.consecutive_failures = 0
                self.last_update_success_time = update_time
                if not self._was_available:
                    self._was_available = True
                    _LOGGER.info("%s: Reconnected successfully.", self.entry.title)

                return {
                    "gateway": gateway_data or {},
                    "health": health,
                    "devices": devices,
                    "sw_version": sw_version,
                }

        except UnifiAuthError as err:
            self.consecutive_failures += 1
            if self.data is not None and self.consecutive_failures <= 3:
                log = (
                    _LOGGER.warning if self.consecutive_failures == 1 else _LOGGER.debug
                )
                log(
                    "%s: Authentication error fetching UniFi data (failure %d/3), holding last values: %s",  # noqa: E501
                    self.entry.title,
                    self.consecutive_failures,
                    err,
                )
                return self.data
            _LOGGER.error("%s: Authentication failed: %s", self.entry.title, err)
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err

        except (UnifiConnectionError, TimeoutError) as err:
            self.consecutive_failures += 1
            if self.data is not None and self.consecutive_failures <= 3:
                log = (
                    _LOGGER.warning if self.consecutive_failures == 1 else _LOGGER.debug
                )
                log(
                    "%s: Error fetching UniFi data (failure %d/3), holding last values: %s",  # noqa: E501
                    self.entry.title,
                    self.consecutive_failures,
                    err,
                )
                return self.data
            self._was_available = False
            _LOGGER.error(
                "%s: Communication lost after 3 failures: %s", self.entry.title, err
            )
            if not self.data:
                raise ConfigEntryNotReady(f"Communication error: {err}") from err
            raise UpdateFailed(f"Communication error: {err}") from err

        except Exception as err:
            self.consecutive_failures += 1
            if self.data is not None and self.consecutive_failures <= 3:
                log = (
                    _LOGGER.warning if self.consecutive_failures == 1 else _LOGGER.debug
                )
                log(
                    "%s: Unexpected error (failure %d/3), holding last values: %s",
                    self.entry.title,
                    self.consecutive_failures,
                    err,
                )
                return self.data
            self._was_available = False
            _LOGGER.error("%s: Unexpected error: %s", self.entry.title, err)
            if not self.data:
                raise ConfigEntryNotReady(f"Unexpected error: {err}") from err
            raise UpdateFailed(f"Unexpected error: {err}") from err
