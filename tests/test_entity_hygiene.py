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

from typing import Any
from unittest.mock import MagicMock, patch

from homeassistant.core import HomeAssistant

from custom_components.unifi_network_monitor.const import DOMAIN

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
