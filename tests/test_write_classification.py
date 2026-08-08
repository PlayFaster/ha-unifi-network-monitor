"""Every write must be classified, and every SAFE write must be exercised.

Phase 3 item 23 of the August 2026 plan (§M), from shared `dev_standards.md` §22.

This file guards a gap that is not a coding error. In this family, a data-limit
switch shipped broken in every release for weeks and a status LED was erratic for
just as long. Neither was subtle — both failed on the first attempt. They survived
because **nobody used those entities**, so nobody tried.

No behavioural test catches that, because the missing thing is not an assertion,
it is the decision to look. What this file enforces is that decision: adding a
command to `api.py` without recording whether a script may exercise it fails the
suite.

Deliberately **not** a behavioural test. It never touches a gateway and proves
nothing about whether any write works. It proves only that none was added in
silence.
"""

from __future__ import annotations

import ast
import pathlib

from scripts.write_classification import (
    ATTENDED,
    EXERCISED_BY_HARDWARE_CHECK,
    NEVER_AUTOMATED,
    SAFE,
    classification,
)

_API = pathlib.Path("custom_components/unifi_network_monitor/api.py")
_HARDWARE_CHECK = pathlib.Path("scripts/hardware_check.py")

# Endpoints that change something on the controller or the gateway. Keyed on the
# **endpoint**, not the HTTP verb — the UniFi controller answers queries with
# POST, so `get_daily_gateway`, `get_monthly_gateway`, `get_rogueaps`,
# `get_backups` and `get_system_logs` are all POSTs and all reads. A verb-based
# detector would report five reads as writes and produce a register nobody reads.
_WRITE_ENDPOINT_FRAGMENTS = (
    "cmd/devmgr",
    "rest/networkconf/",
)

# `login` and `logout` are excluded: they establish and end the session that every
# other call needs, they change nothing on the device, and they are exercised by
# every check rather than needing one of their own.
_NOT_A_DEVICE_WRITE = frozenset({"login", "logout"})


def _api_methods() -> dict[str, ast.AsyncFunctionDef]:
    """Return every public async method on the API class, by name."""
    tree = ast.parse(_API.read_text(encoding="utf-8"))
    api_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "UnifiNetworkAPI"
    )
    return {
        node.name: node
        for node in api_class.body
        if isinstance(node, ast.AsyncFunctionDef) and not node.name.startswith("_")
    }


def _public_writes() -> set[str]:
    """Return every public API method that commands the controller or gateway.

    Detected by the endpoint string each method passes to the transport, which is
    the only reliable signal here: the verb says nothing, and a method name is a
    convention a future author need not follow.
    """
    writes: set[str] = set()
    for name, node in _api_methods().items():
        if name in _NOT_A_DEVICE_WRITE:
            continue
        for sub in ast.walk(node):
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                if any(f in sub.value for f in _WRITE_ENDPOINT_FRAGMENTS):
                    writes.add(name)
    return writes


def test_every_write_is_classified() -> None:
    """A new command in `api.py` fails the suite until someone classifies it.

    This is the whole mechanism. It does not ask whether the write works; it asks
    whether anyone decided how it could be checked.
    """
    unclassified = sorted(
        name for name in _public_writes() if classification(name) is None
    )
    assert not unclassified, (
        "writes with no entry in scripts/write_classification.py — add each to "
        "SAFE, ATTENDED or NEVER_AUTOMATED with a written reason:\n"
        + "\n".join(unclassified)
    )


def test_the_write_detector_actually_finds_the_known_writes() -> None:
    """Guard the guard: a detector that finds nothing passes every test above.

    Pinned by name rather than by count, because a detector that silently started
    matching reads would keep the count plausible while making the register
    meaningless.
    """
    assert _public_writes() == {"trigger_speedtest", "update_networkconf"}


def test_the_detector_does_not_mistake_a_post_query_for_a_write() -> None:
    """UniFi answers queries with POST. Five reads must not be classified.

    The trap runs the opposite way here to the one §22 warns about, and getting
    it wrong produces a register that is mostly noise — which is how a register
    stops being read at all.
    """
    post_queries = {
        "get_daily_gateway",
        "get_monthly_gateway",
        "get_rogueaps",
        "get_backups",
        "get_system_logs",
    }
    methods = set(_api_methods())
    assert post_queries <= methods, (
        f"expected read methods are gone: {post_queries - methods}"
    )
    assert not post_queries & _public_writes()


def test_every_safe_write_is_exercised_by_the_hardware_check() -> None:
    """SAFE is a promise that something runs the command, not that it would be fine.

    Without this, `SAFE` becomes a way of marking a write as untested and moving
    on — which is exactly how the two broken controls survived.
    """
    unexercised = sorted(set(SAFE) - EXERCISED_BY_HARDWARE_CHECK)
    assert not unexercised, (
        "writes classified SAFE but not exercised by scripts/hardware_check.py — "
        "either exercise them or reclassify them ATTENDED:\n" + "\n".join(unexercised)
    )


def test_the_hardware_check_really_calls_every_write_it_claims() -> None:
    """The claim in `EXERCISED_BY_HARDWARE_CHECK` is checked against the source.

    A set literal is easy to keep and easy to make false. This reads the script.
    """
    source = _HARDWARE_CHECK.read_text(encoding="utf-8")
    missing = sorted(
        name for name in EXERCISED_BY_HARDWARE_CHECK if f"api.{name}(" not in source
    )
    assert not missing, (
        "claimed as exercised but never called in scripts/hardware_check.py:\n"
        + "\n".join(missing)
    )


def test_the_hardware_check_never_calls_an_attended_write() -> None:
    """An ATTENDED write must not be reachable from the unattended script.

    ATTENDED means a person judges the outcome. A script that quietly issues one
    has converted a considered classification into a comment.
    """
    source = _HARDWARE_CHECK.read_text(encoding="utf-8")
    offenders = sorted(name for name in ATTENDED if f"api.{name}(" in source)
    assert not offenders, (
        "ATTENDED writes called by the unattended hardware check:\n"
        + "\n".join(offenders)
    )


def test_no_write_is_registered_in_two_tiers() -> None:
    """A write in two tiers has two different answers to the same question."""
    assert not set(SAFE) & set(ATTENDED)
    assert not set(SAFE) & set(NEVER_AUTOMATED)
    assert not set(ATTENDED) & set(NEVER_AUTOMATED)


def test_the_register_has_no_stale_entries() -> None:
    """An entry for a command that no longer exists must be removed.

    Otherwise the register rots: a write is renamed, the old entry keeps reading
    as a considered decision, and the new name is unclassified but invisible
    because the count still looks right.
    """
    known = _public_writes()
    stale = sorted((set(SAFE) | set(ATTENDED) | set(NEVER_AUTOMATED)) - known)
    assert not stale, (
        "register names commands that no longer exist in api.py:\n" + "\n".join(stale)
    )


def test_every_entry_carries_a_written_reason() -> None:
    """A tier without a reason is a label. The reason is the reviewable part."""
    for tier_name, register in (
        ("SAFE", SAFE),
        ("ATTENDED", ATTENDED),
        ("NEVER_AUTOMATED", NEVER_AUTOMATED),
    ):
        for name, reason in register.items():
            assert len(reason.strip()) > 40, f"{tier_name}[{name}] has no real reason"
