# UniFi Network Monitor for Home Assistant

[![HACS Integration](https://img.shields.io/badge/HACS-Integration-orange.svg)](https://hacs.xyz/) [![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5?logo=homeassistant&logoColor=white)](https://hacs.xyz/docs/faq/custom_repositories) [![Latest Release](https://img.shields.io/github/v/release/PlayFaster/ha-unifi-network-monitor?label=Release&logo=github)](https://github.com/PlayFaster/ha-unifi-network-monitor/releases) [![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0) [![Validate](https://github.com/PlayFaster/ha-unifi-network-monitor/actions/workflows/validate.yaml/badge.svg)](https://github.com/PlayFaster/ha-unifi-network-monitor/actions/workflows/validate.yaml) ![Coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/PlayFaster/PLACEHOLDER_GIST_ID/raw/coverage.json) [![Last Commit](https://img.shields.io/github/last-commit/PlayFaster/ha-unifi-network-monitor?label=Last%20commit)](https://github.com/PlayFaster/ha-unifi-network-monitor/commits/main)

A Home Assistant integration for **Ubiquiti UniFi networks** anchored by a UDM Pro (or similar UniFi OS gateway) — providing gateway health, WAN & internet metrics, speedtests, rogue-AP detection, and per-device diagnostics that the official UniFi integration does not expose.

> [!NOTE]
>
> **Is this the right integration for you?**
>
> - **If you run a UniFi network on a UDM Pro** (or similar UniFi OS gateway) and want infrastructure-level monitoring — gateway health, WAN/internet quality, data usage, speedtests, and network security signals — directly in Home Assistant, then **yes**.
> - It is designed to run **alongside** the official Home Assistant UniFi integration (which focuses on client/device tracking). Where both cover the same physical device, entities **merge onto one device card** — no duplicate device entries.
> - **This integration is for you if** you want:
>   - **Gateway & WAN diagnostics** — CPU, memory, temperatures, storage, uptime, dual-WAN status, latency, and daily/monthly data usage.
>   - **Speedtest tracking** — per-WAN download/upload/ping history, plus one-click manual runs.
>   - **Network security signals** — rogue access-point detection with a configurable proximity alert.
>   - **Scoped, low-noise setup** — choose which sensor groups to create; disabled groups also skip their API polls.
>
> This project is developed and tested on the **UDM Pro** but is expected to work with other UniFi OS gateways.

## 📋 Table of Contents

- [UniFi Network Monitor for Home Assistant](#unifi-network-monitor-for-home-assistant)
  - [📋 Table of Contents](#-table-of-contents)
  - [🔧 Compatibility \& Tested Devices](#-compatibility--tested-devices)
  - [🎯 Use Cases](#-use-cases)
  - [✅ Features](#-features)
  - [🔍 What You Get](#-what-you-get)
  - [📸 Screenshots](#-screenshots)
  - [💡 Example Automations](#-example-automations)
  - [📥 Installation](#-installation)
  - [🔧 Configuration](#-configuration)
  - [🧹 Actions (Services)](#-actions-services)
  - [🔩 Under the Hood - Technical Architecture](#-under-the-hood---technical-architecture)
  - [❓ FAQ \& Troubleshooting](#-faq--troubleshooting)
  - [❗ Known Limitations /❔ What's Missing?](#-known-limitations--whats-missing)
  - [❌ Removal](#-removal)
  - [📝 Maintenance Status](#-maintenance-status)
  - [🤝 Contributors \& Acknowledgements](#-contributors--acknowledgements)
  - [📄 License](#-license)

## 🔧 Compatibility & Tested Devices

**📟 Gateway Hardware:**

- **Fully Tested**:
  - **UDM Pro** — tested on **UniFi OS `5.1.19.33549`** with **Network application `10.4.57`**.
- **Expected Compatible**: Other UniFi OS gateways the integration recognises as the gateway device — `UDM`, `UDM-SE`, `UDM Pro SE`, `UDM (base)`, `UNVR`, `UNVR Pro`, `UCG-Ultra`, `UCG-Max`. These are untested.
- **Access Points & Switches**: Adopted UniFi APs and switches are discovered automatically for per-device sensors (optional — see [Configuration](#-configuration)).
- **Not Supported**: Non-UniFi hardware; setups without a UniFi OS gateway.

**🌐 Network:**

- Local network access to the gateway's UniFi Network API is required. No cloud account or internet access is needed.
- **Authentication** — either:
  - A **local API key** (preferred; UniFi OS 3.x and later — `X-API-Key` header), or
  - **Username / password** for the controller (cookie-based session).

**🏠 Home Assistant Version:**

- Minimum: Home Assistant **2024.8.0**
- Minimum Python: **3.12+** (this is built into and handled by HA, but relevant for non-standard installs).

## 🎯 Use Cases

- **Infrastructure Health Monitoring**: Track gateway CPU, memory, temperatures, storage, and uptime — get alerted before a struggling gateway becomes an outage.
- **Dual-WAN & Internet Quality**: Monitor WAN1/WAN2 up/active status, latency, and the active routing interface; drive failover automations and dashboards.
- **Data-Cap Management**: Watch daily and monthly WAN usage and get notified as you approach an ISP data limit.
- **Speedtest History**: Keep a per-WAN record of download/upload/ping and trigger on-demand tests from HA.
- **Network Security Awareness**: Detect nearby **rogue access points** and raise a **Proximity Alert** when an unknown AP is close (strong signal) — useful for spotting rogue/evil-twin APs.
- **Runs With the Official Integration**: Add the infrastructure metrics the native UniFi integration lacks, without duplicate device cards.

## ✅ Features

### 🖥️ Gateway & System Diagnostics

- **Hardware Metrics**: CPU %, memory %, CPU/board temperatures, storage used/size/percentage, and derived uptime/boot time.
- **Firmware & Identity**: UniFi Network application version, gateway model, and SFP transceiver diagnostics.
- **Threat Management State**: IPS/IDS mode, Ad-blocking, and Honeypot status.

### 🌐 WAN, Internet & Data Usage

- **Dual-WAN Status**: WAN1/WAN2 active-uplink and link-up indicators, local/public IP addresses, and configured WAN interface names.
- **Data Usage**: Daily and monthly per-WAN download/upload/total (displayed in GB).
- **Multi-WAN Load Balancing**: Read and adjust the WAN1/WAN2 load-balance weight (always summing to 100).

### ⚡ Speedtest

- **Per-WAN Results**: Download, upload, ping, and last-run time for WAN1 and WAN2.
- **Manual Runs**: **Run WAN1 Speedtest** and **Run WAN2 Speedtest** buttons trigger a test on the specific interface.

### 🛡️ Network Security & Health

- **Rogue AP Detection**: Count of unknown/rogue access points, the **Strongest Rogue SSID** and **Strongest Rogue RSSI**, with the full rogue-AP list as an attribute.
- **Proximity Alert**: A `PROBLEM` binary sensor that fires when the strongest rogue signal is at or above a user-set **Rogue Proximity Threshold** (dBm).
- **Subsystem Health**: Aggregated **Network Problem** indicator plus per-subsystem OK sensors (WAN, Internet/WWW, WiFi/WLAN, LAN).
- **WiFi, VLAN, VPN & Firewall**: Per-SSID broadcast status, per-VPN-tunnel status, VLAN and firewall-rule counts.

### 🔄 Dynamic Polling

- **Pause Polling**: A switch to halt polling temporarily.
- **Configurable Update Interval**: Adjust the scan interval from the HA UI or via automation (default `180` seconds).
- **Standard System Option**: Also honours Home Assistant's **System options > Enable polling for changes** toggle.

### 🎛️ Scoped Setup (Sensor Groups)

Choose at setup — and change any time via **Configure** — which groups of sensors are created. A disabled group both hides its sensors **and skips its API calls**:

- **UniFi device (Access Point & Switch) sensors** — none / AP Satisfaction Score only / all.
- **Speedtest monitoring**, **WAN data-usage statistics**, **Security monitoring** (rogue APs / VPN / firewall).

### 🧹 Housekeeping

- **Clean Up Unused Entities**: A button (and matching action) to remove entities left behind after you turn a sensor group off. See [Actions](#-actions-services).

## 🔍 What You Get

This integration exposes its entities across several sub-devices on the gateway — **Gateway**, **Internet**, **Speedtest**, **Status**, and **System** — plus a dynamic sub-device per adopted **Access Point** and **Switch**. Each sub-device appears as its own card in Home Assistant, and entity IDs are prefixed accordingly (e.g. `sensor.unifi_network_gateway_cpu_temperature`, `binary_sensor.unifi_network_status_network_problem`).

> [!NOTE]
>
> **Entity Visibility:** To keep your Home Assistant UI clean, many secondary/diagnostic entities are **disabled by default**. Enable them via the Entities tab in the device settings. Per-device (AP/switch) sensors are **not created at all by default** — opt in via [Configuration](#-configuration).

The counts below are from a **base install** on a UDM Pro — **no per-device (AP/switch) sensors**, with the **Speedtest**, **WAN data-usage**, and **Security monitoring** groups all **on**. That registers **116 base entities** regardless of anything else; only the enabled-by-default count changes:

- **Without the official HA Core UniFi integration:** **93 enabled / 23 disabled**. The `Enabled / Total` column below reflects this case.
- **With HA Core UniFi installed:** **87 enabled / 29 disabled** — six gateway diagnostics (CPU, Memory, CPU/Board Temperature, Uptime, Update Available) come in **disabled-by-default** because Core already surfaces the gateway (see [Coexistence](#-coexistence-with-the-official-unifi-integration)). So the Gateway row below reads **5 / 18** instead of 11 / 18.

Enable any disabled entity per-entity when you want it. Your totals also differ with your options and hardware (see [Configuration](#-configuration)).

| Sub-Device | Enabled / Total | Key Metrics |
| :-- | :-: | :-- |
| 🖥️ **Gateway** | 11 / 18 | CPU, Memory, CPU/Board Temperature, Storage (used/total/%), Uptime, UniFi OS & Network application versions, WAN1/WAN2 SFP diagnostics, Update Available |
| 🌐 **Internet** | 34 / 39 | WAN1/WAN2 active-uplink & link-up, Local/Public IPs, WAN names, availability, latency, last-restart/uptime, ISP name/org, and daily/monthly data usage; plus Internet Connected / OK, drops, latency, online-since |
| ⚡ **Speedtest** | 14 / 14 | WAN1/WAN2 Download, Upload, Ping, Last Run, Monitoring Period, Last Run Status/Problem; Run WAN1/WAN2 Speedtest buttons |
| 🛡️ **Status** | 22 / 33 | Rogue AP Count, Strongest Rogue SSID/RSSI, Proximity Alert (+ threshold), device/guest/WiFi/VLAN/VPN/firewall counts & per-item status, and the aggregate Network Problem + per-subsystem OK sensors (WAN/Internet/WiFi/LAN) |
| ⚙️ **System** | 12 / 12 | Multi-WAN mode, WAN1/WAN2 Load Balance, Threat-Management mode, Ad-blocking, Honeypot, Polling Interval, Pause Polling, WAN1 Load-Balance Weight, Refresh Now, Clean Up Unused Entities, Last Updated |
| 📶 **Per AP / Per Switch** | opt-in | **11 per AP** (Satisfaction Score + 2.4/5 GHz scores, Clients, Guests, 2.4/5 GHz Clients, CPU, Memory, Uptime, Update Available) · **6 per switch** (Clients, CPU, Memory, Uptime, Model, Update Available) — created only when you choose `Add all device sensors` |

> [!NOTE]
>
> **Per-device sensors scale with your hardware.** Choosing **Add all device sensors** creates one sub-device per adopted AP/switch: **+11 entities per AP** and **+6 per switch**. For example, a rig with 8 APs + 12 switches adds 8×11 + 12×6 = **160 entities**.
>
> **Enabled-by-default depends on HA Core UniFi:** if you do **not** run the official HA Core UniFi integration, all of these per-device entities are created **and enabled**. If you **do** run Core UniFi, only the AP **Satisfaction Score** is enabled by default and the rest come in disabled (they'd duplicate what Core already provides — hence the "duplicates disabled" label).

---

> [!TIP]
>
> **Duplicate-of-core entities:** the per-device Clients / CPU / Memory / Uptime sensors keep their display name but get a `_mon` suffix on their entity ID (e.g. `sensor.<device>_clients_mon`), so when the official UniFi integration is also present you can tell Monitor's copy apart from Core's — on both APs and switches. Per-device entity IDs are prefixed with the **device name**, not `unifi_network_`.

### 📊 Long Term Statistics (LTS)

Home Assistant records Long Term Statistics for a numeric sensor **only when it declares a `state_class`**. Sensors without one still show a live value and short-term history, but are not rolled up into LTS (no hourly min/mean/max, and they can't be used in the Statistics graph). Text, IP, version, mode and timestamp sensors are never LTS candidates.

**Almost every numeric sensor here is in LTS** — CPU/memory/temperatures, signal/RSSI, latency, availability, all counts (devices, clients, VLANs, VPNs, firewall rules, WiFi networks, rogue APs), **monthly** data usage, and speedtest download/upload.

The exceptions — numeric sensors that currently have **no `state_class`** and are therefore **excluded from LTS**:

| Sub-Device | Sensor | Entity ID (this install) | Unit |
| :-- | :-- | :-- | :-- |
| 🖥️ Gateway | Storage Total | `sensor.unifi_network_gateway_storage_total` | GB |
| 🌐 Internet | WAN1/WAN2 Today Download / Upload / Total (6) | `sensor.unifi_network_internet_wan{1,2}_today_{download,upload,total}` | GB |
| 🌐 Internet | WAN1 / WAN2 / Internet Uptime Duration (3) | `sensor.unifi_network_internet_wan{1,2}_uptime_duration`, `…_internet_uptime_duration` | s |
| ⚡ Speedtest | WAN1 / WAN2 Ping (2) | `sensor.unifi_network_speedtest_wan{1,2}_ping` | ms |
| ⚡ Speedtest | WAN1 / WAN2 Monitoring Period (2) | `sensor.unifi_network_speedtest_wan{1,2}_monitoring_period` | h |
| 📶 Access Point | Satisfaction Score / 2.4 GHz / 5 GHz (3) | `sensor.<ap>_satisfaction_score` (+ per-band) | % |

That's **17** numeric sensors (14 base + 3 per-AP). If you want long-term history of any of these — the **daily** usage totals, **Ping**, or the **AP Satisfaction Score** are the natural candidates — give them a `state_class` in `sensor.py` (`measurement`, or `total_increasing` for the daily totals). The full per-sensor breakdown lives in [`docs/all_sensors.md`](docs/all_sensors.md).

## 📸 Screenshots

<!-- PLACEHOLDER: capture and add screenshots under .github/images/ and reference them here (see ZTE README for layout). Suggested shots: integration overview, gateway device, status/security device, speedtest, setup dialog. -->

### Integration Overview

`PLACEHOLDER (.github/images/unifi_integration_screen.png)`

### Setup

`PLACEHOLDER (.github/images/unifi_setup_info.png)`

## 💡 Example Automations

> [!NOTE]
>
> Entity IDs are derived from your gateway/sub-device names and **will differ between installs** (e.g. `sensor.unifi_network_status_...`). Use the entity picker in the Automation editor rather than copying the IDs below verbatim. The examples are illustrative.

### 🛡️ Rogue AP Proximity Alert

Notify when an unknown access point is detected close by (signal at/above your threshold).

```yaml
alias: "UniFi: Rogue AP Nearby"
triggers:
  - trigger: state
    entity_id: binary_sensor.unifi_network_status_rogue_ap_proximity_alert
    to: "on"
    for: "00:02:00"
actions:
  - action: notify.mobile_app_your_phone
    data:
      title: "Rogue AP detected nearby"
      message: >
        Strongest rogue: {{ states('sensor.unifi_network_status_strongest_rogue_ssid') }} at {{ states('sensor.unifi_network_status_strongest_rogue_rssi') }} dBm.
```

### 🌐 Internet / WAN Down Alert

```yaml
alias: "UniFi: Internet Down"
triggers:
  - trigger: state
    entity_id: binary_sensor.unifi_network_internet_internet_connected
    to: "off"
    for: "00:01:00"
actions:
  - action: notify.mobile_app_your_phone
    data:
      title: "Internet connection lost"
      message: "The UniFi gateway reports the internet is down."
```

### 🚨 Monthly Data-Usage Alert

The example assumes usage sensors display in **GB**. Adjust the threshold/units to match your sensor.

```yaml
alias: "UniFi: High WAN Data Usage"
triggers:
  - trigger: numeric_state
    entity_id: sensor.unifi_network_internet_wan1_month_total
    above: 500 # GB
actions:
  - action: notify.mobile_app_your_phone
    data:
      title: "UniFi Data Alert"
      message: "WAN1 monthly usage has exceeded 500 GB."
```

### 🌡️ Gateway Over-Temperature

```yaml
alias: "UniFi: Gateway Hot"
triggers:
  - trigger: numeric_state
    entity_id: sensor.unifi_network_gateway_cpu_temperature
    above: 90 # °C — adjust to your hardware's safe range
    for: "00:05:00"
actions:
  - action: notify.mobile_app_your_phone
    data:
      title: "UniFi gateway temperature high"
      message: "Gateway CPU temperature is {{ states('sensor.unifi_network_gateway_cpu_temperature') }} °C."
```

### 🔁 Auto-Resume Polling

```yaml
alias: "UniFi: Auto-Resume Polling"
description: "Turn polling back on after 1 hour if it was manually paused."
triggers:
  - trigger: state
    entity_id: switch.unifi_network_system_pause_polling
    to: "on"
    for: "01:00:00"
actions:
  - action: switch.turn_off
    target:
      entity_id: switch.unifi_network_system_pause_polling
```

## 📥 Installation

### ✨ HACS (Recommended)

1. Add this [repository](https://github.com/PlayFaster/ha-unifi-network-monitor) as a **Custom Repository** in HACS:
   - Open HACS in Home Assistant
   - Click **Custom repositories** (⋮ menu)
   - Add repository URL and Type: `Integration`
2. Search for "UniFi Network Monitor" and click **Download**
3. Restart Home Assistant
4. Go to **Settings > Devices & Services > Add Integration** and search for "UniFi Network Monitor"

### 💾 Manual Installation

1. Download the [latest release](https://github.com/PlayFaster/ha-unifi-network-monitor/releases).
2. Copy the `custom_components/unifi_network_monitor` folder to your Home Assistant `custom_components` directory
3. Restart Home Assistant
4. Go to **Settings > Devices & Services > Add Integration** and search for "UniFi Network Monitor"

## 🔧 Configuration

### 🔧 Initial Setup

Setup is handled entirely via the UI. Provide connection details for your gateway's UniFi Network API:

- **Host** — Gateway IP address or hostname (e.g. `192.168.1.1`). Any `http://` / `https://` prefix and trailing slashes are stripped automatically.
- **API Key** _(preferred)_ — Local API key from **UniFi Network Settings → Control Plane → API Keys** (UniFi OS 3.x+). Sent as `X-API-Key`.
- **Username / Password** — Alternative to the API key; the same credentials you use for the controller web UI.
- **Site ID** — UniFi site (default `default`; change only if you run multiple sites).

At setup you also choose:

- **UniFi device (Access Point & Switch) sensors** — `Don't add` (default), `AP Satisfaction Score only`, or `Add all` (duplicates disabled).
- **Speedtest monitoring** — on/off (default on).

> [!NOTE]
>
> If the official Home Assistant **UniFi** integration is not installed, the device-sensor choice offers `Don't add` (default) or `Add all`.

### 🔨 Runtime Options (Reconfigure / Configure)

Open **Settings > Devices & Services > UniFi Network Monitor > Configure** (gear), or **⋮ → Reconfigure**, to change connection details and the scoping options. Both screens present the same fields; changes take effect on submit (the entry reloads automatically).

**Sensor groups (enable or disable):**

| Option | Effect when off |
| :-- | :-- |
| Speedtest monitoring | Removes speedtest sensors + run buttons; skips the speedtest poll |
| WAN data-usage statistics | Removes daily/monthly usage sensors; skips those polls |
| Security monitoring | Removes rogue-AP, VPN, and firewall sensors; skips those polls |

> [!NOTE]
>
> Turning a group off **stops creating** its sensors but does **not** delete entities that already exist — they show as `unavailable` until you remove them with the **Clean Up Unused Entities** button or the `unifi_network_monitor.cleanup_unused_entities` action (see [Actions](#-actions-services)).

### 🔘 Runtime Controls & Settings (Entities)

Several settings are exposed as control entities so you can drive them from dashboards or automations:

- **Pause Polling** (`switch`, System) — halt polling temporarily.
- **Polling Interval** (`number`, System) — scan interval in seconds (default `180`).
- **WAN1 Load Balance Weight** (`number`, System) — WAN1 share of a weighted dual-WAN setup; WAN2 is `100 − WAN1`.
- **Rogue Proximity Threshold** (`number`, Status) — dBm at or above which a rogue AP triggers the Proximity Alert (default `-60`; kept negative to match how RSSI is measured). Shown only when Security monitoring is on.
- **Refresh Now** (`button`, System) — immediate data fetch.
- **Clean Up Unused Entities** (`button`, System) — remove orphaned entities (see [Actions](#-actions-services)).

## 🧹 Actions (Services)

### `unifi_network_monitor.cleanup_unused_entities`

Removes entities the current options no longer provide — per-device sensors excluded by the device mode, and gateway sensors for any feature toggled off — and detaches any device left with no Monitor entities. The **Clean Up Unused Entities** button is the one-click equivalent (commit only); this action adds a preview via `dry_run`.

| Parameter | Required | Default | Description |
| :-- | :-- | :-- | :-- |
| `dry_run` | No | `true` | When `true`, only reports what would be removed (nothing is changed). Set `false` to actually remove. |

The action supports **Action Responses**, returning the entities/devices it removed (or would remove) — visible in **Developer Tools → Actions**.

```yaml
# Preview what would be removed (safe — changes nothing)
action: unifi_network_monitor.cleanup_unused_entities
data:
  dry_run: true
response_variable: cleanup_report
```

```yaml
# Actually remove the orphaned entities
action: unifi_network_monitor.cleanup_unused_entities
data:
  dry_run: false
```

> A device shared with the official UniFi integration is **not** deleted — only Monitor's link and entities are removed, leaving the shared device card intact.

## 🔩 Under the Hood - Technical Architecture

### 🔀 Hybrid API Model (Classic + Official v3)

The integration blends two UniFi API generations for the best data:

- **Rich telemetry** comes from the classic `/proxy/network/api/s/{site}/stat/*` endpoints (deep hardware metrics the sparse Official v3 `devices` payload omits).
- **Structured configuration** (WAN interface names, VPN tunnels, firewall rules) comes from the Official v3 / integration endpoints, fetched concurrently via `asyncio.gather()`.
- **Graceful degradation**: if the controller version doesn't support a v3 endpoint, that group degrades to `unavailable` rather than failing the whole update.

### 🔄 Data Polling & Resilience 🩹

A custom `DataUpdateCoordinator` fetches everything per cycle and applies two resilience layers:

- **Global 3-strike** over the mandatory device/health fetches: holds last-known values for up to 3 consecutive failures before marking entities `Unavailable`; auto-recovers on the next good poll.
- **Per-endpoint resilience** for the optional endpoints: each holds its own last-good value for up to 3 failures, then only **its** entities go `unavailable` — a single flaky endpoint (or an API change) degrades one sensor group, not the whole integration.
- **Triggered refresh**: buttons (Refresh, Speedtest) request an immediate fetch for instant feedback.

### 🆔 Flat Identity & Stable Entities

- Gateway **MAC**, model, and firmware version are stored at setup and loaded without a network call, so device metadata is stable immediately at boot.
- **Guard bands**: numeric sensors validate against min/max limits; out-of-range readings are ignored (returned as unknown) to keep history clean.
- **`unknown` vs `unavailable`**: a value that's legitimately absent while the source is healthy reads `unknown` (e.g. Strongest Rogue RSSI with no rogues present); a stale/unreachable endpoint reads `unavailable`.

### 🤝 Coexistence with the Official UniFi Integration

The gateway and all physical devices use `connections={(CONNECTION_NETWORK_MAC, mac)}`, so Home Assistant **merges** this integration's device entries with the official UniFi integration's entries for the same MAC — one device card, both integrations' entities. Duplicate per-device sensors are opt-in and, when created, carry a `_mon` entity-ID suffix.

**Gateway card:** when Core UniFi is installed, this integration's **Gateway** sub-device merges into Core's gateway card (it adopts Core's device name, e.g. `UDM-Pro`, and Core's firmware string). The other four sub-devices (Internet, Speedtest, Status, System) use identifiers only, so they remain separate cards hanging off the gateway.

**Disabled-by-default when Core is present:** to avoid duplicating what Core already provides on that shared card, six gateway diagnostics — **CPU utilization, Memory utilization, CPU temperature, Board Temperature, Uptime, and Update Available** — are **disabled-by-default whenever Core UniFi is installed**, and enabled-by-default only when it isn't. Core surfaces the gateway's CPU and memory itself; the temperatures are unique to this integration but are still left off by default to keep the merged card tidy — enable them (from either integration) if you want them.

### 🔄 Dynamic Polling & Standard System Options

Dynamic pause/interval controls coexist with Home Assistant's standard **System options > Enable polling for changes** toggle (both are honoured).

## ❓ FAQ & Troubleshooting

### 🔌 Connection & Authentication

#### **"Failed to connect" / "Authentication failed"**

- Verify the **Host** is correct and reachable from Home Assistant.
- Prefer an **API key** (UniFi OS 3.x+) from **Network Settings → Control Plane → API Keys**.
- If using **username/password**, confirm they match the controller web UI login (and that they haven't been changed).
- Confirm the **Site ID** (usually `default`).

#### 🔑 **Should I use an API key or username/password?**

- **API key is preferred** — it's stateless (`X-API-Key` header) and avoids session juggling. Username/password uses a cookie session and re-authenticates automatically on expiry.

### 📊 Entities & Values

#### ❔ **Some sensors show "Unknown"**

- Expected. Not every metric exists on every firmware/site (e.g. Strongest Rogue RSSI is `unknown` when no rogue APs are detected; v3-only config sensors are `unknown` on older controllers).

#### 🛑 **A group of sensors shows "Unavailable"**

- That endpoint has failed its retry strikes (see [Resilience](#-data-polling--resilience-)) — the rest keep working. It recovers automatically when the endpoint responds again.

#### 🖥️ **My gateway CPU / Memory / Temperature / Uptime sensors are disabled**

- Expected **when the official HA Core UniFi integration is installed**. Six gateway diagnostics (CPU, Memory, CPU/Board Temperature, Uptime, Update Available) are disabled-by-default in that case because Core already covers the gateway — see [Coexistence](#-coexistence-with-the-official-unifi-integration). Enable any you want from the device's Entities tab. Without Core UniFi, these are enabled by default.

#### 👯 **I see duplicate `_2` entities**

- These appear when per-device sensors are set to **all** and the official UniFi integration is also present. Newer installs use a `_mon` suffix instead. To remove leftover duplicates, set the device mode appropriately and run **Clean Up Unused Entities** (or the action). `PLACEHOLDER: confirm phrasing once the _mon migration story is finalised.`

#### 🧹 **I turned a sensor group off but the entities are still there (Unavailable)**

- By design, options never delete. Use the **Clean Up Unused Entities** button, or run `unifi_network_monitor.cleanup_unused_entities` with `dry_run: false`.

## ❗ Known Limitations /❔ What's Missing?

- **Firmware/endpoint variance**: available data depends on your UniFi OS / Network application version; some v3 configuration sensors require newer controllers.
- **Tested hardware**: developed and tested on the **UDM Pro** only; other UniFi OS gateways are expected-compatible but unverified.
- **Client tracking is out of scope**: this integration monitors infrastructure. For per-client device tracking, use the **official Home Assistant UniFi integration** alongside it.
- **Data Rates**: Current upload and download data rates (i.e. MBit/s) from WAN1 and WAN2 are available from the UniFi API, but are only useful if you are polling very _frequently_. That's not part of the design scope for this integration, so it is not planned to add data rates.
- `PLACEHOLDER: add any further known limitations discovered during real-world use.`

## ❌ Removal

To remove the integration from Home Assistant:

1. Go to **Settings > Devices & Services**.
2. Find the **UniFi Network Monitor** card and click into it.
3. Click the **three dots** (⋮) next to the gear icon and select **Delete**.
4. Confirm deletion.

To fully uninstall (HACS):

1. Go to **HACS**.
2. Find **UniFi Network Monitor** and click into it.
3. Click the **three dots** (⋮) at the top right and select **Remove**.
4. Restart Home Assistant.
5. Home Assistant automatically removes all associated entities and device entries from the registry when the integration is deleted.

## 📝 Maintenance Status

This is a **personal project**. Support and updates are provided on a **"best-effort"** basis only. While I use this integration daily and aim to keep it functional with the latest Home Assistant releases, I cannot guarantee immediate fixes for issues or compatibility with all UniFi firmware versions.

---

## 🤝 Contributors & Acknowledgements

- This project was developed with the assistance of AI to ensure code quality and adherence to best practices.
- `PLACEHOLDER: add any third-party projects, prior art, or contributors to acknowledge.`

---

## 📄 License

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

This project is licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for details.

---

💬 **Questions or Issues?** Visit the [GitHub repository](https://github.com/PlayFaster/ha-unifi-network-monitor).
