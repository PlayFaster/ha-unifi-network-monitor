"""Tests for the UniFi Network Monitor select platform."""

from unittest.mock import AsyncMock, MagicMock

from custom_components.unifi_network_monitor.const import (
    CONF_ROGUE_PERIOD,
    DEFAULT_ROGUE_PERIOD,
    ROGUE_PERIOD_HOURS,
)

from .conftest import MOCK_COORDINATOR_DATA, MOCK_MAC


def _make_coordinator() -> MagicMock:
    coord = MagicMock()
    coord.data = MOCK_COORDINATOR_DATA
    coord.gateway_mac = MOCK_MAC
    coord.gateway_model = "UDMPRO"
    coord.sw_version = "5.1.19.33549"
    coord.endpoint_available = MagicMock(return_value=True)
    coord.async_request_refresh = AsyncMock()
    coord.async_force_refresh = AsyncMock()
    coord.async_add_listener = MagicMock()
    return coord


def _make_entry(unique_id: str = MOCK_MAC, period: str = "1h") -> MagicMock:
    entry = MagicMock()
    entry.unique_id = unique_id
    entry.title = "UniFi Network"
    entry.entry_id = "test_entry_id"
    entry.options = {
        "host": "192.168.1.1",
        CONF_ROGUE_PERIOD: period,
    }
    return entry


def test_current_option_valid() -> None:
    """current_option returns the stored value when valid."""
    from custom_components.unifi_network_monitor.select import UnifiRoguePeriodSelect

    coordinator = _make_coordinator()
    entry = _make_entry(period="30m")
    select = UnifiRoguePeriodSelect(coordinator, entry)
    assert select.current_option == "30m"


def test_current_option_unset_default() -> None:
    """current_option returns default when option is unset/invalid."""
    from custom_components.unifi_network_monitor.select import UnifiRoguePeriodSelect

    coordinator = _make_coordinator()
    entry = _make_entry(period="invalid_option")
    select = UnifiRoguePeriodSelect(coordinator, entry)
    assert select.current_option == DEFAULT_ROGUE_PERIOD


def test_current_option_missing_key() -> None:
    """current_option returns default when option key is missing."""
    from custom_components.unifi_network_monitor.select import UnifiRoguePeriodSelect

    coordinator = _make_coordinator()
    entry = _make_entry()
    entry.options = {"host": "192.168.1.1"}
    select = UnifiRoguePeriodSelect(coordinator, entry)
    assert select.current_option == DEFAULT_ROGUE_PERIOD


def test_options_list() -> None:
    """Options list matches ROGUE_PERIOD_HOURS keys."""
    from custom_components.unifi_network_monitor.select import UnifiRoguePeriodSelect

    coordinator = _make_coordinator()
    entry = _make_entry()
    select = UnifiRoguePeriodSelect(coordinator, entry)
    assert set(select.options) == set(ROGUE_PERIOD_HOURS)


def test_available_when_endpoint_available() -> None:
    """Available returns True when coordinator says endpoint is available."""
    from custom_components.unifi_network_monitor.select import UnifiRoguePeriodSelect

    coordinator = _make_coordinator()
    coordinator.endpoint_available = MagicMock(return_value=True)
    entry = _make_entry()
    select = UnifiRoguePeriodSelect(coordinator, entry)
    assert select.available is True


def test_available_when_endpoint_unavailable() -> None:
    """Available returns False when endpoint is stale."""
    from custom_components.unifi_network_monitor.select import UnifiRoguePeriodSelect

    coordinator = _make_coordinator()
    coordinator.endpoint_available = MagicMock(return_value=False)
    entry = _make_entry()
    select = UnifiRoguePeriodSelect(coordinator, entry)
    assert select.available is False


async def test_async_select_option_valid() -> None:
    """Selecting a valid option updates entry and refreshes."""
    from custom_components.unifi_network_monitor.select import UnifiRoguePeriodSelect

    coordinator = _make_coordinator()
    entry = _make_entry(period="1h")
    select = UnifiRoguePeriodSelect(coordinator, entry)
    hass = MagicMock()
    hass.config_entries.async_update_entry = MagicMock()
    select.hass = hass
    select.async_write_ha_state = MagicMock()

    await select.async_select_option("30m")

    call_kwargs = hass.config_entries.async_update_entry.call_args[1]
    assert call_kwargs["options"][CONF_ROGUE_PERIOD] == "30m"
    select.async_write_ha_state.assert_called_once()
    coordinator.async_force_refresh.assert_awaited_once()


async def test_async_select_option_invalid() -> None:
    """Selecting an invalid option returns early without changes."""
    from custom_components.unifi_network_monitor.select import UnifiRoguePeriodSelect

    coordinator = _make_coordinator()
    entry = _make_entry(period="1h")
    select = UnifiRoguePeriodSelect(coordinator, entry)
    hass = MagicMock()
    hass.config_entries.async_update_entry = MagicMock()
    select.hass = hass

    await select.async_select_option("invalid")

    hass.config_entries.async_update_entry.assert_not_called()
    coordinator.async_force_refresh.assert_not_called()


def test_unique_id() -> None:
    """Unique_id includes entry.unique_id and rogue_period."""
    from custom_components.unifi_network_monitor.select import UnifiRoguePeriodSelect

    coordinator = _make_coordinator()
    entry = _make_entry("aa:bb:cc:dd:ee:ff")
    select = UnifiRoguePeriodSelect(coordinator, entry)
    assert select.unique_id == "aa:bb:cc:dd:ee:ff_rogue_period"


def test_device_info() -> None:
    """Device info is returned."""
    from custom_components.unifi_network_monitor.select import UnifiRoguePeriodSelect

    coordinator = _make_coordinator()
    entry = _make_entry()
    select = UnifiRoguePeriodSelect(coordinator, entry)
    assert select.device_info is not None
