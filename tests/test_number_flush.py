"""Tests for flushing a pending debounced write on entity removal.

**item 6** of the August 2026 plan (§M Phase 1). Both number entities buffer a
slider move for two seconds and used to *cancel* that buffer in
``async_will_remove_from_hass``. A reload is enough to trigger removal — and an
options change is enough to trigger a reload — so a value set inside the
debounce window was silently discarded: the UI showed the new number, the
controller never heard about it, and nothing said so.

The flush must be conditional. Once the apply has actually started it must not
be started a second time; for the WAN pair that would mean a second round of
PUTs against a write the coordinator already shields to completion.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from custom_components.unifi_network_monitor.const import CONF_SCAN_INTERVAL

from .conftest import MOCK_COORDINATOR_DATA, MOCK_MAC


def _make_coordinator() -> MagicMock:
    coord = MagicMock()
    coord.data = MOCK_COORDINATOR_DATA
    coord.gateway_mac = MOCK_MAC
    coord.gateway_model = "UDMPRO"
    coord.sw_version = "5.1.19.33549"
    coord.async_force_refresh = AsyncMock()
    coord.async_request_refresh = AsyncMock()
    coord.async_add_listener = MagicMock()
    coord.async_set_wan_weights = AsyncMock(return_value="confirmed")
    coord.wan_weights_writable = True
    coord.endpoint_available = MagicMock(return_value=True)
    return coord


def _make_entry() -> MagicMock:
    entry = MagicMock()
    entry.unique_id = MOCK_MAC
    entry.title = "UniFi Network"
    entry.options = {"host": "192.168.1.1", CONF_SCAN_INTERVAL: 30}
    return entry


# ---------------------------------------------------------------------------
# WAN load balance
# ---------------------------------------------------------------------------


async def test_wan_removal_flushes_pending_weight(hass: Any) -> None:
    """A weight set inside the debounce window is written, not dropped."""
    from custom_components.unifi_network_monitor.number import WanLoadBalanceNumber

    coordinator = _make_coordinator()
    number = WanLoadBalanceNumber(coordinator, _make_entry())
    number.hass = hass
    number.async_write_ha_state = MagicMock()  # type: ignore[method-assign]

    await number.async_set_native_value(70.0)
    # Removal lands well inside the 2 s debounce window.
    await number.async_will_remove_from_hass()

    coordinator.async_set_wan_weights.assert_awaited_once_with(70)


async def test_wan_removal_with_no_pending_write_does_nothing(hass: Any) -> None:
    """Removal without a buffered change writes nothing."""
    from custom_components.unifi_network_monitor.number import WanLoadBalanceNumber

    coordinator = _make_coordinator()
    number = WanLoadBalanceNumber(coordinator, _make_entry())
    number.hass = hass

    await number.async_will_remove_from_hass()

    coordinator.async_set_wan_weights.assert_not_awaited()


async def test_wan_removal_does_not_reapply_a_started_write(hass: Any) -> None:
    """A write already in flight is not started a second time by the flush."""
    from custom_components.unifi_network_monitor.number import WanLoadBalanceNumber

    started = asyncio.Event()
    release = asyncio.Event()

    async def _slow_write(_value: int) -> str:
        started.set()
        await release.wait()
        return "confirmed"

    coordinator = _make_coordinator()
    coordinator.async_set_wan_weights = AsyncMock(side_effect=_slow_write)
    number = WanLoadBalanceNumber(coordinator, _make_entry())
    number.hass = hass
    number.async_write_ha_state = MagicMock()  # type: ignore[method-assign]

    await number.async_set_native_value(70.0)
    # Skip the debounce so the apply is genuinely under way.
    number._pending_value = None
    task = hass.async_create_task(coordinator.async_set_wan_weights(70))
    async with asyncio.timeout(5):
        await started.wait()

    await number.async_will_remove_from_hass()
    release.set()
    await task

    assert coordinator.async_set_wan_weights.await_count == 1


async def test_wan_flush_swallows_write_errors(hass: Any, caplog: Any) -> None:
    """A failing flush is logged, never raised — removal must not be blocked."""
    from custom_components.unifi_network_monitor.api import UnifiConnectionError
    from custom_components.unifi_network_monitor.number import WanLoadBalanceNumber

    coordinator = _make_coordinator()
    coordinator.async_set_wan_weights = AsyncMock(
        side_effect=UnifiConnectionError("gone")
    )
    number = WanLoadBalanceNumber(coordinator, _make_entry())
    number.hass = hass
    number.async_write_ha_state = MagicMock()  # type: ignore[method-assign]

    await number.async_set_native_value(70.0)

    with caplog.at_level(logging.ERROR):
        await number.async_will_remove_from_hass()

    # Swallowed, but not silently: removal proceeds and the loss is on record.
    coordinator.async_set_wan_weights.assert_awaited_once_with(70)
    assert any("WAN load balance weight" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Scan interval
# ---------------------------------------------------------------------------


async def test_scan_interval_removal_flushes_pending_value(hass: Any) -> None:
    """A polling interval set inside the debounce window is persisted."""
    from custom_components.unifi_network_monitor.number import UnifiScanIntervalNumber

    coordinator = _make_coordinator()
    entry = _make_entry()
    number = UnifiScanIntervalNumber(coordinator, entry, 30)
    number.hass = hass
    number.async_write_ha_state = MagicMock()  # type: ignore[method-assign]
    updated: list[dict[str, Any]] = []
    number.hass.config_entries.async_update_entry = MagicMock(  # type: ignore[method-assign]
        side_effect=lambda _e, options: updated.append(options)
    )

    await number.async_set_native_value(120.0)
    await number.async_will_remove_from_hass()

    assert updated and updated[-1][CONF_SCAN_INTERVAL] == 120
    coordinator.async_force_refresh.assert_awaited()


async def test_scan_interval_removal_with_no_pending_value(hass: Any) -> None:
    """Removal without a buffered change persists nothing."""
    from custom_components.unifi_network_monitor.number import UnifiScanIntervalNumber

    coordinator = _make_coordinator()
    number = UnifiScanIntervalNumber(coordinator, _make_entry(), 30)
    number.hass = hass
    number.hass.config_entries.async_update_entry = MagicMock()  # type: ignore[method-assign]

    await number.async_will_remove_from_hass()

    number.hass.config_entries.async_update_entry.assert_not_called()
    coordinator.async_force_refresh.assert_not_awaited()
