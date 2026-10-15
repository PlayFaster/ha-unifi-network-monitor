"""Diagnostics support for UniFi Network Monitor."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from datetime import UTC, datetime
import logging
import re
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .coordinator import UnifiNetworkDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

REDACTED = "**REDACTED**"

# UniFi's built-in site name. It says nothing about the install, so it is kept;
# any other site name is the user's own and is redacted.
_DEFAULT_SITE = "default"

# Fields the diagnostics captures produce (``api.last_rejection``,
# ``api.login_metadata``, ``api.routes`` and ``coordinator.endpoint_outcomes``),
# partitioned by what the download does with them
# (improve_diagnostics_on_bad_payload_data.md §2.4, §3). PUBLISHED fields are
# names, codes, counts and flags and go out as they are. GATED fields can carry a
# value from the controller and pass the scrubber first. A new field fails
# ``test_every_discovery_field_is_classified`` until it is placed in one set.
DISCOVERY_METADATA_PUBLISHED = frozenset(
    {
        "verdict",
        "method",
        "route",
        "status",
        "rc",
        "records",
        "populated",
        "content_type",
        "text_length",
        "recorded_at",
        "outcome",
        "header_names",
        "cookie_names",
        "token_issued",
        "token_source",
        "csrf_header",
        "error",
        "strikes",
        "reason",
    }
)
DISCOVERY_METADATA_GATED = frozenset({"msg", "keys", "payload", "body_preview"})

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

# The address patterns are those of ``huawei_router_5g`` (and, for the MAC,
# ``zte_router_5g``), so the suite scrubs the same shapes the same way. Every
# IPv4 address is matched, public as well as private. Each octet is bounded to
# 0-255 and not adjacent to a word character or ``(``, nor followed by ``.`` and a
# word character, so a dotted version string carrying a suffix is not mistaken for
# an address while an address ending a sentence is still matched.
_OCTET = r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"
_IPV4_RE = re.compile(
    rf"(?<![\w.])(?:{_OCTET}\.){{3}}{_OCTET}(?![\w(]|\.\w)",
)
_MAC_RE = re.compile(r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b")
# Requires either a ``::`` elision or the full eight-group form. Anything looser
# matches a ``HH:MM:SS`` timestamp, which has three hex-looking colon groups.
_IPV6_RE = re.compile(
    r"\b(?:[0-9A-Fa-f]{1,4}:){1,7}:(?:[0-9A-Fa-f]{1,4}(?::[0-9A-Fa-f]{1,4})*)?"
    r"|\b(?:[0-9A-Fa-f]{1,4}:){7}[0-9A-Fa-f]{1,4}\b"
)
# Addresses that identify no install: loopback, unspecified, and the public
# resolvers a gateway is commonly set to use. They are kept where they appear.
_ALLOWED_ADDRESSES = frozenset(
    {
        "0.0.0.0",  # noqa: S104 - a value compared against, never bound to
        "127.0.0.1",
        "1.1.1.1",
        "1.0.0.1",
        "8.8.8.8",
        "8.8.4.4",
        "9.9.9.9",
        "::",
        "::1",
    }
)


def _redact_address(match: re.Match[str]) -> str:
    """Return the marker for a matched address, unless it is on the allowed set."""
    found = match.group(0)
    return found if found.lower() in _ALLOWED_ADDRESSES else REDACTED


# UniFi alert ``parameters`` block names. These are vendor schema constants,
# not user data. Device-shaped blocks are pseudonymised so cross-references
# survive. Blocks whose fields are radio, traffic or timing measures, or a fixed
# setting, are kept and pass the text backstop. Every other block, including one
# UniFi adds later, has every string redacted at any depth: an allow-list fails
# closed. The safe set was classed by block name and field type
# (docs/DEVELOPMENT.md).
_ALERT_DEVICE_BLOCKS = frozenset(
    {
        "DEVICE",
        "DEVICE_WITH_PORT",
        "DEVICE_FROM",
        "DEVICE_TO",
        "DST_DEVICE",
        "SRC_DEVICE",
    }
)
_ALERT_SAFE_BLOCKS = frozenset(
    {
        "AUTH_METHOD",
        "AVG_INTERFERENCE",
        "AVG_UTILIZATION",
        "CHANNEL",
        "CHANNEL_WIDTH",
        "DATA_DOWN",
        "DATA_UP",
        "DURATION",
        "LEARN_MORE",
        "PORT",
        "PREVIOUS_CHANNEL",
        "PREVIOUS_CHANNEL_WIDTH",
        "PREVIOUS_RADIO_BAND",
        "PREVIOUS_SIGNAL_STRENGTH",
        "RADIO_BAND",
        "SIGNAL_STRENGTH",
        "TRIGGER",
        "WAN_ID",
        "WAN_SLA",
        "WIFI_STATS",
    }
)
# Fields of a redacted block whose value the alert's prose repeats; they are
# learned so the message loses them too. An ``id`` is a generic code, such as
# "WAN", and is not learned.
_ALERT_LEARNED_FIELDS = frozenset({"name", "hostname"})
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

# Gateway maps keyed by the user's own names: SSIDs and site-to-site tunnel
# names (coordinator.py, ``wifi_states`` and ``vpn_states``). The keys are the
# identifiers and are tokenised by kind; the booleans are kept.
_NAMED_STATE_MAPS = (("wifi_states", "wlan"), ("vpn_states", "vpn"))

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
        self._named: dict[str, int] = {}
        self._pattern: re.Pattern[str] | None = None

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

    def named_token(self, value: Any, kind: str) -> str:
        """Return a stable token for one of the user's own names, such as an SSID."""
        key = str(value or "").strip().lower()
        if not key:
            return REDACTED
        token = self._tokens.get(key)
        if token is None:
            self._named[kind] = self._named.get(kind, 0) + 1
            token = f"{kind}-{self._named[kind]}"
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
        """Scrub every known identifier, MAC and IP address from a string.

        A learned literal is replaced only as a whole word, in one pass, so a
        replacement is never scanned again and the redaction marker is never
        entered: a rogue SSID ``RED`` leaves ``**REDACTED**`` and ``Redmond`` alone.
        """
        out = self._literal_pattern().sub(self._replace, value)
        # MACs are swept before IPv6 because the two shapes overlap.
        out = _MAC_RE.sub(REDACTED, out)
        out = _IPV4_RE.sub(_redact_address, out)
        return _IPV6_RE.sub(_redact_address, out)

    def _literal_pattern(self) -> re.Pattern[str]:
        """Return the marker and every literal as one alternation, longest first.

        A literal takes a word boundary only on an edge that is a word character,
        so ``[Guest] WiFi`` and ``IoT-Guest.5G`` match between spaces or
        punctuation (the form ``scripts/diag_check.py`` uses for its leak scan).
        """
        if self._pattern is None:
            parts = [re.escape(REDACTED)]
            for literal in sorted(self._literals, key=len, reverse=True):
                head = r"(?<!\w)" if re.match(r"\w", literal) else ""
                tail = r"(?!\w)" if re.match(r"\w", literal[-1]) else ""
                parts.append(f"{head}{re.escape(literal)}{tail}")
            self._pattern = re.compile("|".join(parts), re.IGNORECASE)
        return self._pattern

    def _replace(self, match: re.Match[str]) -> str:
        """Return the token for a matched literal; the marker is kept as it is."""
        found = match.group(0)
        if found == REDACTED:
            return found
        return self._tokens.get(found.lower(), REDACTED)

    def _remember(self, key: str) -> None:
        """Record a literal for free-text scrubbing if it is long enough to be safe."""
        if len(key) >= _MIN_LITERAL_LEN and key not in self._literals:
            self._literals.add(key)
            self._pattern = None


def _is_mac(value: Any) -> bool:
    """Return True when a key is a MAC address rather than a plain label."""
    return bool(_MAC_RE.fullmatch(str(value or "").strip()))


# entry.data keys written by the gateway identity correction (identity.py);
# each holds a MAC or, for an entry set up with no gateway, the host.
_IDENTITY_KEYS = ("previous_unique_id", "previous_mac", "identity_blocked_mac")


def _scrub_identity_value(scrub: _Scrubber, value: Any) -> Any:
    """Tokenise a MAC as a device MAC; redact anything else, such as a host."""
    if not value:
        return value
    return scrub.device_token(value) if _is_mac(value) else REDACTED


def _scrub_identity_keys(scrub: _Scrubber, entry_data: dict[str, Any]) -> None:
    """Scrub the identity-correction keys, including the pending record."""
    for key in _IDENTITY_KEYS:
        if key in entry_data:
            entry_data[key] = _scrub_identity_value(scrub, entry_data[key])
    pending = entry_data.get("identity_pending")
    if isinstance(pending, dict):
        entry_data["identity_pending"] = {
            k: (_scrub_identity_value(scrub, v) if k in (*_IDENTITY_KEYS, "mac") else v)
            for k, v in pending.items()
        }


def _scrub_value(scrub: _Scrubber, value: Any) -> Any:
    """Scrub every string inside a captured value, at any depth."""
    if isinstance(value, str):
        return scrub.text(value)
    if isinstance(value, dict):
        return {key: _scrub_value(scrub, item) for key, item in value.items()}
    if isinstance(value, list):
        return [_scrub_value(scrub, item) for item in value]
    return value


def _publish_capture(scrub: _Scrubber, record: Any) -> Any:
    """Publish one capture record: gated fields scrubbed, the rest as they are."""
    if not isinstance(record, dict):
        return None
    out: dict[str, Any] = {}
    for key, value in record.items():
        if key in DISCOVERY_METADATA_GATED:
            out[key] = async_redact_data(_scrub_value(scrub, value), TO_REDACT)
        elif key in DISCOVERY_METADATA_PUBLISHED:
            out[key] = value
    return out


def _endpoints_block(scrub: _Scrubber, coordinator: Any) -> dict[str, Any]:
    """Each endpoint's latest outcome, and each route's status and ``meta.rc``."""
    outcomes = getattr(coordinator, "endpoint_outcomes", None)
    routes = getattr(coordinator.api, "routes", None)
    return {
        "outcomes": {
            str(label): _publish_capture(scrub, record)
            for label, record in (
                outcomes if isinstance(outcomes, dict) else {}
            ).items()
        },
        "routes": {
            str(key): _publish_capture(scrub, record)
            for key, record in (routes if isinstance(routes, dict) else {}).items()
        },
    }


def _iso(timestamp: Any) -> str | None:
    """Return an epoch-seconds value as an ISO time in UTC, or None."""
    if isinstance(timestamp, bool) or not isinstance(timestamp, int):
        return None
    return datetime.fromtimestamp(timestamp, UTC).isoformat()


def _gateway_block(
    scrub: _Scrubber, coordinator: Any, data: Any, boot_times: Any
) -> dict[str, Any]:
    """Selection, uptime evidence and controller timezone for the gateway."""
    selection = getattr(coordinator, "gateway_selection", None)
    reason = getattr(selection, "reason", None)
    selected = getattr(selection, "device", None)
    raw_candidates = getattr(selection, "candidates", ())
    candidates = [
        {
            "device": scrub.device_token(device.get("mac")),
            "model": device.get("model"),
            "type": device.get("type"),
            "state": device.get("state"),
        }
        for device in (
            raw_candidates if isinstance(raw_candidates, (tuple, list)) else ()
        )
        if isinstance(device, dict)
    ]
    gateway = data.get("gateway") if isinstance(data, dict) else None
    gateway = gateway if isinstance(gateway, dict) else {}
    startup = getattr(coordinator, "gateway_startup_timestamp", None)
    absent = getattr(coordinator, "stored_mac_absent", None)
    timezone = getattr(coordinator, "controller_timezone", None)
    # The gateway's latched boot time is cached under the label "gateway"
    # (coordinator.get_stable_boot_time), not under its MAC.
    cached = boot_times.get("gateway") if isinstance(boot_times, dict) else None
    return {
        "selection_reason": reason if isinstance(reason, str) else None,
        "selected": scrub.device_token(selected.get("mac"))
        if isinstance(selected, dict)
        else None,
        "candidates": candidates,
        "stored_mac_absent": absent if isinstance(absent, bool) else None,
        "startup_timestamp": startup
        if isinstance(startup, int) and not isinstance(startup, bool)
        else None,
        "startup_time": _iso(startup),
        "published_boot_time": gateway.get("boot_time"),
        "uptime_secs": gateway.get("uptime_secs"),
        "boot_times_cache": cached,
        "controller_timezone": timezone if isinstance(timezone, str) else None,
    }


def _section(name: str, build: Callable[[], Any]) -> Any:
    """Build one download section; a failure is recorded, never raised.

    Home Assistant does not wrap ``config_entry_diagnostics``, so an exception
    here is an HTTP 500 and no file at all (bad payload §5.1).
    """
    try:
        return build()
    except Exception as err:  # noqa: BLE001 - the download must always be produced
        _LOGGER.debug("Diagnostics section %s failed: %s", name, type(err).__name__)
        return {"section_error": type(err).__name__}


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


def _map_strings(value: Any, fn: Callable[[str], Any]) -> Any:
    """Apply ``fn`` to every string inside a value, at any depth."""
    if isinstance(value, str):
        return fn(value)
    if isinstance(value, dict):
        return {key: _map_strings(item, fn) for key, item in value.items()}
    if isinstance(value, list):
        return [_map_strings(item, fn) for item in value]
    return value


def _learn_alert_fields(scrub: _Scrubber, value: Any) -> None:
    """Learn the names a redacted block carries, at any depth."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key in _ALERT_LEARNED_FIELDS and isinstance(item, str):
                scrub.literal(item)
            else:
                _learn_alert_fields(scrub, item)
    elif isinstance(value, list):
        for item in value:
            _learn_alert_fields(scrub, item)


def _scrub_alert_block(scrub: _Scrubber, name: str, block: Any) -> Any:
    """Scrub one block of a UniFi alert ``parameters`` payload."""
    if name in _ALERT_SAFE_BLOCKS:
        return _map_strings(block, scrub.text)
    if name in _ALERT_DEVICE_BLOCKS and isinstance(block, dict):
        out = dict(block)
        if out.get("id"):
            out["id"] = scrub.device_token(out["id"])
            # The device's name resolves to its token wherever it appears.
            scrub.alias(out.get("name"), out["id"])
        if out.get("ip"):
            out["ip"] = REDACTED
        return {
            key: (value if key == "id" else _map_strings(value, scrub.text))
            for key, value in out.items()
        }
    _learn_alert_fields(scrub, block)
    return _map_strings(block, lambda _: REDACTED)


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


def _learn_gateway_and_devices(scrub: _Scrubber, data: Any) -> None:
    """Pass 1: learn the gateway, health and device identifiers."""
    gateway = data.get("gateway") if isinstance(data, dict) else None
    devices = data.get("devices") if isinstance(data, dict) else None
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

    if isinstance(gateway, dict):
        for key, kind in _NAMED_STATE_MAPS:
            states = gateway.get(key)
            if isinstance(states, dict):
                for name in states:
                    scrub.named_token(name, kind)
        # Names in redacted alert blocks are learned before any text is scrubbed,
        # so the other alert's message, scrubbed first, loses them too.
        for key in _ALERT_ATTR_KEYS:
            attrs = gateway.get(key)
            params = attrs.get("parameters") if isinstance(attrs, dict) else None
            if isinstance(params, dict):
                for name, block in params.items():
                    if name not in _ALERT_SAFE_BLOCKS | _ALERT_DEVICE_BLOCKS:
                        _learn_alert_fields(scrub, block)


def _learn_entry(scrub: _Scrubber, entry_data: dict[str, Any], boot_times: Any) -> None:
    """Pass 1: learn the MACs held in the config entry's data."""
    # ``boot_times`` is keyed by MAC for physical devices, but also carries
    # plain labels such as "wan1" for interface uptime. Tokenising those would
    # protect nothing and would corrupt any alert text mentioning "WAN1".
    if isinstance(boot_times, dict):
        for key in boot_times:
            if _is_mac(key):
                scrub.device_token(key)
    if entry_data.get("mac"):
        scrub.device_token(entry_data["mac"], label="gateway")


def _learn_rogues(scrub: _Scrubber, coordinator: Any, gateway: Any) -> None:
    """Pass 1: learn nearby-network names before any free text is scrubbed.

    A real SSID then resolves to its token wherever it appears, while a sentinel
    value such as "None Detected" passes through untouched - no special-casing.
    """
    for record in (coordinator.rogue_history or {}).values():
        if isinstance(record, dict) and record.get("last_label"):
            scrub.rogue_token(record["last_label"])
    if isinstance(gateway, dict):
        for record in gateway.get(_ROGUE_LIST_KEY) or []:
            if isinstance(record, dict) and record.get("essid"):
                scrub.rogue_token(record["essid"])


def _scrub_entry(
    scrub: _Scrubber,
    entry_data: dict[str, Any],
    entry_options: dict[str, Any],
    boot_times: Any,
) -> None:
    """Pass 2: rewrite the config entry's data and options in place."""
    _scrub_identity_keys(scrub, entry_data)
    if isinstance(boot_times, dict):
        entry_data["boot_times"] = {
            (scrub.device_token(key) if _is_mac(key) else key): record
            for key, record in boot_times.items()
        }

    site = entry_options.get("site")
    if isinstance(site, str) and site and site != _DEFAULT_SITE:
        entry_options["site"] = REDACTED

    for key in ("rogue_ignore_ssids", "rogue_ignore_aps"):
        raw = entry_options.get(key)
        if isinstance(raw, str) and raw.strip():
            count = len([part for part in raw.split(",") if part.strip()])
            entry_options[key] = f"{REDACTED} ({count} entries)"


def _scrub_gateway(scrub: _Scrubber, gateway: dict[str, Any]) -> None:
    """Pass 2: rewrite the gateway record in place."""
    if isinstance(gateway.get("name"), str) and gateway["name"]:
        gateway["name"] = scrub.text(gateway["name"])
    for key in _GATEWAY_BLANK_KEYS:
        if isinstance(gateway.get(key), str) and gateway[key]:
            gateway[key] = REDACTED
    for key, kind in _NAMED_STATE_MAPS:
        states = gateway.get(key)
        if isinstance(states, dict):
            gateway[key] = _tokenised_keys(scrub, states, kind)
    if isinstance(gateway.get(_ROGUE_SSID_KEY), str):
        gateway[_ROGUE_SSID_KEY] = scrub.text(gateway[_ROGUE_SSID_KEY])
    if isinstance(gateway.get(_ROGUE_LIST_KEY), list):
        gateway[_ROGUE_LIST_KEY] = [
            _scrub_rogue_entry(scrub, record) for record in gateway[_ROGUE_LIST_KEY]
        ]
    for key in _ALERT_ATTR_KEYS:
        if key in gateway:
            gateway[key] = _scrub_alert(scrub, gateway[key])


def _tokenised_keys(
    scrub: _Scrubber, states: dict[Any, Any], kind: str
) -> dict[str, Any]:
    """Return a map with its keys tokenised and its key count kept.

    Names differing only in case or spacing, or blank, share a token; each later
    one gets a numbered suffix, so no state is lost.
    """
    out: dict[str, Any] = {}
    for name, state in states.items():
        token = scrub.named_token(name, kind)
        unique, n = token, 1
        while unique in out:
            n += 1
            unique = f"{token}#{n}"
        out[unique] = state
    return out


def _rogue_history(scrub: _Scrubber, coordinator: Any) -> list[dict[str, Any]]:
    """Return the rogue history as a list of records with labels tokenised.

    A list, not a BSSID-keyed dict, so the ``bssid`` entry in TO_REDACT masks the
    MAC - async_redact_data redacts values, not keys.
    """
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
    return rogue_history


def _coordinator_block(coordinator: Any) -> dict[str, Any]:
    """Return the coordinator's run state."""
    return {
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
    }


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
    boot_times = entry_data.get("boot_times")

    # --- Pass 1: learn every identifier before rewriting anything ----------
    _learn_gateway_and_devices(scrub, data)
    _learn_entry(scrub, entry_data, boot_times)
    _learn_rogues(scrub, coordinator, gateway)

    # --- Pass 2: rewrite ---------------------------------------------------
    _scrub_entry(scrub, entry_data, entry_options, boot_times)

    if isinstance(devices, dict):
        data["devices"] = {
            scrub.device_token(mac): _scrub_device(scrub, record)
            for mac, record in devices.items()
        }

    if isinstance(gateway, dict):
        _scrub_gateway(scrub, gateway)

    rogue_history = _rogue_history(scrub, coordinator)

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
        "coordinator": _coordinator_block(coordinator),
        "data": async_redact_data(data, TO_REDACT),
        "last_rejection": _section(
            "last_rejection",
            lambda: _publish_capture(
                scrub, getattr(coordinator.api, "last_rejection", None)
            ),
        ),
        "login": _section(
            "login",
            lambda: _publish_capture(
                scrub, getattr(coordinator.api, "login_metadata", None)
            ),
        ),
        "endpoints": _section(
            "endpoints", lambda: _endpoints_block(scrub, coordinator)
        ),
        "gateway": _section(
            "gateway", lambda: _gateway_block(scrub, coordinator, data, boot_times)
        ),
    }
