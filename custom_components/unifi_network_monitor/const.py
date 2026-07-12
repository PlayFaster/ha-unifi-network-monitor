"""Constants for the UniFi Network Monitor integration."""

from collections.abc import Mapping
from typing import Any

DOMAIN = "unifi_network_monitor"
DEFAULT_NAME = "UniFi Network"
NAME = "UniFi Network Monitor"

# Config keys
CONF_API_KEY = "api_key"
CONF_SITE = "site"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_STOP_POLLING = "stop_polling"
CONF_ROGUE_PROXIMITY_RSSI_THRESHOLD = "rogue_proximity_rssi_threshold"

# Setup/reconfigure option keys
CONF_UNIFI_DEVICE_MODE = "unifi_device_mode"
CONF_ENABLE_SPEEDTEST = "enable_speedtest"
CONF_ENABLE_WAN_USAGE = "enable_wan_usage"
CONF_ENABLE_SECURITY_MONITORING = "enable_security_monitoring"
CONF_ENABLE_DUAL_WAN = "enable_dual_wan"
CONF_ENABLE_LOGS_ALERTS = "enable_logs_alerts"

# Rogue-AP expansion option keys (Security sub-device)
CONF_ROGUE_IGNORE_SSIDS = "rogue_ignore_ssids"
CONF_ROGUE_IGNORE_APS = "rogue_ignore_aps"
CONF_ROGUE_PERIOD = "rogue_period"
CONF_ROGUE_SHOW_24GHZ = "rogue_show_24ghz"
CONF_ROGUE_SHOW_5GHZ = "rogue_show_5ghz"
CONF_ROGUE_APPLY_AP_IGNORE = "rogue_apply_ap_ignore"

# unifi_device_mode values — which per-UniFi-device entities Monitor creates
DEVICE_MODE_NONE = "none"
DEVICE_MODE_SATISFACTION = "satisfaction_only"
DEVICE_MODE_ALL = "all"

# Defaults
DEFAULT_SITE = "default"
DEFAULT_SCAN_INTERVAL = 180
# Lean by default: don't add per-UniFi-device sensors unless the user opts in.
DEFAULT_UNIFI_DEVICE_MODE = DEVICE_MODE_NONE
# Feature toggles default ON so existing installs are unchanged on upgrade.
DEFAULT_ENABLE_SPEEDTEST = True
DEFAULT_ENABLE_WAN_USAGE = True
DEFAULT_ENABLE_SECURITY_MONITORING = True
DEFAULT_ENABLE_DUAL_WAN = True
DEFAULT_ENABLE_LOGS_ALERTS = True
# Signal strength (dBm) at or above which a rogue AP is considered "nearby".
# Kept negative to match how RSSI is measured and reported by the sensors.
DEFAULT_ROGUE_PROXIMITY_RSSI_THRESHOLD = -60

# Rogue-AP expansion defaults
DEFAULT_ROGUE_IGNORE_SSIDS = ""
DEFAULT_ROGUE_IGNORE_APS = ""
DEFAULT_ROGUE_PERIOD = "1h"
DEFAULT_ROGUE_SHOW_24GHZ = True
DEFAULT_ROGUE_SHOW_5GHZ = True
DEFAULT_ROGUE_APPLY_AP_IGNORE = False
# Rogue detection period select value -> get_rogueaps(within_hours)
ROGUE_PERIOD_HOURS = {"30m": 1, "1h": 1, "1d": 24, "1w": 168, "1m": 720}


def clamp_device_mode(value: str | None, core_present: bool) -> str:
    """Coerce a stored per-UniFi-device mode to a valid option for the context.

    ``satisfaction_only`` is only meaningful when the HA-native UniFi (core)
    integration is present. Lives here (not config_flow) so both the flow and
    the runtime load-time normaliser can share it without an import cycle.
    """
    valid = (
        {DEVICE_MODE_NONE, DEVICE_MODE_SATISFACTION, DEVICE_MODE_ALL}
        if core_present
        else {DEVICE_MODE_NONE, DEVICE_MODE_ALL}
    )
    return value if value in valid else DEFAULT_UNIFI_DEVICE_MODE


# Per-endpoint resilience
# Optional endpoints hold their last-good value for this many consecutive
# failures, then their entities are marked unavailable.
FETCH_STRIKE_LIMIT = 3

# Optional-endpoint labels — shared between the coordinator fetch tasks and the
# entity `source` tags, so a sensor can be marked unavailable when its endpoint
# goes stale. These strings are the identity used in the per-endpoint state map;
# never inline them separately in the two places.
EP_SYSINFO = "sysinfo"
EP_NETWORKCONF = "network config"
EP_SETTINGS = "site settings"
EP_DAILY = "daily gateway report"
EP_MONTHLY = "monthly gateway report"
EP_ROGUE = "rogue AP list"
EP_GUESTS = "guest list"
EP_BACKUPS = "backup list"
EP_SPEEDTEST = "speedtest results"
EP_WLAN = "wlan config"
EP_WAN_IF = "wan interfaces"
EP_VPN_SERVERS = "vpn servers"
EP_VPN_TUNNELS = "vpn tunnels"
EP_FIREWALL = "firewall policies"
EP_SYSLOG = "system log"


# WAN2 / load-balance key-sets — unique-id suffixes to omit when dual-WAN
# monitoring is off. WAN2 rides the SAME shared endpoints as WAN1 (health,
# daily/monthly, speedtest, stat/device), so this is a creation + cleanup
# key-set filter ONLY — never route it through disabled_endpoints (that would
# kill WAN1 too). Suffix = the part of unique_id after f"{entry.unique_id}_":
# gateway/binary sensors use desc.key, health sensors use "health_"+key, the
# button uses "wan2_speedtest", the LB number uses "wan1_load_balance_weight".
WAN2_KEYS: frozenset[str] = frozenset(
    {
        "wan2_local_ip",
        "wan2_public_ip",
        "wan2_interface_name",
        "wan2_today_rx",
        "wan2_today_tx",
        "wan2_today_total",
        "wan2_month_rx",
        "wan2_month_tx",
        "wan2_month_total",
        "wan2_speedtest_download",
        "wan2_speedtest_upload",
        "wan2_speedtest_ping",
        "wan2_speedtest_lastrun",
        "health_wan2_availability",
        "health_wan2_latency_avg",
        "health_wan2_boot_time",
        "health_wan2_uptime",
        "health_wan2_time_period",
        "wan2_active",
        "wan2_up",
        "wan2_speedtest",
    }
)

# Load-balancing entities — meaningless with one WAN; removed with dual-WAN off.
LOAD_BALANCE_KEYS: frozenset[str] = frozenset(
    {
        "wan1_weight",
        "wan2_weight",
        "wan_mode",
        "wan1_load_balance_weight",
    }
)


def single_wan_excluded_keys() -> frozenset[str]:
    """Unique-id suffixes to omit when dual-WAN monitoring is off."""
    return WAN2_KEYS | LOAD_BALANCE_KEYS


def dual_wan_enabled(options: Mapping[str, Any]) -> bool:
    """Return True when dual-WAN monitoring (WAN2 + load-balance) is enabled."""
    return options.get(CONF_ENABLE_DUAL_WAN, DEFAULT_ENABLE_DUAL_WAN)

# Gateway model identifiers from UniFi stat/device
GATEWAY_MODELS = {
    "UDMPRO",
    "UDM",
    "UDMSE",
    "UDMPROSE",
    "UDMBASE",
    "UNVR",
    "UNVRPRO",
    "UCG-Ultra",
    "UCG-Max",
}
