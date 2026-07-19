# UniFi Network Monitor Integration - Entity Manifest

## Split Structure Information

This document is split into two logical parts:

- **Part I: Base Gateway & Network Entities**: The default virtual devices (comprising 128 entities across the Alerts, Gateway, Internet, Security, Speedtest, Status, and System sub-devices) present in standard gateway-monitoring mode.
- **Part II: Dynamic UniFi Devices (APs & Switches)**: Dynamic sensor entities generated for each physical UniFi Access Point and Switch monitored by the integration (~20 devices, adding ~160 entities when enabled).

> **🔑 API-key-only sensors:** rows marked **_API-key only_** in the Notes column are served by the UniFi Integration (v3) API, which cannot be reached with username/password auth. Under username/password these seven sensors (Rules Active/Configured/Disabled, VPN Connections Active/Total, WAN1/WAN2 Name) are permanently `unknown`. Use an API key to enable them.

---

## Part I: Base Gateway & Network Entities

> **Grouping note:** Sub-devices below match the **actual Home Assistant device cards** (the `sensor.unifi_network_<group>_…` entity-ID prefix a user sees on a default install), verified live against a UDM Pro.
>
> The default sub-device names are **UniFi Network Alerts / Gateway / Internet / Security / Speedtest / Status / System**; counts are for the base scenario: **128 entities** = Alerts 4 + Gateway 18 + Internet 39 + Security 20 + Speedtest 14 + Status 23 + System 10.
>
> **Enabled vs disabled — depends on HA Core UniFi:** the 128 registered entities are the same either way; only the enabled-by-default count differs.
>
> - **Without Core UniFi (standalone):** **105 enabled / 23 disabled** (verified live 2026-07-17; the Integration Health sensor is the only addition since the prior manifest check). Per card, enabled / total: Alerts 4/4, Gateway 11/18, Internet 34/39, Security 20/20, Speedtest 14/14, Status 12/23, System 10/10.
> - **With Core UniFi installed:** **97 enabled / 29 disabled** — six gateway diagnostics (rows tagged _Standalone-only enabled_ in §2: `cpu`, `ram`, `cpu_temp`, `board_temp`, `uptime`, `update_available`) revert to disabled-by-default when Core is present, so the Gateway card reads 5/18. Core already provides the gateway's CPU/memory; the temperatures are Monitor-only but kept off to avoid cluttering the merged gateway card (enable manually if wanted).
>
> The 23 always-disabled rows are the ones marked _Disabled by default_ (Gateway 7 SFP/storage, Internet 5, Status 11).

### 1. Alerts Sub-Device (4 Entities)

_Group: `alerts`_

| Name | Key | Type | Unit | Category | Notes |
| :-- | :-- | :-- | :-- | :-- | :-- |
| High Sev3 Qty Last 24h | `gateway_alerts_high_24h` | Sensor | — | — |  |
| Last High Sev3 | `gateway_last_high` | Sensor | — | — |  |
| Last Very High Sev4 | `gateway_last_very_high` | Sensor | — | — |  |
| Very High Sev4 Qty Last 24h | `gateway_alerts_very_high_24h` | Sensor | — | — |  |
| Get alerts | `get_alerts` | Service | — | — |  |

### 2. Gateway Sub-Device (18 Entities)

_Group: `gateway`_

| Name | Key | Type | Unit | Category | Notes |
| :-- | :-- | :-- | :-- | :-- | :-- |
| Application Version | `gateway_application_version` | Sensor | — | Diagnostic | UniFi Network application version. |
| Board Temperature | `gateway_board_temp` | Sensor | °C | Diagnostic | _Standalone-only enabled_ (disabled by default when Core UniFi present). |
| CPU temperature | `gateway_cpu_temp` | Sensor | °C | Diagnostic | _Standalone-only enabled_ (disabled by default when Core UniFi present). |
| CPU utilization | `gateway_cpu` | Sensor | % | Diagnostic | _Standalone-only enabled_ (disabled by default when Core UniFi present). |
| Last Backup | `gateway_last_backup` | Sensor | — | Diagnostic |  |
| Memory utilization | `gateway_ram` | Sensor | % | Diagnostic | _Standalone-only enabled_ (disabled by default when Core UniFi present). |
| Storage Total | `gateway_storage_size` | Sensor | GB | Diagnostic | **Disabled by default.** No LTS (no state_class). Other display units may be used (e.g. GB). |
| Storage Used | `gateway_storage_used` | Sensor | GB | Diagnostic |  |
| Storage Utilization | `gateway_storage_used_pct` | Sensor | % | Diagnostic | Storage used as a percentage of total. |
| UniFi OS Version | `health_wan_gw_version` | Sensor | — | Diagnostic |  |
| Update Available | `gateway_update_available` | Binary Sensor | — | Diagnostic | _Standalone-only enabled_ (disabled by default when Core UniFi present). |
| Uptime | `gateway_uptime` | Sensor | — | Diagnostic | _Standalone-only enabled_ (disabled by default when Core UniFi present). |
| WAN1 SFP Part Number | `gateway_wan1_sfp_part` | Sensor | — | Diagnostic | **Disabled by default.** Data may not be available in all configurations. |
| WAN1 SFP Serial Number | `gateway_wan1_sfp_serial` | Sensor | — | Diagnostic | **Disabled by default.** Data may not be available in all configurations. |
| WAN1 SFP Vendor | `gateway_wan1_sfp_vendor` | Sensor | — | Diagnostic | **Disabled by default.** Data may not be available in all configurations. |
| WAN2 SFP Part Number | `gateway_wan2_sfp_part` | Sensor | — | Diagnostic | **Disabled by default.** |
| WAN2 SFP Serial Number | `gateway_wan2_sfp_serial` | Sensor | — | Diagnostic | **Disabled by default.** |
| WAN2 SFP Vendor | `gateway_wan2_sfp_vendor` | Sensor | — | Diagnostic | **Disabled by default.** |

### 3. Internet Sub-Device (39 Entities)

_Group: `internet`_

| Name | Key | Type | Unit | Category | Notes |
| :-- | :-- | :-- | :-- | :-- | :-- |
| ISP Name | `health_wan_isp_name` | Sensor | — | Diagnostic |  |
| ISP Organization | `health_wan_isp_org` | Sensor | — | — | **Disabled by default.** |
| Internet Connected | `gateway_internet` | Binary Sensor | — | Diagnostic |  |
| Internet Drops | `health_www_drops` | Sensor | — | Diagnostic |  |
| Internet Latency | `health_www_latency` | Sensor | ms | Diagnostic |  |
| Internet OK | `health_www_ok` | Binary Sensor | — | Diagnostic | **Disabled by default.** |
| Internet Online Since | `health_www_boot_time` | Sensor | — | Diagnostic |  |
| Internet Uptime Duration | `health_www_uptime` | Sensor | s | Diagnostic | **Disabled by default.** Other display units may be used (e.g. s). No LTS (no state_class). |
| Month Total | `gateway_month_total` | Sensor | GB | — |  |
| WAN1 Active Uplink | `gateway_wan1_active` | Binary Sensor | — | Diagnostic |  |
| WAN1 Availability | `health_wan1_availability` | Sensor | % | Diagnostic |  |
| WAN1 Last Restart | `health_wan1_boot_time` | Sensor | — | Diagnostic |  |
| WAN1 Latency | `health_wan1_latency_avg` | Sensor | ms | Diagnostic |  |
| WAN1 Link Connected | `gateway_wan1_up` | Binary Sensor | — | Diagnostic |  |
| WAN1 Local IP Address | `gateway_wan1_local_ip` | Sensor | — | Diagnostic |  |
| WAN1 Month Download | `gateway_wan1_month_rx` | Sensor | GB | — |  |
| WAN1 Month Total | `gateway_wan1_month_total` | Sensor | GB | — |  |
| WAN1 Month Upload | `gateway_wan1_month_tx` | Sensor | GB | — |  |
| WAN1 Name | `gateway_wan1_interface_name` | Sensor | — | Diagnostic | **_API-key only_** (v3 API; `unknown` under username/password). |
| WAN1 Public IP Address | `gateway_wan1_public_ip` | Sensor | — | Diagnostic |  |
| WAN1 Today Download | `gateway_wan1_today_rx` | Sensor | GB | — | In LTS (total_increasing). |
| WAN1 Today Total | `gateway_wan1_today_total` | Sensor | GB | — | In LTS (total_increasing). |
| WAN1 Today Upload | `gateway_wan1_today_tx` | Sensor | GB | — | In LTS (total_increasing). |
| WAN1 Uptime Duration | `health_wan1_uptime` | Sensor | s | Diagnostic | **Disabled by default.** Other display units may be used (e.g. s). No LTS (no state_class). |
| WAN2 Active Uplink | `gateway_wan2_active` | Binary Sensor | — | Diagnostic |  |
| WAN2 Availability | `health_wan2_availability` | Sensor | % | Diagnostic |  |
| WAN2 Last Restart | `health_wan2_boot_time` | Sensor | — | Diagnostic |  |
| WAN2 Latency | `health_wan2_latency_avg` | Sensor | ms | Diagnostic |  |
| WAN2 Link Connected | `gateway_wan2_up` | Binary Sensor | — | Diagnostic |  |
| WAN2 Local IP Address | `gateway_wan2_local_ip` | Sensor | — | Diagnostic |  |
| WAN2 Month Download | `gateway_wan2_month_rx` | Sensor | GB | — |  |
| WAN2 Month Total | `gateway_wan2_month_total` | Sensor | GB | — |  |
| WAN2 Month Upload | `gateway_wan2_month_tx` | Sensor | GB | — |  |
| WAN2 Name | `gateway_wan2_interface_name` | Sensor | — | Diagnostic | **_API-key only_** (v3 API; `unknown` under username/password). |
| WAN2 Public IP Address | `gateway_wan2_public_ip` | Sensor | — | Diagnostic |  |
| WAN2 Today Download | `gateway_wan2_today_rx` | Sensor | GB | — | In LTS (total_increasing). |
| WAN2 Today Total | `gateway_wan2_today_total` | Sensor | GB | — | In LTS (total_increasing). |
| WAN2 Today Upload | `gateway_wan2_today_tx` | Sensor | GB | — | In LTS (total_increasing). |
| WAN2 Uptime Duration | `health_wan2_uptime` | Sensor | s | Diagnostic | **Disabled by default.** Other display units may be used (e.g. s). No LTS (no state_class). |

### 4. Security Sub-Device (19 Entities)

_Group: `security`_

| Name | Key | Type | Unit | Category | Notes |
| :-- | :-- | :-- | :-- | :-- | :-- |
| Ad Blocking | `gateway_ad_blocking` | Binary Sensor | — | Diagnostic |  |
| Apply AP ignore list | `rogue_apply_ap_ignore` | Switch | — | Config |  |
| Apply SSID ignore list | `rogue_apply_ssid_ignore` | Switch | — | Config |  |
| Honeypot | `gateway_honeypot` | Binary Sensor | — | Diagnostic |  |
| Rogue AP Proximity Alert | `gateway_rogue_proximity_alert` | Binary Sensor | — | Diagnostic |  |
| Rogue APs All 24h | `gateway_rogue_raw_24h` | Sensor | — | Diagnostic |  |
| Rogue APs New 24h | `gateway_rogue_new_24h` | Sensor | — | — | BSSIDs first seen by HA within 24h; persistent history, LTS-enabled. |
| Rogue Access Points | `gateway_rogue_ap_count` | Sensor | — | — |  |
| Rogue Detection Period | `rogue_period` | Select | — | Config |  |
| Rogue Proximity Threshold | `gateway_rogue_proximity_threshold` | Number | dBm | Config |  |
| Rules Active | `gateway_rules_active` | Sensor | — | — | **_API-key only_** (v3 API; `unknown` under username/password). |
| Rules Configured | `gateway_rules_configured` | Sensor | — | Diagnostic | **_API-key only_** (v3 API; `unknown` under username/password). |
| Rules Disabled | `gateway_rules_disabled` | Sensor | — | — | **_API-key only_** (v3 API; `unknown` under username/password). |
| Show 2.4 GHz rogues | `rogue_show_24ghz` | Switch | — | Config |  |
| Show 5 GHz rogues | `rogue_show_5ghz` | Switch | — | Config |  |
| Strongest Rogue RSSI | `gateway_strongest_rogue_rssi` | Sensor | dBm | — | Data may not be available in all configurations. |
| Strongest Rogue SSID | `gateway_strongest_rogue_ssid` | Sensor | — | — | `rogue_aps` attribute carries the full rogue-AP list. |
| Threat Management Mode | `gateway_ips_mode` | Sensor | — | Diagnostic |  |
| VPN Connections Active | `gateway_vpn_connections_active` | Sensor | — | — | **_API-key only_** (v3 API; `unknown` under username/password). |
| VPN Connections Total | `gateway_vpn_connections_total` | Sensor | — | Diagnostic | **_API-key only_** (v3 API; `unknown` under username/password). |
| Add Rogue Ignore | `add_rogue_ignore` | Service | — | — |  |
| Clear Rogue AP History | `clear_rogue_history` | Service | — | — |  |
| Get Rogue APs | `get_rogue_aps` | Service | — | — |  |
| Remove Rogue Ignore | `remove_rogue_ignore` | Service | — | — |  |
| Set Rogue Ignore | `set_rogue_ignore` | Service | — | — |  |

### 5. Speedtest Sub-Device (14 Entities)

_Group: `speedtest`_

| Name | Key | Type | Unit | Category | Notes |
| :-- | :-- | :-- | :-- | :-- | :-- |
| Last Run Problem | `health_speedtest_pass` | Binary Sensor | — | Diagnostic |  |
| Last Run Status | `health_www_speedtest_status` | Sensor | — | Diagnostic |  |
| WAN1 Download | `gateway_wan1_speedtest_download` | Sensor | Mbit/s | — |  |
| WAN1 Last Run | `gateway_wan1_speedtest_lastrun` | Sensor | — | Diagnostic |  |
| WAN1 Monitoring Period | `health_wan1_time_period` | Sensor | h | Diagnostic | No LTS (no state_class). |
| WAN1 Ping | `gateway_wan1_speedtest_ping` | Sensor | ms | Diagnostic | In LTS (measurement). |
| WAN1 Run | `gateway_wan1_speedtest` | Button | — | — | Data may not be available in all configurations. |
| WAN1 Upload | `gateway_wan1_speedtest_upload` | Sensor | Mbit/s | — |  |
| WAN2 Download | `gateway_wan2_speedtest_download` | Sensor | Mbit/s | — |  |
| WAN2 Last Run | `gateway_wan2_speedtest_lastrun` | Sensor | — | Diagnostic |  |
| WAN2 Monitoring Period | `health_wan2_time_period` | Sensor | h | Diagnostic | No LTS (no state_class). |
| WAN2 Ping | `gateway_wan2_speedtest_ping` | Sensor | ms | Diagnostic | In LTS (measurement). |
| WAN2 Run | `gateway_wan2_speedtest` | Button | — | — | Data may not be available in all configurations. |
| WAN2 Upload | `gateway_wan2_speedtest_upload` | Sensor | Mbit/s | — |  |

### 6. Status Sub-Device (23 Entities)

_Group: `status`_

| Name | Key | Type | Unit | Category | Notes |
| :-- | :-- | :-- | :-- | :-- | :-- |
| Access Points | `health_wlan_num_ap` | Sensor | — | Diagnostic | **Disabled by default.** |
| Adopted Devices | `health_lan_num_adopted` | Sensor | — | Diagnostic | **Disabled by default.** |
| Configured VLANs | `gateway_configured_vlans` | Sensor | — | Diagnostic | **Disabled by default.** |
| Guest Users | `gateway_guest_user_count` | Sensor | — | — | **Disabled by default.** |
| House WiFi Status | `gateway_wifi_ssid_status` | Binary Sensor | — | Diagnostic |  |
| IoT-Secure WiFi Status | `gateway_wifi_ssid_status` | Binary Sensor | — | Diagnostic |  |
| LAN IoT Devices | `health_lan_num_iot` | Sensor | — | Diagnostic | **Disabled by default.** |
| LAN OK | `health_lan_ok` | Binary Sensor | — | Diagnostic | **Disabled by default.** |
| NetCentral WiFi Status | `gateway_wifi_ssid_status` | Binary Sensor | — | Diagnostic |  |
| Network Problem | `health_all_ok` | Binary Sensor | — | Diagnostic |  |
| Switches | `health_lan_num_sw` | Sensor | — | Diagnostic | **Disabled by default.** |
| Total Devices | `health_wan_num_sta` | Sensor | — | — |  |
| VLANs Active | `gateway_vlans_active` | Sensor | — | — |  |
| VLANs Total | `gateway_vlans_total` | Sensor | — | Diagnostic |  |
| VPN Status | `health_vpn_status` | Sensor | — | Diagnostic | **Disabled by default.** Data may not be available in all configurations. |
| WAN OK | `health_wan_ok` | Binary Sensor | — | Diagnostic | **Disabled by default.** |
| WiFi Devices | `health_wlan_num_user` | Sensor | — | — |  |
| WiFi Guests | `health_wlan_num_guest` | Sensor | — | Diagnostic |  |
| WiFi IoT Devices | `health_wlan_num_iot` | Sensor | — | Diagnostic | **Disabled by default.** |
| WiFi Networks Active | `gateway_wifi_networks_active` | Sensor | — | — |  |
| WiFi Networks Total | `gateway_wifi_networks_total` | Sensor | — | Diagnostic |  |
| WiFi OK | `health_wlan_ok` | Binary Sensor | — | Diagnostic | **Disabled by default.** |
| Wired Devices | `health_lan_num_user` | Sensor | — | — |  |

### 7. System Sub-Device (9 Entities)

_Group: `system`_

| Name | Key | Type | Unit | Category | Notes |
| :-- | :-- | :-- | :-- | :-- | :-- |
| Clean Up Unused Entities | `cleanup_unused_entities` | Button | — | Config |  |
| Integration Health | `integration_health` | Binary Sensor | — | Diagnostic | Problem sensor; on when the integration self-diagnoses a degraded/malformed state. |
| Last Updated | `gateway_last_updated` | Sensor | — | Diagnostic |  |
| Multi-WAN Mode | `gateway_wan_mode` | Sensor | — | Diagnostic |  |
| Pause polling | `pause_polling` | Switch | — | Config |  |
| Polling Interval | `gateway_scan_interval` | Number | s | Config |  |
| Refresh Now | `gateway_refresh` | Button | — | Config |  |
| WAN1 Load Balance | `gateway_wan1_weight` | Sensor | % | — |  |
| WAN1 Load Balance Weight | `wan1_load_balance_weight` | Number | % | Config |  |
| WAN2 Load Balance | `gateway_wan2_weight` | Sensor | % | — |  |
| Clean up unused entities | `cleanup_unused_entities` | Service | — | — |  |

> **Actions (not entities):** seven registered services are **not** part of the 128 entity count — `unifi_network_monitor.cleanup_unused_entities` (the `dry_run` counterpart to the **Clean Up Unused Entities** button), `get_alerts` (on-demand system-log query — Alerts group), `get_rogue_aps` (on-demand rogue-AP query — Security group), `clear_rogue_history` (reset the persistent rogue history), and `add_rogue_ignore` / `remove_rogue_ignore` / `set_rogue_ignore` (manage the Ignore Rogue SSIDs / Ignore detecting APs lists from automations). The `get_*` actions fetch their own data, so they work even when the matching sensor group is off.
>
> **Bus events (not entities):** `unifi_network_monitor_new_alert` (per newly-seen HIGH/VERY_HIGH alert) and `unifi_network_monitor_new_rogue_ap` (per newly-seen rogue BSSID) fire on the bus for automations. They only fire while the Alerts / Security group is enabled.
>
> **Repair issues (Settings → Repairs):** `site_resolution_failed` (v3 site unreachable — VPN/firewall/WAN-name sensors unavailable) and `schema_drift_detected` (a controller update appears to have changed the data format; some sensors may be wrong). Both are also reflected in the **Integration Health** sensor's attributes.
>
> **`about` attribute:** ~20 entities carry an unrecorded `about:` attribute — a one-line explanation shown in More Info / Developer Tools but excluded from the recorder (`_unrecorded_attributes`). The Strongest Rogue SSID `rogue_aps` list attribute is capped at 25 (`rogue_aps_truncated` flags overflow) and is also unrecorded.

## Part II: Dynamic UniFi Devices (APs & Switches)

These entities are **opt-in**, controlled by the _UniFi device (Access Point & Switch) sensors_ dropdown. One sub-device is created per adopted AP/switch; the entity set depends on the mode:

- **Don't add** (`none`, default): nothing. 7 base sub-devices only.
- **AP Satisfaction Score only** (`satisfaction_only`, offered only when Core UniFi is installed): **3 per AP** — Satisfaction Score + 2.4/5 GHz Score — and **0 for switches** (switches have no score, so no switch sub-devices are created).
- **Add all device sensors** (`all`): **11 per AP** and **6 per switch** (§6, §7 below).

**Enabled-by-default depends on Core UniFi** (whichever mode creates the entity):

| Mode (rig: 8 APs, 12 switches) | Devices | Registered | Enabled — no Core | Enabled — Core present |
| :-- | :-: | :-: | :-: | :-: |
| Don't add | 7 | 128 | 105 | 99 |
| AP Satisfaction Score only | 15 | 152 | n/a¹ | 107 |
| Add all device sensors | 27 | 288 | 265 | 107 |

¹ Satisfaction-only is only offered when Core is present. **Without Core**, all created per-device entities are enabled; **with Core**, only the AP **Satisfaction Score** is enabled (band scores + everything else, and all 6 switch sensors, are disabled — 1 enabled per AP, 0 per switch). So under Core, "Add all" enables the _same_ 105 as "Satisfaction only" — the extra 152 per-device entities are all disabled clutter. The **Don't add** base row is verified live (2026-07-14, standalone = 126/103); the per-device rows carry the prior live rig validation plus the +10 base delta (Alerts 4 + Rogue APs All 24h + 4 rogue switches + Rogue Detection Period select), which are all enabled-by-default and mode-independent. The `Default (Core present)` column in §8/§9 reflects the per-entity defaults.

> **Entity IDs:** each physical device is its own HA device card, so entity IDs use the **device name** as the prefix (e.g. `sensor.unifi_ap_ac_pro_garage_satisfaction_score`), **not** the `unifi_network_…` base prefix. The duplicate-of-core sensors get a `_mon` suffix on their entity ID (keeping the display name) so they don't collide with Core's equivalents on the merged card — on an **AP**: Clients, CPU, Memory, Uptime → `…_mon`; on a **switch**: Clients, CPU, Memory, Uptime → `…_mon`. The switch "Clients" sensor uses the `ports_used` key (value = `num_sta`, the client count), but its entity_id stem is `clients`, so it becomes `…_clients_mon` (not `…_ports_used_mon` or a `_2` collision).

### 8. Access Point Sub-Device (11 Entities per AP)

_Group: `ap`_

| Name | Key | Type | Unit | Default (Core present) | Notes |
| :-- | :-- | :-- | :-- | :-- | :-- |
| Clients | `clients` | Sensor | — | Disabled | Entity ID gets `_mon` suffix. |
| Guests | `guests` | Sensor | — | Disabled |  |
| 2.4 GHz Clients | `clients_wifi0` | Sensor | — | Disabled |  |
| 5 GHz Clients | `clients_wifi1` | Sensor | — | Disabled |  |
| Satisfaction Score | `score` | Sensor | % | **Enabled** | In LTS (measurement). |
| 2.4 GHz Score | `score_wifi0` | Sensor | % | Disabled | In LTS (measurement). |
| 5 GHz Score | `score_wifi1` | Sensor | % | Disabled | In LTS (measurement). |
| CPU utilization | `cpu` | Sensor | % | Disabled | Entity ID gets `_mon` suffix. |
| Memory utilization | `ram` | Sensor | % | Disabled | Entity ID gets `_mon` suffix. |
| Uptime | `uptime` | Sensor | — | Disabled | Entity ID gets `_mon` suffix. |
| Update Available | `update_available` | Binary Sensor | — | Disabled |  |

---

### 9. Switch Sub-Device (6 Entities per Switch)

_Group: `switch`_

| Name | Key | Type | Unit | Default (Core present) | Notes |
| :-- | :-- | :-- | :-- | :-- | :-- |
| Clients | `ports_used` | Sensor | — | Disabled | Value is `num_sta` (client count). Entity ID gets `_mon` suffix → `…_clients_mon`. |
| CPU utilization | `cpu` | Sensor | % | Disabled | Entity ID gets `_mon` suffix. |
| Memory utilization | `ram` | Sensor | % | Disabled | Entity ID gets `_mon` suffix. |
| Uptime | `uptime` | Sensor | — | Disabled | Entity ID gets `_mon` suffix. |
| Model | `model` | Sensor | — | Disabled |  |
| Update Available | `update_available` | Binary Sensor | — | Disabled |  |

---

## Long Term Statistics (LTS) Coverage

Home Assistant records **Long Term Statistics** for a numeric sensor **only when it declares a `state_class`** (`measurement`, `total`, or `total_increasing`). Numeric sensors with **no** `state_class` still show a live value and short-term history, but are **excluded from LTS** (no hourly min/mean/max roll-up, and they cannot be used in the Statistics/Energy graphs). Text, IP, version, mode and timestamp sensors are never LTS candidates and are not listed here.

Most numeric sensors carry a `state_class` and **are** in LTS — CPU/RAM/temperatures, signal/RSSI, latency, Storage **Utilization (%)**, the **active/primary** counts (user & guest clients, active VLANs/VPNs/WiFi networks, active & disabled firewall rules, rogue APs), WAN1 Load-Balance weight, **daily _and_ monthly** data usage, and speedtest **download / upload / ping**.

### LTS is a deliberately-curated set — the sibling asymmetry is intentional

The numeric sensors **left out of LTS** below are **not** an oversight. LTS is curated to avoid **redundant or near-static** long-term series (each one is an hourly-rolled-up table in the recorder DB), so when two sensors carry the same information we give a `state_class` to the **one that changes / is primary** and omit its sibling:

- **`storage_used_pct` (Utilization %) is in LTS; the raw `storage_used`/`storage_size` bytes are not** — the % carries the trend.
- **`wan1_weight` is in LTS; `wan2_weight` is not** — they sum to 100 %, so one series reconstructs the other.
- **`rules_active` / `rules_disabled` are in LTS; `rules_configured` (the total) is not** — the changeable counts carry the signal.
- **`*_active` (WiFi networks / VLANs / VPN connections) are in LTS; the `*_total` siblings are not** — the totals are near-static config.
- **Primary `num_user` / `num_guest` client counts are in LTS; the secondary `num_iot` / `num_ap` / `num_sw` / `num_adopted` counts are not.**
- **Availability % and uptime-seconds durations are omitted** — a `boot_time` **timestamp** already marks "since when", so a duration LTS series would be redundant.

Do **not** "fix" these by adding a `state_class` — the omissions are the design. A user who genuinely wants one of them in LTS can add a `state_class` override via HA's Manual Customization (documented in the README LTS tip).

**Numeric sensors with no `state_class` (not in LTS):**

| Group | Sensors | Key(s) |
| :-- | :-- | :-- |
| Raw storage bytes | Storage Used, Storage Total | `storage_used`, `storage_size` |
| WAN availability & durations | WAN1/2 Availability, WAN1/2 & Internet Uptime, WAN1/2 Time Period | `wan{1,2}_availability`, `health_wan{1,2}_uptime`, `health_www_uptime`, `health_wan{1,2}_time_period` |
| Redundant / total siblings | WAN2 Load Balance, Firewall Rules Configured, WiFi Networks Total, VLANs Total & Configured, VPN Connections Total | `wan2_weight`, `rules_configured`, `wifi_networks_total`, `vlans_total`, `configured_vlans`, `vpn_connections_total` |
| Secondary client/device counts | WiFi IoT Clients, WiFi AP count, LAN IoT Clients, LAN Switch count, Adopted Devices | `wlan_num_iot`, `wlan_num_ap`, `lan_num_iot`, `lan_num_sw`, `lan_num_adopted` |

> **Note:** the AP **Satisfaction Score** sensors, the **daily "Today" usage** sensors, and **WAN Ping** _do_ carry a `state_class` and **are in LTS** (an earlier revision of this doc listed them as excluded — corrected 2026-07-17).

---

## Debugging & Maintenance Reference

### Identity Strategy

- **Base Unique ID**: The MAC address of the gateway (normalized to lowercase, with colons, or as stored).
- **Entity Unique ID**: `{{gateway_mac}}_{{key}}`.
- **Device Identifiers**: `{{DOMAIN}}_{{gateway_mac}}_{{group}}`.

### Coexistence with HA Core UniFi Network

- **Gateway card merges.** The Gateway sub-device uses `connections={(CONNECTION_NETWORK_MAC, gateway_mac)}` (`build_gateway_device_info`), so when Core UniFi is installed HA **merges** it into Core's gateway device card. The merged card adopts **Core's** device name (e.g. `UDM-Pro`) and firmware string (Core reports the UniFi OS version, e.g. `5.1.19.33549`, where standalone shows the Network-application version). Expected and intended.
- **Other sub-devices stay separate.** Alerts / Internet / Security / Speedtest / Status / System use `identifiers` only (no MAC connection), so they remain distinct Monitor cards linked to the gateway via `via_device`. Per-physical-device (AP/switch) cards also merge by MAC (`build_unifi_device_info`).
- **Counting caveat.** Core UniFi names its **own** controller device "UniFi Network", so its firewall/traffic-rule switches register as `switch.unifi_network_*`. A substring search for `unifi_network` therefore returns Core's entities too — filter by `platform: unifi_network_monitor` to count only this integration's entities (Monitor's only switch is `…_system_pause_polling`).

### Suggested Display Units & Precision

Sensors are stored in their canonical **native** unit (so long-term statistics and guard bands are stable) but carry a display hint via `suggested_unit_of_measurement` / `suggested_display_precision`. The value shown in the UI can still be overridden per-entity.

---

## Version Control

- **v1.0.0** (2026-07-08) - Initial version. Created based on the exact entities registered for the UniFi Network Monitor.
- **v1.1.0** (2026-07-08) - Restructured into Split-Part structure separating base entities from dynamic UniFi device entities. Added AP and Switch sub-device entity tables.
- **v1.2.0** (2026-07-08) - Added the Long Term Statistics (LTS) Coverage section and flagged the 17 numeric sensors (14 base + 3 per-AP) that lack a `state_class` and are therefore excluded from LTS.
- **v1.3.0** (2026-07-08) - Corrected the sub-device grouping to match the **actual Home Assistant device cards** (verified live on a UDM Pro), replacing the earlier logical grouping. Real per-card counts: Gateway 18, Internet 39, Speedtest 14, Status 33, System 12 (= 116). Removed the service row from the System entity table (documented separately as a non-entity action).
- **v1.4.0** (2026-07-08) - Verified against a fresh **default** install (entity-ID prefix `unifi_network_`, not the earlier `udmp_` which was a user rename). Confirmed **93 enabled by default + 23 disabled-by-default = 116** registered, cross-checked entity-by-entity via the registry (`disabled_by: integration`). Added the enabled/disabled split to the grouping note.
- **v1.5.0** (2026-07-08) - Renamed the storage-percentage sensor `Storage Used (%)` → **`Storage Utilization`** (entity_id `…_storage_utilization`) to remove the `…_storage_used_2` entity-ID collision with `Storage Used` and to parallel the `CPU utilization` / `Memory utilization` sensors. `key`/`unique_id` (`storage_used_pct`) unchanged.
- **v1.6.0** (2026-07-08) - Part II corrected against a live standalone (no Core UniFi) "Add all" install: fixed per-device header counts (AP **10 → 11**, Switch **4 → 6**); replaced the ambiguous _Disabled by default_ column with _Default (Core present)_ and a note that standalone enables all 11/6; documented the device-name entity-ID prefix and the `_mon` suffix rules (incl. the switch `ports_used` exception).
- **v1.8.0** (2026-07-08) - Validated the **Satisfaction-only** and **Add-all** per-device modes with Core present (live). Added the per-mode device/entity/enabled table (Don't add / Satisfaction only / Add all × no-Core / Core). Fixed the switch **Clients** `_2` collision: `ports_used` now maps to the `_mon` stem `clients` (`…_clients_mon`) — see `_DUPLICATES_CORE_KEYS` in `sensor.py`.
- **v1.7.0** (2026-07-08) - Validated the **default install on top of HA Core UniFi** (live). Documented that the base enabled count is **93 (no Core) / 87 (Core present)** — six gateway diagnostics (`cpu`, `ram`, `cpu_temp`, `board_temp`, `uptime`, `update_available`) are _Standalone-only enabled_; tagged those §1 rows. Added a **Coexistence with HA Core UniFi** section: gateway card merges into Core's device (adopting Core's name/firmware), other sub-devices stay separate, and the `switch.unifi_network_*` counting caveat (Core names its controller "UniFi Network").
- **v2.0.0** (2026-07-14) - Restructured to **7 sub-devices** for the Alerts + rogue-action work: new **Alerts** sub-device (4 sensors) and new **Security** sub-device (19 entities — rogue/threat/VPN/firewall relocated off Status & System, plus **Rogue APs All 24h**, the rogue control switches, and the Rogue Detection Period select). Base grew **116 → 126**. Re-verified live on a fresh **standalone** default install (2026-07-14): **103 enabled / 23 disabled**; per-card enabled/total Alerts 4/4, Gateway 11/18, Internet 34/39, Security 19/19, Speedtest 14/14, Status 12/23, System 9/9. Updated the per-mode table (base +10, all enabled-by-default), added the Actions/Events/`about`-attribute note, and corrected the WAN Ping LTS rows (Speedtest, not System).
- **v2.1.0** (2026-07-17) - Added 7 undocumented services as rows in the sub-device entity tables (Alerts, Security, System) to match live discovery. Appended data availability note to Strongest Rogue RSSI.
- **v2.2.0** (2026-07-17) - Rogue expansion / history / self-diagnosis: **Rogue APs New 24h** sensor (Security) + **Integration Health** binary sensor (System); base **127 → 128**. **LTS Coverage section rewritten and corrected against code** — the previous list wrongly excluded the AP Satisfaction Scores, the daily "Today" usage sensors, and WAN Ping (all _do_ carry a `state_class`); those 11 per-row Notes flags were flipped to "In LTS". Documented the **deliberate LTS curation policy** (redundant/derivable/near-static siblings are intentionally omitted — e.g. `storage_used`/`_size` vs `storage_used_pct`, `wan2_weight` vs `wan1_weight`, `*_total` vs `*_active`, secondary `num_*` counts, availability/uptime-seconds vs the `boot_time` timestamp).
