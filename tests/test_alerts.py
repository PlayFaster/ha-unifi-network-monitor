"""Tests for alert helpers."""

from custom_components.unifi_network_monitor.alerts import (
    build_alert_attrs,
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
