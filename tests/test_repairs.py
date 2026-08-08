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

from homeassistant.helpers import issue_registry as ir

from custom_components.unifi_network_monitor.const import (
    DOMAIN,
    REPAIR_ISSUE_NAMES,
    repair_issue_id,
)
from custom_components.unifi_network_monitor.coordinator import (
    UnifiNetworkDataUpdateCoordinator,
)


def test_repair_issue_id_is_entry_scoped() -> None:
    """The id embeds the entry, so two entries cannot collide."""
    assert repair_issue_id("abc123", "site_resolution_failed") == (
        "abc123_site_resolution_failed"
    )
    assert repair_issue_id("abc123", "x") != repair_issue_id("def456", "x")


def test_repair_issue_names_cover_both_repairs() -> None:
    """The clear-on-teardown list must not drift from the raise sites."""
    assert set(REPAIR_ISSUE_NAMES) == {
        "site_resolution_failed",
        "schema_drift_detected",
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
    await async_remove_entry(hass, mock_config_entry)
