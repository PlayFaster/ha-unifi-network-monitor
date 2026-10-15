"""Recorder hygiene — dev_standards Section 14.

The failure this guards is silent. When an attribute is added to an entity and
not added to ``_unrecorded_attributes``, nothing errors and nothing looks
wrong; the value is simply written to the recorder database on every state
change, forever.

Section 14 (Standard Version 1.12.0) makes the default total: every key an
entity can publish must be unrecorded, and a recorded attribute is an exception
needing a written justification. Attributes exist to carry detail about
something that does not merit its own entity — they are not a history
mechanism. A value whose history is genuinely wanted should be promoted to an
entity, or templated into one by the user.

The sweep runs against live entities rather than reading source because
description-driven entities build their attributes from a function on the
entity description, and no static check can see through that.
"""

import ast
from collections.abc import AsyncIterator
import contextlib
import json
from pathlib import Path
import re
import tokenize
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from custom_components.unifi_network_monitor.const import DOMAIN
from homeassistant.core import HomeAssistant

# Attributes deliberately left recorded, with the justification Section 14
# requires. Empty by design — adding an entry here is a visible, reviewable
# act, whereas forgetting to extend `_unrecorded_attributes` is not. That
# asymmetry is the entire point of the allow-list.
ALLOWED_RECORDED: frozenset[str] = frozenset()

# Below this, the sweep is not meaningfully exercising the integration and a
# pass would be vacuous — a fixture that stops producing attributes would let
# a real regression through silently.
MIN_ENTITIES_SWEPT = 3


async def test_no_entity_publishes_a_recorded_attribute(
    hass: HomeAssistant,
    mock_config_entry: Any,
    mock_api: MagicMock,
    mock_coordinator_data: dict[str, Any],
) -> None:
    """Section 14: `_unrecorded_attributes` must cover every published key."""
    mock_config_entry.add_to_hass(hass)

    with (
        # Force disabled-by-default entities to be added. Without this the
        # sweep silently skips them — they are never instantiated, so their
        # attributes are never inspected. Verified in `zte_router_5g` by
        # mutation: removing a key from a disabled-by-default sensor's
        # `_unrecorded_attributes` did not fail the sweep until this patch was
        # added, and adding it immediately surfaced a real offender.
        patch(
            "homeassistant.helpers.entity.Entity.entity_registry_enabled_default",
            property(lambda self: True),
        ),
        patch(
            "custom_components.unifi_network_monitor.UnifiNetworkAPI"
        ) as mock_api_cls,
    ):
        mock_api_cls.return_value = mock_api

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Give the entities real data to build attributes from; several
        # attribute functions short-circuit to `{}` on an empty payload, which
        # would make the sweep pass by finding nothing.
        coordinator = mock_config_entry.runtime_data
        coordinator.data = dict(mock_coordinator_data)
        coordinator.async_update_listeners()
        await hass.async_block_till_done()

        checked = 0
        offenders: list[str] = []
        for component in hass.data["entity_components"].values():
            for entity in component.entities:
                platform = getattr(entity, "platform", None)
                if platform is None or platform.platform_name != DOMAIN:
                    continue
                published = set(entity.extra_state_attributes or {})
                if not published:
                    continue
                checked += 1
                leaked = published - entity._unrecorded_attributes - ALLOWED_RECORDED
                if leaked:
                    offenders.append(f"{entity.entity_id}: {sorted(leaked)}")

    assert not offenders, "attributes published but recorded:\n" + "\n".join(offenders)
    assert checked >= MIN_ENTITIES_SWEPT, (
        f"sweep inspected only {checked} entities — the fixture has gone stale "
        f"and this test is passing vacuously"
    )


async def test_health_detail_is_unrecorded() -> None:
    """The health sensor's detail churns with every failure.

    Kept as a cheap static assertion alongside the sweep: this is the entity
    whose attributes change most often, and the one whose contract Section 19
    pins by name.
    """
    from custom_components.unifi_network_monitor.binary_sensor import (
        UnifiIntegrationHealthBinarySensor,
    )

    unrecorded = UnifiIntegrationHealthBinarySensor._unrecorded_attributes
    for name in ("severity", "issues", "degraded_capabilities", "drift"):
        assert name in unrecorded, f"Section 14 requires '{name}' to be unrecorded"


def test_rogue_proximity_rssi_is_unrecorded() -> None:
    """`strongest_rogue_rssi` moves on every poll.

    Regression guard for a specific miss: the gateway sensor excluded
    `rogue_aps` for exactly this reason, but the reasoning was never carried
    across to the proximity sensor, which declared no set of its own.
    """
    from custom_components.unifi_network_monitor.binary_sensor import (
        UnifiRogueProximityBinarySensor,
    )

    unrecorded = UnifiRogueProximityBinarySensor._unrecorded_attributes
    assert "strongest_rogue_rssi" in unrecorded
    assert "threshold" in unrecorded


def test_gateway_sensor_records_nothing() -> None:
    """Version/build/type were recorded because the set was never extended."""
    from custom_components.unifi_network_monitor.sensor import UnifiGatewaySensor

    unrecorded = UnifiGatewaySensor._unrecorded_attributes
    for name in ("application_version", "application_build", "device_type"):
        assert name in unrecorded, f"Section 14 requires '{name}' to be unrecorded"


# ---------------------------------------------------------------------------
# Live-entity sweeps (C-025, `every_entity_must_have_a_device.md`). Each runs
# against constructed entities on the full-integration setup above, with every
# disabled-by-default entity forced on.
# ---------------------------------------------------------------------------

COMPONENT = Path(__file__).parent.parent / "custom_components" / "unifi_network_monitor"

# Measured at 135 live entities on 2026-10-15. The floor sits just below that,
# so losing a platform's worth of entities fails the guard rather than passing
# with part of the component unswept.
MIN_LIVE_ENTITIES = 130


@contextlib.asynccontextmanager
async def _live_entities(
    hass: HomeAssistant,
    entry: Any,
    api: MagicMock,
    data: dict[str, Any],
) -> AsyncIterator[list[Any]]:
    """Set the integration up and yield every entity it registered."""
    entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.helpers.entity.Entity.entity_registry_enabled_default",
            property(lambda self: True),
        ),
        patch("custom_components.unifi_network_monitor.UnifiNetworkAPI") as api_cls,
    ):
        api_cls.return_value = api
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        coordinator = entry.runtime_data
        coordinator.data = dict(data)
        coordinator.async_update_listeners()
        await hass.async_block_till_done()
        yield [
            entity
            for component in hass.data["entity_components"].values()
            for entity in component.entities
            if getattr(getattr(entity, "platform", None), "platform_name", None)
            == DOMAIN
        ]


async def test_every_live_entity_belongs_to_a_device(
    hass: HomeAssistant,
    mock_config_entry: Any,
    mock_api: MagicMock,
    mock_coordinator_data: dict[str, Any],
) -> None:
    """No entity this integration registers may be without a device.

    Swept over live entities: `device_info` is a property on the entity class,
    so only a constructed entity can be asked where it lives.
    """
    async with _live_entities(
        hass, mock_config_entry, mock_api, mock_coordinator_data
    ) as entities:
        homeless = sorted(
            {
                type(entity).__name__
                for entity in entities
                if not (entity.device_info or {}).get("identifiers")
            }
        )
        checked = len(entities)

    assert not homeless, "entities registered with no device: " + ", ".join(homeless)
    assert checked >= MIN_LIVE_ENTITIES, (
        f"sweep inspected only {checked} entities — the fixture is stale, "
        "not the component"
    )


def test_device_info_is_declared_once() -> None:
    """Each device shape is built in one place, `helpers.py`.

    This project has two genuine shapes, the entry sub-devices and the
    monitored network devices keyed by MAC, so the rule here is that each is
    declared once (`every_entity_must_have_a_device.md`, UniFi row): every
    `device_info` property returns `build_sub_device_info` or
    `build_unifi_device_info`, and no module but `helpers.py` constructs a
    `DeviceInfo`.
    """
    builders = {"build_sub_device_info", "build_unifi_device_info"}
    offenders: list[str] = []
    declared = 0
    for path in sorted(COMPONENT.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                path.name != "helpers.py"
                and isinstance(node, ast.Call)
                and getattr(node.func, "id", None) == "DeviceInfo"
            ):
                offenders.append(f"{path.name}:{node.lineno} constructs DeviceInfo")
            if not (isinstance(node, ast.FunctionDef) and node.name == "device_info"):
                continue
            declared += 1
            returns = [n for n in ast.walk(node) if isinstance(n, ast.Return)]
            if not returns or not all(
                isinstance(r.value, ast.Call)
                and getattr(r.value.func, "id", None) in builders
                for r in returns
            ):
                offenders.append(f"{path.name}:{node.lineno} builds its own device")

    assert not offenders, "\n".join(offenders)
    assert declared >= 19, f"only {declared} device_info properties found"


async def test_every_live_entity_has_an_icon_or_a_device_class(
    hass: HomeAssistant,
    mock_config_entry: Any,
    mock_api: MagicMock,
    mock_coordinator_data: dict[str, Any],
) -> None:
    """`icons.json` must cover every live entity without a device class.

    Looked up under the entity's own platform, so a key filed under another
    platform is a miss, not a pass.
    """
    icons = json.loads((COMPONENT / "icons.json").read_text(encoding="utf-8"))
    entity_icons = icons["entity"]
    async with _live_entities(
        hass, mock_config_entry, mock_api, mock_coordinator_data
    ) as entities:
        missing: list[str] = []
        checked = 0
        for entity in entities:
            if entity.device_class is not None:
                continue
            checked += 1
            key = entity.translation_key
            domain = entity.platform.domain
            if key is None or key not in entity_icons.get(domain, {}):
                missing.append(f"{entity.entity_id} ({domain}/{key})")

    assert not missing, "entities with neither device_class nor icon:\n" + "\n".join(
        missing
    )
    assert checked >= 10, f"only {checked} entities swept — the fixture is stale"


def test_action_icons_use_the_current_nested_form() -> None:
    """Every action icon is `{"service": "mdi:..."}`, Home Assistant's current form."""
    icons = json.loads((COMPONENT / "icons.json").read_text(encoding="utf-8"))
    services = icons.get("services", {})
    assert services, "no services block at all"
    flat = sorted(
        name for name, value in services.items() if not isinstance(value, dict)
    )
    assert not flat, "action icons in the legacy flat form: " + ", ".join(flat)
    for name, value in services.items():
        assert value.get("service", "").startswith("mdi:"), (
            f"{name} has no `service` icon"
        )


# ---------------------------------------------------------------------------
# Suppressions (C-004, `masked_errors_check` Class D). A `noqa`, `type: ignore`
# or `pragma: no cover` hides what a tool would have said, so each one needs a
# written reason here. Keyed on (file, directive) rather than line number, so
# ordinary edits do not churn it. `RUF100` and mypy's `warn_unused_ignores`
# report an unnecessary suppression; neither reports one that is doing work.
# ---------------------------------------------------------------------------

ALLOWED_SUPPRESSIONS: dict[tuple[str, str], str] = {
    ("coordinator.py", "noqa: BLE001"): (
        "Two sites. The per-endpoint fetch tolerates any exception so one "
        "endpoint's payload drift degrades that endpoint alone, recorded in "
        "diagnostics and Integration Health; the v3 site lookup must not fail "
        "the poll, and its classifier below decides what a failure means."
    ),
    ("coordinator.py", "noqa: C901"): (
        "_async_update_data is the one poll entry point and its McCabe score "
        "is recorded as a known finding (v1.1.1 plan D28); splitting it is "
        "deferred work, not hidden work."
    ),
    ("diagnostics.py", "noqa: BLE001"): (
        "Home Assistant does not wrap config_entry_diagnostics, so a section "
        "that raises would turn the download into an HTTP 500; each section "
        "reports its exception type instead."
    ),
    ("diagnostics.py", "noqa: S104"): (
        "0.0.0.0 is a value the address scrubber compares against and keeps, "
        "never an address anything binds to."
    ),
    ("uptime.py", "noqa: BLE001"): (
        "No storage fault may fail entry setup: the uptime store is a "
        "cross-check, and the latch re-anchors from the next reading when the "
        "load fails, as the comment at the site records."
    ),
    ("test_alerts.py", "type: ignore[arg-type]"): (
        "The two tests pass None where the signature says str or dict, "
        "deliberately, to prove format_message tolerates a payload that "
        "breaks its own annotation."
    ),
    ("test_api_lock_concurrency.py", "type: ignore[method-assign]"): (
        "Replaces _login_unlocked with a counting fake so the test can observe "
        "how many logins run at once behind the real login lock."
    ),
    ("test_diagnostics_artefact.py", "type: ignore[assignment]"): (
        "Swaps a section builder for one that raises, and restores it in "
        "finally, to prove the download survives a failing section."
    ),
    ("test_number_flush.py", "type: ignore[method-assign]"): (
        "Assigns a capturing or stub async_write_ha_state on an entity built "
        "outside a platform, where Home Assistant has no state machine to "
        "write to."
    ),
    ("test_platform_branches.py", "type: ignore[assignment]"): (
        "Swaps the service module's entry resolver and option writer for "
        "recording stand-ins, restored in finally, to drive one handler "
        "branch without a loaded entry."
    ),
    ("test_wan_weights.py", "type: ignore[method-assign]"): (
        "Replaces async_force_refresh with an AsyncMock so the write path is "
        "observed without starting a real refresh cycle."
    ),
}

_SUPPRESSION = re.compile(
    r"#\s*((?:ruff:\s*)?(?:type:\s*ignore(?:\[[^\]]*\])?"
    r"|noqa(?::\s*[A-Z0-9, ]+)?|pragma:\s*no cover))"
)


def _live_suppressions() -> dict[tuple[str, str], list[int]]:
    """Map (file, directive) to the lines carrying it, in the component and tests.

    Uses `tokenize`, so a docstring quoting a directive does not count, and
    resolves from this file rather than the imported package, so a `mutants/`
    copy is never swept.
    """
    live: dict[tuple[str, str], list[int]] = {}
    for root in (COMPONENT, Path(__file__).parent):
        for path in sorted(root.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            with path.open("rb") as handle:
                for token in tokenize.tokenize(handle.readline):
                    if token.type != tokenize.COMMENT:
                        continue
                    for raw in _SUPPRESSION.findall(token.string):
                        key = (path.name, " ".join(raw.split()))
                        live.setdefault(key, []).append(token.start[0])
    return live


def test_every_suppression_is_on_the_reviewed_allow_list() -> None:
    """No `type: ignore`, `noqa` or `pragma: no cover` without a written reason."""
    unlisted = sorted(
        f"{filename}:{','.join(str(n) for n in lines)}  {code}"
        for (filename, code), lines in _live_suppressions().items()
        if (filename, code) not in ALLOWED_SUPPRESSIONS
    )
    assert not unlisted, (
        "suppressions with no reviewed justification:\n"
        + "\n".join(unlisted)
        + "\n\nAdd to ALLOWED_SUPPRESSIONS with a reason, or fix the cause."
    )


def test_allowed_suppressions_has_no_dead_entries() -> None:
    """An entry must not outlive the suppression it covers."""
    live = set(_live_suppressions())
    stale = sorted(f"{f}  {c}" for (f, c) in ALLOWED_SUPPRESSIONS if (f, c) not in live)
    assert not stale, "entries that match nothing:\n" + "\n".join(stale)


def test_every_allowed_suppression_states_a_reason() -> None:
    """An entry with a token justification is one added to make a check pass."""
    thin = sorted(
        f"{f}  {c}"
        for (f, c), reason in ALLOWED_SUPPRESSIONS.items()
        if len(reason.strip()) < 40
    )
    assert not thin, "entries with no real justification:\n" + "\n".join(thin)


# ---------------------------------------------------------------------------
# Device registry — deprecated surfaces only through `_compat` (C-038), ported
# from `zte_router_5g`, the C-038 reference.
# ---------------------------------------------------------------------------


def _hass_owned(node: ast.expr) -> bool:
    """`hass` or `<x>.hass`, whose `config_entries` is the manager, not a device's."""
    return (isinstance(node, ast.Name) and node.id == "hass") or (
        isinstance(node, ast.Attribute) and node.attr == "hass"
    )


def _deprecated_registry_uses(tree: ast.AST) -> list[tuple[int, str]]:
    """Return `(line, surface)` for each deprecated device-registry use in `tree`.

    Three surfaces, all deprecated in HA 2026.8: `async_get_device(...)`,
    `DeviceEntry.config_entries` and the `via_device` identifier tuple. Read
    from the syntax tree, so a comment naming a surface does not count, and
    `hass.config_entries`, the config-entry manager, is not a device attribute.
    """
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "async_get_device"
        ):
            found.append((node.lineno, "async_get_device()"))
        elif (
            isinstance(node, ast.Attribute)
            and node.attr == "config_entries"
            and not _hass_owned(node.value)
        ):
            found.append((node.lineno, "DeviceEntry.config_entries"))
        elif isinstance(node, ast.keyword) and node.arg == "via_device":
            found.append((node.lineno, "via_device="))
        elif isinstance(node, ast.Dict):
            found.extend(
                (key.lineno, "'via_device' key")
                for key in node.keys
                if isinstance(key, ast.Constant) and key.value == "via_device"
            )
    return found


def test_deprecated_device_registry_surfaces_only_in_compat() -> None:
    """Deprecated device-registry surfaces are reached only through `_compat`.

    A direct call elsewhere works on today's Home Assistant and breaks on
    removal, which is how 1.1.0-dev12 shipped one in `identity.py`.
    """
    offenders = [
        f"{path.name}:{line}  {surface}"
        for path in sorted(COMPONENT.rglob("*.py"))
        if path.name != "_compat.py"
        for line, surface in _deprecated_registry_uses(
            ast.parse(path.read_text(encoding="utf-8"))
        )
    ]
    assert not offenders, (
        "deprecated device-registry surfaces outside _compat.py:\n"
        + "\n".join(offenders)
        + "\nRoute the lookup through a `_compat` shim."
    )


@pytest.mark.parametrize(
    ("source", "surface"),
    [
        ("dev_reg.async_get_device(identifiers={('d', 'x')})", "async_get_device()"),
        ("ids = device.config_entries", "DeviceEntry.config_entries"),
        ("DeviceInfo(via_device=('d', 'x'))", "via_device="),
        ("info = {'via_device': ('d', 'x')}", "'via_device' key"),
    ],
)
def test_registry_guard_detects_each_surface(source: str, surface: str) -> None:
    """The guard above reports each surface it names."""
    assert [s for _, s in _deprecated_registry_uses(ast.parse(source))] == [surface]


@pytest.mark.parametrize(
    "source",
    [
        "entry = hass.config_entries.async_get_entry(entry_id)",
        "self.hass.config_entries.async_update_entry(entry)",
        "# async_get_device(identifiers=...) is deprecated",
        "link = via_device_link(hass, 'd', 'x', entry_id)",
    ],
)
def test_registry_guard_ignores_manager_and_comments(source: str) -> None:
    """The config-entry manager, comments and the shims do not count."""
    assert _deprecated_registry_uses(ast.parse(source)) == []
