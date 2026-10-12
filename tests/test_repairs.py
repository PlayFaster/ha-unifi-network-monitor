"""Tests for repair-issue identity and lifecycle.

Two defects from the August 2026 plan (§M Phase 1):

- **item 5** — both repair issues used a bare, integration-global ``issue_id``.
  Multi-entry is reachable here (``config_flow`` sets ``unique_id`` from the
  gateway MAC, so two UDMs are two entries), and a bare id means the second
  entry's repair overwrites the first's and either entry clearing it clears it
  for both.
- **item 4** — neither ``async_unload_entry`` nor ``async_remove_entry``
  touched the issue registry, so deleting the integration with a repair raised
  left it in the panel permanently with nothing remaining that could clear it.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.unifi_network_monitor.const import (
    DOMAIN,
    REPAIR_ISSUE_NAMES,
    repair_issue_id,
)
from custom_components.unifi_network_monitor.coordinator import (
    UnifiNetworkDataUpdateCoordinator,
)
from homeassistant.helpers import issue_registry as ir


def test_repair_issue_id_is_entry_scoped() -> None:
    """The id embeds the entry, so two entries cannot collide."""
    assert repair_issue_id("abc123", "site_resolution_failed") == (
        "abc123_site_resolution_failed"
    )
    assert repair_issue_id("abc123", "x") != repair_issue_id("def456", "x")


def test_repair_issue_names_cover_all_four_repairs() -> None:
    """The clear-on-teardown list must not drift from the raise sites."""
    assert set(REPAIR_ISSUE_NAMES) == {
        "site_resolution_failed",
        "schema_drift_detected",
        "gateway_not_recognized",
        "gateway_identity_blocked",
    }


# ---------------------------------------------------------------------------
# item 5 — entry-scoped ids, bare translation_key
# ---------------------------------------------------------------------------


async def test_site_issue_uses_entry_scoped_id(
    hass: Any, mock_config_entry: Any
) -> None:
    """The site repair is raised and cleared under the entry-scoped id."""
    mock_config_entry.add_to_hass(hass)
    api = MagicMock()
    api.api_key = "key"
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    issue_id = repair_issue_id(mock_config_entry.entry_id, "site_resolution_failed")

    coordinator.site_uuid = "failed"
    coordinator._sync_site_issue()
    reg = ir.async_get(hass)
    issue = reg.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    # The user-visible text is shared across entries — only the id is scoped.
    assert issue.translation_key == "site_resolution_failed"
    assert reg.async_get_issue(DOMAIN, "site_resolution_failed") is None

    coordinator.site_uuid = "uuid-1"
    coordinator._sync_site_issue()
    assert reg.async_get_issue(DOMAIN, issue_id) is None


async def test_drift_issue_uses_entry_scoped_id(
    hass: Any, mock_config_entry: Any
) -> None:
    """The schema-drift repair is raised and cleared under the entry-scoped id."""
    mock_config_entry.add_to_hass(hass)
    coordinator = UnifiNetworkDataUpdateCoordinator(
        hass, mock_config_entry, MagicMock()
    )
    issue_id = repair_issue_id(mock_config_entry.entry_id, "schema_drift_detected")

    coordinator._sync_health_issues({"drift": ["Security"]})
    reg = ir.async_get(hass)
    issue = reg.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.translation_key == "schema_drift_detected"

    coordinator._sync_health_issues({"drift": []})
    assert reg.async_get_issue(DOMAIN, issue_id) is None


async def test_two_entries_do_not_share_a_repair(
    hass: Any, mock_config_entry: Any
) -> None:
    """Clearing one entry's repair must not clear the other's."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    mock_config_entry.add_to_hass(hass)
    second = MockConfigEntry(
        domain=DOMAIN,
        data=dict(mock_config_entry.data),
        options=dict(mock_config_entry.options),
        unique_id="ff:ee:dd:cc:bb:aa",
    )
    second.add_to_hass(hass)

    api = MagicMock()
    api.api_key = "key"
    first_coord = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
    second_coord = UnifiNetworkDataUpdateCoordinator(hass, second, api)

    first_coord.site_uuid = "failed"
    second_coord.site_uuid = "failed"
    first_coord._sync_site_issue()
    second_coord._sync_site_issue()

    reg = ir.async_get(hass)
    first_id = repair_issue_id(mock_config_entry.entry_id, "site_resolution_failed")
    second_id = repair_issue_id(second.entry_id, "site_resolution_failed")
    assert reg.async_get_issue(DOMAIN, first_id) is not None
    assert reg.async_get_issue(DOMAIN, second_id) is not None

    # The first entry recovers; the second is still broken and must stay flagged.
    first_coord.site_uuid = "uuid-1"
    first_coord._sync_site_issue()
    assert reg.async_get_issue(DOMAIN, first_id) is None
    assert reg.async_get_issue(DOMAIN, second_id) is not None


# ---------------------------------------------------------------------------
# item 4 — cleared on unload and on removal
# ---------------------------------------------------------------------------


async def test_unload_clears_repair_issues(hass: Any, mock_config_entry: Any) -> None:
    """Unloading the entry takes its repairs down with it."""
    from custom_components.unifi_network_monitor import async_unload_entry

    mock_config_entry.add_to_hass(hass)
    reg = ir.async_get(hass)
    for name in REPAIR_ISSUE_NAMES:
        ir.async_create_issue(
            hass,
            DOMAIN,
            repair_issue_id(mock_config_entry.entry_id, name),
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=name,
        )

    coordinator = MagicMock()
    coordinator.async_flush_stores = AsyncMock()
    coordinator.api.logout = AsyncMock()
    mock_config_entry.runtime_data = coordinator

    with patch.object(
        hass.config_entries, "async_unload_platforms", AsyncMock(return_value=True)
    ):
        assert await async_unload_entry(hass, mock_config_entry) is True

    for name in REPAIR_ISSUE_NAMES:
        assert (
            reg.async_get_issue(
                DOMAIN, repair_issue_id(mock_config_entry.entry_id, name)
            )
            is None
        )


async def test_remove_entry_clears_repair_issues(
    hass: Any, mock_config_entry: Any
) -> None:
    """Removing the entry leaves nothing behind in the Repairs panel.

    This is the one that mattered: after removal there is no coordinator left
    that could ever clear a stale repair, so it would sit there forever.
    """
    from custom_components.unifi_network_monitor import async_remove_entry

    mock_config_entry.add_to_hass(hass)
    reg = ir.async_get(hass)
    for name in REPAIR_ISSUE_NAMES:
        ir.async_create_issue(
            hass,
            DOMAIN,
            repair_issue_id(mock_config_entry.entry_id, name),
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=name,
        )

    await async_remove_entry(hass, mock_config_entry)

    for name in REPAIR_ISSUE_NAMES:
        assert (
            reg.async_get_issue(
                DOMAIN, repair_issue_id(mock_config_entry.entry_id, name)
            )
            is None
        )


async def test_clearing_repairs_is_safe_when_none_raised(
    hass: Any, mock_config_entry: Any
) -> None:
    """Teardown with no repairs raised must not raise."""
    from custom_components.unifi_network_monitor import async_remove_entry

    mock_config_entry.add_to_hass(hass)
    reg = ir.async_get(hass)

    await async_remove_entry(hass, mock_config_entry)

    # Nothing was raised, so nothing is left — and no issue belonging to any
    # other integration was swept up on the way past.
    for name in REPAIR_ISSUE_NAMES:
        assert (
            reg.async_get_issue(
                DOMAIN, repair_issue_id(mock_config_entry.entry_id, name)
            )
            is None
        )
    assert reg.issues == {}


# ---------------------------------------------------------------------------
# gateway_not_recognized (v1.1.0-dev12 I4)
# ---------------------------------------------------------------------------

_SWITCH = {"mac": "aa:00:00:00:00:01", "model": "USM8P210", "type": "usw"}
_AP = {"mac": "aa:00:00:00:00:02", "model": "U6LR", "type": "uap"}
_UNKNOWN = {"mac": "aa:00:00:00:00:03", "model": "UNKNOWNX", "type": "uxx"}


def _gateway_coordinator(hass: Any, entry: Any) -> UnifiNetworkDataUpdateCoordinator:
    entry.add_to_hass(hass)
    return UnifiNetworkDataUpdateCoordinator(hass, entry, MagicMock())


def _poll(coordinator: UnifiNetworkDataUpdateCoordinator, devices: list[Any]) -> None:
    from custom_components.unifi_network_monitor.gateway import select_gateway

    coordinator._sync_gateway_issue(select_gateway(devices), devices)


async def test_none_on_three_polls_raises_listing_non_switch_non_ap_models(
    hass: Any, mock_config_entry: Any
) -> None:
    """No gateway on three consecutive polls raises the repair at ERROR."""
    coordinator = _gateway_coordinator(hass, mock_config_entry)
    issue_id = repair_issue_id(mock_config_entry.entry_id, "gateway_not_recognized")
    reg = ir.async_get(hass)
    devices = [_SWITCH, _AP, _UNKNOWN]

    _poll(coordinator, devices)
    _poll(coordinator, devices)
    assert reg.async_get_issue(DOMAIN, issue_id) is None
    _poll(coordinator, devices)

    issue = reg.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.severity == ir.IssueSeverity.ERROR
    assert issue.translation_key == "gateway_not_recognized"
    assert issue.translation_placeholders == {"models": "UNKNOWNX"}


async def test_ambiguous_lists_the_tied_candidates(
    hass: Any, mock_config_entry: Any
) -> None:
    """Two tied gateways name both candidate models."""
    coordinator = _gateway_coordinator(hass, mock_config_entry)
    issue_id = repair_issue_id(mock_config_entry.entry_id, "gateway_not_recognized")
    tied = [
        {"mac": "aa:00:00:00:00:0a", "model": "UDMPRO", "wan1": {"up": True}},
        {"mac": "aa:00:00:00:00:0b", "model": "UDRULT", "wan1": {"up": True}},
        _SWITCH,
    ]
    for _ in range(3):
        _poll(coordinator, tied)

    issue = ir.async_get(hass).async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.translation_placeholders == {"models": "UDMPRO, UDRULT"}


async def test_a_single_miss_raises_nothing(hass: Any, mock_config_entry: Any) -> None:
    """One poll without a gateway, as during a reboot, raises no repair."""
    coordinator = _gateway_coordinator(hass, mock_config_entry)
    issue_id = repair_issue_id(mock_config_entry.entry_id, "gateway_not_recognized")

    _poll(coordinator, [_SWITCH])

    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None


async def test_a_selected_gateway_clears_the_repair(
    hass: Any, mock_config_entry: Any
) -> None:
    """A later poll that selects a gateway clears the repair and the strikes."""
    coordinator = _gateway_coordinator(hass, mock_config_entry)
    issue_id = repair_issue_id(mock_config_entry.entry_id, "gateway_not_recognized")
    reg = ir.async_get(hass)
    for _ in range(3):
        _poll(coordinator, [_SWITCH])
    assert reg.async_get_issue(DOMAIN, issue_id) is not None

    gateway = {"mac": "aa:00:00:00:00:0c", "type": "udm", "wan1": {"up": True}}
    _poll(coordinator, [_SWITCH, gateway])

    assert reg.async_get_issue(DOMAIN, issue_id) is None
    assert coordinator._gateway_miss_strikes == 0


async def test_unlisted_gateway_by_signature_raises_nothing_and_health_stays_off(
    hass: Any, mock_config_entry: Any
) -> None:
    """A working unlisted gateway changes nothing the user sees (E20).

    The mock payload is sparse, so Integration Health reports the same drift for
    any gateway; the unlisted gateway's health must equal a listed one's.
    """
    from tests.test_coordinator_branches import _api

    mock_config_entry.add_to_hass(hass)
    issue_id = repair_issue_id(mock_config_entry.entry_id, "gateway_not_recognized")

    async def _health(model: str) -> tuple[Any, dict[str, Any]]:
        gateway = {
            "mac": "aa:bb:cc:dd:ee:ff",
            "model": model,
            "type": "udm",
            "state": 1,
            "wan1": {"ifname": "eth4", "up": True},
        }
        api = _api(get_devices=AsyncMock(return_value=[gateway, dict(_SWITCH)]))
        coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)
        for _ in range(3):
            await coordinator._async_update_data()
        return coordinator.gateway_selection, dict(coordinator.health_snapshot or {})

    selection, unlisted = await _health("UNLISTED9")
    _, listed = await _health("UDMPRO")

    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None
    assert selection is not None
    assert selection.reason == "wan_signature"
    for snapshot in (unlisted, listed):
        snapshot.pop("last_good_update", None)
    assert unlisted == listed
