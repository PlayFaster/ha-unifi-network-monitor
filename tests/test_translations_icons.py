"""Translation and icon reconciliation — dev_standards Section 12.

**item 16** of the August 2026 plan (§M Phase 2). Reconciled against **code**,
not file-to-file. Comparing ``strings.json`` with ``icons.json`` proves only
that two hand-maintained files agree with each other; both can agree perfectly
and still describe an entity that no longer exists, or miss one that does.

Three directions, because each fails differently and silently:

1. **code → strings** — an entity with no name entry renders as its raw
   ``translation_key``, which looks like a bug report waiting to happen;
2. **code → icons** — a missing icon falls back to a domain default, which
   looks deliberate;
3. **strings/icons → code** — a dead entry costs nothing at runtime and so is
   never noticed, and it quietly makes every count in the documentation wrong.

`dev_std_review` F-15 records the ``**Test:**`` tag for this section as wholly
unmet. This is that test.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_COMPONENT = (
    Path(__file__).parent.parent / "custom_components" / "unifi_network_monitor"
)


def _load(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((_COMPONENT / name).read_text(encoding="utf-8"))
    return data


_STRINGS = _load("strings.json")
_ICONS = _load("icons.json")
_EN = _load("translations/en.json")


_PLATFORM_MODULES = (
    "sensor",
    "binary_sensor",
    "button",
    "number",
    "switch",
    "select",
)

# Both spellings a platform module can use. Description-driven entities carry
# ``translation_key=`` inside a description; single-instance entities set
# ``_attr_translation_key`` on the class. Enumerating the description tuples
# instead would report every single-instance entity as a dead entry — the false
# positive that gets a reconciliation test deleted rather than fixed.
_KEY_PATTERN = re.compile(
    r"""(?:translation_key\s*=\s*|_attr_translation_key\s*=\s*)["']([a-z0-9_]+)["']"""
)


def _description_keys() -> dict[str, set[str]]:
    """Collect the translation keys each platform module actually declares.

    Read from the **module source**, which is where a key is spelled, so the
    set here is the set the runtime will ask the translation files for.
    """
    keys: dict[str, set[str]] = {}
    for platform in _PLATFORM_MODULES:
        source = (_COMPONENT / f"{platform}.py").read_text(encoding="utf-8")
        # `translation_key=` is also how a raised HomeAssistantError names its
        # message, and those resolve under `exceptions`, not `entity`. They are
        # partitioned out here and checked by their own test below, so neither
        # kind can go missing.
        found = set(_KEY_PATTERN.findall(source)) - _exception_keys()
        if found:
            keys[platform] = found
    return keys


def _exception_keys() -> set[str]:
    """Collect the keys that name an exception message rather than an entity."""
    return set(_STRINGS.get("exceptions", {}))


def _raised_exception_keys() -> set[str]:
    """Collect the exception translation keys the code actually raises."""
    raised: set[str] = set()
    for module in (*_PLATFORM_MODULES, "coordinator", "services", "__init__"):
        source = (_COMPONENT / f"{module}.py").read_text(encoding="utf-8")
        raised |= set(_KEY_PATTERN.findall(source)) & _exception_keys()
    return raised


# ---------------------------------------------------------------------------
# Direction 1 — every declared key has a name
# ---------------------------------------------------------------------------


def test_every_declared_translation_key_has_a_name() -> None:
    """An entity with no name entry renders its raw ``translation_key``."""
    offenders: list[str] = []
    for platform, keys in _description_keys().items():
        declared = _STRINGS["entity"].get(platform, {})
        offenders += [
            f"{platform}.{key}"
            for key in sorted(keys)
            if key not in declared or not declared[key].get("name")
        ]
    assert not offenders, "translation keys with no name:\n" + "\n".join(offenders)


# ---------------------------------------------------------------------------
# Direction 2 — every declared key has an icon or a device class
# ---------------------------------------------------------------------------


def test_every_declared_key_has_an_icon() -> None:
    """A missing icon falls back to a domain default and looks deliberate."""
    offenders: list[str] = []
    for platform, keys in _description_keys().items():
        icons = _ICONS["entity"].get(platform, {})
        offenders += [f"{platform}.{key}" for key in sorted(keys) if key not in icons]
    assert not offenders, "keys with neither an icon nor a device_class:\n" + "\n".join(
        offenders
    )


# ---------------------------------------------------------------------------
# Direction 3 — no entry describes something the code does not declare
# ---------------------------------------------------------------------------


def test_no_dead_translation_entries() -> None:
    """An entry for an entity that no longer exists is invisible at runtime."""
    declared = _description_keys()
    offenders = [
        f"strings.json entity.{platform}.{key}"
        for platform, keys in declared.items()
        for key in sorted(_STRINGS["entity"].get(platform, {}))
        if key not in keys
    ]
    assert not offenders, "translation entries with no entity:\n" + "\n".join(offenders)


def test_no_dead_icon_entries() -> None:
    """Same for icons — a dead icon entry makes every published count wrong."""
    declared = _description_keys()
    offenders = [
        f"icons.json entity.{platform}.{key}"
        for platform, keys in declared.items()
        for key in sorted(_ICONS["entity"].get(platform, {}))
        if key not in keys
    ]
    assert not offenders, "icon entries with no entity:\n" + "\n".join(offenders)


def test_no_key_is_filed_under_the_wrong_platform() -> None:
    """A sensor key listed under ``binary_sensor`` resolves for neither.

    File-to-file comparison cannot see this: both files can carry the same
    misfiling and agree perfectly.
    """
    declared = _description_keys()
    for platform, keys in declared.items():
        others = set().union(*(v for k, v in declared.items() if k != platform))
        misfiled = {
            k for k in _STRINGS["entity"].get(platform, {}) if k in others - keys
        }
        assert not misfiled, f"{platform} carries keys belonging elsewhere: {misfiled}"


# ---------------------------------------------------------------------------
# Actions, and the two files staying in step
# ---------------------------------------------------------------------------


def test_every_action_has_a_name_and_an_icon() -> None:
    """Actions reconcile in both directions too."""
    named = set(_STRINGS["services"])
    iconed = set(_ICONS["services"])
    assert named == iconed, (
        f"actions named but not iconed: {named - iconed}; "
        f"iconed but not named: {iconed - named}"
    )


def test_strings_and_en_json_are_identical() -> None:
    """The two are maintained as copies, so a change to one is a change to both."""
    assert _STRINGS == _EN


def test_reconciliation_is_not_vacuous() -> None:
    """Guard the guard: empty description tuples would pass every check above."""
    declared = _description_keys()
    assert len(declared["sensor"]) >= 100, len(declared["sensor"])
    assert len(declared["binary_sensor"]) >= 15, len(declared["binary_sensor"])


def test_every_raised_exception_key_has_a_message() -> None:
    """An exception whose key has no entry surfaces its raw key to the user."""
    missing = _raised_exception_keys() - _exception_keys()
    assert not missing, f"raised exception keys with no message: {missing}"


def test_no_dead_exception_messages() -> None:
    """A message for an exception nothing raises is dead weight nobody sees."""
    dead = _exception_keys() - _raised_exception_keys()
    assert not dead, f"exception messages never raised: {dead}"
