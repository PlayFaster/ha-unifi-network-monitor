"""A refused write raises. It never reports success having done nothing.

Cross-project chore `C-026`: every public write method either performs the
command or raises an exception — never returning a success-shaped result
having done nothing.
"""

from __future__ import annotations

import ast
from typing import Any

import pytest

from custom_components.unifi_network_monitor.api import (
    UnifiConnectionError,
    UnifiNetworkAPI,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .test_write_classification import _api_methods, _public_writes

_CALLS: dict[str, tuple[Any, ...]] = {
    "trigger_speedtest": ("eth8",),
    "update_networkconf": ("net1", {"wan_load_balance_weight": 50}),
}

# `test_write_classification._public_writes()` already excludes `login` and
# `logout` via `_NOT_A_DEVICE_WRITE`, so the write-refusal carve-out set is
# empty; `logout` teardown is verified separately below.
_CARVE_OUTS: frozenset[str] = frozenset()


def _unannotated_none(node: ast.AsyncFunctionDef) -> bool:
    """Return True when the return annotation is literal ``None``."""
    return isinstance(node.returns, ast.Constant) and node.returns.value is None


def _bare_value_returns(node: ast.AsyncFunctionDef) -> list[int]:
    """Return line numbers of any ``return <expr>`` inside ``node``."""
    return [
        sub.lineno
        for sub in ast.walk(node)
        if isinstance(sub, ast.Return) and sub.value is not None
    ]


@pytest.mark.parametrize("method_name", sorted(_CALLS))
@pytest.mark.parametrize(
    ("status", "payload"),
    [
        (400, {"meta": {"rc": "error", "msg": "api.err.Invalid"}, "data": []}),
        (200, {"meta": {"rc": "error", "msg": "api.err.Invalid"}, "data": []}),
    ],
)
async def test_a_refused_write_raises(
    method_name: str,
    status: int,
    payload: dict[str, Any],
    hass: HomeAssistant,
    aioclient_mock: Any,
) -> None:
    """Every public write raises on both HTTP errors and HTTP 200 rc=error."""
    aioclient_mock.post(
        "https://10.0.0.1/proxy/network/api/s/default/cmd/devmgr",
        status=status,
        json=payload,
    )
    aioclient_mock.put(
        "https://10.0.0.1/proxy/network/api/s/default/rest/networkconf/net1",
        status=status,
        json=payload,
    )
    session = async_get_clientsession(hass)
    api = UnifiNetworkAPI(session, "10.0.0.1", api_key="test-key")
    with pytest.raises(UnifiConnectionError):
        await getattr(api, method_name)(*_CALLS[method_name])


async def test_logout_teardown_carve_out(
    hass: HomeAssistant,
    aioclient_mock: Any,
) -> None:
    """Teardown logout tolerates transport/HTTP errors and clears session state."""
    aioclient_mock.post("https://10.0.0.1/api/auth/logout", status=500)
    session = async_get_clientsession(hass)
    api = UnifiNetworkAPI(session, "10.0.0.1", username="admin", password="secret")
    api._token = "tok"
    api._csrf = "csrf"
    await api.logout()
    assert api._token is None
    assert api._csrf is None


@pytest.mark.parametrize("method_name", sorted(_CALLS))
def test_every_write_is_annotated_to_return_none(method_name: str) -> None:
    """Every public write is annotated ``-> None``."""
    methods = _api_methods()
    assert _unannotated_none(methods[method_name]), (
        f"{method_name} must be annotated -> None"
    )


@pytest.mark.parametrize("method_name", sorted(_CALLS))
def test_no_write_contains_a_bare_return_of_a_value(method_name: str) -> None:
    """No public write returns a value."""
    methods = _api_methods()
    assert _bare_value_returns(methods[method_name]) == []


def test_every_write_is_in_the_refusal_sweep() -> None:
    """A new write in api.py fails until added to _CALLS or _CARVE_OUTS."""
    writes = _public_writes()
    covered = set(_CALLS) | _CARVE_OUTS
    missing = sorted(writes - covered)
    stale = sorted(covered - writes)
    assert not missing, f"Public writes missing from refusal sweep: {missing}"
    assert not stale, f"Entries no longer in _public_writes(): {stale}"


def test_the_carve_out_list_stays_closed() -> None:
    """The carve-out list stays closed."""
    assert not _CARVE_OUTS


def test_the_sweep_is_not_vacuous() -> None:
    """Guard against accidentally emptying _CALLS."""
    assert len(_CALLS) >= 2
