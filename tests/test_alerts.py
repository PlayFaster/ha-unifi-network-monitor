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
    """Title with substituted params is truncated correctly."""
    event = {
        "title_raw": "Alert on {device}" + "X" * 260,
        "parameters": {"device": {"name": "UDM-Pro"}},
    }
    result = alert_title(event)
    assert len(result) == 255
    assert result.endswith("…")


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
