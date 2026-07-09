"""Tests for cleanup module."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from custom_components.unifi_network_monitor.cleanup import (
    CleanupPlan,
    _desired_device_keys,
    _feature_source,
    apply_cleanup,
    plan_device_cleanup,
)
from custom_components.unifi_network_monitor.const import (
    CONF_ENABLE_SECURITY_MONITORING,
    CONF_ENABLE_SPEEDTEST,
    CONF_ENABLE_WAN_USAGE,
    CONF_UNIFI_DEVICE_MODE,
    DEVICE_MODE_ALL,
    DEVICE_MODE_NONE,
    DEVICE_MODE_SATISFACTION,
    EP_ROGUE,
    EP_SPEEDTEST,
    EP_VPN_TUNNELS,
)

from .conftest import MOCK_COORDINATOR_DATA, MOCK_MAC

# ---------------------------------------------------------------------------
# CleanupPlan.is_empty
# ---------------------------------------------------------------------------


def test_plan_empty_when_no_entities_or_devices() -> None:
    """Empty plan returns True."""
    plan = CleanupPlan()
    assert plan.is_empty is True


def test_plan_not_empty_when_entities() -> None:
    """Plan with entities returns False."""
    plan = CleanupPlan(entity_ids=["sensor.test"])
    assert plan.is_empty is False


def test_plan_not_empty_when_devices() -> None:
    """Plan with devices returns False."""
    plan = CleanupPlan(device_ids=["device1"])
    assert plan.is_empty is False


def test_plan_not_empty_when_both() -> None:
    """Plan with both entities and devices returns False."""
    plan = CleanupPlan(entity_ids=["sensor.test"], device_ids=["device1"])
    assert plan.is_empty is False


# ---------------------------------------------------------------------------
# _desired_device_keys
# ---------------------------------------------------------------------------


def test_desired_keys_mode_all() -> None:
    """Mode 'all' returns full set of device sensor keys + binary sensor keys."""
    keys = _desired_device_keys("ap", DEVICE_MODE_ALL)
    assert "clients" in keys
    assert "cpu" in keys
    assert "ram" in keys
    assert "score" in keys
    assert "update_available" in keys


def test_desired_keys_mode_none() -> None:
    """Mode 'none' returns empty set."""
    keys = _desired_device_keys("ap", DEVICE_MODE_NONE)
    assert keys == set()


def test_desired_keys_mode_satisfaction_ap() -> None:
    """Mode 'satisfaction_only' returns only satisfaction keys."""
    keys = _desired_device_keys("ap", DEVICE_MODE_SATISFACTION)
    assert "score" in keys
    assert "score_wifi0" in keys
    assert "score_wifi1" in keys
    assert "clients" not in keys
    assert "cpu" not in keys


def test_desired_keys_mode_satisfaction_switch() -> None:
    """Mode 'satisfaction_only' for switch returns empty set (no satisfaction keys)."""
    keys = _desired_device_keys("switch", DEVICE_MODE_SATISFACTION)
    assert keys == set()


def test_desired_keys_dev_type_none() -> None:
    """None dev_type uses default sensor set."""
    keys = _desired_device_keys(None, DEVICE_MODE_ALL)
    assert "clients" in keys or "ports_used" in keys


# ---------------------------------------------------------------------------
# _feature_source
# ---------------------------------------------------------------------------


def test_feature_source_prefix_mismatch() -> None:
    """unique_id not starting with uid prefix returns None."""
    result = _feature_source("aa:bb:cc:dd:ee:ff", "other_prefix_something")
    assert result is None


def test_feature_source_endpoint_by_key() -> None:
    """Suffix in _ENDPOINT_BY_KEY returns the mapped endpoint."""
    result = _feature_source("uid", "uid_rogue_ap_count")
    assert result == EP_ROGUE


def test_feature_source_rogue_proximity() -> None:
    """rogue_proximity_alert suffix maps to EP_ROGUE."""
    result = _feature_source("uid", "uid_rogue_proximity_alert")
    assert result == EP_ROGUE


def test_feature_source_rogue_proximity_rssi() -> None:
    """rogue_proximity_rssi_threshold suffix maps to EP_ROGUE."""
    result = _feature_source("uid", "uid_rogue_proximity_rssi_threshold")
    assert result == EP_ROGUE


def test_feature_source_speedtest_wan1() -> None:
    """wan1_speedtest suffix maps to EP_SPEEDTEST."""
    result = _feature_source("uid", "uid_wan1_speedtest")
    assert result == EP_SPEEDTEST


def test_feature_source_speedtest_wan2() -> None:
    """wan2_speedtest suffix maps to EP_SPEEDTEST."""
    result = _feature_source("uid", "uid_wan2_speedtest")
    assert result == EP_SPEEDTEST


def test_feature_source_vpn_prefix() -> None:
    """vpn_ prefix suffix maps to EP_VPN_TUNNELS."""
    result = _feature_source("uid", "uid_vpn_officetunnel")
    assert result == EP_VPN_TUNNELS


def test_feature_source_unknown_suffix() -> None:
    """Unknown suffix returns None."""
    result = _feature_source("uid", "uid_nonexistent_key")
    assert result is None


def test_feature_source_no_prefix() -> None:
    """unique_id that equals uid (no suffix) returns None."""
    result = _feature_source("uid", "uid_")
    assert result is None


# ---------------------------------------------------------------------------
# plan_device_cleanup
# ---------------------------------------------------------------------------


def _make_entry(unique_id: str = MOCK_MAC, mode: str = DEVICE_MODE_ALL) -> MagicMock:
    entry = MagicMock()
    entry.unique_id = unique_id
    entry.entry_id = "entry123"
    entry.title = "UniFi Network"
    entry.options = {
        "host": "192.168.1.1",
        CONF_UNIFI_DEVICE_MODE: mode,
        CONF_ENABLE_SPEEDTEST: True,
        CONF_ENABLE_WAN_USAGE: True,
        CONF_ENABLE_SECURITY_MONITORING: True,
    }
    return entry


def _make_coordinator(data: dict[str, Any] | None) -> MagicMock:
    coord = MagicMock()
    coord.data = data
    coord.gateway_mac = MOCK_MAC
    coord.gateway_model = "UDMPRO"
    coord.sw_version = "5.1.19"
    return coord


def _make_reg_entry(entity_id: str, unique_id: str) -> MagicMock:
    entry = MagicMock()
    entry.entity_id = entity_id
    entry.unique_id = unique_id
    entry.config_entry_id = "entry123"
    return entry


def test_plan_empty_coordinator_data() -> None:
    """Empty coordinator data produces empty plan."""
    hass = MagicMock()
    entry = _make_entry()
    coordinator = _make_coordinator(None)

    plan = plan_device_cleanup(hass, entry, coordinator)
    assert plan.is_empty is True


def test_plan_mode_all_keeps_all() -> None:
    """Mode 'all' with devices does not mark any entities for cleanup."""
    hass = MagicMock()
    entry = _make_entry(mode=DEVICE_MODE_ALL)
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)

    ap_mac = "bb:cc:dd:ee:ff:00"
    ent_reg_entries = [
        _make_reg_entry("sensor.ap_clients", f"{MOCK_MAC}_{ap_mac}_clients"),
        _make_reg_entry("sensor.ap_score", f"{MOCK_MAC}_{ap_mac}_score"),
        _make_reg_entry(
            "binary_sensor.ap_update", f"{MOCK_MAC}_{ap_mac}_update_available"
        ),
    ]

    with (
        patch(
            "custom_components.unifi_network_monitor.cleanup.er.async_get",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.unifi_network_monitor.cleanup.dr.async_get",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.unifi_network_monitor.cleanup.er.async_entries_for_config_entry",
            return_value=ent_reg_entries,
        ),
    ):
        plan = plan_device_cleanup(hass, entry, coordinator)
    assert plan.is_empty is True


def test_plan_mode_none_marks_all() -> None:
    """Mode 'none' with devices marks all device entities for cleanup."""
    hass = MagicMock()
    entry = _make_entry(mode=DEVICE_MODE_NONE)
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)

    ap_mac = "bb:cc:dd:ee:ff:00"
    ent_reg_entries = [
        _make_reg_entry("sensor.ap_clients", f"{MOCK_MAC}_{ap_mac}_clients"),
    ]
    device_entry = MagicMock()
    device_entry.id = "device_ap_1"
    device_entry.config_entries = {"entry123"}

    mock_dev_reg = MagicMock()
    mock_dev_reg.async_get_device = MagicMock(return_value=device_entry)

    with (
        patch(
            "custom_components.unifi_network_monitor.cleanup.er.async_get",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.unifi_network_monitor.cleanup.dr.async_get",
            return_value=mock_dev_reg,
        ),
        patch(
            "custom_components.unifi_network_monitor.cleanup.er.async_entries_for_config_entry",
            return_value=ent_reg_entries,
        ),
    ):
        plan = plan_device_cleanup(hass, entry, coordinator)
    assert not plan.is_empty
    assert "sensor.ap_clients" in plan.entity_ids
    assert "device_ap_1" in plan.device_ids


def test_plan_mode_all_with_disabled_endpoints() -> None:
    """Disabled endpoint entities are added to cleanup plan."""
    hass = MagicMock()
    entry = _make_entry(mode=DEVICE_MODE_ALL)
    entry.options = {
        "host": "192.168.1.1",
        CONF_UNIFI_DEVICE_MODE: DEVICE_MODE_ALL,
        CONF_ENABLE_SPEEDTEST: False,
        CONF_ENABLE_WAN_USAGE: True,
        CONF_ENABLE_SECURITY_MONITORING: True,
    }
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)

    ent_reg_entries = [
        _make_reg_entry("sensor.speedtest", f"{MOCK_MAC}_wan1_speedtest_download"),
    ]

    with (
        patch(
            "custom_components.unifi_network_monitor.cleanup.er.async_get",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.unifi_network_monitor.cleanup.dr.async_get",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.unifi_network_monitor.cleanup.er.async_entries_for_config_entry",
            return_value=ent_reg_entries,
        ),
    ):
        plan = plan_device_cleanup(hass, entry, coordinator)
    assert "sensor.speedtest" in plan.entity_ids


def test_plan_gateway_orphan_entities() -> None:
    """Orphan entities (vpn, speedtest) added when toggles off."""
    hass = MagicMock()
    entry = _make_entry(mode=DEVICE_MODE_ALL)
    entry.options = {
        "host": "192.168.1.1",
        CONF_UNIFI_DEVICE_MODE: DEVICE_MODE_ALL,
        CONF_ENABLE_SPEEDTEST: False,
        CONF_ENABLE_WAN_USAGE: True,
        CONF_ENABLE_SECURITY_MONITORING: False,
    }
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)

    ent_reg_entries = [
        _make_reg_entry("sensor.vpn_total", f"{MOCK_MAC}_vpn_connections_total"),
        _make_reg_entry("sensor.speedtest", f"{MOCK_MAC}_wan1_speedtest_download"),
    ]

    with (
        patch(
            "custom_components.unifi_network_monitor.cleanup.er.async_get",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.unifi_network_monitor.cleanup.dr.async_get",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.unifi_network_monitor.cleanup.er.async_entries_for_config_entry",
            return_value=ent_reg_entries,
        ),
    ):
        plan = plan_device_cleanup(hass, entry, coordinator)
    assert "sensor.speedtest" in plan.entity_ids
    assert "sensor.vpn_total" in plan.entity_ids


def test_plan_gateway_orphan_entities_already_in_plan() -> None:
    """Orphan check skips entities already added by per-device cleanup."""
    hass = MagicMock()
    entry = _make_entry(mode=DEVICE_MODE_NONE)
    entry.options = {
        "host": "192.168.1.1",
        CONF_UNIFI_DEVICE_MODE: DEVICE_MODE_NONE,
        CONF_ENABLE_SPEEDTEST: False,
        CONF_ENABLE_WAN_USAGE: True,
        CONF_ENABLE_SECURITY_MONITORING: True,
    }
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)

    ap_mac = "bb:cc:dd:ee:ff:00"
    # Create an entity that is BOTH a per-device entity (will be added by mode=none)
    # AND maps to a disabled endpoint via _feature_source
    entity_id = "sensor.orphan_duplicate"
    ent_reg_entries = [
        _make_reg_entry(entity_id, f"{MOCK_MAC}_{ap_mac}_clients"),
    ]

    with (
        patch(
            "custom_components.unifi_network_monitor.cleanup.er.async_get",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.unifi_network_monitor.cleanup.dr.async_get",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.unifi_network_monitor.cleanup.er.async_entries_for_config_entry",
            return_value=ent_reg_entries,
        ),
    ):
        plan = plan_device_cleanup(hass, entry, coordinator)
    # Entity should only appear once in the plan
    assert plan.entity_ids.count(entity_id) == 1
    """Device not found in device registry does not add device_id."""
    hass = MagicMock()
    entry = _make_entry(mode=DEVICE_MODE_NONE)
    coordinator = _make_coordinator(MOCK_COORDINATOR_DATA)

    ap_mac = "bb:cc:dd:ee:ff:00"
    ent_reg_entries: list[MagicMock] = []

    mock_dev_reg = MagicMock()
    mock_dev_reg.async_get_device = MagicMock(return_value=None)

    with (
        patch(
            "custom_components.unifi_network_monitor.cleanup.er.async_get",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.unifi_network_monitor.cleanup.dr.async_get",
            return_value=mock_dev_reg,
        ),
        patch(
            "custom_components.unifi_network_monitor.cleanup.er.async_entries_for_config_entry",
            return_value=ent_reg_entries,
        ),
    ):
        plan = plan_device_cleanup(hass, entry, coordinator)
    assert plan.device_ids == []


# ---------------------------------------------------------------------------
# apply_cleanup
# ---------------------------------------------------------------------------


def test_apply_cleanup_removes_entities_and_devices() -> None:
    """apply_cleanup removes entity and updates device."""
    hass = MagicMock()
    entry = _make_entry()

    plan = CleanupPlan(
        entity_ids=["sensor.test1", "sensor.test2"],
        device_ids=["device1"],
    )

    mock_ent_reg = MagicMock()
    mock_ent_reg.async_get = MagicMock(return_value=MagicMock())
    mock_dev_reg = MagicMock()
    mock_dev_reg.async_get = MagicMock(return_value=MagicMock())

    with (
        patch(
            "custom_components.unifi_network_monitor.cleanup.er.async_get",
            return_value=mock_ent_reg,
        ),
        patch(
            "custom_components.unifi_network_monitor.cleanup.dr.async_get",
            return_value=mock_dev_reg,
        ),
    ):
        apply_cleanup(hass, entry, plan)

    assert mock_ent_reg.async_remove.call_count == 2
    mock_ent_reg.async_remove.assert_any_call("sensor.test1")
    mock_ent_reg.async_remove.assert_any_call("sensor.test2")
    mock_dev_reg.async_update_device.assert_called_once_with(
        "device1", remove_config_entry_id="entry123"
    )


def test_apply_cleanup_entity_not_found() -> None:
    """Entity that does not exist in registry is skipped."""
    hass = MagicMock()
    entry = _make_entry()

    plan = CleanupPlan(entity_ids=["sensor.gone"])

    mock_ent_reg = MagicMock()
    mock_ent_reg.async_get = MagicMock(return_value=None)

    with (
        patch(
            "custom_components.unifi_network_monitor.cleanup.er.async_get",
            return_value=mock_ent_reg,
        ),
        patch(
            "custom_components.unifi_network_monitor.cleanup.dr.async_get",
            return_value=MagicMock(),
        ),
    ):
        apply_cleanup(hass, entry, plan)

    mock_ent_reg.async_remove.assert_not_called()


def test_apply_cleanup_device_not_found() -> None:
    """Device that does not exist in registry is skipped."""
    hass = MagicMock()
    entry = _make_entry()

    plan = CleanupPlan(device_ids=["device_gone"])

    mock_ent_reg = MagicMock()
    mock_dev_reg = MagicMock()
    mock_dev_reg.async_get = MagicMock(return_value=None)

    with (
        patch(
            "custom_components.unifi_network_monitor.cleanup.er.async_get",
            return_value=mock_ent_reg,
        ),
        patch(
            "custom_components.unifi_network_monitor.cleanup.dr.async_get",
            return_value=mock_dev_reg,
        ),
    ):
        apply_cleanup(hass, entry, plan)

    mock_dev_reg.async_update_device.assert_not_called()


def test_apply_cleanup_empty_plan() -> None:
    """Empty plan does nothing."""
    hass = MagicMock()
    entry = _make_entry()
    plan = CleanupPlan()

    mock_ent_reg = MagicMock()
    mock_dev_reg = MagicMock()

    with (
        patch(
            "custom_components.unifi_network_monitor.cleanup.er.async_get",
            return_value=mock_ent_reg,
        ),
        patch(
            "custom_components.unifi_network_monitor.cleanup.dr.async_get",
            return_value=mock_dev_reg,
        ),
    ):
        apply_cleanup(hass, entry, plan)

    mock_ent_reg.async_remove.assert_not_called()
    mock_dev_reg.async_update_device.assert_not_called()
