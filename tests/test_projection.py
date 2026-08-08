"""Tests for the WAN Projected Usage sensors.

**item 26** of the August 2026 plan (§M Phase 1). Ported from ZTE, with the
plan's four constraints:

- **calendar month only** — UniFi's monthly counters roll on the 1st, so there
  is no router-reported clear day to discover and no fallback to explain;
- **WAN2 gated on the existing ``dual_wan_enabled``**, not a new toggle;
- **no ``state_class``** — a forecast is not a measurement and must never be
  fed to statistics or long-term storage;
- **confidence is an attribute, not an ``unknown``** — a projection on day one
  is weak, but a blank sensor reads as broken, so the number is always shown
  and the caveat rides alongside it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest
from homeassistant.util import dt as dt_util

from custom_components.unifi_network_monitor.const import (
    PROJECTION_CONFIDENCE_LOW,
    PROJECTION_CONFIDENCE_MEDIUM,
    PROJECTION_CREDIBILITY_DAYS,
    WAN2_KEYS,
)
from custom_components.unifi_network_monitor.helpers import (
    calendar_cycle_bounds,
    project_cycle_usage,
)

GB = 1024**3


# ---------------------------------------------------------------------------
# calendar_cycle_bounds
# ---------------------------------------------------------------------------


def test_cycle_bounds_spans_the_calendar_month() -> None:
    """The cycle runs from local midnight on the 1st to the next 1st."""
    now = dt_util.now().replace(
        year=2026, month=8, day=8, hour=13, minute=30, second=0, microsecond=0
    )
    start, end, length = calendar_cycle_bounds(now)

    assert (start.year, start.month, start.day) == (2026, 8, 1)
    assert (start.hour, start.minute, start.second, start.microsecond) == (0, 0, 0, 0)
    assert (end.year, end.month, end.day) == (2026, 9, 1)
    assert length == 31


def test_cycle_bounds_rolls_the_year_in_december() -> None:
    """December's cycle ends on 1 January of the next year."""
    now = dt_util.now().replace(year=2026, month=12, day=20, hour=9)
    start, end, length = calendar_cycle_bounds(now)

    assert (start.year, start.month) == (2026, 12)
    assert (end.year, end.month, end.day) == (2027, 1, 1)
    assert length == 31


@pytest.mark.parametrize(
    ("year", "month", "expected"),
    [(2026, 2, 28), (2028, 2, 29), (2026, 4, 30), (2026, 1, 31)],
)
def test_cycle_bounds_month_lengths(year: int, month: int, expected: int) -> None:
    """Cycle length is the real month length, leap years included."""
    now = dt_util.now().replace(year=year, month=month, day=5, hour=12)
    _start, _end, length = calendar_cycle_bounds(now)
    assert length == expected


def test_cycle_bounds_length_is_counted_in_calendar_days() -> None:
    """A month containing a DST change is still a whole number of days.

    Measured by date subtraction rather than by dividing seconds, so a 23- or
    25-hour day cannot turn a 31-day month into 30.96.
    """
    for month in range(1, 13):
        now = dt_util.now().replace(year=2026, month=month, day=15, hour=12)
        start, end, length = calendar_cycle_bounds(now)
        assert length == (end.date() - start.date()).days
        assert isinstance(length, int)


# ---------------------------------------------------------------------------
# project_cycle_usage
# ---------------------------------------------------------------------------


def test_projection_bounded_immediately_after_a_reset() -> None:
    """The naive `used / elapsed` blows up near zero; the floor prevents it.

    Half a gigabyte one second into the cycle must not project to a petabyte.
    """
    projected = project_cycle_usage(
        used=0.5 * GB,
        elapsed_days=1.0 / 86400,
        cycle_length_days=31,
        prior_rate=None,
        credibility_days=PROJECTION_CREDIBILITY_DAYS,
    )
    # Floored at one day: 0.5 GB/day over 31 days, not 43 200 GB/day.
    assert projected == pytest.approx(0.5 * GB + 31 * 0.5 * GB, rel=1e-6)


def test_projection_is_a_straight_run_rate_without_a_prior() -> None:
    """Ten days in at 2 GB/day over a 30-day month projects 60 GB."""
    projected = project_cycle_usage(
        used=20.0 * GB,
        elapsed_days=10.0,
        cycle_length_days=30,
        prior_rate=None,
        credibility_days=PROJECTION_CREDIBILITY_DAYS,
    )
    assert projected == pytest.approx(60.0 * GB, rel=1e-9)


def test_projection_blends_the_prior_into_the_remainder_only() -> None:
    """Observed bytes are never shrunk toward the prior — only the forecast is."""
    used = 20.0 * GB
    projected = project_cycle_usage(
        used=used,
        elapsed_days=10.0,
        cycle_length_days=30,
        prior_rate=1.0 * GB,
        credibility_days=PROJECTION_CREDIBILITY_DAYS,
    )
    # The blend can only move the unobserved 20 days, so the answer stays above
    # what has actually been used and below the pure run-rate figure.
    assert used < projected < 60.0 * GB


def test_prior_influence_decays_as_the_cycle_runs() -> None:
    """The prior's pull shrinks structurally — no clamp, no cliff."""

    def _gap(elapsed: float) -> float:
        run_rate = project_cycle_usage(
            used=2.0 * GB * elapsed,
            elapsed_days=elapsed,
            cycle_length_days=30,
            prior_rate=None,
            credibility_days=PROJECTION_CREDIBILITY_DAYS,
        )
        blended = project_cycle_usage(
            used=2.0 * GB * elapsed,
            elapsed_days=elapsed,
            cycle_length_days=30,
            prior_rate=1.0 * GB,
            credibility_days=PROJECTION_CREDIBILITY_DAYS,
        )
        return abs(run_rate - blended)

    assert _gap(2.0) > _gap(10.0) > _gap(20.0) > _gap(28.0)


def test_projection_past_the_end_of_the_cycle_is_just_what_was_used() -> None:
    """With no days remaining there is nothing left to forecast."""
    projected = project_cycle_usage(
        used=40.0 * GB,
        elapsed_days=31.0,
        cycle_length_days=31,
        prior_rate=None,
        credibility_days=PROJECTION_CREDIBILITY_DAYS,
    )
    assert projected == pytest.approx(40.0 * GB)


def test_projection_never_goes_backwards_past_the_cycle_end() -> None:
    """An elapsed count beyond the cycle clamps the remainder at zero."""
    projected = project_cycle_usage(
        used=40.0 * GB,
        elapsed_days=45.0,
        cycle_length_days=31,
        prior_rate=None,
        credibility_days=PROJECTION_CREDIBILITY_DAYS,
    )
    assert projected == pytest.approx(40.0 * GB)


def test_projection_treats_negative_elapsed_as_zero() -> None:
    """A clock skew backwards must not produce a negative forecast."""
    projected = project_cycle_usage(
        used=1.0 * GB,
        elapsed_days=-5.0,
        cycle_length_days=30,
        prior_rate=None,
        credibility_days=PROJECTION_CREDIBILITY_DAYS,
    )
    assert projected >= 1.0 * GB


# ---------------------------------------------------------------------------
# Coordinator output — value and attributes
# ---------------------------------------------------------------------------


def _gateway_with_month(rx: int | None, tx: int | None) -> dict[str, Any]:
    return {"wan1_month_rx": rx, "wan1_month_tx": tx}


def test_confidence_bands_are_ordered() -> None:
    """Low < medium < high, so the thresholds cannot be transposed."""
    assert 0.0 < PROJECTION_CONFIDENCE_LOW < PROJECTION_CONFIDENCE_MEDIUM < 1.0


async def test_coordinator_publishes_projection_and_attributes(
    hass: Any, mock_config_entry: Any
) -> None:
    """The gateway dict carries the projected bytes and its context."""
    from custom_components.unifi_network_monitor.coordinator import (
        build_usage_projection,
    )

    now = dt_util.now().replace(
        year=2026, month=8, day=11, hour=0, minute=0, second=0, microsecond=0
    )
    # 10 days elapsed of a 31-day August, 20 GB used.
    value, attrs = build_usage_projection(20 * GB, now)

    assert value is not None
    assert value > 20 * GB
    assert attrs["confidence"] in ("low", "medium", "high")
    assert attrs["cycle_day"] == "11 of 31"
    assert attrs["cycle_start"] == "2026-08-01"
    assert attrs["basis"] == "run_rate_only"


async def test_projection_is_none_without_usage(
    hass: Any, mock_config_entry: Any
) -> None:
    """No monthly counter means no projection — and no invented zero."""
    from custom_components.unifi_network_monitor.coordinator import (
        build_usage_projection,
    )

    value, attrs = build_usage_projection(None, dt_util.now())
    assert value is None
    assert attrs == {}


async def test_projection_confidence_is_low_on_day_one(
    hass: Any, mock_config_entry: Any
) -> None:
    """Day one still publishes a number, flagged ``low`` rather than blank."""
    from custom_components.unifi_network_monitor.coordinator import (
        build_usage_projection,
    )

    now = dt_util.now().replace(year=2026, month=8, day=1, hour=6)
    value, attrs = build_usage_projection(1 * GB, now)

    assert value is not None
    assert attrs["confidence"] == "low"


async def test_projection_confidence_is_high_late_in_the_cycle(
    hass: Any, mock_config_entry: Any
) -> None:
    """Three weeks of observed data is a strong basis."""
    from custom_components.unifi_network_monitor.coordinator import (
        build_usage_projection,
    )

    now = dt_util.now().replace(year=2026, month=8, day=22, hour=12)
    _value, attrs = build_usage_projection(50 * GB, now)

    assert attrs["confidence"] == "high"


# ---------------------------------------------------------------------------
# Entity wiring
# ---------------------------------------------------------------------------


def test_projection_sensors_declare_no_state_class() -> None:
    """A forecast must never reach statistics or long-term storage."""
    from custom_components.unifi_network_monitor.sensor import GATEWAY_SENSORS

    projections = [d for d in GATEWAY_SENSORS if d.key.endswith("_month_projected")]
    assert len(projections) == 2
    for desc in projections:
        assert desc.state_class is None, desc.key


def test_projection_sensor_names_keep_wan_and_avoid_data() -> None:
    """Names stay WAN1/WAN2 and must not contain "Data"."""
    import json
    from pathlib import Path

    strings = json.loads(
        (
            Path(__file__).parent.parent
            / "custom_components"
            / "unifi_network_monitor"
            / "strings.json"
        ).read_text(encoding="utf-8")
    )
    names = strings["entity"]["sensor"]
    for wan in ("wan1", "wan2"):
        name = names[f"gateway_{wan}_month_projected"]["name"]
        assert wan.upper() in name
        assert "data" not in name.lower()


def test_wan2_projection_is_gated_on_dual_wan() -> None:
    """The WAN2 projection is removed with the rest of WAN2, not separately."""
    assert "wan2_month_projected" in WAN2_KEYS


def test_projection_keys_have_a_guard_band() -> None:
    """Usage cannot be negative; the projection is bounded below like the rest."""
    from custom_components.unifi_network_monitor.sensor import GATEWAY_SENSORS

    for desc in GATEWAY_SENSORS:
        if desc.key.endswith("_month_projected"):
            assert desc.min_limit == 0.0


def test_projection_value_fn_reads_the_coordinator_key() -> None:
    """The sensor reads the coordinator's computed value; it does not recompute."""
    from custom_components.unifi_network_monitor.sensor import GATEWAY_SENSORS

    for desc in GATEWAY_SENSORS:
        if desc.key == "wan1_month_projected":
            assert desc.value_fn({"wan1_month_projected": 123}) == 123
            assert desc.value_fn({}) is None


def test_projection_attributes_surface_on_the_entity() -> None:
    """The confidence context is published as attributes on the sensor."""
    from unittest.mock import MagicMock

    from custom_components.unifi_network_monitor.sensor import (
        GATEWAY_SENSORS,
        UnifiGatewaySensor,
    )

    desc = next(d for d in GATEWAY_SENSORS if d.key == "wan1_month_projected")
    coordinator = MagicMock()
    coordinator.data = {
        "gateway": {
            "wan1_month_projected": 999,
            "wan1_month_projected_attrs": {"confidence": "medium"},
        }
    }
    coordinator.async_add_listener = MagicMock()
    entry = MagicMock()
    entry.unique_id = "aa:bb:cc:dd:ee:ff"

    sensor = UnifiGatewaySensor(coordinator, entry, desc, "uid_wan1_month_projected")
    attrs = sensor.extra_state_attributes or {}
    assert attrs.get("confidence") == "medium"


def test_cycle_bounds_uses_local_time_not_utc() -> None:
    """Boundaries are local midnight — a UTC computation shifts the reset day."""
    now = dt_util.now().replace(year=2026, month=8, day=8, hour=1)
    start, _end, _length = calendar_cycle_bounds(now)
    assert start.tzinfo == now.tzinfo
    assert isinstance(start, datetime)


# ---------------------------------------------------------------------------
# Mutation-driven: gaps found by the 2026-08-08 mutmut run
# ---------------------------------------------------------------------------


def test_cycle_start_is_exactly_midnight_whatever_time_it_is_called() -> None:
    """Seconds and microseconds must be zeroed, not inherited from ``now``.

    Found by mutation: removing `second=0` or `microsecond=0` from the
    `.replace()` left every test green, because they all happened to pass a
    ``now`` that was already zeroed on those fields. The boundary the function
    exists to compute is *exactly* local midnight — carry the caller's seconds
    into it and `cycle_start` is published wrong, and `elapsed_days` is off by
    up to a minute in a figure that divides by it.
    """
    now = dt_util.now().replace(
        year=2026, month=8, day=8, hour=13, minute=47, second=37, microsecond=123456
    )
    start, end, _length = calendar_cycle_bounds(now)

    assert (start.hour, start.minute, start.second, start.microsecond) == (0, 0, 0, 0)
    assert (end.hour, end.minute, end.second, end.microsecond) == (0, 0, 0, 0)


def test_the_blend_produces_an_exact_figure_not_merely_a_plausible_one() -> None:
    """Pin the blend arithmetic to a computed value, not a range.

    Found by mutation: `+` → `-` and both `*` → `/` in
    ``weight * current_rate + (1.0 - weight) * prior_rate`` all survived,
    because the existing tests assert only that the answer falls between the
    used total and the pure run-rate figure. Three different formulas satisfy
    that range. This is the arithmetic the whole projection rests on, so it is
    worth one exact assertion.

    Worked by hand: weight = 10 / (10 + 3) = 0.769230…; current_rate = 2 GB/day;
    blended rate = 0.769230… x 2 + 0.230769… x 1 = 1.769230… GB/day; over the
    20 remaining days that is 35.384… GB on top of the 20 GB already used.
    """
    weight = 10.0 / (10.0 + PROJECTION_CREDIBILITY_DAYS)
    expected_rate = weight * (2.0 * GB) + (1.0 - weight) * (1.0 * GB)
    expected = 20.0 * GB + 20.0 * expected_rate

    projected = project_cycle_usage(
        used=20.0 * GB,
        elapsed_days=10.0,
        cycle_length_days=30,
        prior_rate=1.0 * GB,
        credibility_days=PROJECTION_CREDIBILITY_DAYS,
    )

    assert projected == pytest.approx(expected, rel=1e-12)
    # And it is genuinely distinct from the un-blended figure, so the test
    # cannot pass by the prior being ignored.
    assert projected != pytest.approx(60.0 * GB, rel=1e-6)
