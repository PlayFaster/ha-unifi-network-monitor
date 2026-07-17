"""Tests for the UniFi Network Monitor integration setup."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.config_entries import ConfigEntryState

from custom_components.unifi_network_monitor.api import UnifiConnectionError


async def test_setup_entry_succeeds(hass: Any, mock_config_entry: Any) -> None:
    """Integration sets up successfully from a config entry."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.unifi_network_monitor.UnifiNetworkAPI"
    ) as mock_api_cls:
        mock_api = MagicMock()
        mock_api.logout = AsyncMock()
        mock_api.get_devices = AsyncMock(return_value=[])
        mock_api.get_health = AsyncMock(return_value=[])
        mock_api.get_sysinfo = AsyncMock(return_value=[])
        mock_api_cls.return_value = mock_api

        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert result is True
    assert mock_config_entry.state == ConfigEntryState.LOADED


async def test_unload_entry(hass: Any, mock_config_entry: Any) -> None:
    """Integration unloads cleanly."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.unifi_network_monitor.UnifiNetworkAPI"
    ) as mock_api_cls:
        mock_api = MagicMock()
        mock_api.logout = AsyncMock()
        mock_api.get_devices = AsyncMock(return_value=[])
        mock_api.get_health = AsyncMock(return_value=[])
        mock_api.get_sysinfo = AsyncMock(return_value=[])
        mock_api_cls.return_value = mock_api

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        unload_result = await hass.config_entries.async_unload(
            mock_config_entry.entry_id
        )

    assert unload_result is True
    assert mock_config_entry.state == ConfigEntryState.NOT_LOADED


async def test_setup_entry_registers_gateway_device(
    hass: Any, mock_config_entry: Any
) -> None:
    """Setup registers the gateway device in the device registry."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.unifi_network_monitor.UnifiNetworkAPI"
    ) as mock_api_cls:
        mock_api = MagicMock()
        mock_api.logout = AsyncMock()
        mock_api.get_devices = AsyncMock(return_value=[])
        mock_api.get_health = AsyncMock(return_value=[])
        mock_api.get_sysinfo = AsyncMock(return_value=[])
        mock_api_cls.return_value = mock_api

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    dev_reg = hass.data["device_registry"]
    device = dev_reg.async_get_device(
        connections=set(),
        identifiers={("unifi_network_monitor", "aa:bb:cc:dd:ee:ff")},
    )
    assert device is not None
    assert "Gateway" in device.name


async def test_async_setup_returns_true(hass: Any) -> None:
    """async_setup always returns True."""
    from custom_components.unifi_network_monitor import async_setup

    result = await async_setup(hass, {})
    assert result is True


async def test_unload_entry_logout_failure(hass: Any, mock_config_entry: Any) -> None:
    """Unload handles logout failure gracefully."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.unifi_network_monitor.UnifiNetworkAPI"
    ) as mock_api_cls:
        mock_api = MagicMock()
        mock_api.logout = AsyncMock(side_effect=UnifiConnectionError("logout failed"))
        mock_api.get_devices = AsyncMock(return_value=[])
        mock_api.get_health = AsyncMock(return_value=[])
        mock_api.get_sysinfo = AsyncMock(return_value=[])
        mock_api_cls.return_value = mock_api

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        unload_result = await hass.config_entries.async_unload(
            mock_config_entry.entry_id
        )

    assert unload_result is True
    assert mock_config_entry.state == ConfigEntryState.NOT_LOADED


async def test_setup_entry_background_init_failure(
    hass: Any, mock_config_entry: Any
) -> None:
    """Setup handles background init failure gracefully."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.unifi_network_monitor.UnifiNetworkAPI"
    ) as mock_api_cls:
        mock_api = MagicMock()
        mock_api.logout = AsyncMock()
        mock_api.get_devices = AsyncMock(side_effect=Exception("init failure"))
        mock_api.get_health = AsyncMock(return_value=[])
        mock_api.get_sysinfo = AsyncMock(return_value=[])
        mock_api_cls.return_value = mock_api

        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert result is True


# ---------------------------------------------------------------------------
# _async_reload_on_settings_change
# ---------------------------------------------------------------------------


async def test_reload_on_settings_change_different_signature(
    hass: Any, mock_config_entry: Any
) -> None:
    """Reload is triggered when reload_signature changes."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={"host": "192.168.1.1", "scan_interval": 60},
    )

    coordinator = MagicMock()
    coordinator.reload_signature = {"old": "value"}
    mock_config_entry.runtime_data = coordinator

    with (
        patch(
            "custom_components.unifi_network_monitor._reload_signature",
            return_value={"host": "192.168.1.1"},
        ),
        patch.object(hass.config_entries, "async_reload") as mock_reload,
    ):
        from custom_components.unifi_network_monitor import (
            _async_reload_on_settings_change,
        )

        await _async_reload_on_settings_change(hass, mock_config_entry)

    mock_reload.assert_awaited_once_with(mock_config_entry.entry_id)
    assert coordinator.reload_signature == {"host": "192.168.1.1"}


async def test_reload_on_settings_change_same_signature(
    hass: Any, mock_config_entry: Any
) -> None:
    """No reload when reload_signature does not change."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={"host": "192.168.1.1", "scan_interval": 60},
    )

    coordinator = MagicMock()
    coordinator.reload_signature = {"host": "192.168.1.1"}
    mock_config_entry.runtime_data = coordinator

    with (
        patch(
            "custom_components.unifi_network_monitor._reload_signature",
            return_value={"host": "192.168.1.1"},
        ),
        patch.object(hass.config_entries, "async_reload") as mock_reload,
    ):
        from custom_components.unifi_network_monitor import (
            _async_reload_on_settings_change,
        )

        await _async_reload_on_settings_change(hass, mock_config_entry)

    mock_reload.assert_not_called()


# ---------------------------------------------------------------------------
# _handle_cleanup service handler
# ---------------------------------------------------------------------------


async def test_handle_cleanup_dry_run(hass: Any, mock_config_entry: Any) -> None:
    """Cleanup service dry_run=True returns plan without applying it."""
    mock_config_entry.add_to_hass(hass)

    coordinator = MagicMock()
    coordinator.data = {"devices": {}}
    mock_config_entry.runtime_data = coordinator

    from custom_components.unifi_network_monitor import async_setup

    await async_setup(hass, {})

    with (
        patch(
            "custom_components.unifi_network_monitor.plan_device_cleanup",
            return_value=MagicMock(entity_ids=[], device_ids=[]),
        ) as mock_plan,
        patch(
            "custom_components.unifi_network_monitor.apply_cleanup",
        ) as mock_apply,
    ):
        result = await hass.services.async_call(
            "unifi_network_monitor",
            "cleanup_unused_entities",
            {"dry_run": True},
            blocking=True,
            return_response=True,
        )

    mock_plan.assert_called_once()
    mock_apply.assert_not_called()
    assert result["dry_run"] is True


async def test_handle_cleanup_apply(hass: Any, mock_config_entry: Any) -> None:
    """Cleanup service dry_run=False applies and reloads."""
    mock_config_entry.add_to_hass(hass)

    coordinator = MagicMock()
    coordinator.data = {"devices": {}}
    mock_config_entry.runtime_data = coordinator

    from custom_components.unifi_network_monitor import async_setup

    await async_setup(hass, {})

    mock_plan = MagicMock()
    mock_plan.is_empty = False
    mock_plan.entity_ids = ["sensor.test"]
    mock_plan.device_ids = []

    with (
        patch(
            "custom_components.unifi_network_monitor.plan_device_cleanup",
            return_value=mock_plan,
        ) as mock_plan_fn,
        patch(
            "custom_components.unifi_network_monitor.apply_cleanup",
        ) as mock_apply,
        patch.object(hass.config_entries, "async_reload") as mock_reload,
    ):
        result = await hass.services.async_call(
            "unifi_network_monitor",
            "cleanup_unused_entities",
            {"dry_run": False},
            blocking=True,
            return_response=True,
        )

    mock_plan_fn.assert_called_once()
    mock_apply.assert_called_once()
    mock_reload.assert_called_once()
    assert result["dry_run"] is False


async def test_handle_cleanup_skips_entry_without_coordinator(
    hass: Any, mock_config_entry: Any
) -> None:
    """Cleanup service skips entries without runtime_data coordinator."""
    mock_config_entry.add_to_hass(hass)

    from custom_components.unifi_network_monitor import async_setup

    await async_setup(hass, {})

    with patch(
        "custom_components.unifi_network_monitor.plan_device_cleanup",
    ) as mock_plan:
        result = await hass.services.async_call(
            "unifi_network_monitor",
            "cleanup_unused_entities",
            {"dry_run": True},
            blocking=True,
            return_response=True,
        )

    mock_plan.assert_not_called()
    assert result["entries"] == {}


# ---------------------------------------------------------------------------
# async_remove_config_entry_device
# ---------------------------------------------------------------------------


async def test_async_remove_config_entry_device_has_entities(
    hass: Any, mock_config_entry: Any
) -> None:
    """Return False when Monitor has entities on the device."""
    mock_config_entry.add_to_hass(hass)

    from homeassistant.helpers import device_registry as dr
    from homeassistant.helpers import entity_registry as er

    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)

    device_entry = dev_reg.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("unifi_network_monitor", "mac:test:device:1")},
    )

    entity_entry = ent_reg.async_get_or_create(
        "sensor",
        "unifi_network_monitor",
        "test_unique_id",
        suggested_object_id="test_entity",
        config_entry=mock_config_entry,
        device_id=device_entry.id,
    )

    from custom_components.unifi_network_monitor import (
        async_remove_config_entry_device,
    )

    result = await async_remove_config_entry_device(
        hass, mock_config_entry, device_entry
    )

    assert result is False


async def test_async_remove_config_entry_device_no_entities(
    hass: Any, mock_config_entry: Any
) -> None:
    """Return True when Monitor has no entities on the device."""
    mock_config_entry.add_to_hass(hass)

    from homeassistant.helpers import device_registry as dr

    dev_reg = dr.async_get(hass)
    device_entry = dev_reg.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("unifi_network_monitor", "mac:test:device:2")},
    )

    from custom_components.unifi_network_monitor import (
        async_remove_config_entry_device,
    )

    result = await async_remove_config_entry_device(
        hass, mock_config_entry, device_entry
    )

    assert result is True


async def test_async_remove_config_entry_device_other_entry(
    hass: Any, mock_config_entry: Any
) -> None:
    """Return True when entities on the device belong to another config entry."""
    mock_config_entry.add_to_hass(hass)

    from homeassistant.helpers import device_registry as dr
    from homeassistant.helpers import entity_registry as er

    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)

    device_entry = dev_reg.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("unifi_network_monitor", "mac:test:device:3")},
    )

    from pytest_homeassistant_custom_component.common import MockConfigEntry

    other_entry = MockConfigEntry(
        domain="other_domain",
        title="Other",
        unique_id="other_id",
    )
    other_entry.add_to_hass(hass)

    entity_entry = ent_reg.async_get_or_create(
        "sensor",
        "other_domain",
        "other_unique",
        suggested_object_id="other_entity",
        config_entry=other_entry,
        device_id=device_entry.id,
    )

    from custom_components.unifi_network_monitor import (
        async_remove_config_entry_device,
    )

    result = await async_remove_config_entry_device(
        hass, mock_config_entry, device_entry
    )

    assert result is True


async def test_setup_entry_background_init_unifi_error(
    hass: Any, mock_config_entry: Any
) -> None:
    """Setup handles background UnifiError failure (line 77)."""
    from custom_components.unifi_network_monitor.api import UnifiConnectionError

    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.unifi_network_monitor.UnifiNetworkAPI"
    ) as mock_api_cls:
        mock_api = MagicMock()
        mock_api.logout = AsyncMock()
        mock_api.get_devices = AsyncMock(return_value=[])
        mock_api.get_health = AsyncMock(return_value=[])
        mock_api.get_sysinfo = AsyncMock(return_value=[])
        coordinator = MagicMock()
        coordinator.async_initialize = AsyncMock()
        coordinator.async_refresh = AsyncMock(
            side_effect=UnifiConnectionError("connection lost")
        )
        coordinator.gateway_mac = "aa:bb:cc:dd:ee:ff"
        coordinator.gateway_model = "UDMPRO"
        coordinator.sw_version = "5.1.19"
        coordinator.data = None
        coordinator.last_update_success = True
        coordinator.consecutive_failures = 0
        mock_api_cls.return_value = mock_api

        with patch(
            "custom_components.unifi_network_monitor.UnifiNetworkDataUpdateCoordinator",
            return_value=coordinator,
        ):
            result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

    assert result is True


# ---------------------------------------------------------------------------
# device_mode clamping write-back (lines 147-150)
# ---------------------------------------------------------------------------


async def test_setup_entry_clamps_device_mode(
    hass: Any, mock_config_entry: Any
) -> None:
    """Invalid device_mode gets clamped on setup."""
    from custom_components.unifi_network_monitor.const import CONF_UNIFI_DEVICE_MODE

    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={
            **mock_config_entry.options,
            CONF_UNIFI_DEVICE_MODE: "invalid_mode",
        },
    )

    with (
        patch(
            "custom_components.unifi_network_monitor.UnifiNetworkAPI"
        ) as mock_api_cls,
        patch.object(hass.config_entries, "async_update_entry") as mock_update,
    ):
        mock_api = MagicMock()
        mock_api.logout = AsyncMock()
        mock_api.get_devices = AsyncMock(return_value=[])
        mock_api.get_health = AsyncMock(return_value=[])
        mock_api.get_sysinfo = AsyncMock(return_value=[])
        mock_api_cls.return_value = mock_api

        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert result is True
    mock_update.assert_called_once()
    _, kwargs = mock_update.call_args
    assert kwargs["options"][CONF_UNIFI_DEVICE_MODE] == "none"


async def test_setup_entry_does_not_clamp_valid_mode(
    hass: Any, mock_config_entry: Any
) -> None:
    """Valid device_mode is not clamped."""
    from custom_components.unifi_network_monitor.const import (
        CONF_UNIFI_DEVICE_MODE,
        DEVICE_MODE_ALL,
    )

    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={
            **mock_config_entry.options,
            CONF_UNIFI_DEVICE_MODE: DEVICE_MODE_ALL,
        },
    )

    with (
        patch(
            "custom_components.unifi_network_monitor.UnifiNetworkAPI"
        ) as mock_api_cls,
        patch.object(hass.config_entries, "async_update_entry") as mock_update,
    ):
        mock_api = MagicMock()
        mock_api.logout = AsyncMock()
        mock_api.get_devices = AsyncMock(return_value=[])
        mock_api.get_health = AsyncMock(return_value=[])
        mock_api.get_sysinfo = AsyncMock(return_value=[])
        mock_api_cls.return_value = mock_api

        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert result is True
    mock_update.assert_not_called()
