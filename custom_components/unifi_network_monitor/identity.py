"""Automatic correction of an entry set up on a device that is not the gateway.

Detection runs once per load, on the first poll that selects a gateway, and
only writes a pending correction and schedules a reload. The correction runs
in ``async_setup_entry`` before the coordinator is constructed, because the
coordinator copies the gateway MAC, model and boot-time latch from
``entry.data`` once. Every step is idempotent: while ``previous_unique_id`` is
kept, each setup re-runs the entity, stale-card and device steps, so a stop
before the registries are saved resumes rather than orphaning anything.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.device_registry import format_mac

from ._compat import device_by_identifier, owning_entry_ids
from .const import DOMAIN, repair_issue_id
from .gateway import GatewaySelection, is_online, mac_key

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

IDENTITY_PENDING = "identity_pending"
PREVIOUS_UNIQUE_ID = "previous_unique_id"
PREVIOUS_MAC = "previous_mac"
IDENTITY_BLOCKED_MAC = "identity_blocked_mac"

BLOCKED_ISSUE = "gateway_identity_blocked"

# Virtual sub-devices under the gateway root, identified as ``<mac>_<key>``.
SUB_DEVICE_KEYS = (
    "network",
    "internet",
    "system",
    "speedtest",
    "status",
    "security",
    "alerts",
)


def mask_identity(value: str | None) -> str:
    """Return an identity safe to log: a MAC's last two octets, or ``host``."""
    key = mac_key(value)
    if len(key) == 12:
        return f"**:**:**:**:{key[8:10]}:{key[10:12]}"
    return "host" if value else "none"


def needs_correction(
    entry: ConfigEntry,
    selection: GatewaySelection,
    devices: list[dict[str, Any]],
) -> bool:
    """Return True when the stored identity should move to the selected gateway.

    All must hold: two of the three confirmation signals; the gateway online;
    the stored MAC empty or belonging to a device in the list; the stored MAC
    not the gateway's; and no blocked marker naming this gateway.
    """
    gateway = selection.device
    if gateway is None or selection.signals < 2 or not is_online(gateway):
        return False
    target = mac_key(gateway.get("mac"))
    stored = mac_key(entry.data.get("mac"))
    if not target or stored == target:
        return False
    if stored and stored not in {mac_key(d.get("mac")) for d in devices}:
        return False  # hardware replacement: the stored device is gone
    blocked = mac_key(entry.data.get(IDENTITY_BLOCKED_MAC))
    return blocked != target


def request_correction(
    hass: HomeAssistant, entry: ConfigEntry, gateway: dict[str, Any]
) -> None:
    """Write the pending correction and schedule one reload."""
    pending = {
        "mac": format_mac(str(gateway.get("mac", ""))),
        "model": gateway.get("model"),
        PREVIOUS_UNIQUE_ID: entry.unique_id,
        PREVIOUS_MAC: format_mac(str(entry.data.get("mac", ""))),
    }
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, IDENTITY_PENDING: pending}
    )
    hass.config_entries.async_schedule_reload(entry.entry_id)


def detect_on_first_poll(
    hass: HomeAssistant,
    entry: ConfigEntry,
    selection: GatewaySelection,
    devices: list[dict[str, Any]],
) -> bool:
    """Request a correction when one is needed; return True if requested."""
    if selection.device is None or not needs_correction(entry, selection, devices):
        return False
    request_correction(hass, entry, selection.device)
    return True


def stored_mac_absent(entry: ConfigEntry, devices: list[dict[str, Any]]) -> bool | None:
    """Return True when the stored MAC is set but absent from the device list.

    ``None`` when no MAC is stored. Published for the diagnostics download.
    """
    stored = mac_key(entry.data.get("mac"))
    if not stored:
        return None
    return stored not in {mac_key(d.get("mac")) for d in devices}


def async_apply_identity(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Apply a pending correction, resume a completed one, re-raise a block."""
    pending = entry.data.get(IDENTITY_PENDING)
    if isinstance(pending, dict):
        _correct(hass, entry, pending)
    elif entry.data.get(PREVIOUS_UNIQUE_ID) is not None:
        _migrate_registries(
            hass,
            entry,
            str(entry.data[PREVIOUS_UNIQUE_ID]),
            str(entry.data.get(PREVIOUS_MAC, "")),
            str(entry.unique_id),
            format_mac(str(entry.data.get("mac", ""))),
        )
    blocked = entry.data.get(IDENTITY_BLOCKED_MAC)
    if blocked:
        if _is_blocked(hass, entry, str(entry.unique_id), str(blocked)):
            _raise_blocked(hass, entry)
        else:
            # The conflict is gone, as after the duplicate entry is removed:
            # clear the block so the next selecting poll detects again.
            data = {k: v for k, v in entry.data.items() if k != IDENTITY_BLOCKED_MAC}
            hass.config_entries.async_update_entry(entry, data=data)
            ir.async_delete_issue(
                hass, DOMAIN, repair_issue_id(entry.entry_id, BLOCKED_ISSUE)
            )


def _raise_blocked(hass: HomeAssistant, entry: ConfigEntry) -> None:
    ir.async_create_issue(
        hass,
        DOMAIN,
        repair_issue_id(entry.entry_id, BLOCKED_ISSUE),
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key=BLOCKED_ISSUE,
    )


def _is_blocked(
    hass: HomeAssistant, entry: ConfigEntry, prev_uid: str, new_uid: str
) -> bool:
    """Return True when another entry or entity already holds the new identity."""
    for other in hass.config_entries.async_entries(DOMAIN):
        if other.entry_id != entry.entry_id and other.unique_id == new_uid:
            return True
    ent_reg = er.async_get(hass)
    prefix = f"{prev_uid}_"
    for row in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        if not row.unique_id.startswith(prefix):
            continue
        new_id = f"{new_uid}_{row.unique_id[len(prefix) :]}"
        holder = ent_reg.async_get_entity_id(row.domain, DOMAIN, new_id)
        if holder is not None and holder != row.entity_id:
            return True
    return False


def _correct(hass: HomeAssistant, entry: ConfigEntry, pending: dict[str, Any]) -> None:
    """Run steps (1) to (6) of the correction."""
    prev_uid = str(pending.get(PREVIOUS_UNIQUE_ID) or entry.unique_id)
    prev_mac = str(pending.get(PREVIOUS_MAC, ""))
    new_mac = format_mac(str(pending.get("mac", "")))
    data = {k: v for k, v in entry.data.items() if k != IDENTITY_PENDING}

    # (1) Duplicate check: nothing changes, the block is recorded and reported.
    if _is_blocked(hass, entry, prev_uid, new_mac):
        data[IDENTITY_BLOCKED_MAC] = new_mac
        hass.config_entries.async_update_entry(entry, data=data)
        _LOGGER.warning(
            "%s: Gateway identity correction blocked; another entry or entity "
            "holds the gateway identity %s",
            entry.title,
            mask_identity(new_mac),
        )
        return

    # (2) to (4) Entities, stale per-device card, device identifiers.
    _migrate_registries(hass, entry, prev_uid, prev_mac, new_mac, new_mac)

    # (5) Clear the gateway boot-time latch, which belongs to the old device.
    boot_times = data.get("boot_times")
    if isinstance(boot_times, dict) and "gateway" in boot_times:
        data["boot_times"] = {k: v for k, v in boot_times.items() if k != "gateway"}

    # (6) Entry identity last; the pending flag is dropped in the same write.
    data["mac"] = new_mac
    if pending.get("model"):
        data["model"] = pending["model"]
    data[PREVIOUS_UNIQUE_ID] = prev_uid
    data[PREVIOUS_MAC] = prev_mac
    data.pop(IDENTITY_BLOCKED_MAC, None)
    hass.config_entries.async_update_entry(entry, data=data, unique_id=new_mac)
    _LOGGER.warning(
        "%s: Gateway identity corrected from %s to %s; entity IDs, history and "
        "devices are kept",
        entry.title,
        mask_identity(prev_uid),
        mask_identity(new_mac),
    )


def _migrate_registries(
    hass: HomeAssistant,
    entry: ConfigEntry,
    prev_uid: str,
    prev_mac: str,
    new_uid: str,
    new_mac: str,
) -> None:
    """Rewrite entity unique IDs and device identifiers; skip what is done."""
    if not new_uid or prev_uid == new_uid:
        return
    ent_reg = er.async_get(hass)
    prefix = f"{prev_uid}_"
    for row in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        if row.unique_id.startswith(prefix):
            new_id = f"{new_uid}_{row.unique_id[len(prefix) :]}"
            if ent_reg.async_get_entity_id(row.domain, DOMAIN, new_id) is None:
                ent_reg.async_update_entity(row.entity_id, new_unique_id=new_id)

    if prev_mac == new_mac:
        return
    dev_reg = dr.async_get(hass)
    # The device steps are done once a gateway sub-device carries the new MAC;
    # those move only with the root. Re-running them then would take the
    # previous MAC for a root when a per-device card has reused it since.
    if any(
        _entry_device(dev_reg, entry, f"{new_mac}_{key}") is not None
        for key in SUB_DEVICE_KEYS
    ):
        return
    root = _entry_device(dev_reg, entry, prev_mac)
    stale = _entry_device(dev_reg, entry, new_mac)
    # (3) A per-device card already holding the gateway identifier, as when the
    # gateway was parsed as a switch, is removed while the old root remains.
    if root is not None and stale is not None and stale.id != root.id:
        dev_reg.async_remove_device(stale.id)
    # (4) Root and sub-device identifiers move to the gateway MAC.
    pairs = [(prev_mac, new_mac)] + [
        (f"{prev_mac}_{key}", f"{new_mac}_{key}") for key in SUB_DEVICE_KEYS
    ]
    for old_id, new_id in pairs:
        device = _entry_device(dev_reg, entry, old_id)
        if device is None or _entry_device(dev_reg, entry, new_id) is not None:
            continue
        identifiers = {
            ident for ident in device.identifiers if ident != (DOMAIN, old_id)
        }
        identifiers.add((DOMAIN, new_id))
        dev_reg.async_update_device(device.id, new_identifiers=identifiers)


def _entry_device(
    dev_reg: dr.DeviceRegistry, entry: ConfigEntry, identifier: str
) -> dr.DeviceEntry | None:
    """Return this entry's device carrying ``(DOMAIN, identifier)``."""
    device = device_by_identifier(dev_reg, DOMAIN, identifier, entry.entry_id)
    if device is None or entry.entry_id not in owning_entry_ids(device):
        return None
    return device
