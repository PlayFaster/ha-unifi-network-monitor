"""Tests for the UniFi Network Monitor button platform."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.unifi_network_monitor.api import UnifiConnectionError
from custom_components.unifi_network_monitor.const import (
    CONF_ENABLE_SECURITY_MONITORING,
    CONF_ENABLE_SPEEDTEST,
    CONF_ENABLE_WAN_USAGE,
    CONF_UNIFI_DEVICE_MODE,
)

from .conftest import MOCK_COORDINATOR_DATA, MOCK_MAC


def _make_coordinator(data: dict[str, Any] | None) -> MagicMock:
    coord = MagicMock()
    coord.data = data
    coord.gateway_mac = MOCK_MAC
    coord.gateway_model = "UDMPRO"
    coord.sw_version = "5.1.19.33549"
    coord.async_request_refresh = AsyncMock()
    coord.async_add_listener = MagicMock()
    coord.async_trigger_speedtest = AsyncMock()
    return coord


def _make_entry(unique_id: str = MOCK_MAC) -> MagicMock:
    entry = MagicMock()
    entry.unique_id = unique_id
    entry.title = "UniFi Network"
    entry.options = {
        "host": "192.168.1.1",
        CONF_UNIFI_DEVICE_MODE: "all",
        CONF_ENABLE_SPEEDTEST: True,
        CONF_ENABLE_WAN_USAGE: True,
        CONF_ENABLE_SECURITY_MONITORING: True,
    }
    return entry


async def test_async_setup_entry_creates_button(hass: Any) -> None:
    """async_setup_entry creates the refresh button."""
    entry = _make_entry()
    async_add_entities = MagicMock()

    with patch(
        "custom_components.unifi_network_monitor.button.UnifiRefreshButton"
    ) as mock_cls:
        from custom_components.unifi_network_monitor.button import async_setup_entry

        mock_button = MagicMock()
        mock_cls.return_value = mock_button
        await async_setup_entry(hass, entry, async_add_entities)
        async_add_entities.assert_called_once()
        called_entities = async_add_entities.call_args[0][0]
        assert mock_button in called_entities
        assert len(called_entities) == 4


async def test_button_press_calls_refresh() -> None:
    """async_press calls coordinator.async_request_refresh."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()

    from custom_components.unifi_network_monitor.button import UnifiRefreshButton

    button = UnifiRefreshButton(coordinator, entry)
    await button.async_press()
    coordinator.async_request_refresh.assert_awaited_once()


def test_button_unique_id() -> None:
    """Button unique_id is entry.unique_id + _refresh."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry("aa:bb:cc:dd:ee:ff")

    from custom_components.unifi_network_monitor.button import UnifiRefreshButton

    button = UnifiRefreshButton(coordinator, entry)
    assert button.unique_id == "aa:bb:cc:dd:ee:ff_refresh"


def test_button_device_info() -> None:
    """Button device_info matches gateway device."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()

    from custom_components.unifi_network_monitor.button import UnifiRefreshButton

    button = UnifiRefreshButton(coordinator, entry)
    info = button.device_info
    assert info is not None


def test_button_entity_attributes() -> None:
    """Button has correct entity attributes."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()

    from custom_components.unifi_network_monitor.button import UnifiRefreshButton

    button = UnifiRefreshButton(coordinator, entry)
    assert button._attr_has_entity_name is True
    assert button._attr_should_poll is False
    assert button.entity_description.key == "refresh"


# ------------------------------------------------------------------
# Speedtest button coverage
# ------------------------------------------------------------------


async def test_speedtest_button_press_triggers_with_ifname() -> None:
    """UnifiSpeedtestButton.async_press passes wan1_ifname to coordinator."""
    coordinator = _make_coordinator(
        {
            **MOCK_COORDINATOR_DATA,
            "gateway": {
                **MOCK_COORDINATOR_DATA["gateway"],
                "wan1_ifname": "eth8",
            },
        }
    )
    entry = _make_entry()

    from custom_components.unifi_network_monitor.button import (
        _WAN1_SPEEDTEST_DESCRIPTION,
        UnifiSpeedtestButton,
    )

    button = UnifiSpeedtestButton(
        coordinator, entry, _WAN1_SPEEDTEST_DESCRIPTION, "wan1"
    )
    await button.async_press()
    coordinator.async_trigger_speedtest.assert_awaited_with("eth8")


async def test_speedtest_button_press_no_ifname() -> None:
    """UnifiSpeedtestButton.async_press passes None when ifname not in data."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()

    from custom_components.unifi_network_monitor.button import (
        _WAN1_SPEEDTEST_DESCRIPTION,
        UnifiSpeedtestButton,
    )

    button = UnifiSpeedtestButton(
        coordinator, entry, _WAN1_SPEEDTEST_DESCRIPTION, "wan1"
    )
    await button.async_press()
    coordinator.async_trigger_speedtest.assert_awaited_with(None)


async def test_speedtest_button_press_none_data() -> None:
    """Pressing the speedtest button before the first poll does not crash."""
    coordinator = _make_coordinator(None)
    entry = _make_entry()

    from custom_components.unifi_network_monitor.button import (
        _WAN1_SPEEDTEST_DESCRIPTION,
        UnifiSpeedtestButton,
    )

    button = UnifiSpeedtestButton(
        coordinator, entry, _WAN1_SPEEDTEST_DESCRIPTION, "wan1"
    )
    await button.async_press()
    coordinator.async_trigger_speedtest.assert_awaited_with(None)


async def test_speedtest_button_press_wraps_error() -> None:
    """A UnifiError from the trigger is surfaced as HomeAssistantError."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    coordinator.async_trigger_speedtest = AsyncMock(
        side_effect=UnifiConnectionError("boom")
    )
    entry = _make_entry()

    from custom_components.unifi_network_monitor.button import (
        _WAN1_SPEEDTEST_DESCRIPTION,
        UnifiSpeedtestButton,
    )

    button = UnifiSpeedtestButton(
        coordinator, entry, _WAN1_SPEEDTEST_DESCRIPTION, "wan1"
    )
    with pytest.raises(HomeAssistantError) as exc_info:
        await button.async_press()
    assert exc_info.value.translation_key == "speedtest_failed"


# ------------------------------------------------------------------
# Cleanup button coverage
# ------------------------------------------------------------------


async def test_cleanup_button_empty_plan_returns_early() -> None:
    """UnifiCleanupButton.async_press returns early when plan is empty."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()

    from custom_components.unifi_network_monitor.button import UnifiCleanupButton

    button = UnifiCleanupButton(coordinator, entry)

    with (
        patch(
            "custom_components.unifi_network_monitor.button.plan_device_cleanup",
            return_value=MagicMock(is_empty=True),
        ) as mock_plan,
        patch(
            "custom_components.unifi_network_monitor.button.apply_cleanup",
        ) as mock_apply,
    ):
        await button.async_press()
    mock_apply.assert_not_called()


async def test_cleanup_button_applies_and_reloads() -> None:
    """Apply cleanup and reload when plan has entities."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    hass = MagicMock()

    from custom_components.unifi_network_monitor.button import UnifiCleanupButton

    button = UnifiCleanupButton(coordinator, entry)
    # Set the hass reference since ButtonEntity has a hass attribute
    button.hass = hass

    mock_plan = MagicMock()
    mock_plan.is_empty = False
    mock_plan.entity_ids = ["sensor.test"]

    with (
        patch(
            "custom_components.unifi_network_monitor.button.plan_device_cleanup",
            return_value=mock_plan,
        ) as mock_plan_fn,
        patch(
            "custom_components.unifi_network_monitor.button.apply_cleanup",
        ) as mock_apply,
    ):
        await button.async_press()

    mock_plan_fn.assert_called_once()
    mock_apply.assert_called_once()


async def test_cleanup_button_with_devices() -> None:
    """UnifiCleanupButton applies cleanup when plan has devices."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    hass = MagicMock()

    from custom_components.unifi_network_monitor.button import UnifiCleanupButton

    button = UnifiCleanupButton(coordinator, entry)
    button.hass = hass

    mock_plan = MagicMock()
    mock_plan.is_empty = False
    mock_plan.entity_ids = []
    mock_plan.device_ids = ["device_1"]

    with (
        patch(
            "custom_components.unifi_network_monitor.button.plan_device_cleanup",
            return_value=mock_plan,
        ) as mock_plan_fn,
        patch(
            "custom_components.unifi_network_monitor.button.apply_cleanup",
        ) as mock_apply,
    ):
        await button.async_press()

    mock_plan_fn.assert_called_once()
    mock_apply.assert_called_once()
