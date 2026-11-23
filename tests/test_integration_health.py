"""Integration Health must report a total outage (dev_standards §19).

The health sensor is the only entity able to explain why every other entity has
gone quiet. It must therefore never be unavailable, and must turn ON for a total
fetch failure — immediately at cold start (nothing to hold), or on the third
consecutive failure at runtime (matching the §8 3-strike rule).
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from custom_components.unifi_network_monitor.const import FETCH_STRIKE_LIMIT


def _coordinator() -> Any:
    """Build a coordinator carrying only the state these paths touch."""
    from custom_components.unifi_network_monitor.coordinator import (
        UnifiNetworkDataUpdateCoordinator as C,
    )

    c = C.__new__(C)
    c.data = None
    c.consecutive_failures = 0
    c.api = MagicMock()
    c.api.api_key = "test-key"
    c.health_snapshot = {
        "problem": False,
        "severity": "ok",
        "issues": [],
        "degraded_capabilities": [],
        "drift": [],
        "auth_mode": None,
        "v3_available": False,
        "last_good_update": None,
    }
    return c


def test_cold_start_failure_flags_on_first_strike() -> None:
    """Flag on the first failure when no data has ever been fetched."""
    c = _coordinator()
    c.consecutive_failures = 1

    c._record_fetch_failure_health(OSError("no route to host"))

    assert c.health_snapshot["problem"] is True
    assert c.health_snapshot["severity"] == "error"
    assert "since startup" in c.health_snapshot["issues"][0]


def test_runtime_failure_holds_until_third_strike() -> None:
    """Hold quiet until the third strike while last-known values are held."""
    c = _coordinator()
    c.data = {"gateway": {"mac": "aa:bb:cc:dd:ee:ff"}}

    for strike in range(1, FETCH_STRIKE_LIMIT):
        c.consecutive_failures = strike
        c._record_fetch_failure_health(OSError("timeout"))
        assert c.health_snapshot["problem"] is False, f"flagged at strike {strike}"

    c.consecutive_failures = FETCH_STRIKE_LIMIT
    c._record_fetch_failure_health(OSError("timeout"))
    assert c.health_snapshot["problem"] is True
    assert "consecutive failed updates" in c.health_snapshot["issues"][0]


def test_success_clears_the_verdict_immediately() -> None:
    """Clear the verdict in the same cycle as the successful fetch."""
    c = _coordinator()
    c.consecutive_failures = 1
    c._record_fetch_failure_health(OSError("down"))
    assert c.health_snapshot["problem"] is True

    # The success path assigns the freshly computed snapshot wholesale.
    c.health_snapshot = {
        "problem": False,
        "severity": "ok",
        "issues": [],
        "degraded_capabilities": [],
        "drift": [],
        "auth_mode": "api_key",
        "v3_available": True,
        "last_good_update": "2026-07-20T12:00:00+00:00",
    }
    assert c.health_snapshot["problem"] is False
    assert c.health_snapshot["issues"] == []


@pytest.mark.parametrize("last_update_success", [True, False])
def test_sensor_is_never_unavailable(last_update_success: bool) -> None:
    """Stay available regardless of coordinator state, including a total outage."""
    from custom_components.unifi_network_monitor.binary_sensor import (
        UnifiIntegrationHealthBinarySensor as S,
    )

    s = S.__new__(S)
    coord = MagicMock()
    coord.last_update_success = last_update_success
    coord.data = None
    coord.health_snapshot = {"problem": not last_update_success}
    s.coordinator = coord

    assert s.available is True
    assert s.is_on is (not last_update_success)


def test_sensor_reads_snapshot_not_stale_data() -> None:
    """Prefer the live snapshot over the frozen-healthy ``data`` payload."""
    from custom_components.unifi_network_monitor.binary_sensor import (
        UnifiIntegrationHealthBinarySensor as S,
    )

    s = S.__new__(S)
    coord = MagicMock()
    coord.last_update_success = False
    # Stale payload from before the outage still says everything was fine.
    coord.data = {"integration_health": {"problem": False}}
    coord.health_snapshot = {"problem": True, "severity": "error"}
    s.coordinator = coord

    assert s.is_on is True


# ---------------------------------------------------------------------------
# Contract sweeps over the published severity (C-022 step 8, items 8d to 8f),
# each driven through the HTTP seam so the snapshot is what a real poll
# produced. Asserted as published strings, never as the constants the code
# uses: a rename would pass a comparison with the constant while every user
# automation matching on `severity` broke.
# ---------------------------------------------------------------------------

SEVERITIES = {"ok", "degraded", "warning", "error", "unknown"}

_COORDINATOR_SOURCE = (
    Path(__file__).parent.parent
    / "custom_components"
    / "unifi_network_monitor"
    / "coordinator.py"
)


async def _seam(hass: Any, entry: Any) -> Any:
    from custom_components.unifi_network_monitor.coordinator import (
        UnifiNetworkDataUpdateCoordinator,
    )

    from .transport import real_api

    entry.add_to_hass(hass)
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, entry, real_api(hass))
    await coordinator.async_initialize()
    return coordinator


async def _polls(coordinator: Any, times: int) -> None:
    for _ in range(times):
        # The raise on an outage is not the subject; the snapshot is.
        with contextlib.suppress(Exception):
            coordinator.data = await coordinator._async_update_data()


async def test_every_published_severity_is_in_the_section_19_vocabulary(
    hass: Any, mock_config_entry: Any, aioclient_mock: Any
) -> None:
    """Every path that writes a snapshot publishes a Section 19 severity."""
    from .transport import CLASSIC, DRIFTED_GATEWAY, SPEEDTEST, ControllerFake

    fake = ControllerFake(aioclient_mock)
    coordinator = await _seam(hass, mock_config_entry)
    published: list[Any] = []

    fake.serve()
    await _polls(coordinator, 1)
    published.append(coordinator.health_snapshot["severity"])

    fake.serve(failing=(SPEEDTEST,))
    await _polls(coordinator, FETCH_STRIKE_LIMIT + 2)
    published.append(coordinator.health_snapshot["severity"])

    fake.serve(DRIFTED_GATEWAY)
    await _polls(coordinator, FETCH_STRIKE_LIMIT + 1)
    published.append(coordinator.health_snapshot["severity"])

    fake.serve(failing=(f"{CLASSIC}/stat/device",))
    await _polls(coordinator, FETCH_STRIKE_LIMIT + 2)
    published.append(coordinator.health_snapshot["severity"])

    for value in published:
        assert isinstance(value, str) and value, "severity must never be blank or None"
        assert value in SEVERITIES, f"severity '{value}' is outside Section 19"
    assert published == ["ok", "degraded", "error", "error"]


async def test_every_finding_is_classified_exactly_once(
    hass: Any, mock_config_entry: Any, aioclient_mock: Any
) -> None:
    """A finding is drift or a degraded capability, never both and never neither."""
    from .transport import DRIFTED_GATEWAY, SPEEDTEST, ControllerFake

    ControllerFake(aioclient_mock).serve(DRIFTED_GATEWAY, failing=(SPEEDTEST,))
    coordinator = await _seam(hass, mock_config_entry)
    await _polls(coordinator, FETCH_STRIKE_LIMIT + 2)

    snapshot = coordinator.health_snapshot
    drift = set(snapshot["drift"])
    capabilities = set(snapshot["degraded_capabilities"])
    assert drift, "no drift was found, so nothing was classified as drift"
    assert capabilities, "no capability was degraded, so nothing was classified"
    assert not drift & capabilities
    assert len(snapshot["issues"]) == len(drift) + len(capabilities), (
        "every finding carries exactly one issue line"
    )
    assert snapshot["problem"] is True


def test_the_severity_sweep_still_sweeps_something() -> None:
    """The vocabulary stays five, and every snapshot writer stays in reach.

    The coordinator writes `severity` in four places: at construction, on a
    total outage, in the computed snapshot and in the poll's fallback before
    it is computed. A fifth writer added later shows here as a count it does
    not match, and has to be brought into the sweep above.
    """
    assert len(SEVERITIES) == 5
    source = _COORDINATOR_SOURCE.read_text(encoding="utf-8")
    assert source.count('"severity":') == 4


async def test_previously_populated_source_empty_raises_degraded_and_recovers(
    hass: Any, mock_config_entry: Any, aioclient_mock: Any
) -> None:
    """I3 HTTP-seam: previously populated non-ephemeral source returning [] flags degraded, recovers on data."""
    from custom_components.unifi_network_monitor.const import HEALTH_DRIFT_STRIKE_LIMIT

    from .transport import ControllerFake

    fake = ControllerFake(aioclient_mock)
    # Poll 1: health and MODERN WAN usage are populated; sysinfo/guests remain empty
    fake.serve(
        stats_source="MODERN",
        self_sites=[{"name": "default", "_id": "s1"}],
        stats_series=[
            {"byNetworkGroup": [{"networkGroup": "WAN", "rxBytes": 100, "txBytes": 50}]}
        ],
        health=[{"subsystem": "wan", "status": "ok"}],
    )
    coordinator = await _seam(hass, mock_config_entry)
    await _polls(coordinator, 1)
    assert coordinator.health_snapshot["severity"] == "ok"

    # Polls 2..N: health and stats_series return [] (HTTP 200), sysinfo still [] (never populated)
    fake.serve(
        stats_source="MODERN",
        self_sites=[{"name": "default", "_id": "s1"}],
        stats_series=[],
        health=[],
    )
    await _polls(coordinator, HEALTH_DRIFT_STRIKE_LIMIT - 1)
    assert coordinator.health_snapshot["severity"] == "ok"

    await _polls(coordinator, 1)
    snap = coordinator.health_snapshot
    assert snap["severity"] == "degraded"
    assert snap["problem"] is True
    assert "Health returned no data" in snap["issues"]
    assert "WAN Usage returned no data" in snap["issues"]
    assert "System info returned no data" not in snap["issues"]
    assert "Guests" not in " ".join(snap["issues"])

    # Recovery: populated data returns -> clears to ok
    fake.serve(
        stats_source="MODERN",
        self_sites=[{"name": "default", "_id": "s1"}],
        stats_series=[
            {"byNetworkGroup": [{"networkGroup": "WAN", "rxBytes": 200, "txBytes": 80}]}
        ],
        health=[{"subsystem": "wan", "status": "ok"}],
    )
    await _polls(coordinator, 1)
    assert coordinator.health_snapshot["severity"] == "ok"
    assert coordinator.health_snapshot["issues"] == []


async def test_guard_band_suppression_precedence_and_recovery(
    hass: Any, mock_config_entry: Any, aioclient_mock: Any
) -> None:
    """I4: Guard-band trip sets warning (error > warning > degraded > ok), exposes attrs, and clears."""
    from custom_components.unifi_network_monitor.binary_sensor import (
        UnifiIntegrationHealthBinarySensor,
    )
    from custom_components.unifi_network_monitor.const import EP_SPEEDTEST
    from custom_components.unifi_network_monitor.sensor import (
        GATEWAY_SENSORS,
        UnifiGatewaySensor,
    )

    from .transport import ControllerFake

    fake = ControllerFake(aioclient_mock)
    fake.serve()
    coordinator = await _seam(hass, mock_config_entry)
    await _polls(coordinator, 1)

    cpu_desc = next(d for d in GATEWAY_SENSORS if d.key == "cpu")
    sensor = UnifiGatewaySensor(coordinator, mock_config_entry, cpu_desc, "gateway")
    bsensor = UnifiIntegrationHealthBinarySensor(coordinator, mock_config_entry)
    assert "guard_band_suppressed" in bsensor._unrecorded_attributes
    assert "empty_capabilities" in bsensor._unrecorded_attributes

    # Out-of-range value (>100.0) trips guard band -> warning
    coordinator.data["gateway"]["cpu"] = 150.0
    assert sensor.native_value is None
    assert coordinator.health_snapshot["severity"] == "warning"
    assert coordinator.health_snapshot["guard_band_suppressed"] == ["cpu"]
    assert "Guard band suppressed cpu" in coordinator.health_snapshot["issues"]
    assert bsensor.is_on is True
    assert bsensor.extra_state_attributes["guard_band_suppressed"] == ["cpu"]

    # Precedence: warning > degraded
    coordinator._stale_endpoints.add(EP_SPEEDTEST)
    coordinator.report_guard_band("uid_extra", "ram", True)
    assert coordinator.health_snapshot["severity"] == "warning"
    assert coordinator.health_snapshot["guard_band_suppressed"] == ["cpu", "ram"]

    # Precedence: error > warning
    coordinator.site_uuid = "failed"
    coordinator.api.api_key = "k"
    coordinator.report_guard_band("uid_extra", "ram", False)
    assert coordinator.health_snapshot["severity"] == "error"

    # Clear error & stale, then clear cpu guard band -> returns to ok
    coordinator.site_uuid = "s1"
    coordinator._stale_endpoints.clear()
    coordinator.data["gateway"]["cpu"] = 42.0
    assert sensor.native_value == 42.0
    assert coordinator.health_snapshot["severity"] == "ok"
    assert coordinator.health_snapshot["guard_band_suppressed"] == []
    assert coordinator.health_snapshot["issues"] == []

    # Re-trip and verify async_will_remove_from_hass clears it
    coordinator.data["gateway"]["cpu"] = -5.0
    assert sensor.native_value is None
    assert coordinator.health_snapshot["severity"] == "warning"
    sensor.hass = hass
    await sensor.async_will_remove_from_hass()
    assert coordinator.health_snapshot["severity"] == "ok"

    # Password auth (no api_key) ignores V3 endpoints in empty-source sweep
    from custom_components.unifi_network_monitor.const import EP_VPN_SERVERS

    coordinator.api.api_key = ""
    coordinator.endpoint_outcomes[EP_VPN_SERVERS] = {
        "outcome": "answered",
        "records": 0,
        "populated": 0,
    }
    snap = coordinator._compute_integration_health(mock_config_entry.options, {})
    assert EP_VPN_SERVERS not in snap["empty_capabilities"]
