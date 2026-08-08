"""Tests for the WAN load-balance write path.

Covers the three defects the August 2026 plan raises against it (§M Phase 1):

- **item 3** — the control is fed from ``EP_NETWORKCONF``, a *degradable*
  endpoint, and declared no ``source`` gate; and it PUT the entire *held*
  network-configuration object back, so a weight change during a stale window
  silently reverted whatever else had changed controller-side.
- **item 33** — cancelling the debounce once the first PUT has gone out left
  WAN1 written and WAN2 not, so the pair stopped summing to 100 with nothing
  reporting it.
- **item 7** — a write was reported as done without ever being read back, and
  *unverified* was not distinguishable from *failed*.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.unifi_network_monitor.api import UnifiConnectionError
from custom_components.unifi_network_monitor.const import EP_NETWORKCONF
from custom_components.unifi_network_monitor.coordinator import (
    UnifiNetworkDataUpdateCoordinator,
)


def _netconf(wan1: int, wan2: int) -> list[dict[str, Any]]:
    """Build a ``rest/networkconf`` payload: both WANs and an unrelated LAN."""
    return [
        {
            "_id": "lan_id",
            "purpose": "corporate",
            "name": "Default",
        },
        {
            "_id": "wan1_id",
            "purpose": "wan",
            "wan_networkgroup": "WAN",
            "wan_load_balance_weight": wan1,
            "wan_load_balance_type": "failover-only",
            "some_other_field": "set-by-someone-else",
        },
        {
            "_id": "wan2_id",
            "purpose": "wan",
            "wan_networkgroup": "WAN2",
            "wan_load_balance_weight": wan2,
        },
    ]


def _make_coordinator(
    hass: Any, entry: Any, api: MagicMock
) -> UnifiNetworkDataUpdateCoordinator:
    entry.add_to_hass(hass)
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, entry, api)
    coordinator.async_force_refresh = AsyncMock()  # type: ignore[method-assign]
    return coordinator


# ---------------------------------------------------------------------------
# item 3 — write from a fresh read, never from held state
# ---------------------------------------------------------------------------


async def test_set_wan_weights_reads_networkconf_before_writing(
    hass: Any, mock_config_entry: Any
) -> None:
    """The PUT is composed from a fresh GET, not from the held object."""
    api = MagicMock()
    api.update_networkconf = AsyncMock()
    api.get_networkconf = AsyncMock(side_effect=[_netconf(55, 45), _netconf(70, 30)])

    coordinator = _make_coordinator(hass, mock_config_entry, api)
    # Held state is deliberately stale *and* missing the field a third party set.
    coordinator._networkconf_wan = {"_id": "wan1_id", "wan_load_balance_weight": 10}
    coordinator._networkconf_wan2 = {"_id": "wan2_id", "wan_load_balance_weight": 90}

    await coordinator.async_set_wan_weights(70)

    # Read before write.
    assert api.get_networkconf.await_count >= 1
    assert api.update_networkconf.await_count == 2
    sent_wan1 = api.update_networkconf.await_args_list[0].args[1]
    # The concurrently-changed field survives because the PUT came from the GET.
    assert sent_wan1["some_other_field"] == "set-by-someone-else"
    assert sent_wan1["wan_load_balance_weight"] == 70
    sent_wan2 = api.update_networkconf.await_args_list[1].args[1]
    assert sent_wan2["wan_load_balance_weight"] == 30


async def test_set_wan_weights_raises_when_fresh_read_has_no_wan(
    hass: Any, mock_config_entry: Any
) -> None:
    """A fresh read without both WANs refuses the write rather than guessing."""
    api = MagicMock()
    api.update_networkconf = AsyncMock()
    api.get_networkconf = AsyncMock(return_value=[{"_id": "lan", "purpose": "corp"}])

    coordinator = _make_coordinator(hass, mock_config_entry, api)
    coordinator._networkconf_wan = {"_id": "wan1_id"}
    coordinator._networkconf_wan2 = {"_id": "wan2_id"}

    with pytest.raises(ValueError, match="not yet loaded"):
        await coordinator.async_set_wan_weights(70)
    api.update_networkconf.assert_not_awaited()


async def test_set_wan_weights_raises_when_fresh_read_lacks_id(
    hass: Any, mock_config_entry: Any
) -> None:
    """A WAN object with no ``_id`` cannot be addressed, so nothing is written."""
    raw = _netconf(50, 50)
    del raw[1]["_id"]
    api = MagicMock()
    api.update_networkconf = AsyncMock()
    api.get_networkconf = AsyncMock(return_value=raw)

    coordinator = _make_coordinator(hass, mock_config_entry, api)

    with pytest.raises(ValueError, match="missing _id"):
        await coordinator.async_set_wan_weights(60)
    api.update_networkconf.assert_not_awaited()


async def test_wan_load_balance_number_declares_networkconf_source(
    hass: Any, mock_config_entry: Any
) -> None:
    """The entity goes unavailable when EP_NETWORKCONF is stale (item 3's gate)."""
    from custom_components.unifi_network_monitor.number import WanLoadBalanceNumber

    coordinator = MagicMock()
    coordinator.data = {"gateway": {"wan1_weight": 50}}
    coordinator.async_add_listener = MagicMock()
    coordinator.last_update_success = True
    entry = MagicMock()
    entry.unique_id = "aa:bb:cc:dd:ee:ff"
    entry.options = {}

    number = WanLoadBalanceNumber(coordinator, entry)
    number.hass = hass

    coordinator.endpoint_available = MagicMock(return_value=True)
    assert number.available is True
    coordinator.endpoint_available.assert_called_with(EP_NETWORKCONF)

    coordinator.endpoint_available = MagicMock(return_value=False)
    assert number.available is False


async def test_wan_load_balance_set_value_rejected_when_endpoint_stale(
    hass: Any,
) -> None:
    """A stale networkconf endpoint refuses the write instead of PUTting blind."""
    from homeassistant.exceptions import HomeAssistantError

    from custom_components.unifi_network_monitor.number import WanLoadBalanceNumber

    coordinator = MagicMock()
    coordinator.data = {"gateway": {"wan1_weight": 50}}
    coordinator.async_add_listener = MagicMock()
    coordinator.wan_weights_writable = True
    coordinator.endpoint_available = MagicMock(return_value=False)
    entry = MagicMock()
    entry.unique_id = "aa:bb:cc:dd:ee:ff"
    entry.options = {}

    number = WanLoadBalanceNumber(coordinator, entry)
    number.hass = hass

    with pytest.raises(HomeAssistantError) as exc_info:
        await number.async_set_native_value(70.0)
    assert exc_info.value.translation_key == "wan_config_not_loaded"


# ---------------------------------------------------------------------------
# item 33 — the pair is non-interruptible once the first PUT has gone out
# ---------------------------------------------------------------------------


async def test_set_wan_weights_pair_completes_when_cancelled_mid_write(
    hass: Any, mock_config_entry: Any
) -> None:
    """Cancelling between the two PUTs still writes both — the pair sums to 100.

    This is the §N (22) hazard: the debounce task is suspended *inside*
    ``async_set_wan_weights`` between the two writes, so ``cancel()`` used to
    raise there and leave WAN1 written and WAN2 not.
    """
    first_put_started = asyncio.Event()
    release_first_put = asyncio.Event()
    put_calls: list[tuple[str, int]] = []

    async def _slow_put(net_id: str, payload: dict[str, Any]) -> None:
        put_calls.append((net_id, payload["wan_load_balance_weight"]))
        if net_id == "wan1_id":
            first_put_started.set()
            await release_first_put.wait()

    api = MagicMock()
    api.update_networkconf = AsyncMock(side_effect=_slow_put)
    api.get_networkconf = AsyncMock(return_value=_netconf(50, 50))

    coordinator = _make_coordinator(hass, mock_config_entry, api)

    task = hass.async_create_task(coordinator.async_set_wan_weights(70))
    async with asyncio.timeout(5):
        await first_put_started.wait()

    # Cancel exactly where the old code lost WAN2.
    task.cancel()
    release_first_put.set()
    with pytest.raises(asyncio.CancelledError):
        await task

    # Let the shielded pair finish.
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert put_calls == [("wan1_id", 70), ("wan2_id", 30)], (
        "the WAN pair must complete once the first PUT has gone out"
    )


async def test_set_wan_weights_cancelled_before_first_put_writes_nothing(
    hass: Any, mock_config_entry: Any
) -> None:
    """Cancelling before the write begins leaves the controller untouched."""
    read_started = asyncio.Event()
    release_read = asyncio.Event()

    async def _slow_get() -> list[dict[str, Any]]:
        read_started.set()
        await release_read.wait()
        return _netconf(50, 50)

    api = MagicMock()
    api.update_networkconf = AsyncMock()
    api.get_networkconf = AsyncMock(side_effect=_slow_get)

    coordinator = _make_coordinator(hass, mock_config_entry, api)

    task = hass.async_create_task(coordinator.async_set_wan_weights(70))
    async with asyncio.timeout(5):
        await read_started.wait()
    task.cancel()
    release_read.set()
    with pytest.raises(asyncio.CancelledError):
        await task

    api.update_networkconf.assert_not_awaited()


# ---------------------------------------------------------------------------
# item 7 — read back, and keep the three outcomes distinct
# ---------------------------------------------------------------------------


async def test_set_wan_weights_confirmed_when_readback_matches(
    hass: Any, mock_config_entry: Any
) -> None:
    """A read-back that agrees with what was sent reports ``confirmed``."""
    api = MagicMock()
    api.update_networkconf = AsyncMock()
    api.get_networkconf = AsyncMock(side_effect=[_netconf(50, 50), _netconf(70, 30)])

    coordinator = _make_coordinator(hass, mock_config_entry, api)

    assert await coordinator.async_set_wan_weights(70) == "confirmed"


async def test_set_wan_weights_failed_when_readback_disagrees(
    hass: Any, mock_config_entry: Any
) -> None:
    """A read-back showing the old value reports ``failed`` — the write did not take."""
    api = MagicMock()
    api.update_networkconf = AsyncMock()
    api.get_networkconf = AsyncMock(side_effect=[_netconf(50, 50), _netconf(50, 50)])

    coordinator = _make_coordinator(hass, mock_config_entry, api)

    assert await coordinator.async_set_wan_weights(70) == "failed"


async def test_set_wan_weights_unverified_when_readback_errors(
    hass: Any, mock_config_entry: Any
) -> None:
    """A read-back that cannot be taken is ``unverified`` — **not** ``failed``.

    The write may well have landed; reporting it as a failure would send the
    user chasing a change that actually applied.
    """
    api = MagicMock()
    api.update_networkconf = AsyncMock()
    api.get_networkconf = AsyncMock(
        side_effect=[_netconf(50, 50), UnifiConnectionError("controller busy")]
    )

    coordinator = _make_coordinator(hass, mock_config_entry, api)

    assert await coordinator.async_set_wan_weights(70) == "unverified"


async def test_set_wan_weights_unverified_when_readback_lacks_wan(
    hass: Any, mock_config_entry: Any
) -> None:
    """A read-back missing the WAN objects proves nothing either way."""
    api = MagicMock()
    api.update_networkconf = AsyncMock()
    api.get_networkconf = AsyncMock(side_effect=[_netconf(50, 50), []])

    coordinator = _make_coordinator(hass, mock_config_entry, api)

    assert await coordinator.async_set_wan_weights(70) == "unverified"


# ---------------------------------------------------------------------------
# The outcome reaches the log at the right level
# ---------------------------------------------------------------------------


async def test_force_refresh_sets_the_bypass_flag(
    hass: Any, mock_config_entry: Any
) -> None:
    """The post-write refresh bypasses the pause guard (explicit user action)."""
    from unittest.mock import AsyncMock as _AsyncMock

    mock_config_entry.add_to_hass(hass)
    coordinator = UnifiNetworkDataUpdateCoordinator(
        hass, mock_config_entry, MagicMock()
    )
    coordinator.async_request_refresh = _AsyncMock()  # type: ignore[method-assign]

    await coordinator.async_force_refresh()

    assert coordinator._force_refresh_once is True
    coordinator.async_request_refresh.assert_awaited_once()


@pytest.mark.parametrize(
    ("outcome", "level"),
    [("failed", "ERROR"), ("unverified", "WARNING"), ("confirmed", None)],
)
async def test_number_logs_each_write_outcome_at_its_own_level(
    hass: Any, caplog: Any, outcome: str, level: str | None
) -> None:
    """A failed write is an error; an unverified one is only a warning.

    Reporting *unverified* as a failure would send the user chasing a change
    that most likely applied, which is precisely the distinction item 7 exists
    to keep.
    """
    import logging

    from custom_components.unifi_network_monitor.number import WanLoadBalanceNumber

    coordinator = MagicMock()
    coordinator.data = {"gateway": {"wan1_weight": 50}}
    coordinator.async_add_listener = MagicMock()
    coordinator.async_set_wan_weights = AsyncMock(return_value=outcome)
    entry = MagicMock()
    entry.unique_id = "aa:bb:cc:dd:ee:ff"

    number = WanLoadBalanceNumber(coordinator, entry)
    number.hass = hass

    with caplog.at_level(logging.DEBUG):
        await number._apply(70.0)

    coordinator.async_set_wan_weights.assert_awaited_once_with(70)
    records = [r for r in caplog.records if "load balance weight" in r.message]
    if level is None:
        assert not records
    else:
        assert [r.levelname for r in records] == [level]


async def test_debounced_write_base_requires_an_apply() -> None:
    """The mixin is abstract: a subclass that forgets ``_apply`` fails loudly.

    Silently doing nothing is the failure mode this whole phase is about.
    """
    from custom_components.unifi_network_monitor.number import _DebouncedWriteEntity

    with pytest.raises(NotImplementedError):
        await _DebouncedWriteEntity()._apply(1.0)
