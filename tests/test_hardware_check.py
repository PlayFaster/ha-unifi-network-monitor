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


def test_missing_ifname_falls_back_to_the_coordinator_default() -> None:
    """Without a reported port, the coordinator's defaults apply."""
    assert _resolve_ifname([{"model": "UDMPRO"}], "wan1") == "eth8"
    assert _resolve_ifname([], "wan2") == "eth9"


def test_a_port_name_passes_through_unchanged() -> None:
    """A value that is not ``wan1`` / ``wan2`` is sent as given."""
    assert _resolve_ifname([_GATEWAY], "eth8") == "eth8"
