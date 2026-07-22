# AGENTS.md

This file provides guidance to AI coding agents when working with code in this repository.

## What This Integration Does

A Home Assistant custom integration (`unifi_network_monitor`) for Ubiquiti UniFi networks anchored by a UDM Pro (or similar gateway). It is a `local_polling` `hub` integration distributed via HACS. It replaces a previous shell-command + 20+ template sensor setup, exposing **128 base entities** (sensors, binary sensors, buttons, numbers, switches, and a select) across **seven** sub-devices — Gateway, Internet, Speedtest, **Security**, **Alerts**, Status, System — plus optional per-AP/switch sensors. Auth supports both API key (`X-API-Key` header — preferred) and username/password (TOKEN cookie + X-CSRF-Token). There are no external `requirements` beyond `aiohttp` and HA core.

Setup/reconfigure options let users scope which per-device sensors and gateway sensor groups are created (a disabled group also skips its API calls), with per-endpoint hold-then-`unavailable` resilience, an explicit cleanup button/service, and the UI device-delete hook. See **Setup Options, Sensor-Group Scoping & Cleanup** below.

Beyond passive entities it also exposes: **on-demand response actions** (`get_alerts`, `get_rogue_aps` — both with `keyword`/`exclude` comma-list filters + `total_matched`; `get_alerts` also has opt-in `count_total`); **list-management actions** (`clear_rogue_history`, and `add_rogue_ignore` / `remove_rogue_ignore` / `set_rogue_ignore` with a `target: ssids|aps`); two **bus events** (`unifi_network_monitor_new_alert`, `unifi_network_monitor_new_rogue_ap`); a **persistent rogue-AP appearance history** (BSSID-keyed `Store` → `first_seen`/`appearances` + the **Rogue APs New 24h** sensor); and an **Integration Health** self-diagnosis binary sensor (`problem`) backed by the `site_resolution_failed` + `schema_drift_detected` repair issues. See **Architecture** and the sections below.

## Commands

### Tests

```bash
# Run the full test suite
pytest

# Run a single test file / test
pytest tests/test_coordinator.py
pytest tests/test_api.py::test_login -q
```

### Linting & Formatting

```bash
# Lint + autofix and format (config in pyproject.toml)
ruff check --fix .
ruff format .

# Type check (only custom_components; needs /ha_core mounted)
mypy custom_components/

# Run all configured checks at once
pre-commit run --all-files
```

### Running tools from a Windows host

These commands only work **inside** the devcontainer — HA imports `fcntl`, so `pytest` (and other tools) cannot run on a Windows host directly. From Windows, run everything through `docker exec` against the running container. See [`.shared/prompts/devcon_run_gen.md`](.shared/prompts/devcon_run_gen.md) for the full mini-skill. Quick reference:

```bash
# Confirm the container is up first
docker ps --filter "name=<CONTAINER_NAME>" --format "{{.Names}}"

# Run a tool inside the container (-w sets the in-container working dir)
docker exec -w /workspaces/<PROJECT_DIR> <CONTAINER_NAME> bash -c "PYTHONPATH=. pytest tests/"
docker exec -w /workspaces/<PROJECT_DIR> <CONTAINER_NAME> bash -c "ruff check ."
```

Container identity values (`CONTAINER_NAME`, `PROJECT_DIR`) are in `.devcontainer/.env`.

Do not install or run these tools on the host as a workaround.

## Architecture

Data flows in one direction: **`api.py` → `coordinator.py` → platform entities**. Entities never call the API directly for reads; they read `coordinator.data`.

- **`api.py` (`UnifiNetworkAPI`)** — async HTTP client for the UniFi Network API. Key behaviors:
  - Two auth modes: API key (`X-API-Key: <key>` header) or username/password (POST `/api/auth/login`, store TOKEN cookie + X-CSRF-Token header). API key is preferred.
  - **Auth mode gates the v3 endpoints — not a bug:** the Integration (v1) endpoints (`get_sites`/`get_wan_interfaces`/`get_vpn_*`/`get_firewall_policies`) are **API-key only**. Under username/password, `site_uuid` latches `"failed"` and 7 sensors (Rules Active/Configured/Disabled, VPN Connections Active/Total, WAN1/WAN2 Name) are legitimately `unknown` — expected, don't "fix" it. `coordinator._sync_site_issue` only raises the repair issue in API-key mode. See `DEVELOPMENT.md` §5 Gotcha.
  - `_get(path)` handles auto re-auth on 401 for username/password mode.
  - Three data endpoints: `/proxy/network/api/s/{site}/stat/device`, `/stat/health`, `/stat/sysinfo`.
  - `validate_connection()` — fetches devices + sysinfo, finds gateway device, returns `{mac, model, sw_version}`. Used only at config flow time.
  - Two exception types: `UnifiConnectionError` (network/transient) and `UnifiAuthError` (credentials). Raise the right one.

- **`coordinator.py` (`UnifiNetworkDataUpdateCoordinator`)** — polling + parsing + resilience layer.
  - **Flat Identity**: gateway MAC, model, and sw_version are loaded from `entry.data` at init time — no network call needed to identify the gateway device on boot.
  - **Global 3-Strike Rule**: applies to the two mandatory fetches (`get_devices`, `get_health`) and the whole update. On error, return cached `self.data` for failures 1–3; raise `UpdateFailed`/`ConfigEntryAuthFailed` on the 4th. `self.consecutive_failures` tracks the count.
  - **Per-endpoint resilience** (optional fetches): `_fetch_optional` holds each endpoint's last-good payload for `FETCH_STRIKE_LIMIT` (3) failures, then flags it stale (`self._stale_endpoints`). It distinguishes _failure_ from _empty_ and has a broadened `except` so an API-shape change degrades one endpoint, not the whole update. Entities tag their source endpoint (`_ENDPOINT_BY_KEY` / `_BINARY_ENDPOINT_BY_KEY`) and go **`unavailable`** via an `available` override when `coordinator.endpoint_available(source)` is False — while other endpoints keep serving data.
  - **Fetch skip when a feature is off**: `disabled_endpoints(options)` returns the endpoints whose feature toggle is disabled; `_optional(enabled, method, label)` substitutes a no-op `_skip_fetch` for those, preserving the positional `gather` unpack. Endpoint labels are shared `EP_*` constants in `const.py` (used by both the fetch calls and the entity tags — never inline them separately).
  - **Pure parsing functions** (testable without HA): `_parse_gateway`, `_parse_ap`, `_parse_switch`, `_parse_health`, and module-level `parse_rogue_aps` / `normalize_essid` / `hidden_label`. Boot time is derived as `dt_util.now() - timedelta(seconds=uptime_secs)`.
  - **Persistent rogue history**: `rogue_history` (BSSID → `{first_seen, last_seen, appearances, last_label}`) is loaded from a `Store` in `async_initialize()` (called from `__init__` before the first refresh) and updated each poll on the Security path (`_update_rogue_history` → baseline/new detection, TTL + hard-cap prune, coalesced `async_delay_save`). It re-keys the `new_rogue_ap` event so it survives restarts, and feeds `first_seen`/`appearances` + the `rogue_new_24h` sensor.
  - **Integration Health self-diagnosis**: `_compute_integration_health()` turns internal state (`_stale_endpoints − disabled_endpoints`, v3-under-password suppression, per-source schema-drift strike counters) into a health snapshot; `_sync_health_issues()` raises/clears the `schema_drift_detected` repair. The whole block is wrapped so a malformed payload can never crash the update it diagnoses.
  - Returns `{gateway, health, devices, sw_version, integration_health}` where `devices` is a `{mac: parsed_dict}` mapping.

- **`__init__.py`** — entry setup registers the gateway device early (before platform forward), forwards platforms, then runs first refresh in a background task (`async_create_background_task`). Coordinator stored on `entry.runtime_data`. Also:
  - Registers the `cleanup_unused_entities` service (`async_setup`) and implements `async_remove_config_entry_device` (the Gold-tier `stale-devices` hook — allows the UI Delete button only when Monitor has no entities left on the device).
  - Registers an update listener (`_async_reload_on_settings_change`) that reloads the entry when a **non-live** option changes, so reconfigure/options take effect on submit. Live-tunable keys (`scan_interval`, `rogue_proximity_rssi_threshold`, `stop_polling`) are excluded from the reload signature so their control entities don't force a reload.
  - `async_unload_entry` flushes both `Store`s (`coordinator.async_flush_stores()`) before teardown — a reload fires no `HOMEASSISTANT_STOP`, so a coalesced `async_delay_save` would otherwise be lost.
  - `async_remove_entry` deletes both `.storage` files on entry removal (`Store(...).async_remove()`, which suppresses `FileNotFoundError`). Keys come from the shared helpers `rogue_history_storage_key()` / `usage_watermark_storage_key()` in `const.py` — the **same** helpers the coordinator uses to construct the stores, so write-side and delete-side keys cannot drift. Both keys embed `entry_id`, so the files are unreachable once the entry is gone; leaving them would only orphan them.

- **`cleanup.py`** — explicit, user-triggered removal of orphaned entities/devices (`CleanupPlan`, `plan_device_cleanup`, `apply_cleanup`). Removes per-device entities the current `unifi_device_mode` excludes (matched by device-MAC unique-id prefix) and the feature-group orphans (matched by endpoint via `disabled_endpoints`), then removes emptied devices with `async_remove_device`. Monitor never shares a device with core UniFi (identity-only devices — see _Device Co-existence_ below), so every planned device is Monitor-owned and removed outright. Lookups/ownership go through the version shims in `_compat.py` (`device_by_identifier`, `owning_entry_ids`). Never runs automatically — driven by the button and service.

- **`helpers.py`** — three `build_*_device_info` functions. All devices are **identity-only** (`identifiers={(DOMAIN, …)}`, no `connections`) so Monitor never merges with core UniFi (see _Device Co-existence_). Parent links go through `_compat.via_device_link(...)`, which emits `via_device_id` on HA 2026.8+ and the legacy `via_device` tuple on ≤2026.7:
  - `build_gateway_device_info`: root gateway device, `identifiers={(DOMAIN, mac)}`.
  - `build_network_device_info`: virtual "Network Health" sub-device (`identifiers={(DOMAIN, f"{mac}_network")}`), linked to the gateway.
  - `build_unifi_device_info`: per-AP/switch device (`identifiers={(DOMAIN, device_mac)}`), linked to the gateway as connectivity.

- **`alerts.py` / `services.py` / `select.py`** — Alerts helpers (parameter substitution, title cap, attr/response/event payload builders); the response actions `get_alerts` + `get_rogue_aps` (`SupportsResponse.ONLY`, domain-global, target-resolving, self-contained fetch, decoupled from feature toggles) with `keyword`/`exclude` comma-list filters + `total_matched` (and `count_total` on alerts); the **list-management** actions `clear_rogue_history` and `add`/`remove`/`set_rogue_ignore` (mutate `entry.options` → the reload listener applies them; `set` returns `old`/`new`); and the **Rogue Detection Period** select. The two bus events (`EVENT_NEW_ALERT` / `EVENT_NEW_ROGUE_AP`) fire from the coordinator parse with a first-poll/re-enable baseline + bounded dedup, gated on the feature flag. Shared rogue parsing lives in `coordinator.parse_rogue_aps` (band/ignore/BSSID-cluster + `security`/`channel_width`/`wired_rogue`/`is_adhoc`/`ssid_anomaly` fields + `Hidden-<last4>` naming for cloaked SSIDs), used by both the sensor view and `get_rogue_aps`. `helpers.UnifiAboutEntity` adds an unrecorded `about:` attribute; the gateway sensor also unrecords `rogue_aps`/`rogue_aps_truncated`/`parameters`/`udm_version`.

- **Platforms** (`sensor`, `binary_sensor`, `button`, `number`, `switch`, `select`) — read `coordinator.data` only.
  - All platforms set `PARALLEL_UPDATES = 0`.
  - All entity descriptions use `translation_key=` (never `name=`); `_attr_has_entity_name = True`.
  - **Guard bands** — `UnifiSensorEntityDescription` carries `min_limit`/`max_limit`; `native_value` returns `None` for out-of-range numeric values.
  - **Dynamic entities** — entities for APs and switches are created from coordinator data at setup time, plus a coordinator listener adds entities for newly-discovered devices.
  - **Option-gated creation** — each platform's static loop **and** dynamic listener honour `unifi_device_mode` (per-device sensors) and the feature toggles (gateway sensor groups). A disabled group is _not created_ (not created-disabled). See below.
  - `binary_sensor.py` `all_ok` sensor uses **inverted** PROBLEM logic: `is_on = True` means there is a problem.

### Device Identity Model ("Flat Identity")

Hardware metadata (`mac`, `model`, `sw_version`) is discovered once at config flow time via `validate_connection()`, stored in `entry.data`, and loaded into the coordinator without any network call at boot. This keeps device info stable before the first poll completes.

### Config Entry Data vs. Options

- **`entry.data`** — discovered hardware metadata: `mac`, `model`, `sw_version` (plus persisted `boot_times`).
- **`entry.options`** — live, user-editable settings: `host`, `api_key`, `username`, `password`, `site`, `scan_interval`, `stop_polling`, `rogue_proximity_rssi_threshold`, the scoping options `unifi_device_mode` (`none`/`satisfaction_only`/`all`) + `enable_speedtest` / `enable_wan_usage` / `enable_security_monitoring` / `enable_logs_alerts` / `enable_dual_wan`, and the live rogue controls `rogue_period`, `rogue_show_24ghz`/`rogue_show_5ghz`, `rogue_apply_ap_ignore`/`rogue_apply_ssid_ignore`, `rogue_ignore_ssids`/`rogue_ignore_aps`, and `rogue_history_ttl_days` (default 90; 0 = keep forever) (all default to preserve prior behavior: mode `none`, toggles `True`). The rogue-control keys are **live keys** (read each poll, applied via force-refresh) so they don't trigger a reload. **Note:** the two ignore-list text fields use `description={"suggested_value": …}` + `default=""` in `_settings_schema` so a cleared field actually clears — `default=<current>` would let the frontend's omitted-empty-optional restore the old value.

Read credentials from `entry.options`, not `entry.data`. Config flow is `VERSION = 1`.

### Device Co-existence — separate but aware (2026-07 rework)

Monitor **does not merge** its devices with the core `unifi` integration. Devices are **identity-only** (`identifiers={(DOMAIN, …)}`, deliberately **no** `connections={(CONNECTION_NETWORK_MAC, …)}`), so they never collide with core UniFi's devices and Monitor owns its own device tree. This is uniform on every HA version: HA 2026.8 removed cross-integration device merging outright, and not carrying the shared connection makes older HA behave the same way — one behaviour, no version branch.

Why the change: merging depended on the shared MAC connection, which 2026.8 no longer honours. Keeping it would have produced two behaviours across the 2026.8 line (merged on ≤2026.7, split on 2026.8+); dropping it gives one no-merge model everywhere, with **no minimum-version floor**. Full rationale and the deprecated-API migration: `.notes/device_registry/device_model_2026_08.md`.

**Still core-aware** (entity-level, independent of device grouping): when core `unifi` is installed (`"unifi" in hass.config_entries.async_domains()`), sensors that duplicate what it already provides are **created but disabled by default** (`entity_registry_enabled_default=False` + `enable_in_standalone=True`, flipped on only when standalone). So Monitor avoids redundant entities/polling without ever sharing a device card.

**Version compatibility (`_compat.py`).** The deprecated registry surfaces (`async_get_device(identifiers=)`, `DeviceEntry.config_entries`, `DeviceInfo.via_device` tuple — all removed in HA 2027.8) are feature-detected against the HA classes and routed through shims (`device_by_identifier`, `owning_entry_ids`, `via_device_link`), so the integration is correct from ≤2026.7 through post-2027.8 with no floor. Phase 2 (formal child devices, architecture discussion #1414) is tracked but unshipped.

## Setup Options, Sensor-Group Scoping & Cleanup (2026-07 rework)

Full design: `.notes/design_monitor_setup_options.md`. Cross-project porting guide: `shared/SharedNotes/issues/setup_cleanup_options.md`.

- **Per-UniFi-device sensors** (`unifi_device_mode`): `none` (default — create nothing per-device), `satisfaction_only` (AP Satisfaction Score keys only), `all` (everything). Core-detected setup offers all three; core-absent offers `none`/`all`. `sensor.py`'s `_device_descs(dev_type, mode)` returns the descriptions to create; both the static loop and the dynamic listener use it. Superseded the old "always create disabled" behavior (the `standalone` flag now only affects `entity_registry_enabled_default`).
- **Feature toggles** each map to a _sensor group_ **and** its endpoint(s): `enable_speedtest`→`get_speedtest_results`; `enable_wan_usage`→daily/monthly gateway; `enable_security_monitoring`→rogue APs + VPN + firewall + settings; `enable_logs_alerts`→`system-log/all` (Alerts). Off = sensors not created **and** the fetch skipped. `enable_dual_wan` is the exception — WAN2 rides the _shared_ endpoints, so it's a creation/cleanup **key-set** filter (removes WAN2 + load-balance entities), never routed through `disabled_endpoints`.
- **Config flow**: setup + reconfigure + options share schema builders; the feature toggles live in a collapsible **section** (`from homeassistant.data_entry_flow import section`, key `sensor_groups`). Sectioned input comes back nested, so `_flatten_sections()` lifts it before validation. Reauth still uses the credentials-only `_edit_schema`. Reconfigure does `async_update_entry` + `async_abort` (no self-reload) — the update listener owns the single reload for both reconfigure and options.
- **Duplicate-entity `_mon` id**: per-device sensors that duplicate core (`clients`, `cpu`, `ram`, `uptime` in `_DUPLICATES_CORE_KEYS`) keep their display name but get a deterministic `_mon` entity_id (`async_generate_entity_id`) instead of HA's `_2`. AP Satisfaction Score is not suffixed.
- **`unknown` vs `unavailable`**: a value legitimately absent while the source is healthy returns `None` → `unknown` (e.g. Strongest Rogue RSSI with no rogues; SSID uses the sentinel `"None Detected"`). A stale/unreachable endpoint returns `unavailable` (via the `available` override).
- **Cleanup is explicit-only**: options never delete. Removal happens via the **Clean Up Unused Entities** button (`EntityCategory.CONFIG`, enabled by default, commit-only) or the **`unifi_network_monitor.cleanup_unused_entities`** service (`dry_run` default `True`, `SupportsResponse.OPTIONAL` returns a report). Both call `plan_device_cleanup`/`apply_cleanup` in `cleanup.py`, then reload out-of-band.

## Key Patterns & Conventions

- Ruff is strict: `D`, `N`, `ASYNC`, `T20`, `SIM`, `UP` enabled. Target `py314`, line length 88.
- mypy runs in strict mode over `custom_components/` only.
- `_LOGGER` messages are prefixed with `self.entry.title` (`"%s: ..."`) — match that style.
- The `.notes` and `.shared` symlinks point outside the repo (project notes / shared validation configs) and are not part of the shipped integration.

### README Anchor Links & Emoji Headings

README headings carry emoji, and **many of them are two codepoints** — the glyph plus an invisible variation selector `U+FE0F` (`⏱️ ⚙️ ✂️ 🎛️ 🖥️ 🛡️ ♻️ …`). GitHub strips **both** codepoints when generating the heading anchor, so:

- The anchor for `## ✂️ Tailoring What's Monitored` is **`#-tailoring-whats-monitored`** — leading hyphen (from the space the emoji left behind), apostrophe dropped, no emoji remnant.
- Writing `#️-tailoring-whats-monitored` (with the `U+FE0F` carried over) produces a **404**. The link checker reports it as `#%EF%B8%8F-…` — `%EF%B8%8F` is the percent-encoded variation selector and is the tell-tale signature of this bug.

Rules:

- **Never copy the emoji into an anchor.** Build the target from the heading text alone: lowercase, drop punctuation, spaces → hyphens, and keep the leading hyphen the stripped emoji leaves.
- A `-` in a heading becomes `---` in the anchor (space→`-`, hyphen, space→`-`).
- **Prefer single-codepoint emoji for new headings** (`📖 🧰 🔄 🔀 💾 🤝`) over variation-selector ones. It avoids the trap entirely and keeps anchors predictable.
- After adding or renaming a heading, verify with the link checker rather than by eye — `U+FE0F` is invisible in every editor. To inspect bytes: `grep -n '<text>' README.md | cat -A` and look for `M-oM-8M-^O`.

This has been hit three times (2026-07). Fix the link, not the heading — the emoji renders correctly and GitHub handles it; only hand-written anchors get it wrong.

### Exception Tuple Syntax — Settled Decision

Always use `except (A, B):` with explicit parentheses for multi-exception catches. Never use the bare-tuple form `except A, B:`.

- **Do not flag or change this** — it has been researched and decided.
- `except A, B:` silently catches only `A` on Python 3.12–3.13 (what HA runs on in production), making it a correctness issue, not just style.
- `except (A, B):` is correct and unambiguous across Python 2.6 through 3.14+.
- Full background: `shared/SharedNotes/info/py_exception_tuple_syntax/issue_summary.md`

## Development Environment

The project uses a VS Code devcontainer (`.devcontainer/`, image `ha-dev-base:latest`; see `.devcontainer/docker-compose.yml`) running a Home Assistant instance for live testing. HA core source is mounted read-only at `/ha_core`; mypy resolves HA types against it via `mypy_path = "/ha_core"` and will not typecheck correctly outside an environment where that path exists.

### MCP Access (ha-mcp-dev)

When the devcontainer is running, the `ha-mcp-dev` MCP server automatically connects to the HA instance inside it (`http://localhost:8123`). Use it to verify integration changes without leaving the editor.

**After any modification, follow the post-modification process** — see [`.shared/prompts/post_mod_process.md`](.shared/prompts/post_mod_process.md). Specify a `SCOPE` when invoking it:

| SCOPE      | What runs                                                 |
| :--------- | :-------------------------------------------------------- |
| `None`     | Changes only — no validation                              |
| `Basic`    | HA restart + error check + lint/format fixes              |
| `Full`     | Basic + mypy (standard) + pytest (fix failing tests only) |
| `Complete` | Full + pre-commit --all-files + mypy --strict             |

Additional tools useful during development:

- `ha_get_state` / `ha_search_entities` — verify entity states and attributes after a reload
- `ha_call_service` — trigger service calls to exercise platform callbacks directly

Live HA for manual testing runs at `http://localhost:8123`; the integration is mounted into `/config/custom_components/`. Tests use `pytest-homeassistant-custom-component` with `asyncio_mode = "auto"` (no `@pytest.mark.asyncio` needed).

Validation reports are written to the `.reports/` directory (gitignored outputs from lint/test runs).

### Skill Prompts

Three reusable prompts are available via `.shared/prompts/` for working within this devcontainer:

| Prompt | Purpose |
| :-- | :-- |
| `devcon_run_gen.md` | Run any single command inside the container |
| `devcon_run_and_fix.md` | Full test + lint cycle: pytest, ruff, prettier, validate — with auto-fix |
| `devcon_coverage.md` | Coverage report, target file selection, and new test writing |

## API Endpoints Reference

| Endpoint | Purpose |
| :-- | :-- |
| `GET /proxy/network/api/s/{site}/stat/device` | All adopted devices (UDM, APs, switches) with live stats |
| `GET /proxy/network/api/s/{site}/stat/health` | Network health subsystems (wan, www, wlan, lan, vpn) |
| `GET /proxy/network/api/s/{site}/stat/sysinfo` | System info including firmware version |
| `POST /proxy/network/api/s/{site}/stat/rogueap` | Rogue APs within `{within}` hours (Security; queried at the live period + a fixed 24h for the raw sensor) |
| `POST /proxy/network/v2/api/site/{site}/system-log/all` | System-log alerts (Alerts group; `EP_SYSLOG` polls HIGH/VERY_HIGH; `get_alerts` queries all four severities) |
| `POST /api/auth/login` | Obtain TOKEN cookie + X-CSRF-Token (username/password auth only) |
| `POST /api/auth/logout` | Invalidate session |

Full endpoint reference (incl. speedtest, reports, config, v3): `docs/api_endpoints.md`.

## Remaining Work (Future — Separate Session)

Most of the original Phase B has shipped — ISP data-usage sensors, load-balance read (active WAN, mode/weights) and write (WAN1 weight number). Still outstanding:

- GitHub CI wiring (`.github/workflows/` — `validate.yaml` still has a placeholder `CHANGEME` gist_id).
- **Rogue-AP action/event fast-follow refinements** and any further alerts polish.

Note: the test suite is at **100% coverage** (verified 2026-07-17), including the 2026-07 work — options gating, per-endpoint resilience, `cleanup.py`, service/hook, config-flow sections, the Security/Alerts sub-devices, the `get_alerts`/`get_rogue_aps` actions + `new_alert`/`new_rogue_ap` events, `select.py`, the `about`/unrecorded-attribute layer, and the later rogue expansion — hidden-SSID naming + `ssid_anomaly` + new rogue fields, action `keyword`/`exclude`/`total_matched`/`count_total`, the persistent rogue history + `rogue_new_24h` sensor + `clear_rogue_history`, the ignore-list management actions, and the **Integration Health** self-diagnosis (`_compute_integration_health`/`_sync_health_issues` + the `schema_drift_detected` repair). Source is ruff/mypy-clean.
