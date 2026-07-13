"""Helpers for UniFi system-log alert entities.

Kept in its own module so both the coordinator (which builds the attribute
payloads during parse) and the sensor platform can import them without a
circular import.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .const import ALERT_TITLE_MAX


def _iso_timestamp(ts: Any) -> str | None:
    """Convert a UniFi ms-epoch timestamp to an ISO string (None when absent)."""
    if not ts:
        return None
    return datetime.fromtimestamp(ts / 1000.0, tz=UTC).isoformat()


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


def alert_title(event: dict[str, Any]) -> str:
    """Return the substituted, length-capped title for a system-log alert.

    Used as the "Last High/Very High" sensor state, which HA caps at 255 chars;
    truncate defensively (254 + ellipsis) rather than let a long title error.
    """
    title = format_message(event.get("title_raw", ""), event.get("parameters") or {})
    if len(title) > ALERT_TITLE_MAX:
        return title[: ALERT_TITLE_MAX - 1] + "…"
    return title


def build_alert_attrs(event: dict[str, Any]) -> dict[str, Any]:
    """Build the Home Assistant attribute dict for one system-log alert record."""
    params = event.get("parameters") or {}
    return {
        "id": event.get("id"),
        "message": format_message(event.get("message_raw", ""), params),
        "title": format_message(event.get("title_raw", ""), params),
        "event": event.get("event"),
        "category": event.get("category"),
        "subcategory": event.get("subcategory"),
        "severity": event.get("severity"),
        "status": event.get("status"),
        "timestamp": _iso_timestamp(event.get("timestamp")),
        "parameters": params,
    }


def build_alert_response(event: dict[str, Any]) -> dict[str, Any]:
    """Build one human-readable alert record for the get_alerts action response."""
    params = event.get("parameters") or {}
    return {
        "id": event.get("id"),
        "timestamp": _iso_timestamp(event.get("timestamp")),
        "severity": event.get("severity"),
        "category": event.get("category"),
        "subcategory": event.get("subcategory"),
        "event": event.get("event"),
        "title": format_message(event.get("title_raw", ""), params),
        "message": format_message(event.get("message_raw", ""), params),
        "status": event.get("status"),
    }


def build_event_payload(entry_id: str, event: dict[str, Any]) -> dict[str, Any]:
    """Build the ``unifi_network_monitor_new_alert`` bus-event payload."""
    params = event.get("parameters") or {}
    return {
        "entry_id": entry_id,
        "id": event.get("id"),
        "severity": event.get("severity"),
        "category": event.get("category"),
        "event": event.get("event"),
        "title": format_message(event.get("title_raw", ""), params),
        "message": format_message(event.get("message_raw", ""), params),
        "timestamp": _iso_timestamp(event.get("timestamp")),
        "status": event.get("status"),
    }
