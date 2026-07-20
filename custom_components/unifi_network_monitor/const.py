"""Constants for the UniFi Network Monitor integration."""

from collections.abc import Mapping
from typing import Any

DOMAIN = "unifi_network_monitor"
DEFAULT_NAME = "UniFi Network"
NAME = "UniFi Network Monitor"

# Bus event fired once per newly-seen HIGH/VERY_HIGH alert (Alerts monitoring).
# Only fires while Alerts monitoring is enabled (no EP_SYSLOG fetch => no parse
# => no event); HA has no event-type registry, so nothing needs removing when
# the Alerts group is off.
EVENT_NEW_ALERT = f"{DOMAIN}_new_alert"

# On-demand log-query action (response service). Domain-global, stays registered
# regardless of the Alerts toggle.
SERVICE_GET_ALERTS = "get_alerts"

# HA sensor states cap at 255 chars; alert titles are short (~40) but substituted
# parameters can push them over, so cap defensively.
ALERT_TITLE_MAX = 255

# get_alerts pagination bounds. page_size 100 is the verified API default; the
# hard 5-page cap (<=500 records) avoids the ~25s call a 50-page sweep of the
# high-volume LOW/MEDIUM log would incur.
ALERT_PAGE_SIZE = 100
ALERT_MAX_PAGES = 5

# get_alerts quantity control.
ALERT_QUANTITY_DEFAULT = 10
ALERT_QUANTITY_MAX = 100

# The four severity strings the v2 system-log emits (verified live). Sensors and
# events use HIGH+VERY_HIGH; the action can reach all four on demand.
ALERT_SEVERITIES = ("LOW", "MEDIUM", "HIGH", "VERY_HIGH")
DEFAULT_ALERT_SEVERITIES = ("HIGH", "VERY_HIGH")

# Bus event fired once per newly-seen rogue-AP BSSID (Security monitoring). Same
# gating story as EVENT_NEW_ALERT: only fires while Security is enabled (no
# EP_ROGUE fetch => no parse => no event).
EVENT_NEW_ROGUE_AP = f"{DOMAIN}_new_rogue_ap"

# On-demand rogue-AP query action (response service). Domain-global; fetches its
# own data so it works regardless of the Security toggle (fully decoupled).
SERVICE_GET_ROGUE_APS = "get_rogue_aps"

# Persistent rogue-AP appearance history — clear action + ignore-list management.
SERVICE_CLEAR_ROGUE_HISTORY = "clear_rogue_history"
SERVICE_ADD_ROGUE_IGNORE = "add_rogue_ignore"
SERVICE_REMOVE_ROGUE_IGNORE = "remove_rogue_ignore"
SERVICE_SET_ROGUE_IGNORE = "set_rogue_ignore"
# target selector for the ignore-list services (which list to manage).
ROGUE_IGNORE_TARGET_SSIDS = "ssids"
ROGUE_IGNORE_TARGET_APS = "aps"
ROGUE_IGNORE_TARGETS = (ROGUE_IGNORE_TARGET_SSIDS, ROGUE_IGNORE_TARGET_APS)

# get_rogue_aps quantity control.
ROGUE_QUANTITY_DEFAULT = 10
ROGUE_QUANTITY_MAX = 100

# get_rogue_aps age presets -> get_rogueaps(within_hours). Named buckets (a
# select) so the user never converts hours<->days; "all" spans the controller's
# full rogue retention (~3 months) with margin. The endpoint's granularity is
# hourly, so sub-hour buckets map to 1h.
ROGUE_ACTION_PERIOD_HOURS = {
    "30m": 1,
    "1h": 1,
    "6h": 6,
    "24h": 24,
    "7d": 168,
    "30d": 720,
    "90d": 2160,
    "all": 8760,
}
DEFAULT_ROGUE_ACTION_PERIOD = "24h"

# get_rogue_aps band filter values.
ROGUE_ACTION_BANDS = ("2.4", "5", "both")
DEFAULT_ROGUE_ACTION_BAND = "both"

# Display sentinel for a cloaked SSID when its BSSID is unknown (fallback only).
# Normally a hidden SSID is named ``Hidden-<suffix>`` from its BSSID so distinct
# cloaked APs stay distinguishable and trackable across polls.
ROGUE_HIDDEN_SSID = "<Hidden>"

# Prefix for the BSSID-derived pseudo-name of a cloaked SSID (e.g. "Hidden-A2D3").
ROGUE_HIDDEN_PREFIX = "Hidden-"

# Placeholder substituted for control/zero-width/non-printable characters in an
# essid, so a spoofed name renders safely and the tampering stays visible.
ROGUE_ESSID_PLACEHOLDER = "·"  # · (middle dot)

# Max rogue-AP rows carried on the Strongest Rogue SSID sensor's rogue_aps
# attribute. HA rejects a state whose attributes exceed 16 KB; capping at 25
# strongest (~5-6 KB) stays well clear, and the full/filtered list is available
# on demand via the get_rogue_aps action. rogue_ap_count holds the true total.
ROGUE_ATTR_MAX = 25

# Fixed window for the raw rogue-detection volume sensor (hours). Independent of
# the user-tunable live Rogue Detection Period so the long-term trend stays
# comparable over time.
ROGUE_RAW_WINDOW_HOURS = 24

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
CONF_ROGUE_APPLY_SSID_IGNORE = "rogue_apply_ssid_ignore"
CONF_ROGUE_HISTORY_TTL_DAYS = "rogue_history_ttl_days"

# Persistent rogue-history tuning. TTL prunes BSSIDs unseen for N days (0 = keep
# forever); the hard cap bounds the store regardless of TTL (MAC randomization
# can spray many one-off BSSIDs). Writes are coalesced via async_delay_save.
DEFAULT_ROGUE_HISTORY_TTL_DAYS = 90
ROGUE_HISTORY_MAX = 1000
ROGUE_HISTORY_SAVE_DELAY = 120
ROGUE_HISTORY_STORAGE_VERSION = 1

# Per-counter high-water mark for cumulative WAN usage. UniFi apportions the
# current (open) daily/monthly bucket and re-computes it each poll, so a byte
# total can drift slightly *downward* within a period — which breaks the
# total_increasing state class. We clamp each counter to its running maximum and
# reset only when the bucket's period timestamp moves forward (a real rollover).
# Persisted so a restart does not re-emit the drop against what HA already stored.
USAGE_WATERMARK_SAVE_DELAY = 120
USAGE_WATERMARK_STORAGE_VERSION = 1

# Self-diagnosis: how many consecutive cycles a schema-drift signal must persist
# before the Integration Health sensor / repair issue flags it (avoids single-
# cycle false alarms; also gives startup grace).
HEALTH_DRIFT_STRIKE_LIMIT = 3

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
# SSID ignore is a safe direct match, so it applies by default (unlike the
# aggressive all-APs-match AP rule); the switch is a "show everything" override.
DEFAULT_ROGUE_APPLY_SSID_IGNORE = True
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
EP_ROGUE_RAW = "rogue AP raw 24h"
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
        "wan2_sfp_vendor",
        "wan2_sfp_part",
        "wan2_sfp_serial",
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
    return bool(options.get(CONF_ENABLE_DUAL_WAN, DEFAULT_ENABLE_DUAL_WAN))


# Sub-device cards wholly owned by one feature toggle. When the toggle is off,
# EVERY entity on that card is removed (regardless of which endpoint feeds it),
# so the card ends up empty and is detached by cleanup. This card-ownership rule
# is distinct from per-endpoint availability gating.
def disabled_device_keys(options: Mapping[str, Any]) -> frozenset[str]:
    """Return the ``device_key`` cards whose owning feature toggle is off."""
    disabled: set[str] = set()
    if not options.get(CONF_ENABLE_SPEEDTEST, DEFAULT_ENABLE_SPEEDTEST):
        disabled.add("speedtest")
    if not options.get(
        CONF_ENABLE_SECURITY_MONITORING, DEFAULT_ENABLE_SECURITY_MONITORING
    ):
        disabled.add("security")
    if not options.get(CONF_ENABLE_LOGS_ALERTS, DEFAULT_ENABLE_LOGS_ALERTS):
        disabled.add("alerts")
    return frozenset(disabled)


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
