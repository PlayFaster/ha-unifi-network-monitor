"""Tests for services module."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol
from homeassistant.exceptions import ServiceValidationError

from custom_components.unifi_network_monitor.const import (
    ALERT_MAX_PAGES,
    ALERT_PAGE_SIZE,
    ALERT_QUANTITY_DEFAULT,
    ALERT_QUANTITY_MAX,
    DOMAIN,
    ROGUE_ACTION_PERIOD_HOURS,
    ROGUE_QUANTITY_MAX,
    SERVICE_GET_ALERTS,
    SERVICE_GET_ROGUE_APS,
)
from custom_components.unifi_network_monitor.services import (
    _cached_ap_name_map,
    _fetch_alerts,
    _resolve_coordinator,
    _rogue_response_item,
    async_register_services,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_coordinator(data: dict[str, Any] | None = None) -> MagicMock:
    coord = MagicMock()
    coord.data = data or {}
    return coord


def _make_entry(domain: str = DOMAIN, has_runtime: bool = True) -> MagicMock:
    entry = MagicMock()
    entry.domain = domain
    if has_runtime:
        entry.runtime_data = _make_coordinator()
    else:
        entry.runtime_data = None
    return entry


# ---------------------------------------------------------------------------
# _resolve_coordinator
# ---------------------------------------------------------------------------


def test_resolve_coordinator_no_entries() -> None:
    """_resolve_coordinator raises when no entries loaded."""
    hass = MagicMock()
    hass.config_entries.async_entries = MagicMock(return_value=[])
    call = MagicMock()
    call.data = {}

    with pytest.raises(ServiceValidationError) as err:
        _resolve_coordinator(hass, call)
    assert err.value.translation_key == "no_entries_loaded"


def test_resolve_coordinator_multiple_entries_no_device() -> None:
    """_resolve_coordinator raises when multiple entries and no device_id."""
    hass = MagicMock()
    entry1 = _make_entry()
    entry2 = _make_entry()
    hass.config_entries.async_entries = MagicMock(return_value=[entry1, entry2])
    call = MagicMock()
    call.data = {}

    with pytest.raises(ServiceValidationError) as err:
        _resolve_coordinator(hass, call)
    assert err.value.translation_key == "multiple_entries"


def test_resolve_coordinator_single_entry() -> None:
    """_resolve_coordinator returns sole entry's coordinator."""
    hass = MagicMock()
    coord = _make_coordinator()
    entry = MagicMock()
    entry.runtime_data = coord
    hass.config_entries.async_entries = MagicMock(return_value=[entry])
    call = MagicMock()
    call.data = {}

    result = _resolve_coordinator(hass, call)
    assert result is coord


def test_resolve_coordinator_device_id_unknown() -> None:
    """_resolve_coordinator raises when device_id is unknown."""
    hass = MagicMock()
    hass.config_entries.async_entries = MagicMock(return_value=[])
    mock_dev_reg = MagicMock()
    mock_dev_reg.async_get = MagicMock(return_value=None)
    dr = MagicMock()
    dr.async_get = MagicMock(return_value=mock_dev_reg)

    call = MagicMock()
    call.data = {"device_id": "unknown-dev"}

    with (
        patch(
            "custom_components.unifi_network_monitor.services.dr.async_get",
            return_value=mock_dev_reg,
        ),
        pytest.raises(ServiceValidationError) as err,
    ):
        _resolve_coordinator(hass, call)
    assert err.value.translation_key == "unknown_device"


def test_resolve_coordinator_device_id_not_monitor() -> None:
    """_resolve_coordinator raises when device not a monitor device."""
    hass = MagicMock()
    other_entry = _make_entry(domain="other_domain")
    hass.config_entries.async_entries = MagicMock(return_value=[other_entry])
    hass.config_entries.async_get_entry = MagicMock(return_value=other_entry)

    mock_device = MagicMock()
    mock_device.config_entries = {"other_entry_id"}
    mock_dev_reg = MagicMock()
    mock_dev_reg.async_get = MagicMock(return_value=mock_device)

    call = MagicMock()
    call.data = {"device_id": "dev-001"}

    with (
        patch(
            "custom_components.unifi_network_monitor.services.dr.async_get",
            return_value=mock_dev_reg,
        ),
        pytest.raises(ServiceValidationError) as err,
    ):
        _resolve_coordinator(hass, call)
    assert err.value.translation_key == "not_a_monitor_device"


def test_resolve_coordinator_device_id_success() -> None:
    """_resolve_coordinator resolves coordinator from device_id."""
    hass = MagicMock()
    coord = _make_coordinator()
    entry = MagicMock()
    entry.domain = DOMAIN
    entry.runtime_data = coord
    hass.config_entries.async_entries = MagicMock(return_value=[entry])
    hass.config_entries.async_get_entry = MagicMock(return_value=entry)

    mock_device = MagicMock()
    mock_device.config_entries = {"entry_id"}
    mock_dev_reg = MagicMock()
    mock_dev_reg.async_get = MagicMock(return_value=mock_device)

    call = MagicMock()
    call.data = {"device_id": "dev-001"}

    with patch(
        "custom_components.unifi_network_monitor.services.dr.async_get",
        return_value=mock_dev_reg,
    ):
        result = _resolve_coordinator(hass, call)
    assert result is coord


# ---------------------------------------------------------------------------
# _resolve_entry
# ---------------------------------------------------------------------------


def test_resolve_entry_no_entries() -> None:
    """_resolve_entry raises when no entries loaded."""
    from custom_components.unifi_network_monitor.services import _resolve_entry

    hass = MagicMock()
    hass.config_entries.async_entries = MagicMock(return_value=[])
    call = MagicMock()
    call.data = {}

    with pytest.raises(ServiceValidationError) as err:
        _resolve_entry(hass, call)
    assert err.value.translation_key == "no_entries_loaded"


def test_resolve_entry_multiple_entries_no_device() -> None:
    """_resolve_entry raises when multiple entries and no device_id."""
    from custom_components.unifi_network_monitor.services import _resolve_entry

    hass = MagicMock()
    entry1 = _make_entry()
    entry2 = _make_entry()
    hass.config_entries.async_entries = MagicMock(return_value=[entry1, entry2])
    call = MagicMock()
    call.data = {}

    with pytest.raises(ServiceValidationError) as err:
        _resolve_entry(hass, call)
    assert err.value.translation_key == "multiple_entries"


def test_resolve_entry_device_id_unknown() -> None:
    """_resolve_entry raises when device_id is unknown."""
    from custom_components.unifi_network_monitor.services import _resolve_entry

    hass = MagicMock()
    hass.config_entries.async_entries = MagicMock(return_value=[])
    mock_dev_reg = MagicMock()
    mock_dev_reg.async_get = MagicMock(return_value=None)

    call = MagicMock()
    call.data = {"device_id": "unknown-dev"}

    with (
        patch(
            "custom_components.unifi_network_monitor.services.dr.async_get",
            return_value=mock_dev_reg,
        ),
        pytest.raises(ServiceValidationError) as err,
    ):
        _resolve_entry(hass, call)
    assert err.value.translation_key == "unknown_device"


def test_resolve_entry_device_id_not_monitor() -> None:
    """_resolve_entry raises when device not a monitor device."""
    from custom_components.unifi_network_monitor.services import _resolve_entry

    hass = MagicMock()
    other_entry = _make_entry(domain="other_domain")
    hass.config_entries.async_entries = MagicMock(return_value=[other_entry])
    hass.config_entries.async_get_entry = MagicMock(return_value=other_entry)

    mock_device = MagicMock()
    mock_device.config_entries = {"other_entry_id"}
    mock_dev_reg = MagicMock()
    mock_dev_reg.async_get = MagicMock(return_value=mock_device)

    call = MagicMock()
    call.data = {"device_id": "dev-001"}

    with (
        patch(
            "custom_components.unifi_network_monitor.services.dr.async_get",
            return_value=mock_dev_reg,
        ),
        pytest.raises(ServiceValidationError) as err,
    ):
        _resolve_entry(hass, call)
    assert err.value.translation_key == "not_a_monitor_device"


def test_resolve_entry_device_id_success() -> None:
    """_resolve_entry resolves entry from device_id."""
    from custom_components.unifi_network_monitor.services import _resolve_entry

    hass = MagicMock()
    entry = MagicMock()
    entry.domain = DOMAIN
    entry.runtime_data = MagicMock()
    hass.config_entries.async_entries = MagicMock(return_value=[entry])
    hass.config_entries.async_get_entry = MagicMock(return_value=entry)

    mock_device = MagicMock()
    mock_device.config_entries = {"entry_id"}
    mock_dev_reg = MagicMock()
    mock_dev_reg.async_get = MagicMock(return_value=mock_device)

    call = MagicMock()
    call.data = {"device_id": "dev-001"}

    with patch(
        "custom_components.unifi_network_monitor.services.dr.async_get",
        return_value=mock_dev_reg,
    ):
        result = _resolve_entry(hass, call)
    assert result is entry


# ---------------------------------------------------------------------------
# _fetch_alerts
# ---------------------------------------------------------------------------


async def test_fetch_alerts_empty_batch() -> None:
    """_fetch_alerts stops on empty batch."""
    coordinator = _make_coordinator()
    coordinator.api.get_system_logs = AsyncMock(return_value=[])

    result, total, truncated = await _fetch_alerts(
        coordinator, ["HIGH"], 10, None, [], []
    )
    assert result == []
    assert total is None
    assert truncated is False


async def test_fetch_alerts_collects_up_to_quantity() -> None:
    """_fetch_alerts returns up to quantity alerts."""
    coordinator = _make_coordinator()
    coordinator.api.get_system_logs = AsyncMock(
        return_value=[
            {"id": f"evt_{i}", "title_raw": f"Alert {i}", "severity": "HIGH"}
            for i in range(5)
        ]
    )

    result, _, _ = await _fetch_alerts(coordinator, ["HIGH"], 3, None, [], [])
    assert len(result) == 3
    assert result[0]["id"] == "evt_0"


async def test_fetch_alerts_cutoff() -> None:
    """_fetch_alerts stops at records older than cutoff."""
    coordinator = _make_coordinator()
    coordinator.api.get_system_logs = AsyncMock(
        return_value=[
            {
                "id": "evt_1",
                "timestamp": 2000,
                "title_raw": "Recent",
                "severity": "HIGH",
            },
            {"id": "evt_2", "timestamp": 500, "title_raw": "Old", "severity": "HIGH"},
        ]
    )

    result, _, _ = await _fetch_alerts(coordinator, ["HIGH"], 10, 1000, [], [])
    assert len(result) == 1
    assert result[0]["id"] == "evt_1"


async def test_fetch_alerts_keyword_filter() -> None:
    """_fetch_alerts filters by a single keyword term."""
    coordinator = _make_coordinator()
    coordinator.api.get_system_logs = AsyncMock(
        return_value=[
            {
                "id": "evt_1",
                "title_raw": "CPU Alert",
                "message_raw": "",
                "severity": "HIGH",
            },
            {
                "id": "evt_2",
                "title_raw": "Memory Alert",
                "message_raw": "",
                "severity": "HIGH",
            },
        ]
    )

    result, _, _ = await _fetch_alerts(coordinator, ["HIGH"], 10, None, ["cpu"], [])
    assert len(result) == 1
    assert result[0]["id"] == "evt_1"


async def test_fetch_alerts_keyword_multi_term() -> None:
    """_fetch_alerts keeps a record matching ANY keyword term (comma-list OR)."""
    coordinator = _make_coordinator()
    coordinator.api.get_system_logs = AsyncMock(
        return_value=[
            {"id": "evt_1", "title_raw": "CPU Alert", "severity": "HIGH"},
            {"id": "evt_2", "title_raw": "Memory Alert", "severity": "HIGH"},
            {"id": "evt_3", "title_raw": "Disk Alert", "severity": "HIGH"},
        ]
    )

    result, _, _ = await _fetch_alerts(
        coordinator, ["HIGH"], 10, None, ["cpu", "disk"], []
    )
    assert [r["id"] for r in result] == ["evt_1", "evt_3"]


async def test_fetch_alerts_exclude_filter() -> None:
    """_fetch_alerts drops records matching any exclude term (comma-list)."""
    coordinator = _make_coordinator()
    coordinator.api.get_system_logs = AsyncMock(
        return_value=[
            {
                "id": "evt_1",
                "title_raw": "CPU Alert",
                "message_raw": "",
                "severity": "HIGH",
            },
            {
                "id": "evt_2",
                "title_raw": "Memory Alert",
                "message_raw": "",
                "severity": "HIGH",
            },
            {
                "id": "evt_3",
                "title_raw": "Disk Alert",
                "message_raw": "",
                "severity": "HIGH",
            },
        ]
    )

    # No include; exclude drops cpu + memory, leaving only disk.
    result, _, _ = await _fetch_alerts(
        coordinator, ["HIGH"], 10, None, [], ["cpu", "memory"]
    )
    assert [r["id"] for r in result] == ["evt_3"]


async def test_fetch_alerts_short_page_ends_early() -> None:
    """_fetch_alerts stops when page has fewer records than page_size."""
    coordinator = _make_coordinator()
    coordinator.api.get_system_logs = AsyncMock(
        return_value=[{"id": "evt_1", "title_raw": "Only one", "severity": "HIGH"}]
    )

    result, _, _ = await _fetch_alerts(coordinator, ["HIGH"], 10, None, [], [])
    assert len(result) == 1


async def test_fetch_alerts_stops_at_max_pages() -> None:
    """_fetch_alerts stops after ALERT_MAX_PAGES."""
    coordinator = _make_coordinator()
    # Return full pages for ALERT_MAX_PAGES calls, then stop
    coordinator.api.get_system_logs = AsyncMock(
        return_value=[
            {"id": f"evt_{i}", "title_raw": f"Alert {i}", "severity": "HIGH"}
            for i in range(ALERT_PAGE_SIZE)
        ]
    )

    result, _, _ = await _fetch_alerts(
        coordinator, ["HIGH"], ALERT_PAGE_SIZE * ALERT_MAX_PAGES, None, [], []
    )
    assert len(result) == ALERT_PAGE_SIZE * ALERT_MAX_PAGES
    assert coordinator.api.get_system_logs.call_count == ALERT_MAX_PAGES


async def test_fetch_alerts_count_total_exact_when_log_ends() -> None:
    """count_total returns the exact match total (not truncated) on a short page."""
    coordinator = _make_coordinator()
    coordinator.api.get_system_logs = AsyncMock(
        return_value=[
            {"id": f"evt_{i}", "title_raw": f"Alert {i}", "severity": "HIGH"}
            for i in range(5)
        ]
    )

    result, total, truncated = await _fetch_alerts(
        coordinator, ["HIGH"], 2, None, [], [], count_total=True
    )
    assert len(result) == 2  # still capped at quantity
    assert total == 5  # but counts every match
    assert truncated is False  # short page = end of log reached


async def test_fetch_alerts_count_total_truncated_at_cap() -> None:
    """count_total flags truncated when the page cap is hit on full pages."""
    coordinator = _make_coordinator()
    coordinator.api.get_system_logs = AsyncMock(
        return_value=[
            {"id": f"evt_{i}", "title_raw": f"Alert {i}", "severity": "HIGH"}
            for i in range(ALERT_PAGE_SIZE)
        ]
    )

    result, total, truncated = await _fetch_alerts(
        coordinator, ["HIGH"], 5, None, [], [], count_total=True
    )
    assert len(result) == 5
    assert total == ALERT_PAGE_SIZE * ALERT_MAX_PAGES
    assert truncated is True
    assert coordinator.api.get_system_logs.call_count == ALERT_MAX_PAGES


# ---------------------------------------------------------------------------
# _cached_ap_name_map
# ---------------------------------------------------------------------------


def test_cached_ap_name_map_empty_data() -> None:
    """_cached_ap_name_map returns empty dict when no data."""
    coordinator = _make_coordinator(None)
    result = _cached_ap_name_map(coordinator)
    assert result == {}


def test_cached_ap_name_map_with_devices() -> None:
    """_cached_ap_name_map builds map from device data."""
    coordinator = _make_coordinator(
        {
            "devices": {
                "aa:bb:cc:dd:ee:01": {
                    "mac": "aa:bb:cc:dd:ee:01",
                    "name": "AP-1",
                    "model": "UAP-AC-Pro",
                }
            }
        }
    )
    result = _cached_ap_name_map(coordinator)
    assert result["aa:bb:cc:dd:ee:01"] == "AP-1"


def test_cached_ap_name_map_with_gateway() -> None:
    """_cached_ap_name_map includes gateway in the map."""
    coordinator = _make_coordinator(
        {
            "gateway": {"mac": "aa:bb:cc:dd:ee:ff", "name": "UDM-Pro"},
            "devices": {},
        }
    )
    result = _cached_ap_name_map(coordinator)
    assert result["aa:bb:cc:dd:ee:ff"] == "UDM-Pro"


# ---------------------------------------------------------------------------
# _rogue_response_item
# ---------------------------------------------------------------------------


def test_rogue_response_item_full() -> None:
    """_rogue_response_item shapes a full rogue AP record."""
    result = _rogue_response_item(
        {
            "essid": "TestNet",
            "ssid_anomaly": False,
            "bssid": "00:11:22:33:44:55",
            "band": "ng",
            "channel": 6,
            "channel_width": 40,
            "signal": -80,
            "security": "WPA2-Personal (AES/CCMP)",
            "oui": "VendorA",
            "wired_rogue": True,
            "is_adhoc": False,
            "last_seen": 1700000000,
            "age": "2h",
            "detected_by": "AP-1",
        },
        {},
    )
    assert result["essid"] == "TestNet"
    assert result["ssid_anomaly"] is False
    assert result["bssid"] == "00:11:22:33:44:55"
    assert result["band"] == "2.4 GHz"
    assert result["channel"] == 6
    assert result["channel_width"] == 40
    assert result["signal"] == -80
    assert result["security"] == "WPA2-Personal (AES/CCMP)"
    assert result["oui"] == "VendorA"
    assert result["wired_rogue"] is True
    assert result["is_adhoc"] is False
    assert result["last_seen"] is not None
    assert result["age"] == "2h"
    assert result["detected_by"] == "AP-1"


def test_rogue_response_item_no_last_seen() -> None:
    """_rogue_response_item handles missing last_seen."""
    result = _rogue_response_item({"bssid": "00:11:22:33:44:55"}, {})
    assert result["last_seen"] is None


def test_rogue_response_item_empty() -> None:
    """_rogue_response_item handles empty dict."""
    result = _rogue_response_item({}, {})
    assert result["essid"] is None
    assert result["bssid"] is None
    assert result["last_seen"] is None


# ---------------------------------------------------------------------------
# _handle_get_alerts (integration-style via async_register_services)
# ---------------------------------------------------------------------------


async def test_get_alerts_service_registration(hass: Any) -> None:
    """async_register_services registers get_alerts and get_rogue_aps."""
    async_register_services(hass)
    services = hass.services.async_services().get(DOMAIN, {})
    assert SERVICE_GET_ALERTS in services
    assert SERVICE_GET_ROGUE_APS in services


async def test_get_alerts_service_idempotent(hass: Any) -> None:
    """async_register_services can be called twice without error."""
    async_register_services(hass)
    async_register_services(hass)
    services = hass.services.async_services().get(DOMAIN, {})
    assert SERVICE_GET_ALERTS in services


async def test_get_alerts_service_call(hass: Any, mock_config_entry: Any) -> None:
    """End-to-end: get_alerts handler returns alerts."""
    mock_config_entry.add_to_hass(hass)
    from custom_components.unifi_network_monitor.services import _handle_get_alerts

    api = MagicMock()
    api.get_system_logs = AsyncMock(
        return_value=[
            {
                "id": "evt_001",
                "title_raw": "CPU High",
                "message_raw": "",
                "severity": "HIGH",
                "timestamp": 2000000,
            }
        ]
    )

    coord = MagicMock()
    coord.api = api
    coord.data = {"gateway": {"mac": "aa:bb:cc:dd:ee:ff"}, "devices": {}}

    entry = MagicMock()
    entry.domain = DOMAIN
    entry.runtime_data = coord
    hass.config_entries.async_entries = MagicMock(return_value=[entry])

    call = MagicMock()
    call.data = {"quantity": 5}

    response = await _handle_get_alerts(hass, call)
    assert response is not None
    assert response["count"] == 1
    assert response["alerts"][0]["id"] == "evt_001"
    # count_total defaults off — no total_matched/truncated keys.
    assert "total_matched" not in response
    assert "truncated" not in response


async def test_get_alerts_count_total(hass: Any, mock_config_entry: Any) -> None:
    """get_alerts with count_total returns total_matched and truncated."""
    mock_config_entry.add_to_hass(hass)
    from custom_components.unifi_network_monitor.services import _handle_get_alerts

    api = MagicMock()
    api.get_system_logs = AsyncMock(
        return_value=[
            {"id": f"evt_{i}", "title_raw": f"Alert {i}", "severity": "HIGH"}
            for i in range(4)
        ]
    )
    coord = MagicMock()
    coord.api = api
    coord.data = {"gateway": {"mac": "aa:bb:cc:dd:ee:ff"}, "devices": {}}
    entry = MagicMock()
    entry.domain = DOMAIN
    entry.runtime_data = coord
    hass.config_entries.async_entries = MagicMock(return_value=[entry])

    call = MagicMock()
    call.data = {"quantity": 2, "count_total": True}
    response = await _handle_get_alerts(hass, call)
    assert response["count"] == 2  # capped at quantity
    assert response["total_matched"] == 4  # full match count
    assert response["truncated"] is False  # short page = log exhausted


async def test_get_rogue_aps_service_call(hass: Any, mock_config_entry: Any) -> None:
    """End-to-end: get_rogue_aps handler returns rogue APs."""
    mock_config_entry.add_to_hass(hass)
    from custom_components.unifi_network_monitor.services import _handle_get_rogue_aps

    api = MagicMock()
    api.get_rogueaps = AsyncMock(
        return_value=[
            {
                "essid": "RogueNet",
                "bssid": "00:11:22:33:44:55",
                "band": "ng",
                "channel": 6,
                "signal": -80,
                "oui": "VendorA",
                "ap_mac": "aa:bb:cc:dd:ee:ff",
                "last_seen": 1700000000,
            }
        ]
    )

    coord = MagicMock()
    coord.api = api
    coord.data = {
        "gateway": {"mac": "aa:bb:cc:dd:ee:ff"},
        "devices": {},
    }

    entry = MagicMock()
    entry.domain = DOMAIN
    entry.runtime_data = coord
    hass.config_entries.async_entries = MagicMock(return_value=[entry])

    call = MagicMock()
    call.data = {"period": "24h", "band": "both", "quantity": 10}

    response = await _handle_get_rogue_aps(hass, call)
    assert response is not None
    assert response["count"] == 1
    assert response["rogue_aps"][0]["essid"] == "RogueNet"


# ---------------------------------------------------------------------------
# Schema validation tests
# ---------------------------------------------------------------------------


def test_get_alerts_schema_defaults() -> None:
    """GET_ALERTS_SCHEMA provides defaults for optional fields."""
    from custom_components.unifi_network_monitor.services import GET_ALERTS_SCHEMA

    data = GET_ALERTS_SCHEMA({})
    assert data["quantity"] == ALERT_QUANTITY_DEFAULT


def test_get_alerts_schema_validates_quantity() -> None:
    """GET_ALERTS_SCHEMA rejects quantity outside range."""
    from custom_components.unifi_network_monitor.services import GET_ALERTS_SCHEMA

    with pytest.raises(vol.Invalid):
        GET_ALERTS_SCHEMA({"quantity": ALERT_QUANTITY_MAX + 1})


def test_get_rogue_aps_schema_defaults() -> None:
    """GET_ROGUE_APS_SCHEMA provides defaults for optional fields."""
    from custom_components.unifi_network_monitor.services import GET_ROGUE_APS_SCHEMA

    data = GET_ROGUE_APS_SCHEMA({})
    assert data["period"] in ROGUE_ACTION_PERIOD_HOURS
    assert data["band"] in ("2.4", "5", "both")


def test_get_rogue_aps_schema_validates_quantity() -> None:
    """GET_ROGUE_APS_SCHEMA rejects quantity outside range."""
    from custom_components.unifi_network_monitor.services import GET_ROGUE_APS_SCHEMA

    with pytest.raises(vol.Invalid):
        GET_ROGUE_APS_SCHEMA({"quantity": ROGUE_QUANTITY_MAX + 1})


async def test_get_alerts_with_age_days(hass: Any, mock_config_entry: Any) -> None:
    """_handle_get_alerts handles age_days parameter (line 174)."""
    from custom_components.unifi_network_monitor.services import _handle_get_alerts

    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    api.get_system_logs = AsyncMock(return_value=[])
    coord = MagicMock()
    coord.api = api
    coord.data = {"gateway": {"mac": "aa:bb:cc:dd:ee:ff"}, "devices": {}}
    entry = MagicMock()
    entry.domain = DOMAIN
    entry.runtime_data = coord
    hass.config_entries.async_entries = MagicMock(return_value=[entry])

    call = MagicMock()
    call.data = {"quantity": 5, "age_days": 7}

    response = await _handle_get_alerts(hass, call)
    assert response is not None
    assert response["count"] == 0


async def test_get_rogue_aps_with_min_signal(hass: Any, mock_config_entry: Any) -> None:
    """_handle_get_rogue_aps filters by min_signal (line 247)."""
    from custom_components.unifi_network_monitor.services import _handle_get_rogue_aps

    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    api.get_rogueaps = AsyncMock(
        return_value=[
            {
                "essid": "WeakNet",
                "bssid": "00:11:22:33:44:55",
                "band": "ng",
                "signal": -90,
                "ap_mac": "aa:bb:cc:dd:ee:ff",
                "last_seen": 1000,
            },
        ]
    )
    api.get_devices = AsyncMock(return_value=[])
    coord = MagicMock()
    coord.api = api
    coord.data = {"gateway": {"mac": "aa:bb:cc:dd:ee:ff"}, "devices": {}}
    entry = MagicMock()
    entry.domain = DOMAIN
    entry.runtime_data = coord
    hass.config_entries.async_entries = MagicMock(return_value=[entry])

    call = MagicMock()
    call.data = {"period": "24h", "band": "both", "quantity": 10, "min_signal": -80}

    response = await _handle_get_rogue_aps(hass, call)
    assert response is not None
    assert response["count"] == 0  # filtered out by min_signal


async def test_get_rogue_aps_with_keyword(hass: Any, mock_config_entry: Any) -> None:
    """_handle_get_rogue_aps filters by keyword (lines 249-251)."""
    from custom_components.unifi_network_monitor.services import _handle_get_rogue_aps

    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    api.get_rogueaps = AsyncMock(
        return_value=[
            {
                "essid": "CorpNet",
                "bssid": "00:11:22:33:44:55",
                "band": "ng",
                "oui": "VendorX",
                "signal": -70,
                "ap_mac": "aa:bb:cc:dd:ee:ff",
                "last_seen": 1000,
            },
            {
                "essid": "GuestNet",
                "bssid": "66:77:88:99:aa:bb",
                "band": "ng",
                "signal": -75,
                "ap_mac": "aa:bb:cc:dd:ee:ff",
                "last_seen": 2000,
            },
        ]
    )
    api.get_devices = AsyncMock(return_value=[])
    coord = MagicMock()
    coord.api = api
    coord.data = {"gateway": {"mac": "aa:bb:cc:dd:ee:ff"}, "devices": {}}
    entry = MagicMock()
    entry.domain = DOMAIN
    entry.runtime_data = coord
    hass.config_entries.async_entries = MagicMock(return_value=[entry])

    call = MagicMock()
    call.data = {"period": "24h", "band": "both", "quantity": 10, "keyword": "CorpNet"}

    response = await _handle_get_rogue_aps(hass, call)
    assert response is not None
    assert response["count"] == 1
    assert response["rogue_aps"][0]["essid"] == "CorpNet"


def _rogue_action_env(hass: Any, rogueaps: list[dict[str, Any]]) -> Any:
    """Wire a MagicMock coordinator/entry for a get_rogue_aps handler call."""
    api = MagicMock()
    api.get_rogueaps = AsyncMock(return_value=rogueaps)
    api.get_devices = AsyncMock(return_value=[])
    coord = MagicMock()
    coord.api = api
    coord.data = {"gateway": {"mac": "aa:bb:cc:dd:ee:ff"}, "devices": {}}
    entry = MagicMock()
    entry.domain = DOMAIN
    entry.runtime_data = coord
    hass.config_entries.async_entries = MagicMock(return_value=[entry])


async def test_get_rogue_aps_with_exclude(hass: Any, mock_config_entry: Any) -> None:
    """_handle_get_rogue_aps drops APs matching any exclude term (comma-list)."""
    from custom_components.unifi_network_monitor.services import _handle_get_rogue_aps

    mock_config_entry.add_to_hass(hass)
    _rogue_action_env(
        hass,
        [
            {
                "essid": "CorpNet",
                "bssid": "00:11:22:33:44:55",
                "band": "ng",
                "oui": "eero",
                "signal": -70,
                "ap_mac": "aa:bb:cc:dd:ee:ff",
                "last_seen": 1000,
            },
            {
                "essid": "GuestNet",
                "bssid": "66:77:88:99:aa:bb",
                "band": "ng",
                "oui": "netgear",
                "signal": -75,
                "ap_mac": "aa:bb:cc:dd:ee:ff",
                "last_seen": 2000,
            },
        ],
    )

    call = MagicMock()
    call.data = {
        "period": "24h",
        "band": "both",
        "quantity": 10,
        "exclude": "eero, apple",
    }
    response = await _handle_get_rogue_aps(hass, call)
    assert response["count"] == 1
    assert response["rogue_aps"][0]["essid"] == "GuestNet"


async def test_get_rogue_aps_keyword_matches_security(
    hass: Any, mock_config_entry: Any
) -> None:
    """Keyword now also matches the security field."""
    from custom_components.unifi_network_monitor.services import _handle_get_rogue_aps

    mock_config_entry.add_to_hass(hass)
    _rogue_action_env(
        hass,
        [
            {
                "essid": "OpenNet",
                "bssid": "00:11:22:33:44:55",
                "band": "ng",
                "security": "Open",
                "signal": -70,
                "ap_mac": "aa:bb:cc:dd:ee:ff",
                "last_seen": 1000,
            },
            {
                "essid": "SecureNet",
                "bssid": "66:77:88:99:aa:bb",
                "band": "ng",
                "security": "WPA3-Personal (AES/CCMP)",
                "signal": -75,
                "ap_mac": "aa:bb:cc:dd:ee:ff",
                "last_seen": 2000,
            },
        ],
    )

    call = MagicMock()
    call.data = {"period": "24h", "band": "both", "quantity": 10, "keyword": "open"}
    response = await _handle_get_rogue_aps(hass, call)
    assert response["count"] == 1
    assert response["rogue_aps"][0]["essid"] == "OpenNet"


async def test_get_rogue_aps_keyword_multi_term(
    hass: Any, mock_config_entry: Any
) -> None:
    """Keyword accepts a comma-list; any matching term includes the AP."""
    from custom_components.unifi_network_monitor.services import _handle_get_rogue_aps

    mock_config_entry.add_to_hass(hass)
    _rogue_action_env(
        hass,
        [
            {
                "essid": "shelly-1A2B",
                "bssid": "00:11:22:33:44:55",
                "band": "ng",
                "signal": -60,
                "ap_mac": "aa:bb:cc:dd:ee:ff",
                "last_seen": 1000,
            },
            {
                "essid": "sonoff_1001",
                "bssid": "66:77:88:99:aa:bb",
                "band": "ng",
                "signal": -65,
                "ap_mac": "aa:bb:cc:dd:ee:ff",
                "last_seen": 2000,
            },
            {
                "essid": "NeighborNet",
                "bssid": "12:34:56:78:9a:bc",
                "band": "ng",
                "signal": -70,
                "ap_mac": "aa:bb:cc:dd:ee:ff",
                "last_seen": 3000,
            },
        ],
    )

    call = MagicMock()
    call.data = {
        "period": "24h",
        "band": "both",
        "quantity": 10,
        "keyword": "shelly, sonoff",
    }
    response = await _handle_get_rogue_aps(hass, call)
    assert response["count"] == 2
    essids = {ap["essid"] for ap in response["rogue_aps"]}
    assert essids == {"shelly-1A2B", "sonoff_1001"}


async def test_get_rogue_aps_total_matched(hass: Any, mock_config_entry: Any) -> None:
    """total_matched reports the full filtered count even when quantity caps output."""
    from custom_components.unifi_network_monitor.services import _handle_get_rogue_aps

    mock_config_entry.add_to_hass(hass)
    _rogue_action_env(
        hass,
        [
            {
                "essid": f"Net-{i}",
                "bssid": f"00:11:22:33:44:{i:02x}",
                "band": "ng",
                "signal": -60 - i,
                "ap_mac": "aa:bb:cc:dd:ee:ff",
                "last_seen": 1000 + i,
            }
            for i in range(4)
        ],
    )

    call = MagicMock()
    call.data = {"period": "24h", "band": "both", "quantity": 1}
    response = await _handle_get_rogue_aps(hass, call)
    assert response["count"] == 1  # capped at quantity
    assert response["total_matched"] == 4  # full filtered count
    assert len(response["rogue_aps"]) == 1


async def test_service_handlers_via_registration(hass: Any) -> None:
    """Test the inner wrapper functions (lines 269, 272) via service registration."""
    from custom_components.unifi_network_monitor.const import DOMAIN
    from custom_components.unifi_network_monitor.services import (
        SERVICE_GET_ALERTS,
        SERVICE_GET_ROGUE_APS,
        async_register_services,
    )

    async_register_services(hass)
    services = hass.services.async_services().get(DOMAIN, {})
    assert SERVICE_GET_ALERTS in services
    assert SERVICE_GET_ROGUE_APS in services


async def test_service_wrappers_called_through_hass(
    hass: Any, mock_config_entry: Any
) -> None:
    """Call services via HA to invoke wrapper defs (lines 269, 272)."""
    from custom_components.unifi_network_monitor.const import (
        DOMAIN,
        SERVICE_ADD_ROGUE_IGNORE,
        SERVICE_CLEAR_ROGUE_HISTORY,
        SERVICE_GET_ALERTS,
        SERVICE_GET_ROGUE_APS,
        SERVICE_REMOVE_ROGUE_IGNORE,
        SERVICE_SET_ROGUE_IGNORE,
    )
    from custom_components.unifi_network_monitor.services import (
        async_register_services,
    )

    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    api.get_system_logs = AsyncMock(return_value=[])
    api.get_rogueaps = AsyncMock(return_value=[])
    api.get_devices = AsyncMock(return_value=[])
    coord = MagicMock()
    coord.api = api
    coord.async_clear_rogue_history = AsyncMock()
    coord.data = {"gateway": {"mac": "aa:bb:cc:dd:ee:ff"}, "devices": {}}
    mock_config_entry.runtime_data = coord
    hass.config_entries.async_entries = MagicMock(return_value=[mock_config_entry])
    hass.config_entries.async_get_entry = MagicMock(return_value=mock_config_entry)

    async_register_services(hass)

    alerts_response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_ALERTS,
        service_data={"quantity": 5},
        blocking=True,
        return_response=True,
    )
    assert alerts_response is not None
    assert alerts_response["count"] == 0

    rogue_response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_ROGUE_APS,
        service_data={"period": "24h", "band": "both", "quantity": 10},
        blocking=True,
        return_response=True,
    )
    assert rogue_response is not None
    assert rogue_response["count"] == 0

    clear_response = await hass.services.async_call(
        DOMAIN,
        SERVICE_CLEAR_ROGUE_HISTORY,
        service_data={},
        blocking=True,
    )
    assert clear_response is None

    add_response = await hass.services.async_call(
        DOMAIN,
        SERVICE_ADD_ROGUE_IGNORE,
        service_data={"target": "ssids", "value": "Guest_*"},
        blocking=True,
        return_response=True,
    )
    assert add_response is not None

    remove_response = await hass.services.async_call(
        DOMAIN,
        SERVICE_REMOVE_ROGUE_IGNORE,
        service_data={"target": "aps", "value": "AP1"},
        blocking=True,
        return_response=True,
    )
    assert remove_response is not None

    set_response = await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_ROGUE_IGNORE,
        service_data={"target": "ssids", "values": "New1, New2"},
        blocking=True,
        return_response=True,
    )
    assert set_response is not None


# ---------------------------------------------------------------------------
# Persistent history in the action response + clear service
# ---------------------------------------------------------------------------


async def test_get_rogue_aps_includes_history(
    hass: Any, mock_config_entry: Any
) -> None:
    """get_rogue_aps annotates each AP with first_seen/appearances from history."""
    from custom_components.unifi_network_monitor.services import _handle_get_rogue_aps

    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    api.get_rogueaps = AsyncMock(
        return_value=[
            {
                "essid": "CorpNet",
                "bssid": "00:11:22:33:44:55",
                "band": "ng",
                "signal": -70,
                "ap_mac": "aa:bb:cc:dd:ee:ff",
                "last_seen": 1000,
            }
        ]
    )
    api.get_devices = AsyncMock(return_value=[])
    coord = MagicMock()
    coord.api = api
    coord.data = {"gateway": {"mac": "aa:bb:cc:dd:ee:ff"}, "devices": {}}
    coord.rogue_history = {
        "00:11:22:33:44:55": {
            "first_seen": "2026-07-01T00:00:00+00:00",
            "appearances": 42,
        }
    }
    entry = MagicMock()
    entry.domain = DOMAIN
    entry.runtime_data = coord
    hass.config_entries.async_entries = MagicMock(return_value=[entry])

    call = MagicMock()
    call.data = {"period": "24h", "band": "both", "quantity": 10}
    response = await _handle_get_rogue_aps(hass, call)
    ap = response["rogue_aps"][0]
    assert ap["first_seen"] == "2026-07-01T00:00:00+00:00"
    assert ap["appearances"] == 42


async def test_clear_rogue_history_service(hass: Any, mock_config_entry: Any) -> None:
    """clear_rogue_history resolves the coordinator and clears its history."""
    from custom_components.unifi_network_monitor.services import (
        _handle_clear_rogue_history,
    )

    coord = MagicMock()
    coord.async_clear_rogue_history = AsyncMock()
    entry = MagicMock()
    entry.domain = DOMAIN
    entry.runtime_data = coord
    hass.config_entries.async_entries = MagicMock(return_value=[entry])

    call = MagicMock()
    call.data = {}
    response = await _handle_clear_rogue_history(hass, call)
    assert response is None
    coord.async_clear_rogue_history.assert_awaited_once()


# ---------------------------------------------------------------------------
# Ignore-list management services
# ---------------------------------------------------------------------------


async def test_add_rogue_ignore(hass: Any, mock_config_entry: Any) -> None:
    """add_rogue_ignore appends a pattern to the chosen list."""
    from custom_components.unifi_network_monitor.services import (
        _handle_add_rogue_ignore,
    )

    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = MagicMock()

    call = MagicMock()
    call.data = {"target": "ssids", "value": "Guest_*"}
    response = await _handle_add_rogue_ignore(hass, call)
    assert response["target"] == "ssids"
    assert "Guest_*" in response["entries"]
    assert mock_config_entry.options.get("rogue_ignore_ssids") == "Guest_*"


async def test_remove_rogue_ignore(hass: Any, mock_config_entry: Any) -> None:
    """remove_rogue_ignore drops an exact pattern from the chosen list."""
    from custom_components.unifi_network_monitor.services import (
        _handle_remove_rogue_ignore,
    )

    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={**mock_config_entry.options, "rogue_ignore_aps": "AP1, AP2"},
    )
    mock_config_entry.runtime_data = MagicMock()

    call = MagicMock()
    call.data = {"target": "aps", "value": "AP1"}
    response = await _handle_remove_rogue_ignore(hass, call)
    assert response["entries"] == ["AP2"]
    assert mock_config_entry.options.get("rogue_ignore_aps") == "AP2"


async def test_set_rogue_ignore_returns_old_new(
    hass: Any, mock_config_entry: Any
) -> None:
    """set_rogue_ignore replaces the list and returns old + new."""
    from custom_components.unifi_network_monitor.services import (
        _handle_set_rogue_ignore,
    )

    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={**mock_config_entry.options, "rogue_ignore_ssids": "Old1, Old2"},
    )
    mock_config_entry.runtime_data = MagicMock()

    call = MagicMock()
    call.data = {"target": "ssids", "values": "New1, New2, New3"}
    response = await _handle_set_rogue_ignore(hass, call)
    assert response["old"] == ["Old1", "Old2"]
    assert response["new"] == ["New1", "New2", "New3"]
    assert mock_config_entry.options.get("rogue_ignore_ssids") == "New1, New2, New3"
