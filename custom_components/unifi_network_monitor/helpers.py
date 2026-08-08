"""Shared helpers for the UniFi Network Monitor integration."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from homeassistant.helpers.device_registry import DeviceInfo, format_mac

from ._compat import via_device_link
from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from .coordinator import UnifiNetworkDataUpdateCoordinator


class UnifiAboutEntity:
    """Mixin exposing a static, human-facing ``about`` note as an attribute.

    Set the text via ``_attr_about`` (class-level for single-instance entities)
    or an ``about`` field on the entity description (for description-driven
    entities). The note shows in Tools / the More Info dialog but is
    listed in ``_unrecorded_attributes`` so the recorder never writes it to
    history — zero cost no matter how often the state changes.

    List this mixin FIRST in an entity's bases so its ``extra_state_attributes``
    wins over the platform default. Entities that define their own
    ``extra_state_attributes`` should route the result through ``_with_about``.
    """

    _unrecorded_attributes = frozenset({"about"})
    _attr_about: str | None = None

    @property
    def _about_text(self) -> str | None:
        """Resolve the note from ``_attr_about`` or the entity description."""
        if self._attr_about is not None:
            return self._attr_about
        description = getattr(self, "entity_description", None)
        return getattr(description, "about", None) if description is not None else None

    def _with_about(self, attrs: dict[str, Any] | None) -> dict[str, Any] | None:
        """Merge the ``about`` note into an entity's own attribute dict."""
        about = self._about_text
        if about is None:
            return attrs
        return {"about": about, **(attrs or {})}

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Default: expose only the ``about`` note when one is set."""
        return self._with_about(None)


def build_gateway_device_info(
    coordinator: UnifiNetworkDataUpdateCoordinator,
    entry: ConfigEntry,
) -> DeviceInfo:
    """Build DeviceInfo for the UDM Pro gateway device.

    The gateway is the root of Monitor's own device tree. It is identified solely
    by its domain identifier — deliberately no shared MAC ``connections`` — so it
    is never merged with the core ``unifi`` integration's device. Monitor owns its
    devices identically on every HA version (HA 2026.8 removed cross-integration
    merging; not sharing the connection makes older HA behave the same way). See
    ``.notes/device_registry/device_model_2026_08.md``.
    """
    mac = coordinator.gateway_mac
    return DeviceInfo(
        identifiers={(DOMAIN, mac)},
        name=f"{entry.title} Gateway",
        manufacturer="Ubiquiti",
        model=coordinator.gateway_model,
        sw_version=coordinator.sw_version,
        configuration_url=f"https://{entry.options.get('host', '')}",
    )


def build_network_device_info(
    coordinator: UnifiNetworkDataUpdateCoordinator,
    entry: ConfigEntry,
) -> DeviceInfo:
    """Build DeviceInfo for the virtual Network Health sub-device."""
    mac = coordinator.gateway_mac
    info = DeviceInfo(
        identifiers={(DOMAIN, f"{mac}_network")},
        name=f"{entry.title} Network",
        manufacturer="Ubiquiti",
    )
    cast(dict[str, Any], info).update(
        via_device_link(coordinator.hass, DOMAIN, mac, coordinator.entry.entry_id)
    )
    return info


def build_sub_device_info(
    coordinator: UnifiNetworkDataUpdateCoordinator,
    entry: ConfigEntry,
    device_key: str,
) -> DeviceInfo:
    """Build DeviceInfo for a virtual sub-device under the gateway."""
    mac = coordinator.gateway_mac
    if device_key == "gateway":
        return build_gateway_device_info(coordinator, entry)

    suffixes = {
        "internet": "Internet",
        "system": "System",
        "speedtest": "Speedtest",
        "status": "Status",
        "security": "Security",
        "alerts": "Alerts",
    }
    suffix = suffixes.get(device_key, "System")

    info = DeviceInfo(
        identifiers={(DOMAIN, f"{mac}_{device_key}")},
        name=f"{entry.title} {suffix}",
        manufacturer="Ubiquiti",
    )
    cast(dict[str, Any], info).update(
        via_device_link(coordinator.hass, DOMAIN, mac, coordinator.entry.entry_id)
    )
    return info


def build_unifi_device_info(
    coordinator: UnifiNetworkDataUpdateCoordinator,
    device_mac: str,
    device_name: str,
    device_model: str,
) -> DeviceInfo:
    """Build DeviceInfo for a dynamic UniFi device (AP or switch).

    Identified by its own domain identifier only — deliberately no shared MAC
    ``connections`` — so it is never merged with the core ``unifi`` integration on
    any HA version. Linked to the gateway as genuine connectivity (hardware behind
    the gateway): ``via_device_id`` on 2026.8+, the ``via_device`` tuple on older
    HA (see ``_compat.via_device_link``).
    """
    gateway_mac = coordinator.gateway_mac
    # Per-device MACs come straight off the controller payload, so canonicalise
    # here — the gateway MAC is already normalized by the coordinator (§3).
    device_mac = format_mac(device_mac)
    info = DeviceInfo(
        identifiers={(DOMAIN, device_mac)},
        name=device_name,
        manufacturer="Ubiquiti",
        model=device_model or None,
    )
    cast(dict[str, Any], info).update(
        via_device_link(
            coordinator.hass, DOMAIN, gateway_mac, coordinator.entry.entry_id
        )
    )
    return info


def calendar_cycle_bounds(now: datetime) -> tuple[datetime, datetime, int]:
    """Return (start, end, length_in_days) of the calendar month containing ``now``.

    UniFi's monthly counters roll on the 1st, so — unlike ZTE, which this is
    ported from — there is no router-reported clear day to discover and no
    fallback assumption to publish. Dropping the parameter is deliberate: a
    ``clear_day`` argument only ever called with ``1`` would be untestable
    generality carrying its own unreachable branches.

    ``now`` must be timezone-aware and in the user's local zone. Boundaries are
    **local** midnight; computing them in UTC would shift the reset day by up to
    a day for anyone not on UTC.

    Length is measured in **calendar days** by date subtraction rather than by
    dividing seconds, so a month containing a DST transition is still 30 or 31
    days rather than 30.04.
    """

    def _first_of(year: int, month: int) -> datetime:
        return now.replace(
            year=year, month=month, day=1, hour=0, minute=0, second=0, microsecond=0
        )

    start = _first_of(now.year, now.month)
    next_year, next_month = (
        (start.year + 1, 1) if start.month == 12 else (start.year, start.month + 1)
    )
    end = _first_of(next_year, next_month)
    return start, end, (end.date() - start.date()).days


def project_cycle_usage(
    used: float,
    elapsed_days: float,
    cycle_length_days: int,
    prior_rate: float | None,
    credibility_days: float,
) -> float:
    """Project end-of-cycle usage from usage so far.

    The naive form — ``used / elapsed * length`` — divides by a number
    approaching zero, so its error early in a cycle is unbounded: half a
    gigabyte one second after a reset projects to over a million. Two things
    tame it.

    First, the denominator is floored at one day. That alone bounds the result
    without inventing a cap.

    Second, when a previous cycle is known, its daily rate is blended in — but
    **only into the unobserved remainder**. Blending the whole projection would
    be wrong: by day 20 most of the figure is a meter reading rather than a
    forecast, and shrinking observed bytes toward last cycle is meaningless.
    Applying it to the remainder alone makes the prior's influence decay
    structurally, because it is multiplied by a shrinking number of days. No
    clamp and no cliff: at day 20 of 30 the prior moves the answer by around one
    percent, and by day 28 it is noise.

    ``credibility_days`` sets how quickly this cycle's own rate displaces the
    prior — the weight reaches one half at that many days elapsed.
    """
    elapsed = max(elapsed_days, 0.0)
    remaining = max(cycle_length_days - elapsed, 0.0)

    current_rate = used / max(elapsed, 1.0)

    if prior_rate is None:
        rate = current_rate
    else:
        weight = elapsed / (elapsed + credibility_days)
        rate = weight * current_rate + (1.0 - weight) * prior_rate

    return used + remaining * rate
