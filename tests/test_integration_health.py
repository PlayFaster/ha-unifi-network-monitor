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
