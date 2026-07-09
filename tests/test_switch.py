"""Tests for the UniFi Network Monitor switch platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from custom_components.unifi_network_monitor.const import CONF_STOP_POLLING

from .conftest import MOCK_COORDINATOR_DATA, MOCK_MAC


def _make_coordinator() -> MagicMock:
    coord = MagicMock()
    coord.data = MOCK_COORDINATOR_DATA
    coord.gateway_mac = MOCK_MAC
    coord.gateway_model = "UDMPRO"
    coord.sw_version = "5.1.19.33549"
    coord.async_request_refresh = AsyncMock()
    coord.async_add_listener = MagicMock()
    return coord


def _make_entry(unique_id: str = MOCK_MAC, stop_polling: bool = False) -> MagicMock:
    entry = MagicMock()
    entry.unique_id = unique_id
    entry.title = "UniFi Network"
    entry.entry_id = "test_entry_id"
    entry.options = {
        "host": "192.168.1.1",
        CONF_STOP_POLLING: stop_polling,
    }
    return entry


async def test_async_setup_entry_creates_switch(hass) -> None:
    """async_setup_entry creates the pause polling switch."""
    entry = _make_entry()
    async_add_entities = MagicMock()

    from custom_components.unifi_network_monitor.switch import async_setup_entry

    await async_setup_entry(hass, entry, async_add_entities)
    async_add_entities.assert_called_once()
    entities = async_add_entities.call_args[0][0]
    assert len(entities) == 1
    assert entities[0].unique_id == f"{MOCK_MAC}_pause_polling"


def test_switch_initial_is_on() -> None:
    """Switch is_on reflects entry.options CONF_STOP_POLLING default."""
    coordinator = _make_coordinator()
    entry = _make_entry(stop_polling=False)

    from custom_components.unifi_network_monitor.switch import UnifiPausePollingSwitch

    switch = UnifiPausePollingSwitch(coordinator, entry)
    assert switch.is_on is False


def test_switch_is_on_when_polling_paused() -> None:
    """Switch is_on is True when CONF_STOP_POLLING is True."""
    coordinator = _make_coordinator()
    entry = _make_entry(stop_polling=True)

    from custom_components.unifi_network_monitor.switch import UnifiPausePollingSwitch

    switch = UnifiPausePollingSwitch(coordinator, entry)
    assert switch.is_on is True


def test_switch_unique_id() -> None:
    """Switch unique_id uses entry.unique_id."""
    coordinator = _make_coordinator()
    entry = _make_entry("aa:bb:cc:dd:ee:ff")

    from custom_components.unifi_network_monitor.switch import UnifiPausePollingSwitch

    switch = UnifiPausePollingSwitch(coordinator, entry)
    assert switch.unique_id == "aa:bb:cc:dd:ee:ff_pause_polling"


def test_switch_entity_attributes() -> None:
    """Switch has correct entity attributes."""
    coordinator = _make_coordinator()
    entry = _make_entry()

    from custom_components.unifi_network_monitor.switch import UnifiPausePollingSwitch

    switch = UnifiPausePollingSwitch(coordinator, entry)
    assert switch._attr_has_entity_name is True
    assert switch._attr_should_poll is False
    assert switch.entity_description.key == "pause_polling"


def test_switch_device_info() -> None:
    """Switch device_info returns system sub-device info."""
    coordinator = _make_coordinator()
    entry = _make_entry()

    from custom_components.unifi_network_monitor.switch import UnifiPausePollingSwitch

    switch = UnifiPausePollingSwitch(coordinator, entry)
    info = switch.device_info
    assert info is not None


async def test_switch_turn_on_pauses_polling() -> None:
    """async_turn_on pauses polling via _set_state."""
    coordinator = _make_coordinator()
    entry = _make_entry(stop_polling=False)

    from custom_components.unifi_network_monitor.switch import UnifiPausePollingSwitch

    switch = UnifiPausePollingSwitch(coordinator, entry)
    hass = MagicMock()
    hass.config_entries.async_update_entry = MagicMock()
    switch.hass = hass
    switch.async_write_ha_state = MagicMock()

    await switch.async_turn_on()
    call_kwargs = hass.config_entries.async_update_entry.call_args[1]
    assert call_kwargs["options"][CONF_STOP_POLLING] is True
    switch.async_write_ha_state.assert_called_once()


async def test_switch_turn_off_resumes_polling() -> None:
    """async_turn_off resumes polling via _set_state."""
    coordinator = _make_coordinator()
    entry = _make_entry(stop_polling=True)

    from custom_components.unifi_network_monitor.switch import UnifiPausePollingSwitch

    switch = UnifiPausePollingSwitch(coordinator, entry)
    hass = MagicMock()
    hass.config_entries.async_update_entry = MagicMock()
    switch.hass = hass
    switch.async_write_ha_state = MagicMock()

    await switch.async_turn_off()
    call_kwargs = hass.config_entries.async_update_entry.call_args[1]
    assert call_kwargs["options"][CONF_STOP_POLLING] is False
    switch.async_write_ha_state.assert_called_once()
    coordinator.async_request_refresh.assert_awaited_once()
