"""Tests for alert helpers."""

from custom_components.unifi_network_monitor.alerts import (
    alert_title,
    build_alert_attrs,
    build_alert_response,
    build_event_payload,
    format_message,
)


def test_format_message_dict_param() -> None:
    """Dict parameter is substituted by its 'name' key."""
    result = format_message("Device {device}", {"device": {"name": "UDM-Pro"}})
    assert result == "Device UDM-Pro"


def test_format_message_dict_param_id_fallback() -> None:
    """Dict parameter without 'name' falls back to 'id'."""
    result = format_message("Device {device}", {"device": {"id": "DEV-001"}})
    assert result == "Device DEV-001"


def test_format_message_scalar_param() -> None:
    """Scalar parameter is substituted directly."""
    result = format_message("Port {port}", {"port": "eth8"})
    assert result == "Port eth8"


def test_format_message_missing_param() -> None:
    """Unmatched placeholder is left as-is."""
    result = format_message("Duration: {duration}s", {"other": "val"})
    assert result == "Duration: {duration}s"


def test_format_message_empty_raw() -> None:
    """Empty raw string returns empty string."""
    assert format_message("", {"k": "v"}) == ""


def test_format_message_none_raw() -> None:
    """None raw string returns empty string."""
    assert format_message(None, {"k": "v"}) == ""  # type: ignore[arg-type]


def test_format_message_empty_params() -> None:
    """Empty parameters dict makes no substitutions."""
    result = format_message("Hello {name}", {})
    assert result == "Hello {name}"


def test_format_message_none_params() -> None:
    """None parameters are treated as empty."""
    result = format_message("Hello {name}", None)  # type: ignore[arg-type]
    assert result == "Hello {name}"


def test_build_alert_attrs_full_event() -> None:
    """Full event produces all expected attributes."""
    event = {
        "message_raw": "High CPU on {device}",
        "title_raw": "CPU Alert",
        "parameters": {"device": {"name": "UDM-Pro"}},
        "event": "cpu_high",
        "category": "system",
        "subcategory": "hardware",
        "severity": "HIGH",
        "status": "active",
        "timestamp": 1700000000000,
    }
    attrs = build_alert_attrs(event)
    assert attrs["message"] == "High CPU on UDM-Pro"
    assert attrs["title"] == "CPU Alert"
    assert attrs["event"] == "cpu_high"
    assert attrs["category"] == "system"
    assert attrs["subcategory"] == "hardware"
    assert attrs["severity"] == "HIGH"
    assert attrs["status"] == "active"
    assert attrs["timestamp"] is not None
    assert attrs["parameters"] == {"device": {"name": "UDM-Pro"}}


def test_build_alert_attrs_no_timestamp() -> None:
    """Event without timestamp yields None timestamp."""
    event = {
        "message_raw": "Alert",
        "title_raw": "",
        "severity": "LOW",
    }
    attrs = build_alert_attrs(event)
    assert attrs["timestamp"] is None
    assert attrs["message"] == "Alert"


def test_build_alert_attrs_empty_event() -> None:
    """Empty event produces defaults without errors."""
    attrs = build_alert_attrs({})
    assert attrs["message"] == ""
    assert attrs["title"] == ""
    assert attrs["event"] is None
    assert attrs["timestamp"] is None
    assert attrs["parameters"] == {}


# ---------------------------------------------------------------------------
# alert_title
# ---------------------------------------------------------------------------


def test_alert_title_no_truncation() -> None:
    """Short title is returned as-is."""
    result = alert_title({"title_raw": "CPU Alert", "parameters": {}})
    assert result == "CPU Alert"


def test_alert_title_truncated() -> None:
    """Title longer than ALERT_TITLE_MAX is truncated with ellipsis."""
    long_title = "A" * 260
    event = {"title_raw": long_title, "parameters": {}}
    result = alert_title(event)
    assert len(result) == 255
    assert result.endswith("…")


def test_alert_title_empty() -> None:
    """Empty title_raw returns empty string."""
    result = alert_title({})
    assert result == ""


def test_alert_title_with_params() -> None:
    """A long title with params is truncated; substitution is checked separately.

    The substitution assertions that this test's name implied now live in
    ``test_alert_title_substitutes_a_parameter``. They could never have worked
    here: the title is deliberately long enough to truncate, so the substituted
    text is cut off before the assertions can see it.
    """
    event = {
        "title_raw": "Alert on {device}" + "X" * 260,
        "parameters": {"device": {"name": "UDM-Pro"}},
    }
    result = alert_title(event)
    assert len(result) == 255
    assert result.endswith("…")


def test_alert_title_substitutes_a_parameter() -> None:
    """The title actually has its placeholder replaced.

    Covers finding ASSERT.1 from recommendations_20260808.md. The title is kept
    short on purpose - the previous test used a 277-character title, so the
    substituted value was truncated away and asserting on the length proved
    nothing about substitution. Six surviving mutants dropped the parameters
    dict in one way or another and every one passed the old assertions.
    """
    event = {
        "title_raw": "Alert on {device}",
        "parameters": {"device": {"name": "UDM-Pro"}},
    }

    assert alert_title(event) == "Alert on UDM-Pro"


def test_alert_title_falls_back_to_the_parameter_id() -> None:
    """A parameter carrying only an ``id`` substitutes the id.

    Covers finding ASSERT.1 from recommendations_20260808.md - the documented
    name-then-id fallback, exercised through ``alert_title`` rather than only
    through ``format_message``.
    """
    event = {
        "title_raw": "Alert on {device}",
        "parameters": {"device": {"id": "abc123"}},
    }

    assert alert_title(event) == "Alert on abc123"


def test_alert_title_leaves_an_unmatched_placeholder_alone() -> None:
    """With no parameters the placeholder survives verbatim.

    Covers finding ASSERT.1 from recommendations_20260808.md. This is the
    documented behaviour of ``format_message``, and it is what distinguishes a
    dropped parameters dict from a correctly substituted one.
    """
    event: dict[str, object] = {"title_raw": "Alert on {device}", "parameters": {}}

    assert alert_title(event) == "Alert on {device}"


def test_alert_title_of_exactly_the_maximum_length_is_not_truncated() -> None:
    """A title at exactly ALERT_TITLE_MAX is returned whole.

    Covers finding BVA.1 from recommendations_20260808.md. The guard is
    ``len(title) > ALERT_TITLE_MAX``; relaxing it to ``>=`` survived mutation
    because the only tests used 9 and 260 characters. Asserting the *length*
    cannot catch it either - under the mutant a 255-character title becomes
    254 characters plus an ellipsis, which is still 255 long. Only equality
    with the input distinguishes the two.
    """
    title = "A" * 255
    result = alert_title({"title_raw": title, "parameters": {}})

    assert result == title
    assert not result.endswith("…")


def test_alert_title_one_over_the_maximum_is_truncated_at_the_boundary() -> None:
    """A title one character too long loses exactly one character to the ellipsis.

    Covers finding BVA.1 from recommendations_20260808.md - the other side of
    the boundary, pinning where the cut falls rather than only that one happened.
    """
    result = alert_title({"title_raw": "A" * 256, "parameters": {}})

    assert len(result) == 255
    assert result == "A" * 254 + "…"


# ---------------------------------------------------------------------------
# build_alert_response
# ---------------------------------------------------------------------------


def test_build_alert_response_full() -> None:
    """Full event produces all expected response fields."""
    event = {
        "id": "evt_001",
        "message_raw": "High CPU on {device}",
        "title_raw": "CPU Alert",
        "parameters": {"device": {"name": "UDM-Pro"}},
        "event": "cpu_high",
        "category": "system",
        "subcategory": "hardware",
        "severity": "HIGH",
        "status": "active",
        "timestamp": 1700000000000,
    }
    resp = build_alert_response(event)
    assert resp["id"] == "evt_001"
    assert resp["title"] == "CPU Alert"
    assert resp["message"] == "High CPU on UDM-Pro"
    assert resp["event"] == "cpu_high"
    assert resp["severity"] == "HIGH"
    assert resp["timestamp"] is not None


def test_build_alert_response_no_timestamp() -> None:
    """Event without timestamp yields None timestamp."""
    resp = build_alert_response({"title_raw": "Test", "severity": "LOW"})
    assert resp["timestamp"] is None
    assert resp["title"] == "Test"


def test_build_alert_response_empty() -> None:
    """Empty event produces defaults without errors."""
    resp = build_alert_response({})
    assert resp["id"] is None
    assert resp["title"] == ""
    assert resp["message"] == ""
    assert resp["timestamp"] is None
    assert resp["severity"] is None
    assert resp["status"] is None


# ---------------------------------------------------------------------------
# build_event_payload
# ---------------------------------------------------------------------------


def test_build_event_payload_full() -> None:
    """Full event produces all expected bus event payload fields."""
    payload = build_event_payload(
        "entry_001",
        {
            "id": "evt_001",
            "message_raw": "Critical on {device}",
            "title_raw": "Critical Alert",
            "parameters": {"device": {"name": "UDM-Pro"}},
            "event": "critical_error",
            "category": "system",
            "severity": "VERY_HIGH",
            "status": "active",
            "timestamp": 1700000000000,
        },
    )
    assert payload["entry_id"] == "entry_001"
    assert payload["id"] == "evt_001"
    assert payload["title"] == "Critical Alert"
    assert payload["message"] == "Critical on UDM-Pro"
    assert payload["severity"] == "VERY_HIGH"
    assert payload["timestamp"] is not None


def test_build_event_payload_no_timestamp() -> None:
    """Event without timestamp yields None timestamp."""
    payload = build_event_payload("entry_001", {"title_raw": "Test"})
    assert payload["timestamp"] is None


def test_build_event_payload_empty() -> None:
    """Empty event produces defaults without errors."""
    payload = build_event_payload("entry_001", {})
    assert payload["entry_id"] == "entry_001"
    assert payload["id"] is None
    assert payload["title"] == ""
    assert payload["message"] == ""
    assert payload["severity"] is None
    assert payload["timestamp"] is None
    assert payload["status"] is None
