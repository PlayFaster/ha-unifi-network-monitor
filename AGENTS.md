# AGENTS.md

This file provides guidance to AI coding agents when working with code in this repository.

## What This Integration Does

A Home Assistant custom integration (`unifi_network_monitor`) for Ubiquiti UniFi networks anchored by a UDM Pro (or similar gateway). It is a `local_polling` `hub` integration distributed via HACS. It replaces a previous shell-command + 20+ template sensor setup, exposing ~40 sensors and binary sensors across the gateway, network health, access points, and switches. Auth supports both API key (`X-API-Key` header — preferred) and username/password (TOKEN cookie + X-CSRF-Token). There are no external `requirements` beyond `aiohttp` and HA core.

Setup/reconfigure options let users scope which per-device sensors and gateway sensor groups are created (a disabled group also skips its API calls), with per-endpoint hold-then-`unavailable` resilience, an explicit cleanup button/service, and the UI device-delete hook. See **Setup Options, Sensor-Group Scoping & Cleanup** below.

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
  - **Pure parsing functions** (testable without HA): `_parse_gateway`, `_parse_ap`, `_parse_switch`, `_parse_health`. Boot time is derived as `dt_util.now() - timedelta(seconds=uptime_secs)`.
  - Returns `{gateway, health, devices, sw_version}` where `devices` is a `{mac: parsed_dict}` mapping.

- **`__init__.py`** — entry setup registers the gateway device early (before platform forward), forwards platforms, then runs first refresh in a background task (`async_create_background_task`). Coordinator stored on `entry.runtime_data`. Also:
  - Registers the `cleanup_unused_entities` service (`async_setup`) and implements `async_remove_config_entry_device` (the Gold-tier `stale-devices` hook — allows the UI Delete button only when Monitor has no entities left on the device).
  - Registers an update listener (`_async_reload_on_settings_change`) that reloads the entry when a **non-live** option changes, so reconfigure/options take effect on submit. Live-tunable keys (`scan_interval`, `rogue_proximity_rssi_threshold`, `stop_polling`) are excluded from the reload signature so their control entities don't force a reload.

- **`cleanup.py`** — explicit, user-triggered removal of orphaned entities/devices (`CleanupPlan`, `plan_device_cleanup`, `apply_cleanup`). Removes per-device entities the current `unifi_device_mode` excludes (matched by device-MAC unique-id prefix) and the feature-group orphans (matched by endpoint via `disabled_endpoints`), then detaches devices with `async_update_device` using `remove_config_entry_id` (removes a Monitor-only device; only drops the link on a device shared with core). Never runs automatically — driven by the button and service.

- **`helpers.py`** — three `build_*_device_info` functions:
  - `build_gateway_device_info`: uses `connections={(CONNECTION_NETWORK_MAC, mac)}` + `identifiers={(DOMAIN, mac)}` — merges with native UniFi integration device entries.
  - `build_network_device_info`: virtual "Network Health" sub-device (`identifiers={(DOMAIN, f"{mac}_network")}`), linked `via_device=(DOMAIN, mac)`.
  - `build_unifi_device_info`: per-AP/switch device, also uses `connections` + `identifiers`, linked `via_device=(DOMAIN, gateway_mac)`.

- **Platforms** (`sensor`, `binary_sensor`, `button`, `number`, `switch`) — read `coordinator.data` only.
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
- **`entry.options`** — live, user-editable settings: `host`, `api_key`, `username`, `password`, `site`, `scan_interval`, `stop_polling`, `rogue_proximity_rssi_threshold`, and the scoping options `unifi_device_mode` (`none`/`satisfaction_only`/`all`), `enable_speedtest`, `enable_wan_usage`, `enable_security_monitoring` (all default to preserve prior behavior: mode `none`, toggles `True`).

Read credentials from `entry.options`, not `entry.data`. Config flow is `VERSION = 1`.

### UniFi Device Merging

Using `connections={(CONNECTION_NETWORK_MAC, mac)}` in `DeviceInfo` for all physical devices causes HA's device registry to merge this integration's device entries with those created by the native UniFi integration, when both reference the same MAC address. This means custom component sensors appear alongside native integration entities on the same HA device card — no duplicate device entries.

## Setup Options, Sensor-Group Scoping & Cleanup (2026-07 rework)

Full design: `.notes/design_monitor_setup_options.md`. Cross-project porting guide: `shared/SharedNotes/issues/setup_cleanup_options.md`.

- **Per-UniFi-device sensors** (`unifi_device_mode`): `none` (default — create nothing per-device), `satisfaction_only` (AP Satisfaction Score keys only), `all` (everything). Core-detected setup offers all three; core-absent offers `none`/`all`. `sensor.py`'s `_device_descs(dev_type, mode)` returns the descriptions to create; both the static loop and the dynamic listener use it. Superseded the old "always create disabled" behavior (the `standalone` flag now only affects `entity_registry_enabled_default`).
- **Feature toggles** each map to a _sensor group_ **and** its endpoint(s): `enable_speedtest`→`get_speedtest_results`; `enable_wan_usage`→daily/monthly gateway; `enable_security_monitoring`→rogue APs + VPN + firewall. Off = sensors not created **and** the fetch skipped.
- **Config flow**: setup + reconfigure + options share schema builders; the feature toggles live in a collapsible **section** (`from homeassistant.data_entry_flow import section`, key `sensor_groups`). Sectioned input comes back nested, so `_flatten_sections()` lifts it before validation. Reauth still uses the credentials-only `_edit_schema`. Reconfigure does `async_update_entry` + `async_abort` (no self-reload) — the update listener owns the single reload for both reconfigure and options.
- **Duplicate-entity `_mon` id**: per-device sensors that duplicate core (`clients`, `cpu`, `ram`, `uptime` in `_DUPLICATES_CORE_KEYS`) keep their display name but get a deterministic `_mon` entity_id (`async_generate_entity_id`) instead of HA's `_2`. AP Satisfaction Score is not suffixed.
- **`unknown` vs `unavailable`**: a value legitimately absent while the source is healthy returns `None` → `unknown` (e.g. Strongest Rogue RSSI with no rogues; SSID uses the sentinel `"None Detected"`). A stale/unreachable endpoint returns `unavailable` (via the `available` override).
- **Cleanup is explicit-only**: options never delete. Removal happens via the **Clean Up Unused Entities** button (`EntityCategory.CONFIG`, enabled by default, commit-only) or the **`unifi_network_monitor.cleanup_unused_entities`** service (`dry_run` default `True`, `SupportsResponse.OPTIONAL` returns a report). Both call `plan_device_cleanup`/`apply_cleanup` in `cleanup.py`, then reload out-of-band.

## Key Patterns & Conventions

- Ruff is strict: `D`, `N`, `ASYNC`, `T20`, `SIM`, `UP` enabled. Target `py314`, line length 88.
- mypy runs in strict mode over `custom_components/` only.
- `_LOGGER` messages are prefixed with `self.entry.title` (`"%s: ..."`) — match that style.
- The `.notes` and `.shared` symlinks point outside the repo (project notes / shared validation configs) and are not part of the shipped integration.

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
| `POST /api/auth/login` | Obtain TOKEN cookie + X-CSRF-Token (username/password auth only) |
| `POST /api/auth/logout` | Invalidate session |

## Phase B (Future — Separate Session)

Planned additions not in the current implementation:

- ISP data usage sensors (WAN1/WAN2 GB used/remaining from `/proxy/network/api/s/{site}/stat/daily`)
- Load-sharing read sensors (active WAN, load-sharing mode)
- Load-sharing write capability (`select` entity + HA service to switch between WAN failover modes)
- GitHub CI wiring (`.github/workflows/`)

Note: the test suite reached 100% coverage before the 2026-07 setup-options/resilience/cleanup rework; that rework's new code (options gating, per-endpoint resilience, `cleanup.py`, service/hook, config-flow sections) still needs test updates.
