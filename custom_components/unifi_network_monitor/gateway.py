"""Gateway selection from a UniFi ``stat/device`` list.

Signature first: the gateway is the device carrying a non-empty ``wan1`` or
``wan2`` object. The device ``type`` and the model list narrow ties and serve
as fallbacks where no device carries a WAN object. The module has no Home
Assistant imports, so the API client, the coordinator and the hardware-check
script share it without an import cycle.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
import re
from typing import Any, Literal

from .const import GATEWAY_MODELS, GATEWAY_TYPES

SelectionReason = Literal["wan_signature", "type", "model", "ambiguous", "none"]

_Device = dict[str, Any]


@dataclass(frozen=True)
class GatewaySelection:
    """The selected gateway, the reason, and its confirmation signals."""

    device: _Device | None
    reason: SelectionReason
    candidates: tuple[_Device, ...] = field(default_factory=tuple)

    @property
    def has_wan(self) -> bool:
        """Return True when the selected device carries a WAN object."""
        return self.device is not None and has_wan_signature(self.device)

    @property
    def type_match(self) -> bool:
        """Return True when the selected device's type is a gateway type."""
        return self.device is not None and is_gateway_type(self.device)

    @property
    def model_listed(self) -> bool:
        """Return True when the selected device's model is listed."""
        return self.device is not None and is_listed_model(self.device)

    @property
    def signals(self) -> int:
        """Return how many of the three confirmation signals hold."""
        return int(self.has_wan) + int(self.type_match) + int(self.model_listed)


def has_wan_signature(device: _Device) -> bool:
    """Return True when ``wan1`` or ``wan2`` is a non-empty dict."""
    return any(
        isinstance(device.get(key), dict) and bool(device.get(key))
        for key in ("wan1", "wan2")
    )


def is_gateway_type(device: _Device) -> bool:
    """Return True when the device ``type`` is a gateway type."""
    return device.get("type") in GATEWAY_TYPES


def is_listed_model(device: _Device) -> bool:
    """Return True when the device ``model`` is in the gateway model list."""
    return device.get("model") in GATEWAY_MODELS


def is_online(device: _Device) -> bool:
    """Return True unless ``state`` is 0; a missing ``state`` counts as online."""
    return bool(device.get("state", 1) != 0)


def mac_key(mac: Any) -> str:
    """Return a MAC reduced to lowercase hex digits, for comparison only."""
    return re.sub(r"[^0-9a-f]", "", str(mac or "").lower())


def _narrow(
    candidates: list[_Device], predicate: Callable[[_Device], bool]
) -> list[_Device]:
    """Keep candidates matching ``predicate``; skip the step if none would remain."""
    kept = [d for d in candidates if predicate(d)]
    return kept or candidates


def _resolve(
    candidates: list[_Device], reason: SelectionReason, stored_mac: str
) -> GatewaySelection:
    """Return the single candidate, or break a tie on the stored MAC."""
    if len(candidates) == 1:
        return GatewaySelection(candidates[0], reason, tuple(candidates))
    if stored_mac:
        held = [d for d in candidates if mac_key(d.get("mac")) == stored_mac]
        if len(held) == 1:
            return GatewaySelection(held[0], reason, tuple(candidates))
    return GatewaySelection(None, "ambiguous", tuple(candidates))


def _by_signature(carriers: list[_Device], stored_mac: str) -> GatewaySelection:
    """Select among WAN carriers, narrowed by type, online state and model."""
    pool = _narrow(carriers, is_gateway_type)
    pool = _narrow(pool, is_online)
    pool = _narrow(pool, is_listed_model)
    return _resolve(pool, "wan_signature", stored_mac)


def _by_type_or_model(
    devices: list[_Device], stored_mac: str
) -> GatewaySelection | None:
    """Select by gateway type, then by listed model; None when neither applies."""
    typed = [d for d in devices if is_gateway_type(d)]
    if typed:
        pool = _narrow(_narrow(typed, is_online), is_listed_model)
        return _resolve(pool, "type", stored_mac)
    listed = [d for d in devices if is_listed_model(d)]
    if listed:
        return _resolve(_narrow(listed, is_online), "model", stored_mac)
    return None


def select_gateway(
    devices: Sequence[_Device], stored_mac: str | None = None
) -> GatewaySelection:
    """Select the gateway from a ``stat/device`` list.

    Online WAN carriers are considered first, then online devices by type or
    model, then offline WAN carriers, then any device by type or model, so an
    offline gateway is still identified but never preferred over an online
    candidate. A tie is broken in favor of the stored MAC before ``ambiguous``
    is returned.
    """
    stored = mac_key(stored_mac)
    all_devices = [d for d in devices if isinstance(d, dict)]
    online = [d for d in all_devices if is_online(d)]

    carriers = [d for d in online if has_wan_signature(d)]
    if carriers:
        return _by_signature(carriers, stored)
    selection = _by_type_or_model(online, stored)
    if selection is not None:
        return selection
    offline_carriers = [d for d in all_devices if has_wan_signature(d)]
    if offline_carriers:
        return _by_signature(offline_carriers, stored)
    selection = _by_type_or_model(all_devices, stored)
    if selection is not None:
        return selection
    return GatewaySelection(None, "none")
