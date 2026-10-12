# UniFi Network Monitor Capabilities Dossier

An architectural reference and at-a-glance inventory of verified capabilities, interfaces, technical guarantees, and version lineage for `ha-unifi-network-monitor`.

**Current Through:** `v1.1.0-dev11` (covering `v1.0.0` to `v1.1.0-dev11`) · **Last Audited:** 2026-10-11 · **Status:** `In-Progress Dev`

Version lineage: the `1.0.1-dev1` to `1.0.1-dev22` series shipped as public `v1.1.0` on 2026-08-08. `1.1.0-dev3` to `1.1.0-dev11` are unreleased builds that follow it. Capabilities that predate the detailed changelog are recorded as `v1.0.0 verified`, the earliest verified release.

---

## 1. Connection & Session Control

### Hybrid API Access with Dual Authentication

- **Purpose**: Reads a UniFi Network site through the classic `/proxy/network/api/s/{site}/…` endpoints and, where available, the Official v3 / Integration endpoints, under either an API key or username and password.
- **Entities & Interfaces**: Config flow fields `host`, `api_key`, `username`, `password`, `site`; `api.py` (`UnifiNetworkAPI`).
- **Technical Guarantees**:
  - Classic `stat/*` endpoints serve device and health data under either authentication mode.
  - Official v3 / Integration endpoints (WAN names, VPN tunnels, firewall policies) are fetched concurrently via `asyncio.gather()` and are reachable only with an API key; under username and password auth the seven sensors they feed stay `unknown`, which is documented as expected behavior.
  - A v3 endpoint that is unsupported or fails degrades its sensor group to `unavailable` without failing the update cycle.
- **Lifecycle Timeline**:
  - `v1.0.0 verified`: Hybrid classic and v3 model in place.
  - `v1.1.0`: The API-key menu path in the setup form aligned with the README (**UniFi Network → Integrations → Create New API Key**).

### Three-Strike Poll Resilience

- **Purpose**: Keeps entities on their last good values through short controller outages instead of flapping to `unavailable` on a single failed poll.
- **Entities & Interfaces**: `UnifiNetworkDataUpdateCoordinator._async_update_data`; `consecutive_failures` in diagnostics.
- **Technical Guarantees**:
  - Data is held through `FETCH_STRIKE_LIMIT = 3` consecutive failures (`const.py:255`).
  - Optional endpoints are fetched through `_fetch_optional`, which normalizes success and failure to a list, so one endpoint failing degrades only its own capability.
- **Lifecycle Timeline**:
  - `v1.0.0 verified`: Three-strike hold and per-endpoint degradation.
  - `v1.1.0`: Three hard-coded `<= 3` comparisons replaced with `FETCH_STRIKE_LIMIT` (`1.0.1-dev3`).

### Polling Interval, Pause Polling and Refresh Now

- **Purpose**: Controls update frequency, suspends scheduled polling without taking entities offline, and fetches on demand.
- **Entities & Interfaces**:
  - `number.unifi_network_system_polling_interval`
  - `switch.unifi_network_system_pause_polling`
  - `button.unifi_network_system_refresh_now`
- **Technical Guarantees**:
  - Explicit user actions (Refresh Now, speedtest, weight and interval changes) fetch even while Pause Polling is on.
  - Refresh Now uses a non-debounced refresh (`async_force_refresh_now`) and raises `HomeAssistantError` (`refresh_failed`) when the controller cannot be reached, so an automation can detect the failure.
  - Interval changes are debounced and a pending value is flushed, not discarded, when the entity is removed.
- **Lifecycle Timeline**:
  - `v1.0.0 verified`: Interval number, pause switch and Refresh Now button.
  - `v1.1.0`: Refresh Now reports failure (`1.0.1-dev22`); pending debounced writes flushed on removal (`1.0.1-dev12`).

### Reauthentication and Reconfiguration

- **Purpose**: Recovers from rejected credentials and allows host or credential changes without removing the integration.
- **Entities & Interfaces**: Config flow steps `reauth_confirm` and `reconfigure`.
- **Technical Guarantees**:
  - Reauth resolves its entry through `self._get_reauth_entry()`, which raises `UnknownEntry` when the entry no longer exists.
  - Stored credentials are never pre-filled as `default` or `suggested_value` in any config-flow schema; enforced by `test_stored_secrets_are_never_pre_filled` and `test_no_field_leaks_a_stored_secret`.
  - The reauth form describes what a blank credential field does.
- **Lifecycle Timeline**:
  - `v1.0.0 verified`: Reauth and reconfigure flows.
  - `v1.1.0`: Entry resolution via `_get_reauth_entry()` (`1.0.1-dev10`); secret pre-fill guards (`1.0.1-dev13`); reauth field descriptions (`1.0.1-dev12`).

---

## 2. Sensor Metrics & Data

### Internet Data Usage per WAN

- **Purpose**: Reports daily and monthly download, upload and total data usage, per WAN in dual-WAN mode.
- **Entities & Interfaces**: Internet sub-device (41 entities), for example `sensor.unifi_network_internet_wan1_month_total`.
- **Technical Guarantees**:
  - Counters carry raw bytes with `native_unit_of_measurement=BYTES`; unit conversion is left to Home Assistant.
  - Every accumulating counter uses `TOTAL_INCREASING`; `SensorStateClass.TOTAL` is banned by `test_no_sensor_uses_the_total_state_class`, because these counters reset without publishing `last_reset`.
  - A high-water mark persisted in `Store` (`{DOMAIN}.{entry_id}.usage_watermark`) keeps the UDM's bucket apportionment from publishing a lower value after a restart.
- **Lifecycle Timeline**:
  - `v1.0.0 verified`: Daily and monthly usage per WAN; persisted high-water mark.
  - `v1.1.0`: `TOTAL` state-class ban and no-upper-bound sweep on accumulating counters (`1.0.1-dev13`).

### Projected Monthly Usage

- **Purpose**: Forecasts end-of-calendar-month usage per WAN from counters already polled, with no additional API request.
- **Entities & Interfaces**: `sensor.unifi_network_internet_wan1_projected_usage`, `sensor.unifi_network_internet_wan2_projected_usage`; attributes `confidence`, `basis`, `cycle_day`, `cycle_start`.
- **Technical Guarantees**:
  - No `state_class`, so a revising forecast never reaches long-term statistics; enforced by `test_a_forecast_never_carries_a_state_class`.
  - Confidence is weighted by `elapsed / (elapsed + 3)` days (`PROJECTION_CREDIBILITY_DAYS = 3.0`) and published as `low` below 0.4, `medium` below 0.75 and `high` above.
- **Lifecycle Timeline**:
  - `v1.1.0`: Introduced (`1.0.1-dev12`).
  - `v1.1.0-dev11`: All three confidence bands driven by tests.

### Dual-WAN Status and Load-Balance Weight Control

- **Purpose**: Reports per-WAN active and link state, latency, availability, local and public IP and interface names, and sets the WAN1/WAN2 load-balance weight.
- **Entities & Interfaces**: WAN active and up binary sensors; `sensor.unifi_network_system_wan1_load_balance`, `sensor.unifi_network_system_wan2_load_balance`; `number.unifi_network_system_wan1_load_balance_weight`.
- **Technical Guarantees**:
  - The weight write is composed from a fresh `networkconf` read immediately before the PUT, never from coordinator-held state (`coordinator.py:954`).
  - The WAN1 and WAN2 PUTs run under `asyncio.shield`, so a cancelled debounce cannot leave the pair not summing to 100.
  - The write is read back and returns one of three distinct outcomes; an unverified read-back is logged as a warning, not as a failure.
  - Classified `ATTENDED` in `scripts/write_classification.py` and excluded from the hardware check.
- **Lifecycle Timeline**:
  - `v1.0.0 verified`: Dual-WAN status and weight control.
  - `v1.1.0`: Fresh-read composition, shielded pair write and read-back (`1.0.1-dev12`).

### Speedtest Results and Manual Runs

- **Purpose**: Reports per-WAN download, upload, ping and last run, and starts a speedtest on demand.
- **Entities & Interfaces**: Speedtest sub-device (12 entities); `button.unifi_network_speedtest_wan1_run`, `button.unifi_network_speedtest_wan2_run`.
- **Technical Guarantees**:
  - The button sends the gateway's physical port (`wan1_ifname` / `wan2_ifname`, falling back to `eth8` / `eth9`) to `cmd/devmgr`, which refuses the logical WAN name with HTTP 400.
  - A failed trigger raises `HomeAssistantError` (`speedtest_failed`).
  - Classified `SAFE` and exercised against real hardware by `scripts/hardware_check.py`.
- **Lifecycle Timeline**:
  - `v1.0.0 verified`: Speedtest sensors and run buttons.
  - `v1.1.0-dev11`: Hardware check resolves the same port name and passes against a UDM Pro.

### Gateway, Status and System Data

- **Purpose**: Reports gateway CPU, memory, temperatures, storage, uptime, firmware and backup state, subsystem health, configuration counts (VLANs, VPNs, firewall rules, WiFi networks) and client counts.
- **Entities & Interfaces**: Gateway (34), Status (22) and System (15) sub-devices.
- **Technical Guarantees**:
  - Numeric values are rounded to 3 decimal places at parse time by `_safe_float` / `_safe_int`, separately from `suggested_display_precision`.
  - Every numeric sensor declares a lower guard band or is listed on a named allow-list; percentage sensors also declare an upper band (`test_standards_guards.py`).
  - Guard bands are documented per sensor in `docs/value_min_max.md`.
- **Lifecycle Timeline**:
  - `v1.0.0 verified`: Gateway, status and system sensors.
  - `v1.1.0`: Guard-band sweeps (`1.0.1-dev13`); all 34 previously undocumented guard bands documented (`1.0.1-dev16`).

---

## 3. Security, Alerts & Actions

### Rogue Access Point Detection and Proximity Alert

- **Purpose**: Reports neighboring and rogue access points, filters them by band and ignore lists, and alerts when one is closer than a signal threshold.
- **Entities & Interfaces**: Security sub-device (13 entities); `number.unifi_network_security_rogue_proximity_threshold`; `select.unifi_network_security_rogue_detection_period`; switches `show_2_4_ghz_rogues`, `show_5_ghz_rogues`, `apply_ssid_ignore_list`, `apply_ap_ignore_list`; event `unifi_network_monitor_new_rogue_ap`.
- **Technical Guarantees**:
  - The `rogue_aps` attribute is capped at `ROGUE_ATTR_MAX = 25` strongest entries with a `rogue_aps_truncated` flag, and both are unrecorded.
  - First-seen history persists in `Store` and expires after `DEFAULT_ROGUE_HISTORY_TTL_DAYS = 90`.
  - The 24-hour new-rogue window uses a strict `first > cutoff` comparison, tested at the 24-hour boundary.
- **Lifecycle Timeline**:
  - `v1.0.0 verified`: Rogue detection, proximity alert, filters and history.
  - `v1.1.0`: Proximity attributes `strongest_rogue_rssi` and `threshold` removed from the recorder (`1.0.1-dev4`); cap, flag and ordering tested (`1.0.1-dev20`).

### UniFi System-Log Alerts

- **Purpose**: Surfaces UniFi system-log alerts of High and Very High severity as sensors and bus events.
- **Entities & Interfaces**: Alerts sub-device (4 entities); event `unifi_network_monitor_new_alert`.
- **Technical Guarantees**:
  - Default severities are `HIGH` and `VERY_HIGH` (`DEFAULT_ALERT_SEVERITIES`).
  - Alert titles are bounded and substituted from the alert parameters; covered by boundary tests.
- **Lifecycle Timeline**:
  - `v1.0.0 verified`: Alerts sensors and event.
  - `v1.1.0`: Title truncation and substitution boundary tests (`1.0.1-dev20`).

### Response Actions and Ignore-List Management

- **Purpose**: Exposes on-demand queries and ignore-list maintenance for automations.
- **Entities & Interfaces**: Actions `get_alerts`, `get_rogue_aps` (both returning response data), `clear_rogue_history`, `add_rogue_ignore`, `remove_rogue_ignore`, `set_rogue_ignore`.
- **Technical Guarantees**:
  - Every invalid call path raises `ServiceValidationError` with a translated message, including an unknown `device_id`.
  - Action icons and translations are reconciled against source by `test_translations_icons.py`.
- **Lifecycle Timeline**:
  - `v1.0.0 verified`: All six actions.

---

## 4. Device Management & Home Assistant Compatibility

### Sub-Device Architecture and Per-Device Sensors

- **Purpose**: Groups the integration's entities into seven sub-devices under a gateway device and, on request, adds one sub-device per adopted access point and switch.
- **Entities & Interfaces**: Sub-devices Alerts, Gateway, Internet, Security, Speedtest, Status and System (141 static entities); option `unifi_device_mode` with `none`, `satisfaction_only` and `all`.
- **Technical Guarantees**:
  - Per-device entities are opt-in (`DEFAULT_UNIFI_DEVICE_MODE = "none"`).
  - Defaults depend on whether the core `unifi` integration is installed (`"unifi" in hass.config_entries.async_domains()`); with core present, duplicated gateway diagnostics and per-device entities are created disabled.
  - Sensor groups (speedtest, WAN usage, security, dual WAN, logs and alerts) can each be disabled in options.
- **Lifecycle Timeline**:
  - `v1.0.0 verified`: Sub-device model, device modes and coexistence defaults.

### Device-Registry Compatibility Shims

- **Purpose**: Runs one behavior across Home Assistant versions before and after the 2026.8 single-config-entry device registry.
- **Entities & Interfaces**: `_compat.py`: `device_by_identifier()`, `owning_entry_ids()`, `via_device_link()`.
- **Technical Guarantees**:
  - Each surface is feature-detected on Home Assistant classes, not instances, so a mock registry cannot mislead detection.
  - Covers the `async_get_device(identifiers=…)`, `DeviceEntry.config_entries` and `via_device` tuple deprecations, removed in 2027.8 and 2027.10.
  - `owning_entry_ids()` accepts both `DeviceEntry` and the 2026.9 `ChildDeviceEntry`.
- **Lifecycle Timeline**:
  - `v1.0.0 verified`: All three shims; this project is the family's reference implementation.
  - `v1.1.0-dev11`: `ChildDeviceEntry` accepted; tests moved off `DeviceRegistry.devices` mapping access, which raises from 2026.10.

### Explicit Entity Cleanup

- **Purpose**: Removes entities and devices that the current options no longer create.
- **Entities & Interfaces**: Action `cleanup_unused_entities`; `button.unifi_network_system_clean_up_unused_entities`.
- **Technical Guarantees**:
  - Runs only when requested; setup and option changes never delete registry entries.
- **Lifecycle Timeline**:
  - `v1.0.0 verified`: Cleanup action and button.

---

## 5. Diagnostics, Health & Repairs

### Integration Health Self-Diagnosis

- **Purpose**: Reports silent failures, where a fetch succeeds but the data is unusable, as well as unavailable data sources.
- **Entities & Interfaces**: `binary_sensor.unifi_network_system_integration_health` with attributes `issues`, `severity`, `degraded_capabilities`, `drift`, `auth_mode`, `v3_available`, `last_good_update`.
- **Technical Guarantees**:
  - Schema drift (a non-empty response parsing to nothing) is flagged only after `HEALTH_DRIFT_STRIKE_LIMIT = 3` cycles.
  - Capabilities the user disabled, and v3 endpoints under username and password auth, are excluded from the verdict.
- **Lifecycle Timeline**:
  - `v1.0.0 verified`: Integration Health sensor.
  - `v1.1.0`: README example corrected to `last_good_update` (`1.0.1-dev3`).

### Repair Issues

- **Purpose**: Raises Home Assistant repairs for conditions the user must act on.
- **Entities & Interfaces**: Repairs `site_resolution_failed`, `schema_drift_detected`.
- **Technical Guarantees**:
  - Issue ids are scoped to the config entry through `repair_issue_id(entry_id, name)`, so two gateways cannot overwrite each other's issue.
  - Every name in `REPAIR_ISSUE_NAMES` is cleared on unload and on removal.
- **Lifecycle Timeline**:
  - `v1.0.0 verified`: Both repairs.
  - `v1.1.0`: Entry-scoped ids; cleared on unload and removal (`1.0.1-dev12`).

### Diagnostics Download Sanitization

- **Purpose**: Produces a config-entry diagnostics download that can be shared publicly.
- **Entities & Interfaces**: Home Assistant **Download diagnostics**; `diagnostics.py`.
- **Technical Guarantees**:
  - `TO_REDACT` masks credentials, host, MACs, local and public IPs, ISP name and organization, and BSSIDs.
  - `_Scrubber` assigns stable pseudonymous tokens, so the same device keeps the same token across the download, and scrubs identifiers from alert free text and parameters.
  - Verified against a populated live capture, not only by source reading.
- **Lifecycle Timeline**:
  - `v1.0.0 verified`: Redaction in place.
  - `v1.1.0`: Token scrubbing mutation-tested (`1.0.1-dev19`); verified against a live capture (`1.0.1-dev22`).

### Recorder Hygiene and About Notes

- **Purpose**: Keeps bulky and explanatory attributes out of the recorder database.
- **Entities & Interfaces**: Unrecorded `about` attribute on 46 entities via `UnifiAboutEntity`.
- **Technical Guarantees**:
  - A runtime sweep (`test_no_entity_publishes_a_recorded_attribute`) sets up the integration and fails if any live entity publishes an attribute that is not unrecorded.
- **Lifecycle Timeline**:
  - `v1.0.0 verified`: `about` notes.
  - `v1.1.0`: Five attributes removed from the recorder and the runtime sweep added (`1.0.1-dev4`); `about` coverage raised from 23 to 46 entities (`1.0.1-dev17`).

---

## 6. Platform, Tooling & Infrastructure

### Unit and Regression Test Suite

- **Purpose**: Verifies behavior and standards across all 17 component modules.
- **Interfaces**: `tests/` (40 files); `Pytest: Check Test Coverage` task with `--cov-branch`.
- **Lifecycle Timeline**:
  - `v1.1.0`: 100% branch coverage with 0 partial branches (`1.0.1-dev18`); `fail_under = 100` enforced from `1.1.0-dev10`.
  - `v1.1.0-dev11`: 846 tests, 100% line and branch coverage.

### Standards Guard Sweeps

- **Purpose**: Fails the suite when a change breaks a family standard.
- **Interfaces**: `test_standards_guards.py` (guard bands, `TOTAL` ban, forecast state class); `test_translations_icons.py` (translation, icon and exception keys reconciled against source in both directions); `test_entity_hygiene.py`; `test_write_classification.py`; rationale in `docs/test_guards.md`.
- **Lifecycle Timeline**:
  - `v1.1.0`: Introduced across `1.0.1-dev4`, `1.0.1-dev13` and `1.0.1-dev16`.

### Mutation Testing

- **Purpose**: Measures whether tests detect changed behavior in the modules whose tests exercise real code.
- **Interfaces**: `mutmut`; `.validate/mutmut_modules.txt`; `setup.cfg` `also_copy`.
- **Lifecycle Timeline**:
  - `v1.1.0`: Introduced (`1.0.1-dev8`); `diagnostics.py` survivors reduced from 87 to 8, all triaged (`1.0.1-dev19`).

### Write Register and Hardware Check

- **Purpose**: Classifies every controller write and exercises each `SAFE` write against real hardware.
- **Interfaces**: `scripts/write_classification.py`; `scripts/hardware_check.py`; `Hardware: Check Device` task.
- **Lifecycle Timeline**:
  - `v1.1.0`: Register and hardware check introduced (`1.0.1-dev16`).
  - `v1.1.0-dev11`: Hardware check reads `/config/.storage`, resolves the WAN port name and prints a verdict banner; `PASSED (1/1)` against a UDM Pro.

### Complexity Scorecard and Compatibility Ledger

- **Purpose**: Tracks structural complexity and Home Assistant version support.
- **Interfaces**: `docs/project_complexity.md`; `docs/ha_compatibility.md`; `Complexity: Check McCabe` task (`max-complexity = 25`).
- **Lifecycle Timeline**:
  - `v1.1.0-dev6`: McCabe rule adopted; `_async_update_data` (83) and `async_get_config_entry_diagnostics` (31) under temporary `# noqa: C901`.
  - `v1.1.0-dev7`: Scorecard added; PlayFaster Health Index 33/100 at `1.1.0-dev11`.
  - `v1.1.0-dev8`: Minimum Home Assistant 2025.2.0 (Python 3.13); tested against 2026.10.1 at `1.1.0-dev11`.

### Sensor Manifest Synchronization

- **Purpose**: Keeps the entity inventory documentation in step with the code.
- **Interfaces**: `.workbench/check_sensor_manifest.py --sync-docs` and `--verify-ha`; `docs/all_sensors.md`, `docs/about_attribute_list.md`, `docs/value_min_max.md`.
- **Lifecycle Timeline**:
  - `v1.1.0-dev10`: Documents regenerated from the manifest; 141 static entities in sync.

---

*Capabilities dossier audited against codebase and changelogs up to `v1.1.0-dev11` on 2026-10-11. Maintained via `capabilities_build.md`.*
