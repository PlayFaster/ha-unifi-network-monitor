"""Automatic gateway identity correction (v1.1.0-dev12 I5).

Issue #23: an entry set up when no listed model matched stored a switch's MAC
as its identity. On the first poll that selects a gateway confirmed by two of
three signals, the entry is moved to the gateway's identity: every entity
``unique_id`` and the eight gateway-tree device identifiers are rewritten,
while entity IDs, history and device IDs are kept.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager, suppress
import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.unifi_network_monitor.const import (
    CONF_UNIFI_DEVICE_MODE,
    DEVICE_MODE_ALL,
    DEVICE_MODE_NONE,
    DOMAIN,
    repair_issue_id,
)
from custom_components.unifi_network_monitor.gateway import select_gateway
from custom_components.unifi_network_monitor.identity import (
    IDENTITY_BLOCKED_MAC,
    IDENTITY_PENDING,
    PREVIOUS_UNIQUE_ID,
    SUB_DEVICE_KEYS,
    async_apply_identity,
    needs_correction,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from tests.conftest import MOCK_ENTRY_OPTIONS
from tests.test_coordinator_branches import _api

SWITCH_MAC = "aa:00:00:00:00:01"
GATEWAY_MAC = "aa:00:00:00:00:10"
HOST = MOCK_ENTRY_OPTIONS["host"]

_WAN = {"ifname": "eth4", "up": True, "is_uplink": True}


def _switch(**extra: Any) -> dict[str, Any]:
    return {
        "mac": SWITCH_MAC,
        "name": "Switch Ultra",
        "model": "USM8P210",
        "type": "usw",
        "state": 1,
        **extra,
    }


def _gateway(**extra: Any) -> dict[str, Any]:
    return {
        "mac": GATEWAY_MAC,
        "name": "Gateway",
        "model": "UDRULT",
        "type": "udm",
        "state": 1,
        "wan1": dict(_WAN),
        **extra,
    }


def _entry(
    mac: str = SWITCH_MAC,
    unique_id: str | None = SWITCH_MAC,
    mode: str = DEVICE_MODE_NONE,
    **data: Any,
) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="UniFi Network",
        unique_id=unique_id,
        data={"mac": mac, "model": "USM8P210", "sw_version": "1", **data},
        options={**MOCK_ENTRY_OPTIONS, CONF_UNIFI_DEVICE_MODE: mode},
    )


@contextmanager
def _controller(devices: list[dict[str, Any]]) -> Iterator[MagicMock]:
    api = _api(get_devices=AsyncMock(return_value=devices))
    api.logout = AsyncMock()
    with patch(
        "custom_components.unifi_network_monitor.UnifiNetworkAPI", return_value=api
    ):
        yield api


async def _load(hass: Any, entry: MockConfigEntry) -> None:
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    await hass.async_block_till_done(wait_background_tasks=True)


def _entities(hass: Any, entry: MockConfigEntry) -> dict[str, Any]:
    reg = er.async_get(hass)
    return {
        row.entity_id: row
        for row in er.async_entries_for_config_entry(reg, entry.entry_id)
    }


def _device_ids(hass: Any, entry: MockConfigEntry) -> dict[str, str]:
    """Map each domain identifier of this entry's devices to its device ID."""
    reg = dr.async_get(hass)
    out: dict[str, str] = {}
    for device in dr.async_entries_for_config_entry(reg, entry.entry_id):
        for domain, ident in device.identifiers:
            if domain == DOMAIN:
                out[ident] = device.id
    return out


def _tree(mac: str) -> set[str]:
    return {mac} | {f"{mac}_{key}" for key in SUB_DEVICE_KEYS}


async def _seed(hass: Any, entry: MockConfigEntry, devices: list[Any]) -> None:
    """Load the entry once with detection disabled, as a dev11 install."""
    with (
        _controller(devices),
        patch(
            "custom_components.unifi_network_monitor.identity.detect_on_first_poll",
            return_value=False,
        ),
    ):
        await _load(hass, entry)
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


# --- end-to-end ----------------------------------------------------------------


async def test_switch_mac_in_default_mode_is_corrected_keeping_ids(
    hass: Any, caplog: Any
) -> None:
    """The issue #23 install moves to the gateway identity on first start."""
    entry = _entry()
    entry.add_to_hass(hass)
    devices = [_switch(), _gateway()]
    await _seed(hass, entry, devices)
    before = _entities(hass, entry)
    before_devices = _device_ids(hass, entry)
    assert before
    assert all(r.unique_id.startswith(f"{SWITCH_MAC}_") for r in before.values())
    seeded = _tree(SWITCH_MAC) & set(before_devices)
    assert SWITCH_MAC in seeded and len(seeded) >= 5

    caplog.set_level(logging.WARNING)
    with _controller(devices):
        await _load(hass, entry)

    assert entry.state is ConfigEntryState.LOADED
    assert entry.unique_id == GATEWAY_MAC
    assert entry.data["mac"] == GATEWAY_MAC
    assert entry.data["model"] == "UDRULT"
    assert entry.data[PREVIOUS_UNIQUE_ID] == SWITCH_MAC
    assert IDENTITY_PENDING not in entry.data

    after = _entities(hass, entry)
    assert set(after) == set(before)
    for entity_id, row in after.items():
        assert row.unique_id.startswith(f"{GATEWAY_MAC}_")
        assert row.device_id == before[entity_id].device_id

    after_devices = _device_ids(hass, entry)
    for old in seeded:
        new = GATEWAY_MAC + old[len(SWITCH_MAC) :]
        assert after_devices[new] == before_devices[old]
    assert not _tree(SWITCH_MAC) & set(after_devices)
    corrected = [r for r in caplog.records if "identity corrected" in r.getMessage()]
    assert len(corrected) == 1
    assert SWITCH_MAC not in corrected[0].getMessage()

    # A further restart (upgrade sequence, second start) changes nothing.
    await hass.config_entries.async_unload(entry.entry_id)
    with _controller(devices):
        await _load(hass, entry)
    assert {k: r.unique_id for k, r in _entities(hass, entry).items()} == {
        k: r.unique_id for k, r in after.items()
    }
    assert _device_ids(hass, entry) == after_devices


async def test_reload_is_scheduled_once_and_after_the_first_refresh(
    hass: Any,
) -> None:
    """Detection schedules one reload, from a completed first refresh."""
    entry = _entry()
    entry.add_to_hass(hass)
    devices = [_switch(), _gateway()]
    await _seed(hass, entry, devices)

    calls: list[str] = []
    real = hass.config_entries.async_schedule_reload

    def _spy(entry_id: str) -> None:
        coordinator = hass.config_entries.async_get_entry(entry_id).runtime_data
        calls.append(str(coordinator.gateway_selection.reason))
        real(entry_id)

    with (
        _controller(devices),
        patch.object(hass.config_entries, "async_schedule_reload", _spy),
    ):
        await _load(hass, entry)

    assert calls == ["wan_signature"]
    assert entry.state is ConfigEntryState.LOADED
    assert entry.unique_id == GATEWAY_MAC


async def test_opt_in_mode_removes_the_stale_gateway_as_switch_card(
    hass: Any,
) -> None:
    """A per-device card already holding the gateway MAC is removed."""
    entry = _entry(mode=DEVICE_MODE_ALL)
    entry.add_to_hass(hass)
    devices = [_switch(), _gateway()]
    await _seed(hass, entry, devices)
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    stale = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, GATEWAY_MAC)},
        name="Gateway parsed as a switch",
    )
    stale_entity = ent_reg.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{SWITCH_MAC}_{GATEWAY_MAC}_stale",
        config_entry=entry,
        device_id=stale.id,
    )
    root_id = _device_ids(hass, entry)[SWITCH_MAC]

    with _controller(devices):
        await _load(hass, entry)

    ids = _device_ids(hass, entry)
    assert dev_reg.async_get(stale.id) is None
    assert ent_reg.async_get(stale_entity.entity_id) is None
    assert ids[GATEWAY_MAC] == root_id
    # The switch is back on a card of its own, not the gateway root.
    assert SWITCH_MAC in ids
    assert ids[SWITCH_MAC] != root_id


async def test_another_entry_holding_the_gateway_blocks_and_reports(
    hass: Any,
) -> None:
    """A duplicate changes nothing, stores the block and raises the repair."""
    other = _entry(mac=GATEWAY_MAC, unique_id=GATEWAY_MAC)
    other.add_to_hass(hass)
    entry = _entry()
    entry.add_to_hass(hass)
    devices = [_switch(), _gateway()]
    await _seed(hass, entry, devices)
    before = {k: r.unique_id for k, r in _entities(hass, entry).items()}

    calls: list[str] = []
    real = hass.config_entries.async_schedule_reload

    def _spy(entry_id: str) -> None:
        calls.append(entry_id)
        real(entry_id)

    with (
        _controller(devices),
        patch.object(hass.config_entries, "async_schedule_reload", _spy),
    ):
        await _load(hass, entry)
        # A further reload: no second correction, and the repair survives.
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert calls == [entry.entry_id]
    assert entry.unique_id == SWITCH_MAC
    assert entry.data[IDENTITY_BLOCKED_MAC] == GATEWAY_MAC
    assert IDENTITY_PENDING not in entry.data
    assert {k: r.unique_id for k, r in _entities(hass, entry).items()} == before
    issue_id = repair_issue_id(entry.entry_id, "gateway_identity_blocked")
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is not None


async def test_interrupted_correction_completes_on_the_next_setup(
    hass: Any,
) -> None:
    """The entry saved corrected, the registries not: setup completes it."""
    entry = _entry()
    entry.add_to_hass(hass)
    devices = [_switch(), _gateway()]
    await _seed(hass, entry, devices)
    before = _entities(hass, entry)
    before_devices = _device_ids(hass, entry)
    device_count = len(before_devices)

    # The state a stop inside the 10 s registry save window leaves behind.
    hass.config_entries.async_update_entry(
        entry,
        unique_id=GATEWAY_MAC,
        data={
            **entry.data,
            "mac": GATEWAY_MAC,
            "model": "UDRULT",
            PREVIOUS_UNIQUE_ID: SWITCH_MAC,
            "previous_mac": SWITCH_MAC,
        },
    )

    with _controller(devices):
        await _load(hass, entry)

    after = _entities(hass, entry)
    assert set(after) == set(before)
    for entity_id, row in after.items():
        assert row.unique_id.startswith(f"{GATEWAY_MAC}_")
        assert row.device_id == before[entity_id].device_id
    after_devices = _device_ids(hass, entry)
    assert len(after_devices) == device_count
    for old, device_id in before_devices.items():
        assert after_devices[GATEWAY_MAC + old[len(SWITCH_MAC) :]] == device_id


async def test_empty_mac_with_host_unique_id_is_corrected(hass: Any) -> None:
    """An entry set up with no gateway moves from the host to the gateway."""
    entry = _entry(mac="", unique_id=HOST)
    entry.add_to_hass(hass)
    devices = [_switch(), _gateway()]
    await _seed(hass, entry, devices)
    before = _entities(hass, entry)
    before_devices = _device_ids(hass, entry)
    assert "" in before_devices
    assert all(r.unique_id.startswith(f"{HOST}_") for r in before.values())

    with _controller(devices):
        await _load(hass, entry)

    assert entry.unique_id == GATEWAY_MAC
    after = _entities(hass, entry)
    assert set(after) == set(before)
    assert all(r.unique_id.startswith(f"{GATEWAY_MAC}_") for r in after.values())
    after_devices = _device_ids(hass, entry)
    assert after_devices[GATEWAY_MAC] == before_devices[""]
    assert "" not in after_devices


async def test_correct_stored_mac_is_untouched(hass: Any) -> None:
    """An entry already on its gateway changes nothing across restarts."""
    entry = _entry(mac=GATEWAY_MAC, unique_id=GATEWAY_MAC)
    entry.add_to_hass(hass)
    devices = [_switch(), _gateway()]
    await _seed(hass, entry, devices)
    before = {k: r.unique_id for k, r in _entities(hass, entry).items()}
    data = dict(entry.data)

    with _controller(devices):
        await _load(hass, entry)

    assert dict(entry.data) == data
    assert {k: r.unique_id for k, r in _entities(hass, entry).items()} == before


async def test_controller_offline_at_start_keeps_the_check_armed(
    hass: Any,
) -> None:
    """No poll selects a gateway, so the one-time check stays armed."""
    from custom_components.unifi_network_monitor.api import UnifiConnectionError
    from custom_components.unifi_network_monitor.coordinator import (
        UnifiNetworkDataUpdateCoordinator,
    )
    from homeassistant.exceptions import ConfigEntryNotReady
    from homeassistant.helpers.update_coordinator import UpdateFailed

    entry = _entry()
    entry.add_to_hass(hass)
    api = _api(get_devices=AsyncMock(side_effect=UnifiConnectionError("down")))
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, entry, api)

    with suppress(UpdateFailed, ConfigEntryNotReady):
        await coordinator._async_update_data()

    assert coordinator._identity_check_armed is True
    assert IDENTITY_PENDING not in entry.data


# --- detection rules -----------------------------------------------------------


def _needs(entry: MockConfigEntry, devices: list[dict[str, Any]]) -> bool:
    return needs_correction(entry, select_gateway(devices, entry.data["mac"]), devices)


def test_rule_wan_object_alone_is_not_enough() -> None:
    """A WAN object with no gateway type and an unlisted model: one signal."""
    gw = _gateway(model="UNLISTED9", type="uxx")
    assert not _needs(_entry(), [_switch(), gw])


def test_rule_unlisted_model_with_wan_and_type_udm_is_corrected() -> None:
    """WAN object and gateway type: two signals."""
    assert _needs(_entry(), [_switch(), _gateway(model="UNLISTED9")])


def test_rule_wan_unknown_type_and_listed_model_is_corrected() -> None:
    """WAN object and listed model: two signals."""
    assert _needs(_entry(), [_switch(), _gateway(type="uxx")])


def test_rule_no_wan_type_udm_and_listed_model_is_corrected() -> None:
    """Gateway type and listed model, no WAN object: two signals."""
    gw = _gateway()
    del gw["wan1"]
    assert _needs(_entry(), [_switch(), gw])


def test_rule_type_alone_is_not_enough() -> None:
    """A gateway type with no WAN object and an unlisted model: one signal."""
    gw = _gateway(model="UNLISTED9")
    del gw["wan1"]
    assert not _needs(_entry(), [_switch(), gw])


def test_rule_offline_gateway_is_not_corrected() -> None:
    """The selected device must be online."""
    assert not _needs(_entry(), [_switch(), _gateway(state=0)])


def test_rule_ambiguous_or_none_changes_nothing() -> None:
    """No single gateway: nothing to correct to."""
    twin = _gateway(mac="aa:00:00:00:00:11")
    assert not _needs(_entry(), [_switch(), _gateway(), twin])
    assert not _needs(_entry(), [_switch()])


def test_rule_stored_mac_absent_changes_nothing() -> None:
    """A hardware replacement: the stored device is gone; nothing changes."""
    from custom_components.unifi_network_monitor.identity import stored_mac_absent

    entry = _entry(mac="aa:00:00:00:00:99")
    devices = [_switch(), _gateway()]
    assert not _needs(entry, devices)
    assert stored_mac_absent(entry, devices) is True
    assert stored_mac_absent(_entry(), devices) is False
    assert stored_mac_absent(_entry(mac=""), devices) is None


def test_rule_blocked_marker_for_this_gateway_changes_nothing() -> None:
    """A recorded block for this gateway suppresses detection."""
    entry = _entry(**{IDENTITY_BLOCKED_MAC: GATEWAY_MAC})
    assert not _needs(entry, [_switch(), _gateway()])


async def test_apply_without_pending_or_previous_does_nothing(hass: Any) -> None:
    """Setup on an ordinary entry touches no registry."""
    entry = _entry(mac=GATEWAY_MAC, unique_id=GATEWAY_MAC)
    entry.add_to_hass(hass)
    async_apply_identity(hass, entry)
    assert entry.unique_id == GATEWAY_MAC
    assert PREVIOUS_UNIQUE_ID not in entry.data


async def test_removing_the_duplicate_clears_the_block_and_corrects(
    hass: Any,
) -> None:
    """Once the duplicate entry is gone, a reload clears the block and corrects."""
    other = _entry(mac=GATEWAY_MAC, unique_id=GATEWAY_MAC)
    other.add_to_hass(hass)
    entry = _entry()
    entry.add_to_hass(hass)
    devices = [_switch(), _gateway()]
    await _seed(hass, entry, devices)

    with _controller(devices):
        await _load(hass, entry)
        assert entry.data[IDENTITY_BLOCKED_MAC] == GATEWAY_MAC
        await hass.config_entries.async_remove(other.entry_id)
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert IDENTITY_BLOCKED_MAC not in entry.data
    assert entry.unique_id == GATEWAY_MAC
    issue_id = repair_issue_id(entry.entry_id, "gateway_identity_blocked")
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None


# --- step-level branches -------------------------------------------------------


async def test_correction_clears_the_gateway_latch_and_keeps_model_when_unknown(
    hass: Any,
) -> None:
    """Step (5) drops only the gateway latch; no target model keeps the old one."""
    entry = _entry(
        boot_times={"gateway": {"boot_time": "x"}, "wan1": {"boot_time": "y"}},
        **{
            IDENTITY_PENDING: {
                "mac": GATEWAY_MAC,
                "model": None,
                PREVIOUS_UNIQUE_ID: SWITCH_MAC,
                "previous_mac": SWITCH_MAC,
            }
        },
    )
    entry.add_to_hass(hass)

    async_apply_identity(hass, entry)

    assert entry.unique_id == GATEWAY_MAC
    assert entry.data["boot_times"] == {"wan1": {"boot_time": "y"}}
    assert entry.data["model"] == "USM8P210"


async def test_an_entity_holding_a_new_unique_id_blocks_the_correction(
    hass: Any,
) -> None:
    """Step (1): a foreign entity already on a new unique_id blocks."""
    entry = _entry(
        **{
            IDENTITY_PENDING: {
                "mac": GATEWAY_MAC,
                "model": "UDRULT",
                PREVIOUS_UNIQUE_ID: SWITCH_MAC,
                "previous_mac": SWITCH_MAC,
            }
        }
    )
    entry.add_to_hass(hass)
    other = _entry(mac="aa:00:00:00:00:77", unique_id="aa:00:00:00:00:77")
    other.add_to_hass(hass)
    ent_reg = er.async_get(hass)
    ent_reg.async_get_or_create("sensor", DOMAIN, "unrelated", config_entry=entry)
    ent_reg.async_get_or_create(
        "sensor", DOMAIN, f"{SWITCH_MAC}_cpu", config_entry=entry
    )
    ent_reg.async_get_or_create(
        "sensor", DOMAIN, f"{GATEWAY_MAC}_cpu", config_entry=other
    )

    async_apply_identity(hass, entry)

    assert entry.unique_id == SWITCH_MAC
    assert entry.data[IDENTITY_BLOCKED_MAC] == GATEWAY_MAC


async def test_resume_skips_a_row_whose_new_unique_id_is_taken(hass: Any) -> None:
    """Resume leaves a row alone when its new unique_id already exists."""
    entry = _entry(
        mac=GATEWAY_MAC,
        unique_id=GATEWAY_MAC,
        **{PREVIOUS_UNIQUE_ID: SWITCH_MAC, "previous_mac": SWITCH_MAC},
    )
    entry.add_to_hass(hass)
    ent_reg = er.async_get(hass)
    old = ent_reg.async_get_or_create(
        "sensor", DOMAIN, f"{SWITCH_MAC}_cpu", config_entry=entry
    )
    ent_reg.async_get_or_create(
        "sensor", DOMAIN, f"{GATEWAY_MAC}_cpu", config_entry=entry
    )

    async_apply_identity(hass, entry)

    assert ent_reg.async_get(old.entity_id).unique_id == f"{SWITCH_MAC}_cpu"


async def test_resume_with_the_same_identity_or_mac_is_a_no_op(hass: Any) -> None:
    """Resume returns early when nothing differs, and skips unchanged-MAC devices."""
    same = _entry(
        mac=GATEWAY_MAC,
        unique_id=GATEWAY_MAC,
        **{PREVIOUS_UNIQUE_ID: GATEWAY_MAC, "previous_mac": GATEWAY_MAC},
    )
    same.add_to_hass(hass)
    async_apply_identity(hass, same)
    assert same.unique_id == GATEWAY_MAC

    host = _entry(
        mac=GATEWAY_MAC,
        unique_id=GATEWAY_MAC,
        **{PREVIOUS_UNIQUE_ID: HOST, "previous_mac": GATEWAY_MAC},
    )
    host.add_to_hass(hass)
    ent_reg = er.async_get(hass)
    row = ent_reg.async_get_or_create(
        "sensor", DOMAIN, f"{HOST}_cpu", config_entry=host
    )
    async_apply_identity(hass, host)
    assert ent_reg.async_get(row.entity_id).unique_id == f"{GATEWAY_MAC}_cpu"


async def test_correction_moves_only_this_entrys_device_when_identifiers_are_shared(
    hass: Any,
) -> None:
    """Two no-gateway entries share ``(DOMAIN, "")``; only this entry's moves.

    The lookup is scoped to the entry (``_compat.device_by_identifier``), so the
    other entry's device with the same identifier is neither chosen nor moved.
    """
    other = _entry(mac="", unique_id="192.168.9.9")
    other.add_to_hass(hass)
    entry = _entry(
        mac="",
        unique_id=HOST,
        **{
            IDENTITY_PENDING: {
                "mac": GATEWAY_MAC,
                "model": "UDRULT",
                PREVIOUS_UNIQUE_ID: HOST,
                "previous_mac": "",
            }
        },
    )
    entry.add_to_hass(hass)
    dev_reg = dr.async_get(hass)
    other_root = dev_reg.async_get_or_create(
        config_entry_id=other.entry_id, identifiers={(DOMAIN, "")}, name="Other"
    )
    own_root = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, "")}, name="Own"
    )

    async_apply_identity(hass, entry)

    assert dev_reg.async_get(own_root.id).identifiers == {(DOMAIN, GATEWAY_MAC)}
    assert dev_reg.async_get(other_root.id).identifiers == {(DOMAIN, "")}


async def test_opt_in_correction_survives_later_restarts(hass: Any) -> None:
    """After an opt-in correction the switch card reuses the previous MAC.

    Later setups resume while ``previous_unique_id`` is kept. The gateway root
    and its entities must survive, and the switch card must keep its own
    identifier rather than being moved onto the gateway's.
    """
    entry = _entry(mode=DEVICE_MODE_ALL)
    entry.add_to_hass(hass)
    devices = [_switch(), _gateway()]
    await _seed(hass, entry, devices)
    with _controller(devices):
        await _load(hass, entry)
    root_id = _device_ids(hass, entry)[GATEWAY_MAC]
    switch_id = _device_ids(hass, entry)[SWITCH_MAC]
    entities = {k: r.device_id for k, r in _entities(hass, entry).items()}

    with _controller(devices):
        for _ in range(2):
            await hass.config_entries.async_reload(entry.entry_id)
            await hass.async_block_till_done(wait_background_tasks=True)

    ids = _device_ids(hass, entry)
    assert ids[GATEWAY_MAC] == root_id
    assert ids[SWITCH_MAC] == switch_id
    assert {k: r.device_id for k, r in _entities(hass, entry).items()} == entities
