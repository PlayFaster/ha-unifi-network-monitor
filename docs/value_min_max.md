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
```

Non-numeric values (strings, timestamps) pass through unchanged.

**Rounding (complementary):** guard bands reject impossible values; a single `_safe_float` / `_safe_int` coercion helper additionally rounds all numeric telemetry to **3 dp at parse time**, curtailing the dozen-decimal noise the controller can emit (e.g. `99.930600002408 %`) so stored history / LTS stay clean. This is distinct from display: per-sensor `suggested_display_precision` controls how many decimals are _shown_.

---

## Part I: Base Gateway & Network Entities

### Gateway Sensors (`GATEWAY_SENSORS`)

Source: `/stat/device` — gateway hardware data.

| Sensor Key         | Translation Key            | Min | Max | Rationale                                             |
| :----------------- | :------------------------- | :-- | :-- | :---------------------------------------------------- |
| `cpu`              | `gateway_cpu`              | 0   | 100 | Percentage                                            |
| `ram`              | `gateway_ram`              | 0   | 100 | Percentage                                            |
| `cpu_temp`         | `gateway_cpu_temp`         | 0   | 120 | °C — realistic range for embedded networking hardware |
| `board_temp`       | `gateway_board_temp`       | 0   | 120 | °C — same as CPU temp                                 |
| `uptime`           | `gateway_uptime`           | —   | —   | TIMESTAMP — no numeric guard                          |
| `storage_used`     | `gateway_storage_used`     | 0   | —   | Bytes cannot be negative                              |
| `storage_size`     | `gateway_storage_size`     | 0   | —   | Bytes cannot be negative                              |
| `storage_used_pct` | `gateway_storage_used_pct` | 0   | 100 | Percentage                                            |

---

### Internet & WAN Sensors

Source: `/stat/device` (load balance, real-time interface telemetry), `report/daily.gw` and `report/monthly.gw` (usage). All live in the `GATEWAY_SENSORS` tuple with `device_key` `internet`.

Every byte counter is bounded below at `0` and **deliberately has no upper bound**: a total has no credible ceiling, and inventing one would send the sensor to `unknown` for the remainder of the cycle the moment real usage crossed it. That is the single most important rule on this page — a guard band exists to reject impossible values, not large ones.

| Sensor Key             | Translation Key                | Min | Max | Rationale                                                                                       |
| :--------------------- | :----------------------------- | :-- | :-- | :---------------------------------------------------------------------------------------------- |
| `wan1_weight`          | `gateway_wan1_weight`          | 0   | 100 | Load-balance share, percentage — the pair sums to 100                                           |
| `wan2_weight`          | `gateway_wan2_weight`          | 0   | 100 | Percentage — as WAN1                                                                            |
| `wan1_today_rx`        | `gateway_wan1_today_rx`        | 0   | —   | Bytes cannot be negative; no ceiling on a total                                                 |
| `wan1_today_tx`        | `gateway_wan1_today_tx`        | 0   | —   | As above                                                                                        |
| `wan1_today_total`     | `gateway_wan1_today_total`     | 0   | —   | As above                                                                                        |
| `wan2_today_rx`        | `gateway_wan2_today_rx`        | 0   | —   | As above                                                                                        |
| `wan2_today_tx`        | `gateway_wan2_today_tx`        | 0   | —   | As above                                                                                        |
| `wan2_today_total`     | `gateway_wan2_today_total`     | 0   | —   | As above                                                                                        |
| `wan1_month_rx`        | `gateway_wan1_month_rx`        | 0   | —   | As above                                                                                        |
| `wan1_month_tx`        | `gateway_wan1_month_tx`        | 0   | —   | As above                                                                                        |
| `wan1_month_total`     | `gateway_wan1_month_total`     | 0   | —   | As above                                                                                        |
| `wan2_month_rx`        | `gateway_wan2_month_rx`        | 0   | —   | As above                                                                                        |
| `wan2_month_tx`        | `gateway_wan2_month_tx`        | 0   | —   | As above                                                                                        |
| `wan2_month_total`     | `gateway_wan2_month_total`     | 0   | —   | As above                                                                                        |
| `month_total`          | `gateway_month_total`          | 0   | —   | As above                                                                                        |
| `wan1_month_projected` | `gateway_wan1_month_projected` | 0   | —   | Projected end-of-month bytes. A **forecast**, so it carries no `state_class` — see Design Notes |
| `wan2_month_projected` | `gateway_wan2_month_projected` | 0   | —   | As WAN1; created only when dual-WAN monitoring is enabled                                       |
| `guest_user_count`     | `gateway_guest_user_count`     | 0   | —   | Client count cannot be negative                                                                 |

---

### Speedtest Sensors

Source: `archive.speedtest`. `device_key` `speedtest`.

| Sensor Key                | Translation Key                   | Min | Max  | Rationale                                                                      |
| :------------------------ | :-------------------------------- | :-- | :--- | :----------------------------------------------------------------------------- |
| `wan1_speedtest_download` | `gateway_wan1_speedtest_download` | 0   | —    | Mbit/s — no ceiling, so the guard does not need revisiting as links get faster |
| `wan1_speedtest_upload`   | `gateway_wan1_speedtest_upload`   | 0   | —    | As download                                                                    |
| `wan1_speedtest_ping`     | `gateway_wan1_speedtest_ping`     | 0   | 9999 | ms — same transient-spike cap as the latency sensors                           |
| `wan2_speedtest_download` | `gateway_wan2_speedtest_download` | 0   | —    | As WAN1                                                                        |
| `wan2_speedtest_upload`   | `gateway_wan2_speedtest_upload`   | 0   | —    | As WAN1                                                                        |
| `wan2_speedtest_ping`     | `gateway_wan2_speedtest_ping`     | 0   | 9999 | As WAN1                                                                        |

---

### Configuration Count Sensors

Source: `rest/wlanconf`, `rest/networkconf`, and the v3 integration endpoints for VPN and firewall. `device_key` `status` / `security`.

All are counts, so all are bounded below at `0` with no ceiling. Note the v3-fed ones are legitimately `unknown` under username/password auth — those endpoints are API-key only, and that is expected rather than a fault (`AGENTS.md`, `DEVELOPMENT.md` §5).

| Sensor Key               | Translation Key                  | Min | Max | Rationale                                   |
| :----------------------- | :------------------------------- | :-- | :-- | :------------------------------------------ |
| `wifi_networks_total`    | `gateway_wifi_networks_total`    | 0   | —   | Count cannot be negative                    |
| `wifi_networks_active`   | `gateway_wifi_networks_active`   | 0   | —   | Count cannot be negative                    |
| `configured_vlans`       | `gateway_configured_vlans`       | 0   | —   | Count cannot be negative                    |
| `vlans_total`            | `gateway_vlans_total`            | 0   | —   | Count cannot be negative                    |
| `vlans_active`           | `gateway_vlans_active`           | 0   | —   | Count cannot be negative                    |
| `vpn_connections_total`  | `gateway_vpn_connections_total`  | 0   | —   | Count cannot be negative; v3 — API-key only |
| `vpn_connections_active` | `gateway_vpn_connections_active` | 0   | —   | As above                                    |
| `rules_configured`       | `gateway_rules_configured`       | 0   | —   | As above                                    |
| `rules_active`           | `gateway_rules_active`           | 0   | —   | As above                                    |
| `rules_disabled`         | `gateway_rules_disabled`         | 0   | —   | As above                                    |

---

### Network Health Sensors (`HEALTH_SENSORS`)

Source: `/stat/health` — network subsystem health data.

#### WAN subsystem

| Sensor Key              | Translation Key         | Min | Max | Rationale                       |
| :---------------------- | :---------------------- | :-- | :-- | :------------------------------ |
| `health_wan_isp_name`   | `health_wan_isp_name`   | —   | —   | String                          |
| `health_wan_isp_org`    | `health_wan_isp_org`    | —   | —   | String                          |
| `health_wan_gw_version` | `health_wan_gw_version` | —   | —   | String                          |
| `health_wan_num_sta`    | `health_wan_num_sta`    | 0   | —   | Device count cannot be negative |

#### WAN1 uptime monitoring

| Sensor Key                 | Translation Key            | Min | Max  | Rationale                        |
| :------------------------- | :------------------------- | :-- | :--- | :------------------------------- |
| `health_wan1_availability` | `health_wan1_availability` | 0   | 100  | Percentage                       |
| `health_wan1_latency_avg`  | `health_wan1_latency_avg`  | 0   | 9999 | ms — filters absurd spike values |
| `health_wan1_boot_time`    | `health_wan1_boot_time`    | —   | —    | TIMESTAMP                        |
| `health_wan1_uptime`       | `health_wan1_uptime`       | 0   | —    | Seconds cannot be negative       |
| `health_wan1_time_period`  | `health_wan1_time_period`  | 0   | —    | Seconds cannot be negative       |

#### WAN2 uptime monitoring

| Sensor Key                 | Translation Key            | Min | Max  | Rationale                        |
| :------------------------- | :------------------------- | :-- | :--- | :------------------------------- |
| `health_wan2_availability` | `health_wan2_availability` | 0   | 100  | Percentage                       |
| `health_wan2_latency_avg`  | `health_wan2_latency_avg`  | 0   | 9999 | ms — filters absurd spike values |
| `health_wan2_boot_time`    | `health_wan2_boot_time`    | —   | —    | TIMESTAMP                        |
| `health_wan2_uptime`       | `health_wan2_uptime`       | 0   | —    | Seconds cannot be negative       |
| `health_wan2_time_period`  | `health_wan2_time_period`  | 0   | —    | Seconds cannot be negative       |

#### WWW (internet) subsystem

| Sensor Key                    | Translation Key               | Min | Max  | Rationale                        |
| :---------------------------- | :---------------------------- | :-- | :--- | :------------------------------- |
| `health_www_latency`          | `health_www_latency`          | 0   | 9999 | ms — filters absurd spike values |
| `health_www_drops`            | `health_www_drops`            | 0   | —    | Drop count cannot be negative    |
| `health_www_speedtest_status` | `health_www_speedtest_status` | —   | —    | String                           |
| `health_speedtest_pass`       | `health_speedtest_pass`       | —   | —    | Binary status check              |
| `health_www_uptime`           | `health_www_uptime`           | 0   | —    | Seconds cannot be negative       |

#### WLAN subsystem

| Sensor Key              | Translation Key         | Min | Max | Rationale                       |
| :---------------------- | :---------------------- | :-- | :-- | :------------------------------ |
| `health_wlan_num_user`  | `health_wlan_num_user`  | 0   | —   | Client count cannot be negative |
| `health_wlan_num_guest` | `health_wlan_num_guest` | 0   | —   | Client count cannot be negative |
| `health_wlan_num_iot`   | `health_wlan_num_iot`   | 0   | —   | Client count cannot be negative |
| `health_wlan_num_ap`    | `health_wlan_num_ap`    | 0   | —   | AP count cannot be negative     |

#### LAN subsystem

| Sensor Key               | Translation Key          | Min | Max | Rationale                               |
| :----------------------- | :----------------------- | :-- | :-- | :-------------------------------------- |
| `health_lan_num_user`    | `health_lan_num_user`    | 0   | —   | Client count cannot be negative         |
| `health_lan_num_iot`     | `health_lan_num_iot`     | 0   | —   | Client count cannot be negative         |
| `health_lan_num_sw`      | `health_lan_num_sw`      | 0   | —   | Switch count cannot be negative         |
| `health_lan_num_adopted` | `health_lan_num_adopted` | 0   | —   | Adopted device count cannot be negative |

#### VPN subsystem

| Sensor Key          | Translation Key     | Min | Max | Rationale |
| :------------------ | :------------------ | :-- | :-- | :-------- |
| `health_vpn_status` | `health_vpn_status` | —   | —   | String    |

---

### Security & Alerts Sensors

Source: `stat/rogueap` (rogue), `system-log/all` (alerts). These live in the `GATEWAY_SENSORS` tuple with `device_key` `security` / `alerts`.

| Sensor Key                     | Translation Key                                | Min  | Max | Rationale                                                       |
| :----------------------------- | :--------------------------------------------- | :--- | :-- | :-------------------------------------------------------------- |
| `rogue_ap_count`               | `gateway_rogue_ap_count`                       | 0    | —   | Count cannot be negative                                        |
| `rogue_raw_24h`                | `gateway_rogue_raw_24h`                        | 0    | —   | Raw 24h detection count cannot be negative                      |
| `rogue_new_24h`                | `gateway_rogue_new_24h`                        | 0    | —   | Count of BSSIDs first seen in HA within 24h; cannot be negative |
| `strongest_rogue_rssi`         | `gateway_strongest_rogue_rssi`                 | -100 | 0   | dBm — RSSI is negative; `None` (→ `unknown`) when no rogues     |
| `strongest_rogue_ssid`         | `gateway_strongest_rogue_ssid`                 | —    | —   | String — sentinel `"None Detected"` when none                   |
| `alerts_high_24h`              | `gateway_alerts_high_24h`                      | 0    | —   | Count cannot be negative                                        |
| `alerts_very_high_24h`         | `gateway_alerts_very_high_24h`                 | 0    | —   | Count cannot be negative                                        |
| `last_high` / `last_very_high` | `gateway_last_high` / `gateway_last_very_high` | —    | —   | Text (title) — sentinel `"None Detected"` when none             |

---

## Part II: Dynamic UniFi Devices (APs & Switches)

### Per-AP Sensors (`AP_SENSORS`)

Source: `/stat/device` — one set of entities per discovered access point.

| Sensor Key      | Translation Key        | Min | Max | Rationale                                                                                                      |
| :-------------- | :--------------------- | :-- | :-- | :------------------------------------------------------------------------------------------------------------- |
| `clients`       | `device_clients`       | 0   | —   | Client count cannot be negative                                                                                |
| `guests`        | `device_guests`        | 0   | —   | Client count cannot be negative                                                                                |
| `clients_wifi0` | `device_clients_wifi0` | 0   | —   | Client count cannot be negative                                                                                |
| `clients_wifi1` | `device_clients_wifi1` | 0   | —   | Client count cannot be negative                                                                                |
| `score`         | `device_score`         | 0   | 100 | Satisfaction percentage. UniFi's `-1` is deliberately **excluded** and renders as `unknown` — see Design Notes |
| `score_wifi0`   | `device_score_wifi0`   | 0   | 100 | Same as `score`                                                                                                |
| `score_wifi1`   | `device_score_wifi1`   | 0   | 100 | Same as `score`                                                                                                |
| `cpu`           | `device_cpu`           | 0   | 100 | Percentage                                                                                                     |
| `ram`           | `device_ram`           | 0   | 100 | Percentage                                                                                                     |
| `uptime`        | `device_uptime`        | —   | —   | TIMESTAMP                                                                                                      |

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

**Score min=0, and `-1` is deliberately excluded**: UniFi uses `-1` (not null) to mean "satisfaction score not yet computed" for a radio band. That is an **indicator, not a measurement** — admitting it would put a value on a percentage sensor that is not a percentage, and it would chart, average and enter long-term statistics as though the AP had scored below zero. The guard band is therefore `0`, which turns the sentinel into `unknown`, and `unknown` is the correct answer to "what is the score?" when there is not one yet (dev_standards §18 — a sentinel belongs in `unknown`).

This document previously specified `-1` and argued that a min of `0` would wrongly suppress newly provisioned APs. **That reasoning is superseded.** Suppression is the intended outcome: a newly provisioned AP has no score, and reporting `unknown` says so, whereas reporting `-1` invents a number. The code has always shipped `0`; this document was the side that was wrong.

**Projections carry no `state_class`**: `wan1_month_projected` and `wan2_month_projected` are forecasts, not measurements. They are bounded below at `0` like any byte counter, but they are deliberately kept out of statistics and long-term storage — a forecast that revises itself every poll would corrupt any long-term series it entered. The confidence in the figure is published as a `confidence` attribute alongside it rather than withheld as `unknown`, because a blank sensor on the 1st of the month reads as broken.

**Temperature bounds (0–120°C)**: The UDM Pro operating range is approximately 0–40°C ambient, with internal chip temperatures reaching 60–80°C under load. The 120°C cap filters sensor errors while not suppressing any realistic reading. Negative temperatures would indicate a sensor fault.

---

## Version Control

- **[2026-06-22]** — Initial document. Guard bands audited across all four sensor tuples.
- **[2026-06-22]** — Added guard bands for new Multi-WAN modes/weights/latencies, storage partition used percentages, and Threat Management.
- **[2026-07-08]** — Restructured into Part I and Part II split structure. Corrected translation and sensor keys to match those present in the manifest.
- **[2026-07-14]** — Added the **Security & Alerts** guard-band table (rogue count / raw-24h / RSSI, alert counts) for the new sub-devices, and documented the `_safe_float` 3-dp rounding helper alongside guard bands.
