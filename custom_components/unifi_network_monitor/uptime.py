"""Boot-time latches for the link uptime counters.

Ported from `zte_router_5g` `[3.3.10-dev1]`, the reference for
`fix_uptime_timestamp_gets_stuck.md`. The methods below are that project's,
verbatim; the differences UniFi forces are in the methods written here: the
anchors live in `entry.data["boot_times"]` keyed by link, the store record has
no Total Connected Time, and devices need no latch because the controller
reports each device's `startup_timestamp`.

A counter is a good reset detector and a poor clock. Comparing a counter with
its own previous value needs no clock at all and cannot drift; deriving a
timestamp as `now - counter` inherits the divergence between the gateway's
clock and the host's. The anchor is therefore latched once and held, and
re-derived only when something says it must be.

Four paths, in the order they are evaluated:

  1. Guards         - a reading or a clock that cannot be trusted.
  2. Counter drop   - conclusive, vetoed by nothing.
  3. Startup        - did the counter continue across a gap Home Assistant
                      did not observe?
  4. Plausibility   - is the anchor still credible? Every poll.

The design and the drift measurement behind the constants are in
`.shared/info/uptime_timestamp/uptime_drift_analyzed.md`.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CLOCK_FLOOR_YEAR,
    DOMAIN,
    DRIFT_ACCUMULATOR_CAP,
    DRIFT_MIN_ACCUMULATED,
    DRIFT_MIN_INTERVAL,
    MAX_DRIFT,
    MAX_PLAUSIBLE_UPTIME,
    PLAUSIBILITY_TOLERANCE,
    SHORTFALL_MARGIN_FLOOR,
    SHORTFALL_MARGIN_RATE,
    UPTIME_REBOOT_MARGIN,
    UPTIME_SAVE_DELAY,
    UPTIME_STORAGE_VERSION,
    UPTIME_WRITE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

# The links whose start the integration publishes from a counter. Devices are
# published from their own `startup_timestamp` and carry no latch.
LINK_LATCH_KEYS = ("wan1", "wan2", "www")

# The counter key each `entry.data["boot_times"]` record carried before this
# design. It is never read, and is dropped at the first latch.
LEGACY_COUNTER_KEYS = frozenset({"last_uptime"})


@dataclass
class _UptimeLatch:
    """One link counter, its anchor, and everything learned about its rate.

    Three run here, `wan1`, `wan2` and `www`, and **nothing is shared between
    them**: each resets on its own link's events, so a rate, a stored counter
    or a reconciliation flag borrowed from one would be evidence about a
    different question. None pauses (measured 2026-10-15, docs/DEVELOPMENT.md),
    so `pauses` stays `False`; the floor rule a pausing counter needs is kept
    from the shared design so the three projects remain one implementation.
    """

    label: str
    boot_key: str
    counter_key: str
    pauses: bool = False

    boot_time: datetime | None = None
    last_counter: int | None = None
    last_poll_at: datetime | None = None
    startup_reconciled: bool = False

    stored_counter: int | None = None
    stored_written_at: datetime | None = None
    last_counter_write: datetime | None = None

    drift_sum_wall: float = 0.0
    drift_sum_counter: float = 0.0
    drift_interval_count: int = 0
    drift_rate_min: float | None = None
    drift_rate_max: float | None = None


class UptimeLatchMixin:
    """The link latches, mixed into the coordinator."""

    hass: HomeAssistant
    entry: ConfigEntry

    def _init_uptime_latches(self, boot_times: dict[str, dict[str, Any]]) -> None:
        """Create one latch per link, anchored at its stored boot time."""
        self._store: Store[dict[str, Any]] | None = None
        self._latches_by_key: dict[str, _UptimeLatch] = {}
        for key in LINK_LATCH_KEYS:
            latch = _UptimeLatch(
                label=f"{key} start time",
                boot_key=key,
                counter_key=f"last_{key}_uptime",
            )
            raw = (boot_times.get(key) or {}).get("boot_time")
            if raw:
                with contextlib.suppress(Exception):
                    parsed = dt_util.parse_datetime(str(raw))
                    # A naive or unparsable anchor is treated as absent.
                    if parsed is not None and parsed.tzinfo is not None:
                        latch.boot_time = parsed
            self._latches_by_key[key] = latch
        self._latches = tuple(self._latches_by_key.values())
        self._primary_latch = self._latches_by_key["www"]

    @property
    def _startup_reconciled(self) -> bool:
        """Whether every link latch that has reported has finished reconciling.

        A link that never reports, such as WAN2 on a single-WAN gateway, is
        not waited for.
        """
        return all(
            latch.startup_reconciled
            for latch in self._latches
            if latch.last_counter is not None or latch.startup_reconciled
        )

    def link_boot_time(self, key: str, raw: Any) -> datetime | None:
        """Route one link counter reading through its latch; return the anchor."""
        latch = self._latches_by_key[key]
        self._apply_uptime_readings([(latch, raw)])
        return latch.boot_time

    def _apply_uptime_readings(self, readings: Any) -> None:
        """Route each `(latch, raw)` reading, then write the anchors once.

        The anchors live in `entry.data["boot_times"]`, keyed by link. The
        legacy `last_uptime` counter is dropped from every record here: it is
        no longer read - the counters come from the store, which is written on
        an interval rather than only at a latch - and leaving it invites a
        future reader to wire the frozen copy back in.
        """
        entry_data_updates: dict[str, Any] = {}
        for latch, raw in readings:
            self._apply_uptime(latch, raw, entry_data_updates)
        if entry_data_updates:
            stored = self.entry.data.get("boot_times")
            # Only the link records are kept: device boot times come from
            # `startup_timestamp`, so the v1.1.0 gateway and per-MAC records
            # are never read again.
            boot_times = {
                key: {k: v for k, v in record.items() if k not in LEGACY_COUNTER_KEYS}
                for key, record in (stored if isinstance(stored, dict) else {}).items()
                if isinstance(record, dict) and key in LINK_LATCH_KEYS
            }
            for key, boot_time in entry_data_updates.items():
                boot_times[key] = {"boot_time": boot_time}
            self.hass.config_entries.async_update_entry(
                self.entry, data={**self.entry.data, "boot_times": boot_times}
            )

    def _store_record(self) -> dict[str, Any]:
        """Return the persisted form of every link latch.

        One record rather than three files: the three are written on the same
        poll and read on the same setup. The fields inside each block match the
        sibling projects, so one reader serves all of them.
        """
        record: dict[str, Any] = {}
        for latch in self._latches:
            block: dict[str, Any] = {
                "last_uptime": latch.stored_counter,
                "written_at": (
                    latch.stored_written_at.isoformat()
                    if latch.stored_written_at is not None
                    else None
                ),
                "sum_wall": round(latch.drift_sum_wall, 3),
                "sum_counter": round(latch.drift_sum_counter, 3),
                "interval_count": latch.drift_interval_count,
            }
            if latch.drift_rate_min is not None:
                block["rate_min"] = round(latch.drift_rate_min, 6)
            if latch.drift_rate_max is not None:
                block["rate_max"] = round(latch.drift_rate_max, 6)
            record[latch.counter_key] = block
        return record

    async def async_load_stored_uptime(self) -> None:
        """Load the persisted counters and accumulators. Never raises.

        An absent, corrupt or unreadable record resolves to "nothing learned",
        which routes to the cold-start path - the store is a cross-check, never
        the anchor.
        """
        self._store = Store(
            self.hass,
            UPTIME_STORAGE_VERSION,
            f"{DOMAIN}_{self.entry.entry_id}_uptime",
        )
        stored: dict[str, Any] | None = None
        try:
            stored = await self._store.async_load()
        except Exception as err:  # noqa: BLE001 - see below
            # Deliberately broad. The contract is that **no** storage fault
            # can fail entry setup: the store is a cross-check and the
            # cold-start path works without it.
            _LOGGER.debug(
                "%s: uptime store unreadable, continuing without it: %s",
                self.entry.title,
                err,
            )
            return
        if not isinstance(stored, dict):
            return
        for latch in self._latches:
            block = stored.get(latch.counter_key)
            if isinstance(block, dict):
                self._restore_latch(latch, block)

    async def async_flush_uptime_store(self) -> None:
        """Write the latch record now; called on unload beside the other stores."""
        if self._store is not None:
            await self._store.async_save(self._store_record())

    def _drift_rate(self, latch: _UptimeLatch) -> float | None:
        """Return the fraction of wall time this counter loses, once trustworthy.

        `None` until enough has accumulated. The minimum is checked **before**
        the division, which is also what stops a fresh install dividing by a
        zero denominator.
        """
        if latch.pauses or latch.drift_sum_wall < DRIFT_MIN_ACCUMULATED:
            return None
        rate = 1.0 - (latch.drift_sum_counter / latch.drift_sum_wall)
        # Clamped at both ends for opposite reasons. An unbounded high rate
        # lowers the expected counter until a real shortfall stops
        # registering, suppressing detection; an unbounded low one raises it
        # and produces false alarms.
        return max(-MAX_DRIFT, min(MAX_DRIFT, rate))

    def _record_drift_sample(
        self, latch: _UptimeLatch, seconds: int, now: datetime
    ) -> None:
        """Fold one poll-to-poll interval into this latch's accumulators.

        Duration-weighted, so an interval spanning a long pause carries
        proportionally more evidence than one spanning three minutes. The
        measurement makes no reference to the anchor - the anchor is what the
        rate is used to judge, and deriving one from the other would be
        circular.
        """
        if latch.pauses or latch.last_counter is None or latch.last_poll_at is None:
            return
        wall = (now - latch.last_poll_at).total_seconds()
        advance = seconds - latch.last_counter
        if wall < DRIFT_MIN_INTERVAL or advance <= 0:
            # Too short for the counter's whole-second resolution, or a
            # reset. Neither says anything about the rate.
            return

        latch.drift_sum_wall += wall
        latch.drift_sum_counter += advance
        sample = 1.0 - (advance / wall)
        latch.drift_rate_min = (
            sample
            if latch.drift_rate_min is None
            else min(latch.drift_rate_min, sample)
        )
        latch.drift_rate_max = (
            sample
            if latch.drift_rate_max is None
            else max(latch.drift_rate_max, sample)
        )
        latch.drift_interval_count += 1

        if latch.drift_sum_wall > DRIFT_ACCUMULATOR_CAP:
            # Scale both down together: the ratio survives, but newer
            # evidence can move it, so a firmware fix to the timer is
            # followed rather than averaged away against history.
            scale = DRIFT_ACCUMULATOR_CAP / latch.drift_sum_wall
            latch.drift_sum_wall *= scale
            latch.drift_sum_counter *= scale

    def _derived_boot(
        self, latch: _UptimeLatch, seconds: int, now: datetime
    ) -> datetime:
        """Return the instant this counter started, corrected for its drift.

        `now - counter` is late by exactly the drift the counter has
        accumulated. Dividing by `(1 - rate)` recovers the wall time the
        counter represents. It matters twice: a latch taken long after the
        event is accurate, and the plausibility check can use a tight
        tolerance - without the correction a fresh anchor sits a full `rate`
        from the ratio that check predicts, so any device drifting past the
        tolerance would re-latch on every poll.

        Falls back to the uncorrected instant before a rate is known, where
        the error is bounded by the short accumulation that implies.
        """
        rate = self._drift_rate(latch)
        elapsed = seconds if rate is None else seconds / (1.0 - rate)
        return now - timedelta(seconds=elapsed)

    def _apply_uptime(
        self,
        latch: _UptimeLatch,
        raw: Any,
        entry_data_updates: dict[str, Any],
    ) -> None:
        """Route one counter reading through its latch."""
        seconds: int | None = None
        with contextlib.suppress(ValueError, TypeError):
            if raw is not None:
                seconds = int(float(raw))

        if seconds is None or seconds < 0:
            # Bad-reading guard: missing, unparsable or negative changes
            # nothing at all. Advancing the last-seen counter to a rejected
            # reading would move the reset comparison to a value the router
            # never reported.
            return

        now = dt_util.now()
        if now.year < CLOCK_FLOOR_YEAR:
            # The host has no battery-backed clock and NTP has not completed.
            # Defer rather than latch an instant decades adrift.
            _LOGGER.debug(
                "%s: system clock reads %s; deferring %s reconciliation",
                self.entry.title,
                now.isoformat(),
                latch.label,
            )
            return
        if seconds > MAX_PLAUSIBLE_UPTIME:
            _LOGGER.warning(
                "%s: implausible %s counter %s s; keeping the stored anchor",
                self.entry.title,
                latch.label,
                seconds,
            )
            return

        self._record_drift_sample(latch, seconds, now)

        if latch.startup_reconciled:
            self._apply_runtime_uptime(latch, seconds, now, entry_data_updates)
        else:
            self._reconcile_startup_uptime(latch, seconds, now, entry_data_updates)

        self._check_anchor_plausible(latch, seconds, now, entry_data_updates)

        latch.last_counter = seconds
        latch.last_poll_at = now
        self._maybe_persist_counter(latch, seconds, now)

    def _apply_runtime_uptime(
        self,
        latch: _UptimeLatch,
        seconds: int,
        now: datetime,
        entry_data_updates: dict[str, Any],
    ) -> None:
        """Compare the counter against itself during an unbroken session.

        Exact, and the reason the anchor is stable: no clock enters the
        comparison, so no drift can reach the timestamp. A drop beyond the
        margin is a reset, and nothing vetoes it.
        """
        if latch.last_counter is None:
            return
        if seconds < latch.last_counter - UPTIME_REBOOT_MARGIN:
            self._latch_boot_time(
                latch,
                self._derived_boot(latch, seconds, now),
                seconds,
                now,
                entry_data_updates,
            )
        elif seconds < latch.last_counter:
            # Inside the margin, so not a reset. Logged rather than absorbed
            # in silence: nothing has established that these counters never
            # step backwards, and the margin would otherwise hide the
            # evidence that they do.
            _LOGGER.info(
                "%s: %s counter stepped back %s s (%s to %s), within the %s s "
                "margin and not treated as a reset",
                self.entry.title,
                latch.label,
                latch.last_counter - seconds,
                latch.last_counter,
                seconds,
                UPTIME_REBOOT_MARGIN,
            )

    def _reconcile_startup_uptime(
        self,
        latch: _UptimeLatch,
        seconds: int,
        now: datetime,
        entry_data_updates: dict[str, Any],
    ) -> None:
        """Decide, on the first usable poll, whether a gap contained a reset.

        This is the boundary the running comparison cannot see. The stored
        counter is what makes it answerable, and the defect this mechanism
        replaces was that the stored counter was written **only at a latch**:
        one instance held 61 s against a live 213,412 s, frozen for nineteen
        days, so the comparison could never fire again.
        """
        if latch.stored_counter is not None:
            if latch.pauses or latch.stored_written_at is None:
                self._floor_test(latch, seconds, now, entry_data_updates)
            else:
                self._shortfall_test(
                    latch,
                    seconds,
                    now,
                    latch.stored_counter,
                    latch.stored_written_at,
                    entry_data_updates,
                )
            self._finish_startup(latch)
            return

        # Nothing stored: a fresh install, or the first start after this
        # upgrade. The only evidence is the anchor against the counter,
        # judged with the wide universal bound.
        if latch.boot_time is None or self._cold_start_implausible(latch, seconds, now):
            self._log_reconciliation(latch, "cold start, re-latching", seconds, now)
            self._latch_boot_time(
                latch,
                self._derived_boot(latch, seconds, now),
                seconds,
                now,
                entry_data_updates,
            )
        else:
            self._log_reconciliation(latch, "cold start, anchor retained", seconds, now)
        self._finish_startup(latch)

    def _floor_test(
        self,
        latch: _UptimeLatch,
        seconds: int,
        now: datetime,
        entry_data_updates: dict[str, Any],
    ) -> None:
        """Ask whether a counter that may legitimately pause moved backwards.

        The only question available for `TotalConnectTime`. It stops whenever
        the session is down, so under-running wall time across a gap says
        nothing - a week offline and a week disconnected look identical. It
        moves backwards for exactly one reason, a statistics clear, and that
        is what this detects.
        """
        stored = latch.stored_counter
        if stored is not None and seconds < stored:
            self._log_reconciliation(
                latch,
                f"counter reset during the gap (stored {stored} s)",
                seconds,
                now,
            )
            self._latch_boot_time(
                latch,
                self._derived_boot(latch, seconds, now),
                seconds,
                now,
                entry_data_updates,
            )
        else:
            self._log_reconciliation(
                latch,
                f"counter continued (stored {stored} s)",
                seconds,
                now,
            )

    def _shortfall_test(
        self,
        latch: _UptimeLatch,
        seconds: int,
        now: datetime,
        stored_counter: int,
        written_at: datetime,
        entry_data_updates: dict[str, Any],
    ) -> None:
        """Ask whether the counter continued across the gap as this device does.

        The stored pair is passed in rather than read from the latch: the
        caller has already established both are present, and passing them
        says so.
        """
        elapsed = (dt_util.as_utc(now) - written_at).total_seconds()
        if elapsed < 0:
            # The stored write is dated after now. Nothing useful can be said
            # about the gap, so fall back to the anchor comparison.
            _LOGGER.warning(
                "%s: stored %s write is dated ahead of now; using the "
                "cold-start comparison instead",
                self.entry.title,
                latch.label,
            )
            if latch.boot_time is None or self._cold_start_implausible(
                latch, seconds, now
            ):
                self._latch_boot_time(
                    latch,
                    self._derived_boot(latch, seconds, now),
                    seconds,
                    now,
                    entry_data_updates,
                )
            return

        rate = self._drift_rate(latch) or 0.0
        expected = stored_counter + elapsed * (1.0 - rate)
        # The margin scales because the error it absorbs scales: the dominant
        # term is rate-estimate error multiplied by the gap. The floor covers
        # quantization and poll latency on short gaps.
        margin = max(SHORTFALL_MARGIN_FLOOR, elapsed * SHORTFALL_MARGIN_RATE)

        if seconds < expected - margin:
            self._log_reconciliation(
                latch,
                f"reset during the gap (expected {expected:.0f} s, "
                f"margin {margin:.0f} s)",
                seconds,
                now,
            )
            self._latch_boot_time(
                latch,
                self._derived_boot(latch, seconds, now),
                seconds,
                now,
                entry_data_updates,
            )
        else:
            self._log_reconciliation(
                latch,
                f"counter continued (expected {expected:.0f} s, margin {margin:.0f} s)",
                seconds,
                now,
            )

    def _cold_start_implausible(
        self, latch: _UptimeLatch, seconds: int, now: datetime
    ) -> bool:
        """Judge the anchor with the universal bound, nothing having been learned.

        Two-sided for a counter that tracks wall time. The low side catches
        an anchor that is too early, which is the observed failure; the high
        side catches one that is too late, and exists because no counter has
        been measured running fast.

        **One-sided for a counter that pauses.** Downtime makes the ratio
        arbitrarily small with nothing wrong, so only the high side means
        anything: a counter cannot have run for longer than the anchor says
        has elapsed.
        """
        if latch.boot_time is None:
            return True
        elapsed = (
            dt_util.as_utc(now) - dt_util.as_utc(latch.boot_time)
        ).total_seconds()
        if elapsed <= 0:
            return True
        ratio = seconds / elapsed
        if latch.pauses:
            return ratio > (1.0 + MAX_DRIFT)
        return ratio < (1.0 - MAX_DRIFT) or ratio > (1.0 + MAX_DRIFT)

    def _check_anchor_plausible(
        self,
        latch: _UptimeLatch,
        seconds: int,
        now: datetime,
        entry_data_updates: dict[str, Any],
    ) -> None:
        """Backstop: is the anchor still credible against the counter?

        The startup tests run once and the runtime comparison only sees drops
        as they happen. Neither watches for an anchor that has *become*
        wrong, and retaining a stale anchor indefinitely is the failure this
        design exists to prevent.

        Compared against the counter's own measured rate rather than a
        universal constant, so no guess decides whether an unseen device
        works. A pausing counter has no rate and is not checked here at all:
        its ratio falls legitimately with every outage.
        """
        rate = self._drift_rate(latch)
        if rate is None or latch.boot_time is None:
            return
        elapsed = (
            dt_util.as_utc(now) - dt_util.as_utc(latch.boot_time)
        ).total_seconds()
        if elapsed <= 0:
            return
        if abs(seconds / elapsed - (1.0 - rate)) <= PLAUSIBILITY_TOLERANCE:
            return

        candidate = self._derived_boot(latch, seconds, now)
        if candidate <= latch.boot_time:
            # A reset moves the start instant forward: the anchor can only be
            # ahead of the true start by drift accumulated within the epoch
            # that produced it, and a few percent of an interval cannot
            # exceed the interval. A backward move is therefore not a reset.
            _LOGGER.warning(
                "%s: %s anchor implausible against the counter but the "
                "candidate instant is earlier (%s vs %s); not treating as a reset",
                self.entry.title,
                latch.label,
                candidate.isoformat(),
                latch.boot_time.isoformat(),
            )
            return

        self._log_reconciliation(
            latch, "anchor implausible against the counter", seconds, now
        )
        self._latch_boot_time(latch, candidate, seconds, now, entry_data_updates)

    def _finish_startup(self, latch: _UptimeLatch) -> None:
        """Mark this latch's startup reconciliation complete."""
        latch.startup_reconciled = True

    def _log_reconciliation(
        self, latch: _UptimeLatch, outcome: str, seconds: int, now: datetime
    ) -> None:
        """Record every input to a latch decision, and the decision.

        The absence of this is a substantial part of why the equivalent fault
        took five days of forensics on the sibling project rather than
        showing on the first restart.
        """
        rate = self._drift_rate(latch)
        _LOGGER.info(
            "%s: %s reconciliation - %s (live %s s, stored counter %s, "
            "written at %s, rate %s, stored anchor %s, derived anchor %s)",
            self.entry.title,
            latch.label,
            outcome,
            seconds,
            latch.stored_counter,
            latch.stored_written_at.isoformat() if latch.stored_written_at else None,
            f"{rate * 100:.2f}%" if rate is not None else "not yet measured",
            latch.boot_time.isoformat() if latch.boot_time is not None else None,
            self._derived_boot(latch, seconds, now).replace(microsecond=0).isoformat(),
        )

    def _latch_boot_time(
        self,
        latch: _UptimeLatch,
        boot_time: datetime,
        seconds: int,
        now: datetime,
        entry_data_updates: dict[str, Any],
    ) -> None:
        """Re-anchor this latch and persist it immediately."""
        previous = latch.boot_time
        latch.boot_time = boot_time.replace(microsecond=0)
        _LOGGER.info(
            "%s: %s latched: %s",
            self.entry.title,
            latch.label,
            latch.boot_time.isoformat(),
        )
        if previous is not None and latch.last_counter is not None:
            dropped = seconds < latch.last_counter - UPTIME_REBOOT_MARGIN
            if not dropped:
                # The signature of this entire bug class. A timestamp that
                # moves without the counter having dropped is either a
                # genuine gap reset or a defect, and the two are worth
                # telling apart from the log alone.
                _LOGGER.warning(
                    "%s: %s moved from %s to %s without a counter drop "
                    "(live %s s, previous %s s)",
                    self.entry.title,
                    latch.label,
                    previous.isoformat(),
                    latch.boot_time.isoformat(),
                    seconds,
                    latch.last_counter,
                )
        entry_data_updates[latch.boot_key] = latch.boot_time.isoformat()
        self._write_counter(latch, seconds, now)

    def _maybe_persist_counter(
        self, latch: _UptimeLatch, seconds: int, now: datetime
    ) -> None:
        """Flush the counter and accumulators on a fixed interval.

        **This is the half of the fix that addresses the observed defect.**
        The counter used to reach disk only when a latch happened, so the
        stored value froze at whatever the counter read one poll after a
        boot - 61 s on the instance this was written against - and the
        restart comparison could never fire again. Writing on an interval
        bounds how stale the stored value can be, for every stop condition
        rather than only an orderly one.

        A clean shutdown needs no hook: `async_delay_save` registers a
        final-write listener that flushes a pending save when Home Assistant
        stops.
        """
        if (
            latch.last_counter_write is not None
            and now - latch.last_counter_write < UPTIME_WRITE_INTERVAL
        ):
            return
        self._write_counter(latch, seconds, now)

    def _write_counter(self, latch: _UptimeLatch, seconds: int, now: datetime) -> None:
        """Schedule a debounced write of every latch's counter and accumulators."""
        latch.stored_counter = seconds
        latch.stored_written_at = dt_util.as_utc(now)
        latch.last_counter_write = now
        if self._store is None:
            return
        record = self._store_record()
        self._store.async_delay_save(lambda: record, UPTIME_SAVE_DELAY)

    def _restore_latch(self, latch: _UptimeLatch, block: dict[str, Any]) -> None:
        """Read one latch's block back, treating anything unusable as absent."""
        with contextlib.suppress(ValueError, TypeError):
            raw = block.get("last_uptime")
            if raw is not None:
                latch.stored_counter = int(raw)
        with contextlib.suppress(ValueError, TypeError):
            latch.drift_sum_wall = float(block.get("sum_wall", 0.0))
            latch.drift_sum_counter = float(block.get("sum_counter", 0.0))
            latch.drift_interval_count = int(block.get("interval_count", 0))
        for key, attr in (
            ("rate_min", "drift_rate_min"),
            ("rate_max", "drift_rate_max"),
        ):
            with contextlib.suppress(ValueError, TypeError):
                raw = block.get(key)
                if raw is not None:
                    setattr(latch, attr, float(raw))

        # `written_at` carries the same naive-versus-aware hazard as the
        # anchor: both are read back as strings and both are subtracted from
        # `now()`. A value that will not parse, or parses naive, is treated
        # as absent - which means the record cannot date the gap, and the
        # floor comparison applies instead.
        raw_written = block.get("written_at")
        if raw_written:
            with contextlib.suppress(Exception):
                parsed = dt_util.parse_datetime(raw_written)
                if parsed is not None and parsed.tzinfo is not None:
                    latch.stored_written_at = dt_util.as_utc(parsed)

    def _latch_rate_pct(self, latch: _UptimeLatch) -> float | None:
        """Return one latch's measured rate as a percentage, or `None`."""
        rate = self._drift_rate(latch)
        return round(rate * 100, 3) if rate is not None else None

    @property
    def uptime_diagnostics(self) -> dict[str, Any]:
        """Return the drift picture, for the health sensor and diagnostics.

        Published because every constant in the latch was set from one device
        over one week on a sibling project. Without this a field report
        carries no rate, and the only route to one is a recorder extraction.

        Reports the `www` counter alone, UniFi's equivalent of the system
        counter. The WAN counters keep their own accumulators, and none is a
        property of the host clock, so listing all three here would invite
        exactly the comparison that is not meaningful.
        """
        latch = self._primary_latch
        rate = self._drift_rate(latch)
        return {
            "drift_rate_pct": round(rate * 100, 3) if rate is not None else None,
            "drift_rate_min_pct": (
                round(latch.drift_rate_min * 100, 3)
                if latch.drift_rate_min is not None
                else None
            ),
            "drift_rate_max_pct": (
                round(latch.drift_rate_max * 100, 3)
                if latch.drift_rate_max is not None
                else None
            ),
            "drift_intervals": latch.drift_interval_count,
            "drift_measured_seconds": round(latch.drift_sum_wall),
            "drift_deficit_seconds": round(
                latch.drift_sum_wall - latch.drift_sum_counter
            ),
        }

    @property
    def uptime_state(self) -> dict[str, Any]:
        """Return every latch's full state, for the diagnostics download.

        Wider than `uptime_diagnostics`, which is the rate summary the health
        sensor publishes. Carries no device data and nothing to redact:
        counters, rates and timestamps.
        """
        return {
            **self.uptime_diagnostics,
            "latches": {
                latch.counter_key: {
                    "anchor": (
                        latch.boot_time.isoformat()
                        if latch.boot_time is not None
                        else None
                    ),
                    "live_counter": latch.last_counter,
                    "stored_counter": latch.stored_counter,
                    "stored_written_at": (
                        latch.stored_written_at.isoformat()
                        if latch.stored_written_at is not None
                        else None
                    ),
                    "startup_reconciled": latch.startup_reconciled,
                    "pauses": latch.pauses,
                    "drift_rate_pct": self._latch_rate_pct(latch),
                }
                for latch in self._latches
            },
        }
