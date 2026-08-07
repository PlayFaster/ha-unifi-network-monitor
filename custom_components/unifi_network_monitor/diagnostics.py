"""Diagnostics support for UniFi Network Monitor."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .coordinator import UnifiNetworkDataUpdateCoordinator

REDACTED = "**REDACTED**"

TO_REDACT = {
    "api_key",
    "password",
    "username",
    "host",
    "wan_isp_name",
    "wan_isp_org",
    "mac",
    "wan1_local_ip",
    "wan1_public_ip",
    "wan2_local_ip",
    "wan2_public_ip",
    "bssid",
}

# ``async_redact_data`` rewrites values, never keys, and only matches keys this
# integration chose itself. Two classes of identifier therefore escape it:
# MAC-keyed dictionaries, and payloads passed through verbatim from UniFi
# (notably the alert ``parameters`` blob, which uses generic key names). The
# scrubbing below closes both gaps and runs *before* ``async_redact_data``.
#
# Matching here is structural only - by value shape, and by position in the
# payload. No real identifier is ever hard-coded: every literal is learned from
# the payload being scrubbed, so this works identically for any install.

_MAC_RE = re.compile(r"\b[0-9a-f]{2}(?::[0-9a-f]{2}){5}\b", re.IGNORECASE)
_IP_RE = re.compile(
    r"\b(?:"
    r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|192\.168\.\d{1,3}\.\d{1,3}"
    r"|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"
    r"|100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3}"
    r")(?:/\d{1,2})?\b"
)

# UniFi alert ``parameters`` block names. These are vendor schema constants,
# not user data. DEVICE blocks are pseudonymised so cross-references survive;
# the rest are blanked outright.
_ALERT_DEVICE_BLOCKS = frozenset({"DEVICE", "DEVICE_WITH_PORT"})
_ALERT_BLANK_BLOCKS = frozenset(
    {"ISP_NAME", "WAN_SUBNET", "WAN_NAME", "CONSOLE_NAME", "AP_NAME", "CLIENT"}
)
_ALERT_ATTR_KEYS = ("last_high_attrs", "last_very_high_attrs")
_ALERT_TEXT_KEYS = ("message", "title")

# Values worth scrubbing out of free text wherever they appear.
_LITERAL_KEYS = (
    "wan_isp_name",
    "wan_isp_org",
    "wan1_interface_name",
    "wan2_interface_name",
    "name",
)

# Gateway fields blanked outright. User-assigned WAN interface names routinely
# name the ISP (and sometimes the product or account), so they identify the
# subscriber even though nothing else about the field is sensitive. SFP serials
# are globally unique hardware identifiers; the vendor and part number beside
# them carry the diagnostic value, so nothing useful is lost.
_GATEWAY_BLANK_KEYS = (
    "wan1_interface_name",
    "wan2_interface_name",
    "wan1_sfp_serial",
    "wan2_sfp_serial",
)

# Fields on the rogue-AP list that describe *other people's* networks.
_ROGUE_LIST_KEY = "rogue_aps_list"
_ROGUE_SSID_KEY = "strongest_rogue_ssid"

# Literals shorter than this are not substituted into free text - a device
# named "1" would otherwise corrupt every number in the payload.
_MIN_LITERAL_LEN = 3


class _Scrubber:
    """Allocate stable tokens for identifiers and scrub them from free text.

    The same physical device keeps the same token everywhere it appears, so a
    diagnostics file stays useful for cross-referencing while carrying no real
    MAC, IP, device name or SSID.
    """

    def __init__(self) -> None:
        """Initialize an empty token map."""
        self._tokens: dict[str, str] = {}
        self._literals: set[str] = set()
        self._devices = 0
        self._rogues = 0

    def device_token(self, value: Any, label: str | None = None) -> str:
        """Return a stable token for a device MAC, allocating one if needed."""
        key = str(value or "").strip().lower()
        if not key or key == REDACTED.lower():
            return REDACTED
        token = self._tokens.get(key)
        if token is None:
            if label is not None:
                token = label
            else:
                self._devices += 1
                token = f"device-{self._devices}"
            self._tokens[key] = token
        self._remember(key)
        return token

    def rogue_token(self, value: Any) -> str:
        """Return a stable token for a nearby-network label (a third-party SSID)."""
        key = str(value or "").strip().lower()
        if not key:
            return REDACTED
        token = self._tokens.get(key)
        if token is None:
            self._rogues += 1
            token = f"rogue-{self._rogues}"
            self._tokens[key] = token
        self._remember(key)
        return token

    def alias(self, value: Any, token: str) -> None:
        """Point a second identifier (e.g. a device name) at an existing token."""
        key = str(value or "").strip().lower()
        if key:
            self._tokens.setdefault(key, token)
            self._remember(key)

    def literal(self, value: Any) -> None:
        """Mark a value for removal from free text, with no token of its own."""
        key = str(value or "").strip().lower()
        if key:
            self._remember(key)

    def text(self, value: str) -> str:
        """Scrub every known identifier, MAC and private IP from a string."""
        out = value
        for literal in sorted(self._literals, key=len, reverse=True):
            replacement = self._tokens.get(literal, REDACTED)
            out = re.sub(re.escape(literal), replacement, out, flags=re.IGNORECASE)
        out = _MAC_RE.sub(REDACTED, out)
        return _IP_RE.sub(REDACTED, out)

    def _remember(self, key: str) -> None:
        """Record a literal for free-text scrubbing if it is long enough to be safe."""
        if len(key) >= _MIN_LITERAL_LEN:
            self._literals.add(key)


def _is_mac(value: Any) -> bool:
    """Return True when a key is a MAC address rather than a plain label."""
    return bool(_MAC_RE.fullmatch(str(value or "").strip()))


def _learn(scrub: _Scrubber, source: Any) -> None:
    """Learn the free-text identifiers carried by a mapping."""
    if not isinstance(source, dict):
        return
    for key in _LITERAL_KEYS:
        value = source.get(key)
        if isinstance(value, str) and value:
            scrub.literal(value)


def _scrub_device(scrub: _Scrubber, record: Any) -> Any:
    """Pseudonymise the identifying fields of a single device record."""
    if not isinstance(record, dict):
        return record
    out = dict(record)
    if out.get("mac"):
        out["mac"] = scrub.device_token(out["mac"])
    for key in ("name", "hostname"):
        if isinstance(out.get(key), str) and out[key]:
            out[key] = scrub.text(out[key])
    return out


def _scrub_rogue_entry(scrub: _Scrubber, entry: Any) -> Any:
    """Scrub one rogue-AP record - a description of somebody else's network."""
    if not isinstance(entry, dict):
        return entry
    out = dict(entry)
    if out.get("essid"):
        out["essid"] = scrub.rogue_token(out["essid"])
    # ``detected_by`` is a comma-joined list of this user's own AP names.
    if isinstance(out.get("detected_by"), str) and out["detected_by"]:
        out["detected_by"] = scrub.text(out["detected_by"])
    return out


def _scrub_alert_block(scrub: _Scrubber, name: str, block: Any) -> Any:
    """Scrub one block of a UniFi alert ``parameters`` payload."""
    if not isinstance(block, dict):
        return scrub.text(block) if isinstance(block, str) else block

    out = dict(block)
    if name in _ALERT_DEVICE_BLOCKS:
        if out.get("id"):
            out["id"] = scrub.device_token(out["id"])
        if out.get("ip"):
            out["ip"] = REDACTED
    elif name in _ALERT_BLANK_BLOCKS:
        for key in ("id", "name"):
            if isinstance(out.get(key), str):
                out[key] = REDACTED

    # Backstop: UniFi can add parameter types we have not mapped, so every
    # remaining string goes through shape-based scrubbing regardless.
    for key, value in out.items():
        if isinstance(value, str):
            out[key] = scrub.text(value)
    return out


def _scrub_alert(scrub: _Scrubber, attrs: Any) -> Any:
    """Scrub a captured alert - both its free text and its parameters blob."""
    if not isinstance(attrs, dict):
        return attrs
    out = dict(attrs)
    params = out.get("parameters")
    if isinstance(params, dict):
        out["parameters"] = {
            name: _scrub_alert_block(scrub, name, block)
            for name, block in params.items()
        }
    for key in _ALERT_TEXT_KEYS:
        if isinstance(out.get(key), str):
            out[key] = scrub.text(out[key])
    return out


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: UnifiNetworkDataUpdateCoordinator = entry.runtime_data
    scrub = _Scrubber()

    # Copy before touching anything - diagnostics must never mutate live data.
    entry_data = deepcopy(dict(entry.data))
    entry_options = dict(entry.options)
    data = deepcopy(coordinator.data or {})

    gateway = data.get("gateway") if isinstance(data, dict) else None
    devices = data.get("devices") if isinstance(data, dict) else None

    # --- Pass 1: learn every identifier before rewriting anything ----------
    if isinstance(gateway, dict):
        if gateway.get("mac"):
            scrub.device_token(gateway["mac"], label="gateway")
        _learn(scrub, gateway)
    _learn(scrub, data.get("health") if isinstance(data, dict) else None)

    if isinstance(devices, dict):
        for mac, record in devices.items():
            token = scrub.device_token(mac)
            if isinstance(record, dict):
                scrub.alias(record.get("name"), token)
                scrub.alias(record.get("mac"), token)

    # ``boot_times`` is keyed by MAC for physical devices, but also carries
    # plain labels such as "wan1" for interface uptime. Tokenising those would
    # protect nothing and would corrupt any alert text mentioning "WAN1".
    boot_times = entry_data.get("boot_times")
    if isinstance(boot_times, dict):
        for key in boot_times:
            if _is_mac(key):
                scrub.device_token(key)
    if entry_data.get("mac"):
        scrub.device_token(entry_data["mac"], label="gateway")

    # Learn nearby-network names before any free text is scrubbed, so a real
    # SSID resolves to its token wherever it appears while a sentinel value
    # such as "None Detected" passes through untouched - no special-casing.
    for record in (coordinator.rogue_history or {}).values():
        if isinstance(record, dict) and record.get("last_label"):
            scrub.rogue_token(record["last_label"])
    if isinstance(gateway, dict):
        for record in gateway.get(_ROGUE_LIST_KEY) or []:
            if isinstance(record, dict) and record.get("essid"):
                scrub.rogue_token(record["essid"])

    # --- Pass 2: rewrite ---------------------------------------------------
    if isinstance(boot_times, dict):
        entry_data["boot_times"] = {
            (scrub.device_token(key) if _is_mac(key) else key): record
            for key, record in boot_times.items()
        }

    for key in ("rogue_ignore_ssids", "rogue_ignore_aps"):
        raw = entry_options.get(key)
        if isinstance(raw, str) and raw.strip():
            count = len([part for part in raw.split(",") if part.strip()])
            entry_options[key] = f"{REDACTED} ({count} entries)"

    if isinstance(devices, dict):
        data["devices"] = {
            scrub.device_token(mac): _scrub_device(scrub, record)
            for mac, record in devices.items()
        }

    if isinstance(gateway, dict):
        if isinstance(gateway.get("name"), str) and gateway["name"]:
            gateway["name"] = scrub.text(gateway["name"])
        for key in _GATEWAY_BLANK_KEYS:
            if isinstance(gateway.get(key), str) and gateway[key]:
                gateway[key] = REDACTED
        if isinstance(gateway.get(_ROGUE_SSID_KEY), str):
            gateway[_ROGUE_SSID_KEY] = scrub.text(gateway[_ROGUE_SSID_KEY])
        if isinstance(gateway.get(_ROGUE_LIST_KEY), list):
            gateway[_ROGUE_LIST_KEY] = [
                _scrub_rogue_entry(scrub, record) for record in gateway[_ROGUE_LIST_KEY]
            ]
        for key in _ALERT_ATTR_KEYS:
            if key in gateway:
                gateway[key] = _scrub_alert(scrub, gateway[key])

    # Emit history as a list of records (not a BSSID-keyed dict) so the ``bssid``
    # entry in TO_REDACT masks the MAC - async_redact_data redacts values, not keys.
    rogue_history = []
    for bssid, record in (coordinator.rogue_history or {}).items():
        item: dict[str, Any] = {"bssid": bssid}
        if isinstance(record, dict):
            item.update(record)
        # A nearby network's label is another person's SSID - the sibling BSSID
        # being redacted makes this look covered when it is the more
        # identifying half of the pair.
        if item.get("last_label"):
            item["last_label"] = scrub.rogue_token(item["last_label"])
        rogue_history.append(item)

    # The default title carries nothing, but a user may have renamed the entry
    # to something identifying - scrub it like any other free text.
    title = entry.title
    if isinstance(title, str) and title:
        title = scrub.text(title)

    return {
        "entry": {
            "title": title,
            "data": async_redact_data(entry_data, TO_REDACT),
            "options": async_redact_data(entry_options, TO_REDACT),
        },
        "rogue_history": async_redact_data(rogue_history, TO_REDACT),
        "coordinator": {
            "consecutive_failures": coordinator.consecutive_failures,
            "last_update_success": coordinator.last_update_success,
            "last_update_success_time": (
                coordinator.last_update_success_time.isoformat()
                if coordinator.last_update_success_time
                else None
            ),
            "data_available": coordinator.data is not None,
            "gateway_mac": async_redact_data(
                {"mac": coordinator.gateway_mac}, TO_REDACT
            ).get("mac"),
            "gateway_model": coordinator.gateway_model,
            "sw_version": coordinator.sw_version,
            "integration_health": (coordinator.data or {}).get("integration_health"),
        },
        "data": async_redact_data(data, TO_REDACT),
    }
