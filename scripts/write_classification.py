"""Every command this integration can send, and whether a script may send it.

Source: shared `dev_standards.md` §22, added at standard version 1.18.0. Not
invented here.

**Why it exists.** The two worst control defects in this family were a data-limit
switch that had never worked in any release and a status LED that failed on the
first attempt. Both survived for weeks. Neither was a subtle bug — and neither
was a testing failure in the usual sense, because **the owner did not personally
use those entities, so nobody ever tried them.** No behavioural test catches
that: what is missing is not an assertion but the decision to look. This register
converts "someone should check" into a list with a test behind it.

The guarantee is therefore *not* "these writes are tested". It is **"no write can
be added without someone deciding, in writing, whether it can be exercised"**.
`tests/test_write_classification.py` fails on an unclassified write, and fails
again if something classified `SAFE` is not actually exercised by
`scripts/hardware_check.py`.

### The three tiers

``SAFE``
    Fine to run unattended. Reversible, no service interruption, no cost, and no
    reach into anyone else's property — and, because a crash can strand the
    script mid-run, **either resting state must be harmless**.

``ATTENDED``
    A human confirms each step. Recoverable, but a script cannot judge whether it
    recovered.

``NEVER_AUTOMATED``
    Must never be issued by a script under any flag. **Currently empty, and
    deliberately kept defined** so the decision point exists for a future command
    that warrants it.

### The UniFi-specific trap, which runs backwards

§22 warns that finding writes by searching for the protocol verb misses commands
that delegate to another method. **Here the danger is the opposite.** The UniFi
controller uses `POST` for *queries*: `get_daily_gateway`, `get_monthly_gateway`,
`get_rogueaps`, `get_backups` and `get_system_logs` are all POSTs and all reads.
A verb-based detector would classify five reads as writes and produce a register
that is mostly noise, which is how a register stops being read. **Key on the
endpoint, not the verb** — see `_public_writes()` in the test.
"""

from __future__ import annotations

# --- Fine to run unattended -------------------------------------------------
SAFE: dict[str, str] = {
    "trigger_speedtest": (
        "Reversible by construction — it starts a measurement and changes no "
        "configuration, so there is no state to strand if the script dies "
        "mid-run. It saturates the WAN for roughly a minute, which is the one "
        "argument against SAFE; it is outweighed by the fact that the README "
        "ships a *Scheduled Speedtests* automation, so users already run this "
        "unattended on a timer. Calling it ATTENDED while shipping an "
        "automation that schedules it would be a register that disagrees with "
        "the product."
    ),
}

# --- A human confirms each step ---------------------------------------------
ATTENDED: dict[str, str] = {
    "update_networkconf": (
        "Changes routing. The WAN load-balance weights are written as a pair "
        "and the pair must sum to 100, so a run interrupted between the two "
        "PUTs leaves the gateway splitting traffic in a ratio nobody chose. "
        "The coordinator shields the pair against cancellation "
        "(`[1.0.1-dev12]`), but shielding is not the same as a script being "
        "able to judge the outcome — and the outcome here is which link the "
        "household's traffic uses. A person confirms, and a person restores."
    ),
}

# --- Must never be scripted at all ------------------------------------------
NEVER_AUTOMATED: dict[str, str] = {}

# Writes that `scripts/hardware_check.py` actually exercises. A SAFE entry
# missing from this set fails the test: SAFE is a promise that something runs the
# command, not merely that it would be acceptable to.
EXERCISED_BY_HARDWARE_CHECK: frozenset[str] = frozenset({"trigger_speedtest"})


def classification(name: str) -> str | None:
    """Return the tier ``name`` is registered in, or None if it is unclassified."""
    for tier, register in (
        ("SAFE", SAFE),
        ("ATTENDED", ATTENDED),
        ("NEVER_AUTOMATED", NEVER_AUTOMATED),
    ):
        if name in register:
            return tier
    return None
