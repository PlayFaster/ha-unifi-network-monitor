"""Helpers for UniFi system-log alert entities.

Kept in its own module so both the coordinator (which builds the attribute
payloads during parse) and the sensor platform can import them without a
circular import.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def format_message(raw: str, parameters: dict[str, Any]) -> str:
    """Substitute ``{PARAM}`` placeholders in a raw UniFi alert string.

    UniFi ``parameters`` values are dicts carrying a ``name`` (occasionally only
    an ``id``); scalars are substituted directly. Unmatched placeholders are
    left as-is.
    """
    out = raw or ""
    for key, val in (parameters or {}).items():
        if isinstance(val, dict):
            sub = val.get("name", val.get("id", ""))
        else:
            sub = val
        out = out.replace(f"{{{key}}}", str(sub))
    return out


def build_alert_attrs(event: dict[str, Any]) -> dict[str, Any]:
    """Build the Home Assistant attribute dict for one system-log alert record."""
    params = event.get("parameters") or {}
    ts = event.get("timestamp")
    return {
        "message": format_message(event.get("message_raw", ""), params),
        "title": format_message(event.get("title_raw", ""), params),
        "event": event.get("event"),
        "category": event.get("category"),
        "subcategory": event.get("subcategory"),
        "severity": event.get("severity"),
        "status": event.get("status"),
        "timestamp": (
            datetime.fromtimestamp(ts / 1000.0, tz=UTC).isoformat() if ts else None
        ),
        "parameters": params,
    }
