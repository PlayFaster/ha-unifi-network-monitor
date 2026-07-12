"""Sensor platform for UniFi Network Monitor."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

from homeassistant.components.sensor import (
    ENTITY_ID_FORMAT,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfDataRate,
    UnitOfInformation,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_UNIFI_DEVICE_MODE,
    DEFAULT_UNIFI_DEVICE_MODE,
    DEVICE_MODE_NONE,
    DEVICE_MODE_SATISFACTION,
    EP_BACKUPS,
    EP_DAILY,
    EP_FIREWALL,
    EP_GUESTS,
    EP_MONTHLY,
    EP_NETWORKCONF,
    EP_ROGUE,
    EP_SETTINGS,
    EP_SPEEDTEST,
    EP_SYSINFO,
    EP_SYSLOG,
    EP_VPN_TUNNELS,
    EP_WAN_IF,
    EP_WLAN,
    dual_wan_enabled,
    single_wan_excluded_keys,
)
from .coordinator import (
    UnifiNetworkDataUpdateCoordinator,
    disabled_endpoints,
)
from .helpers import (
    build_sub_device_info,
    build_unifi_device_info,
)

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

_MS_UNIT = "ms"

# Maps a gateway sensor's key to the optional endpoint it depends on. When that
# endpoint goes stale (see coordinator per-endpoint resilience), the sensor
# reports "unavailable". Keys absent here are sourced from the mandatory
# get_devices()/get_health() calls and follow the global 3-strike instead.
_ENDPOINT_BY_KEY: dict[str, str] = {
    "application_version": EP_SYSINFO,
    "wan_mode": EP_NETWORKCONF,
    "wan1_weight": EP_NETWORKCONF,
    "wan2_weight": EP_NETWORKCONF,
    "configured_vlans": EP_NETWORKCONF,
    "vlans_total": EP_NETWORKCONF,
    "vlans_active": EP_NETWORKCONF,
    "ips_mode": EP_SETTINGS,
    "wan1_today_rx": EP_DAILY,
    "wan1_today_tx": EP_DAILY,
    "wan1_today_total": EP_DAILY,
    "wan2_today_rx": EP_DAILY,
    "wan2_today_tx": EP_DAILY,
    "wan2_today_total": EP_DAILY,
    "wan1_month_rx": EP_MONTHLY,
    "wan1_month_tx": EP_MONTHLY,
    "wan1_month_total": EP_MONTHLY,
    "wan2_month_rx": EP_MONTHLY,
    "wan2_month_tx": EP_MONTHLY,
    "wan2_month_total": EP_MONTHLY,
    "month_total": EP_MONTHLY,
    "rogue_ap_count": EP_ROGUE,
    "strongest_rogue_ssid": EP_ROGUE,
    "strongest_rogue_rssi": EP_ROGUE,
    "guest_user_count": EP_GUESTS,
    "last_backup": EP_BACKUPS,
    "wan1_speedtest_download": EP_SPEEDTEST,
    "wan1_speedtest_upload": EP_SPEEDTEST,
    "wan1_speedtest_ping": EP_SPEEDTEST,
    "wan1_speedtest_lastrun": EP_SPEEDTEST,
    "wan2_speedtest_download": EP_SPEEDTEST,
    "wan2_speedtest_upload": EP_SPEEDTEST,
    "wan2_speedtest_ping": EP_SPEEDTEST,
    "wan2_speedtest_lastrun": EP_SPEEDTEST,
    "wifi_networks_total": EP_WLAN,
    "wifi_networks_active": EP_WLAN,
    "wan1_interface_name": EP_WAN_IF,
    "wan2_interface_name": EP_WAN_IF,
    "vpn_connections_total": EP_VPN_TUNNELS,
    "vpn_connections_active": EP_VPN_TUNNELS,
    "rules_configured": EP_FIREWALL,
    "rules_active": EP_FIREWALL,
    "rules_disabled": EP_FIREWALL,
    "last_critical_alert": EP_SYSLOG,
    "alerts_high_24h": EP_SYSLOG,
    "alerts_very_high_24h": EP_SYSLOG,
}


@dataclass(frozen=True, kw_only=True)
class UnifiSensorEntityDescription(SensorEntityDescription):
    """Extends SensorEntityDescription with value extraction and guard bands."""

    value_fn: Callable[[dict[str, Any]], Any]
    min_limit: float | None = None
    max_limit: float | None = None
    enable_in_standalone: bool = False
    device_key: str = "gateway"


# ---------------------------------------------------------------------------
# Gateway sensor descriptions
# ---------------------------------------------------------------------------

GATEWAY_SENSORS: Final[tuple[UnifiSensorEntityDescription, ...]] = (
    UnifiSensorEntityDescription(
        key="cpu",
        translation_key="gateway_cpu",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        enable_in_standalone=True,
        min_limit=0.0,
        max_limit=100.0,
        value_fn=lambda d: d.get("cpu"),
    ),
    UnifiSensorEntityDescription(
        key="ram",
        translation_key="gateway_ram",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        enable_in_standalone=True,
        min_limit=0.0,
        max_limit=100.0,
        value_fn=lambda d: d.get("ram"),
    ),
    UnifiSensorEntityDescription(
        key="cpu_temp",
        translation_key="gateway_cpu_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        enable_in_standalone=True,
        min_limit=0.0,
        max_limit=120.0,
        value_fn=lambda d: d.get("cpu_temp"),
    ),
    UnifiSensorEntityDescription(
        key="board_temp",
        translation_key="gateway_board_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        enable_in_standalone=True,
        min_limit=0.0,
        max_limit=120.0,
        value_fn=lambda d: d.get("board_temp"),
    ),
    UnifiSensorEntityDescription(
        key="uptime",
        translation_key="gateway_uptime",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        enable_in_standalone=True,
        value_fn=lambda d: d.get("boot_time"),
    ),
    UnifiSensorEntityDescription(
        key="wan1_local_ip",
        translation_key="gateway_wan1_local_ip",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("wan1_local_ip"),
        device_key="internet",
    ),
    UnifiSensorEntityDescription(
        key="wan1_public_ip",
        translation_key="gateway_wan1_public_ip",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("wan1_public_ip"),
        device_key="internet",
    ),
    UnifiSensorEntityDescription(
        key="wan2_local_ip",
        translation_key="gateway_wan2_local_ip",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("wan2_local_ip"),
        device_key="internet",
    ),
    UnifiSensorEntityDescription(
        key="wan2_public_ip",
        translation_key="gateway_wan2_public_ip",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("wan2_public_ip"),
        device_key="internet",
    ),
    UnifiSensorEntityDescription(
        key="storage_used",
        translation_key="gateway_storage_used",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
        min_limit=0.0,
        value_fn=lambda d: d.get("storage_used"),
    ),
    UnifiSensorEntityDescription(
        key="storage_size",
        translation_key="gateway_storage_size",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        min_limit=0.0,
        value_fn=lambda d: d.get("storage_size"),
    ),
    UnifiSensorEntityDescription(
        key="last_updated",
        translation_key="gateway_last_updated",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: None,
        device_key="system",
    ),
    UnifiSensorEntityDescription(
        key="storage_used_pct",
        translation_key="gateway_storage_used_pct",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        min_limit=0.0,
        max_limit=100.0,
        value_fn=lambda d: d.get("storage_used_pct"),
    ),
    UnifiSensorEntityDescription(
        key="wan_mode",
        translation_key="gateway_wan_mode",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("wan_mode"),
        device_key="system",
    ),
    UnifiSensorEntityDescription(
        key="wan1_weight",
        translation_key="gateway_wan1_weight",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        min_limit=0.0,
        max_limit=100.0,
        value_fn=lambda d: d.get("wan1_weight"),
        device_key="system",
    ),
    UnifiSensorEntityDescription(
        key="wan2_weight",
        translation_key="gateway_wan2_weight",
        native_unit_of_measurement=PERCENTAGE,
        min_limit=0.0,
        max_limit=100.0,
        value_fn=lambda d: d.get("wan2_weight"),
        device_key="system",
    ),
    UnifiSensorEntityDescription(
        key="ips_mode",
        translation_key="gateway_ips_mode",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("ips_mode"),
        device_key="security",
    ),
    UnifiSensorEntityDescription(
        key="wan1_sfp_vendor",
        translation_key="gateway_wan1_sfp_vendor",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.get("wan1_sfp_vendor"),
        device_key="gateway",
    ),
    UnifiSensorEntityDescription(
        key="wan1_sfp_part",
        translation_key="gateway_wan1_sfp_part",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.get("wan1_sfp_part"),
        device_key="gateway",
    ),
    UnifiSensorEntityDescription(
        key="wan1_sfp_serial",
        translation_key="gateway_wan1_sfp_serial",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.get("wan1_sfp_serial"),
        device_key="gateway",
    ),
    UnifiSensorEntityDescription(
        key="wan2_sfp_vendor",
        translation_key="gateway_wan2_sfp_vendor",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.get("wan2_sfp_vendor"),
        device_key="gateway",
    ),
    UnifiSensorEntityDescription(
        key="wan2_sfp_part",
        translation_key="gateway_wan2_sfp_part",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.get("wan2_sfp_part"),
        device_key="gateway",
    ),
    UnifiSensorEntityDescription(
        key="wan2_sfp_serial",
        translation_key="gateway_wan2_sfp_serial",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.get("wan2_sfp_serial"),
        device_key="gateway",
    ),
    UnifiSensorEntityDescription(
        key="wan1_today_rx",
        translation_key="gateway_wan1_today_rx",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        suggested_display_precision=2,
        min_limit=0.0,
        value_fn=lambda d: d.get("wan1_today_rx"),
        device_key="internet",
    ),
    UnifiSensorEntityDescription(
        key="wan1_today_tx",
        translation_key="gateway_wan1_today_tx",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        suggested_display_precision=2,
        min_limit=0.0,
        value_fn=lambda d: d.get("wan1_today_tx"),
        device_key="internet",
    ),
    UnifiSensorEntityDescription(
        key="wan1_today_total",
        translation_key="gateway_wan1_today_total",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        suggested_display_precision=2,
        min_limit=0.0,
        value_fn=lambda d: (
            d.get("wan1_today_rx", 0) + d.get("wan1_today_tx", 0)
            if d.get("wan1_today_rx") is not None or d.get("wan1_today_tx") is not None
            else None
        ),
        device_key="internet",
    ),
    UnifiSensorEntityDescription(
        key="wan2_today_rx",
        translation_key="gateway_wan2_today_rx",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        suggested_display_precision=2,
        min_limit=0.0,
        value_fn=lambda d: d.get("wan2_today_rx"),
        device_key="internet",
    ),
    UnifiSensorEntityDescription(
        key="wan2_today_tx",
        translation_key="gateway_wan2_today_tx",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        suggested_display_precision=2,
        min_limit=0.0,
        value_fn=lambda d: d.get("wan2_today_tx"),
        device_key="internet",
    ),
    UnifiSensorEntityDescription(
        key="wan2_today_total",
        translation_key="gateway_wan2_today_total",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        suggested_display_precision=2,
        min_limit=0.0,
        value_fn=lambda d: (
            d.get("wan2_today_rx", 0) + d.get("wan2_today_tx", 0)
            if d.get("wan2_today_rx") is not None or d.get("wan2_today_tx") is not None
            else None
        ),
        device_key="internet",
    ),
    UnifiSensorEntityDescription(
        key="wan1_month_rx",
        translation_key="gateway_wan1_month_rx",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        suggested_display_precision=1,
        state_class=SensorStateClass.TOTAL_INCREASING,
        min_limit=0.0,
        value_fn=lambda d: d.get("wan1_month_rx"),
        device_key="internet",
    ),
    UnifiSensorEntityDescription(
        key="wan1_month_tx",
        translation_key="gateway_wan1_month_tx",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        suggested_display_precision=1,
        state_class=SensorStateClass.TOTAL_INCREASING,
        min_limit=0.0,
        value_fn=lambda d: d.get("wan1_month_tx"),
        device_key="internet",
    ),
    UnifiSensorEntityDescription(
        key="wan1_month_total",
        translation_key="gateway_wan1_month_total",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        suggested_display_precision=1,
        state_class=SensorStateClass.TOTAL_INCREASING,
        min_limit=0.0,
        value_fn=lambda d: (
            d.get("wan1_month_rx", 0) + d.get("wan1_month_tx", 0)
            if d.get("wan1_month_rx") is not None or d.get("wan1_month_tx") is not None
            else None
        ),
        device_key="internet",
    ),
    UnifiSensorEntityDescription(
        key="wan2_month_rx",
        translation_key="gateway_wan2_month_rx",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        suggested_display_precision=1,
        state_class=SensorStateClass.TOTAL_INCREASING,
        min_limit=0.0,
        value_fn=lambda d: d.get("wan2_month_rx"),
        device_key="internet",
    ),
    UnifiSensorEntityDescription(
        key="wan2_month_tx",
        translation_key="gateway_wan2_month_tx",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        suggested_display_precision=1,
        state_class=SensorStateClass.TOTAL_INCREASING,
        min_limit=0.0,
        value_fn=lambda d: d.get("wan2_month_tx"),
        device_key="internet",
    ),
    UnifiSensorEntityDescription(
        key="wan2_month_total",
        translation_key="gateway_wan2_month_total",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        suggested_display_precision=1,
        state_class=SensorStateClass.TOTAL_INCREASING,
        min_limit=0.0,
        value_fn=lambda d: (
            d.get("wan2_month_rx", 0) + d.get("wan2_month_tx", 0)
            if d.get("wan2_month_rx") is not None or d.get("wan2_month_tx") is not None
            else None
        ),
        device_key="internet",
    ),
    UnifiSensorEntityDescription(
        key="month_total",
        translation_key="gateway_month_total",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        suggested_display_precision=1,
        state_class=SensorStateClass.TOTAL_INCREASING,
        min_limit=0.0,
        value_fn=lambda d: (
            d.get("wan1_month_rx", 0)
            + d.get("wan1_month_tx", 0)
            + d.get("wan2_month_rx", 0)
            + d.get("wan2_month_tx", 0)
            if any(
                d.get(k) is not None
                for k in (
                    "wan1_month_rx",
                    "wan1_month_tx",
                    "wan2_month_rx",
                    "wan2_month_tx",
                )
            )
            else None
        ),
        device_key="internet",
    ),
    UnifiSensorEntityDescription(
        key="rogue_ap_count",
        translation_key="gateway_rogue_ap_count",
        state_class=SensorStateClass.MEASUREMENT,
        min_limit=0.0,
        value_fn=lambda d: d.get("rogue_ap_count"),
        device_key="security",
    ),
    UnifiSensorEntityDescription(
        key="strongest_rogue_ssid",
        translation_key="gateway_strongest_rogue_ssid",
        value_fn=lambda d: d.get("strongest_rogue_ssid"),
        device_key="security",
    ),
    UnifiSensorEntityDescription(
        key="strongest_rogue_rssi",
        translation_key="gateway_strongest_rogue_rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement="dBm",
        state_class=SensorStateClass.MEASUREMENT,
        min_limit=-100.0,
        max_limit=0.0,
        value_fn=lambda d: d.get("strongest_rogue_rssi"),
        device_key="security",
    ),
    UnifiSensorEntityDescription(
        key="guest_user_count",
        translation_key="gateway_guest_user_count",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        min_limit=0.0,
        value_fn=lambda d: d.get("guest_user_count"),
        device_key="status",
    ),
    UnifiSensorEntityDescription(
        key="last_backup",
        translation_key="gateway_last_backup",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("last_backup"),
    ),
    UnifiSensorEntityDescription(
        key="configured_vlans",
        translation_key="gateway_configured_vlans",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        min_limit=0.0,
        value_fn=lambda d: d.get("configured_vlans"),
        device_key="status",
    ),
    UnifiSensorEntityDescription(
        key="application_version",
        translation_key="gateway_application_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("application_version"),
    ),
    UnifiSensorEntityDescription(
        key="wan1_speedtest_download",
        translation_key="gateway_wan1_speedtest_download",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        suggested_display_precision=0,
        state_class=SensorStateClass.MEASUREMENT,
        min_limit=0.0,
        value_fn=lambda d: d.get("wan1_speedtest_download"),
        device_key="speedtest",
    ),
    UnifiSensorEntityDescription(
        key="wan1_speedtest_upload",
        translation_key="gateway_wan1_speedtest_upload",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        suggested_display_precision=0,
        state_class=SensorStateClass.MEASUREMENT,
        min_limit=0.0,
        value_fn=lambda d: d.get("wan1_speedtest_upload"),
        device_key="speedtest",
    ),
    UnifiSensorEntityDescription(
        key="wan1_speedtest_ping",
        translation_key="gateway_wan1_speedtest_ping",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=_MS_UNIT,
        entity_category=EntityCategory.DIAGNOSTIC,
        min_limit=0.0,
        max_limit=9999.0,
        value_fn=lambda d: d.get("wan1_speedtest_ping"),
        device_key="speedtest",
    ),
    UnifiSensorEntityDescription(
        key="wan1_speedtest_lastrun",
        translation_key="gateway_wan1_speedtest_lastrun",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("wan1_speedtest_lastrun"),
        device_key="speedtest",
    ),
    UnifiSensorEntityDescription(
        key="wan2_speedtest_download",
        translation_key="gateway_wan2_speedtest_download",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        suggested_display_precision=0,
        state_class=SensorStateClass.MEASUREMENT,
        min_limit=0.0,
        value_fn=lambda d: d.get("wan2_speedtest_download"),
        device_key="speedtest",
    ),
    UnifiSensorEntityDescription(
        key="wan2_speedtest_upload",
        translation_key="gateway_wan2_speedtest_upload",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        suggested_display_precision=0,
        state_class=SensorStateClass.MEASUREMENT,
        min_limit=0.0,
        value_fn=lambda d: d.get("wan2_speedtest_upload"),
        device_key="speedtest",
    ),
    UnifiSensorEntityDescription(
        key="wan2_speedtest_ping",
        translation_key="gateway_wan2_speedtest_ping",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=_MS_UNIT,
        entity_category=EntityCategory.DIAGNOSTIC,
        min_limit=0.0,
        max_limit=9999.0,
        value_fn=lambda d: d.get("wan2_speedtest_ping"),
        device_key="speedtest",
    ),
    UnifiSensorEntityDescription(
        key="wan2_speedtest_lastrun",
        translation_key="gateway_wan2_speedtest_lastrun",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("wan2_speedtest_lastrun"),
        device_key="speedtest",
    ),
    # WiFi SSIDs
    UnifiSensorEntityDescription(
        key="wifi_networks_total",
        translation_key="gateway_wifi_networks_total",
        entity_category=EntityCategory.DIAGNOSTIC,
        min_limit=0.0,
        value_fn=lambda d: d.get("wifi_networks_total"),
        device_key="status",
    ),
    UnifiSensorEntityDescription(
        key="wifi_networks_active",
        translation_key="gateway_wifi_networks_active",
        state_class=SensorStateClass.MEASUREMENT,
        min_limit=0.0,
        value_fn=lambda d: d.get("wifi_networks_active"),
        device_key="status",
    ),
    # VLANs
    UnifiSensorEntityDescription(
        key="vlans_total",
        translation_key="gateway_vlans_total",
        entity_category=EntityCategory.DIAGNOSTIC,
        min_limit=0.0,
        value_fn=lambda d: d.get("vlans_total"),
        device_key="status",
    ),
    UnifiSensorEntityDescription(
        key="vlans_active",
        translation_key="gateway_vlans_active",
        state_class=SensorStateClass.MEASUREMENT,
        min_limit=0.0,
        value_fn=lambda d: d.get("vlans_active"),
        device_key="status",
    ),
    # VPN Connections
    UnifiSensorEntityDescription(
        key="vpn_connections_total",
        translation_key="gateway_vpn_connections_total",
        entity_category=EntityCategory.DIAGNOSTIC,
        min_limit=0.0,
        value_fn=lambda d: d.get("vpn_connections_total"),
        device_key="security",
    ),
    UnifiSensorEntityDescription(
        key="vpn_connections_active",
        translation_key="gateway_vpn_connections_active",
        state_class=SensorStateClass.MEASUREMENT,
        min_limit=0.0,
        value_fn=lambda d: d.get("vpn_connections_active"),
        device_key="security",
    ),
    # Firewall Rules
    UnifiSensorEntityDescription(
        key="rules_configured",
        translation_key="gateway_rules_configured",
        entity_category=EntityCategory.DIAGNOSTIC,
        min_limit=0.0,
        value_fn=lambda d: d.get("rules_configured"),
        device_key="security",
    ),
    UnifiSensorEntityDescription(
        key="rules_active",
        translation_key="gateway_rules_active",
        state_class=SensorStateClass.MEASUREMENT,
        min_limit=0.0,
        value_fn=lambda d: d.get("rules_active"),
        device_key="security",
    ),
    UnifiSensorEntityDescription(
        key="rules_disabled",
        translation_key="gateway_rules_disabled",
        state_class=SensorStateClass.MEASUREMENT,
        min_limit=0.0,
        value_fn=lambda d: d.get("rules_disabled"),
        device_key="security",
    ),
    # WAN Names
    UnifiSensorEntityDescription(
        key="wan1_interface_name",
        translation_key="gateway_wan1_interface_name",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("wan1_interface_name"),
        device_key="internet",
    ),
    UnifiSensorEntityDescription(
        key="wan2_interface_name",
        translation_key="gateway_wan2_interface_name",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("wan2_interface_name"),
        device_key="internet",
    ),
    # Alerts sub-device (system-log critical alerts)
    UnifiSensorEntityDescription(
        key="last_critical_alert",
        translation_key="gateway_last_critical_alert",
        value_fn=lambda d: d.get("last_critical_alert"),
        device_key="alerts",
    ),
    UnifiSensorEntityDescription(
        key="alerts_very_high_24h",
        translation_key="gateway_alerts_very_high_24h",
        state_class=SensorStateClass.MEASUREMENT,
        min_limit=0.0,
        value_fn=lambda d: d.get("alerts_very_high_24h"),
        device_key="alerts",
    ),
    UnifiSensorEntityDescription(
        key="alerts_high_24h",
        translation_key="gateway_alerts_high_24h",
        state_class=SensorStateClass.MEASUREMENT,
        min_limit=0.0,
        value_fn=lambda d: d.get("alerts_high_24h"),
        device_key="alerts",
    ),
)


# ---------------------------------------------------------------------------
# Network health sensor descriptions (WAN1 / WAN2 / WWW / WLAN / LAN)
# ---------------------------------------------------------------------------

HEALTH_SENSORS: Final[tuple[UnifiSensorEntityDescription, ...]] = (
    # WAN
    UnifiSensorEntityDescription(
        key="wan_isp_name",
        translation_key="health_wan_isp_name",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("wan_isp_name"),
        device_key="internet",
    ),
    UnifiSensorEntityDescription(
        key="wan_isp_org",
        translation_key="health_wan_isp_org",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.get("wan_isp_org"),
        device_key="internet",
    ),
    UnifiSensorEntityDescription(
        key="wan_gw_version",
        translation_key="health_wan_gw_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("wan_gw_version"),
        device_key="gateway",
    ),
    UnifiSensorEntityDescription(
        key="wan_num_sta",
        translation_key="health_wan_num_sta",
        state_class=SensorStateClass.MEASUREMENT,
        min_limit=0.0,
        value_fn=lambda d: d.get("wan_num_sta"),
        device_key="status",
    ),
    # WAN1
    UnifiSensorEntityDescription(
        key="wan1_availability",
        translation_key="health_wan1_availability",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        min_limit=0.0,
        max_limit=100.0,
        value_fn=lambda d: d.get("wan1_availability"),
        device_key="internet",
    ),
    UnifiSensorEntityDescription(
        key="wan1_latency_avg",
        translation_key="health_wan1_latency_avg",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=_MS_UNIT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        min_limit=0.0,
        max_limit=9999.0,
        value_fn=lambda d: d.get("wan1_latency_avg"),
        device_key="internet",
    ),
    UnifiSensorEntityDescription(
        key="wan1_boot_time",
        translation_key="health_wan1_boot_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("wan1_boot_time"),
        device_key="internet",
    ),
    UnifiSensorEntityDescription(
        key="wan1_uptime",
        translation_key="health_wan1_uptime",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        min_limit=0.0,
        value_fn=lambda d: d.get("wan1_uptime"),
        device_key="internet",
    ),
    UnifiSensorEntityDescription(
        key="wan1_time_period",
        translation_key="health_wan1_time_period",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        entity_category=EntityCategory.DIAGNOSTIC,
        min_limit=0.0,
        value_fn=lambda d: d.get("wan1_time_period"),
        device_key="speedtest",
    ),
    # WAN2
    UnifiSensorEntityDescription(
        key="wan2_availability",
        translation_key="health_wan2_availability",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        min_limit=0.0,
        max_limit=100.0,
        value_fn=lambda d: d.get("wan2_availability"),
        device_key="internet",
    ),
    UnifiSensorEntityDescription(
        key="wan2_latency_avg",
        translation_key="health_wan2_latency_avg",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=_MS_UNIT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        min_limit=0.0,
        max_limit=9999.0,
        value_fn=lambda d: d.get("wan2_latency_avg"),
        device_key="internet",
    ),
    UnifiSensorEntityDescription(
        key="wan2_boot_time",
        translation_key="health_wan2_boot_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("wan2_boot_time"),
        device_key="internet",
    ),
    UnifiSensorEntityDescription(
        key="wan2_uptime",
        translation_key="health_wan2_uptime",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        min_limit=0.0,
        value_fn=lambda d: d.get("wan2_uptime"),
        device_key="internet",
    ),
    UnifiSensorEntityDescription(
        key="wan2_time_period",
        translation_key="health_wan2_time_period",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        entity_category=EntityCategory.DIAGNOSTIC,
        min_limit=0.0,
        value_fn=lambda d: d.get("wan2_time_period"),
        device_key="speedtest",
    ),
    # WWW
    UnifiSensorEntityDescription(
        key="www_latency",
        translation_key="health_www_latency",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=_MS_UNIT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        min_limit=0.0,
        max_limit=9999.0,
        value_fn=lambda d: d.get("www_latency"),
        device_key="internet",
    ),
    UnifiSensorEntityDescription(
        key="www_drops",
        translation_key="health_www_drops",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        min_limit=0.0,
        value_fn=lambda d: d.get("www_drops"),
        device_key="internet",
    ),
    UnifiSensorEntityDescription(
        key="www_boot_time",
        translation_key="health_www_boot_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("www_boot_time"),
        device_key="internet",
    ),
    UnifiSensorEntityDescription(
        key="www_speedtest_status",
        translation_key="health_www_speedtest_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("www_speedtest_status"),
        device_key="speedtest",
    ),
    UnifiSensorEntityDescription(
        key="www_uptime",
        translation_key="health_www_uptime",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        min_limit=0.0,
        value_fn=lambda d: d.get("www_uptime"),
        device_key="internet",
    ),
    # WLAN
    UnifiSensorEntityDescription(
        key="wlan_num_user",
        translation_key="health_wlan_num_user",
        state_class=SensorStateClass.MEASUREMENT,
        min_limit=0.0,
        value_fn=lambda d: d.get("wlan_num_user"),
        device_key="status",
    ),
    UnifiSensorEntityDescription(
        key="wlan_num_guest",
        translation_key="health_wlan_num_guest",
        state_class=SensorStateClass.MEASUREMENT,
        min_limit=0.0,
        value_fn=lambda d: d.get("wlan_num_guest"),
        device_key="status",
    ),
    UnifiSensorEntityDescription(
        key="wlan_num_iot",
        translation_key="health_wlan_num_iot",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        min_limit=0.0,
        value_fn=lambda d: d.get("wlan_num_iot"),
        device_key="status",
    ),
    UnifiSensorEntityDescription(
        key="wlan_num_ap",
        translation_key="health_wlan_num_ap",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        min_limit=0.0,
        value_fn=lambda d: d.get("wlan_num_ap"),
        device_key="status",
    ),
    # LAN
    UnifiSensorEntityDescription(
        key="lan_num_user",
        translation_key="health_lan_num_user",
        state_class=SensorStateClass.MEASUREMENT,
        min_limit=0.0,
        value_fn=lambda d: d.get("lan_num_user"),
        device_key="status",
    ),
    UnifiSensorEntityDescription(
        key="lan_num_iot",
        translation_key="health_lan_num_iot",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        min_limit=0.0,
        value_fn=lambda d: d.get("lan_num_iot"),
        device_key="status",
    ),
    UnifiSensorEntityDescription(
        key="lan_num_sw",
        translation_key="health_lan_num_sw",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        min_limit=0.0,
        value_fn=lambda d: d.get("lan_num_sw"),
        device_key="status",
    ),
    UnifiSensorEntityDescription(
        key="lan_num_adopted",
        translation_key="health_lan_num_adopted",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        min_limit=0.0,
        value_fn=lambda d: d.get("lan_num_adopted"),
        device_key="status",
    ),
    UnifiSensorEntityDescription(
        key="vpn_status",
        translation_key="health_vpn_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.get("vpn_status"),
        device_key="status",
    ),
)


# ---------------------------------------------------------------------------
# Per-AP sensor descriptions
# ---------------------------------------------------------------------------

AP_SENSORS: Final[tuple[UnifiSensorEntityDescription, ...]] = (
    UnifiSensorEntityDescription(
        key="clients",
        translation_key="device_clients",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        min_limit=0.0,
        value_fn=lambda d: d.get("clients"),
    ),
    UnifiSensorEntityDescription(
        key="guests",
        translation_key="device_guests",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        min_limit=0.0,
        value_fn=lambda d: d.get("guests"),
    ),
    UnifiSensorEntityDescription(
        key="clients_wifi0",
        translation_key="device_clients_wifi0",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        min_limit=0.0,
        value_fn=lambda d: d.get("clients_wifi0"),
    ),
    UnifiSensorEntityDescription(
        key="clients_wifi1",
        translation_key="device_clients_wifi1",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        min_limit=0.0,
        value_fn=lambda d: d.get("clients_wifi1"),
    ),
    UnifiSensorEntityDescription(
        key="score",
        translation_key="device_score",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        min_limit=0.0,
        max_limit=100.0,
        value_fn=lambda d: d.get("score"),
    ),
    UnifiSensorEntityDescription(
        key="score_wifi0",
        translation_key="device_score_wifi0",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
        min_limit=0.0,
        max_limit=100.0,
        value_fn=lambda d: d.get("score_wifi0"),
    ),
    UnifiSensorEntityDescription(
        key="score_wifi1",
        translation_key="device_score_wifi1",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
        min_limit=0.0,
        max_limit=100.0,
        value_fn=lambda d: d.get("score_wifi1"),
    ),
    UnifiSensorEntityDescription(
        key="cpu",
        translation_key="device_cpu",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        min_limit=0.0,
        max_limit=100.0,
        value_fn=lambda d: d.get("cpu"),
    ),
    UnifiSensorEntityDescription(
        key="ram",
        translation_key="device_ram",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        min_limit=0.0,
        max_limit=100.0,
        value_fn=lambda d: d.get("ram"),
    ),
    UnifiSensorEntityDescription(
        key="uptime",
        translation_key="device_uptime",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.get("boot_time"),
    ),
)

# ---------------------------------------------------------------------------
# Per-switch sensor descriptions
# ---------------------------------------------------------------------------

SWITCH_SENSORS: Final[tuple[UnifiSensorEntityDescription, ...]] = (
    UnifiSensorEntityDescription(
        key="ports_used",
        translation_key="device_ports_used",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        min_limit=0.0,
        value_fn=lambda d: d.get("ports_used"),
    ),
    UnifiSensorEntityDescription(
        key="cpu",
        translation_key="device_cpu",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        min_limit=0.0,
        max_limit=100.0,
        value_fn=lambda d: d.get("cpu"),
    ),
    UnifiSensorEntityDescription(
        key="ram",
        translation_key="device_ram",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        min_limit=0.0,
        max_limit=100.0,
        value_fn=lambda d: d.get("ram"),
    ),
    UnifiSensorEntityDescription(
        key="uptime",
        translation_key="device_uptime",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.get("boot_time"),
    ),
    UnifiSensorEntityDescription(
        key="model",
        translation_key="device_model",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.get("model"),
    ),
)

# ---------------------------------------------------------------------------
# Base entity class
# ---------------------------------------------------------------------------


class UnifiSensorBase(
    CoordinatorEntity[UnifiNetworkDataUpdateCoordinator],
    SensorEntity,
):
    """Base sensor — coordinator-driven, no per-entity polling."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    entity_description: UnifiSensorEntityDescription

    def __init__(
        self,
        coordinator: UnifiNetworkDataUpdateCoordinator,
        entry: ConfigEntry,
        description: UnifiSensorEntityDescription,
        unique_id_suffix: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._attr_unique_id = f"{entry.unique_id}_{unique_id_suffix}"

    @property
    def available(self) -> bool:
        """Unavailable when this sensor's source endpoint has gone stale."""
        if not super().available:
            return False
        return self.coordinator.endpoint_available(
            _ENDPOINT_BY_KEY.get(self.entity_description.key)
        )

    @property
    def native_value(self) -> Any:
        """Return the sensor value, applying guard bands."""
        if self.entity_description.key == "last_updated":
            return self.coordinator.last_update_success_time
        val = self._get_value()
        if val is None:
            return None
        desc = self.entity_description
        if (
            desc.min_limit is not None
            and isinstance(val, (int, float))
            and val < desc.min_limit
        ):
            return None
        if (
            desc.max_limit is not None
            and isinstance(val, (int, float))
            and val > desc.max_limit
        ):
            return None
        return val

    def _get_value(self) -> Any:
        """Extract value from coordinator data — overridden per subclass."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Static entity subclasses (gateway + network health)
# ---------------------------------------------------------------------------


class UnifiGatewaySensor(UnifiSensorBase):
    """Sensor entity bound to the UDM Pro gateway sub-dict."""

    def __init__(
        self,
        coordinator: UnifiNetworkDataUpdateCoordinator,
        entry: ConfigEntry,
        description: UnifiSensorEntityDescription,
        unique_id_suffix: str,
        standalone: bool = False,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, entry, description, unique_id_suffix)
        self._standalone = standalone

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Enable select gateway entities in standalone mode."""
        if self._standalone and self.entity_description.enable_in_standalone:
            return True
        return self.entity_description.entity_registry_enabled_default

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for the gateway."""
        return build_sub_device_info(
            self.coordinator, self._entry, self.entity_description.device_key
        )

    def _get_value(self) -> Any:
        if not self.coordinator.data:
            return None
        return self.entity_description.value_fn(
            self.coordinator.data.get("gateway") or {}
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes for gateway sensors."""
        if not self.coordinator.data:
            return None
        gw = self.coordinator.data.get("gateway") or {}
        if self.entity_description.key == "application_version":
            return {
                "application_version": gw.get("application_version"),
                "application_build": gw.get("application_build"),
                "device_type": gw.get("device_type"),
                "udm_version": gw.get("udm_version"),
            }
        if self.entity_description.key == "strongest_rogue_ssid":
            return {
                "rogue_aps": gw.get("rogue_aps_list"),
            }
        if self.entity_description.key == "last_critical_alert":
            attrs = dict(gw.get("last_critical_alert_attrs") or {})
            attrs["recent_alerts"] = gw.get("recent_alerts")
            return attrs
        return None


class UnifiHealthSensor(UnifiSensorBase):
    """Sensor entity bound to the network health sub-dict."""

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for the Network Health sub-device."""
        return build_sub_device_info(
            self.coordinator, self._entry, self.entity_description.device_key
        )

    def _get_value(self) -> Any:
        if not self.coordinator.data:
            return None
        health_data = self.coordinator.data.get("health") or {}
        val = self.entity_description.value_fn(health_data)
        if val is not None:
            return val
        # Fallback to gateway sub-dict for telemetry configured rules/VLANs/VPNs/WiFi
        gw_data = self.coordinator.data.get("gateway") or {}
        return self.entity_description.value_fn(gw_data)


# ---------------------------------------------------------------------------
# Dynamic device sensor (one instance per physical AP or switch)
# ---------------------------------------------------------------------------

# AP-only "Satisfaction Score" sensors — Monitor's unique per-device value.
_SATISFACTION_KEYS = frozenset({"score", "score_wifi0", "score_wifi1"})
# Per-device sensors that duplicate the native (core) UniFi integration. When
# created, these get a deterministic "_mon" entity_id instead of HA's "_2" so
# they can be told apart while keeping the same display name. Maps the Monitor
# description key to the entity_id stem: the switch "Clients" sensor uses the
# `ports_used` key (its value is num_sta = client count), but its stem is
# `clients` so it becomes "<device>_clients_mon" — matching Core's naming and
# the AP Clients sensor — instead of colliding with Core's switch Clients ("_2").
_DUPLICATES_CORE_KEYS: Final[dict[str, str]] = {
    "clients": "clients",
    "cpu": "cpu",
    "ram": "ram",
    "uptime": "uptime",
    "ports_used": "clients",
}


def _device_descs(
    dev_type: str | None, mode: str
) -> tuple[UnifiSensorEntityDescription, ...]:
    """Per-device sensor descriptions to create for the chosen device mode."""
    if mode == DEVICE_MODE_NONE:
        return ()
    base = AP_SENSORS if dev_type == "ap" else SWITCH_SENSORS
    if mode == DEVICE_MODE_SATISFACTION:
        return tuple(d for d in base if d.key in _SATISFACTION_KEYS)
    return base


class UnifiDeviceSensor(UnifiSensorBase):
    """Sensor entity for a dynamic UniFi AP or switch."""

    def __init__(
        self,
        coordinator: UnifiNetworkDataUpdateCoordinator,
        entry: ConfigEntry,
        description: UnifiSensorEntityDescription,
        device_mac: str,
        standalone: bool = False,
    ) -> None:
        """Initialize with a specific device MAC."""
        super().__init__(
            coordinator, entry, description, f"{device_mac}_{description.key}"
        )
        self._device_mac = device_mac
        self._standalone = standalone
        # Duplicate-of-core sensors keep their display name but get a stable
        # "_mon" entity_id (vs HA's ambiguous "_2") so their origin is obvious.
        mon_stem = _DUPLICATES_CORE_KEYS.get(description.key)
        if mon_stem is not None:
            dev = (coordinator.data or {}).get("devices", {}).get(device_mac) or {}
            device_name = dev.get("name") or device_mac
            self.entity_id = async_generate_entity_id(
                ENTITY_ID_FORMAT,
                f"{device_name}_{mon_stem}_mon",
                hass=coordinator.hass,
            )

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Enable all entities when running without native UniFi integration."""
        if self._standalone:
            return True
        return self.entity_description.entity_registry_enabled_default

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info using MAC-based merging."""
        devices = (self.coordinator.data or {}).get("devices", {})
        dev = devices.get(self._device_mac) or {}
        return build_unifi_device_info(
            self.coordinator,
            self._device_mac,
            dev.get("name", self._device_mac),
            dev.get("model", ""),
        )

    def _get_value(self) -> Any:
        if not self.coordinator.data:
            return None
        dev = self.coordinator.data.get("devices", {}).get(self._device_mac)
        if dev is None:
            return None
        return self.entity_description.value_fn(dev)


# ---------------------------------------------------------------------------
# Platform setup
# ---------------------------------------------------------------------------


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities, including dynamic per-device entities."""
    coordinator: UnifiNetworkDataUpdateCoordinator = entry.runtime_data

    # When the native UniFi integration is absent, enable all per-device entities
    # by default so sub-devices are not created with every sensor disabled.
    # entity_registry_enabled_default is only evaluated on first registration, so
    # this reflects the environment at the time of initial setup or reload.
    standalone = "unifi" not in hass.config_entries.async_domains()
    device_mode = entry.options.get(CONF_UNIFI_DEVICE_MODE, DEFAULT_UNIFI_DEVICE_MODE)
    disabled_eps = disabled_endpoints(entry.options)
    excluded = set() if dual_wan_enabled(entry.options) else single_wan_excluded_keys()

    entities: list[SensorEntity] = []

    # Static gateway sensors (skip those whose feature toggle is off, or whose
    # WAN2/load-balance key is excluded when dual-WAN monitoring is off)
    entities.extend(
        UnifiGatewaySensor(coordinator, entry, desc, desc.key, standalone)
        for desc in GATEWAY_SENSORS
        if _ENDPOINT_BY_KEY.get(desc.key) not in disabled_eps
        and desc.key not in excluded
    )

    # Static network health sensors
    entities.extend(
        UnifiHealthSensor(coordinator, entry, desc, f"health_{desc.key}")
        for desc in HEALTH_SENSORS
        if f"health_{desc.key}" not in excluded
    )

    # Dynamic device sensors from first coordinator data snapshot (per device mode)
    known_macs: set[str] = set()
    if coordinator.data:
        for mac, dev in coordinator.data.get("devices", {}).items():
            known_macs.add(mac)
            entities.extend(
                UnifiDeviceSensor(coordinator, entry, desc, mac, standalone)
                for desc in _device_descs(dev.get("type"), device_mode)
            )

    async_add_entities(entities)

    # Subscribe to coordinator to add entities for new devices discovered later
    @callback
    def _handle_coordinator_update() -> None:
        if not coordinator.data:
            return
        new_entities: list[SensorEntity] = []
        for mac, dev in coordinator.data.get("devices", {}).items():
            if mac in known_macs:
                continue
            known_macs.add(mac)
            new_entities.extend(
                UnifiDeviceSensor(coordinator, entry, desc, mac, standalone)
                for desc in _device_descs(dev.get("type"), device_mode)
            )
        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_handle_coordinator_update))
