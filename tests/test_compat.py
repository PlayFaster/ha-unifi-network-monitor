"""Tests for the HA-version device-registry compatibility shims.

The suite runs on whatever HA the devcontainer has (≤2026.7 today), so the
2026.8+ branches would never execute — and would drop coverage — unless forced.
Each test patches the module capability flags to exercise both the old and new
paths regardless of the installed HA version.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from custom_components.unifi_network_monitor import _compat

DOMAIN = "unifi_network_monitor"
IDENT = "aa:bb:cc:dd:ee:ff"
ENTRY_ID = "entry123"


# --- device_by_identifier ---------------------------------------------------


def test_device_by_identifier_new_api() -> None:
    """2026.8+: scoped lookup by identifier + owning entry id."""
    dev_reg = MagicMock()
    sentinel = object()
    dev_reg.async_get_device_by_identifier = MagicMock(return_value=sentinel)

    with patch.object(_compat, "_HAS_BY_IDENTIFIER", True):
        result = _compat.device_by_identifier(dev_reg, DOMAIN, IDENT, ENTRY_ID)

    assert result is sentinel
    dev_reg.async_get_device_by_identifier.assert_called_once_with(
        (DOMAIN, IDENT), ENTRY_ID
    )


def test_device_by_identifier_old_api() -> None:
    """≤2026.7: fall back to async_get_device(identifiers=...)."""
    dev_reg = MagicMock()
    sentinel = object()
    dev_reg.async_get_device = MagicMock(return_value=sentinel)

    with patch.object(_compat, "_HAS_BY_IDENTIFIER", False):
        result = _compat.device_by_identifier(dev_reg, DOMAIN, IDENT, ENTRY_ID)

    assert result is sentinel
    dev_reg.async_get_device.assert_called_once_with(identifiers={(DOMAIN, IDENT)})


# --- owning_entry_ids -------------------------------------------------------


def test_owning_entry_ids_new_scalar() -> None:
    """2026.8+: the single config_entry_id, as a one-item list."""
    device = MagicMock()
    device.config_entry_id = ENTRY_ID

    with patch.object(_compat, "_HAS_CONFIG_ENTRY_ID", True):
        assert _compat.owning_entry_ids(device) == [ENTRY_ID]


def test_owning_entry_ids_new_scalar_none() -> None:
    """2026.8+: a device with no owning entry yields an empty list."""
    device = MagicMock()
    device.config_entry_id = None

    with patch.object(_compat, "_HAS_CONFIG_ENTRY_ID", True):
        assert _compat.owning_entry_ids(device) == []


def test_owning_entry_ids_old_set() -> None:
    """≤2026.7: the config_entries set, as a list."""
    device = MagicMock()
    device.config_entries = {ENTRY_ID}

    with patch.object(_compat, "_HAS_CONFIG_ENTRY_ID", False):
        assert _compat.owning_entry_ids(device) == [ENTRY_ID]


# --- via_device_link --------------------------------------------------------


def test_via_device_link_new_resolves_parent_id() -> None:
    """2026.8+: resolve the parent's id and return via_device_id."""
    parent = MagicMock()
    parent.id = "parent_device_id"
    reg = MagicMock()
    reg.async_get_device_by_identifier = MagicMock(return_value=parent)

    with (
        patch.object(_compat, "_HAS_BY_IDENTIFIER", True),
        patch.object(_compat.dr, "async_get", return_value=reg),
    ):
        link: dict[str, Any] = _compat.via_device_link(
            MagicMock(), DOMAIN, IDENT, ENTRY_ID
        )

    assert link == {"via_device_id": "parent_device_id"}
    reg.async_get_device_by_identifier.assert_called_once_with(
        (DOMAIN, IDENT), ENTRY_ID
    )


def test_via_device_link_new_unresolved_parent() -> None:
    """2026.8+: an unresolved parent yields no link."""
    reg = MagicMock()
    reg.async_get_device_by_identifier = MagicMock(return_value=None)

    with (
        patch.object(_compat, "_HAS_BY_IDENTIFIER", True),
        patch.object(_compat.dr, "async_get", return_value=reg),
    ):
        assert _compat.via_device_link(MagicMock(), DOMAIN, IDENT, ENTRY_ID) == {}


def test_via_device_link_old_tuple() -> None:
    """≤2026.7: return the via_device identifier tuple unchanged."""
    with patch.object(_compat, "_HAS_BY_IDENTIFIER", False):
        link = _compat.via_device_link(MagicMock(), DOMAIN, IDENT, ENTRY_ID)

    assert link == {"via_device": (DOMAIN, IDENT)}
