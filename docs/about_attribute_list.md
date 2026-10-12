# About Attributes — UniFi Network Monitor

Most entities in this integration carry a short built-in **`about`** note — a plain-language explanation of what the entity is, and for the signal metrics, what a good value looks like.

> [!TIP]
>
> **To see one in Home Assistant:** click the entity, open the **⋮ (three-dots) menu → Details**, and look for the **`about`** attribute.

---

> [!NOTE]
>
> **These notes are never written to your database.** They are declared as _unrecorded attributes_, so Home Assistant shows them live in the entity's details but the recorder ignores them entirely — they cost nothing to carry, however often the entity updates. See `dev_standards.md` Section 14.

The `about` attribute is a plain-language note attached to key entities to provide context or instructions to the user directly in the Home Assistant More Info dialog. They are stored directly in the state machine as entity attributes and do not write to long-term statistics or DB storage.

**42 of the 141 static base entities carry a note.** Self-explanatory entities deliberately do not carry notes, as a note on every entity trains users to ignore them. Omissions are listed at the end.

ᴰ = **disabled by default.** Enable it from the entity's settings if you want it; it is hidden to keep the default entity list manageable.

---

<!-- GENERATED:start -->

## Alerts (4)

| Entity | Platform | Key | Note |
| :-- | :-- | :-- | :-- |
| High Sev3 Qty Last 24h | Sensor | `alerts_high_24h` | Count of HIGH (Sev 3) alerts in the last 24 hours, from the UniFi system log. See the Get Alerts action for full history. |
| Very High Sev4 Qty Last 24h | Sensor | `alerts_very_high_24h` | Count of VERY HIGH (Sev 4) alerts in the last 24 hours, from the UniFi system log. See the Get Alerts action for full history. |
| Last High Sev3 | Sensor | `last_high` | Title of the most recent HIGH (Sev 3) alert; 'None Detected' when there are none. Full history via the Get Alerts action. |
| Last Very High Sev4 | Sensor | `last_very_high` | Title of the most recent VERY HIGH (Sev 4) alert; 'None Detected' when there are none. Full history via the Get Alerts action. |

## Gateway (1)

| Entity | Platform | Key | Note |
| :-- | :-- | :-- | :-- |
| Board Temperature | Sensor | `board_temp` | Gateway mainboard temperature — the same reading as 'Phy temperature' in the HA core UniFi Network integration. |

## Internet (18)

| Entity | Platform | Key | Note |
| :-- | :-- | :-- | :-- |
| Month Total | Sensor | `month_total` | Combined WAN internet usage (upload + download) for the current calendar month; includes WAN2 when Dual-WAN is enabled. |
| WAN1 Availability | Sensor | `wan1_availability` | Percentage of UniFi's own monitoring window in which WAN1 was up — not an all-time figure. The window is the controller's, so it resets when the gateway restarts. |
| WAN1 Last Restart | Sensor | `wan1_boot_time` | When WAN1 last came up, derived from the interface's uptime. It moves on every reconnection, so a recent value after an outage is expected rather than a fault. |
| WAN1 Name | Sensor | `wan1_interface_name` | The WAN's configured name from the controller. Needs an API key: under username/password this endpoint is unavailable and the sensor is legitimately unknown. |
| WAN1 Latency | Sensor | `wan1_latency_avg` | Average latency to UniFi's monitoring target over its window, not a live ping. For the current figure use Internet Latency, which is measured per poll. |
| WAN1 Local IP Address | Sensor | `wan1_local_ip` | The address the gateway's own WAN interface holds. On a CGNAT connection this is a carrier-private address and is not reachable from the internet — WAN1 Public IP Address is the one the world sees. |
| WAN1 Projected Usage | Sensor | `wan1_month_projected` | Projected WAN1 usage by the end of the calendar month, from usage so far. Check the confidence attribute — it is weak early in the month. |
| WAN1 Month Total | Sensor | `wan1_month_total` | This calendar month's WAN1 usage so far, clamped so it only rises within the month. Resets on the 1st. WAN1 Projected Usage estimates where it is heading. |
| WAN1 Public IP Address | Sensor | `wan1_public_ip` | The address the internet sees, as reported by the controller. On CGNAT it differs from WAN1 Local IP Address and is shared with other subscribers. |
| WAN1 Today Total | Sensor | `wan1_today_total` | Today's WAN1 usage so far. UniFi recomputes the open bucket each poll, so the raw figure can dip slightly; it is clamped to its running maximum here so it only ever rises within the day. |
| WAN1 Uptime Duration | Sensor | `wan1_uptime` | How long WAN1 has been up, as a duration. WAN1 Last Restart is the same fact as a timestamp — use whichever suits the automation. |
| WAN2 Availability | Sensor | `wan2_availability` | As WAN1 Availability, for the second WAN. Only meaningful when a second WAN is actually connected. |
| WAN2 Latency | Sensor | `wan2_latency_avg` | As WAN1 Latency, for the second WAN. |
| WAN2 Projected Usage | Sensor | `wan2_month_projected` | Projected WAN2 usage by the end of the calendar month, from usage so far. Check the confidence attribute — it is weak early in the month. |
| ISP Name | Sensor | `wan_isp_name` | The ISP as UniFi identifies it from the WAN address. ISP Organisation is the registered owner of the address block, which is often a parent company or a wholesale carrier rather than the company billing you. |
| ISP Organization | Sensor | `wan_isp_org` | Registered owner of the WAN address block. Frequently differs from ISP Name — a reseller's customers show the wholesaler here. |
| Internet Drops | Sensor | `www_drops` | Count of dropped connectivity checks in UniFi's monitoring window. A handful is normal; a rising count during good latency usually means packet loss rather than a slow link. |
| Internet Latency | Sensor | `www_latency` | Current internet latency as the controller last measured it. Differs from WAN1/WAN2 Latency, which are averages over UniFi's longer window. |

## Security (5)

| Entity | Platform | Key | Note |
| :-- | :-- | :-- | :-- |
| Rogue Access Points | Sensor | `rogue_ap_count` | Filtered count of unique rogue APs after your band, SSID and UniFi AP ignore settings are applied. See 'Rogue APs All 24h' for unfiltered volume. |
| Rogue APs New 24h | Sensor | `rogue_new_24h` | Count of rogue BSSIDs first seen by Home Assistant within the last 24 hours — brand-new neighbours/devices, distinct from long-standing ones. Tracked across restarts. Note: on first enable everything counts as new for the first 24h, and BSSID-randomising devices appear new on each rotation. |
| Rogue APs All 24h | Sensor | `rogue_raw_24h` | Raw total rogue detections over a rolling 24-hour window, unaffected by any settings or ignore lists. Counts every detection by every UniFi AP — a gauge of background rogue noise/coverage, not unique rogues. |
| Strongest Rogue RSSI | Sensor | `strongest_rogue_rssi` | Signal (dBm) of the strongest rogue AP among those left after your inclusion/exclusion settings. |
| Strongest Rogue SSID | Sensor | `strongest_rogue_ssid` | SSID of the strongest rogue AP after your inclusion/exclusion settings. Full list via the Get Rogue APs action. |

## Speedtest (4)

| Entity | Platform | Key | Note |
| :-- | :-- | :-- | :-- |
| WAN1 Download | Sensor | `wan1_speedtest_download` | Download speed from the last speedtest UniFi ran — not a live measurement. Check WAN1 Speedtest Last Run before acting on it; a figure hours old says nothing about now. |
| WAN1 Last Run | Sensor | `wan1_speedtest_lastrun` | When the last WAN1 speedtest completed. This is what makes the other speedtest sensors interpretable — a stale run is the usual explanation for a figure that looks wrong. |
| WAN1 Ping | Sensor | `wan1_speedtest_ping` | Latency recorded during the speedtest, under load. Usually higher than Internet Latency, which is measured on an idle link. |
| WAN1 Upload | Sensor | `wan1_speedtest_upload` | Upload speed from the same run as WAN1 Speedtest Download. Both are as old as WAN1 Speedtest Last Run. |

## Status (4)

| Entity | Platform | Key | Note |
| :-- | :-- | :-- | :-- |
| Guest Users | Sensor | `guest_user_count` | Total active sessions tracked by the controller's Guest Portal / Hotspot Manager (voucher, payment, social login, or pending authorization) — may include wired and wireless. |
| VLANs Active | Sensor | `vlans_active` | How many configured VLANs are enabled. VLANs Total includes disabled ones, so a gap between the two is a deliberate configuration rather than a fault. |
| WiFi Networks Active | Sensor | `wifi_networks_active` | How many configured WiFi networks are currently enabled. WiFi Networks Total counts every configured SSID including disabled ones. |
| WiFi Guests | Sensor | `wlan_num_guest` | Guest-network clients currently connected over WiFi. |

## System (6)

| Entity | Platform | Key | Note |
| :-- | :-- | :-- | :-- |
| Last Updated | Sensor | `last_updated` | When this integration last completed a poll — not when the gateway last changed. If it stops advancing, the integration has stopped polling even while entities still show their last values. |
| Multi-WAN Mode | Sensor | `wan_mode` | Fill level of the gateway's /persistent partition, which holds logs and settings rather than recordings. Sustained high values usually mean log growth. |
| Apply AP ignore list | Switch | `rogue_apply_ap_ignore` | When on, a rogue is hidden only when every UniFi AP that reports it matches the AP ignore list. Edit the list in Configure. |
| Apply SSID ignore list | Switch | `rogue_apply_ssid_ignore` | When on, rogue APs whose SSID matches the SSID ignore list are hidden. Edit the list in Configure. |
| Show 2.4 GHz rogues | Switch | `rogue_show_24ghz` | On: include 2.4 GHz rogue APs in detection. Off: drop them from all rogue sensors. |
| Show 5 GHz rogues | Switch | `rogue_show_5ghz` | On: include 5 GHz rogue APs in detection. Off: drop them from all rogue sensors. |

## Entities without an `about` note (99)

The following entities carry no `about` attribute (self-explanatory or intentionally unannotated):

| Entity | Platform | Key | Group |
| :-- | :-- | :-- | :-- |
| Update Available | Binary sensor | `update_available` | Gateway |
| Update Available | Binary sensor | `update_available` | Gateway |
| Application Version | Sensor | `application_version` | Gateway |
| Clients | Sensor | `clients` | Gateway |
| 2.4 GHz Clients | Sensor | `clients_wifi0` | Gateway |
| 5 GHz Clients | Sensor | `clients_wifi1` | Gateway |
| CPU utilization | Sensor | `cpu` | Gateway |
| CPU utilization | Sensor | `cpu` | Gateway |
| CPU utilization | Sensor | `cpu` | Gateway |
| CPU temperature | Sensor | `cpu_temp` | Gateway |
| Guests | Sensor | `guests` | Gateway |
| Last Backup | Sensor | `last_backup` | Gateway |
| Model | Sensor | `model` | Gateway |
| Clients | Sensor | `ports_used` | Gateway |
| Memory utilization | Sensor | `ram` | Gateway |
| Memory utilization | Sensor | `ram` | Gateway |
| Memory utilization | Sensor | `ram` | Gateway |
| Satisfaction Score | Sensor | `score` | Gateway |
| 2.4 GHz Score | Sensor | `score_wifi0` | Gateway |
| 5 GHz Score | Sensor | `score_wifi1` | Gateway |
| Storage Total | Sensor | `storage_size` | Gateway |
| Storage Used | Sensor | `storage_used` | Gateway |
| Storage Utilization | Sensor | `storage_used_pct` | Gateway |
| Uptime | Sensor | `uptime` | Gateway |
| Uptime | Sensor | `uptime` | Gateway |
| Uptime | Sensor | `uptime` | Gateway |
| WAN1 SFP Part Number | Sensor | `wan1_sfp_part` | Gateway |
| WAN1 SFP Serial Number | Sensor | `wan1_sfp_serial` | Gateway |
| WAN1 SFP Vendor | Sensor | `wan1_sfp_vendor` | Gateway |
| WAN2 SFP Part Number | Sensor | `wan2_sfp_part` | Gateway |
| WAN2 SFP Serial Number | Sensor | `wan2_sfp_serial` | Gateway |
| WAN2 SFP Vendor | Sensor | `wan2_sfp_vendor` | Gateway |
| UniFi OS Version | Sensor | `wan_gw_version` | Gateway |
| Internet Connected | Binary sensor | `internet` | Internet |
| WAN1 Active Uplink | Binary sensor | `wan1_active` | Internet |
| WAN1 Link Connected | Binary sensor | `wan1_up` | Internet |
| WAN2 Active Uplink | Binary sensor | `wan2_active` | Internet |
| WAN2 Link Connected | Binary sensor | `wan2_up` | Internet |
| Internet OK | Binary sensor | `www_ok` | Internet |
| WAN1 Month Download | Sensor | `wan1_month_rx` | Internet |
| WAN1 Month Upload | Sensor | `wan1_month_tx` | Internet |
| WAN1 Today Download | Sensor | `wan1_today_rx` | Internet |
| WAN1 Today Upload | Sensor | `wan1_today_tx` | Internet |
| WAN2 Last Restart | Sensor | `wan2_boot_time` | Internet |
| WAN2 Name | Sensor | `wan2_interface_name` | Internet |
| WAN2 Local IP Address | Sensor | `wan2_local_ip` | Internet |
| WAN2 Month Download | Sensor | `wan2_month_rx` | Internet |
| WAN2 Month Total | Sensor | `wan2_month_total` | Internet |
| WAN2 Month Upload | Sensor | `wan2_month_tx` | Internet |
| WAN2 Public IP Address | Sensor | `wan2_public_ip` | Internet |
| WAN2 Today Download | Sensor | `wan2_today_rx` | Internet |
| WAN2 Today Total | Sensor | `wan2_today_total` | Internet |
| WAN2 Today Upload | Sensor | `wan2_today_tx` | Internet |
| WAN2 Uptime Duration | Sensor | `wan2_uptime` | Internet |
| Internet Online Since | Sensor | `www_boot_time` | Internet |
| Internet Uptime Duration | Sensor | `www_uptime` | Internet |
| Ad Blocking | Binary sensor | `ad_blocking` | Security |
| Honeypot | Binary sensor | `honeypot` | Security |
| Threat Management Mode | Sensor | `ips_mode` | Security |
| Rules Active | Sensor | `rules_active` | Security |
| Rules Configured | Sensor | `rules_configured` | Security |
| Rules Disabled | Sensor | `rules_disabled` | Security |
| VPN Connections Active | Sensor | `vpn_connections_active` | Security |
| VPN Connections Total | Sensor | `vpn_connections_total` | Security |
| Last Run Problem | Binary sensor | `speedtest_pass` | Speedtest |
| WAN1 Monitoring Period | Sensor | `wan1_time_period` | Speedtest |
| WAN2 Download | Sensor | `wan2_speedtest_download` | Speedtest |
| WAN2 Last Run | Sensor | `wan2_speedtest_lastrun` | Speedtest |
| WAN2 Ping | Sensor | `wan2_speedtest_ping` | Speedtest |
| WAN2 Upload | Sensor | `wan2_speedtest_upload` | Speedtest |
| WAN2 Monitoring Period | Sensor | `wan2_time_period` | Speedtest |
| Last Run Status | Sensor | `www_speedtest_status` | Speedtest |
| Network Problem | Binary sensor | `all_ok` | Status |
| LAN OK | Binary sensor | `lan_ok` | Status |
| VPN Tunnel Status | Binary sensor | `vpn_tunnel_name` | Status |
| WAN OK | Binary sensor | `wan_ok` | Status |
| WiFi Status | Binary sensor | `wifi_ssid` | Status |
| WiFi OK | Binary sensor | `wlan_ok` | Status |
| Configured VLANs | Sensor | `configured_vlans` | Status |
| Adopted Devices | Sensor | `lan_num_adopted` | Status |
| LAN IoT Devices | Sensor | `lan_num_iot` | Status |
| Switches | Sensor | `lan_num_sw` | Status |
| Wired Devices | Sensor | `lan_num_user` | Status |
| VLANs Total | Sensor | `vlans_total` | Status |
| VPN Status | Sensor | `vpn_status` | Status |
| Total Devices | Sensor | `wan_num_sta` | Status |
| WiFi Networks Total | Sensor | `wifi_networks_total` | Status |
| Access Points | Sensor | `wlan_num_ap` | Status |
| WiFi IoT Devices | Sensor | `wlan_num_iot` | Status |
| WiFi Devices | Sensor | `wlan_num_user` | Status |
| Refresh Now | Button | `refresh` | System |
| WAN1 Run | Button | `wan1_speedtest` | System |
| WAN2 Run | Button | `wan2_speedtest` | System |
| Rogue Proximity Threshold | Number | `rogue_proximity_rssi_threshold` | System |
| Polling Interval | Number | `scan_interval` | System |
| WAN1 Load Balance Weight | Number | `wan1_load_balance_weight` | System |
| WAN1 Load Balance | Sensor | `wan1_weight` | System |
| WAN2 Load Balance | Sensor | `wan2_weight` | System |
| Pause polling | Switch | `pause_polling` | System |

<!-- GENERATED:end -->

---

_Note: The source of truth for these notes is the `about=` fields and `_attr_about` declarations in the component code. This file is generated dynamically from the live HA state attributes and should not be hand-edited._

- **Created:** 2026-08-08
- **Last Updated:** 2026-08-08
