# Development & Architecture Notes: UniFi Network Monitor

## 1. Project Objective

To develop a high-performance Home Assistant custom component for monitoring a UniFi Network installation (UDM Pro / UDM-SE gateway, access points, and switches). The integration uses the UniFi Network application's local REST API to expose gateway health, WAN/internet metrics, per-device diagnostics, and network-wide client counts into the Home Assistant ecosystem. It is designed to work alongside the official UniFi integration, which focuses on device tracking, not infrastructure monitoring.

## 2. Architecture & File Structure

The integration follows the standard Home Assistant Custom Component pattern, optimized for asynchronous performance.

### Core Files (`custom_components/unifi_network_monitor/`)

- **`api.py`**: Async wrapper for the UniFi Network local API using `aiohttp`. Supports both API-key authentication (preferred, UniFi OS 3.x+) and username/password cookie-based sessions.
- **`coordinator.py`**: specialized `DataUpdateCoordinator`. Polls the mandatory endpoints plus a set of optional ones per cycle, parses raw responses into flat dicts for each sub-device. Two resilience layers: a **global** 3-strike over the whole update (mandatory `get_devices`/`get_health`), and **per-endpoint** hold-then-`unavailable` for the optional fetches (`_fetch_optional`). `disabled_endpoints(options)` + `_optional()` skip the fetches for disabled feature groups. Endpoint identity constants (`EP_*`) live in `const.py`.
- **`helpers.py`**: Shared `build_gateway_device_info`, `build_network_device_info`, and `build_unifi_device_info` functions. All platform files delegate `device_info` to these helpers to prevent 5-way copy-paste drift.
- **`__init__.py`**: Manages integration lifecycle (setup/unload). Stores the coordinator in `entry.runtime_data`. Registers the `cleanup_unused_entities` service, the `async_remove_config_entry_device` (device-delete) hook, and an update listener that reloads the entry on non-live option changes (`_async_reload_on_settings_change`).
- **`sensor.py`**: Declarative `value_fn` sensor engine for gateway, network health, per-AP, and per-switch sensors (including the **Alerts** sub-device's four per-severity sensors and the **Security** sub-device's rogue/threat/VPN/firewall sensors + **Rogue APs All 24h** and **Rogue APs New 24h** — the latter counting BSSIDs first-seen-by-HA within 24 h from the persistent history). Guard bands enforced at `native_value` time. Per-device creation gated by `unifi_device_mode` (`_device_descs`); gateway groups gated by `disabled_endpoints`; an `available` override + `_ENDPOINT_BY_KEY` map ties each sensor to its source endpoint; duplicate-of-core keys get a `_mon` entity_id.
- **`binary_sensor.py`**: Gateway connectivity/update/speedtest-pass sensors, network health OK sensors, dynamic WiFi/VPN status sensors, the Security **Ad Blocking**/**Honeypot** sensors, the **Rogue AP Proximity Alert** (`PROBLEM`), and the **Integration Health** self-diagnosis sensor (`PROBLEM`, System sub-device, always created, deliberately not endpoint-tagged so it stays available to report staleness). Same `available`/endpoint-tag pattern as `sensor.py` (`_BINARY_ENDPOINT_BY_KEY`) for the rest.
- **`button.py`**: "Refresh Now" button, WAN1/WAN2 speedtest run buttons (gated on `enable_speedtest`), and the **Clean Up Unused Entities** button (`EntityCategory.CONFIG`, enabled by default, commit-only).
- **`number.py`**: UI-controlled polling interval and WAN load-balance weight, plus the **Rogue Proximity Threshold** number (dBm, gated on security). All persist to `ConfigEntry` options.
- **`select.py`**: the **Rogue Detection Period** select (Security sub-device) — the live look-back window for the rogue poll; applies via force-refresh.
- **`switch.py`**: Pause Polling switch (`stop_polling`) plus the four Security rogue-control switches (**Show 2.4/5 GHz Rogues**, **Apply AP/SSID Ignore List**) backed by config-entry options and applied live via force-refresh.
- **`alerts.py`**: pure helpers shared by coordinator + sensor/service — `format_message` (parameter substitution), `alert_title` (capped), `build_alert_attrs`, `build_alert_response`, `build_event_payload`. Kept separate to avoid a circular import.
- **`services.py`**: registers the on-demand response actions — `get_alerts` (system-log query) and `get_rogue_aps` (fresh rogue-AP query), both `SupportsResponse.ONLY`, domain-global, target-resolving, decoupled from the feature toggles, with `keyword`/`exclude` comma-list filters + `total_matched` (and `count_total` on alerts) — plus the **list-management** actions `clear_rogue_history` and `add`/`remove`/`set_rogue_ignore` (`target: ssids|aps`; mutate `entry.options` so the reload listener re-applies them; `set` returns `old`/`new`). Shared filter helpers `_included`/`_excluded`/`_split_terms`; entry resolver `_resolve_entry`.
- **`config_flow.py`**: Initial setup, reconfigure, reauth, and options flows. Credentials never pre-filled in edit flows. Five feature toggles (Alerts, Dual-WAN, Security, Speedtest, WAN Usage) grouped in a collapsible `sensor_groups` **section**; `_flatten_sections()` un-nests them. Reconfigure updates + aborts (the update listener owns the reload).
- **`cleanup.py`**: `CleanupPlan`, `plan_device_cleanup`, `apply_cleanup` — explicit removal of per-device and feature-group orphans + device detach. Driven by the button and service; never automatic.
- **`services.yaml`**: `cleanup_unused_entities` (`dry_run`), `get_alerts` (severity/quantity/age_days/keyword/exclude/count_total/device), `get_rogue_aps` (period/band/min_signal/quantity/keyword/exclude/device), `clear_rogue_history` (device), `add`/`remove`/`set_rogue_ignore` (target/value|values/device).
- **`helpers.py`** _(also)_: `UnifiAboutEntity` mixin — an unrecorded `about:` annotation attribute for ~20 entities.
- **`const.py`**: All domain constants, default values, gateway model strings, option keys, `EP_*` endpoint labels, the two event names (`EVENT_NEW_ALERT`, `EVENT_NEW_ROGUE_AP`), and the action-tuning constants.
- **`diagnostics.py`**: Redacts sensitive fields (API key, password, username, host, gateway MAC, WAN local/public IPs, rogue-AP BSSIDs, ISP name/org) from diagnostics output via `async_redact_data` (recurses by key name). Also dumps `integration_health` and the `rogue_history` — the latter emitted as a **list of `{bssid, …}` records** so the `bssid` key is redacted (`async_redact_data` masks values, not dict keys).

## 3. Architecture Decisions

### Dual API Endpoint Model

The UniFi API returns overlapping data from two distinct endpoints:

- **`/stat/device`** — device-level data: hardware stats (CPU, RAM, temperature, storage), uplink connectivity, firmware status.
- **`/stat/health`** — network-level data: WAN/WAN2 availability and latency averages, WWW latency/drops/speedtest results, WLAN/LAN client counts.

Both endpoints return some version of speedtest and WAN metrics. The architectural decision is: **health endpoint (`/stat/health`) is the authoritative source for network-level metrics**. The gateway device exposes only device-specific sensors. Duplication was removed as part of the initial design phase.

### Hybrid API Model (Official API v3 + Classic API)

While UniFi OS v3.0.0 and its Official API (using API Keys) introduces a highly structured endpoint hierarchy (e.g., `get_wan_interfaces`, `get_vpn_tunnels`), the integration uses a **hybrid API model** to fetch the best of both worlds:

- **Telemetries**: The integration continues to use the richer classic `/proxy/network/api/s/{site}/stat/device` endpoint for deep hardware metrics (CPU/RAM, gateway temperatures, storage partition sizes, port tables, etc.) since the official v3 `devices` payload is extremely sparse.
- **Structured Configurations**: The integration queries the official v3 / integration endpoints (via `asyncio.gather()` for zero overhead) to retrieve:
  - Custom user-configured WAN names (e.g. `WAN1_ISP1` and `WAN1_ISP2`) to map interfaces.
  - Active/configured firewall rules.
  - VLAN/VPN tunnels configuration lists.
- **Graceful Degradation**: If the user's controller version does not support these v3 endpoints (or returns 404/403/TypeError), the coordinator catches the error, fallbacks to returning empty configurations, and the corresponding telemetry sensors gracefully become `unavailable` instead of crashing the update cycle.

### Removal of Misleading Gateway-Level "Ports" Client Counts

Previously, the integration exposed `Ports in Use`, `User Ports`, and `Guest Ports` under the Gateway's **Ports** sub-device. Investigation revealed a naming/source discrepancy:

- These sensors retrieved the Gateway device's local station caches (`num_sta`, `user-num_sta`, `guest-num_sta` from `/stat/device`).
- They did not represent physical port telemetry or link states.
- Because the gateway's station cache behaves as a lagging subset of the global site state (leading to slight mismatches like 157 gateway clients vs. 161 site-wide clients), having duplicate, slightly different versions of client counts was confusing and contradictory.
- These misleading/redundant sensors were removed. Site-wide client counts under the **System** sub-device (derived from `/stat/health` WAN/LAN/WLAN health objects) remain the authoritative source for active devices.

### Calculated Subsystem Health (Network Problem)

The **Network Problem** binary sensor (`health_all_ok` under the **Health** sub-device) is a calculated entity. Instead of reflecting a single API field, it aggregates the status values of the four core subsystems from the `/stat/health` endpoint (`wan`, `www`, `wlan`, and `lan`). It transitions to `Problem (On)` if any of the underlying subsystems do not report a status of `"ok"`.

### Sub-Device Architecture

Entities are grouped into **7** logical sub-devices (for the main system) and dynamic per-device sub-devices. Each sub-device's card is set by the entity's `device_key`, not by which fetch produced the data. See `docs/all_sensors.md` for the full per-entity manifest (128 base entities).

| Sub-device | Source | Contains |
| --- | --- | --- |
| **UniFi Network Gateway** | `/stat/device` / `/stat/health` | Gateway hardware (CPU, RAM, temp, storage, uptime), backup status, SFP transceiver diagnostics, and application/firmware versions. |
| **UniFi Network Internet** | `/stat/device` / `/stat/health` / Speedtest V2 API | Active WAN routing interface, ISP monthly/daily data usage, network uptime/drops/latency, WAN availability, and internal/external IPs. |
| **UniFi Network Speedtest** | Speedtest V2 API / `/stat/health` | Per-WAN speedtest results (download, upload, ping, last run, monitoring period) and the run buttons. |
| **UniFi Network Security** | `/stat/rogueap` / `/rest/setting` / Integration endpoints | Rogue-AP detection (count, strongest SSID/RSSI, **Rogue APs All 24h**, **Rogue APs New 24h**, proximity alert), the rogue controls (period select, band-show / apply-ignore switches, proximity threshold), threat management (IPS mode, Ad-blocking, Honeypot), VPN connection counts, and firewall-rule counts. Gated by `enable_security_monitoring`. |
| **UniFi Network Alerts** | `system-log/all` (v2) | Per-severity system-log sensors — **Last High Sev3**, **Last Very High Sev4** (title state), and **High/Very High Sev4 Qty Last 24h** (counts). Gated by `enable_logs_alerts`. |
| **UniFi Network System** | `/stat/device` / `/stat/health` / Config options / self-diagnosis | Polling configuration (Pause Polling, interval), multi-WAN load-balance mode/weights, Last Updated, the Refresh Now / Clean Up buttons, and the **Integration Health** self-diagnosis binary sensor. |
| **UniFi Network Status** | `/stat/health` / Integration endpoints | Live client counts (WLAN/LAN user/guest/iot), adopted device count, active/total config counts (VLANs, WiFi networks), individual WiFi & VPN tunnel binary statuses, and subsystem health indicators (All OK, WAN OK, WiFi OK, LAN OK). |
| **Per AP / Per Switch** | `/stat/device` | Per-device CPU, RAM, uptime, client counts (AP), port counts (switch), firmware update status. |

> **Note:** Rogue/threat/VPN/firewall entities moved to the new **Security** sub-device (out of Status/System), and the **Alerts** sub-device was added, in the 2026-07 alerts + rogue-action work. `helpers.build_sub_device_info` maps `device_key` → card name for all seven.

### Flat Identity Pattern

Gateway MAC, model, and firmware version are stored in `entry.data` at setup time and loaded into the coordinator at `__init__`. This provides stable metadata to the UI instantly at boot, even if the hardware is offline.

### Credential Security

Credential fields (API key, password) use `TextSelectorType.PASSWORD` in all flows. Edit flows (`reconfigure`, `options`, `reauth`) intentionally leave these fields blank — the stored value cannot be retrieved via the eye icon. If the user submits a blank field, the existing credential is retained via `_merge_credentials()`.

### Diagnostics Sanitization (§20 of shared dev_standards)

`diagnostics.py` runs a two-pass sanitizer **before** `async_redact_data`. Pass 1 walks the payload and learns identifiers — device MACs, device names, the ISP name, WAN interface names, rogue SSIDs — allocating a stable token for each (`device-1`, `gateway`, `rogue-2`). Pass 2 rewrites: MAC-keyed dictionaries (`entry.data["boot_times"]`, `data["devices"]`) get their **keys** replaced, device records get `mac`/`name` tokenised, the UniFi alert `parameters` subtree is sanitized by block name (`DEVICE` → token, `ISP_NAME`/`WAN_SUBNET`/`WAN_NAME`/`CONSOLE_NAME` → blanked), and free-text `message`/`title` have every learned literal substituted out. A shape-based backstop (MAC regex, RFC1918 + CGNAT regex) covers alert blocks UniFi may add later.

Tokens are stable across sections, so an alert about `device-4` still resolves against `device-4` in the device list — the file stays diagnostically useful. `TO_REDACT` is retained unchanged and still runs last.

Design constraints: matching is **structural only** (shape and position), so no real identifier is ever hard-coded; the coordinator payload is `deepcopy`'d because diagnostics is a read path; and `strongest_rogue_ssid` is resolved through the learned-literal pass rather than a sentinel check, so a real SSID becomes its token while `"None Detected"` passes through untouched.

Rogue-AP records get particular attention: they describe **other people's** networks. `essid` is tokenised, `bssid` redacted, `detected_by` (a comma-joined list of this user's own AP names) run through the text scrubber. `oui` is deliberately **kept** — vendor alone identifies nobody and is genuinely useful when diagnosing detection behaviour.

### 3-Strike Resilience

The coordinator holds last known data for up to 3 consecutive poll failures before raising `UpdateFailed`. On failure 1, a warning is logged. Failures 2–3 log at debug. Failure 4+ triggers Unavailable. A successful poll resets the counter to 0 and logs reconnection if the integration was previously unavailable.

### Dynamic Device Discovery

AP and switch entities are created on the first coordinator data snapshot and on subsequent updates when new MACs appear. The `known_macs` set prevents duplicate creation. This handles network growth (new APs, new switches) without requiring an integration reload.

### Standalone vs. Coexistence Mode (Per-Device Entity Defaults)

The native UniFi integration (`domain: unifi`) covers per-device tracking. To avoid duplication, all AP and switch sensor descriptions carry `entity_registry_enabled_default=False`. This is the right default when both integrations are running together.

However, if a user runs this integration **without** the native UniFi integration, those sub-devices would be created with every sensor disabled — cluttering the device list with empty shells.

At `async_setup_entry` time, `sensor.py` checks:

```python
standalone = "unifi" not in hass.config_entries.async_domains()
```

If the native integration is absent, `UnifiDeviceSensor` overrides `entity_registry_enabled_default` via a property returning `True` for all per-device entities. The descriptions themselves are unchanged.

**Key constraint**: `entity_registry_enabled_default` is only evaluated on **first registration**. After an entity is registered, HA stores the enabled/disabled state in the entity registry and ignores this property on subsequent loads. This means:

- Installing standalone → per-device entities enabled ✓
- Later adding the native integration + reloading → entities remain enabled (user must manually disable duplicates) ✗
- Installing with both integrations → per-device entities disabled ✓
- Later removing the native integration + reloading → entities remain disabled (user must manually enable) ✗

This is an accepted limitation. The check correctly handles the initial setup for the two primary target configurations: standalone users (full visibility) and coexistence users (no duplication).

**Known simplification**: in standalone mode, the override enables _all_ per-device entities — including secondary/diagnostic ones (e.g. Model, User Ports, Guest Ports) that were disabled for reasons unrelated to native integration duplication. A future refinement could add a second description flag (e.g. `disabled_without_native: bool = False`) to distinguish "disabled to avoid duplication" from "disabled because it's secondary data regardless". For now, enabling everything in standalone is the accepted behavior.

> **Superseded (2026-07):** whether per-device entities are created at all is now governed by the `unifi_device_mode` option (below). The `standalone` flag now only affects `entity_registry_enabled_default` for whatever is created.

### Gateway Coexistence: Card Merge + `enable_in_standalone`

Two Core-present behaviors affect the **base** (gateway) entities, both verified live (2026-07-08):

- **Gateway card merges.** `build_gateway_device_info` uses `connections={(CONNECTION_NETWORK_MAC, gateway_mac)}`, so when Core UniFi is installed HA merges the Monitor **Gateway** sub-device into Core's gateway device card. The merged card shows **Core's** device name (e.g. `UDM-Pro`) and firmware string (UniFi-OS version, e.g. `5.1.19.33549`, vs the Network-application version standalone shows). The other four sub-devices use `identifiers` only, so they stay separate and hang off the gateway via `via_device`. AP/switch cards likewise merge by MAC.
- **`enable_in_standalone` gateway sensors.** Six gateway diagnostics carry `enable_in_standalone=True` (`cpu`, `ram`, `cpu_temp`, `board_temp`, `uptime` in `sensor.py`; `update_available` in `binary_sensor.py`). The gateway entity classes force these enabled **only** when standalone; with Core present they revert to `entity_registry_enabled_default=False` (disabled). Intended: when Core is present it already surfaces the gateway's CPU, memory, and temperature sensors, so all six are disabled by default to avoid cluttering the merged card (user can enable from either integration). Net base enabled-by-default: **93 without Core / 87 with Core** (116 registered either way).

### Per-Device Enabled Counts by Mode (verified live)

Reference rig = 8 APs + 12 switches. `unifi_device_mode` controls _creation_; Core presence controls _enabled defaults_:

| Mode                | Devices | Registered | Enabled (no Core) | Enabled (Core) |
| ------------------- | :-----: | :--------: | :---------------: | :------------: |
| `none` (default)    |    5    |    116     |        93         |       87       |
| `satisfaction_only` |   13    |    140     |       n/a¹        |       95       |
| `all`               |   25    |    276     |        253        |       95       |

¹ `satisfaction_only` is only offered when Core is present. Under Core, only the AP **Satisfaction Score** is enabled per device (1/AP, 0/switch), so `all` enables the same 95 as `satisfaction_only` — the extra 136 are disabled clutter. **Counting caveat:** Core names its own controller device "UniFi Network", so its firewall/traffic switches are `switch.unifi_network_*`; filter by `platform: unifi_network_monitor` when counting.

### Setup Options & Sensor-Group Scoping (2026-07 rework)

Full design in `.notes/design_monitor_setup_options.md`; cross-project porting guide in `shared/SharedNotes/issues/setup_cleanup_options.md`.

Two axes of user control, stored in `entry.options`, all defaulting to preserve prior behavior:

- **`unifi_device_mode`** (`none` / `satisfaction_only` / `all`, default `none`) — which per-AP/switch sensors to create. `sensor.py`'s `_device_descs(dev_type, mode)` drives both the static loop and the dynamic-discovery listener. Core-detected setup offers all three; core-absent offers `none`/`all` (lean default either way).
- **Feature toggles** (`enable_speedtest`, `enable_wan_usage`, `enable_security_monitoring`, `enable_logs_alerts`, `enable_dual_wan`, default `True`) — each maps a group of gateway sensors **and** its endpoint(s). Disabling a group both stops creating its sensors and skips the API calls (`disabled_endpoints(options)` + `_optional()` substitute a no-op fetch, preserving the positional `gather` unpack). `enable_logs_alerts` gates the Alerts sub-device + `system-log/all`; `enable_dual_wan` is a creation/cleanup **key-set** filter that removes the WAN2 + load-balance entities on a single-WAN setup (WAN2 rides the _shared_ endpoints, so it is never routed through `disabled_endpoints`). Config-flow order is alphabetical: **Alerts, Dual-WAN, Security, Speedtest, WAN Usage**.

**Config flow:** setup, reconfigure and options share schema builders. The feature toggles live in a collapsible HA **section** (`from homeassistant.data_entry_flow import section`, key `sensor_groups`); sectioned input arrives nested, so `_flatten_sections()` un-nests it before validation. Reauth keeps the credentials-only `_edit_schema`.

**Reload on submit:** a single update listener (`_async_reload_on_settings_change`) reloads the entry when a **non-live** option changes, so both reconfigure and options apply immediately. It's gated by a _reload signature_ — `entry.options` minus the live-tunable keys (`scan_interval`, `rogue_proximity_rssi_threshold`, `stop_polling`) — so their control entities don't trigger a reload. Reconfigure uses `async_update_entry` + `async_abort` (not `async_update_reload_and_abort`) so the listener owns the single reload for both paths.

### Per-Endpoint Resilience

Two layers now coexist. The **global** 3-strike (above) covers the mandatory `get_devices`/`get_health` and the whole update. The **per-endpoint** layer applies to the optional fetches via `_fetch_optional`: each endpoint holds its last-good payload for `FETCH_STRIKE_LIMIT` (3) consecutive failures, then is flagged stale in `self._stale_endpoints`. Entities tag their source endpoint (`_ENDPOINT_BY_KEY` / `_BINARY_ENDPOINT_BY_KEY`; dynamic sensors override `_source_endpoint`) and return `unavailable` via an `available` override when `coordinator.endpoint_available(source)` is False — so one dead endpoint doesn't take down the rest, and a blip no longer zeroes a sensor. `_fetch_optional` distinguishes _failure_ from _empty_ (the prior version returned `[]` for both) and uses a broadened `except` so a changed API shape degrades one endpoint instead of the whole update.

### Rogue AP Proximity Detection

From the `stat/rogueap` data the coordinator derives `strongest_rogue_ssid` and `strongest_rogue_rssi` (highest, i.e. least-negative, signal). Exposed as **Strongest Rogue SSID** (text; sentinel `"None Detected"` when none) and **Strongest Rogue RSSI** (dBm; `None` → `unknown` when none — _not_ `unavailable`, since the endpoint is healthy). The rogue-AP list attribute lives on Strongest Rogue SSID (not the count sensor). A **Rogue AP Proximity Alert** `PROBLEM` binary sensor fires when the strongest RSSI ≥ a user threshold, set by the **Rogue Proximity Threshold** number (negative dBm, kept negative per how RSSI is measured; gated on the security group).

### Rogue Controls, Filtering & the Shared Parser

The rogue view is user-tunable via Security-sub-device controls (all live-applied via force-refresh, no reload): a **Rogue Detection Period** select (`select.py`, look-back window for the poll), **Show 2.4/5 GHz Rogues** switches (band filter), and **Apply AP/SSID Ignore List** switches (with ignore-list text set at setup). The band-filter + SSID/AP-ignore + BSSID-clustering logic lives in one shared function, `coordinator.parse_rogue_aps(...)` (with `build_ap_name_map`), used by **both** the curated sensor view (Security options applied) **and** the `get_rogue_aps` action (self-contained — ignore-lists deliberately not applied so the action can surface a hidden AP). Each clustered item carries `last_seen` (epoch) + derived `age`, and the extended fields `security`, `channel_width` (from raw `bw`), `wired_rogue` (raw `is_rogue` — `any()` across cluster rows), `is_adhoc`, and `ssid_anomaly`.

**Hidden-SSID naming:** a cloaked SSID (empty/whitespace essid) is named `Hidden-<last-4-hex-of-BSSID>` (`normalize_essid` flags it; `hidden_label` builds it; a post-cluster pass extends colliding last-4 to last-6). `<Hidden>` remains only as the BSSID-missing fallback. `ssid_anomaly` is also set for control/zero-width/RTL characters (sanitized to `·`). BSSID is the stable identity; the label is cosmetic.

**Rogue APs All 24h** (`rogue_raw_24h`, Diagnostic, `MEASUREMENT`/LTS) is a separate dedicated fetch — `get_rogueaps(within_hours=24)` (`EP_ROGUE_RAW`) — that counts raw per-(BSSID × reporter) detection rows with no filtering, a background-noise gauge distinct from the filtered count. Fixed 24 h window so the trend stays comparable regardless of the live Period.

### Alerts Monitoring (Sensors + Event + Action)

Gated by `enable_logs_alerts` (Alerts sub-device). The coordinator fetches `system-log/all` (v2, POST) filtered to `HIGH`/`VERY_HIGH` (`EP_SYSLOG`) and splits the newest of each severity into **Last High Sev3** / **Last Very High Sev4** (title as state, "None Detected" when none; title capped at 255) plus **High/Very High Sev4 Qty Last 24h** counts. "Sev3/Sev4" maps to the UniFi GUI 3-/4-dot severity (not an API field). `alerts.py` holds the shared parameter-substitution/attr/response helpers.

### New-Item Bus Events (`new_alert` / `new_rogue_ap`)

Two bus events let advanced users trigger automations: `EVENT_NEW_ALERT` (per newly-seen alert `id`) and `EVENT_NEW_ROGUE_AP` (per newly-seen rogue BSSID). Both use the same machinery: a **first-poll (and re-enable) baseline** records the existing backlog silently so a restart doesn't replay history; a **bounded seen-set** reset to the current window each poll dedups (an item fires once; reappearance re-fires); firing is **gated on the feature flag** (`want_logs` / `want_security`) so a disabled group emits nothing. HA has no event-type registry, so the events simply don't exist when the group is off.

### On-demand Response Actions (`get_alerts` / `get_rogue_aps`)

`services.py` registers two `SupportsResponse.ONLY` actions (domain-global, in `async_setup`). Each resolves its target (device id → config entry, defaulting to the sole entry) and performs its **own fresh, capped fetch** rather than reading a sensor's cached state — so both work even when the passive group is off. `get_alerts`: 4-level severity (default HIGH+VERY_HIGH), quantity (default 10 / max 100), age_days, `keyword`/`exclude`, and opt-in `count_total`; hard 5-page/500-record cap on the paginated `system-log/all`. `get_rogue_aps`: period preset → `within_hours`, band, min_signal, `keyword`/`exclude`, quantity; self-contained parse (no ignore-lists).

- **`keyword` / `exclude`** are both **comma-lists** (any-term OR): `keyword` includes, `exclude` (applied after) drops. Haystack = title+message (alerts) or essid+oui+security (rogue). `keyword` used to be a single substring — it now splits on commas.
- **`total_matched`** = the true count of matches vs the `quantity`-capped `count`. **Free for `get_rogue_aps`** (the full filtered list already exists before slicing); **opt-in for `get_alerts`** via `count_total` (it otherwise stops scanning at `quantity`), which also returns `truncated: true` when the 500-record cap is hit before the log/age is exhausted.
- **History annotation:** each `get_rogue_aps` response item also carries `first_seen`/`appearances` **read** (never written) from `coordinator.rogue_history` — `null` for a BSSID HA hasn't polled.

### Persistent Rogue-AP Appearance History

BSSID-keyed `Store` (`{DOMAIN}.{entry_id}.rogue_history`), loaded in `coordinator.async_initialize()` before the first refresh. `_update_rogue_history` runs each poll on the Security path: first-seen baseline (silent, like the event), `appearances` increment, TTL prune (`rogue_history_ttl_days`, default 90; 0 = forever) + hard max-entries cap (`ROGUE_HISTORY_MAX`, bounds MAC-randomisation churn), saved via **`async_delay_save`** (coalesced — never per-poll `async_save`). It re-keys `new_rogue_ap` so the event fires only for genuinely-new BSSIDs and **survives restarts** (the old in-memory seen-set was removed). `first_seen` = first-seen-**by-HA**, not by the gateway. `clear_rogue_history` action + `async_clear_rogue_history` reset it. **Rogue APs New 24h** (`rogue_new_24h`, `MEASUREMENT`/LTS) counts BSSIDs first-seen within 24 h.

### Ignore-List Management Actions

`add_rogue_ignore` / `remove_rogue_ignore` / `set_rogue_ignore` (each with `target: ssids|aps`) mutate `entry.options[rogue_ignore_ssids|rogue_ignore_aps]` via `async_update_entry`; since those keys aren't live-tunable, the reload listener re-applies them immediately. `set` returns `{target, old, new}` (undo); `add`/`remove` return the resulting list. They affect the **passive Security view only** — the `get_rogue_aps` action deliberately ignores the ignore-lists.

### Integration Health & Self-Diagnosis (§19 of shared dev_standards)

`_compute_integration_health(opts, raw_drift)` builds a health snapshot (`problem`/`severity`/`issues`/`degraded_capabilities`/`drift`/`auth_mode`/…), surfaced by the **Integration Health** `PROBLEM` binary sensor. It catches **silent** failures HA misses:

- **Capability degradation** — `_stale_endpoints − disabled_endpoints(opts)` (so a **user-disabled** group is never flagged; v3 endpoints are excluded under password auth) → moderate, sensor-only.
- **Schema drift** — a non-empty upstream response that parsed to nothing (gateway stats all-None / rogue all-empty-bssid / alerts no-severity), gated by a **per-source strike counter** (`HEALTH_DRIFT_STRIKE_LIMIT`, 3) to avoid single-cycle trips → serious, **sensor + `schema_drift_detected` repair** (`_sync_health_issues`, auto-clears). `site_resolution_failed` is reflected in the attributes (owned by `_sync_site_issue`). - **Total outage** — the whole fetch failing, not just one endpoint. `_record_fetch_failure_health(err)` runs in all three `except` blocks of `_async_update_data` and flags **immediately at cold start** (`self.data is None` — nothing to hold, so waiting out the strikes would leave the integration silent for up to 3 poll intervals) or **at `FETCH_STRIKE_LIMIT` consecutive failures at runtime** (matching §8, so a blip raises no alarm). The success path assigns the freshly computed snapshot wholesale, clearing the verdict in the same cycle.

The whole block is wrapped so a malformed payload can't crash the update it diagnoses; the sensor is not endpoint-tagged so it stays available to _report_ staleness.

**Two design points that are easy to regress (2026-07-20):**

- **The snapshot lives on `coordinator.health_snapshot`, NOT in `coordinator.data`.** `data` is `None` before the first success and frozen at the last good values during an outage — a verdict stored there cannot describe the failure that stopped it being updated, and would keep asserting the pre-outage state, which was healthy. Both the success path and `_record_fetch_failure_health` write the attribute. A copy is still emitted into `data["integration_health"]` for diagnostics and back-compat; the sensor does not read it.
- **The sensor overrides `available` to return `True` unconditionally.** `CoordinatorEntity.available` returns `last_update_success` (verified in HA 2026.7.2), which would take the sensor unavailable at exactly the moment it has something to report. An `unavailable` `problem` sensor is not actionable: automations wait for `on`, and users read `unavailable` as a broken sensor rather than a down gateway.

### Startup: No Connectivity Probe (§1 of shared dev_standards)

`async_setup_entry` awaits `coordinator.async_initialize()` — which only loads the persisted rogue-AP history from **local storage**, no network call — registers the gateway root, forwards the platforms, then offloads the first fetch via `entry.async_create_background_task` and returns `True`. No `ConfigEntryNotReady` is raised at setup, so HA shows no native "Retrying setup" card. This is the §1 departure from IQS `test-before-setup`, and it is deliberate.

**A connectivity probe was considered and rejected.** The reasoning, so it is not relitigated:

- The API client uses `_API_TIMEOUT = ClientTimeout(total=15)`. A probe reusing it would block `async_setup_entry` for up to 15 s against an unreachable gateway — tripping the *"Integration taking more than 10s to set up"* warning §1 exists to prevent. It would need its own 2–3 s timeout.
- `ConfigEntryNotReady` triggers HA's setup-retry backoff, so the probe's cost is paid repeatedly while the gateway is down.
- It would create two failure regimes for one fault: down at boot → retry card; down later → the 3-strike hold. Same condition, different UX.
- Every healthy restart would pay the probe's latency, forever, to improve one uncommon case.

**It is also unnecessary here.** Platforms are forwarded (`__init__.py`) **before** the background task is created, and `DataUpdateCoordinator.async_refresh()` swallows `ConfigEntryNotReady` rather than propagating it — so **entities already exist at cold start**, merely unavailable. The Integration Health sensor stays available and turns `on` on the first cold-start failure, which reports the same fact with no startup cost. See the §19 notes above.

### Force-Refresh Bypasses Pause (Explicit User Actions)

Every explicit user action fetches **even while Pause Polling is on**, via a one-shot flag the coordinator honours in `_async_update_data`: `async_force_refresh()` sets `_force_refresh_once`, then clears it on the next fetch. Wired to Refresh Now, the speedtest buttons (which also `async_schedule_refresh_in(75)` for the delayed result), the load-balance/scan-interval/threshold numbers, the rogue period select, and all rogue-control switches. Scheduled polls still respect the pause. (Historically these called `async_request_refresh()`, which a pause-aware coordinator silently swallowed.)

### `about` Annotation + Recorder Hygiene

The `UnifiAboutEntity` mixin (`helpers.py`) exposes an optional unrecorded `about:` attribute (a one-line explanation surfaced in More Info, listed in `_unrecorded_attributes` so it never hits history) on ~20 entities whose purpose/similarity could confuse. The gateway sensor also unrecords the bulky/high-churn attributes `rogue_aps`, `rogue_aps_truncated`, `parameters`, and `udm_version`; the `rogue_aps` list is capped at 25 strongest (`ROGUE_ATTR_MAX`) with a `rogue_aps_truncated` flag. `_safe_float` rounds all numeric telemetry to 3 dp at parse time (stored-precision hygiene, distinct from `suggested_display_precision`).

### Duplicate-Entity `_mon` entity_id

Per-device sensors that duplicate the native integration keep their display name but receive a deterministic `_mon` entity_id via `async_generate_entity_id` — instead of HA's ambiguous `_2` collision suffix — so their origin is obvious when debugging. `_DUPLICATES_CORE_KEYS` is a **key → entity_id-stem map** (`sensor.py`): `clients`/`cpu`/`ram`/`uptime` map to themselves, and **`ports_used` maps to `clients`**. The switch "Clients" sensor uses the `ports_used` key (its value is `num_sta` = client count, the same metric as Core's switch Clients), so without this mapping it collided with Core's `…_clients` and HA appended `_2` on every switch. Mapping it to the `clients` stem yields `…_clients_mon`, matching the AP Clients sensor. Devices still merge by MAC; AP Satisfaction Score (Monitor's unique value) is not suffixed.

> **Note:** the collision only manifests with Core present _and_ a switch-creating mode (`all`) — standalone has no Core `…_clients` to clash with. Verified live across all four modes (2026-07-08).

### Cleanup Layer (explicit only)

Options are non-destructive: disabling a group leaves the old entities as `unavailable` orphans. Removal is always user-triggered:

- **Clean Up Unused Entities** button (`EntityCategory.CONFIG`, enabled by default, commit-only — a button press can't carry a dry-run).
- **`unifi_network_monitor.cleanup_unused_entities`** service (`dry_run` default `True`, `SupportsResponse.OPTIONAL` returns a report of what would be removed).

Both call `plan_device_cleanup`/`apply_cleanup` (`cleanup.py`): entities via `entity_registry.async_remove`, devices via `device_registry.async_update_device(remove_config_entry_id=...)` (removes a Monitor-only device; only drops the link on a device shared with core), then reload out-of-band. `async_remove_config_entry_device` in `__init__.py` enables the UI per-device Delete button only when Monitor has no entities left on the device (Gold-tier `stale-devices` rule).

## 4. Success Patterns

- **`DataUpdateCoordinator`**: Single fetch per poll cycle distributes data to all entities. `button.py` uses `coordinator.async_request_refresh()` for immediate feedback on manual refresh.
- **Explicit Coordinator `config_entry` (HA polling option)**: Pass `config_entry=entry` to `DataUpdateCoordinator.__init__`. HA core's `_schedule_refresh()` reads `self.config_entry.pref_disable_polling` — the flag behind the "Enable polling for changes" system option — and skips arming the next timer when it's OFF (manual `update_entity` / "Refresh Now" still fetch via `async_request_refresh`, which ignores the flag). Passing the entry explicitly is also required going forward: HA deprecated implicit `ContextVar` detection and reports it as an error from **2026.8** (the argument dates from **2024.8**; the README now states a 2024.8.0 minimum). Orthogonal to the "Pause Polling" switch (`stop_polling`), which short-circuits `_async_update_data` to cached data for _all_ triggers. Full write-up: `.shared/info/sys_options_enable_polling.md`.
- **Declarative Entities**: `value_fn` lambda in `UnifiSensorEntityDescription` makes adding a new sensor a data-entry task — no new class required.
- **Shared `build_*_device_info()` helpers**: All five platform files delegate `device_info` to helpers. Adding a new platform requires zero `device_info` boilerplate.
- **Translation-Based Naming**: All entities use `translation_key=` rather than hardcoded `name=`. `translations/en.json` is the canonical display-name source.
- **Guard Bands**: All numeric sensors carry `min_limit` and/or `max_limit` in their description. The base class enforces them at `native_value` time. See `docs/value_min_max.md` for the complete table.
- **`entry.data` vs `entry.options`**: `entry.data` holds immutable hardware identity (MAC, model, sw_version). `entry.options` holds all user-changeable settings (host, credentials, site, scan interval).

- **Suggested Units & Display Precision**: For large-byte sensors (e.g. data usage statistics), the native unit of measurement is kept as `UnitOfInformation.BYTES` to ensure raw state integrity. However, we declare `suggested_unit_of_measurement=UnitOfInformation.GIGABYTES` to automatically display these in GB in the UI. In addition, `suggested_display_precision` is defined (`2` for daily sensors, `1` for monthly sensors) to enforce a clean default decimal representation in the Home Assistant frontend while preserving raw float values in the backend database.

## 5. Technical Pitfalls & Fixes

- **`SensorDeviceClass.TIMESTAMP` requires timezone-aware datetimes**: `datetime.fromtimestamp()` without `tz=` produces a naive datetime object and HA raises a runtime error. Fix: always pass `tz=timezone.utc` (or `tz=UTC` from `datetime import UTC`).

- **Duplicate sensors from dual endpoints**: Both `/stat/device` (uplink object) and `/stat/health` (www/wan subsystems) report speedtest results and WAN latency. Initially both were surfaced, producing 8 duplicate entities split between the Gateway and Network sub-devices. Fix: removed all speedtest/WAN sensors from the gateway layer; health endpoint is authoritative for these.

- **Credential eye-icon exposure**: Using `TextSelectorType.PASSWORD` prevents a field from being read as plain text, but pre-filling the field with the stored value allows the user to reveal it via the browser's eye icon. Fix: split setup schema (`_user_schema`) from edit schema (`_edit_schema`); credential fields always default to `""` in edit flows, with `_merge_credentials()` retaining existing values when blank is submitted.

- **`async_redact_data` redacts values, never keys**: `entry.data["boot_times"]` and `data["devices"]` are both keyed by device MAC, so every MAC passed through in cleartext while the `mac` _values_ beside them were correctly redacted — the output looked sanitized. The codebase already knew this (`rogue_history` was flattened from a BSSID-keyed dict to a list of records for exactly this reason) but the insight had not been applied to the other two. Fix: rewrite the keys through the pseudonymiser (`_is_mac()`-gated).

- **Redaction does not reach verbatim vendor payloads**: captured alerts store UniFi's `parameters` blob as-is, and UniFi names its fields `id`, `ip`, `name`. The gateway MAC, internal IPs, ISP name, WAN subnet and WAN interface name all survived inside it despite the same values being redacted at top level. Fix: sanitize the subtree explicitly by block name, plus a shape-based regex backstop for block types not yet mapped.

- **Free text embeds identifiers no key rule can reach**: the alert `message` reads `Internet connection WAN1 <ISP> on port 9 went down…` — the ISP name inline in prose. Fix: learn identifiers in a first pass, then substitute them out of `message`/`title`.

- **Over-redaction is also a defect**: `boot_times` mixes MAC keys with plain interface labels (`wan1`, `wan2`, `www`). Tokenising those turned every alert mentioning WAN1 into `device-22`, destroying the readability of the text a maintainer reads first, while protecting nothing. Fix: gate key rewriting on `_is_mac()`. General rule — sanitize identifiers, not everything that happens to be a dict key.

- **A single diagnostics capture only proves what that capture contained**: the first regenerated file showed `strongest_rogue_ssid: "None Detected"` and an empty `rogue_aps_list` simply because no rogues were present at that moment; both were latent third-party-SSID leaks. Fix: verify against a capture taken while the optional data is populated (long rogue history selected), not just a quiet one.

- **`asyncio.Task` mypy type-arg error**: `asyncio.Task` without a type parameter produces a mypy `type-arg` error under `--strict`. Fix: `asyncio.Task[None]`.

- **Unreachable guard after `_raw_data()` refactor**: Binary sensor base class `_raw_data()` was changed to always return `{}` rather than `None`. A `if data is None: return None` guard at the call site became unreachable and raised a mypy error. Fix: removed the dead guard.

- **`uptime_stats.WAN.alerting_monitors` on the device endpoint**: The device endpoint includes a `uptime_stats.WAN.alerting_monitors` block that reports latency and availability from a 1.1.1.1 ping monitor. This duplicates data already in the health endpoint's `uptime_stats.WAN` block. This block was parsed initially for gateway-level latency/availability sensors; those sensors were removed when duplicates were identified.

- **Host input prefix cleaning**: The API client strips any `http://` / `https://` prefix and trailing slashes from the host input in `__init__` to prevent malformed endpoint URLs.

- **API key auth vs. username/password session**: API key mode sends `X-API-Key: <key>` on every request — no session state. Username/password mode uses a cookie-based session token; a 401 on any request triggers a transparent re-login attempt before failing.

- **Gotcha — auth mode gates the v3 (integration) endpoints**: the UniFi Integration (v3) API (`/proxy/network/integration/v1/…`: `get_sites`, `get_wan_interfaces`, `get_vpn_servers`, `get_vpn_tunnels`, `get_firewall_policies`) is **only reachable with an API key**. Under username/password auth, `get_sites()` fails, so `coordinator.site_uuid` latches to `"failed"` and the seven v3-sourced sensors (Rules Active/Configured/Disabled, VPN Connections Active/Total, WAN1/WAN2 Name) are permanently `unknown`. This is a fundamental UniFi API limitation, **not a bug** — every classic (`/proxy/network/api/s/{site}/…`) endpoint still works under either auth mode. Because the failure is expected under username/password, `_sync_site_issue()` is **auth-mode-aware**: it only raises the `site_resolution_failed` repair issue when `self.api.api_key` is set (a real permission/key problem), and suppresses/clears it in username/password mode. See README FAQ "Why are my firewall, VPN, or WAN-name sensors unknown?" for the user-facing explanation.

- **Daily/Monthly Gateway Stats HTTP 500 Error**: The standard endpoints `/stat/report/daily.gateway` and `/stat/report/monthly.gateway` return HTTP 500 errors on UDM Pro gateways. The correct endpoints are `/stat/report/daily.gw` and `/stat/report/monthly.gw`. These reports return historical traffic statistics containing total RX/TX byte counts (`wan-rx_bytes`, `wan-tx_bytes`, `wan2-rx_bytes`, `wan2-tx_bytes`) used by the data usage sensors.

- **Speedtest Interface Mapping & Target Options**:
  - **Sources of Speedtest Data**: The controller provides speedtest info from three sources: `/stat/health` (WWW subsystem speedtest stats representing the most recent overall run, generally WAN2), `/stat/report/archive.speedtest` (historical, flat list without interface metadata), and the v2 endpoint `/proxy/network/v2/api/site/{site}/speedtest` which returns a history of results populated with `"interface_name"` (e.g. `'eth8'`, `'eth9'`) and `"wan_networkgroup"` (e.g. `'WAN'`, `'WAN2'`).
  - **Retrieval per WAN**: We sort the v2 speedtest history descending (newest first) and match results by checking their `interface_name` against the gateway's configured WAN physical interfaces (`wan1_ifname` and `wan2_ifname` retrieved from the gateway device dictionary, defaulting to `'eth8'` and `'eth9'`).
  - **Proximity Matching Fallback**: For backward compatibility (such as in legacy mock test data environments), if the results do not contain `"interface_name"` metadata, we fall back to a chronological proximity pairing. If the two latest results are within 10 minutes, the older is assigned to WAN1 and the newer to WAN2.
  - **Triggering manual speedtests**: Triggering a manual speedtest via `/proxy/network/api/s/{site}/cmd/devmgr` payload `{"cmd": "speedtest"}` runs on the primary WAN1 interface by default. To trigger a speedtest on a specific interface, we pass `"interface_name": "<interface>"` (e.g. `eth8` or `eth9`) in the trigger payload. We expose separate buttons (**Run WAN1 Speedtest** and **Run WAN2 Speedtest**) to execute targeted tests.

- **Redundant Health Subsystem Speedtests**: The `www` subsystem in `get_health()` contains a single speedtest run (representing the latest run, which duplicates WAN2). Because it lacks interface metadata, it cannot be used as a reliable fallback for WAN1 or WAN2. Redundant speedtest sensors (download, upload, latency, last run) were removed from the Network sub-device, keeping only the diagnostic `speedtest_status`.

- **`mdi:honeycomb` removed from bundled MDI**: an icon name valid in older Material Design Icons was dropped in the version HA bundles, so it rendered blank (Honeypot binary sensor). Fix: use a current icon (`mdi:shield-bug`). Verify `mdi:` names against the bundled set, not the MDI website.

- **Config-flow sections return nested input**: fields inside a `section()` come back as `user_input["<section>"][...]`, not flat. A flat processing pipeline silently loses them (validation/merge sees no toggles). Fix: `_flatten_sections()` at the top of each step handler lifts the section's fields to the top level before anything else touches `user_input`.

- **Options change didn't take effect until manual reload**: the Options flow (gear → Configure) does not reload the entry on submit, and it's a _different_ flow from ⋮ → Reconfigure. Fix: one `add_update_listener` that reloads on non-live option changes, and switch Reconfigure to `async_update_entry` + `async_abort` (no self-reload) so both paths reload exactly once. Exclude live-tunable keys from the reload signature or every scan-interval/threshold tweak reloads the whole integration.

- **Prettier mangles underscores in Markdown prose**: unbackticked identifiers with underscores adjacent to punctuation (e.g. `f"{uid}_{mac}_"`, a leading `_helper`) can be parsed as emphasis and get corrupted (`unique*id`, `\_helper`) when the docs are auto-formatted. Fix: keep every underscore-bearing token inside backtick code spans, or phrase around it.

- **Gotcha — Rogue AP "Age" is Frozen and Not Relative to Present Time**:
  - **API Behavior**: The `/proxy/network/api/s/{site}/stat/rogueap` endpoint returns a static `"age"` integer field. This value represents the age of the detection _at the moment the scan report was generated by the AP_ (computed as `report_time - last_seen` in seconds).
  - **The Pitfall**: Once a rogue AP stops broadcasting, the AP stops reporting it. The controller keeps this final record frozen in its database. Because the record is frozen, `report_time` and `last_seen` remain frozen, and the API's `"age"` field (`report_time - last_seen`) remains `0` seconds forever. This causes the integration to display `"0h"`, even if the device was last seen 17 hours ago.
  - **The Fix**: The integration calculates the true elapsed time since the AP last saw the rogue device using `current_timestamp - last_seen` (defaulting to the API's static age if `last_seen` is absent).
  - **Filtering**: By default, a `GET` request on `/stat/rogueap` returns all rogue APs seen within the last 24 hours (equivalent to a `POST` request with `{"within": 24}`). To retrieve only recent detections (e.g. within the last hour), the integration performs a `POST` request passing `{"within": 1}`.

- **Ruff can strip a still-used import mid-edit**: after a multi-step edit, `ruff check --fix` occasionally removes an import it briefly considered unused, then flags `F821` on the usage. Re-check imports after autofix.

## 6. Environment Constraints

- **Native Async API**: All network calls use `aiohttp` via `async_get_clientsession(hass)` — HA's shared connection pool. No `executor_job` threading required.
- **SSL Verification**: UniFi OS uses self-signed certificates for the local API. The API client sets `ssl=False` for local connectivity.
- **UniFi OS 3.x+**: API key authentication is only available on UniFi OS 3.x and later (UDM Pro on firmware 3+). Older firmware or CloudKey-based controllers require username/password.

## 7. Technical Debt & Future Work

- **GitHub CI**: `.github/workflows/validate.yaml` contains a placeholder `CHANGEME` gist_id that must be updated.
- **Translation-Key Synchronization**: When adding a new sensor, `translations/en.json` must be updated. `strings.json` is not currently used (translation-only integration), but should be kept in sync if Hassfest validation is introduced.

---

## Version Control

- **[2026-06-18]** — Initial commit. Core architecture established: coordinator with 3-strike resilience, dual-endpoint model, gateway/network/device sub-device split, declarative sensor engine, config flow with credential security.
- **[2026-06-21]** — Fixed TIMESTAMP timezone error (`tz=UTC`). Fixed mypy errors (`Task[None]`, unreachable guard). Fixed 5 ruff lint errors. Implemented credential security (blank edit fields + `_merge_credentials`). Added `mcp-wrapper.js` container entry for devcontainer HA MCP server.
- **[2026-06-22]** — Removed 8 duplicate speedtest/WAN sensors from Gateway sub-device (authoritative source is Network/health endpoint). Added missing guard bands to all numeric count and temperature sensors.
- **[2026-06-22]** — Added Pause Polling toggle switch (persisted to `entry.options`, survives restarts; resumes trigger immediate coordinator refresh). Added host URL normalization in all config flow steps (`_clean_host()` strips `http://`/`https://` prefix and trailing slashes before storing). Per-device entity standalone detection: when native `unifi` integration is absent, all AP/switch entities enable by default instead of creating empty disabled sub-devices.
- **[2026-06-22]** — Implemented Multi-WAN load balancing configuration tracking (Failover vs. Weighted Load Balancing modes and split weights) and active routing interface indicators. Added SFP slot transceiver diagnostics, Threat Management state metrics (IPS/IDS mode, Ad-blocking, Honeypot), and persistent storage used percentage. Added 20 new sensor/binary sensor entities and updated tests and translations.
- **[2026-06-22]** — Fixed gateway daily/monthly stats HTTP 500 error by switching endpoints to `.gw`. Fixed speedtest interface assignment and stale values by sorting descending, matching against gateway physical interfaces (eth8/eth9), and fallback proximity-pairing. Removed duplicate speedtest sensors from health/Network sub-device, keeping only `www_speedtest_status`. Renamed firmware version to Application Version, setting state to application version (e.g. 10.4.57) and OS firmware in attributes. Implemented default `GB` suggested unit of measurement for data use sensors. Replaced single "Run Speedtest" button with dedicated target buttons (**Run WAN1 Speedtest** and **Run WAN2 Speedtest**) using `"interface_name"` payloads to force speedtest on specific interfaces.
- **[2026-06-22]** — Removed misleading and redundant gateway-level client counts (`ports_used`, `ports_user`, `ports_guest`) mislabeled as "Ports" under the Gateway's Ports sub-device. Updated development documentation.
- **[2026-06-22]** — Documented the calculated nature of the "Network Problem" health sensor in development documentation.
- **[2026-07-02]** — Coordinator now passes `config_entry=entry` to `DataUpdateCoordinator` (honours the "Enable polling for changes" system option via `pref_disable_polling`; required as HA removes implicit context detection in 2026.8). README now states a 2024.8.0 minimum HA version.
- **[2026-07-08]** — Added Rogue AP proximity detection: **Strongest Rogue SSID** / **Strongest Rogue RSSI** sensors, **Rogue AP Proximity Alert** binary sensor, and a **Rogue Proximity Threshold** number; moved the rogue-AP list attribute onto Strongest Rogue SSID. Brought `config_flow.py` + `coordinator.py` to 100% coverage (added the tests; `# pragma: no cover` on one provably-unreachable defensive branch).
- **[2026-07-09]** — IQS Gold completion (first compliance pass landed the project at 48/50; this closes the last two): **exception-translations** — the `HomeAssistantError` raises in `button.py` (speedtest) and `number.py` (WAN weight) now use `translation_domain`/`translation_key`, with an `exceptions` block in `strings.json` + `translations/en.json`; **repair-issues** — `coordinator._sync_site_issue` raises the `site_resolution_failed` repair (via `issue_registry`) when v3 site resolution fails (disabling VPN/firewall/WAN-name sensors) and clears it on recovery, with an `issues` block in strings/en.json. All 50 trackable IQS rules now DONE.
- **[2026-07-09]** — Code-review fixes (`.notes/code_review/code_review_20260709.md`): (1) `UnifiSpeedtestButton.async_press` now guards `coordinator.data is None` and wraps `UnifiError` as `HomeAssistantError`; (2) `diagnostics.py` `TO_REDACT` corrected to redact `host` and the WAN local/public IPs + `bssid` (the old `uplink_ip` key was never emitted); (3) the **Last Run Problem** binary sensor returns `None` (unknown) instead of `on` when `www_speedtest_status` is empty — **behavior change**: no more false PROBLEM on controllers that have never run a speedtest; (4) dynamic WiFi/VPN unique-ids now use `slugify()` + in-pass de-duplication (`_dedup_suffix`) so names that normalize identically can't collide; (5) `WanLoadBalanceNumber` rejects a set with `HomeAssistantError` up front when the WAN config isn't loaded (`coordinator.wan_weights_writable`), and the detached debounce task logs rather than raising into the void. Tests added for each; ruff/mypy/pytest clean.
- **[2026-07-08]** — Live-validated all four per-device configurations against a devcontainer on a real UDM Pro (standalone and on top of HA Core UniFi): `none`, `satisfaction_only`, `all`. Documented the gateway card-merge and `enable_in_standalone` behavior (base enabled 93 no-Core / 87 Core), the per-mode device/entity/enabled matrix, and the `switch.unifi_network_*` counting caveat. **Bug fix:** switch **Clients** (`ports_used` key) collided with Core's switch Clients and got a `_2` suffix on every switch; `_DUPLICATES_CORE_KEYS` is now a key→stem map with `ports_used → clients`, so it registers as `…_clients_mon`. Renamed **Storage Used (%)** → **Storage Utilization** (removes an earlier `…_storage_used_2` self-collision).
- **[2026-07-09]** — Auth-mode / v3-endpoint limitation made explicit. The UniFi Integration (v3) API is API-key only, so username/password auth legitimately leaves seven sensors (Rules Active/Configured/Disabled, VPN Connections Active/Total, WAN1/WAN2 Name) `unknown`. **`_sync_site_issue` is now auth-mode-aware** — the `site_resolution_failed` repair issue is only raised when `self.api.api_key` is set (and any stale issue is cleared under username/password), so the expected u/p state no longer nags the user (added `test_coordinator_site_issue_suppressed_without_api_key`). Repair-issue text hardened ("exists and has full site permissions"). Setup/reconfigure/reauth step descriptions now flag the API-key preference. Documented the limitation in README (setup callout + FAQ + Known Limitations), `all_sensors.md` (per-row _API-key only_ markers + legend), `api_endpoints.md` (auth-mode flag on the v3 endpoints), and this file (Pitfalls "Gotcha"). No periodic-retry added — it can't help the deterministic u/p case (see plan rationale).
- **[2026-07-08]** — Setup-options / resilience / cleanup rework: `unifi_device_mode` + three feature toggles (`enable_speedtest`/`enable_wan_usage`/`enable_security_monitoring`) gating both entity creation and API fetches (`disabled_endpoints`); per-endpoint hold-then-`unavailable` resilience (`_fetch_optional` reworked, `endpoint_available`, entity `available` overrides, `EP_*` labels); config-flow `sensor_groups` section + `_flatten_sections` + reload-on-settings-change listener; `_mon` entity_id for duplicate-of-core per-device sensors; `cleanup.py` + **Clean Up Unused Entities** button + `cleanup_unused_entities` service (`dry_run`) + `async_remove_config_entry_device` hook; fixed the blank Honeypot icon (`mdi:honeycomb` → `mdi:shield-bug`). New files: `cleanup.py`, `services.yaml`. Source is ruff/mypy-clean; the new code's test suite is a separate follow-up.
- **[2026-07-10]** — Updated rogue AP query logic: changed `get_rogueaps` from `GET` (defaulting to last 24 hours) to `POST` passing `{"within": 1}` to query only detections in the last 1 hour. Fixed the static/frozen `age` attribute by dynamically calculating the true age relative to the present moment (`current_timestamp - last_seen`). Added dedicated unit tests and documented the API age gotcha.
- **[2026-07-13]** — **Security & Alerts sub-devices + rogue expansion.** New `device_key="security"` sub-device (rogue/threat/VPN/firewall relocated off Status/System) with rogue controls: **Rogue Detection Period** select (new `select.py` platform), **Show 2.4/5 GHz Rogues** + **Apply AP/SSID Ignore List** switches, SSID/AP ignore-list setup fields. Shared `parse_rogue_aps`/`build_ap_name_map`. New `enable_dual_wan` (WAN2 key-set filter) and `enable_security_monitoring`/`enable_logs_alerts` gating.
- **[2026-07-13]** — **Alerts monitoring.** New `device_key="alerts"` sub-device (4 per-severity sensors from `system-log/all`/`EP_SYSLOG`, gated by `enable_logs_alerts`), `alerts.py` helpers, `unifi_network_monitor.get_alerts` response action, and the `unifi_network_monitor_new_alert` bus event (baseline + bounded dedup).
- **[2026-07-13]** — **Rogue action/event + raw sensor.** `unifi_network_monitor.get_rogue_aps` response action (`services.py`), `unifi_network_monitor_new_rogue_ap` bus event, and the **Rogue APs All 24h** diagnostic sensor (`rogue_raw_24h`, dedicated `get_rogueaps(within_hours=24)` / `EP_ROGUE_RAW`).
- **[2026-07-13]** — **Recorder/UX hygiene.** `UnifiAboutEntity` mixin adds unrecorded `about:` notes to ~20 entities; `_unrecorded_attributes` on `rogue_aps`/`rogue_aps_truncated`/`parameters`/`udm_version`; `rogue_aps` list capped at 25 (`ROGUE_ATTR_MAX`); `_safe_float` rounds to 3 dp; alert-icon `icons.json` entries added. **Force-refresh** (`async_force_refresh`) makes all explicit user actions bypass Pause Polling.
- **[2026-07-14]** — Docs pass: re-verified the entity manifest live on a fresh standalone default install (**126 registered / 103 enabled / 23 disabled**); updated `all_sensors.md` (7 sub-devices), this file, `api_endpoints.md`, `value_min_max.md`, and `AGENTS.md`.
- **[2026-07-17]** — **Rogue expansion + persistent history + self-diagnosis.** Extended `parse_rogue_aps` (security/channel_width/wired_rogue/is_adhoc/ssid_anomaly) and added **Hidden-`<last4>`** naming (`normalize_essid`/`hidden_label`). Actions gained comma-list `keyword`/`exclude` + `total_matched` (and opt-in `count_total`/`truncated` on `get_alerts`). Added **persistent BSSID-keyed rogue history** (`Store` + `async_initialize`, `first_seen`/`appearances`, TTL + cap, `async_delay_save`), the **Rogue APs New 24h** LTS sensor, restart-surviving `new_rogue_ap`, and `clear_rogue_history`. Added **ignore-list management actions** (`add`/`remove`/`set_rogue_ignore`). Added **Integration Health** self-diagnosis (binary sensor + `schema_drift_detected` repair; shared dev_standards §19). Fixed the config-flow ignore-list fields so a blank submit clears them (`suggested_value` + `default=""`). Counts now **128 base** (verified live 2026-07-17 — Integration Health is the only delta since the prior manifest). Test suite green at 100% coverage. Refined the shared standard to v1.8.0.
