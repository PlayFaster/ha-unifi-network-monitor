"""The reauth screen must explain what a blank field does.

**item 8** of the August 2026 plan (§M Phase 1), from ``dev_std_review`` F-1.
Reconfigure and Options both carry "Leave blank to keep the current…".
``reauth_confirm`` carried no ``data_description`` block at all — and reauth is
the one screen where a blank submit re-tries the credential that just failed and
loops the user straight back with no explanation of why.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_COMPONENT = (
    Path(__file__).parent.parent / "custom_components" / "unifi_network_monitor"
)


def _load(name: str) -> dict[str, Any]:
    path = _COMPONENT / name
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def _reauth_step(name: str) -> dict[str, Any]:
    step: dict[str, Any] = _load(name)["config"]["step"]["reauth_confirm"]
    return step


def test_reauth_has_data_description_in_both_files() -> None:
    """Both translation files describe the reauth fields."""
    for name in ("strings.json", "translations/en.json"):
        assert "data_description" in _reauth_step(name), name


def test_reauth_describes_every_secret_field() -> None:
    """Each credential field the reauth form offers is described.

    These are the fields where a blank submit is silently meaningful, so they
    are the ones that must say what blank does.
    """
    for name in ("strings.json", "translations/en.json"):
        step = _reauth_step(name)
        described = step["data_description"]
        for field in ("api_key", "password"):
            assert field in described, f"{name}: {field}"
            assert described[field].strip(), f"{name}: {field} is empty"


def test_reauth_warns_that_blank_retries_the_rejected_credential() -> None:
    """The text must not simply copy reconfigure's reassuring wording.

    On reconfigure, "leave blank to keep the current value" is a convenience.
    On reauth the current value is the one the controller just rejected, so the
    same sentence without a warning sends the user round the loop again.
    """
    for name in ("strings.json", "translations/en.json"):
        step = _reauth_step(name)
        for field in ("api_key", "password"):
            text = step["data_description"][field].lower()
            assert "reject" in text or "fail" in text, f"{name}: {field}"


def test_strings_and_en_json_stay_identical() -> None:
    """The two files are maintained as copies — a change to one is a change to both."""
    assert _load("strings.json") == _load("translations/en.json")
