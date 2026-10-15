"""Logins are serialized (ZTE techniques row 9).

Named and shaped as in huawei_router_5g ``tests/test_api_lock_concurrency.py``.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import aiohttp

from custom_components.unifi_network_monitor.api import UnifiNetworkAPI


def _api_counting_logins() -> tuple[UnifiNetworkAPI, dict[str, int]]:
    api = UnifiNetworkAPI(
        MagicMock(spec=aiohttp.ClientSession), "192.0.2.1", username="u", password="p"
    )
    seen = {"in_flight": 0, "peak": 0, "done": 0}

    async def fake_login() -> None:
        seen["in_flight"] += 1
        seen["peak"] = max(seen["peak"], seen["in_flight"])
        await asyncio.sleep(0.01)
        seen["in_flight"] -= 1
        seen["done"] += 1

    api._login_unlocked = fake_login  # type: ignore[method-assign]
    return api, seen


async def test_two_logins_take_turns() -> None:
    """Two logins started together are serialized, and both complete."""
    api, seen = _api_counting_logins()
    await asyncio.gather(api.login(), api.login())
    assert seen["peak"] == 1
    assert seen["done"] == 2


async def test_the_count_sees_two_calls_without_the_lock() -> None:
    """The positive control: the same two calls unlocked show as 2."""
    api, seen = _api_counting_logins()
    await asyncio.gather(api._login_unlocked(), api._login_unlocked())
    assert seen["peak"] == 2
