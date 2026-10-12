"""The gateway parser on payloads shaped unlike a UDM Pro (v1.1.0-dev12 I8).

An unseen gateway must work or degrade without error: an absent block makes
its sensors unavailable (``None``), never zero, and leaves the rest intact.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from unittest.mock import AsyncMock

import pytest

from custom_components.unifi_network_monitor.coordinator import (
    UnifiNetworkDataUpdateCoordinator,
    _parse_gateway,
)
from homeassistant.util import dt as dt_util
from tests.test_coordinator_branches import _api

_FULL: dict[str, Any] = {
    "mac": "aa:bb:cc:dd:ee:ff",
    "name": "Gateway",
    "model": "UDMPRO",
    "type": "udm",
    "state": 1,
    "uptime": 3600,
    "system-stats": {"cpu": "12.5", "mem": "40.0"},
    "temperatures": [
        {"type": "cpu", "value": 60.0},
        {"type": "board", "value": 41.5},
    ],
    "storage": [{"mount_point": "/persistent", "used": 50, "size": 200}],
    "wan1": {"ifname": "eth8", "is_uplink": True, "up": True, "latency": 9},
    "wan2": {"ifname": "eth9", "is_uplink": False, "up": True, "latency": 12},
}


def _variant(**changes: Any) -> dict[str, Any]:
    device = deepcopy(_FULL)
    for key, value in changes.items():
        if value is _DROP:
            device.pop(key, None)
        else:
            device[key] = value
    return device


_DROP = object()


def _parse(device: dict[str, Any]) -> dict[str, Any]:
    return _parse_gateway(device, dt_util.now())


def test_full_payload_baseline() -> None:
    """The reference payload fills every field the variants below remove."""
    result = _parse(deepcopy(_FULL))
    assert result["cpu"] == 12.5
    assert result["cpu_temp"] == 60.0
    assert result["storage_used_pct"] == 25.0
    assert result["wan1_active"] is True
    assert result["wan2_up"] is True


def test_no_temperatures() -> None:
    """Temperatures absent: both unavailable, the rest intact."""
    result = _parse(_variant(temperatures=_DROP))
    assert result["cpu_temp"] is None
    assert result["board_temp"] is None
    assert result["cpu"] == 12.5
    assert result["wan1_latency"] == 9


def test_no_storage() -> None:
    """Storage absent: storage sensors unavailable, not zero."""
    result = _parse(_variant(storage=_DROP))
    assert result["storage_used"] is None
    assert result["storage_size"] is None
    assert result["storage_used_pct"] is None
    assert result["cpu_temp"] == 60.0


def test_no_system_stats() -> None:
    """System stats absent: CPU and RAM unavailable, not zero."""
    result = _parse(_variant(**{"system-stats": _DROP}))
    assert result["cpu"] is None
    assert result["ram"] is None
    assert result["storage_used_pct"] == 25.0


def test_no_wan2() -> None:
    """A single-WAN gateway: WAN2 unknown, not down; WAN1 intact."""
    result = _parse(_variant(wan2=_DROP))
    assert result["wan2_active"] is None
    assert result["wan2_up"] is None
    assert result["wan2_ifname"] is None
    assert result["wan1_active"] is True
    assert result["wan1_up"] is True


def test_wan1_without_ifname() -> None:
    """WAN1 with no port name: no default port, WAN1 state intact."""
    result = _parse(_variant(wan1={"is_uplink": True, "up": True, "latency": 9}))
    assert result["wan1_ifname"] is None
    assert result["wan1_up"] is True
    assert result["wan1_latency"] == 9


def test_wan1_none() -> None:
    """``wan1: None`` parses as an absent WAN1, without raising."""
    result = _parse(_variant(wan1=None))
    assert result["wan1_active"] is None
    assert result["wan1_up"] is None
    assert result["wan1_latency"] is None
    assert result["wan2_up"] is True


@pytest.mark.parametrize(
    "variant",
    [
        _variant(temperatures=_DROP),
        _variant(storage=_DROP),
        _variant(**{"system-stats": _DROP}),
        _variant(wan2=_DROP),
        _variant(wan1={"is_uplink": True, "up": True}),
        _variant(wan1=None),
        _variant(model="UNLISTED9"),
    ],
    ids=[
        "no_temperatures",
        "no_storage",
        "no_system_stats",
        "no_wan2",
        "wan1_no_ifname",
        "wan1_none",
        "unlisted_model_type_udm",
    ],
)
async def test_full_poll_on_each_variant(
    hass: Any, mock_config_entry: Any, variant: dict[str, Any]
) -> None:
    """A full poll selects the variant gateway and publishes its data."""
    mock_config_entry.add_to_hass(hass)
    api = _api(get_devices=AsyncMock(return_value=[variant]))
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)

    result = await coordinator._async_update_data()

    assert coordinator.gateway_selection is not None
    assert coordinator.gateway_selection.device is variant
    assert result["gateway"]["mac"] == "aa:bb:cc:dd:ee:ff"
