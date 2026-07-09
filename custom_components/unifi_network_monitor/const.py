"""Constants for the UniFi Network Monitor integration."""

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
# Signal strength (dBm) at or above which a rogue AP is considered "nearby".
# Kept negative to match how RSSI is measured and reported by the sensors.
DEFAULT_ROGUE_PROXIMITY_RSSI_THRESHOLD = -60

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
