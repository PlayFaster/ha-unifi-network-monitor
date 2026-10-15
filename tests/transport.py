"""A fake UniFi controller at the HTTP layer, for driving real polls in tests.

Every other suite in this project builds the coordinator over a `MagicMock`
standing in for `UnifiNetworkAPI`. That proves the coordinator handles what the
API object returns, and proves nothing about `api.py`, because none of it runs.

The seam is `aioclient_mock`, which `pytest-homeassistant-custom-component`
ships and which intercepts `async_get_clientsession`, the session
`async_setup_entry` hands the API. No dependency is added, and it is the seam
`zte_router_5g` and `wifi_ssid_monitor` use (`fault_injection_options.md` §3).

Pattern, from the `zte_router_5g` reference:

1. build the component's real API object over the mocked session
2. register the controller's answers for this cycle
3. drive `_async_update_data()`, assigning `coordinator.data` yourself, because
   the coordinator wrapper is not in play when you call it directly
4. re-arm with a changed answer for as many cycles as the test needs

Two things about this controller in particular:

**API-key mode needs no login.** The key travels as `X-API-Key` on every
request, so the fake answers the data endpoints only. The integration (`v1`)
endpoints exist only in that mode, and site resolution reads them first.

**Every response is an envelope.** The classic endpoints answer
`{"meta": {"rc": "ok"}, "data": [...]}`, and `api.py` reads `data`. An
endpoint left unregistered fails with `AssertionError` inside the mocker, which
`_request` reports as a connection failure; every endpoint the poll calls is
registered here so
a test's fault lands only where the test puts it.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

HOST = "192.168.1.1"
API_KEY = "test-api-key-abc123"
SITE = "default"
SITE_UUID = "88f7af54-98f8-306a-a1c7-c9349722b1f6"
BASE = f"https://{HOST}"
CLASSIC = f"{BASE}/proxy/network/api/s/{SITE}"
V2 = f"{BASE}/proxy/network/v2/api/site/{SITE}"
V1 = f"{BASE}/proxy/network/integration/v1/sites"
SPEEDTEST = f"{V2}/speedtest"

# A gateway that `_parse_gateway` reads in full, so a poll built on it takes the
# success path and every drift signal stays clear. Values are invented; the
# field names are the UDM Pro's, as `tests/test_gateway_parse_variants.py`
# records them.
GATEWAY: dict[str, Any] = {
    "mac": "aa:bb:cc:dd:ee:ff",
    "name": "Gateway",
    "model": "UDMPRO",
    "type": "udm",
    "state": 1,
    "uptime": 3600,
    "system-stats": {"cpu": "12.5", "mem": "40.0"},
    "temperatures": [{"type": "cpu", "value": 60.0}],
    "storage": [{"mount_point": "/persistent", "used": 50, "size": 200}],
    "wan1": {"ifname": "eth8", "is_uplink": True, "up": True, "latency": 9},
}

# The gateway as a firmware change that renamed its stats block would present
# it: the device still answers and is still selected, and none of `cpu`, `ram`
# or `uptime_secs` parses. That is the `gateway` drift signal.
DRIFTED_GATEWAY: dict[str, Any] = {
    key: value
    for key, value in GATEWAY.items()
    if key not in ("system-stats", "uptime")
} | {"system_stats_v2": {"cpu_pct": "12.5"}}

SITES: list[dict[str, Any]] = [{"id": SITE_UUID, "internalReference": SITE}]

# Classic endpoints answered by GET, and the ones answered by POST.
_CLASSIC_GET = (
    "stat/health",
    "stat/sysinfo",
    "rest/networkconf",
    "rest/setting",
    "stat/guest",
    "stat/sta",
    "rest/wlanconf",
)
_CLASSIC_POST = (
    "stat/report/daily.gw",
    "stat/report/monthly.gw",
    "stat/rogueap",
    "cmd/backup",
)
_V1_PER_SITE = ("wans", "vpn/servers", "vpn/site-to-site-tunnels", "firewall/policies")


def _envelope(data: list[Any]) -> dict[str, Any]:
    return {"meta": {"rc": "ok"}, "data": data}


class ControllerFake:
    """Registers controller responses, and can be re-armed between poll cycles."""

    def __init__(self, aioclient_mock: Any) -> None:
        """Take the mocker this fake writes its registrations into."""
        self._mock = aioclient_mock
        self._failing: tuple[str, ...] = ()

    def serve(
        self,
        gateway: dict[str, Any] | None = None,
        *,
        sites: list[dict[str, Any]] | None = None,
        failing: tuple[str, ...] = (),
    ) -> None:
        """Arm the controller for one or more cycles.

        Replaces every previous registration, so a test can change what the
        controller says between polls. Each URL in `failing` answers HTTP 500,
        which `api.py` reports as a connection failure for that endpoint alone.
        """
        self._mock.clear_requests()
        self._failing = failing
        device = deepcopy(GATEWAY if gateway is None else gateway)
        self._answer("get", f"{CLASSIC}/stat/device", _envelope([device]))
        for path in _CLASSIC_GET:
            self._answer("get", f"{CLASSIC}/{path}", _envelope([]))
        for path in _CLASSIC_POST:
            self._answer("post", f"{CLASSIC}/{path}", _envelope([]))
        self._answer("get", SPEEDTEST, [])
        self._answer("post", f"{V2}/system-log/all", {"data": []})
        self._answer("get", V1, _envelope(SITES if sites is None else sites))
        for path in _V1_PER_SITE:
            self._answer("get", f"{V1}/{SITE_UUID}/{path}", _envelope([]))

    def _answer(self, method: str, url: str, body: Any) -> None:
        if url in self._failing:
            getattr(self._mock, method)(url, status=500, json={"meta": {"rc": "error"}})
        else:
            getattr(self._mock, method)(url, json=body)


def real_api(hass: Any) -> Any:
    """Build the real `UnifiNetworkAPI` over Home Assistant's mocked session."""
    from custom_components.unifi_network_monitor.api import UnifiNetworkAPI
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    return UnifiNetworkAPI(
        async_get_clientsession(hass), HOST, api_key=API_KEY, site=SITE
    )
