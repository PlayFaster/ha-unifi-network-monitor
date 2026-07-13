"""Tests for services module."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol

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

    with pytest.raises(Exception, match="No UniFi Network Monitor entries are loaded"):
        _resolve_coordinator(hass, call)


def test_resolve_coordinator_multiple_entries_no_device() -> None:
    """_resolve_coordinator raises when multiple entries and no device_id."""
    hass = MagicMock()
    entry1 = _make_entry()
    entry2 = _make_entry()
    hass.config_entries.async_entries = MagicMock(return_value=[entry1, entry2])
    call = MagicMock()
    call.data = {}

    with pytest.raises(Exception, match="specify a device"):
        _resolve_coordinator(hass, call)


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
        pytest.raises(Exception, match="Unknown device id"),
    ):
        _resolve_coordinator(hass, call)


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
        pytest.raises(Exception, match="not a UniFi Network Monitor device"),
    ):
        _resolve_coordinator(hass, call)


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
# _fetch_alerts
# ---------------------------------------------------------------------------


async def test_fetch_alerts_empty_batch() -> None:
    """_fetch_alerts stops on empty batch."""
    coordinator = _make_coordinator()
    coordinator.api.get_system_logs = AsyncMock(return_value=[])

    result = await _fetch_alerts(coordinator, ["HIGH"], 10, None, "")
    assert result == []


async def test_fetch_alerts_collects_up_to_quantity() -> None:
    """_fetch_alerts returns up to quantity alerts."""
    coordinator = _make_coordinator()
    coordinator.api.get_system_logs = AsyncMock(
        return_value=[
            {"id": f"evt_{i}", "title_raw": f"Alert {i}", "severity": "HIGH"}
            for i in range(5)
        ]
    )

    result = await _fetch_alerts(coordinator, ["HIGH"], 3, None, "")
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

    result = await _fetch_alerts(coordinator, ["HIGH"], 10, 1000, "")
    assert len(result) == 1
    assert result[0]["id"] == "evt_1"


async def test_fetch_alerts_keyword_filter() -> None:
    """_fetch_alerts filters by keyword."""
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

    result = await _fetch_alerts(coordinator, ["HIGH"], 10, None, "cpu")
    assert len(result) == 1
    assert result[0]["id"] == "evt_1"


async def test_fetch_alerts_short_page_ends_early() -> None:
    """_fetch_alerts stops when page has fewer records than page_size."""
    coordinator = _make_coordinator()
    coordinator.api.get_system_logs = AsyncMock(
        return_value=[{"id": "evt_1", "title_raw": "Only one", "severity": "HIGH"}]
    )

    result = await _fetch_alerts(coordinator, ["HIGH"], 10, None, "")
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

    result = await _fetch_alerts(
        coordinator, ["HIGH"], ALERT_PAGE_SIZE * ALERT_MAX_PAGES, None, ""
    )
    assert len(result) == ALERT_PAGE_SIZE * ALERT_MAX_PAGES
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
            "bssid": "00:11:22:33:44:55",
            "band": "ng",
            "channel": 6,
            "signal": -80,
            "oui": "VendorA",
            "last_seen": 1700000000,
            "age": "2h",
            "detected_by": "AP-1",
        }
    )
    assert result["essid"] == "TestNet"
    assert result["bssid"] == "00:11:22:33:44:55"
    assert result["band"] == "2.4 GHz"
    assert result["channel"] == 6
    assert result["signal"] == -80
    assert result["oui"] == "VendorA"
    assert result["last_seen"] is not None
    assert result["age"] == "2h"
    assert result["detected_by"] == "AP-1"


def test_rogue_response_item_no_last_seen() -> None:
    """_rogue_response_item handles missing last_seen."""
    result = _rogue_response_item({"bssid": "00:11:22:33:44:55"})
    assert result["last_seen"] is None


def test_rogue_response_item_empty() -> None:
    """_rogue_response_item handles empty dict."""
    result = _rogue_response_item({})
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
            {"essid": "WeakNet", "bssid": "00:11:22:33:44:55", "band": "ng",
             "signal": -90, "ap_mac": "aa:bb:cc:dd:ee:ff", "last_seen": 1000},
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
            {"essid": "CorpNet", "bssid": "00:11:22:33:44:55", "band": "ng",
             "oui": "VendorX", "signal": -70, "ap_mac": "aa:bb:cc:dd:ee:ff",
             "last_seen": 1000},
            {"essid": "GuestNet", "bssid": "66:77:88:99:aa:bb", "band": "ng",
             "signal": -75, "ap_mac": "aa:bb:cc:dd:ee:ff", "last_seen": 2000},
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
    from custom_components.unifi_network_monitor.const import DOMAIN
    from custom_components.unifi_network_monitor.services import (
        SERVICE_GET_ALERTS,
        SERVICE_GET_ROGUE_APS,
        async_register_services,
    )

    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    api.get_system_logs = AsyncMock(return_value=[])
    api.get_rogueaps = AsyncMock(return_value=[])
    api.get_devices = AsyncMock(return_value=[])
    coord = MagicMock()
    coord.api = api
    coord.data = {"gateway": {"mac": "aa:bb:cc:dd:ee:ff"}, "devices": {}}
    entry = MagicMock()
    entry.domain = DOMAIN
    entry.runtime_data = coord
    hass.config_entries.async_entries = MagicMock(return_value=[entry])

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
