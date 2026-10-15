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

import ast
import json
from pathlib import Path
import re
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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


_COMPONENT = (
    Path(__file__).parent.parent / "custom_components" / "unifi_network_monitor"
)


def _raised_repair_names() -> set[str]:
    """Collect the name argument of every ``repair_issue_id`` call in the component.

    String literals are taken as they are, and a module constant (such as
    ``identity.BLOCKED_ISSUE``) is resolved from its module. The one call whose
    name iterates ``REPAIR_ISSUE_NAMES`` itself, the clearing loop in
    ``__init__.py``, is skipped: it reads the list this test checks.
    """
    names: set[str] = set()
    for path in sorted(_COMPONENT.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        constants = {
            target.id: node.value.value
            for node in tree.body
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant)
            for target in node.targets
            if isinstance(target, ast.Name) and isinstance(node.value.value, str)
        }
        loop_vars = {
            node.target.id
            for node in ast.walk(tree)
            if isinstance(node, ast.For)
            and isinstance(node.target, ast.Name)
            and isinstance(node.iter, ast.Name)
            and node.iter.id == "REPAIR_ISSUE_NAMES"
        }
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and getattr(node.func, "id", getattr(node.func, "attr", None))
                == "repair_issue_id"
                and len(node.args) == 2
            ):
                continue
            arg = node.args[1]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                names.add(arg.value)
            elif isinstance(arg, ast.Name) and arg.id in loop_vars:
                continue
            elif isinstance(arg, ast.Name) and arg.id in constants:
                names.add(constants[arg.id])
            else:
                raise AssertionError(
                    f"{path.name}:{node.lineno}: repair_issue_id name not resolvable"
                )
    return names


def test_every_repair_the_code_raises_is_registered_for_removal() -> None:
    """Every repair name raised in the component is cleared on unload and removal."""
    raised = _raised_repair_names()
    assert len(raised) >= 4, "the sweep found too few raise sites to mean anything"
    assert raised == set(REPAIR_ISSUE_NAMES)


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


# ---------------------------------------------------------------------------
# Real polls through the HTTP seam (C-021): `api.py` runs for real over
# `aioclient_mock`, so each outcome below is produced by what the controller
# answered, not by a mock that hands the coordinator its conclusion.
# ---------------------------------------------------------------------------


async def _seam_coordinator(hass: Any, entry: Any) -> UnifiNetworkDataUpdateCoordinator:
    from .transport import real_api

    if hass.config_entries.async_get_entry(entry.entry_id) is None:
        entry.add_to_hass(hass)
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, entry, real_api(hass))
    await coordinator.async_initialize()
    return coordinator


async def _seam_polls(
    coordinator: UnifiNetworkDataUpdateCoordinator, times: int
) -> None:
    for _ in range(times):
        coordinator.data = await coordinator._async_update_data()


def _issue(hass: Any, entry: Any, name: str) -> Any:
    return ir.async_get(hass).async_get_issue(
        DOMAIN, repair_issue_id(entry.entry_id, name)
    )


async def test_a_good_controller_raises_neither_repair(
    hass: Any, mock_config_entry: Any, aioclient_mock: Any
) -> None:
    """The fake's baseline: a resolved site and a readable gateway raise nothing."""
    from .transport import SITE_UUID, ControllerFake

    ControllerFake(aioclient_mock).serve()
    coordinator = await _seam_coordinator(hass, mock_config_entry)
    await _seam_polls(coordinator, 3)
    assert coordinator.site_uuid == SITE_UUID
    assert coordinator.data["gateway"]["cpu"] == 12.5
    assert _issue(hass, mock_config_entry, "site_resolution_failed") is None
    assert _issue(hass, mock_config_entry, "schema_drift_detected") is None


async def test_an_unlisted_site_raises_site_resolution_failed(
    hass: Any, mock_config_entry: Any, aioclient_mock: Any
) -> None:
    """The v1 sites list lacks the configured site, so the repair is raised."""
    from .transport import ControllerFake

    ControllerFake(aioclient_mock).serve(
        sites=[{"id": "other-uuid", "internalReference": "branch_office"}]
    )
    coordinator = await _seam_coordinator(hass, mock_config_entry)
    await _seam_polls(coordinator, 1)
    assert coordinator.site_uuid == "failed"
    assert _issue(hass, mock_config_entry, "site_resolution_failed") is not None
    assert coordinator.health_snapshot["v3_available"] is False


async def test_a_renamed_stats_block_raises_schema_drift_detected(
    hass: Any, mock_config_entry: Any, aioclient_mock: Any
) -> None:
    """A gateway whose stats no longer parse raises drift after the strike limit."""
    from custom_components.unifi_network_monitor.const import HEALTH_DRIFT_STRIKE_LIMIT

    from .transport import DRIFTED_GATEWAY, ControllerFake

    fake = ControllerFake(aioclient_mock)
    fake.serve(DRIFTED_GATEWAY)
    coordinator = await _seam_coordinator(hass, mock_config_entry)
    await _seam_polls(coordinator, HEALTH_DRIFT_STRIKE_LIMIT - 1)
    assert _issue(hass, mock_config_entry, "schema_drift_detected") is None
    await _seam_polls(coordinator, 1)
    issue = _issue(hass, mock_config_entry, "schema_drift_detected")
    assert issue is not None
    assert coordinator.health_snapshot["severity"] == "error"

    fake.serve()
    await _seam_polls(coordinator, 1)
    assert _issue(hass, mock_config_entry, "schema_drift_detected") is None


# ---------------------------------------------------------------------------
# Contract sweeps over the repair set (C-022 step 8, C-035). Each asserts a
# property of every member of `REPAIR_ISSUE_NAMES`, the set `__init__.py`
# clears on removal, rather than of one mechanism.
# ---------------------------------------------------------------------------


def _load_text(name: str) -> dict[str, Any]:
    return json.loads((_COMPONENT / name).read_text(encoding="utf-8"))


def _text_files() -> list[str]:
    """Every file that must carry the rendered text, `strings.json` included."""
    return ["strings.json"] + [
        f"translations/{p.name}"
        for p in sorted((_COMPONENT / "translations").glob("*.json"))
    ]


def test_every_repair_issue_has_title_and_rendered_text() -> None:
    """A missing entry shows the raw key, or a card with an empty body.

    `hassfest` requires a `title` and exactly one of `description` or
    `fix_flow`, so the sweep asserts that form rather than both.
    """
    for name in _text_files():
        issues = _load_text(name).get("issues", {})
        for key in REPAIR_ISSUE_NAMES:
            assert key in issues, f"{name}: no text for repair '{key}'"
            text = issues[key]
            assert text.get("title"), f"{name}: '{key}' has no title"
            assert bool(text.get("description")) != bool(text.get("fix_flow")), (
                f"{name}: '{key}' must carry exactly one of description or fix_flow"
            )


def test_every_repair_issue_has_translated_text() -> None:
    """Each translation renders the same placeholders `strings.json` declares.

    A translation that drops `{capabilities}` or `{models}` renders a card
    that no longer says what failed; one that adds a placeholder the code never
    supplies renders it literally.
    """
    source = _load_text("strings.json")["issues"]
    for name in _text_files()[1:]:
        issues = _load_text(name)["issues"]
        for key in REPAIR_ISSUE_NAMES:
            for part in ("title", "description"):
                expected = set(re.findall(r"\{(\w+)\}", source[key][part]))
                rendered = issues[key][part]
                assert rendered.strip(), f"{name}: '{key}' {part} is blank"
                assert set(re.findall(r"\{(\w+)\}", rendered)) == expected, (
                    f"{name}: '{key}' {part} placeholders differ from strings.json"
                )


def test_no_orphan_issue_translations() -> None:
    """Text left behind for a key nothing raises any more."""
    for name in _text_files():
        orphans = set(_load_text(name).get("issues", {})) - set(REPAIR_ISSUE_NAMES)
        assert not orphans, f"{name}: issue text for keys nothing raises: {orphans}"


def test_the_repair_text_sweep_is_not_vacuous() -> None:
    """The text sweeps pass trivially if the key set or the file set is empty."""
    assert set(REPAIR_ISSUE_NAMES) == {
        "site_resolution_failed",
        "schema_drift_detected",
        "gateway_not_recognized",
        "gateway_identity_blocked",
    }
    assert len(_text_files()) >= 2, "expected strings.json plus a translation"


async def _fire_site_resolution_failed(hass: Any, entry: Any, mock: Any) -> None:
    from .transport import ControllerFake

    ControllerFake(mock).serve(sites=[])
    await _seam_polls(await _seam_coordinator(hass, entry), 1)


async def _fire_schema_drift_detected(hass: Any, entry: Any, mock: Any) -> None:
    from custom_components.unifi_network_monitor.const import HEALTH_DRIFT_STRIKE_LIMIT

    from .transport import DRIFTED_GATEWAY, ControllerFake

    ControllerFake(mock).serve(DRIFTED_GATEWAY)
    await _seam_polls(await _seam_coordinator(hass, entry), HEALTH_DRIFT_STRIKE_LIMIT)


async def _fire_gateway_not_recognized(hass: Any, entry: Any, mock: Any) -> None:
    from custom_components.unifi_network_monitor.const import HEALTH_DRIFT_STRIKE_LIMIT

    from .transport import ControllerFake

    ControllerFake(mock).serve(dict(_UNKNOWN))
    await _seam_polls(await _seam_coordinator(hass, entry), HEALTH_DRIFT_STRIKE_LIMIT)


async def _fire_gateway_identity_blocked(hass: Any, entry: Any, mock: Any) -> None:
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.unifi_network_monitor.identity import (
        IDENTITY_BLOCKED_MAC,
        async_apply_identity,
    )

    holder = "aa:00:00:00:00:10"
    MockConfigEntry(domain=DOMAIN, unique_id=holder).add_to_hass(hass)
    if hass.config_entries.async_get_entry(entry.entry_id) is None:
        entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, IDENTITY_BLOCKED_MAC: holder}
    )
    async_apply_identity(hass, entry)


_FIRING = {
    "site_resolution_failed": _fire_site_resolution_failed,
    "schema_drift_detected": _fire_schema_drift_detected,
    "gateway_not_recognized": _fire_gateway_not_recognized,
    "gateway_identity_blocked": _fire_gateway_identity_blocked,
}


@pytest.mark.parametrize("name", REPAIR_ISSUE_NAMES)
async def test_every_check_has_a_firing_fixture(
    hass: Any, mock_config_entry: Any, aioclient_mock: Any, name: str
) -> None:
    """Every repair has a fixture that makes the real code raise it.

    The poll-raised three are fired through the HTTP seam; the identity block
    is raised at setup, so its fixture is the conflicting entry it detects.
    """
    assert set(_FIRING) == set(REPAIR_ISSUE_NAMES)
    await _FIRING[name](hass, mock_config_entry, aioclient_mock)
    issue = _issue(hass, mock_config_entry, name)
    assert issue is not None, f"no fixture fires '{name}'"
    assert issue.translation_key == name


async def test_a_stale_repair_is_cleared_by_a_fresh_coordinator(
    hass: Any, mock_config_entry: Any, aioclient_mock: Any
) -> None:
    """The issue registry survives a reload; the strike counts do not.

    Models the reload without driving one: a fresh coordinator is what a
    reload builds: no drift strikes and no
    resolved site in memory, while the card raised before it is still in the
    registry. Its first good poll must clear the card.
    """
    from custom_components.unifi_network_monitor.const import HEALTH_DRIFT_STRIKE_LIMIT

    from .transport import DRIFTED_GATEWAY, ControllerFake

    ControllerFake(aioclient_mock).serve(DRIFTED_GATEWAY, sites=[])
    before = await _seam_coordinator(hass, mock_config_entry)
    await _seam_polls(before, HEALTH_DRIFT_STRIKE_LIMIT)
    assert _issue(hass, mock_config_entry, "schema_drift_detected") is not None
    assert _issue(hass, mock_config_entry, "site_resolution_failed") is not None

    ControllerFake(aioclient_mock).serve()
    reloaded = await _seam_coordinator(hass, mock_config_entry)
    await _seam_polls(reloaded, 1)
    assert _issue(hass, mock_config_entry, "schema_drift_detected") is None
    assert _issue(hass, mock_config_entry, "site_resolution_failed") is None
