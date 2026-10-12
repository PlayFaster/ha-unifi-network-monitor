"""Teardown contract — the session is ended, not merely dropped.

**item 18** of the August 2026 plan (§M Phase 2), and changelog §10's `PENDING`
row. The code has always awaited ``logout()``; what was missing was the test.
That distinction matters: the call sits inside a ``try`` whose ``except`` is
deliberately broad, so deleting the ``await`` leaves a suite that still passes
and a controller accumulating an orphaned session per reload.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.unifi_network_monitor import async_unload_entry
from custom_components.unifi_network_monitor.api import UnifiConnectionError


def _coordinator() -> MagicMock:
    coordinator = MagicMock()
    coordinator.async_flush_stores = AsyncMock()
    coordinator.api.logout = AsyncMock()
    return coordinator


async def test_unload_awaits_logout(hass: Any, mock_config_entry: Any) -> None:
    """The session-terminating call is awaited, not merely scheduled."""
    mock_config_entry.add_to_hass(hass)
    coordinator = _coordinator()
    mock_config_entry.runtime_data = coordinator

    with patch.object(
        hass.config_entries, "async_unload_platforms", AsyncMock(return_value=True)
    ):
        assert await async_unload_entry(hass, mock_config_entry) is True

    coordinator.api.logout.assert_awaited_once()


async def test_unload_flushes_stores_before_logging_out(
    hass: Any, mock_config_entry: Any
) -> None:
    """Order matters: a flush after the session ends could need a live session.

    A reload fires no ``HOMEASSISTANT_STOP``, so the coalesced ``async_delay_save``
    is only written here — and writing it must not depend on a session that has
    already been torn down.
    """
    mock_config_entry.add_to_hass(hass)
    order: list[str] = []
    coordinator = MagicMock()
    coordinator.async_flush_stores = AsyncMock(
        side_effect=lambda: order.append("flush")
    )
    coordinator.api.logout = AsyncMock(side_effect=lambda: order.append("logout"))
    mock_config_entry.runtime_data = coordinator

    with patch.object(
        hass.config_entries, "async_unload_platforms", AsyncMock(return_value=True)
    ):
        await async_unload_entry(hass, mock_config_entry)

    assert order == ["flush", "logout"]


async def test_unload_still_unloads_when_logout_fails(
    hass: Any, mock_config_entry: Any
) -> None:
    """A controller that cannot be reached must not block the unload.

    Refusing to unload would leave the entry wedged in a half-loaded state that
    only a restart clears — much worse than an orphaned server-side session.
    """
    mock_config_entry.add_to_hass(hass)
    coordinator = _coordinator()
    coordinator.api.logout = AsyncMock(side_effect=UnifiConnectionError("unreachable"))
    mock_config_entry.runtime_data = coordinator

    with patch.object(
        hass.config_entries, "async_unload_platforms", AsyncMock(return_value=True)
    ):
        assert await async_unload_entry(hass, mock_config_entry) is True

    coordinator.api.logout.assert_awaited_once()


async def test_unload_propagates_the_platform_unload_result(
    hass: Any, mock_config_entry: Any
) -> None:
    """A platform that refuses to unload is reported, not swallowed."""
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = _coordinator()

    with patch.object(
        hass.config_entries, "async_unload_platforms", AsyncMock(return_value=False)
    ):
        assert await async_unload_entry(hass, mock_config_entry) is False


# ---------------------------------------------------------------------------
# Number platform setup — both option branches
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("dual_wan", "security", "expected"),
    [
        (True, True, 3),
        (False, True, 2),
        (True, False, 2),
        (False, False, 1),
    ],
)
async def test_number_setup_honours_both_toggles(
    hass: Any, dual_wan: bool, security: bool, expected: int
) -> None:
    """Each optional number is created only when its own toggle is on.

    Both off is included deliberately: it is the combination no earlier test
    exercised, and it is the one where a mistaken ``or`` for an ``and`` would
    still create an entity fed by an endpoint that is no longer fetched.
    """
    from custom_components.unifi_network_monitor.number import async_setup_entry

    coordinator = MagicMock()
    coordinator.data = {"gateway": {}}
    coordinator.async_add_listener = MagicMock()
    entry = MagicMock()
    entry.unique_id = "aa:bb:cc:dd:ee:ff"
    entry.runtime_data = coordinator
    entry.options = {
        "enable_dual_wan": dual_wan,
        "enable_security_monitoring": security,
    }

    added: list[Any] = []
    await async_setup_entry(hass, entry, lambda new: added.extend(new))

    assert len(added) == expected
