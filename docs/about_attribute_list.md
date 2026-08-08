# `about` Note Inventory

The `about` attribute is a plain-language note attached to key entities to provide context or instructions to the user directly in the Home Assistant More Info dialog (as per [dev_standards](../dev_std/dev_standards.md) §14). They are stored directly in the state machine as entity attributes and do not write to long-term statistics or DB storage.

ᴰ = **disabled by default.**

## Contents

- [Alerts Sub-Device](#alerts-sub-device) (4 entities)
- [Gateway Sub-Device](#gateway-sub-device) (1 entities)
- [Internet Sub-Device](#internet-sub-device) (6 entities)
- [Security Sub-Device](#security-sub-device) (12 entities)
- [Status Sub-Device](#status-sub-device) (2 entities)
- [System Sub-Device](#system-sub-device) (3 entities)
- [🚫 Entities without a note](#-entities-without-a-note)

---

## Overview

**28 of the 130 entities carry an `about` note.** Self-explanatory entities (like LAN IP Address, Model Name, or basic diagnostics) deliberately do not carry notes, as a note on every entity trains users to ignore them.

---

## Alerts Sub-Device

| Entity | About |
| :--- | :--- |
| **UniFi Network Alerts High Sev3 Qty Last 24h** | Count of HIGH (Sev 3) alerts in the last 24 hours, from the UniFi system log. See the Get Alerts action for full history. |
| **UniFi Network Alerts Last High Sev3** | Title of the most recent HIGH (Sev 3) alert; 'None Detected' when there are none. Full history via the Get Alerts action. |
| **UniFi Network Alerts Last Very High Sev4** | Title of the most recent VERY HIGH (Sev 4) alert; 'None Detected' when there are none. Full history via the Get Alerts action. |
| **UniFi Network Alerts Very High Sev4 Qty Last 24h** | Count of VERY HIGH (Sev 4) alerts in the last 24 hours, from the UniFi system log. See the Get Alerts action for full history. |

## Gateway Sub-Device

| Entity | About |
| :--- | :--- |
| **UniFi Network Gateway Board Temperature** | Gateway mainboard temperature — the same reading as 'Phy temperature' in the HA core UniFi Network integration. |

## Internet Sub-Device

| Entity | About |
| :--- | :--- |
| **UniFi Network Internet Month Total** | Combined WAN internet usage (upload + download) for the current calendar month; includes WAN2 when Dual-WAN is enabled. |
| **UniFi Network Internet WAN1 Projected Usage** | Projected WAN1 usage by the end of the calendar month, from usage so far. Check the confidence attribute — it is weak early in the month. |
| **UniFi Network Internet WAN2 Projected Usage** | Projected WAN2 usage by the end of the calendar month, from usage so far. Check the confidence attribute — it is weak early in the month. |
| **UniFi Network Speedtest WAN1 Run** | Press to run an immediate speedtest on this WAN. Takes ~1 minute; results refresh shortly after. |
| **UniFi Network Speedtest WAN2 Run** | Press to run an immediate speedtest on this WAN. Takes ~1 minute; results refresh shortly after. |
| **UniFi Network System WAN1 Load Balance Weight** | WAN1's share of load-balanced traffic; WAN2 automatically gets the remainder (both sum to 100). |

## Security Sub-Device

| Entity | About |
| :--- | :--- |
| **UniFi Network Security Apply AP ignore list** | When on, a rogue is hidden only when every UniFi AP that reports it matches the AP ignore list. Edit the list in Configure. |
| **UniFi Network Security Apply SSID ignore list** | When on, rogue APs whose SSID matches the SSID ignore list are hidden. Edit the list in Configure. |
| **UniFi Network Security Rogue AP Proximity Alert** | On when a rogue AP at or above the Proximity Threshold survives your band/SSID/AP ignore settings. |
| **UniFi Network Security Rogue APs All 24h** | Raw total rogue detections over a rolling 24-hour window, unaffected by any settings or ignore lists. Counts every detection by every UniFi AP — a gauge of background rogue noise/coverage, not unique rogues. |
| **UniFi Network Security Rogue APs New 24h** | Count of rogue BSSIDs first seen by Home Assistant within the last 24 hours — brand-new neighbours/devices, distinct from long-standing ones. Tracked across restarts. Note: on first enable everything counts as new for the first 24h, and BSSID-randomising devices appear new on each rotation. |
| **UniFi Network Security Rogue Access Points** | Filtered count of unique rogue APs after your band, SSID and UniFi AP ignore settings are applied. See 'Rogue APs All 24h' for unfiltered volume. |
| **UniFi Network Security Rogue Detection Period** | How far back each poll looks when counting current rogues. Separate from the on-demand Get Rogue APs action. |
| **UniFi Network Security Rogue Proximity Threshold** | Signal cutoff (dBm) for 'nearby'. Always negative; closer to 0 = stronger/closer. Feeds the Rogue AP Proximity Alert. |
| **UniFi Network Security Show 2.4 GHz rogues** | On: include 2.4 GHz rogue APs in detection. Off: drop them from all rogue sensors. |
| **UniFi Network Security Show 5 GHz rogues** | On: include 5 GHz rogue APs in detection. Off: drop them from all rogue sensors. |
| **UniFi Network Security Strongest Rogue RSSI** | Signal (dBm) of the strongest rogue AP among those left after your inclusion/exclusion settings. |
| **UniFi Network Security Strongest Rogue SSID** | SSID of the strongest rogue AP after your inclusion/exclusion settings. Full list via the Get Rogue APs action. |

## Status Sub-Device

| Entity | About |
| :--- | :--- |
| **UniFi Network Status Guest Users** | Total active sessions tracked by the controller's Guest Portal / Hotspot Manager (voucher, payment, social login, or pending authorization) — may include wired and wireless. |
| **UniFi Network Status WiFi Guests** | Guest-network clients currently connected over WiFi. |

## System Sub-Device

| Entity | About |
| :--- | :--- |
| **UniFi Network System Integration Health** | On when the integration self-diagnoses a problem: a data source is unavailable (and not one you disabled), or a controller update appears to have changed the data format. See the attributes for details. |
| **UniFi Network System Pause polling** | Stops scheduled polling. Manual actions (Refresh Now, speedtest, control changes) still fetch. |
| **UniFi Network System Refresh Now** | Forces an immediate poll, even while Pause Polling is on. |


## 🚫 Entities without a note

To keep the interface clean and avoid user fatigue, notes are omitted from self-explanatory entities. They are grouped here by category:

### Self-explanatory / Diagnostic Identity

The following entities are self-explanatory or direct telemetry/status indicators requiring no note:

- UniFi Network Gateway Application Version
- UniFi Network Gateway CPU temperature
- UniFi Network Gateway CPU utilization
- UniFi Network Gateway Last Backup
- UniFi Network Gateway Memory utilization
- UniFi Network Gateway Storage Total
- UniFi Network Gateway Storage Used
- UniFi Network Gateway Storage Utilization
- UniFi Network Gateway UniFi OS Version
- UniFi Network Gateway Uptime
- UniFi Network Gateway WAN1 SFP Part Number
- UniFi Network Gateway WAN1 SFP Serial Number
- UniFi Network Gateway WAN1 SFP Vendor
- UniFi Network Gateway WAN2 SFP Part Number
- UniFi Network Gateway WAN2 SFP Serial Number
- UniFi Network Gateway WAN2 SFP Vendor
- UniFi Network Internet ISP Name
- UniFi Network Internet ISP Organization
- UniFi Network Internet Internet Drops
- UniFi Network Internet Internet Latency
- UniFi Network Internet Internet Online Since
- UniFi Network Internet Internet Uptime Duration
- UniFi Network Internet WAN1 Availability
- UniFi Network Internet WAN1 Last Restart
- UniFi Network Internet WAN1 Latency
- UniFi Network Internet WAN1 Local IP Address
- UniFi Network Internet WAN1 Name
- UniFi Network Internet WAN1 Public IP Address
- UniFi Network Internet WAN1 Uptime Duration
- UniFi Network Internet WAN2 Availability
- UniFi Network Internet WAN2 Last Restart
- UniFi Network Internet WAN2 Latency
- UniFi Network Internet WAN2 Local IP Address
- UniFi Network Internet WAN2 Name
- UniFi Network Internet WAN2 Public IP Address
- UniFi Network Internet WAN2 Uptime Duration
- UniFi Network Security Rules Active
- UniFi Network Security Rules Configured
- UniFi Network Security Rules Disabled
- UniFi Network Security Threat Management Mode
- UniFi Network Security VPN Connections Active
- UniFi Network Security VPN Connections Total
- UniFi Network Speedtest Last Run Status
- UniFi Network Speedtest WAN1 Download
- UniFi Network Speedtest WAN1 Last Run
- UniFi Network Speedtest WAN1 Monitoring Period
- UniFi Network Speedtest WAN1 Ping
- UniFi Network Speedtest WAN1 Upload
- UniFi Network Speedtest WAN2 Download
- UniFi Network Speedtest WAN2 Last Run
- UniFi Network Speedtest WAN2 Monitoring Period
- UniFi Network Speedtest WAN2 Ping
- UniFi Network Speedtest WAN2 Upload
- UniFi Network Status Access Points
- UniFi Network Status Adopted Devices
- UniFi Network Status Configured VLANs
- UniFi Network Status LAN IoT Devices
- UniFi Network Status Switches
- UniFi Network Status Total Devices
- UniFi Network Status VLANs Active
- UniFi Network Status VLANs Total
- UniFi Network Status VPN Status
- UniFi Network Status WiFi Devices
- UniFi Network Status WiFi IoT Devices
- UniFi Network Status WiFi Networks Active
- UniFi Network Status WiFi Networks Total
- UniFi Network Status Wired Devices
- UniFi Network System Last Updated
- UniFi Network System Multi-WAN Mode
- UniFi Network System Polling Interval
- UniFi Network System WAN1 Load Balance
- UniFi Network System WAN2 Load Balance

### Secondary Telemetry / Totals

The following entities are self-explanatory or direct telemetry/status indicators requiring no note:

- UniFi Network Internet WAN1 Month Download
- UniFi Network Internet WAN1 Month Total
- UniFi Network Internet WAN1 Month Upload
- UniFi Network Internet WAN1 Today Download
- UniFi Network Internet WAN1 Today Total
- UniFi Network Internet WAN1 Today Upload
- UniFi Network Internet WAN2 Month Download
- UniFi Network Internet WAN2 Month Total
- UniFi Network Internet WAN2 Month Upload
- UniFi Network Internet WAN2 Today Download
- UniFi Network Internet WAN2 Today Total
- UniFi Network Internet WAN2 Today Upload

### Binary Connectivity / Status Indicators

The following entities are self-explanatory or direct telemetry/status indicators requiring no note:

- UniFi Network Gateway Update Available
- UniFi Network Internet Internet Connected
- UniFi Network Internet Internet OK
- UniFi Network Internet WAN1 Active Uplink
- UniFi Network Internet WAN1 Link Connected
- UniFi Network Internet WAN2 Active Uplink
- UniFi Network Internet WAN2 Link Connected
- UniFi Network Security Ad Blocking
- UniFi Network Security Honeypot
- UniFi Network Speedtest Last Run Problem
- UniFi Network Status House WiFi Status
- UniFi Network Status IoT-Secure WiFi Status
- UniFi Network Status LAN OK
- UniFi Network Status NetCentral WiFi Status
- UniFi Network Status Network Problem
- UniFi Network Status WAN OK
- UniFi Network Status WiFi OK

### Control / Action Toggles

The following entities are self-explanatory or direct telemetry/status indicators requiring no note:

- UniFi Network System Clean Up Unused Entities


---

*Note: The source of truth for these notes is the `about=` fields and `_attr_about` declarations in the component code. This file is generated dynamically from the live HA state attributes and should not be hand-edited.*

**Created:** 2026-08-08  
**Last Updated:** 2026-08-08
