"""Tests for the UniFi Network Monitor number platform."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.unifi_network_monitor.const import CONF_SCAN_INTERVAL

from .conftest import MOCK_COORDINATOR_DATA, MOCK_MAC


def _make_coordinator(data: dict[str, Any] | None) -> MagicMock:
    coord = MagicMock()
    coord.data = data
    coord.gateway_mac = MOCK_MAC
    coord.gateway_model = "UDMPRO"
    coord.sw_version = "5.1.19.33549"
    coord.async_request_refresh = AsyncMock()
    coord.async_force_refresh = AsyncMock()
    coord.async_add_listener = MagicMock()
    return coord


def _make_entry(unique_id: str = MOCK_MAC) -> MagicMock:
    entry = MagicMock()
    entry.unique_id = unique_id
    entry.title = "UniFi Network"
    entry.options = {
        "host": "192.168.1.1",
        CONF_SCAN_INTERVAL: 30,
    }
    return entry


@patch("custom_components.unifi_network_monitor.number.build_sub_device_info")
async def test_async_setup_entry_creates_number(
    mock_build: MagicMock, hass: Any
) -> None:
    """async_setup_entry creates the scan interval number entity."""
    entry = _make_entry()
    async_add_entities = MagicMock()

    from custom_components.unifi_network_monitor.number import async_setup_entry

    await async_setup_entry(hass, entry, async_add_entities)
    async_add_entities.assert_called_once()
    entity = async_add_entities.call_args[0][0][0]
    assert entity.unique_id == f"{MOCK_MAC}_scan_interval"
    assert entity.native_value == 30


def test_number_unique_id() -> None:
    """Number unique_id is entry.unique_id + _scan_interval."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry("aa:bb:cc:dd:ee:ff")

    from custom_components.unifi_network_monitor.number import (
        UnifiScanIntervalNumber,
    )

    number = UnifiScanIntervalNumber(coordinator, entry, 30)
    assert number.unique_id == "aa:bb:cc:dd:ee:ff_scan_interval"


def test_number_native_min_max() -> None:
    """Number has correct min/max constraints."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()

    from custom_components.unifi_network_monitor.number import (
        UnifiScanIntervalNumber,
    )

    number = UnifiScanIntervalNumber(coordinator, entry, 30)
    assert number.native_min_value == 10
    assert number.native_max_value == 3600
    assert number.native_step == 10


def test_number_initial_value() -> None:
    """Number entity stores initial value."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()

    from custom_components.unifi_network_monitor.number import (
        UnifiScanIntervalNumber,
    )

    number = UnifiScanIntervalNumber(coordinator, entry, 60)
    assert number.native_value == 60


async def test_number_set_native_value_updates_state(hass: Any) -> None:
    """Setting value updates native_value and writes state."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()

    from custom_components.unifi_network_monitor.number import (
        UnifiScanIntervalNumber,
    )

    number = UnifiScanIntervalNumber(coordinator, entry, 30)
    number.hass = hass

    with patch.object(number, "async_write_ha_state") as mock_write:
        await number.async_set_native_value(60)

    assert number.native_value == 60
    mock_write.assert_called_once()


def test_number_device_info() -> None:
    """Number device_info matches gateway device."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()

    from custom_components.unifi_network_monitor.number import (
        UnifiScanIntervalNumber,
    )

    number = UnifiScanIntervalNumber(coordinator, entry, 30)
    info = number.device_info
    assert info is not None


async def test_number_will_remove_from_hass_cancels_debounce(hass: Any) -> None:
    """Removing the entity cancels any pending debounce task."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()

    from custom_components.unifi_network_monitor.number import (
        UnifiScanIntervalNumber,
    )

    number = UnifiScanIntervalNumber(coordinator, entry, 30)
    number.hass = hass
    fut = asyncio.get_event_loop().create_future()
    number._debounce_task = fut
    await number.async_will_remove_from_hass()


async def test_apply_after_debounce_refreshes_coordinator(hass: Any) -> None:
    """_apply_after_debounce calls async_request_refresh after updating options."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()

    from custom_components.unifi_network_monitor.number import (
        UnifiScanIntervalNumber,
    )

    number = UnifiScanIntervalNumber(coordinator, entry, 30)
    number.hass = hass
    hass.config_entries.async_update_entry = MagicMock()

    await number._apply_after_debounce(60)
    coordinator.async_force_refresh.assert_awaited_once()


async def test_apply_after_debounce_handles_exception(hass: Any) -> None:
    """_apply_after_debounce handles exceptions gracefully."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()

    from custom_components.unifi_network_monitor.number import (
        UnifiScanIntervalNumber,
    )

    number = UnifiScanIntervalNumber(coordinator, entry, 30)
    number.hass = hass
    coordinator.async_request_refresh = AsyncMock(
        side_effect=Exception("refresh error")
    )

    await number._apply_after_debounce(60)


async def test_async_set_native_value_cancels_prior_debounce(hass: Any) -> None:
    """Setting value cancels prior pending debounce."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()

    from custom_components.unifi_network_monitor.number import (
        UnifiScanIntervalNumber,
    )

    number = UnifiScanIntervalNumber(coordinator, entry, 30)
    number.hass = hass
    fut = asyncio.get_event_loop().create_future()
    number._debounce_task = fut

    with (
        patch.object(number, "_apply_after_debounce", MagicMock()),
        patch.object(number, "async_write_ha_state"),
        patch.object(hass, "async_create_task"),
    ):
        await number.async_set_native_value(60)
        assert number._debounce_task is not None
        assert number._debounce_task.cancelled()


# ---------------------------------------------------------------------------
# WAN Load Balance Number tests
# ---------------------------------------------------------------------------


def _make_wlb_coordinator(data: dict[str, Any] | None) -> MagicMock:
    coord = MagicMock()
    coord.data = data
    coord.gateway_mac = MOCK_MAC
    coord.gateway_model = "UDMPRO"
    coord.sw_version = "5.1.19.33549"
    coord.async_request_refresh = AsyncMock()
    coord.async_force_refresh = AsyncMock()
    coord.async_add_listener = MagicMock()
    coord.async_set_wan_weights = AsyncMock()
    return coord


def test_wan_load_balance_native_value() -> None:
    """WanLoadBalanceNumber native_value reads wan1_weight from coordinator."""
    coordinator = _make_wlb_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()

    from custom_components.unifi_network_monitor.number import (
        WanLoadBalanceNumber,
    )

    number = WanLoadBalanceNumber(coordinator, entry)
    assert number.native_value == pytest.approx(55.0)


def test_wan_load_balance_native_value_no_data() -> None:
    """WanLoadBalanceNumber native_value is None when coordinator data is None."""
    coordinator = _make_wlb_coordinator(None)
    entry = _make_entry()

    from custom_components.unifi_network_monitor.number import (
        WanLoadBalanceNumber,
    )

    number = WanLoadBalanceNumber(coordinator, entry)
    assert number.native_value is None


def test_wan_load_balance_native_value_missing_key() -> None:
    """WanLoadBalanceNumber native_value is None when wan1_weight is missing."""
    data = {**MOCK_COORDINATOR_DATA, "gateway": {"mac": "aa:bb:cc:dd:ee:ff"}}
    coordinator = _make_wlb_coordinator(data)
    entry = _make_entry()

    from custom_components.unifi_network_monitor.number import (
        WanLoadBalanceNumber,
    )

    number = WanLoadBalanceNumber(coordinator, entry)
    assert number.native_value is None


def test_wan_load_balance_unique_id() -> None:
    """WanLoadBalanceNumber unique_id includes _wan1_load_balance_weight."""
    coordinator = _make_wlb_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry("aa:bb:cc:dd:ee:ff")

    from custom_components.unifi_network_monitor.number import (
        WanLoadBalanceNumber,
    )

    number = WanLoadBalanceNumber(coordinator, entry)
    assert number.unique_id == "aa:bb:cc:dd:ee:ff_wan1_load_balance_weight"


def test_wan_load_balance_device_info() -> None:
    """WanLoadBalanceNumber device_info matches gateway."""
    coordinator = _make_wlb_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()

    from custom_components.unifi_network_monitor.number import (
        WanLoadBalanceNumber,
    )

    number = WanLoadBalanceNumber(coordinator, entry)
    assert number.device_info is not None


async def test_wan_load_balance_set_native_value(hass: Any) -> None:
    """Setting value writes state and schedules debounce apply."""
    coordinator = _make_wlb_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()

    from custom_components.unifi_network_monitor.number import (
        WanLoadBalanceNumber,
    )

    number = WanLoadBalanceNumber(coordinator, entry)
    number.hass = hass

    with patch.object(number, "async_write_ha_state") as mock_write:
        await number.async_set_native_value(70.0)

    mock_write.assert_called_once()
    assert number._debounce_task is not None


async def test_wan_load_balance_set_native_value_cancels_prior(hass: Any) -> None:
    """Setting value cancels prior pending debounce."""
    coordinator = _make_wlb_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()

    from custom_components.unifi_network_monitor.number import (
        WanLoadBalanceNumber,
    )

    number = WanLoadBalanceNumber(coordinator, entry)
    number.hass = hass
    import asyncio

    fut = asyncio.get_event_loop().create_future()
    number._debounce_task = fut

    with (
        patch.object(number, "_apply_after_debounce", MagicMock()),
        patch.object(number, "async_write_ha_state"),
        patch.object(hass, "async_create_task"),
    ):
        await number.async_set_native_value(60)
        assert number._debounce_task is not None
        assert number._debounce_task.cancelled()


async def test_wan_load_balance_apply_after_debounce(hass: Any) -> None:
    """_apply_after_debounce calls async_set_wan_weights after delay."""
    coordinator = _make_wlb_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()

    from custom_components.unifi_network_monitor.number import (
        WanLoadBalanceNumber,
    )

    number = WanLoadBalanceNumber(coordinator, entry)
    number.hass = hass

    await number._apply_after_debounce(70)
    coordinator.async_set_wan_weights.assert_awaited_once_with(70)


async def test_wan_load_balance_apply_after_debounce_logs_error(
    hass: Any,
) -> None:
    """_apply_after_debounce logs and swallows expected errors (detached task)."""
    from custom_components.unifi_network_monitor.api import UnifiConnectionError
    from custom_components.unifi_network_monitor.number import (
        WanLoadBalanceNumber,
    )

    coordinator = _make_wlb_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    number = WanLoadBalanceNumber(coordinator, entry)
    number.hass = hass
    coordinator.async_set_wan_weights = AsyncMock(
        side_effect=UnifiConnectionError("API error")
    )

    # Detached task: the failure is logged, not raised.
    await number._apply_after_debounce(80)


async def test_wan_load_balance_set_value_raises_when_not_writable(
    hass: Any,
) -> None:
    """Setting the weight before WAN config is loaded raises HomeAssistantError."""
    from homeassistant.exceptions import HomeAssistantError

    from custom_components.unifi_network_monitor.number import (
        WanLoadBalanceNumber,
    )

    coordinator = _make_wlb_coordinator(MOCK_COORDINATOR_DATA)
    coordinator.wan_weights_writable = False
    entry = _make_entry()
    number = WanLoadBalanceNumber(coordinator, entry)
    number.hass = hass

    with pytest.raises(HomeAssistantError) as exc_info:
        await number.async_set_native_value(70.0)
    assert exc_info.value.translation_key == "wan_config_not_loaded"


async def test_wan_load_balance_will_remove_cancels_debounce(hass: Any) -> None:
    """Removing WanLoadBalanceNumber cancels pending debounce."""
    coordinator = _make_wlb_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()

    from custom_components.unifi_network_monitor.number import (
        WanLoadBalanceNumber,
    )

    number = WanLoadBalanceNumber(coordinator, entry)
    number.hass = hass
    import asyncio

    fut = asyncio.get_event_loop().create_future()
    number._debounce_task = fut
    await number.async_will_remove_from_hass()


# ---------------------------------------------------------------------------
# Rogue Proximity Threshold Number tests
# ---------------------------------------------------------------------------


def test_rogue_threshold_initial_and_unique_id() -> None:
    """Threshold number stores its initial value and a stable unique_id."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry("aa:bb:cc:dd:ee:ff")

    from custom_components.unifi_network_monitor.number import (
        UnifiRogueProximityThresholdNumber,
    )

    number = UnifiRogueProximityThresholdNumber(coordinator, entry, -60)
    assert number.native_value == -60
    assert number.unique_id == "aa:bb:cc:dd:ee:ff_rogue_proximity_rssi_threshold"


def test_rogue_threshold_min_max() -> None:
    """Threshold number constrains to the negative dBm range."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()

    from custom_components.unifi_network_monitor.number import (
        UnifiRogueProximityThresholdNumber,
    )

    number = UnifiRogueProximityThresholdNumber(coordinator, entry, -60)
    assert number.native_min_value == -100
    assert number.native_max_value == -30
    assert number.native_step == 1


async def test_rogue_threshold_set_value_persists_and_refreshes(hass: Any) -> None:
    """Setting the threshold writes options and refreshes the coordinator."""
    from custom_components.unifi_network_monitor.const import (
        CONF_ROGUE_PROXIMITY_RSSI_THRESHOLD,
    )
    from custom_components.unifi_network_monitor.number import (
        UnifiRogueProximityThresholdNumber,
    )

    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()
    number = UnifiRogueProximityThresholdNumber(coordinator, entry, -60)
    number.hass = hass
    hass.config_entries.async_update_entry = MagicMock()

    with patch.object(number, "async_write_ha_state") as mock_write:
        await number.async_set_native_value(-75)

    assert number.native_value == -75
    mock_write.assert_called_once()
    _, kwargs = hass.config_entries.async_update_entry.call_args
    assert kwargs["options"][CONF_ROGUE_PROXIMITY_RSSI_THRESHOLD] == -75
    coordinator.async_force_refresh.assert_awaited_once()


def test_rogue_threshold_device_info() -> None:
    """Threshold number reports device info."""
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)
    entry = _make_entry()

    from custom_components.unifi_network_monitor.number import (
        UnifiRogueProximityThresholdNumber,
    )

    number = UnifiRogueProximityThresholdNumber(coordinator, entry, -60)
    assert number.device_info is not None
