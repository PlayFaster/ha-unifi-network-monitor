"""Port-name resolution in ``scripts/hardware_check.py``.

``cmd/devmgr`` refuses the logical WAN name with a bare HTTP 400, so the script
must send the gateway's port name, as ``UnifiSpeedtestButton`` does.
"""

from __future__ import annotations

from scripts.hardware_check import _resolve_ifname

_GATEWAY = {
    "model": "UDMPRO",
    "wan1": {"ifname": "eth9"},
    "wan2": {"ifname": "eth8"},
}
_SWITCH = {"model": "USW24", "wan1": {"ifname": "eth0"}}


def test_logical_name_resolves_to_the_gateway_port() -> None:
    """A later gateway is found past a non-gateway device listed first."""
    assert _resolve_ifname([_SWITCH, _GATEWAY], "wan1") == "eth9"
    assert _resolve_ifname([_SWITCH, _GATEWAY], "wan2") == "eth8"


def test_missing_ifname_resolves_to_none() -> None:
    """Without a reported port there is no default; the check skips (I7)."""
    assert _resolve_ifname([{"model": "UDMPRO"}], "wan1") is None
    assert _resolve_ifname([], "wan2") is None


def test_a_logical_name_on_a_gateway_with_port_eth4_resolves_to_eth4() -> None:
    """A gateway reporting ``eth4`` is sent ``eth4``, not a UDM Pro port."""
    gateway = {"model": "UDRULT", "type": "udm", "wan1": {"ifname": "eth4"}}
    assert _resolve_ifname([gateway], "wan1") == "eth4"
    assert _resolve_ifname([gateway], "eth4") == "eth4"


def test_a_port_name_passes_through_unchanged() -> None:
    """A value that is not ``wan1`` / ``wan2`` is sent as given."""
    assert _resolve_ifname([_GATEWAY], "eth8") == "eth8"


async def test_a_gateway_without_a_port_is_a_skip_and_sends_nothing() -> None:
    """No port name: the check skips and never triggers a speedtest (I7)."""
    from unittest.mock import AsyncMock, MagicMock

    from scripts.hardware_check import _check_speedtest

    api = MagicMock()
    api.get_devices = AsyncMock(return_value=[{"model": "UDRULT", "wan1": {}}])
    api.trigger_speedtest = AsyncMock()

    assert await _check_speedtest(api, "wan1", timeout=1) is None
    api.trigger_speedtest.assert_not_awaited()
