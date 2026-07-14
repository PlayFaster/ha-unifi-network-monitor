# Sensor Guard Bands

To ensure the Home Assistant UI remains clean and professional, numeric sensors apply "Guard Bands" to incoming API data. If a value falls outside its realistic physical limits, the sensor is marked as `Unavailable` to prevent misleading spikes or impossible values from corrupting dashboards and long-term statistics.

## Split Structure Information

This document is split into two logical parts:

- **Part I: Base Gateway & Network Entities**: Guard bands for the default virtual devices (Gateway and Network Health).
- **Part II: Dynamic UniFi Devices (APs & Switches)**: Guard bands for the physical Access Points and Switches.

---

## Guard Band Strategy

We use a **Declarative Validation** approach. Limits are defined directly within `UnifiSensorEntityDescription` for each sensor. The base class `UnifiSensorBase.native_value` enforces the bounds before the value reaches Home Assistant.

### Why this approach?

- **Readability**: Limits are visible next to the sensor definition in `sensor.py`.
- **Maintainability**: Changing a limit requires updating one number in one place.
- **Stability**: Prevents impossible values (e.g., negative client counts, -5°C on a CPU) from corrupting historical graphs or triggering false automations.

### Implementation

`UnifiSensorEntityDescription` carries `min_limit: float | None` and `max_limit: float | None`. The base class checks:

```python
if desc.min_limit is not None and isinstance(val, (int, float)) and val < desc.min_limit:
    return None
if desc.max_limit is not None and isinstance(val, (int, float)) and val > desc.max_limit:
    return None
```

Non-numeric values (strings, timestamps) pass through unchanged.

**Rounding (complementary):** guard bands reject impossible values; a single `_safe_float` / `_safe_int` coercion helper additionally rounds all numeric telemetry to **3 dp at parse time**, curtailing the dozen-decimal noise the controller can emit (e.g. `99.930600002408 %`) so stored history / LTS stay clean. This is distinct from display: per-sensor `suggested_display_precision` controls how many decimals are *shown*.

---

## Part I: Base Gateway & Network Entities

### Gateway Sensors (`GATEWAY_SENSORS`)

Source: `/stat/device` — gateway hardware data.

| Sensor Key | Translation Key | Min | Max | Rationale |
| :-- | :-- | :-- | :-- | :-- |
| `cpu` | `gateway_cpu` | 0 | 100 | Percentage |
| `ram` | `gateway_ram` | 0 | 100 | Percentage |
| `cpu_temp` | `gateway_cpu_temp` | 0 | 120 | °C — realistic range for embedded networking hardware |
| `board_temp` | `gateway_board_temp` | 0 | 120 | °C — same as CPU temp |
| `uptime` | `gateway_uptime` | — | — | TIMESTAMP — no numeric guard |
| `storage_used` | `gateway_storage_used` | 0 | — | Bytes cannot be negative |
| `storage_size` | `gateway_storage_size` | 0 | — | Bytes cannot be negative |
| `storage_used_pct` | `gateway_storage_used_pct` | 0 | 100 | Percentage |

---

### Network Health Sensors (`HEALTH_SENSORS`)

Source: `/stat/health` — network subsystem health data.

#### WAN subsystem

| Sensor Key | Translation Key | Min | Max | Rationale |
| :-- | :-- | :-- | :-- | :-- |
| `health_wan_isp_name` | `health_wan_isp_name` | — | — | String |
| `health_wan_isp_org` | `health_wan_isp_org` | — | — | String |
| `health_wan_gw_version` | `health_wan_gw_version` | — | — | String |
| `health_wan_num_sta` | `health_wan_num_sta` | 0 | — | Device count cannot be negative |

#### WAN1 uptime monitoring

| Sensor Key | Translation Key | Min | Max | Rationale |
| :-- | :-- | :-- | :-- | :-- |
| `health_wan1_availability` | `health_wan1_availability` | 0 | 100 | Percentage |
| `health_wan1_latency_avg` | `health_wan1_latency_avg` | 0 | 9999 | ms — filters absurd spike values |
| `health_wan1_boot_time` | `health_wan1_boot_time` | — | — | TIMESTAMP |
| `health_wan1_uptime` | `health_wan1_uptime` | 0 | — | Seconds cannot be negative |
| `health_wan1_time_period` | `health_wan1_time_period` | 0 | — | Seconds cannot be negative |

#### WAN2 uptime monitoring

| Sensor Key | Translation Key | Min | Max | Rationale |
| :-- | :-- | :-- | :-- | :-- |
| `health_wan2_availability` | `health_wan2_availability` | 0 | 100 | Percentage |
| `health_wan2_latency_avg` | `health_wan2_latency_avg` | 0 | 9999 | ms — filters absurd spike values |
| `health_wan2_boot_time` | `health_wan2_boot_time` | — | — | TIMESTAMP |
| `health_wan2_uptime` | `health_wan2_uptime` | 0 | — | Seconds cannot be negative |
| `health_wan2_time_period` | `health_wan2_time_period` | 0 | — | Seconds cannot be negative |

#### WWW (internet) subsystem

| Sensor Key | Translation Key | Min | Max | Rationale |
| :-- | :-- | :-- | :-- | :-- |
| `health_www_latency` | `health_www_latency` | 0 | 9999 | ms — filters absurd spike values |
| `health_www_drops` | `health_www_drops` | 0 | — | Drop count cannot be negative |
| `health_www_speedtest_status` | `health_www_speedtest_status` | — | — | String |
| `health_speedtest_pass` | `health_speedtest_pass` | — | — | Binary status check |
| `health_www_uptime` | `health_www_uptime` | 0 | — | Seconds cannot be negative |

#### WLAN subsystem

| Sensor Key | Translation Key | Min | Max | Rationale |
| :-- | :-- | :-- | :-- | :-- |
| `health_wlan_num_user` | `health_wlan_num_user` | 0 | — | Client count cannot be negative |
| `health_wlan_num_guest` | `health_wlan_num_guest` | 0 | — | Client count cannot be negative |
| `health_wlan_num_iot` | `health_wlan_num_iot` | 0 | — | Client count cannot be negative |
| `health_wlan_num_ap` | `health_wlan_num_ap` | 0 | — | AP count cannot be negative |

#### LAN subsystem

| Sensor Key | Translation Key | Min | Max | Rationale |
| :-- | :-- | :-- | :-- | :-- |
| `health_lan_num_user` | `health_lan_num_user` | 0 | — | Client count cannot be negative |
| `health_lan_num_iot` | `health_lan_num_iot` | 0 | — | Client count cannot be negative |
| `health_lan_num_sw` | `health_lan_num_sw` | 0 | — | Switch count cannot be negative |
| `health_lan_num_adopted` | `health_lan_num_adopted` | 0 | — | Adopted device count cannot be negative |

#### VPN subsystem

| Sensor Key          | Translation Key     | Min | Max | Rationale |
| :------------------ | :------------------ | :-- | :-- | :-------- |
| `health_vpn_status` | `health_vpn_status` | —   | —   | String    |

---

### Security & Alerts Sensors

Source: `stat/rogueap` (rogue), `system-log/all` (alerts). These live in the `GATEWAY_SENSORS` tuple with `device_key` `security` / `alerts`.

| Sensor Key | Translation Key | Min | Max | Rationale |
| :-- | :-- | :-- | :-- | :-- |
| `rogue_ap_count` | `gateway_rogue_ap_count` | 0 | — | Count cannot be negative |
| `rogue_raw_24h` | `gateway_rogue_raw_24h` | 0 | — | Raw 24h detection count cannot be negative |
| `strongest_rogue_rssi` | `gateway_strongest_rogue_rssi` | -100 | 0 | dBm — RSSI is negative; `None` (→ `unknown`) when no rogues |
| `strongest_rogue_ssid` | `gateway_strongest_rogue_ssid` | — | — | String — sentinel `"None Detected"` when none |
| `alerts_high_24h` | `gateway_alerts_high_24h` | 0 | — | Count cannot be negative |
| `alerts_very_high_24h` | `gateway_alerts_very_high_24h` | 0 | — | Count cannot be negative |
| `last_high` / `last_very_high` | `gateway_last_high` / `gateway_last_very_high` | — | — | Text (title) — sentinel `"None Detected"` when none |

---

## Part II: Dynamic UniFi Devices (APs & Switches)

### Per-AP Sensors (`AP_SENSORS`)

Source: `/stat/device` — one set of entities per discovered access point.

| Sensor Key | Translation Key | Min | Max | Rationale |
| :-- | :-- | :-- | :-- | :-- |
| `clients` | `device_clients` | 0 | — | Client count cannot be negative |
| `guests` | `device_guests` | 0 | — | Client count cannot be negative |
| `clients_wifi0` | `device_clients_wifi0` | 0 | — | Client count cannot be negative |
| `clients_wifi1` | `device_clients_wifi1` | 0 | — | Client count cannot be negative |
| `score` | `device_score` | -1 | 100 | UniFi reports -1 as "unknown/not computed"; 0–100 otherwise |
| `score_wifi0` | `device_score_wifi0` | -1 | 100 | Same as score — -1 = not available |
| `score_wifi1` | `device_score_wifi1` | -1 | 100 | Same as score — -1 = not available |
| `cpu` | `device_cpu` | 0 | 100 | Percentage |
| `ram` | `device_ram` | 0 | 100 | Percentage |
| `uptime` | `device_uptime` | — | — | TIMESTAMP |

---

### Per-Switch Sensors (`SWITCH_SENSORS`)

Source: `/stat/device` — one set of entities per discovered switch.

| Sensor Key   | Translation Key     | Min | Max | Rationale                     |
| :----------- | :------------------ | :-- | :-- | :---------------------------- |
| `ports_used` | `device_ports_used` | 0   | —   | Port count cannot be negative |
| `cpu`        | `device_cpu`        | 0   | 100 | Percentage                    |
| `ram`        | `device_ram`        | 0   | 100 | Percentage                    |
| `uptime`     | `device_uptime`     | —   | —   | TIMESTAMP                     |

---

## Design Notes

**Upper bound on latency/ping (9999 ms)**: The UniFi API occasionally emits transient spike values (e.g., 99999 ms) when a measurement fails mid-interval. The 9999 ms cap filters these while leaving room for genuinely high-latency links.

**No upper bound on throughput**: `www_xput_up` and `www_xput_down` have no upper bound. Capping at a fixed Mbps value would create a maintenance burden as broadband speeds increase. The `min=0` guard is sufficient to catch firmware glitches returning negative values.

**Score min=-1**: UniFi uses -1 (not null) to represent "satisfaction score not yet computed" for a radio band. The guard band is set to -1 rather than 0 so this valid sentinel value passes through unchanged. A min of 0 would incorrectly suppress newly provisioned APs.

**Temperature bounds (0–120°C)**: The UDM Pro operating range is approximately 0–40°C ambient, with internal chip temperatures reaching 60–80°C under load. The 120°C cap filters sensor errors while not suppressing any realistic reading. Negative temperatures would indicate a sensor fault.

---

## Version Control

- **[2026-06-22]** — Initial document. Guard bands audited across all four sensor tuples.
- **[2026-06-22]** — Added guard bands for new Multi-WAN modes/weights/latencies, storage partition used percentages, and Threat Management.
- **[2026-07-08]** — Restructured into Part I and Part II split structure. Corrected translation and sensor keys to match those present in the manifest.
- **[2026-07-14]** — Added the **Security & Alerts** guard-band table (rogue count / raw-24h / RSSI, alert counts) for the new sub-devices, and documented the `_safe_float` 3-dp rounding helper alongside guard bands.
