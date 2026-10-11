# UniFi Network Monitor Integration - Entity Manifest

## Split Structure Information

This document is split into two logical parts:

- **Part I: Base Gateway & Network Entities**: The default virtual devices (Alerts, Gateway, Internet, Security, Speedtest, Status, and System sub-devices) present in standard gateway-monitoring mode.
- **Part II: Dynamic UniFi Devices (APs & Switches)**: Dynamic sensor entities generated for each physical UniFi Access Point and Switch monitored by the integration (~20 devices, adding ~160 entities when enabled).

> **🔑 API-key-only sensors:** rows marked **_API-key only_** in the Notes column are served by the UniFi Integration (v3) API, which cannot be reached with username/password auth. Under username/password these seven sensors (Rules Active/Configured/Disabled, VPN Connections Active/Total, WAN1/WAN2 Name) are permanently `unknown`. Use an API key to enable them.
>
> **🔑 What the `Key` column holds — read this before comparing it to anything.** It is the entity description's **`translation_key`** (`gateway_board_temp`), **not** its `key` (`board_temp`), and not the entity ID slug (`gateway_board_temperature`). Those are three different identifier spaces and they do not diff against each other.
>
> That matters because the mismatch is **silent**: comparing this column against `unique_id` (which is built from `key`, not `translation_key`) produces a plausible-looking delta that is entirely artificial. The mapping lives in the entity descriptions in source — `key=` beside `translation_key=` — and that is the only reliable way to line the two up.

---

## Part I: Base Gateway & Network Entities

<!-- GENERATED:start -->

## Summary

| Sub-Device | Entity Count | Description |
| :-- | :-- | :-- |
| **Alerts** | 4 | Alerts entities. |
| **Gateway** | 34 | Gateway entities. |
| **Internet** | 41 | Internet entities. |
| **Security** | 13 | Security entities. |
| **Speedtest** | 12 | Speedtest entities. |
| **Status** | 22 | Status entities. |
| **System** | 15 | System entities. |
| **Total** | **141** | Total static entities. |

## Alerts Sub-Device (4 Entities)

| Name | Key | Type | Unit | Category | Notes |
| :-- | :-- | :-- | :-- | :-- | :-- |
| High Sev3 Qty Last 24h | `alerts_high_24h` | Sensor | - | - | LTS: `measurement` |
| Very High Sev4 Qty Last 24h | `alerts_very_high_24h` | Sensor | - | - | LTS: `measurement` |
| Last High Sev3 | `last_high` | Sensor | - | - | - |
| Last Very High Sev4 | `last_very_high` | Sensor | - | - | - |

## Gateway Sub-Device (34 Entities)

| Name | Key | Type | Unit | Category | Notes |
| :-- | :-- | :-- | :-- | :-- | :-- |
| Update Available | `update_available` | Binary Sensor | - | Diagnostic | **Disabled by default.** |
| Update Available | `update_available` | Binary Sensor | - | Diagnostic | **Disabled by default.** |
| Application Version | `application_version` | Sensor | - | Diagnostic | - |
| Board Temperature | `board_temp` | Sensor | °C | Diagnostic | **Disabled by default.** LTS: `measurement` |
| Clients | `clients` | Sensor | - | Diagnostic | **Disabled by default.** LTS: `measurement` |
| 2.4 GHz Clients | `clients_wifi0` | Sensor | - | Diagnostic | **Disabled by default.** LTS: `measurement` |
| 5 GHz Clients | `clients_wifi1` | Sensor | - | Diagnostic | **Disabled by default.** LTS: `measurement` |
| CPU utilization | `cpu` | Sensor | % | Diagnostic | **Disabled by default.** LTS: `measurement` |
| CPU utilization | `cpu` | Sensor | % | Diagnostic | **Disabled by default.** LTS: `measurement` |
| CPU utilization | `cpu` | Sensor | % | Diagnostic | **Disabled by default.** LTS: `measurement` |
| CPU temperature | `cpu_temp` | Sensor | °C | Diagnostic | **Disabled by default.** LTS: `measurement` |
| Guests | `guests` | Sensor | - | Diagnostic | **Disabled by default.** LTS: `measurement` |
| Last Backup | `last_backup` | Sensor | - | Diagnostic | - |
| Model | `model` | Sensor | - | Diagnostic | **Disabled by default.** |
| Clients | `ports_used` | Sensor | - | Diagnostic | **Disabled by default.** LTS: `measurement` |
| Memory utilization | `ram` | Sensor | % | Diagnostic | **Disabled by default.** LTS: `measurement` |
| Memory utilization | `ram` | Sensor | % | Diagnostic | **Disabled by default.** LTS: `measurement` |
| Memory utilization | `ram` | Sensor | % | Diagnostic | **Disabled by default.** LTS: `measurement` |
| Satisfaction Score | `score` | Sensor | % | - | LTS: `measurement` |
| 2.4 GHz Score | `score_wifi0` | Sensor | % | - | **Disabled by default.** LTS: `measurement` |
| 5 GHz Score | `score_wifi1` | Sensor | % | - | **Disabled by default.** LTS: `measurement` |
| Storage Total | `storage_size` | Sensor | B | Diagnostic | **Disabled by default.** |
| Storage Used | `storage_used` | Sensor | B | Diagnostic | - |
| Storage Utilization | `storage_used_pct` | Sensor | % | Diagnostic | LTS: `measurement` |
| Uptime | `uptime` | Sensor | - | Diagnostic | **Disabled by default.** |
| Uptime | `uptime` | Sensor | - | Diagnostic | **Disabled by default.** |
| Uptime | `uptime` | Sensor | - | Diagnostic | **Disabled by default.** |
| WAN1 SFP Part Number | `wan1_sfp_part` | Sensor | - | Diagnostic | **Disabled by default.** |
| WAN1 SFP Serial Number | `wan1_sfp_serial` | Sensor | - | Diagnostic | **Disabled by default.** |
| WAN1 SFP Vendor | `wan1_sfp_vendor` | Sensor | - | Diagnostic | **Disabled by default.** |
| WAN2 SFP Part Number | `wan2_sfp_part` | Sensor | - | Diagnostic | **Disabled by default.** |
| WAN2 SFP Serial Number | `wan2_sfp_serial` | Sensor | - | Diagnostic | **Disabled by default.** |
| WAN2 SFP Vendor | `wan2_sfp_vendor` | Sensor | - | Diagnostic | **Disabled by default.** |
| UniFi OS Version | `wan_gw_version` | Sensor | - | Diagnostic | - |

## Internet Sub-Device (41 Entities)

| Name | Key | Type | Unit | Category | Notes |
| :-- | :-- | :-- | :-- | :-- | :-- |
| Internet Connected | `internet` | Binary Sensor | - | Diagnostic | - |
| WAN1 Active Uplink | `wan1_active` | Binary Sensor | - | Diagnostic | - |
| WAN1 Link Connected | `wan1_up` | Binary Sensor | - | Diagnostic | - |
| WAN2 Active Uplink | `wan2_active` | Binary Sensor | - | Diagnostic | - |
| WAN2 Link Connected | `wan2_up` | Binary Sensor | - | Diagnostic | - |
| Internet OK | `www_ok` | Binary Sensor | - | Diagnostic | **Disabled by default.** |
| Month Total | `month_total` | Sensor | B | - | LTS: `total_increasing` |
| WAN1 Availability | `wan1_availability` | Sensor | % | Diagnostic | - |
| WAN1 Last Restart | `wan1_boot_time` | Sensor | - | Diagnostic | - |
| WAN1 Name | `wan1_interface_name` | Sensor | - | Diagnostic | - |
| WAN1 Latency | `wan1_latency_avg` | Sensor | ms | Diagnostic | LTS: `measurement` |
| WAN1 Local IP Address | `wan1_local_ip` | Sensor | - | Diagnostic | - |
| WAN1 Projected Usage | `wan1_month_projected` | Sensor | B | - | - |
| WAN1 Month Download | `wan1_month_rx` | Sensor | B | - | LTS: `total_increasing` |
| WAN1 Month Total | `wan1_month_total` | Sensor | B | - | LTS: `total_increasing` |
| WAN1 Month Upload | `wan1_month_tx` | Sensor | B | - | LTS: `total_increasing` |
| WAN1 Public IP Address | `wan1_public_ip` | Sensor | - | Diagnostic | - |
| WAN1 Today Download | `wan1_today_rx` | Sensor | B | - | LTS: `total_increasing` |
| WAN1 Today Total | `wan1_today_total` | Sensor | B | - | LTS: `total_increasing` |
| WAN1 Today Upload | `wan1_today_tx` | Sensor | B | - | LTS: `total_increasing` |
| WAN1 Uptime Duration | `wan1_uptime` | Sensor | s | Diagnostic | **Disabled by default.** |
| WAN2 Availability | `wan2_availability` | Sensor | % | Diagnostic | - |
| WAN2 Last Restart | `wan2_boot_time` | Sensor | - | Diagnostic | - |
| WAN2 Name | `wan2_interface_name` | Sensor | - | Diagnostic | - |
| WAN2 Latency | `wan2_latency_avg` | Sensor | ms | Diagnostic | LTS: `measurement` |
| WAN2 Local IP Address | `wan2_local_ip` | Sensor | - | Diagnostic | - |
| WAN2 Projected Usage | `wan2_month_projected` | Sensor | B | - | - |
| WAN2 Month Download | `wan2_month_rx` | Sensor | B | - | LTS: `total_increasing` |
| WAN2 Month Total | `wan2_month_total` | Sensor | B | - | LTS: `total_increasing` |
| WAN2 Month Upload | `wan2_month_tx` | Sensor | B | - | LTS: `total_increasing` |
| WAN2 Public IP Address | `wan2_public_ip` | Sensor | - | Diagnostic | - |
| WAN2 Today Download | `wan2_today_rx` | Sensor | B | - | LTS: `total_increasing` |
| WAN2 Today Total | `wan2_today_total` | Sensor | B | - | LTS: `total_increasing` |
| WAN2 Today Upload | `wan2_today_tx` | Sensor | B | - | LTS: `total_increasing` |
| WAN2 Uptime Duration | `wan2_uptime` | Sensor | s | Diagnostic | **Disabled by default.** |
| ISP Name | `wan_isp_name` | Sensor | - | Diagnostic | - |
| ISP Organization | `wan_isp_org` | Sensor | - | Diagnostic | **Disabled by default.** |
| Internet Online Since | `www_boot_time` | Sensor | - | Diagnostic | - |
| Internet Drops | `www_drops` | Sensor | - | Diagnostic | LTS: `measurement` |
| Internet Latency | `www_latency` | Sensor | ms | Diagnostic | LTS: `measurement` |
| Internet Uptime Duration | `www_uptime` | Sensor | s | Diagnostic | **Disabled by default.** |

## Security Sub-Device (13 Entities)

| Name | Key | Type | Unit | Category | Notes |
| :-- | :-- | :-- | :-- | :-- | :-- |
| Ad Blocking | `ad_blocking` | Binary Sensor | - | Diagnostic | - |
| Honeypot | `honeypot` | Binary Sensor | - | Diagnostic | - |
| Threat Management Mode | `ips_mode` | Sensor | - | Diagnostic | - |
| Rogue Access Points | `rogue_ap_count` | Sensor | - | - | LTS: `measurement` |
| Rogue APs New 24h | `rogue_new_24h` | Sensor | - | - | LTS: `measurement` |
| Rogue APs All 24h | `rogue_raw_24h` | Sensor | - | Diagnostic | LTS: `measurement` |
| Rules Active | `rules_active` | Sensor | - | - | LTS: `measurement` |
| Rules Configured | `rules_configured` | Sensor | - | Diagnostic | - |
| Rules Disabled | `rules_disabled` | Sensor | - | - | LTS: `measurement` |
| Strongest Rogue RSSI | `strongest_rogue_rssi` | Sensor | dBm | - | LTS: `measurement` |
| Strongest Rogue SSID | `strongest_rogue_ssid` | Sensor | - | - | - |
| VPN Connections Active | `vpn_connections_active` | Sensor | - | - | LTS: `measurement` |
| VPN Connections Total | `vpn_connections_total` | Sensor | - | Diagnostic | - |

## Speedtest Sub-Device (12 Entities)

| Name | Key | Type | Unit | Category | Notes |
| :-- | :-- | :-- | :-- | :-- | :-- |
| Last Run Problem | `speedtest_pass` | Binary Sensor | - | Diagnostic | - |
| WAN1 Download | `wan1_speedtest_download` | Sensor | Mbit/s | - | LTS: `measurement` |
| WAN1 Last Run | `wan1_speedtest_lastrun` | Sensor | - | Diagnostic | - |
| WAN1 Ping | `wan1_speedtest_ping` | Sensor | ms | Diagnostic | LTS: `measurement` |
| WAN1 Upload | `wan1_speedtest_upload` | Sensor | Mbit/s | - | LTS: `measurement` |
| WAN1 Monitoring Period | `wan1_time_period` | Sensor | s | Diagnostic | - |
| WAN2 Download | `wan2_speedtest_download` | Sensor | Mbit/s | - | LTS: `measurement` |
| WAN2 Last Run | `wan2_speedtest_lastrun` | Sensor | - | Diagnostic | - |
| WAN2 Ping | `wan2_speedtest_ping` | Sensor | ms | Diagnostic | LTS: `measurement` |
| WAN2 Upload | `wan2_speedtest_upload` | Sensor | Mbit/s | - | LTS: `measurement` |
| WAN2 Monitoring Period | `wan2_time_period` | Sensor | s | Diagnostic | - |
| Last Run Status | `www_speedtest_status` | Sensor | - | Diagnostic | - |

## Status Sub-Device (22 Entities)

| Name | Key | Type | Unit | Category | Notes |
| :-- | :-- | :-- | :-- | :-- | :-- |
| Network Problem | `all_ok` | Binary Sensor | - | Diagnostic | - |
| LAN OK | `lan_ok` | Binary Sensor | - | Diagnostic | **Disabled by default.** |
| VPN Tunnel Status | `vpn_tunnel_name` | Binary Sensor | - | Diagnostic | - |
| WAN OK | `wan_ok` | Binary Sensor | - | Diagnostic | **Disabled by default.** |
| WiFi Status | `wifi_ssid` | Binary Sensor | - | Diagnostic | - |
| WiFi OK | `wlan_ok` | Binary Sensor | - | Diagnostic | **Disabled by default.** |
| Configured VLANs | `configured_vlans` | Sensor | - | Diagnostic | **Disabled by default.** |
| Guest Users | `guest_user_count` | Sensor | - | Diagnostic | **Disabled by default.** LTS: `measurement` |
| Adopted Devices | `lan_num_adopted` | Sensor | - | Diagnostic | **Disabled by default.** |
| LAN IoT Devices | `lan_num_iot` | Sensor | - | Diagnostic | **Disabled by default.** |
| Switches | `lan_num_sw` | Sensor | - | Diagnostic | **Disabled by default.** |
| Wired Devices | `lan_num_user` | Sensor | - | - | LTS: `measurement` |
| VLANs Active | `vlans_active` | Sensor | - | - | LTS: `measurement` |
| VLANs Total | `vlans_total` | Sensor | - | Diagnostic | - |
| VPN Status | `vpn_status` | Sensor | - | Diagnostic | **Disabled by default.** |
| Total Devices | `wan_num_sta` | Sensor | - | - | LTS: `measurement` |
| WiFi Networks Active | `wifi_networks_active` | Sensor | - | - | LTS: `measurement` |
| WiFi Networks Total | `wifi_networks_total` | Sensor | - | Diagnostic | - |
| Access Points | `wlan_num_ap` | Sensor | - | Diagnostic | **Disabled by default.** |
| WiFi Guests | `wlan_num_guest` | Sensor | - | - | LTS: `measurement` |
| WiFi IoT Devices | `wlan_num_iot` | Sensor | - | Diagnostic | **Disabled by default.** |
| WiFi Devices | `wlan_num_user` | Sensor | - | - | LTS: `measurement` |

## System Sub-Device (15 Entities)

| Name | Key | Type | Unit | Category | Notes |
| :-- | :-- | :-- | :-- | :-- | :-- |
| Refresh Now | `refresh` | Button | - | Config | - |
| WAN1 Run | `wan1_speedtest` | Button | - | - | - |
| WAN2 Run | `wan2_speedtest` | Button | - | - | - |
| Rogue Proximity Threshold | `rogue_proximity_rssi_threshold` | Number | dBm | Config | - |
| Polling Interval | `scan_interval` | Number | s | Config | - |
| WAN1 Load Balance Weight | `wan1_load_balance_weight` | Number | % | Config | - |
| Last Updated | `last_updated` | Sensor | - | Diagnostic | - |
| WAN1 Load Balance | `wan1_weight` | Sensor | % | - | LTS: `measurement` |
| WAN2 Load Balance | `wan2_weight` | Sensor | % | - | - |
| Multi-WAN Mode | `wan_mode` | Sensor | - | Diagnostic | - |
| Pause polling | `pause_polling` | Switch | - | Config | - |
| Apply AP ignore list | `rogue_apply_ap_ignore` | Switch | - | Config | - |
| Apply SSID ignore list | `rogue_apply_ssid_ignore` | Switch | - | Config | - |
| Show 2.4 GHz rogues | `rogue_show_24ghz` | Switch | - | Config | - |
| Show 5 GHz rogues | `rogue_show_5ghz` | Switch | - | Config | - |

<!-- GENERATED:end -->

## Part II: Dynamic UniFi Devices (APs & Switches)

These entities are **opt-in**, controlled by the _UniFi device (Access Point & Switch) sensors_ dropdown. One sub-device is created per adopted AP/switch; the entity set depends on the mode:

- **Don't add** (`none`, default): nothing. 7 base sub-devices only.
- **AP Satisfaction Score only** (`satisfaction_only`, offered only when Core UniFi is installed): **3 per AP** — Satisfaction Score + 2.4/5 GHz Score — and **0 for switches** (switches have no score, so no switch sub-devices are created).
- **Add all device sensors** (`all`): **11 per AP** and **6 per switch** (§6, §7 below).

**Enabled-by-default depends on Core UniFi** (whichever mode creates the entity):

> Every figure below moved by **+2** at `[1.0.1-dev16]` when the two **Projected Usage** sensors were added. They are enabled by default and do not duplicate anything Core UniFi provides, so they land in the registered _and_ both enabled columns in every mode.

| Mode (rig: 8 APs, 12 switches) | Devices | Registered | Enabled — no Core | Enabled — Core present |
| :-- | :-: | :-: | :-: | :-: |
| Don't add | 7 | 130 | 107 | 101 |
| AP Satisfaction Score only | 15 | 154 | n/a¹ | 109 |
| Add all device sensors | 27 | 290 | 267 | 109 |

¹ Satisfaction-only is only offered when Core is present. **Without Core**, all created per-device entities are enabled; **with Core**, only the AP **Satisfaction Score** is enabled (band scores + everything else, and all 6 switch sensors, are disabled — 1 enabled per AP, 0 per switch). So under Core, "Add all" enables the _same_ 105 as "Satisfaction only" — the extra 152 per-device entities are all disabled clutter. The **Don't add** base row is verified live (2026-07-14, standalone = 126/103); the per-device rows carry the prior live rig validation plus the +10 base delta (Alerts 4 + Rogue APs All 24h + 4 rogue switches + Rogue Detection Period select), which are all enabled-by-default and mode-independent. The `Default (Core present)` column in §8/§9 reflects the per-entity defaults.

> **Entity IDs:** each physical device is its own HA device card, so entity IDs use the **device name** as the prefix (e.g. `sensor.unifi_ap_ac_pro_garage_satisfaction_score`), **not** the `unifi_network_…` base prefix. The duplicate-of-core sensors get a `_mon` suffix on their entity ID (keeping the display name) so they don't collide with Core's equivalents on the merged card — on an **AP**: Clients, CPU, Memory, Uptime → `…_mon`; on a **switch**: Clients, CPU, Memory, Uptime → `…_mon`. The switch "Clients" sensor uses the `ports_used` key (value = `num_sta`, the client count), but its entity_id stem is `clients`, so it becomes `…_clients_mon` (not `…_ports_used_mon` or a `_2` collision).

### 8. Access Point Sub-Device (11 Entities per AP)

_Group: `ap`_

| Name | Key | Type | Unit | Default (Core present) | Notes | About |
| :-- | :-- | :-- | :-- | :-- | :-- | :-: |
| Clients | `clients` | Sensor | — | Disabled | Entity ID gets `_mon` suffix. |  |
| Guests | `guests` | Sensor | — | Disabled |  |  |
| 2.4 GHz Clients | `clients_wifi0` | Sensor | — | Disabled |  |  |
| 5 GHz Clients | `clients_wifi1` | Sensor | — | Disabled |  |  |
| Satisfaction Score | `score` | Sensor | % | **Enabled** | In LTS (measurement). |  |
| 2.4 GHz Score | `score_wifi0` | Sensor | % | Disabled | In LTS (measurement). |  |
| 5 GHz Score | `score_wifi1` | Sensor | % | Disabled | In LTS (measurement). |  |
| CPU utilization | `cpu` | Sensor | % | Disabled | Entity ID gets `_mon` suffix. |  |
| Memory utilization | `ram` | Sensor | % | Disabled | Entity ID gets `_mon` suffix. |  |
| Uptime | `uptime` | Sensor | — | Disabled | Entity ID gets `_mon` suffix. |  |
| Update Available | `update_available` | Binary Sensor | — | Disabled |  |  |

---

### 9. Switch Sub-Device (6 Entities per Switch)

_Group: `switch`_

| Name | Key | Type | Unit | Default (Core present) | Notes | About |
| :-- | :-- | :-- | :-- | :-- | :-- | :-: |
| Clients | `ports_used` | Sensor | — | Disabled | Value is `num_sta` (client count). Entity ID gets `_mon` suffix → `…_clients_mon`. |  |
| CPU utilization | `cpu` | Sensor | % | Disabled | Entity ID gets `_mon` suffix. |  |
| Memory utilization | `ram` | Sensor | % | Disabled | Entity ID gets `_mon` suffix. |  |
| Uptime | `uptime` | Sensor | — | Disabled | Entity ID gets `_mon` suffix. |  |
| Model | `model` | Sensor | — | Disabled |  |  |
| Update Available | `update_available` | Binary Sensor | — | Disabled |  |  |

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
