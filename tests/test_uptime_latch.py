"""Boot-time latch for the link uptime counters: drift, startup tests, guards.

Ported from `zte_router_5g` `tests/test_uptime_latch.py`, the reference for
`fix_uptime_timestamp_gets_stuck.md` §3, under the same names. The latch under
test here is the `www` link counter, UniFi's equivalent of the router's system
counter; the WAN latches run the same code. Device boot times carry no latch and
are tested at the end.

The cases are driven by a simulated counter that advances at a configurable
rate, so "no false alarm across thirty days" is something the suite can assert.
Everything here is offline. The design and the constants are in
`.shared/info/uptime_timestamp/uptime_drift_analyzed.md`.
"""

from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.unifi_network_monitor.const import (
    DOMAIN,
    DRIFT_ACCUMULATOR_CAP,
    DRIFT_MIN_ACCUMULATED,
    MAX_DRIFT,
    UPTIME_WRITE_INTERVAL,
)
from custom_components.unifi_network_monitor.coordinator import (
    UnifiNetworkDataUpdateCoordinator,
)
from homeassistant.core import HomeAssistant

from .conftest import MOCK_MAC

NOW = datetime(2026, 9, 1, 12, 0, 0, tzinfo=UTC)
POLL = timedelta(minutes=16)
ZTE_RATE = 0.0434


def _entry(**data) -> MockConfigEntry:
    """Return a config entry; a `boot_time` keyword anchors the `www` latch."""
    boot = data.pop("boot_time", None)
    legacy = data.pop("last_uptime", None)
    if boot is not None or legacy is not None:
        record = data.setdefault("boot_times", {}).setdefault("www", {})
        if boot is not None:
            record["boot_time"] = boot
        if legacy is not None:
            # The v1.1.0 record shape, carrying the frozen counter.
            record["last_uptime"] = legacy
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_MAC,
        title="UniFi Network",
        data={"mac": MOCK_MAC, **data},
        options={"host": "192.0.2.1", "api_key": "test-key"},
    )


def _coordinator(hass: HomeAssistant, entry: MockConfigEntry):
    """Return a coordinator with a mocked API and a mocked store."""
    entry.add_to_hass(hass)
    api = MagicMock()
    api.api_key = "test-key"
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, entry, api)
    coordinator._store = MagicMock()
    return coordinator


def _poll(coordinator, seconds, now) -> None:
    """Feed one counter reading through the latch at a pinned clock."""
    with patch(
        "custom_components.unifi_network_monitor.uptime.dt_util.now", return_value=now
    ):
        coordinator._apply_uptime_readings(
            ((coordinator._primary_latch, int(seconds)),)
        )


class Router:
    """A router whose counter advances at `rate` slower than wall time.

    Positive `rate` is a slow counter, which is what real hardware does here.
    Negative is a counter running fast, which has never been measured but is not
    ruled out.
    """

    def __init__(self, rate: float = ZTE_RATE, uptime: float = 0.0) -> None:
        """Start at `uptime` seconds, losing `rate` of every second thereafter."""
        self.rate = rate
        self.counter = uptime

    def advance(self, seconds: float) -> None:
        """Advance the counter by what this router would count in that wall time."""
        self.counter += seconds * (1.0 - self.rate)

    def reboot(self) -> None:
        """Reset the counter, as a power cycle does."""
        self.counter = 0.0


def _run(coordinator, router: Router, *, start, polls: int, interval=POLL):
    """Poll a simulated router repeatedly and return the final clock."""
    now = start
    for _ in range(polls):
        _poll(coordinator, router.counter, now)
        now += interval
        router.advance(interval.total_seconds())
    return now


# ---------------------------------------------------------------------------
# Drift measurement
# ---------------------------------------------------------------------------


# Rates deliberately span PLAUSIBILITY_TOLERANCE. A suite that stopped at the
# measured 4.34% passed a build in which any device drifting past the
# tolerance re-latched on every poll, because the anchor was not corrected
# for drift and the observed ratio therefore sat a full `rate` from the
# predicted one.
@pytest.mark.parametrize("rate", [0.0, ZTE_RATE, 0.08, 0.12, -0.02])
@pytest.mark.asyncio
async def test_the_measured_rate_converges_on_the_real_one(hass, rate):
    """The estimate is what replaces a universal constant, so it must be right."""
    router = Router(rate=rate, uptime=100_000)
    boot = NOW - timedelta(seconds=router.counter / (1 - rate))
    coordinator = _coordinator(hass, _entry(boot_time=boot.isoformat()))

    _run(coordinator, router, start=NOW, polls=40)

    assert coordinator._drift_rate(coordinator._primary_latch) == pytest.approx(
        rate, abs=0.001
    )
    assert coordinator._primary_latch.drift_interval_count == 39


@pytest.mark.asyncio
async def test_the_rate_is_withheld_until_enough_has_accumulated(hass):
    """Below the minimum there is no estimate, and no division by zero."""
    coordinator = _coordinator(hass, _entry())
    assert coordinator._primary_latch.drift_sum_wall == 0
    assert coordinator._drift_rate(coordinator._primary_latch) is None, (
        "a fresh install must not divide"
    )

    router = Router(uptime=50_000)
    _run(coordinator, router, start=NOW, polls=3)

    assert coordinator._primary_latch.drift_sum_wall < DRIFT_MIN_ACCUMULATED
    assert coordinator._drift_rate(coordinator._primary_latch) is None

    _run(coordinator, router, start=NOW + POLL * 3, polls=6)
    assert coordinator._drift_rate(coordinator._primary_latch) is not None


@pytest.mark.asyncio
async def test_short_and_negative_intervals_are_excluded(hass):
    """Quantization dominates a short interval; a drop is a reboot, not drift."""
    coordinator = _coordinator(hass, _entry())
    coordinator._primary_latch.startup_reconciled = True

    _poll(coordinator, 10_000, NOW)
    _poll(coordinator, 10_030, NOW + timedelta(seconds=30))
    assert coordinator._primary_latch.drift_interval_count == 0, (
        "sub-60 s interval counted"
    )

    _poll(coordinator, 20, NOW + timedelta(seconds=60))
    assert coordinator._primary_latch.drift_interval_count == 0, (
        "a reboot polluted the rate"
    )


@pytest.mark.asyncio
async def test_a_runaway_sample_cannot_move_the_rate_past_the_clamp(hass):
    """An unbounded high rate would suppress detection; the clamp prevents it."""
    coordinator = _coordinator(hass, _entry())
    coordinator._primary_latch.drift_sum_wall = 100_000.0
    coordinator._primary_latch.drift_sum_counter = 1_000.0  # 99% "loss"

    assert coordinator._drift_rate(coordinator._primary_latch) == MAX_DRIFT

    coordinator._primary_latch.drift_sum_counter = 200_000.0  # counter twice wall time
    assert coordinator._drift_rate(coordinator._primary_latch) == -MAX_DRIFT


@pytest.mark.asyncio
async def test_the_cap_lets_the_estimate_follow_a_firmware_fix(hass):
    """A counter that stops drifting must not be outvoted by its own history."""
    coordinator = _coordinator(hass, _entry())
    coordinator._primary_latch.startup_reconciled = True

    drifting = Router(rate=ZTE_RATE, uptime=0)
    now = _run(coordinator, drifting, start=NOW, polls=200, interval=timedelta(hours=6))
    assert coordinator._drift_rate(coordinator._primary_latch) == pytest.approx(
        ZTE_RATE, abs=0.002
    )
    assert coordinator._primary_latch.drift_sum_wall <= DRIFT_ACCUMULATOR_CAP

    fixed = Router(rate=0.0, uptime=drifting.counter)
    _run(coordinator, fixed, start=now, polls=200, interval=timedelta(hours=6))

    assert coordinator._drift_rate(coordinator._primary_latch) < ZTE_RATE / 2, (
        "the cap did not let it move"
    )


# ---------------------------------------------------------------------------
# No false alarms — the failure this redesign exists to remove
# ---------------------------------------------------------------------------


# Rates deliberately span PLAUSIBILITY_TOLERANCE. A suite that stopped at the
# measured 4.34% passed a build in which any device drifting past the
# tolerance re-latched on every poll, because the anchor was not corrected
# for drift and the observed ratio therefore sat a full `rate` from the
# predicted one.
@pytest.mark.parametrize("rate", [0.0, ZTE_RATE, 0.08, 0.12, -0.02])
@pytest.mark.asyncio
async def test_a_running_router_never_moves_the_timestamp(hass, rate):
    """Thirty days of polling at any believable rate, with no reboot."""
    router = Router(rate=rate, uptime=3600)
    boot = NOW - timedelta(seconds=3600 / (1 - rate))
    coordinator = _coordinator(hass, _entry(boot_time=boot.isoformat()))

    _poll(coordinator, router.counter, NOW)
    router.advance(POLL.total_seconds())
    latched = coordinator._primary_latch.boot_time
    assert latched is not None

    _run(coordinator, router, start=NOW + POLL, polls=2700)

    assert coordinator._primary_latch.boot_time == latched, (
        f"timestamp moved at rate {rate}"
    )


@pytest.mark.asyncio
async def test_restarts_across_a_month_never_move_the_timestamp(hass):
    """The original defect surfaced on restarts, so restart repeatedly.

    A new coordinator each time, as a real restart gives, carrying the store
    record forward exactly as the real one would.
    """
    router = Router(rate=ZTE_RATE, uptime=3600)
    entry = _entry(boot_time=(NOW - timedelta(seconds=3760)).isoformat())
    carried: dict = {}
    now = NOW
    latched = None

    for _ in range(30):
        coordinator = _coordinator(hass, entry)
        coordinator._primary_latch.stored_counter = carried.get("counter")
        coordinator._primary_latch.stored_written_at = carried.get("written_at")
        coordinator._primary_latch.drift_sum_wall = carried.get("wall", 0.0)
        coordinator._primary_latch.drift_sum_counter = carried.get("counter_sum", 0.0)

        now = _run(coordinator, router, start=now, polls=20)

        if latched is None:
            latched = coordinator._primary_latch.boot_time
        assert coordinator._primary_latch.boot_time == latched, (
            "a restart moved the timestamp"
        )

        carried = {
            "counter": coordinator._primary_latch.stored_counter,
            "written_at": coordinator._primary_latch.stored_written_at,
            "wall": coordinator._primary_latch.drift_sum_wall,
            "counter_sum": coordinator._primary_latch.drift_sum_counter,
        }
        now += timedelta(hours=8)
        router.advance(8 * 3600)


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_counter_drop_is_a_reboot_unconditionally(hass):
    """The one signal needing no clock and no assumption. Nothing vetoes it."""
    router = Router(uptime=500_000)
    boot = NOW - timedelta(seconds=520_000)
    coordinator = _coordinator(hass, _entry(boot_time=boot.isoformat()))
    coordinator._primary_latch.startup_reconciled = True
    coordinator._primary_latch.boot_time = boot
    coordinator._primary_latch.last_counter = 500_000

    _poll(coordinator, 20, NOW)

    assert coordinator._primary_latch.boot_time == NOW - timedelta(seconds=20)
    assert (
        coordinator.entry.data["boot_times"]["www"]["boot_time"]
        == coordinator._primary_latch.boot_time.isoformat()
    )


@pytest.mark.asyncio
async def test_a_reboot_inside_an_offline_gap_is_detected(hass):
    """Failure Mode 1: the shortfall test is what sees it."""
    boot = NOW - timedelta(days=6)
    coordinator = _coordinator(hass, _entry(boot_time=boot.isoformat()))
    coordinator._primary_latch.stored_counter = 432_000
    coordinator._primary_latch.stored_written_at = NOW - timedelta(days=1)
    coordinator._primary_latch.drift_sum_wall = 200_000.0
    coordinator._primary_latch.drift_sum_counter = 200_000.0 * (1 - ZTE_RATE)

    # Home Assistant was away a day; the router rebooted eight hours ago.
    _poll(coordinator, 28_800, NOW)

    # The anchor is corrected for the counter's drift: 28,800 counted seconds
    # represent 28,800 / (1 - rate) of wall time, so `now - counter` would sit
    # twenty minutes late.
    expected = NOW - timedelta(seconds=28_800 / (1 - ZTE_RATE))
    assert coordinator._primary_latch.boot_time == expected.replace(microsecond=0)
    assert coordinator._primary_latch.startup_reconciled


@pytest.mark.asyncio
async def test_a_simultaneous_cold_start_is_detected(hass):
    """Failure Mode 2: mains restored, both devices boot together."""
    boot = NOW - timedelta(days=5)
    coordinator = _coordinator(hass, _entry(boot_time=boot.isoformat()))
    coordinator._primary_latch.stored_counter = 400_000
    coordinator._primary_latch.stored_written_at = NOW - timedelta(minutes=30)

    _poll(coordinator, 45, NOW)

    assert coordinator._primary_latch.boot_time == NOW - timedelta(seconds=45)


@pytest.mark.asyncio
async def test_a_clean_restart_preserves_the_timestamp_exactly(hass):
    """No reboot, so the stored instant is kept — not recomputed."""
    boot = NOW - timedelta(days=5)
    coordinator = _coordinator(hass, _entry(boot_time=boot.isoformat()))
    coordinator._primary_latch.stored_counter = 400_000
    coordinator._primary_latch.stored_written_at = NOW - timedelta(minutes=20)

    _poll(coordinator, 400_000 + 1200 * (1 - ZTE_RATE), NOW)

    assert coordinator._primary_latch.boot_time == boot
    assert coordinator._primary_latch.startup_reconciled


@pytest.mark.asyncio
async def test_the_plausibility_backstop_catches_a_stale_anchor(hass):
    """The failure the whole design exists to prevent, caught on any poll."""
    stale = NOW - timedelta(days=24)
    coordinator = _coordinator(hass, _entry(boot_time=stale.isoformat()))
    coordinator._primary_latch.startup_reconciled = True
    coordinator._primary_latch.boot_time = stale
    coordinator._primary_latch.drift_sum_wall = 200_000.0
    coordinator._primary_latch.drift_sum_counter = 200_000.0 * (1 - ZTE_RATE)

    # Four days of counter against twenty-four days of anchor.
    _poll(coordinator, 4 * 86_400, NOW)

    expected = NOW - timedelta(seconds=4 * 86_400 / (1 - ZTE_RATE))
    assert coordinator._primary_latch.boot_time == expected.replace(microsecond=0)


@pytest.mark.asyncio
async def test_a_backward_candidate_is_never_treated_as_a_reboot(hass):
    """A reboot moves the boot instant forward. A backward move cannot be one."""
    boot = NOW - timedelta(hours=1)
    coordinator = _coordinator(hass, _entry(boot_time=boot.isoformat()))
    coordinator._primary_latch.startup_reconciled = True
    coordinator._primary_latch.boot_time = boot
    coordinator._primary_latch.drift_sum_wall = 200_000.0
    coordinator._primary_latch.drift_sum_counter = 200_000.0 * (1 - ZTE_RATE)

    # A counter far larger than the anchor allows: the candidate lands earlier.
    _poll(coordinator, 10 * 86_400, NOW)

    assert coordinator._primary_latch.boot_time == boot


# ---------------------------------------------------------------------------
# Cold start
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cold_start_retains_a_healthy_anchor(hass):
    """No store and no rate: the wide bound must not fire on a good anchor."""
    boot = NOW - timedelta(days=4)
    counter = 4 * 86_400 * (1 - ZTE_RATE)
    coordinator = _coordinator(hass, _entry(boot_time=boot.isoformat()))

    _poll(coordinator, counter, NOW)

    assert coordinator._primary_latch.boot_time == boot
    assert coordinator._primary_latch.startup_reconciled


@pytest.mark.asyncio
async def test_cold_start_relatches_a_stale_anchor(hass):
    """The upgrade case: a reboot happened while nothing was watching."""
    coordinator = _coordinator(
        hass, _entry(boot_time=(NOW - timedelta(days=24)).isoformat())
    )

    _poll(coordinator, 4 * 86_400, NOW)

    assert coordinator._primary_latch.boot_time == NOW - timedelta(days=4)


@pytest.mark.asyncio
async def test_a_fresh_install_latches_unconditionally(hass):
    """Nothing stored at all, so there is nothing to preserve."""
    coordinator = _coordinator(hass, _entry())

    _poll(coordinator, 3_600, NOW)

    assert coordinator._primary_latch.boot_time == NOW - timedelta(seconds=3_600)


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_an_unset_clock_defers_rather_than_latching(hass):
    """A host with no battery-backed clock starts in 1970."""
    boot = NOW - timedelta(days=5)
    coordinator = _coordinator(hass, _entry(boot_time=boot.isoformat()))

    _poll(coordinator, 3_600, datetime(1970, 1, 1, 0, 5, tzinfo=UTC))
    assert coordinator._primary_latch.boot_time == boot
    assert not coordinator._primary_latch.startup_reconciled, "deferred, not skipped"

    _poll(coordinator, 3_600, NOW)
    assert coordinator._primary_latch.startup_reconciled


@pytest.mark.asyncio
async def test_an_implausible_counter_is_rejected(hass):
    """Believing it would write a boot instant decades adrift."""
    boot = NOW - timedelta(days=5)
    coordinator = _coordinator(hass, _entry(boot_time=boot.isoformat()))

    _poll(coordinator, 20 * 365 * 86_400, NOW)

    assert coordinator._primary_latch.boot_time == boot
    assert not coordinator._primary_latch.startup_reconciled


@pytest.mark.parametrize("bad", [None, -1, "abc", ""])
@pytest.mark.asyncio
async def test_a_bad_reading_leaves_the_latch_alone(hass, bad):
    """The pre-existing guard, retained deliberately."""
    boot = NOW - timedelta(days=5)
    coordinator = _coordinator(hass, _entry(boot_time=boot.isoformat()))
    with patch(
        "custom_components.unifi_network_monitor.uptime.dt_util.now", return_value=NOW
    ):
        published = coordinator.link_boot_time("www", bad)

    assert published == boot
    assert not coordinator._primary_latch.startup_reconciled


@pytest.mark.parametrize("value", ["2026-08-01T10:00:00", "not a datetime", ""])
@pytest.mark.asyncio
async def test_a_naive_or_unparsable_anchor_is_treated_as_absent(hass, value):
    """Mixing naive and aware raises; treat it as no stored value."""
    coordinator = _coordinator(hass, _entry(boot_time=value))
    assert coordinator._primary_latch.boot_time is None

    _poll(coordinator, 3_600, NOW)

    assert coordinator._primary_latch.boot_time == NOW - timedelta(seconds=3_600)


@pytest.mark.asyncio
async def test_a_small_backward_step_is_logged_not_absorbed(hass, caplog):
    """Nothing establishes that this counter never steps back. Say so if it does."""
    coordinator = _coordinator(hass, _entry())
    coordinator._primary_latch.startup_reconciled = True
    coordinator._primary_latch.boot_time = NOW - timedelta(hours=2)
    coordinator._primary_latch.last_counter = 7_200

    _poll(coordinator, 7_190, NOW)

    assert coordinator._primary_latch.boot_time == NOW - timedelta(hours=2), (
        "10 s is not a reboot"
    )
    assert "stepped back" in caplog.text


@pytest.mark.asyncio
async def test_a_move_without_a_counter_drop_is_flagged(hass, caplog):
    """The signature of this bug class, made visible from the log alone."""
    coordinator = _coordinator(
        hass, _entry(boot_time=(NOW - timedelta(days=24)).isoformat())
    )
    coordinator._primary_latch.startup_reconciled = True
    coordinator._primary_latch.boot_time = NOW - timedelta(days=24)
    coordinator._primary_latch.last_counter = 4 * 86_400
    coordinator._primary_latch.drift_sum_wall = 200_000.0
    coordinator._primary_latch.drift_sum_counter = 200_000.0 * (1 - ZTE_RATE)

    _poll(coordinator, 4 * 86_400 + 900, NOW)

    assert "without a counter drop" in caplog.text


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_store_record_carries_the_accumulators(hass):
    """What a restart needs: the counter, when it was written, and the rate."""
    coordinator = _coordinator(hass, _entry())
    coordinator._primary_latch.startup_reconciled = True
    coordinator._primary_latch.drift_sum_wall = 100_000.0
    coordinator._primary_latch.drift_sum_counter = 95_660.0
    coordinator._primary_latch.drift_rate_min = 0.0424
    coordinator._primary_latch.drift_rate_max = 0.0473
    coordinator._primary_latch.drift_interval_count = 15

    _poll(coordinator, 43_359, NOW)

    record = coordinator._store.async_delay_save.call_args.args[0]()["last_www_uptime"]
    assert record["last_uptime"] == 43_359
    assert record["written_at"] == NOW.isoformat()
    assert record["sum_wall"] == pytest.approx(100_000.0, abs=1000)
    assert record["rate_min"] == pytest.approx(0.0424)
    assert record["interval_count"] >= 15


@pytest.mark.parametrize(
    "payload",
    [None, "junk", {}, {"last_uptime": "nope"}, {"written_at": "2026-09-01T12:00:00"}],
)
@pytest.mark.asyncio
async def test_an_unusable_store_record_falls_back_cleanly(hass, payload):
    """A naive `written_at` cannot date the gap, so the record is not usable."""
    coordinator = _coordinator(hass, _entry())
    with patch("custom_components.unifi_network_monitor.uptime.Store") as store_cls:
        store_cls.return_value.async_load = AsyncMock(return_value=payload)
        await coordinator.async_load_stored_uptime()

    assert coordinator._primary_latch.stored_written_at is None


@pytest.mark.parametrize(
    "failure", [ValueError("corrupt"), OSError("unreadable"), RuntimeError("odd")]
)
@pytest.mark.asyncio
async def test_a_failing_store_load_never_reaches_setup(hass, failure):
    """No storage fault may fail entry setup: the store is a cross-check."""
    coordinator = _coordinator(hass, _entry())
    with patch("custom_components.unifi_network_monitor.uptime.Store") as store_cls:
        store_cls.return_value.async_load = AsyncMock(side_effect=failure)
        await coordinator.async_load_stored_uptime()

    assert coordinator._primary_latch.stored_counter is None


@pytest.mark.asyncio
async def test_a_full_store_record_is_read_back(hass):
    """Fields are additive, so an older block without them still loads.

    The entry carries an anchor: since 3.4.2-dev8 a stored counter without one
    is dropped, which `test_uptime_upgrade_paths.py` covers.
    """
    coordinator = _coordinator(hass, _entry(boot_time="2026-09-01T00:00:00+00:00"))
    block = {
        "last_uptime": 43_359,
        "written_at": "2026-09-01T15:10:00+00:00",
        "sum_wall": 378_494.2,
        "sum_counter": 362_079.5,
        "rate_min": 0.0424,
        "rate_max": 0.0473,
        "interval_count": 15,
    }
    with patch("custom_components.unifi_network_monitor.uptime.Store") as store_cls:
        store_cls.return_value.async_load = AsyncMock(
            return_value={"last_www_uptime": block}
        )
        await coordinator.async_load_stored_uptime()

    assert coordinator._primary_latch.stored_counter == 43_359
    assert coordinator._primary_latch.stored_written_at == datetime(
        2026, 9, 1, 15, 10, tzinfo=UTC
    )
    assert coordinator._drift_rate(coordinator._primary_latch) == pytest.approx(
        0.0434, abs=0.0005
    )


@pytest.mark.asyncio
async def test_the_store_is_keyed_to_the_entry(hass):
    """One store per entry, so two routers cannot overwrite each other."""
    entry = _entry()
    coordinator = _coordinator(hass, entry)
    with patch("custom_components.unifi_network_monitor.uptime.Store") as store_cls:
        store_cls.return_value.async_load = AsyncMock(return_value=None)
        await coordinator.async_load_stored_uptime()

    assert entry.entry_id in store_cls.call_args.args[2]


@pytest.mark.asyncio
async def test_the_counter_is_flushed_on_the_interval_not_every_poll(hass):
    """Write economy: the accumulators update in memory, not on disk."""
    coordinator = _coordinator(hass, _entry())
    coordinator._primary_latch.startup_reconciled = True
    coordinator._primary_latch.boot_time = NOW - timedelta(hours=1)

    _poll(coordinator, 3_600, NOW)
    first = coordinator._store.async_delay_save.call_count

    _poll(coordinator, 3_660, NOW + timedelta(minutes=1))
    assert coordinator._store.async_delay_save.call_count == first

    _poll(coordinator, 5_000, NOW + UPTIME_WRITE_INTERVAL)
    assert coordinator._store.async_delay_save.call_count == first + 1


@pytest.mark.asyncio
async def test_a_latch_drops_the_legacy_counter_from_entry_data(hass):
    """The key that caused the original defect must not survive the fix."""
    coordinator = _coordinator(hass, _entry(last_uptime=60))
    coordinator._primary_latch.startup_reconciled = True
    coordinator._primary_latch.boot_time = NOW - timedelta(days=5)
    coordinator._primary_latch.last_counter = 400_000

    _poll(coordinator, 45, NOW)

    record = coordinator.entry.data["boot_times"]["www"]
    assert "last_uptime" not in record
    assert "boot_time" in record


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_drift_picture_is_published(hass):
    """Every constant here came from one device; this is how another reports."""
    coordinator = _coordinator(hass, _entry())
    coordinator._primary_latch.drift_sum_wall = 378_494.0
    coordinator._primary_latch.drift_sum_counter = 362_079.0
    coordinator._primary_latch.drift_rate_min = 0.0424
    coordinator._primary_latch.drift_rate_max = 0.0473
    coordinator._primary_latch.drift_interval_count = 15

    published = coordinator.uptime_diagnostics
    assert published["drift_rate_pct"] == pytest.approx(4.337, abs=0.01)
    assert published["drift_rate_min_pct"] == pytest.approx(4.24, abs=0.01)
    assert published["drift_intervals"] == 15
    assert published["drift_deficit_seconds"] == 16_415

    state = coordinator.uptime_state["latches"]["last_www_uptime"]
    assert "anchor" in state
    assert "stored_written_at" in state
    assert state["startup_reconciled"] is False


@pytest.mark.asyncio
async def test_the_drift_picture_is_empty_before_measurement(hass):
    """A fresh install reports nothing rather than a confident zero."""
    coordinator = _coordinator(hass, _entry())
    assert coordinator.uptime_diagnostics["drift_rate_pct"] is None


# ---------------------------------------------------------------------------
# Replay of the real device
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_real_recorder_series_produces_no_false_alarm(hass):
    """Real drift, a real reboot and real gaps, from the device that failed.

    Captured from `home-assistant_v2.db` on 2026-09-01 before the recorder's
    ten-day purge. No synthetic fixture carries this much awkwardness: an
    intermittently-running Home Assistant, a counter losing 4.3%, and one
    genuine router reboot inside a thirteen-hour gap.
    """
    fixture = json.loads(
        (
            Path(__file__).parent / "fixtures" / "uptime_drift_real_series.json"
        ).read_text(encoding="utf-8")
    )
    samples = [s for s in fixture["samples"] if s["counter"] is not None]
    reboot_at = datetime.fromisoformat(fixture["known_events"]["router_reboot_utc"])

    coordinator = _coordinator(hass, _entry())
    moves: list[datetime] = []

    for sample in samples:
        now = datetime.fromisoformat(sample["utc"])
        before = coordinator._primary_latch.boot_time
        _poll(coordinator, sample["counter"], now)
        if coordinator._primary_latch.boot_time != before:
            moves.append(coordinator._primary_latch.boot_time)

    # The counter drop is unmissable, so the reboot must be found.
    assert any(abs((m - reboot_at).total_seconds()) < 3600 for m in moves), (
        f"the real reboot at {reboot_at} was not detected; moves were {moves}"
    )
    # One latch for the first poll, one for the reboot. Anything more is the
    # drift moving the timestamp, which is the defect being fixed.
    assert len(moves) <= 2, f"timestamp moved {len(moves)} times: {moves}"
    assert coordinator._drift_rate(coordinator._primary_latch) == pytest.approx(
        fixture["measured"]["aggregate_drift_rate"], abs=0.01
    )


# ---------------------------------------------------------------------------
# Defensive paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_store_record_dated_ahead_of_now_falls_back(hass):
    """Only reachable from a clock that has since been corrected backwards."""
    boot = NOW - timedelta(days=4)
    coordinator = _coordinator(hass, _entry(boot_time=boot.isoformat()))
    coordinator._primary_latch.stored_counter = 400_000
    coordinator._primary_latch.stored_written_at = NOW + timedelta(hours=2)

    _poll(coordinator, 4 * 86_400 * (1 - ZTE_RATE), NOW)

    assert coordinator._primary_latch.boot_time == boot, (
        "a healthy anchor was discarded"
    )
    assert coordinator._primary_latch.startup_reconciled


@pytest.mark.asyncio
async def test_a_store_record_dated_ahead_still_relatches_a_stale_anchor(hass):
    """The fallback must not become a way to keep a wrong anchor."""
    coordinator = _coordinator(
        hass, _entry(boot_time=(NOW - timedelta(days=24)).isoformat())
    )
    coordinator._primary_latch.stored_counter = 400_000
    coordinator._primary_latch.stored_written_at = NOW + timedelta(hours=2)

    _poll(coordinator, 4 * 86_400, NOW)

    assert coordinator._primary_latch.boot_time == NOW - timedelta(days=4)


@pytest.mark.asyncio
async def test_an_anchor_dated_ahead_of_now_is_implausible_at_cold_start(hass):
    """A zero or negative elapsed cannot be judged, so it is not believed."""
    coordinator = _coordinator(
        hass, _entry(boot_time=(NOW + timedelta(hours=1)).isoformat())
    )

    _poll(coordinator, 3_600, NOW)

    assert coordinator._primary_latch.boot_time == NOW - timedelta(seconds=3_600)


@pytest.mark.asyncio
async def test_the_plausibility_check_skips_a_future_anchor(hass):
    """It cannot divide by a non-positive elapsed, and must not try."""
    ahead = NOW + timedelta(hours=1)
    coordinator = _coordinator(hass, _entry())
    coordinator._primary_latch.startup_reconciled = True
    coordinator._primary_latch.boot_time = ahead
    coordinator._primary_latch.drift_sum_wall = 200_000.0
    coordinator._primary_latch.drift_sum_counter = 200_000.0 * (1 - ZTE_RATE)

    _poll(coordinator, 3_600, NOW)

    assert coordinator._primary_latch.boot_time == ahead, (
        "no latch from an unjudgeable anchor"
    )


@pytest.mark.parametrize("rate", [0.0, ZTE_RATE, 0.08, 0.12, -0.02])
@pytest.mark.asyncio
async def test_the_latched_instant_is_corrected_for_drift(hass, rate):
    """`now - counter` is late by the drift the counter has accumulated.

    On a device losing 4.34%, a counter reading four days puts the instant four
    and a half hours late. Dividing by `(1 - rate)` recovers the wall time the
    counter represents, which is both a more accurate timestamp and what keeps
    the plausibility check's tolerance independent of the device.
    """
    coordinator = _coordinator(hass, _entry())
    coordinator._primary_latch.startup_reconciled = True
    coordinator._primary_latch.boot_time = NOW - timedelta(days=30)
    coordinator._primary_latch.last_counter = 500_000
    coordinator._primary_latch.drift_sum_wall = 200_000.0
    coordinator._primary_latch.drift_sum_counter = 200_000.0 * (1 - rate)

    counter = 4 * 86_400
    _poll(coordinator, counter, NOW)

    expected = NOW - timedelta(seconds=counter / (1 - rate))
    assert coordinator._primary_latch.boot_time == expected.replace(microsecond=0)


@pytest.mark.parametrize("rate", [ZTE_RATE, 0.08, 0.12])
@pytest.mark.asyncio
async def test_a_stale_anchor_is_corrected_once_and_stays_corrected(hass, rate):
    """The upgrade case, at rates either side of the tolerance.

    Regression guard for the build in which this thrashed: 397 timestamp moves
    across 400 polls at 6% drift, which is worse than the defect being fixed.
    """
    coordinator = _coordinator(
        hass,
        _entry(boot_time=(NOW - timedelta(days=24)).isoformat(), last_uptime=60),
    )
    router = Router(rate=rate, uptime=4 * 86_400 * (1 - rate))

    moves = []
    previous = coordinator._primary_latch.boot_time
    now = NOW
    for _ in range(200):
        _poll(coordinator, router.counter, now)
        if coordinator._primary_latch.boot_time != previous:
            moves.append(coordinator._primary_latch.boot_time)
            previous = coordinator._primary_latch.boot_time
        now += POLL
        router.advance(POLL.total_seconds())

    assert len(moves) == 1, f"{len(moves)} moves at rate {rate:.2%}"
    assert "last_uptime" not in coordinator.entry.data["boot_times"]["www"]


# ---------------------------------------------------------------------------
# Total Connected Time guard (v345_plan I7)
# ---------------------------------------------------------------------------


def _total(coordinator, raw, now):
    return coordinator._checked_total_time(raw, now)


# ---------------------------------------------------------------------------
# UniFi: device boot times and the store on unload
# ---------------------------------------------------------------------------


def test_a_device_boot_time_is_its_startup_timestamp() -> None:
    """A device publishes its own ``startup_timestamp``, whatever was stored."""
    from custom_components.unifi_network_monitor.coordinator import _device_boot_time

    device = {"startup_timestamp": 1_789_810_718}
    published = _device_boot_time(device, 5, NOW)
    assert published == datetime.fromtimestamp(1_789_810_718, UTC)


def test_a_device_without_a_startup_timestamp_falls_back_to_uptime() -> None:
    """Without the field the boot time is ``now - uptime``."""
    from custom_components.unifi_network_monitor.coordinator import _device_boot_time

    assert _device_boot_time({}, 3600, NOW) == NOW - timedelta(hours=1)
    assert _device_boot_time({"startup_timestamp": True}, 60, NOW) == (
        NOW - timedelta(minutes=1)
    )


@pytest.mark.asyncio
async def test_the_latch_store_is_saved_on_unload(hass):
    """``async_flush_stores`` writes the latch record beside the other stores."""
    coordinator = _coordinator(hass, _entry())
    coordinator._store = MagicMock()
    coordinator._store.async_save = AsyncMock()
    coordinator._usage_store = MagicMock(async_save=AsyncMock())
    coordinator._rogue_history_store = MagicMock(async_save=AsyncMock())

    await coordinator.async_flush_stores()

    coordinator._store.async_save.assert_awaited_once()
    (record,) = coordinator._store.async_save.await_args.args
    assert set(record) == {"last_wan1_uptime", "last_wan2_uptime", "last_www_uptime"}


# ---------------------------------------------------------------------------
# Branches kept for alignment that no UniFi link counter reaches
#
# The floor rule serves a counter that pauses, which Huawei has and UniFi does
# not; it is kept verbatim so the three implementations stay one design.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_startup_reconciled_tracks_every_link(hass):
    """``_startup_reconciled`` is true only once every link latch has finished."""
    coordinator = _coordinator(hass, _entry())
    for latch in coordinator._latches:
        latch.last_counter = 10
    assert not coordinator._startup_reconciled
    for latch in coordinator._latches:
        latch.startup_reconciled = True
    assert coordinator._startup_reconciled


@pytest.mark.parametrize(("live", "relatched"), [(100, True), (5_000, False)])
@pytest.mark.asyncio
async def test_a_pausing_counter_uses_the_floor_rule(hass, live, relatched):
    """A pausing counter re-latches only when it moved below its stored value."""
    boot = NOW - timedelta(days=3)
    coordinator = _coordinator(hass, _entry(boot_time=boot.isoformat()))
    latch = coordinator._primary_latch
    latch.pauses = True
    latch.stored_counter = 1_000
    latch.stored_written_at = NOW - timedelta(hours=1)
    _poll(coordinator, live, NOW)
    assert (latch.boot_time != boot) is relatched


@pytest.mark.asyncio
async def test_a_pausing_counter_cold_start_is_one_sided(hass):
    """Below wall rate is legitimate for a pausing counter; above it is not."""
    boot = NOW - timedelta(days=3)
    coordinator = _coordinator(hass, _entry(boot_time=boot.isoformat()))
    latch = coordinator._primary_latch
    latch.pauses = True
    assert not coordinator._cold_start_implausible(latch, 1_000, NOW)
    assert coordinator._cold_start_implausible(latch, 400_000, NOW)


@pytest.mark.asyncio
async def test_the_plausibility_check_skips_an_anchor_dated_now(hass):
    """An anchor at or after now has no elapsed time to judge against."""
    coordinator = _coordinator(hass, _entry(boot_time=NOW.isoformat()))
    latch = coordinator._primary_latch
    latch.startup_reconciled = True
    latch.drift_sum_wall = 200_000.0
    latch.drift_sum_counter = 200_000.0
    _poll(coordinator, 10, NOW)
    assert latch.boot_time == NOW


@pytest.mark.asyncio
async def test_a_counter_write_without_a_store_is_kept_in_memory(hass):
    """With no store loaded the counter is still recorded on the latch."""
    coordinator = _coordinator(hass, _entry())
    coordinator._store = None
    latch = coordinator._primary_latch
    coordinator._write_counter(latch, 1_234, NOW)
    assert latch.stored_counter == 1_234


@pytest.mark.asyncio
async def test_a_naive_written_at_is_treated_as_absent(hass):
    """A ``written_at`` without an offset cannot date the gap and is dropped."""
    coordinator = _coordinator(hass, _entry())
    latch = coordinator._primary_latch
    coordinator._restore_latch(
        latch, {"last_uptime": 10, "written_at": "2026-09-01T12:00:00"}
    )
    assert latch.stored_counter == 10
    assert latch.stored_written_at is None


@pytest.mark.asyncio
async def test_no_anchor_is_implausible_at_cold_start(hass):
    """With no anchor there is nothing to retain, so the cold start re-latches."""
    coordinator = _coordinator(hass, _entry())
    assert coordinator._cold_start_implausible(coordinator._primary_latch, 10, NOW)


@pytest.mark.asyncio
async def test_a_link_that_never_reports_is_not_waited_for(hass):
    """WAN2 on a single-WAN gateway never reports; startup still completes."""
    coordinator = _coordinator(hass, _entry())
    for key in ("wan1", "www"):
        latch = coordinator._latches_by_key[key]
        latch.last_counter = 10
        latch.startup_reconciled = True
    assert coordinator._startup_reconciled


@pytest.mark.asyncio
async def test_a_latch_keeps_only_the_link_records(hass):
    """The v1.1.0 gateway and per-MAC records are dropped at the first latch."""
    entry = _entry(boot_time=(NOW - timedelta(days=5)).isoformat(), last_uptime=60)
    entry.data["boot_times"]["gateway"] = {"boot_time": "2026-07-18T16:27:00+00:00"}
    entry.data["boot_times"]["aa:bb:cc:00:00:02"] = {
        "boot_time": "2026-07-17T04:37:53+00:00"
    }
    coordinator = _coordinator(hass, entry)
    _poll(coordinator, 45, NOW)
    assert set(coordinator.entry.data["boot_times"]) == {"www"}
