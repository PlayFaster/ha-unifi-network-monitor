"""Cumulative-usage high-water-mark tests.

UniFi apportions the open daily/monthly reporting bucket and recomputes it on
every poll, so a WAN byte total can drift slightly *downward* within a period.
That breaks the ``total_increasing`` state class. ``_clamp_usage`` holds each
counter's running maximum and resets only on a genuine period rollover, keyed on
the bucket's ``time`` moving *forward* — never on the value.
"""

from __future__ import annotations

from typing import Any

from custom_components.unifi_network_monitor.coordinator import (
    UnifiNetworkDataUpdateCoordinator as Coordinator,
)

KEY = "wan1_month_tx"
P1, P2 = 1_780_268_400_000, 1_782_860_400_000  # two real month-start stamps


def _coord() -> Any:
    c = Coordinator.__new__(Coordinator)
    c.usage_watermark = {}
    return c


def test_downward_wobble_is_held() -> None:
    """A within-period downward restatement must not step the counter back."""
    c = _coord()
    assert c._clamp_usage(KEY, P1, 256_719_487_164.182) == 256_719_487_164
    # UniFi re-apportions the open bucket slightly lower — hold the maximum.
    assert c._clamp_usage(KEY, P1, 256_713_823_164.182) == 256_719_487_164


def test_upward_movement_is_followed() -> None:
    """Genuine growth within the period is tracked."""
    c = _coord()
    c._clamp_usage(KEY, P1, 100.0)
    assert c._clamp_usage(KEY, P1, 500.0) == 500


def test_period_rollover_resets_to_new_value() -> None:
    """A forward period move is a real reset — adopt the new near-zero value."""
    c = _coord()
    c._clamp_usage(KEY, P1, 900_000_000_000.0)
    # New month: the bucket legitimately restarts near zero.
    assert c._clamp_usage(KEY, P2, 5_000.0) == 5_000
    assert c.usage_watermark[KEY] == {"period": P2, "value": 5_000}


def test_same_period_restamp_cannot_reset() -> None:
    """The reset is forward-only: a lower value at the SAME period must hold.

    Guards against the controller re-stamping the current bucket without a real
    rollover — only a strictly larger period counts as a new period.
    """
    c = _coord()
    c.usage_watermark = {KEY: {"period": P2, "value": 5_000}}
    assert c._clamp_usage(KEY, P2, 4_000.0) == 5_000


def test_stale_bucket_is_ignored() -> None:
    """An out-of-order older bucket must not overwrite the current maximum."""
    c = _coord()
    c.usage_watermark = {KEY: {"period": P2, "value": 5_000}}
    assert c._clamp_usage(KEY, P1, 999_999_999_999.0) == 5_000


def test_none_raw_returns_none() -> None:
    """A missing counter value stays None (sensor shows unknown)."""
    c = _coord()
    assert c._clamp_usage(KEY, P1, None) is None
    assert KEY not in c.usage_watermark  # nothing recorded


def test_missing_period_passes_value_through_rounded() -> None:
    """With no bucket timestamp, pass the value through — rounded, unclamped."""
    c = _coord()
    assert c._clamp_usage(KEY, None, 42.7) == 43
    assert KEY not in c.usage_watermark  # cannot track a period-less counter


def test_counters_are_independent() -> None:
    """Each counter holds its own watermark; one does not clamp another."""
    c = _coord()
    c._clamp_usage("wan1_month_rx", P1, 1_000.0)
    c._clamp_usage("wan1_month_tx", P1, 9_000.0)
    # rx dips — only rx is held; tx is untouched.
    assert c._clamp_usage("wan1_month_rx", P1, 500.0) == 1_000
    assert c.usage_watermark["wan1_month_tx"]["value"] == 9_000


def test_bytes_rounded_to_whole_numbers() -> None:
    """Fractional apportionment noise is dropped; the source is a byte counter."""
    c = _coord()
    assert c._clamp_usage(KEY, P1, 78_099_916_089.591) == 78_099_916_090


async def test_watermark_survives_a_reload(hass: Any) -> None:
    """A persisted watermark is restored, so a restart re-emits no downward step.

    Simulates: run 1 records a high value, HA restarts, run 2's first poll reads
    the controller's slightly-lower open-bucket value — which must be clamped to
    the persisted maximum rather than reported as a decrease.
    """
    from unittest.mock import patch

    from custom_components.unifi_network_monitor.coordinator import (
        UnifiNetworkDataUpdateCoordinator,
    )

    persisted = {KEY: {"period": P2, "value": 256_719_487_164}}

    with patch.object(UnifiNetworkDataUpdateCoordinator, "__init__", return_value=None):
        coord = UnifiNetworkDataUpdateCoordinator()
        coord.rogue_history = {}
        coord.usage_watermark = {}

        async def _load_usage() -> dict[str, Any]:
            return persisted

        async def _load_rogue() -> dict[str, Any]:
            return {}

        coord._usage_store = type("S", (), {"async_load": staticmethod(_load_usage)})()
        coord._rogue_history_store = type(
            "S", (), {"async_load": staticmethod(_load_rogue)}
        )()

        await coord.async_initialize()

    # Restored intact.
    assert coord.usage_watermark == persisted
    # First post-restart poll reads the open bucket slightly lower — held.
    assert coord._clamp_usage(KEY, P2, 256_713_823_164.182) == 256_719_487_164


async def test_flush_stores_forces_immediate_save(hass: Any) -> None:
    """Unload flushes pending delayed saves, so a reload cannot lose them.

    A config-entry reload fires no HOMEASSISTANT_STOP event, so a coalesced
    ``async_delay_save`` would otherwise be dropped. ``async_flush_stores`` writes
    both stores immediately with the current in-memory state.
    """
    from unittest.mock import AsyncMock, patch

    from custom_components.unifi_network_monitor.coordinator import (
        UnifiNetworkDataUpdateCoordinator,
    )

    with patch.object(UnifiNetworkDataUpdateCoordinator, "__init__", return_value=None):
        coord = UnifiNetworkDataUpdateCoordinator()
        coord.usage_watermark = {KEY: {"period": P2, "value": 256_719_487_164}}
        coord.rogue_history = {"aa:bb:cc:dd:ee:ff": {"appearances": 3}}
        coord._usage_store = type("S", (), {"async_save": AsyncMock()})()
        coord._rogue_history_store = type("S", (), {"async_save": AsyncMock()})()

        await coord.async_flush_stores()

    coord._usage_store.async_save.assert_awaited_once_with(coord.usage_watermark)
    coord._rogue_history_store.async_save.assert_awaited_once_with(coord.rogue_history)
