"""Regression tests for the WAN usage `*_total` value functions.

A `*_total` sensor sums the rx and tx counters. The coordinator always writes
both keys, using ``None`` when the bucket lacked that attr — so a one-sided
bucket (one direction present, the other ``None``) must report the side it has,
not raise ``None + int``. Both-None must still report ``None`` (unknown).
"""

from __future__ import annotations

import pytest

from custom_components.unifi_network_monitor.sensor import GATEWAY_SENSORS

TOTAL_KEYS = (
    ("wan1_today_total", "wan1_today_rx", "wan1_today_tx"),
    ("wan2_today_total", "wan2_today_rx", "wan2_today_tx"),
    ("wan1_month_total", "wan1_month_rx", "wan1_month_tx"),
    ("wan2_month_total", "wan2_month_rx", "wan2_month_tx"),
)


def _value_fn(total_key: str):
    desc = next(d for d in GATEWAY_SENSORS if d.key == total_key)
    return desc.value_fn


@pytest.mark.parametrize(("total_key", "rx_key", "tx_key"), TOTAL_KEYS)
def test_both_present_sums(total_key: str, rx_key: str, tx_key: str) -> None:
    """Normal path: both directions present are summed."""
    assert _value_fn(total_key)({rx_key: 100, tx_key: 400}) == 500


@pytest.mark.parametrize(("total_key", "rx_key", "tx_key"), TOTAL_KEYS)
def test_tx_missing_reports_rx(total_key: str, rx_key: str, tx_key: str) -> None:
    """One-sided bucket (tx None) must report rx, not raise None + int."""
    assert _value_fn(total_key)({rx_key: 100, tx_key: None}) == 100


@pytest.mark.parametrize(("total_key", "rx_key", "tx_key"), TOTAL_KEYS)
def test_rx_missing_reports_tx(total_key: str, rx_key: str, tx_key: str) -> None:
    """One-sided bucket (rx None) must report tx, not raise None + int."""
    assert _value_fn(total_key)({rx_key: None, tx_key: 400}) == 400


@pytest.mark.parametrize(("total_key", "rx_key", "tx_key"), TOTAL_KEYS)
def test_both_none_reports_unknown(total_key: str, rx_key: str, tx_key: str) -> None:
    """Both absent (single-WAN, or no data) stays None -> sensor 'unknown'."""
    assert _value_fn(total_key)({rx_key: None, tx_key: None}) is None


@pytest.mark.parametrize(("total_key", "rx_key", "tx_key"), TOTAL_KEYS)
def test_zero_is_a_real_value(total_key: str, rx_key: str, tx_key: str) -> None:
    """A genuine zero-byte side is summed as 0, not treated as absent."""
    assert _value_fn(total_key)({rx_key: 0, tx_key: 250}) == 250
