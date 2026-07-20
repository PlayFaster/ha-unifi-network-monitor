"""Tests for the UniFi Network Monitor diagnostics."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from .conftest import MOCK_COORDINATOR_DATA, MOCK_MAC


def _make_coordinator(data: dict[str, Any] | None) -> MagicMock:
    coord = MagicMock()
    coord.data = data
    coord.gateway_mac = MOCK_MAC
    coord.gateway_model = "UDMPRO"
    coord.sw_version = "5.1.19.33549"
    coord.consecutive_failures = 0
    coord.last_update_success = True
    coord.last_update_success_time = None
    coord.async_add_listener = MagicMock()
    return coord


def _make_entry() -> MagicMock:
    entry = MagicMock()
    entry.unique_id = MOCK_MAC
    entry.title = "UniFi Network"
    entry.data = {
        "mac": MOCK_MAC,
        "model": "UDMPRO",
        "sw_version": "5.1.19.33549",
    }
    entry.options = {
        "host": "192.168.1.1",
        "api_key": "test-api-key-abc123",
        "username": "",
        "password": "",
        "site": "default",
        "scan_interval": 30,
    }
    return entry


async def test_diagnostics_returns_expected_structure(hass: Any) -> None:
    """Diagnostics returns dict with entry, coordinator, data keys."""
    from custom_components.unifi_network_monitor.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    entry.runtime_data = coordinator

    result = await async_get_config_entry_diagnostics(hass, entry)
    assert "entry" in result
    assert "coordinator" in result
    assert "data" in result


async def test_diagnostics_redacts_sensitive_fields(hass: Any) -> None:
    """Diagnostics redacts api_key in entry options."""
    from custom_components.unifi_network_monitor.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    entry.runtime_data = coordinator

    result = await async_get_config_entry_diagnostics(hass, entry)
    redacted_options = result["entry"]["options"]
    assert redacted_options.get("api_key") == "**REDACTED**"


async def test_diagnostics_redacts_host_and_wan_ips(hass: Any) -> None:
    """Diagnostics redacts the host and the WAN local/public IP addresses."""
    from custom_components.unifi_network_monitor.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    entry.runtime_data = coordinator

    result = await async_get_config_entry_diagnostics(hass, entry)
    assert result["entry"]["options"].get("host") == "**REDACTED**"
    gateway = result["data"]["gateway"]
    assert gateway["wan1_public_ip"] == "**REDACTED**"
    assert gateway["wan2_public_ip"] == "**REDACTED**"
    assert gateway["wan1_local_ip"] == "**REDACTED**"


async def test_diagnostics_handles_no_update_time(hass: Any) -> None:
    """Diagnostics handles None last_update_success_time."""
    from custom_components.unifi_network_monitor.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    coordinator.last_update_success_time = None
    entry = _make_entry()
    entry.runtime_data = coordinator

    result = await async_get_config_entry_diagnostics(hass, entry)
    assert result["coordinator"]["last_update_success_time"] is None


async def test_diagnostics_handles_no_data(hass: Any) -> None:
    """Diagnostics handles None coordinator.data."""
    from custom_components.unifi_network_monitor.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    coordinator = _make_coordinator(None)
    entry = _make_entry()
    entry.runtime_data = coordinator

    result = await async_get_config_entry_diagnostics(hass, entry)
    assert result["coordinator"]["data_available"] is False
    assert result["data"] == {}


async def test_diagnostics_includes_coordinator_state(hass: Any) -> None:
    """Diagnostics includes consecutive_failures and gateway info."""
    from custom_components.unifi_network_monitor.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    coordinator.consecutive_failures = 3
    entry = _make_entry()
    entry.runtime_data = coordinator

    result = await async_get_config_entry_diagnostics(hass, entry)
    assert result["coordinator"]["consecutive_failures"] == 3
    assert result["coordinator"]["gateway_model"] == "UDMPRO"
    assert result["coordinator"]["sw_version"] == "5.1.19.33549"


# ---------------------------------------------------------------------------
# _Scrubber helper guards
# ---------------------------------------------------------------------------


def test_device_token_empty_returns_redacted() -> None:
    """device_token returns REDACTED for empty/falsy value (line 95)."""
    from custom_components.unifi_network_monitor.diagnostics import (
        REDACTED,
        _Scrubber,
    )

    scrub = _Scrubber()
    assert scrub.device_token("") == REDACTED
    assert scrub.device_token(None) == REDACTED
    assert scrub.device_token(REDACTED) == REDACTED


def test_rogue_token_empty_returns_redacted() -> None:
    """rogue_token returns REDACTED for empty value (line 111)."""
    from custom_components.unifi_network_monitor.diagnostics import (
        REDACTED,
        _Scrubber,
    )

    scrub = _Scrubber()
    assert scrub.rogue_token("") == REDACTED
    assert scrub.rogue_token(None) == REDACTED


def test_scrub_device_non_dict_returns_input() -> None:
    """_scrub_device returns non-dict input unchanged (line 161)."""
    from custom_components.unifi_network_monitor.diagnostics import _scrub_device

    scrub = MagicMock()
    assert _scrub_device(scrub, None) is None
    assert _scrub_device(scrub, "string") == "string"
    assert _scrub_device(scrub, 42) == 42


def test_scrub_alert_block_non_dict_returns_input() -> None:
    """_scrub_alert_block handles non-dict block (line 174)."""
    from custom_components.unifi_network_monitor.diagnostics import _scrub_alert_block

    scrub = MagicMock()
    scrub.text = MagicMock(side_effect=lambda x: f"scrubbed:{x}")
    result = _scrub_alert_block(scrub, "NAME", "free text")
    assert result == "scrubbed:free text"
    result = _scrub_alert_block(scrub, "NAME", None)
    assert result is None
    result = _scrub_alert_block(scrub, "NAME", 42)
    assert result == 42


def test_scrub_alert_non_dict_returns_input() -> None:
    """_scrub_alert returns non-dict input unchanged (line 198)."""
    from custom_components.unifi_network_monitor.diagnostics import _scrub_alert

    scrub = MagicMock()
    assert _scrub_alert(scrub, None) is None
    assert _scrub_alert(scrub, "string") == "string"
    assert _scrub_alert(scrub, 42) == 42


def test_scrub_rogue_entry_non_dict_returns_input() -> None:
    """_scrub_rogue_entry returns non-dict input unchanged (line 183)."""
    from custom_components.unifi_network_monitor.diagnostics import _scrub_rogue_entry

    scrub = MagicMock()
    assert _scrub_rogue_entry(scrub, None) is None
    assert _scrub_rogue_entry(scrub, "string") == "string"
    assert _scrub_rogue_entry(scrub, 42) == 42
