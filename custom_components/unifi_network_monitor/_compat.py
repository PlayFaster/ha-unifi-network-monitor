"""Device-registry compatibility across Home Assistant versions.

HA 2026.8 makes a device belong to a single config entry and deprecates several
registry surfaces (removed in 2027.8): the ambiguous ``async_get_device``,
``DeviceEntry.config_entries``, and the ``DeviceInfo.via_device`` identifier
tuple. UniFi Network Monitor stays **floor-free** — one behaviour on <=2026.7 and
on post-2027.8 alike — by feature-detecting each surface and using the new API
where present, the old one otherwise.

Detection probes the HA **classes** (not instances), so it reflects the actually
installed HA and is not fooled by a ``MagicMock`` registry in tests. The two
booleans are module globals so tests can patch them to exercise either path
regardless of the HA version the suite runs against.

See ``.notes/device_registry/device_model_2026_08.md`` for the full rationale.
"""

from __future__ import annotations

from typing import Any, cast

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

# Both surfaces land together in 2026.8; probe each independently all the same.
_HAS_BY_IDENTIFIER = hasattr(dr.DeviceRegistry, "async_get_device_by_identifier")
_HAS_CONFIG_ENTRY_ID = hasattr(dr.DeviceEntry, "config_entry_id")


def device_by_identifier(
    dev_reg: dr.DeviceRegistry, domain: str, ident: str, entry_id: str
) -> dr.DeviceEntry | None:
    """Look up a device by ``(domain, ident)``.

    2026.8+ scopes the lookup to the owning config entry
    (``async_get_device_by_identifier``); older HA takes an ``identifiers`` set.
    """
    if _HAS_BY_IDENTIFIER:
        # 2026.8+ only; cast past the older type stubs that lack this method.
        return cast(
            "dr.DeviceEntry | None",
            cast(Any, dev_reg).async_get_device_by_identifier(
                (domain, ident), entry_id
            ),
        )
    return dev_reg.async_get_device(identifiers={(domain, ident)})


def owning_entry_ids(device: dr.DeviceEntry) -> list[str]:
    """Return the config-entry id(s) owning ``device``.

    2026.8+ exposes a single ``config_entry_id``; older HA a ``config_entries``
    set. Returned as a list so membership and iteration call sites stay uniform.
    """
    if _HAS_CONFIG_ENTRY_ID:
        # 2026.8+ only; cast past the older type stubs that lack this attribute.
        cid: str | None = cast(Any, device).config_entry_id
        return [cid] if cid else []
    return list(device.config_entries)


def via_device_link(
    hass: HomeAssistant, domain: str, parent_ident: str, entry_id: str
) -> dict[str, Any]:
    """Return the ``DeviceInfo`` kwarg linking a child device to its parent.

    2026.8+ deprecates the ``via_device`` identifier tuple in favour of
    ``via_device_id`` (a resolved device id), because identifiers are no longer
    globally unique — so resolve the parent's id from its identifier. Older HA
    gets the ``via_device`` tuple unchanged. An unresolved parent yields no link
    (the same outcome a dangling tuple would have had).
    """
    if _HAS_BY_IDENTIFIER:
        # 2026.8+ only; cast past the older type stubs that lack this method.
        parent = cast(Any, dr.async_get(hass)).async_get_device_by_identifier(
            (domain, parent_ident), entry_id
        )
        return {"via_device_id": parent.id} if parent is not None else {}
    return {"via_device": (domain, parent_ident)}
