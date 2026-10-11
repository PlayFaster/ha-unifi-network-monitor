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

**Rounding (complementary):** guard bands reject impossible values; a single `_safe_float` / `_safe_int` coercion helper additionally rounds all numeric sensor values to **3 dp at parse time**, curtailing the dozen-decimal noise the controller can emit (e.g. `99.930600002408 %`) so stored history / LTS stay clean. This is distinct from display: per-sensor `suggested_display_precision` controls how many decimals are _shown_.

---

## Part I: Base Gateway & Network Entities

<!-- GENERATED:start -->

| Sub-device | Sensor key                |      Min |      Max | Unit   |
| :--------- | :------------------------ | -------: | -------: | :----- |
| Alerts     | `alerts_high_24h`         |    `0.0` |        — | —      |
| Alerts     | `alerts_very_high_24h`    |    `0.0` |        — | —      |
| Gateway    | `board_temp`              |    `0.0` |  `120.0` | °C     |
| Gateway    | `clients`                 |    `0.0` |        — | —      |
| Gateway    | `clients_wifi0`           |    `0.0` |        — | —      |
| Gateway    | `clients_wifi1`           |    `0.0` |        — | —      |
| Gateway    | `cpu`                     |    `0.0` |  `100.0` | %      |
| Gateway    | `cpu`                     |    `0.0` |  `100.0` | %      |
| Gateway    | `cpu`                     |    `0.0` |  `100.0` | %      |
| Gateway    | `cpu_temp`                |    `0.0` |  `120.0` | °C     |
| Gateway    | `guests`                  |    `0.0` |        — | —      |
| Gateway    | `ports_used`              |    `0.0` |        — | —      |
| Gateway    | `ram`                     |    `0.0` |  `100.0` | %      |
| Gateway    | `ram`                     |    `0.0` |  `100.0` | %      |
| Gateway    | `ram`                     |    `0.0` |  `100.0` | %      |
| Gateway    | `score`                   |    `0.0` |  `100.0` | %      |
| Gateway    | `score_wifi0`             |    `0.0` |  `100.0` | %      |
| Gateway    | `score_wifi1`             |    `0.0` |  `100.0` | %      |
| Gateway    | `storage_size`            |    `0.0` |        — | B      |
| Gateway    | `storage_used`            |    `0.0` |        — | B      |
| Gateway    | `storage_used_pct`        |    `0.0` |  `100.0` | %      |
| Internet   | `month_total`             |    `0.0` |        — | B      |
| Internet   | `wan1_availability`       |    `0.0` |  `100.0` | %      |
| Internet   | `wan1_latency_avg`        |    `0.0` | `9999.0` | ms     |
| Internet   | `wan1_month_projected`    |    `0.0` |        — | B      |
| Internet   | `wan1_month_rx`           |    `0.0` |        — | B      |
| Internet   | `wan1_month_total`        |    `0.0` |        — | B      |
| Internet   | `wan1_month_tx`           |    `0.0` |        — | B      |
| Internet   | `wan1_today_rx`           |    `0.0` |        — | B      |
| Internet   | `wan1_today_total`        |    `0.0` |        — | B      |
| Internet   | `wan1_today_tx`           |    `0.0` |        — | B      |
| Internet   | `wan1_uptime`             |    `0.0` |        — | s      |
| Internet   | `wan2_availability`       |    `0.0` |  `100.0` | %      |
| Internet   | `wan2_latency_avg`        |    `0.0` | `9999.0` | ms     |
| Internet   | `wan2_month_projected`    |    `0.0` |        — | B      |
| Internet   | `wan2_month_rx`           |    `0.0` |        — | B      |
| Internet   | `wan2_month_total`        |    `0.0` |        — | B      |
| Internet   | `wan2_month_tx`           |    `0.0` |        — | B      |
| Internet   | `wan2_today_rx`           |    `0.0` |        — | B      |
| Internet   | `wan2_today_total`        |    `0.0` |        — | B      |
| Internet   | `wan2_today_tx`           |    `0.0` |        — | B      |
| Internet   | `wan2_uptime`             |    `0.0` |        — | s      |
| Internet   | `www_drops`               |    `0.0` |        — | —      |
| Internet   | `www_latency`             |    `0.0` | `9999.0` | ms     |
| Internet   | `www_uptime`              |    `0.0` |        — | s      |
| Security   | `rogue_ap_count`          |    `0.0` |        — | —      |
| Security   | `rogue_new_24h`           |    `0.0` |        — | —      |
| Security   | `rogue_raw_24h`           |    `0.0` |        — | —      |
| Security   | `rules_active`            |    `0.0` |        — | —      |
| Security   | `rules_configured`        |    `0.0` |        — | —      |
| Security   | `rules_disabled`          |    `0.0` |        — | —      |
| Security   | `strongest_rogue_rssi`    | `-100.0` |    `0.0` | dBm    |
| Security   | `vpn_connections_active`  |    `0.0` |        — | —      |
| Security   | `vpn_connections_total`   |    `0.0` |        — | —      |
| Speedtest  | `wan1_speedtest_download` |    `0.0` |        — | Mbit/s |
| Speedtest  | `wan1_speedtest_ping`     |    `0.0` | `9999.0` | ms     |
| Speedtest  | `wan1_speedtest_upload`   |    `0.0` |        — | Mbit/s |
| Speedtest  | `wan1_time_period`        |    `0.0` |        — | s      |
| Speedtest  | `wan2_speedtest_download` |    `0.0` |        — | Mbit/s |
| Speedtest  | `wan2_speedtest_ping`     |    `0.0` | `9999.0` | ms     |
| Speedtest  | `wan2_speedtest_upload`   |    `0.0` |        — | Mbit/s |
| Speedtest  | `wan2_time_period`        |    `0.0` |        — | s      |
| Status     | `configured_vlans`        |    `0.0` |        — | —      |
| Status     | `guest_user_count`        |    `0.0` |        — | —      |
| Status     | `lan_num_adopted`         |    `0.0` |        — | —      |
| Status     | `lan_num_iot`             |    `0.0` |        — | —      |
| Status     | `lan_num_sw`              |    `0.0` |        — | —      |
| Status     | `lan_num_user`            |    `0.0` |        — | —      |
| Status     | `vlans_active`            |    `0.0` |        — | —      |
| Status     | `vlans_total`             |    `0.0` |        — | —      |
| Status     | `wan_num_sta`             |    `0.0` |        — | —      |
| Status     | `wifi_networks_active`    |    `0.0` |        — | —      |
| Status     | `wifi_networks_total`     |    `0.0` |        — | —      |
| Status     | `wlan_num_ap`             |    `0.0` |        — | —      |
| Status     | `wlan_num_guest`          |    `0.0` |        — | —      |
| Status     | `wlan_num_iot`            |    `0.0` |        — | —      |
| Status     | `wlan_num_user`           |    `0.0` |        — | —      |
| System     | `wan1_weight`             |    `0.0` |  `100.0` | %      |
| System     | `wan2_weight`             |    `0.0` |  `100.0` | %      |

<!-- GENERATED:end -->

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
