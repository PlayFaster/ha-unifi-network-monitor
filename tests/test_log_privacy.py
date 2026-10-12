"""Logging privacy and accuracy (dev_standards §20; chore C-020).

The tests assert the property rather than a message: no ``_LOGGER`` call in the
component passes a raw MAC, and a failing poll never puts a planted MAC,
hostname or SSID into the log.
"""

from __future__ import annotations

import ast
import logging
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.unifi_network_monitor.api import UnifiConnectionError
from custom_components.unifi_network_monitor.coordinator import (
    UnifiNetworkDataUpdateCoordinator,
)

COMPONENT = Path(__file__).parent.parent / "custom_components" / "unifi_network_monitor"
_LOG_METHODS = {"debug", "info", "warning", "error", "exception", "critical", "log"}
_MASKS = {"mask_identity", "device_token"}

PLANTED_MAC = "aa:00:00:00:00:99"
PLANTED_HOST = "kitchen-laptop-planted"
PLANTED_SSID = "Planted Neighbour SSID"


def _raw_mac_args(node: ast.Call) -> list[int]:
    """Line numbers of arguments that read a ``mac`` field without masking it."""
    hits = []
    for arg in node.args[1:]:
        for sub in ast.walk(arg):
            if (
                isinstance(sub, ast.Call)
                and isinstance(sub.func, ast.Attribute)
                and sub.func.attr in _MASKS
            ):
                break
            if (
                isinstance(sub, ast.Call)
                and isinstance(sub.func, ast.Attribute)
                and sub.func.attr == "get"
                and sub.args
                and isinstance(sub.args[0], ast.Constant)
                and sub.args[0].value == "mac"
            ):
                hits.append(sub.lineno)
            if isinstance(sub, ast.Subscript) and isinstance(sub.slice, ast.Constant):
                if sub.slice.value == "mac":
                    hits.append(sub.lineno)
    return hits


def test_no_logger_call_passes_a_raw_mac() -> None:
    """No ``_LOGGER`` call in the component interpolates an unmasked ``mac``."""
    offenders = []
    calls = 0
    for path in sorted(COMPONENT.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in _LOG_METHODS
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "_LOGGER"
            ):
                calls += 1
                offenders += [f"{path.name}:{line}" for line in _raw_mac_args(node)]
    assert calls > 30, "the sweep found too few logger calls to mean anything"
    assert offenders == []


def _api(**overrides: Any) -> MagicMock:
    api = MagicMock()
    for name in (
        "get_devices",
        "get_health",
        "get_sysinfo",
        "get_networkconf",
        "get_settings",
        "get_daily_gateway",
        "get_monthly_gateway",
        "get_rogueaps",
        "get_guests",
        "get_backups",
        "get_speedtest_results",
        "get_wlanconf",
        "get_system_logs",
        "get_sites",
    ):
        setattr(api, name, AsyncMock(return_value=overrides.get(name, [])))
    return api


async def test_a_failing_device_parse_logs_no_identity(
    hass: Any, mock_config_entry: Any, caplog: pytest.LogCaptureFixture
) -> None:
    """A device that fails to parse is logged by masked MAC, never by name or MAC."""
    mock_config_entry.add_to_hass(hass)
    device = {
        "mac": PLANTED_MAC,
        "state": 1,
        "type": "usw",
        "name": PLANTED_HOST,
        "hostname": PLANTED_HOST,
        "essid": PLANTED_SSID,
    }
    api = _api(get_devices=[device])
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    coordinator.site_uuid = "failed"
    with (
        caplog.at_level(logging.DEBUG),
        patch(
            "custom_components.unifi_network_monitor.coordinator._parse_switch",
            side_effect=ValueError("bad record"),
        ),
    ):
        await coordinator._async_update_data()
    assert "Failed to parse device" in caplog.text
    assert "**:**:**:**:00:99" in caplog.text
    for value in (PLANTED_MAC, PLANTED_HOST, PLANTED_SSID):
        assert value.lower() not in caplog.text.lower()


async def test_strike_budget_is_interpolated(
    hass: Any, mock_config_entry: Any, caplog: pytest.LogCaptureFixture
) -> None:
    """The held-values warning reports the configured strike budget, not 3."""
    mock_config_entry.add_to_hass(hass)
    api = _api()
    api.get_devices = AsyncMock(side_effect=UnifiConnectionError("down"))
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    coordinator.data = {"gateway": {}}
    with (
        caplog.at_level(logging.WARNING),
        patch(
            "custom_components.unifi_network_monitor.coordinator.FETCH_STRIKE_LIMIT", 5
        ),
    ):
        await coordinator._async_update_data()
    assert "failure 1/5" in caplog.text


async def test_an_empty_exception_names_its_class(
    hass: Any, mock_config_entry: Any, caplog: pytest.LogCaptureFixture
) -> None:
    """A ``TimeoutError()`` with no message is named in the warning."""
    mock_config_entry.add_to_hass(hass)
    api = _api()
    api.get_devices = AsyncMock(side_effect=TimeoutError())
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    coordinator.data = {"gateway": {}}
    with caplog.at_level(logging.WARNING):
        await coordinator._async_update_data()
    assert "holding last values: TimeoutError" in caplog.text
