"""Tests for const helpers."""

from custom_components.unifi_network_monitor.const import disabled_device_keys


def test_disabled_device_keys_alerts_off() -> None:
    """disabled_device_keys includes 'alerts' when logs_alerts is off."""
    result = disabled_device_keys({"enable_logs_alerts": False})
    assert "alerts" in result


def test_disabled_device_keys_all_off() -> None:
    """disabled_device_keys includes all keys when all toggles are off."""
    result = disabled_device_keys(
        {
            "enable_speedtest": False,
            "enable_security_monitoring": False,
            "enable_logs_alerts": False,
        }
    )
    assert "speedtest" in result
    assert "security" in result
    assert "alerts" in result


def test_disabled_device_keys_all_on() -> None:
    """disabled_device_keys is empty when all toggles are on."""
    result = disabled_device_keys(
        {
            "enable_speedtest": True,
            "enable_security_monitoring": True,
            "enable_logs_alerts": True,
        }
    )
    assert result == frozenset()


def test_disabled_device_keys_defaults() -> None:
    """disabled_device_keys is empty with empty options (all defaults True)."""
    result = disabled_device_keys({})
    assert result == frozenset()
