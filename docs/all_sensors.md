# UniFi Network Monitor Integration - Entity Manifest

## Split Structure Information

This document is split into two logical parts:

- **Part I: Base Gateway & Network Entities**: The default virtual devices (comprising 116 entities across the Gateway, Internet, Speedtest, Status, and System sub-devices) present in standard gateway-monitoring mode.
- **Part II: Dynamic UniFi Devices (APs & Switches)**: Dynamic sensor entities generated for each physical UniFi Access Point and Switch monitored by the integration (~20 devices, adding ~160 entities when enabled).

---

## Part I: Base Gateway & Network Entities

> **Grouping note:** Sub-devices below match the **actual Home Assistant device cards** (the `sensor.unifi_network_<group>_…` entity-ID prefix a user sees on a default install), verified live against a UDM Pro. Each entity's card is set by its `device_key` / `group` in the integration source — `DOMAIN_{gateway_mac}_{group}` — not by which fetch produced the data. The default sub-device names are **UniFi Network Gateway / Internet / Speedtest / Status / System**; renaming a sub-device changes its entity-ID prefix. Counts are for the base scenario (all three optional groups on, no per-device sensors): **116 entities** = Gateway 18 + Internet 39 + Speedtest 14 + Status 33 + System 12.
>
> **Enabled vs disabled — depends on HA Core UniFi:** the 116 registered entities are the same either way; only the enabled-by-default count differs.
>
> - **Without Core UniFi (standalone):** **93 enabled / 23 disabled**. Per card, enabled / total: Gateway 11/18, Internet 34/39, Speedtest 14/14, Status 22/33, System 12/12.
> - **With Core UniFi installed:** **87 enabled / 29 disabled** — six gateway diagnostics (rows tagged _Standalone-only enabled_ in §1: `cpu`, `ram`, `cpu_temp`, `board_temp`, `uptime`, `update_available`) are enabled-by-default **only** when Core is absent. With Core present they revert to disabled-by-default, so the Gateway card reads 5/18. This is intentional: Core already provides the gateway's CPU/memory; the temperatures are Monitor-only but kept off to avoid cluttering the merged gateway card (enable manually from either integration if wanted).
>
> Both cases verified live on fresh (default) installs. The 23 always-disabled rows are the ones marked _Disabled by default_ (Gateway 7, Internet 5, Status 11).

### 1. Gateway Sub-Device (18 Entities)

_Group: `gateway`_

| Name | Key | Type | Unit | Category | Notes |
| :-- | :-- | :-- | :-- | :-- | :-- |
| Application Version | `application_version` | Sensor | — | Diagnostic | UniFi Network application version. |
| Board Temperature | `board_temp` | Sensor | °C | Diagnostic | _Standalone-only enabled_ (disabled by default when Core UniFi present). |
| CPU temperature | `cpu_temp` | Sensor | °C | Diagnostic | _Standalone-only enabled_ (disabled by default when Core UniFi present). |
| CPU utilization | `cpu` | Sensor | % | Diagnostic | _Standalone-only enabled_ (disabled by default when Core UniFi present). |
| Last Backup | `last_backup` | Sensor | — | Diagnostic |  |
| Memory utilization | `ram` | Sensor | % | Diagnostic | _Standalone-only enabled_ (disabled by default when Core UniFi present). |
| Storage Total | `storage_size` | Sensor | GB | Diagnostic | **Disabled by default.** No LTS (no state_class). |
| Storage Used | `storage_used` | Sensor | GB | Diagnostic |  |
| Storage Utilization | `storage_used_pct` | Sensor | % | Diagnostic | Storage used as a percentage of total. |
| UniFi OS Version | `health_wan_gw_version` | Sensor | — | Diagnostic |  |
| Update Available | `update_available` | Binary Sensor | — | Diagnostic | _Standalone-only enabled_ (disabled by default when Core UniFi present). |
| Uptime | `uptime` | Sensor | — | Diagnostic | _Standalone-only enabled_ (disabled by default when Core UniFi present). |
| WAN1 SFP Part Number | `wan1_sfp_part` | Sensor | — | Diagnostic | **Disabled by default.** Data may not be available in all configurations. |
| WAN1 SFP Serial Number | `wan1_sfp_serial` | Sensor | — | Diagnostic | **Disabled by default.** Data may not be available in all configurations. |
| WAN1 SFP Vendor | `wan1_sfp_vendor` | Sensor | — | Diagnostic | **Disabled by default.** Data may not be available in all configurations. |
| WAN2 SFP Part Number | `wan2_sfp_part` | Sensor | — | Diagnostic | **Disabled by default.** |
| WAN2 SFP Serial Number | `wan2_sfp_serial` | Sensor | — | Diagnostic | **Disabled by default.** |
| WAN2 SFP Vendor | `wan2_sfp_vendor` | Sensor | — | Diagnostic | **Disabled by default.** |

---

### 2. Internet Sub-Device (39 Entities)

_Group: `internet`_

| Name | Key | Type | Unit | Category | Notes |
| :-- | :-- | :-- | :-- | :-- | :-- |
| Internet Connected | `internet` | Binary Sensor | — | Diagnostic |  |
| Internet Drops | `health_www_drops` | Sensor | — | Diagnostic |  |
| Internet Latency | `health_www_latency` | Sensor | ms | Diagnostic |  |
| Internet OK | `health_www_ok` | Binary Sensor | — | Diagnostic | **Disabled by default.** |
| Internet Online Since | `health_www_boot_time` | Sensor | — | Diagnostic |  |
| Internet Uptime Duration | `health_www_uptime` | Sensor | s | Diagnostic | **Disabled by default.** Other display units may be used (e.g. s). No LTS (no state_class). |
| ISP Name | `health_wan_isp_name` | Sensor | — | Diagnostic |  |
| ISP Organisation | `health_wan_isp_org` | Sensor | — | Diagnostic | **Disabled by default.** |
| Month Total | `month_total` | Sensor | GB | — |  |
| WAN1 Active Uplink | `wan1_active` | Binary Sensor | — | Diagnostic |  |
| WAN1 Availability | `health_wan1_availability` | Sensor | % | Diagnostic |  |
| WAN1 Last Restart | `health_wan1_boot_time` | Sensor | — | Diagnostic |  |
| WAN1 Latency | `health_wan1_latency_avg` | Sensor | ms | Diagnostic |  |
| WAN1 Link Connected | `wan1_up` | Binary Sensor | — | Diagnostic |  |
| WAN1 Local IP Address | `wan1_local_ip` | Sensor | — | Diagnostic |  |
| WAN1 Month Download | `wan1_month_rx` | Sensor | GB | — |  |
| WAN1 Month Total | `wan1_month_total` | Sensor | GB | — |  |
| WAN1 Month Upload | `wan1_month_tx` | Sensor | GB | — |  |
| WAN1 Name | `wan1_interface_name` | Sensor | — | Diagnostic |  |
| WAN1 Public IP Address | `wan1_public_ip` | Sensor | — | Diagnostic |  |
| WAN1 Today Download | `wan1_today_rx` | Sensor | GB | — | No LTS (no state_class). |
| WAN1 Today Total | `wan1_today_total` | Sensor | GB | — | No LTS (no state_class). |
| WAN1 Today Upload | `wan1_today_tx` | Sensor | GB | — | No LTS (no state_class). |
| WAN1 Uptime Duration | `health_wan1_uptime` | Sensor | s | Diagnostic | **Disabled by default.** Other display units may be used (e.g. s). No LTS (no state_class). |
| WAN2 Active Uplink | `wan2_active` | Binary Sensor | — | Diagnostic |  |
| WAN2 Availability | `health_wan2_availability` | Sensor | % | Diagnostic |  |
| WAN2 Last Restart | `health_wan2_boot_time` | Sensor | — | Diagnostic |  |
| WAN2 Latency | `health_wan2_latency_avg` | Sensor | ms | Diagnostic |  |
| WAN2 Link Connected | `wan2_up` | Binary Sensor | — | Diagnostic |  |
| WAN2 Local IP Address | `wan2_local_ip` | Sensor | — | Diagnostic |  |
| WAN2 Month Download | `wan2_month_rx` | Sensor | GB | — |  |
| WAN2 Month Total | `wan2_month_total` | Sensor | GB | — |  |
| WAN2 Month Upload | `wan2_month_tx` | Sensor | GB | — |  |
| WAN2 Name | `wan2_interface_name` | Sensor | — | Diagnostic |  |
| WAN2 Public IP Address | `wan2_public_ip` | Sensor | — | Diagnostic |  |
| WAN2 Today Download | `wan2_today_rx` | Sensor | GB | — | No LTS (no state_class). |
| WAN2 Today Total | `wan2_today_total` | Sensor | GB | — | No LTS (no state_class). |
| WAN2 Today Upload | `wan2_today_tx` | Sensor | GB | — | No LTS (no state_class). |
| WAN2 Uptime Duration | `health_wan2_uptime` | Sensor | s | Diagnostic | **Disabled by default.** Other display units may be used (e.g. s). No LTS (no state_class). |

---

### 3. Speedtest Sub-Device (14 Entities)

_Group: `speedtest`_

| Name | Key | Type | Unit | Category | Notes |
| :-- | :-- | :-- | :-- | :-- | :-- |
| Last Run Problem | `health_speedtest_pass` | Binary Sensor | — | Diagnostic |  |
| Last Run Status | `health_www_speedtest_status` | Sensor | — | Diagnostic |  |
| WAN1 Download | `wan1_speedtest_download` | Sensor | Mbit/s | — |  |
| WAN1 Last Run | `wan1_speedtest_lastrun` | Sensor | — | Diagnostic |  |
| WAN1 Monitoring Period | `health_wan1_time_period` | Sensor | h | Diagnostic | No LTS (no state_class). |
| WAN1 Ping | `wan1_speedtest_ping` | Sensor | ms | Diagnostic | No LTS (no state_class). |
| WAN1 Run | `wan1_speedtest` | Button | — | — | Data may not be available in all configurations. |
| WAN1 Upload | `wan1_speedtest_upload` | Sensor | Mbit/s | — |  |
| WAN2 Download | `wan2_speedtest_download` | Sensor | Mbit/s | — |  |
| WAN2 Last Run | `wan2_speedtest_lastrun` | Sensor | — | Diagnostic |  |
| WAN2 Monitoring Period | `health_wan2_time_period` | Sensor | h | Diagnostic | No LTS (no state_class). |
| WAN2 Ping | `wan2_speedtest_ping` | Sensor | ms | Diagnostic | No LTS (no state_class). |
| WAN2 Run | `wan2_speedtest` | Button | — | — | Data may not be available in all configurations. |
| WAN2 Upload | `wan2_speedtest_upload` | Sensor | Mbit/s | — |  |

---

### 4. Status Sub-Device (33 Entities)

_Group: `status`_

| Name | Key | Type | Unit | Category | Notes |
| :-- | :-- | :-- | :-- | :-- | :-- |
| Access Points | `health_wlan_num_ap` | Sensor | — | Diagnostic | **Disabled by default.** |
| Adopted Devices | `health_lan_num_adopted` | Sensor | — | Diagnostic | **Disabled by default.** |
| Configured VLANs | `configured_vlans` | Sensor | — | Diagnostic | **Disabled by default.** |
| Guest Users | `guest_user_count` | Sensor | — | — |  |
| House WiFi Status | `wifi_house` | Binary Sensor | — | Diagnostic |  |
| IoT-Secure WiFi Status | `wifi_iot-secure` | Binary Sensor | — | Diagnostic |  |
| LAN IoT Devices | `health_lan_num_iot` | Sensor | — | Diagnostic | **Disabled by default.** |
| LAN OK | `health_lan_ok` | Binary Sensor | — | Diagnostic | **Disabled by default.** |
| NetCentral WiFi Status | `wifi_netcentral` | Binary Sensor | — | Diagnostic |  |
| Network Problem | `health_all_ok` | Binary Sensor | — | Diagnostic |  |
| Rogue AP Proximity Alert | `rogue_proximity_alert` | Binary Sensor | — | Diagnostic |  |
| Rogue Access Points | `rogue_ap_count` | Sensor | — | — |  |
| Rogue Proximity Threshold | `rogue_proximity_rssi_threshold` | Number | dBm | Config |  |
| Rules Active | `rules_active` | Sensor | — | — |  |
| Rules Configured | `rules_configured` | Sensor | — | Diagnostic |  |
| Rules Disabled | `rules_disabled` | Sensor | — | — |  |
| Strongest Rogue RSSI | `strongest_rogue_rssi` | Sensor | dBm | — |  |
| Strongest Rogue SSID | `strongest_rogue_ssid` | Sensor | — | — | `rogue_aps` attribute carries the full rogue-AP list. |
| Switches | `health_lan_num_sw` | Sensor | — | Diagnostic | **Disabled by default.** |
| Total Devices | `health_wan_num_sta` | Sensor | — | — |  |
| VLANs Active | `vlans_active` | Sensor | — | — |  |
| VLANs Total | `vlans_total` | Sensor | — | Diagnostic |  |
| VPN Connections Active | `vpn_connections_active` | Sensor | — | — |  |
| VPN Connections Total | `vpn_connections_total` | Sensor | — | Diagnostic |  |
| VPN Status | `health_vpn_status` | Sensor | — | Diagnostic | **Disabled by default.** Data may not be available in all configurations. |
| WAN OK | `health_wan_ok` | Binary Sensor | — | Diagnostic | **Disabled by default.** |
| WiFi Devices | `health_wlan_num_user` | Sensor | — | — |  |
| WiFi Guests | `health_wlan_num_guest` | Sensor | — | Diagnostic | **Disabled by default.** |
| WiFi IoT Devices | `health_wlan_num_iot` | Sensor | — | Diagnostic | **Disabled by default.** |
| WiFi Networks Active | `wifi_networks_active` | Sensor | — | — |  |
| WiFi Networks Total | `wifi_networks_total` | Sensor | — | Diagnostic |  |
| WiFi OK | `health_wlan_ok` | Binary Sensor | — | Diagnostic | **Disabled by default.** |
| Wired Devices | `health_lan_num_user` | Sensor | — | — |  |

---

### 5. System Sub-Device (12 Entities)

_Group: `system`_

| Name | Key | Type | Unit | Category | Notes |
| :-- | :-- | :-- | :-- | :-- | :-- |
| Ad Blocking | `ad_blocking` | Binary Sensor | — | Diagnostic |  |
| Clean Up Unused Entities | `cleanup_unused_entities` | Button | — | Config |  |
| Honeypot | `honeypot` | Binary Sensor | — | Diagnostic |  |
| Last Updated | `last_updated` | Sensor | — | Diagnostic |  |
| Multi-WAN Mode | `wan_mode` | Sensor | — | Diagnostic |  |
| Pause Polling | `pause_polling` | Switch | — | Config |  |
| Polling Interval | `scan_interval` | Number | s | Config |  |
| Refresh Now | `refresh` | Button | — | Config |  |
| Threat Management Mode | `ips_mode` | Sensor | — | Diagnostic |  |
| WAN1 Load Balance | `wan1_weight` | Sensor | % | — |  |
| WAN1 Load Balance Weight | `wan1_load_balance_weight` | Number | % | Config |  |
| WAN2 Load Balance | `wan2_weight` | Sensor | % | — |  |

> **Service (not an entity):** `unifi_network_monitor.cleanup_unused_entities` is a registered action, not a device entity, so it is not part of the 116 count. It is the `dry_run`-capable counterpart to the **Clean Up Unused Entities** button above.

---

## Part II: Dynamic UniFi Devices (APs & Switches)

These entities are **opt-in**, controlled by the _UniFi device (Access Point & Switch) sensors_ dropdown. One sub-device is created per adopted AP/switch; the entity set depends on the mode:

- **Don't add** (`none`, default): nothing. 5 base devices only.
- **AP Satisfaction Score only** (`satisfaction_only`, offered only when Core UniFi is installed): **3 per AP** — Satisfaction Score + 2.4/5 GHz Score — and **0 for switches** (switches have no score, so no switch sub-devices are created).
- **Add all device sensors** (`all`): **11 per AP** and **6 per switch** (§6, §7 below).

**Enabled-by-default depends on Core UniFi** (whichever mode creates the entity):

| Mode (rig: 8 APs, 12 switches) | Devices | Registered | Enabled — no Core | Enabled — Core present |
| :-- | :-: | :-: | :-: | :-: |
| Don't add | 5 | 116 | 93 | 87 |
| AP Satisfaction Score only | 13 | 140 | n/a¹ | 95 |
| Add all device sensors | 25 | 276 | 253 | 95 |

¹ Satisfaction-only is only offered when Core is present. **Without Core**, all created per-device entities are enabled; **with Core**, only the AP **Satisfaction Score** is enabled (band scores + everything else, and all 6 switch sensors, are disabled — 1 enabled per AP, 0 per switch). So under Core, "Add all" enables the _same_ 95 as "Satisfaction only" — the extra 136 entities are all disabled clutter. All four cases verified live on the reference rig; the `Default (Core present)` column in §6/§7 reflects the per-entity defaults.

> **Entity IDs:** each physical device is its own HA device card, so entity IDs use the **device name** as the prefix (e.g. `sensor.unifi_ap_ac_pro_garage_satisfaction_score`), **not** the `unifi_network_…` base prefix. The duplicate-of-core sensors get a `_mon` suffix on their entity ID (keeping the display name) so they don't collide with Core's equivalents on the merged card — on an **AP**: Clients, CPU, Memory, Uptime → `…_mon`; on a **switch**: Clients, CPU, Memory, Uptime → `…_mon`. The switch "Clients" sensor uses the `ports_used` key (value = `num_sta`, the client count), but its entity_id stem is `clients`, so it becomes `…_clients_mon` (not `…_ports_used_mon` or a `_2` collision).

### 6. Access Point Sub-Device (11 Entities per AP)

_Group: `ap`_

| Name | Key | Type | Unit | Default (Core present) | Notes |
| :-- | :-- | :-- | :-- | :-- | :-- |
| Clients | `clients` | Sensor | — | Disabled | Entity ID gets `_mon` suffix. |
| Guests | `guests` | Sensor | — | Disabled |  |
| 2.4 GHz Clients | `clients_wifi0` | Sensor | — | Disabled |  |
| 5 GHz Clients | `clients_wifi1` | Sensor | — | Disabled |  |
| Satisfaction Score | `score` | Sensor | % | **Enabled** | No LTS (no state_class). |
| 2.4 GHz Score | `score_wifi0` | Sensor | % | Disabled | No LTS (no state_class). |
| 5 GHz Score | `score_wifi1` | Sensor | % | Disabled | No LTS (no state_class). |
| CPU utilization | `cpu` | Sensor | % | Disabled | Entity ID gets `_mon` suffix. |
| Memory utilization | `ram` | Sensor | % | Disabled | Entity ID gets `_mon` suffix. |
| Uptime | `uptime` | Sensor | — | Disabled | Entity ID gets `_mon` suffix. |
| Update Available | `update_available` | Binary Sensor | — | Disabled |  |

---

### 7. Switch Sub-Device (6 Entities per Switch)

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

Almost every numeric sensor in this integration carries a `state_class` and **is** in LTS (CPU/RAM/temperatures, signal/RSSI, latency, availability, all counts, monthly data usage, speedtest download/upload, etc.). The following numeric sensors are the exceptions — they are numeric but currently have **no `state_class`**, so they are **not** in LTS:

| Sub-Device      | Name                     | Key                       | Unit |
| :-------------- | :----------------------- | :------------------------ | :--- |
| 🖥️ Gateway      | Storage Total            | `storage_size`            | GB   |
| 🌐 Internet     | WAN1 Today Download      | `wan1_today_rx`           | GB   |
| 🌐 Internet     | WAN1 Today Upload        | `wan1_today_tx`           | GB   |
| 🌐 Internet     | WAN1 Today Total         | `wan1_today_total`        | GB   |
| 🌐 Internet     | WAN2 Today Download      | `wan2_today_rx`           | GB   |
| 🌐 Internet     | WAN2 Today Upload        | `wan2_today_tx`           | GB   |
| 🌐 Internet     | WAN2 Today Total         | `wan2_today_total`        | GB   |
| 🌐 Internet     | WAN1 Uptime Duration     | `health_wan1_uptime`      | s    |
| 🌐 Internet     | WAN2 Uptime Duration     | `health_wan2_uptime`      | s    |
| 🌐 Internet     | Internet Uptime Duration | `health_www_uptime`       | s    |
| ⚙️ System       | WAN1 Ping                | `wan1_speedtest_ping`     | ms   |
| ⚙️ System       | WAN2 Ping                | `wan2_speedtest_ping`     | ms   |
| ⚡ Speedtest    | WAN1 Monitoring Period   | `health_wan1_time_period` | h    |
| ⚡ Speedtest    | WAN2 Monitoring Period   | `health_wan2_time_period` | h    |
| 📶 Access Point | Satisfaction Score       | `score`                   | %    |
| 📶 Access Point | 2.4 GHz Score            | `score_wifi0`             | %    |
| 📶 Access Point | 5 GHz Score              | `score_wifi1`             | %    |

> **Note:** The individual rows above are also flagged with `No LTS (no state_class).` in the Notes column of their respective entity tables. Daily-usage totals, ping and the AP Satisfaction Score are natural trend candidates — if long-term history of these is wanted, give them a `state_class` (`measurement`, or `total_increasing` for the daily totals) in `sensor.py`.

---

## Debugging & Maintenance Reference

### Identity Strategy

- **Base Unique ID**: The MAC address of the gateway (normalized to lowercase, with colons, or as stored).
- **Entity Unique ID**: `{{gateway_mac}}_{{key}}`.
- **Device Identifiers**: `{{DOMAIN}}_{{gateway_mac}}_{{group}}`.

### Coexistence with HA Core UniFi Network

- **Gateway card merges.** The Gateway sub-device uses `connections={(CONNECTION_NETWORK_MAC, gateway_mac)}` (`build_gateway_device_info`), so when Core UniFi is installed HA **merges** it into Core's gateway device card. The merged card adopts **Core's** device name (e.g. `UDM-Pro`) and firmware string (Core reports the UniFi OS version, e.g. `5.1.19.33549`, where standalone shows the Network-application version). Expected and intended.
- **Other sub-devices stay separate.** Internet / Speedtest / Status / System use `identifiers` only (no MAC connection), so they remain distinct Monitor cards linked to the gateway via `via_device`. Per-physical-device (AP/switch) cards also merge by MAC (`build_unifi_device_info`).
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
