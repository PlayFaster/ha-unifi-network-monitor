"""Removal of per-UniFi-device entities/devices Monitor no longer provides.

Cleanup is always explicit (a button press or the ``cleanup_unused_entities``
action) —
never an automatic side effect of a reconfigure — so a debug/reconfig session is
never disrupted. It only touches per-physical-device (AP/switch) entities that
the current ``unifi_device_mode`` excludes, and detaches devices that end up with
no Monitor entities (which leaves a core-owned device card intact).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from ._compat import device_by_identifier, owning_entry_ids
from .binary_sensor import DEVICE_BINARY_SENSORS
from .const import (
    CONF_UNIFI_DEVICE_MODE,
    DEFAULT_UNIFI_DEVICE_MODE,
    DEVICE_MODE_ALL,
    DOMAIN,
    EP_ROGUE,
    EP_SPEEDTEST,
    EP_VPN_TUNNELS,
    disabled_device_keys,
    dual_wan_enabled,
    single_wan_excluded_keys,
)
from .coordinator import UnifiNetworkDataUpdateCoordinator, disabled_endpoints
from .sensor import _ENDPOINT_BY_KEY, _device_descs


@dataclass
class CleanupPlan:
    """What a cleanup run would remove — usable as a dry-run report."""

    entity_ids: list[str] = field(default_factory=list)
    device_ids: list[str] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        """True when there is nothing to remove."""
        return not self.entity_ids and not self.device_ids


def _desired_device_keys(dev_type: str | None, mode: str) -> set[str]:
    """Per-device entity keys Monitor should keep for a device under ``mode``."""
    keys = {d.key for d in _device_descs(dev_type, mode)}
    if mode == DEVICE_MODE_ALL:
        keys |= {d.key for d in DEVICE_BINARY_SENSORS}
    return keys


def _feature_source(uid: str, unique_id: str) -> str | None:
    """Return the feature endpoint a gateway-level entity depends on, or None.

    Covers the sensors mapped by ``_ENDPOINT_BY_KEY`` plus the entities whose
    unique_id isn't a plain key: the proximity alert/threshold, the speedtest
    run buttons, and the dynamic VPN-tunnel binary sensors.
    """
    prefix = f"{uid}_"
    if not unique_id.startswith(prefix):
        return None
    suffix = unique_id[len(prefix) :]
    if suffix in _ENDPOINT_BY_KEY:
        return _ENDPOINT_BY_KEY[suffix]
    if suffix in (
        "rogue_proximity_alert",
        "rogue_proximity_rssi_threshold",
        "rogue_show_24ghz",
        "rogue_show_5ghz",
        "rogue_apply_ap_ignore",
        "rogue_period",
    ):
        return EP_ROGUE
    if suffix in ("wan1_speedtest", "wan2_speedtest"):
        return EP_SPEEDTEST
    if suffix.startswith("vpn_"):
        return EP_VPN_TUNNELS
    return None


@callback
def plan_device_cleanup(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: UnifiNetworkDataUpdateCoordinator,
) -> CleanupPlan:
    """Build the set of per-device entities/devices to remove for current options."""
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    uid = entry.unique_id or ""
    mode = entry.options.get(CONF_UNIFI_DEVICE_MODE, DEFAULT_UNIFI_DEVICE_MODE)
    devices = (coordinator.data or {}).get("devices", {})
    registered = er.async_entries_for_config_entry(ent_reg, entry.entry_id)

    plan = CleanupPlan()
    for mac, dev in devices.items():
        desired = _desired_device_keys(dev.get("type"), mode)
        prefix = f"{uid}_{mac}_"
        for reg_entry in registered:
            if not reg_entry.unique_id.startswith(prefix):
                continue
            if reg_entry.unique_id[len(prefix) :] not in desired:
                plan.entity_ids.append(reg_entry.entity_id)

        # If Monitor keeps nothing for this device, detach its device entry too.
        if not desired:
            device = device_by_identifier(dev_reg, DOMAIN, mac, entry.entry_id)
            if device is not None and entry.entry_id in owning_entry_ids(device):
                plan.device_ids.append(device.id)

    # Gateway-level entities whose feature toggle is currently off (orphans left
    # unavailable after unchecking a feature and reloading).
    disabled = disabled_endpoints(entry.options)
    if disabled:
        already = set(plan.entity_ids)
        for reg_entry in registered:
            if reg_entry.entity_id in already:
                continue
            if _feature_source(uid, reg_entry.unique_id) in disabled:
                plan.entity_ids.append(reg_entry.entity_id)

    # WAN2 / load-balance entities orphaned when dual-WAN monitoring is off. WAN2
    # rides shared endpoints, so it is a key-set filter — not endpoint-aligned.
    if not dual_wan_enabled(entry.options):
        excluded = single_wan_excluded_keys()
        already = set(plan.entity_ids)
        prefix = f"{uid}_"
        for reg_entry in registered:
            if reg_entry.entity_id in already:
                continue
            if not reg_entry.unique_id.startswith(prefix):
                continue
            if reg_entry.unique_id[len(prefix) :] in excluded:
                plan.entity_ids.append(reg_entry.entity_id)

    # Card-owned sub-devices whose feature toggle is off: remove EVERY entity on
    # the card (regardless of source — catches health-fed entities that the
    # endpoint branch misses) and detach the now-empty card device.
    gateway_mac = coordinator.gateway_mac
    if gateway_mac:
        already = set(plan.entity_ids)
        for card in disabled_device_keys(entry.options):
            device = device_by_identifier(
                dev_reg, DOMAIN, f"{gateway_mac}_{card}", entry.entry_id
            )
            if device is None:
                continue
            for reg_entry in registered:
                if reg_entry.entity_id in already:
                    continue
                if reg_entry.device_id == device.id:
                    plan.entity_ids.append(reg_entry.entity_id)
                    already.add(reg_entry.entity_id)
            # The card is Monitor-only; once emptied, detach it.
            if entry.entry_id in owning_entry_ids(device):
                plan.device_ids.append(device.id)

    return plan


@callback
def apply_cleanup(hass: HomeAssistant, entry: ConfigEntry, plan: CleanupPlan) -> None:
    """Remove the planned entities, then remove the planned devices.

    Monitor never shares a device with the core ``unifi`` integration (its devices
    carry only the domain identifier, no shared MAC connection), so every planned
    device is Monitor-only. Removing it outright with ``async_remove_device`` is
    therefore correct on every HA version — and avoids the deprecated
    ``async_update_device(remove_config_entry_id=...)`` path.
    """
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    for entity_id in plan.entity_ids:
        if ent_reg.async_get(entity_id) is not None:
            ent_reg.async_remove(entity_id)
    for device_id in plan.device_ids:
        if dev_reg.async_get(device_id) is not None:
            dev_reg.async_remove_device(device_id)
