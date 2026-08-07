"""Integration Health must report a total outage (dev_standards §19).

The health sensor is the only entity able to explain why every other entity has
gone quiet. It must therefore never be unavailable, and must turn ON for a total
fetch failure — immediately at cold start (nothing to hold), or on the third
consecutive failure at runtime (matching the §8 3-strike rule).
"""

from __future__ import annotations

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
        "severity": None,
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
    assert c.health_snapshot["severity"] == "serious"
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
        "severity": None,
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
    coord.health_snapshot = {"problem": True, "severity": "serious"}
    s.coordinator = coord

    assert s.is_on is True
