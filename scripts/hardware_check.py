"""Exercise the SAFE write path against a real UniFi gateway.

Not part of CI, and not a unit test. It exists because a `SAFE` classification in
`scripts/write_classification.py` is a **promise that something actually runs the
command** — the register's whole point is that the two worst control defects in
this family shipped broken for weeks purely because nobody pressed the button.
`tests/test_write_classification.py` fails if a `SAFE` write is not exercised
here, so this file is what makes that classification honest rather than
aspirational.

Deliberately small. UniFi has exactly two device writes:

  * **`trigger_speedtest`** — `SAFE`, and the only thing this script runs. It
    starts a measurement and changes no configuration, so there is nothing to
    strand if the run dies partway.
  * **`update_networkconf`** — `ATTENDED`, and **not offered here at all.** It
    changes which link the household's traffic uses, and a script cannot judge
    whether that recovered. Restoring it is a person's job, so it is not behind a
    prompt in this file; it is simply absent.

The check confirms the command is accepted **and then waits for the result to
land**, because "the controller took the request" and "the gateway ran a
speedtest" are different claims and only the second one is worth asserting. A
speedtest that is accepted and silently never runs is precisely the failure shape
the register was written for.

Usage, inside the devcontainer, from anywhere — paths resolve from ``__file__``:

    /usr/local/bin/python scripts/hardware_check.py
    /usr/local/bin/python scripts/hardware_check.py --interface wan2
    /usr/local/bin/python scripts/hardware_check.py --timeout 180

**Use the container interpreter, not `uv run`.** This imports the integration,
which imports Home Assistant; only ``/usr/local/bin/python`` has those installed.

Credentials are read from the config entry in ``.storage/core.config_entries`` —
the same place the integration reads them — so there is nothing to pass on the
command line and no secret in shell history.
"""

# ruff: noqa: T201 - an operator script's output *is* its interface; printing is
# the point, and routing it through a logger would hide it behind log levels.

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT))

from custom_components.unifi_network_monitor.api import (  # noqa: E402
    UnifiError,
    UnifiNetworkAPI,
)
from custom_components.unifi_network_monitor.const import DOMAIN  # noqa: E402

_STORAGE = _PROJECT / "config" / ".storage" / "core.config_entries"


def _load_options() -> dict[str, Any]:
    """Read this integration's options out of the HA config-entry store.

    Reading the store rather than taking arguments keeps credentials out of shell
    history, and guarantees the script authenticates exactly as the integration
    does — a check that logs in differently is not checking the same thing.
    """
    if not _STORAGE.is_file():
        raise SystemExit(
            f"No config-entry store at {_STORAGE}. Start Home Assistant and set "
            "the integration up before running the hardware check."
        )
    store = json.loads(_STORAGE.read_text(encoding="utf-8"))
    for entry in store.get("data", {}).get("entries", []):
        if entry.get("domain") == DOMAIN:
            options: dict[str, Any] = dict(entry.get("options") or {})
            return options
    raise SystemExit(f"No {DOMAIN} config entry found in {_STORAGE}.")


def _latest_run(results: list[dict[str, Any]]) -> tuple[int, dict[str, Any] | None]:
    """Return the newest speedtest record's timestamp and the record itself."""
    if not results:
        return 0, None
    newest = max(results, key=lambda r: r.get("time") or 0)
    return int(newest.get("time") or 0), newest


async def _check_speedtest(api: UnifiNetworkAPI, interface: str, timeout: int) -> bool:
    """Run the SAFE write and confirm a *new* result actually appears."""
    print("[A] trigger_speedtest  (SAFE)")

    before_ts, _ = _latest_run(await api.get_speedtest_results())
    print(f"    newest result before: {before_ts or 'none'}")

    try:
        await api.trigger_speedtest(interface)
    except UnifiError as err:
        print(f"    FAIL  command refused: {err}")
        return False
    print(f"    command accepted for {interface}")

    # Accepted is not done. Poll until a strictly newer record appears — a
    # gateway that accepts the command and never runs it is the exact failure
    # this register exists to catch, and it looks like success from the reply
    # alone.
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        await asyncio.sleep(5)
        after_ts, record = _latest_run(await api.get_speedtest_results())
        if after_ts > before_ts:
            when = datetime.fromtimestamp(after_ts / 1000.0, tz=UTC)
            down = record.get("download_mbps") if record else None
            up = record.get("upload_mbps") if record else None
            print(f"    PASS  new result at {when.isoformat()} — {down}/{up} Mbps")
            return True
        print("    …waiting for the run to complete")

    print(
        f"    FAIL  accepted but no new result within {timeout}s. The command was "
        "taken and nothing ran — do not read the acceptance as success."
    )
    return False


async def _main(interface: str, timeout: int) -> int:
    import aiohttp

    options = _load_options()
    async with aiohttp.ClientSession() as session:
        api = UnifiNetworkAPI(
            session,
            options.get("host", ""),
            api_key=(options.get("api_key") or "").strip() or None,
            username=(options.get("username") or "").strip() or None,
            password=(options.get("password") or "").strip() or None,
            site=options.get("site", "default"),
        )
        if api.username and api.password and not api.api_key:
            await api.login()
        try:
            ok = await _check_speedtest(api, interface, timeout)
        finally:
            await api.logout()

    print()
    print("SAFE writes exercised: 1 of 1" if ok else "SAFE writes exercised: 0 of 1")
    print(
        "update_networkconf is ATTENDED and is deliberately not offered here — "
        "changing the WAN weights is a person's decision to make and undo."
    )
    return 0 if ok else 1


def main() -> int:
    """Parse arguments and run the check."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--interface",
        default="wan1",
        help="WAN interface to test (default: wan1).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Seconds to wait for a new result before failing (default: 120).",
    )
    args = parser.parse_args()
    return asyncio.run(_main(args.interface, args.timeout))


if __name__ == "__main__":
    raise SystemExit(main())
