#!/usr/bin/env python3
"""Check the REAL diagnostics download against a real UniFi controller.

Not part of CI, and not a unit test. It takes the download a user attaches to an
issue, from Home Assistant itself, and asserts over the file rather than over the
code that builds it (improve_diagnostics_on_bad_payload_data.md §5.6):

  * **Two downloads, compared.** Taken one after the other through
    ``GET /api/diagnostics/config_entry/<entry_id>``. Their structure must match,
    with list positions ignored and a listed set of sections that legitimately
    come and go.
  * **Each block holds what a healthy run holds.** ``endpoints`` lists an outcome
    for every endpoint; ``gateway`` carries a selection reason and the uptime and
    timezone keys; ``last_rejection`` is present and ``null``; ``login`` is
    present, and empty in API-key mode, where ``login()`` never runs.
  * **Leak scan.** The controller's own client, device, WLAN, network and rogue
    lists are read read-only, and any of their values found as a whole word in
    either download fails the check. The script prints counts and paths, never a
    value.

``--sabotage`` (run by ``Hardware: Check Diagnostics Recovery``) is not
applicable to this integration: an API-key install holds no session to take
away, and recovery from a lost password-mode session is unmeasured (see
``docs/DEVELOPMENT.md``). It prints that and exits 0.

Usage, inside the devcontainer, with Home Assistant running:
    /usr/local/bin/python scripts/diag_check.py
"""

# ruff: noqa: T201 - an operator script's output *is* its interface; printing is
# the point, and routing it through a logger would hide it behind log levels.

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

# Installs probatio as `voluptuous` before the package imports it (C-036).
import homeassistant  # noqa: F401

_PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT))

from custom_components.unifi_network_monitor.api import (  # noqa: E402
    UnifiError,
    UnifiNetworkAPI,
)
from custom_components.unifi_network_monitor.const import DOMAIN  # noqa: E402

# Colour is on unless `NO_COLOR` is set, matching the Huawei and ZTE scripts:
# stdout here is usually a pipe into `tee`, so auto-detection would strip it
# exactly when it is wanted. The task strips ANSI codes with `sed` before it
# writes the report file the results summary reads.
_COLOUR = os.environ.get("NO_COLOR") is None


def _c(code: str, text: str) -> str:
    """Wrap text in an ANSI code, or return it unchanged when colour is off."""
    return f"\033[{code}m{text}\033[0m" if _COLOUR else text


def _green(text: str) -> str:
    """Return text in bold green."""
    return _c("1;32", text)


def _red(text: str) -> str:
    """Return text in bold red."""
    return _c("1;31", text)


_STORAGE = Path("/config/.storage/core.config_entries")
_TOKEN = _PROJECT / ".notes" / "ha_restart" / "token.txt"
_HA = "http://127.0.0.1:8123"

# Values shorter than this match ordinary words and numbers, so they are not
# scanned for.
_MIN_VALUE_LEN = 4

# Sections whose presence legitimately changes between two downloads: an alert
# or a rejection can arrive between them.
_VOLATILE_PREFIXES = (
    "data.gateway.last_high_attrs",
    "data.gateway.last_very_high_attrs",
    "last_rejection",
)

# Fields built from fixed request paths with placeholders; a word in them is the
# integration's own route, never user data.
_ROUTE_FIELDS = frozenset({"route"})


def _load_options() -> dict[str, Any]:
    """Read this integration's options out of the HA config-entry store."""
    if not _STORAGE.is_file():
        raise SystemExit(f"No config-entry store at {_STORAGE}.")
    store = json.loads(_STORAGE.read_text(encoding="utf-8"))
    for entry in store.get("data", {}).get("entries", []):
        if entry.get("domain") == DOMAIN:
            return dict(entry.get("options") or {})
    raise SystemExit(f"No {DOMAIN} config entry found in {_STORAGE}.")


def paths(value: Any, prefix: str = "") -> set[str]:
    """Return the key paths of a structure, list positions collapsed to ``[]``."""
    out = {prefix} if prefix else set()
    if isinstance(value, dict):
        for key, item in value.items():
            out |= paths(item, f"{prefix}.{key}" if prefix else str(key))
    elif isinstance(value, list):
        for item in value:
            out |= paths(item, f"{prefix}[]")
    return out


def structure_drift(first: dict[str, Any], second: dict[str, Any]) -> list[str]:
    """Return key paths present in one download only, outside the volatile set."""
    diff = paths(first) ^ paths(second)
    return sorted(p for p in diff if not p.startswith(_VOLATILE_PREFIXES))


def block_problems(download: dict[str, Any], api_key_mode: bool) -> list[str]:
    """Return what a healthy download's blocks lack."""
    problems = [
        f"missing block: {key}"
        for key in ("endpoints", "gateway", "last_rejection", "login")
        if key not in download
    ]
    outcomes = (download.get("endpoints") or {}).get("outcomes") or {}
    if not outcomes:
        problems.append("endpoints.outcomes is empty")
    for label, record in outcomes.items():
        if not isinstance(record, dict) or not record.get("outcome"):
            problems.append(f"endpoints.outcomes.{label} has no outcome")
    gateway = download.get("gateway") or {}
    if not isinstance(gateway.get("selection_reason"), str):
        problems.append("gateway.selection_reason is not set")
    problems.extend(
        f"gateway.{key} is missing"
        for key in ("startup_timestamp", "controller_timezone", "published_boot_time")
        if key not in gateway
    )
    if download.get("last_rejection") is not None:
        problems.append("last_rejection is set on a healthy run")
    if api_key_mode and download.get("login") is not None:
        problems.append("login is set although API-key mode never logs in")
    return problems


def leaves(value: Any, prefix: str = "") -> list[tuple[str, str]]:
    """Return every string leaf with its path, route fields excluded."""
    out: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in _ROUTE_FIELDS:
                continue
            out += leaves(item, f"{prefix}.{key}" if prefix else str(key))
    elif isinstance(value, list):
        for item in value:
            out += leaves(item, f"{prefix}[]")
    elif isinstance(value, str):
        out.append((prefix, value))
    return out


def leak_hits(
    download: dict[str, Any], secrets: dict[str, set[str]]
) -> dict[str, list[str]]:
    """Return, per category, the paths where a listed value appears as a word."""
    found: dict[str, list[str]] = {}
    strings = leaves(download)
    for category, values in secrets.items():
        for value in values:
            if len(value) < _MIN_VALUE_LEN:
                continue
            pattern = re.compile(rf"(?<!\w){re.escape(value)}(?!\w)", re.IGNORECASE)
            for path, text in strings:
                if pattern.search(text):
                    found.setdefault(category, []).append(path)
    return found


async def _controller_values(api: UnifiNetworkAPI, site: str) -> dict[str, set[str]]:
    """Read the controller's identifying values, read-only."""
    values: dict[str, set[str]] = {}

    def add(category: str, value: Any) -> None:
        if isinstance(value, str) and value.strip():
            values.setdefault(category, set()).add(value.strip())

    add("host", api.host)
    for device in await api.get_devices():
        for key in ("name", "mac", "serial", "ip"):
            add(f"device_{key}", device.get(key))
        for wan in ("wan1", "wan2"):
            record = device.get(wan) or {}
            if isinstance(record, dict):
                add("wan_ip", record.get("ip"))
                add("wan_mac", record.get("mac"))
        for info in (device.get("geo_info") or {}).values():
            if isinstance(info, dict):
                add("wan_ip", info.get("address"))
        for port in device.get("port_table") or []:
            add("port_name", port.get("name"))
    for wlan in await api.get_wlanconf():
        add("ssid", wlan.get("name"))
        add("wifi_key", wlan.get("x_passphrase"))
    for network in await api.get_networkconf():
        add("network_name", network.get("name"))
        add("subnet", network.get("ip_subnet"))
    for rogue in await api.get_rogueaps(24):
        add("rogue_ssid", rogue.get("essid"))
        add("rogue_bssid", rogue.get("bssid"))
    for subsystem in await api.get_health():
        add("isp_name", subsystem.get("isp_name"))
        add("isp_name", subsystem.get("isp_organization"))
    for info in await api.get_sysinfo():
        add("console_name", info.get("name"))
        add("console_name", info.get("hostname"))
    for site_record in await api.get_sites():
        site_id = site_record.get("id")
        if isinstance(site_id, str) and site_id:
            for wan in await api.get_wan_interfaces(site_id):
                add("wan_name", wan.get("name"))
    for client in await api.get_clients():
        for key in ("name", "hostname", "mac", "ip"):
            add(f"client_{key}", client.get(key))
    if site != "default":
        add("site_name", site)
    # A MAC may be published in another separator form; scan those too.
    for category in [c for c in values if c.endswith("_mac") or c == "rogue_bssid"]:
        for mac in list(values[category]):
            bare = re.sub(r"[^0-9a-fA-F]", "", mac)
            if len(bare) == 12:
                pairs = [bare[i : i + 2] for i in range(0, 12, 2)]
                values[category] |= {"-".join(pairs), bare}
    return values


_MAC_SHAPES = re.compile(
    r"(?<![0-9a-f])[0-9a-f]{2}(?:[:-][0-9a-f]{2}){5}(?![0-9a-f])"
    r"|(?<![0-9a-f])[0-9a-f]{4}\.[0-9a-f]{4}\.[0-9a-f]{4}(?![0-9a-f])",
    re.IGNORECASE,
)
_IPV6_SHAPE = re.compile(
    r"(?<![0-9a-f:])(?:[0-9a-f]{1,4}:){3,7}[0-9a-f]{1,4}(?![0-9a-f:])"
    r"|(?<![0-9a-f:])(?:[0-9a-f]{1,4}:)*[0-9a-f]{0,4}::(?:[0-9a-f]{1,4}:)*[0-9a-f]{1,4}(?![0-9a-f:])",
    re.IGNORECASE,
)


def shape_hits(download: dict[str, Any]) -> dict[str, list[str]]:
    """Return paths of MAC-shaped (any separator) and IPv6-shaped values."""
    found: dict[str, list[str]] = {}
    for path, text in leaves(download):
        if _MAC_SHAPES.search(text):
            found.setdefault("mac_shape", []).append(path)
        # A colon-form MAC also reads as IPv6 groups; it is reported above.
        if _IPV6_SHAPE.search(_MAC_SHAPES.sub("", text)):
            found.setdefault("ipv6_shape", []).append(path)
    return found


async def _download(session: Any, token: str) -> dict[str, Any]:
    """Take one diagnostics download from Home Assistant."""
    headers = {"Authorization": f"Bearer {token}"}
    async with session.get(
        f"{_HA}/api/config/config_entries/entry", headers=headers
    ) as resp:
        entries = await resp.json()
    entry_id = next(e["entry_id"] for e in entries if e["domain"] == DOMAIN)
    async with session.get(
        f"{_HA}/api/diagnostics/config_entry/{entry_id}", headers=headers
    ) as resp:
        resp.raise_for_status()
        body = await resp.json()
    data: dict[str, Any] = body.get("data") or {}
    return data


async def _main() -> int:
    import aiohttp

    options = _load_options()
    token = _TOKEN.read_text(encoding="utf-8").strip()
    api_key = (options.get("api_key") or "").strip() or None
    site = options.get("site", "default")
    async with aiohttp.ClientSession() as session:
        try:
            first = await _download(session, token)
            second = await _download(session, token)
        except (aiohttp.ClientError, OSError) as err:
            print(f"Home Assistant did not answer the download: {type(err).__name__}")
            print(_red("\n✖  Diagnostics check: FAILED  (no download)"))
            return 1
        api = UnifiNetworkAPI(
            session,
            options.get("host", ""),
            api_key=api_key,
            username=(options.get("username") or "").strip() or None,
            password=(options.get("password") or "").strip() or None,
            site=site,
        )
        try:
            if api.username and api.password and not api.api_key:
                await api.login()
            secrets = await _controller_values(api, site)
        except UnifiError as err:
            print(_red(f"router stopped answering: {type(err).__name__}"))
            print(_red("\n✖  Diagnostics check: FAILED  (controller unreachable)"))
            return 1
        finally:
            await api.logout()

    drift = structure_drift(first, second)
    problems = block_problems(first, api_key is not None)
    hits: dict[str, list[str]] = {}
    for download in (first, second):
        for source in (leak_hits(download, secrets), shape_hits(download)):
            for category, found in source.items():
                hits.setdefault(category, []).extend(found)

    print(f"Downloads: 2; structure paths compared: {len(paths(first))}")
    print(f"Structure drift outside the volatile set: {len(drift)}")
    for path in drift:
        print(f"  drift: {path}")
    print(f"Block problems: {len(problems)}")
    for problem in problems:
        print(f"  block: {problem}")
    scanned = sum(len(v) for v in secrets.values())
    print(f"Leak scan: {scanned} controller values in {len(secrets)} categories")
    for category, found in sorted(hits.items()):
        print(f"  leak: {category} at {sorted(set(found))}")
    failed = bool(drift or problems or hits)
    if failed:
        print(_red("\n✖  Diagnostics check: FAILED"))
        return 1
    print(_green("\n✔  Diagnostics check: PASSED"))
    return 0


def main() -> int:
    """Parse arguments and run the check."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sabotage",
        action="store_true",
        help="Session-loss recovery check; not applicable to this integration.",
    )
    args = parser.parse_args()
    if args.sabotage:
        print(
            "Diagnostics recovery check: not applicable. An API-key install holds "
            "no session to take away, and recovery from a lost password-mode "
            "session is unmeasured (docs/DEVELOPMENT.md)."
        )
        return 0
    return asyncio.run(_main())


if __name__ == "__main__":
    raise SystemExit(main())
