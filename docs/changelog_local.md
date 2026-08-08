# Internal Detailed Changelog: UniFi Network Monitor

All changes to this project will be documented in this file. This is the detailed changelog, to include non user facing changes and intra-release changes.

---

- [Internal Detailed Changelog: UniFi Network Monitor](#internal-detailed-changelog-unifi-network-monitor)
  - [\[1.0.1-dev13\] - 2026-08-08 - Standards Sweeps; Translation Reconciliation; Zero-Assertion Tests Fixed](#101-dev13---2026-08-08---standards-sweeps-translation-reconciliation-zero-assertion-tests-fixed)
  - [\[1.0.1-dev12\] - 2026-08-08 - WAN Write Path Hardened; Repairs Scoped; Projected Usage](#101-dev12---2026-08-08---wan-write-path-hardened-repairs-scoped-projected-usage)
  - [\[1.0.1-dev11\] - 2026-08-08 - Green Suite: Device-Registry Test Shape; Ruff Clean](#101-dev11---2026-08-08---green-suite-device-registry-test-shape-ruff-clean)
  - [\[1.0.1-dev9\] - 2026-08-07 - Readme Automation Corrections; Formats](#101-dev9---2026-08-07---readme-automation-corrections-formats)
  - [\[1.0.1-dev8\] - 2026-08-07 - CI Bumps; Github Zipfile; PyTest Branch \& Mutation Testing](#101-dev8---2026-08-07---ci-bumps-github-zipfile-pytest-branch--mutation-testing)
  - [\[1.0.1-dev7\] - 2026-07-28 - Automation Example Glitch Guards \& Float Rounding in README](#101-dev7---2026-07-28---automation-example-glitch-guards--float-rounding-in-readme)
  - [\[1.0.1-dev6\] - 2026-07-27 - Device-Registry Record Split](#101-dev6---2026-07-27---device-registry-record-split)
  - [\[1.0.1-dev5\] - 2026-07-27 - Standards Test Coverage Recorded](#101-dev5---2026-07-27---standards-test-coverage-recorded)
  - [\[1.0.1-dev4\] - 2026-07-27 - §14 Attributes Are Unrecorded by Default](#101-dev4---2026-07-27---14-attributes-are-unrecorded-by-default)
  - [\[1.0.1-dev3\] - 2026-07-27 - Cross-Project Alignment](#101-dev3---2026-07-27---cross-project-alignment)
  - [\[1.0.1-dev2\] - 2026-07-26 - README Section Moved; Automation Cross-Links](#101-dev2---2026-07-26---readme-section-moved-automation-cross-links)
  - [\[1.0.1-dev1\] - 2026-07-26 - Health Automation Example; AGENTS Restructured; Bumps](#101-dev1---2026-07-26---health-automation-example-agents-restructured-bumps)
  - [\[1.0.0\] - 2026-07-22 - Initial Public Release](#100---2026-07-22---initial-public-release)

---

## [1.0.1-dev13] - 2026-08-08 - Standards Sweeps; Translation Reconciliation; Zero-Assertion Tests Fixed

Phase 2 of the August 2026 update plan — the test baseline. No production behaviour changes; this release is entirely about what the suite can catch.

### Added

- **Guard-band coverage sweeps** (`tests/test_standards_guards.py`). Every numeric sensor must declare a lower bound or appear on a named, currently-empty allow-list, and no accumulating counter may carry an upper bound. The sweep is deliberately **static**: a guard band is never published as state or an attribute — it only suppresses an out-of-range value — so no live query can tell whether one exists. The upper-bound requirement is scoped to percentages, the only quantity here with a real ceiling; demanding one of every counter would push the next author into inventing a number that silently suppresses real data.
- **A ban on `SensorStateClass.TOTAL`**, with an empty allow-list and a stale-entry check. Under `TOTAL` the recorder recognises a reset only from a changing `last_reset`; every counter here resets to zero without publishing one, so `TOTAL_INCREASING` is always correct and nothing fails at runtime when it is not.
- **Translation and icon reconciliation** (`tests/test_translations_icons.py`), against **code** rather than file-to-file — two hand-maintained files can agree perfectly and both describe an entity that no longer exists. Keys are read from module source so that single-instance entities, which set `_attr_translation_key` on the class rather than in a description, are not reported as dead entries. Exception messages are reconciled separately and in both directions.
- **Stored-secret pre-fill guards** for all three config-flow schemas and both credentials. No defect today; the guard is on what comes next.
- **Teardown contract tests** — `logout()` is awaited on unload, the store flush is ordered before it, a failing logout does not block the unload, and the platform-unload result is propagated.
- **Shared device-registry helpers in `tests/conftest.py`** — `make_device`, `make_device_registry`, `assert_links_to_parent`, `assert_is_root` — with the three files that branched on the HA version ad hoc migrated onto them. The version question is now asked in one place.

### Fixed

- **The seven zero-assertion tests now assert an outcome.** The audit reports **0 of 687**, and no allow-list file was needed: every case had an observable outcome once looked for. The rogue-event tests listen on the bus and assert what fired — including that a rogue with no BSSID is dropped rather than fired with a null dedup key. `test_apply_after_debounce_handles_exception` was asserting nothing about nothing: it raised from a call the rewritten code no longer makes, so it could not have failed for any reason.
- **Line coverage restored to 100%** — the five statements left uncovered by the Phase 1 changes are now exercised, including the three distinct write-outcome log levels.

### Verified

- `pytest tests/` — **715 passed**, 0 failed. Coverage **100% line** (2944 statements, 0 missing), 98% branch.
- Assertion audit **PASSED**; `ruff check`, `ruff format --check` and `mypy --strict` all clean.
- **Partial branches stand at 59** and are the outstanding half of this phase, listed by module in the plan's execution log.

## [1.0.1-dev12] - 2026-08-08 - WAN Write Path Hardened; Repairs Scoped; Projected Usage

Phase 1 of the August 2026 update plan — the behaviour changes. A failing test was written and seen to fail for every item before any source changed.

### Fixed

- **The WAN load-balance write no longer PUTs stale held state.** `networkconf` is a degradable endpoint, so the object the coordinator was holding could be minutes old — and the write PUT that whole object back with one field replaced, silently reverting every other controller-side change made since. It now re-reads `networkconf` immediately before composing the PUT. Both refusal paths (no WAN objects, no `_id`) fire before any write, so a bad read writes nothing at all.
- **A cancelled debounce could leave WAN1 and WAN2 disagreeing.** The entity cancels its own debounce task on every slider move, and once the two-second wait had elapsed that cancellation landed _between the two weight PUTs_ — WAN1 written, WAN2 not, the pair no longer summing to 100, and nothing reporting it. Two slider moves about two seconds apart were enough. The pair is now awaited through `asyncio.shield`: the caller can still be cancelled, but the write completes.
- **A pending debounced write is now flushed on removal, not discarded.** Both number entities cancelled their buffer in `async_will_remove_from_hass`. A reload triggers removal and an options change triggers a reload, so a value set inside the two-second window was routinely lost while the UI went on showing it. The flush is conditional on the write not having started, so an in-flight write is never issued twice.
- **Repair issues are cleared on unload and on removal.** Neither teardown path touched the issue registry. After removal in particular there was nothing left that could ever clear a raised repair, leaving a permanent Repairs warning about an integration the user had deleted.
- **The reauth screen explains what a blank field does.** `config.step.reauth_confirm` had no `data_description` at all — on the one screen where a blank submit re-tries the credential that just failed. The new text says so explicitly rather than copying reconfigure's reassuring "leave blank to keep the current value".

### Added

- **WAN1 and WAN2 Projected Usage sensors.** Projected end-of-calendar-month usage, derived from the monthly counters already polled — no new API call. Deliberately carries **no `state_class`**: a forecast is not a measurement and must never reach statistics or long-term storage. Confidence is published as an attribute (`confidence`, `basis`, `cycle_day`, `cycle_start`) rather than withheld as `unknown`, because a blank sensor on the 1st of the month reads as broken. WAN2 is gated on the existing dual-WAN toggle. Ported from the ZTE integration, with `cycle_bounds` reduced to a calendar-month form since UniFi's counters roll on the 1st.

### Changed

- **Repair issue IDs are scoped to the config entry** (`f"{entry_id}_{name}"`), via a shared `repair_issue_id()` helper so raise-side and clear-side ids cannot drift. Multi-entry is reachable — the config flow sets `unique_id` from the gateway MAC, so two UDMs are two entries — and a bare id let one entry's repair overwrite the other's. The `translation_key` stays bare, so the user-visible text is unchanged.
- **WAN weight writes are read back**, returning one of three distinct outcomes. **Unverified is not failed**: a read-back that could not be taken says nothing about whether the write landed, so it is logged as a warning rather than an error that would send the user chasing a change that already applied.
- **`_DebouncedWriteEntity`** factors the debounce-and-flush machinery shared by the two number entities.

### Verified

- `pytest tests/` — **676 passed**, 0 failed (624 before; 55 new tests across five files, 3 superseded ones removed).
- `ruff check`, `ruff format --check` and `mypy --strict` all clean.

## [1.0.1-dev11] - 2026-08-08 - Green Suite: Device-Registry Test Shape; Ruff Clean

Phase 0 of the August 2026 update plan (`.notes/info/updates_202608/status_plan.md` §M) — the red suite and the lint baseline. Every coverage and branch figure in that document was measured from a failing run, so nothing else in the plan was trustworthy until this landed.

### Fixed

- **Three failing `test_cleanup.py` tests, one fault — and the fault was in the tests.** `plan_device_cleanup` reaches the device registry through the `_compat` shims, which on HA 2026.8+ use `async_get_device_by_identifier` and `DeviceEntry.config_entry_id`. The tests stubbed only the &le;2026.7 surfaces (`async_get_device`, `DeviceEntry.config_entries`), so the unstubbed 2026.8 lookup was answered by a bare `MagicMock` whose `config_entry_id` never matched the entry — the device was found but judged un-owned, and `CleanupPlan.device_ids` came back empty. Two new local helpers make the mocks version-agnostic: `_make_device()` sets **both** ownership attributes and `_make_dev_reg()` stubs **both** lookup methods. `cleanup.py` is unchanged — there was no product defect.

### Changed

- **`coordinator._cancel_scheduled_refresh` is now public `cancel_scheduled_refresh`.** It is handed to `entry.async_on_unload` from `__init__.py`, which made the `SLF001` private-access error a correct report about a naming mistake rather than noise to suppress. No `noqa`, and no project-local `pyproject.toml` edit (a sync would erase one).
- **Two `PERF401` loops in `_compute_integration_health`** replaced with a list comprehension and an `extend()` generator.

### Verified

- `pytest tests/` — **624 passed**, 0 failed (was 3 failed / 621 passed).
- Coverage **100% line** across all 17 modules, 2832 statements, 0 missing — the 5 previously-missing statements were all in `cleanup.py` and were the red suite, exactly as predicted.
- `ruff check` **All checks passed** (was 3 errors); `ruff format --check` clean; `mypy --strict` **Success, 17 source files**.

## [1.0.1-dev9] - 2026-08-07 - Readme Automation Corrections; Formats

### Changed

- **Formats**: Formats and Lints for previous dev8
- **README**: Corrected Automation Examples in `README.md` , several used `sensor.unifi_network_system_polling_interval`instead of `number.`.

## [1.0.1-dev8] - 2026-08-07 - CI Bumps; Github Zipfile; PyTest Branch & Mutation Testing

### Bumps

- **Shared CI**: Bump `.github` Shared CI Validation via SHA from v2.0.7 to v2.0.10
- **Validate Bump**: Update `ruff` from 0.15.22 to 0.16.1
- **Validate Bump**: Update `zizmor` from 1.25.2 to 1.28.0
- **Validate Bump**: Bumped PHACC `pytest-homeassistant-custom-component` from 0.13.348 to 0.13.354

### Changed

- **`release.yaml`**: Along with `.github`shared CI v2.0.10, added `release.yaml`to auto create and attached a zipfile to each new release, for download tracking purposes.
- **`hacs.json`:** Updated to add `filename:`and `zip_release: true`fields, for zipfile use, for download tracking.
- **PyTest Branch Coverage:** Added branch coverage to existing PyTest line coverage measurement. Added via shared sync `tasks.json`.
- **`mutmut`:** Added `mutmut` via shared Dockerfile base image for Mutation Testing. Added task to `tasks.json`via shared sync.
- **`ruff`Rules:** Updated `ruff`rules, via shared CI to match latest HA exclusions and inclusions.
- **Shared Sync Do Not Edit**: Added comments to several of the shared sync files to clarify they were shared and not to be edited locally.
- **AGENTS No git:** Updated `AGENTS.md` to clarify strict restrictive rules around write git use.
- **US UK Spelling**: Updated spelling to US standard (z vs s, color vs colour etc), to match HA standard.
- **Tools not Dev Tools**: Changed References to "Developer Tools" to "Tools" to align with HA 2026.8+
- **`changelog_local` ToC**: Added Table of Contents to `changelog_local` (top-of-file) and to end of `CHANGELOG`.

## [1.0.1-dev7] - 2026-07-28 - Automation Example Glitch Guards & Float Rounding in README

Reinforced example automations in `README.md` to prevent false triggers during controller disconnects, network glitches, or entity unavailability, and rounded numeric outputs.

### Changed

- **`README.md` Example Automations Glitch Protection**:
  - **`Internet Down` & `WAN Failover`**: Added `not_from: ["unknown", "unavailable"]` state trigger filters to ensure controller reconnects or startup transitions do not fire false outage/failover alerts.
  - **`High WAN Data Usage`**: Applied `| float(0) | round(0)` formatting to monthly usage rendering in notification messages to prevent raw 8+ decimal place floats.
  - **`Slow Speedtest`**: Applied `| float(0) | round(0)` formatting to verified speedtest download results.

---

## [1.0.1-dev6] - 2026-07-27 - Device-Registry Record Split

**No code changed.** `.notes/device_registry/device_model_2026_08.md` has been split: the family-wide analysis moves to `.shared/issues/device_registry_2026_08.md`, and this project's file keeps its own history.

### Changed

- **`device_model_2026_08.md` trimmed from 233 to ~140 lines.** Retained: Phase 1's MAC-drop reasoning (specific to co-existing with core `unifi`), the "what deliberately does not change — core-`unifi` awareness" section, the implementation record, the validation record (617 tests, 2026-07-22), and Phase 2 (#1414) tracking. Replaced with pointers: the three deprecated APIs, the feature-detection pattern, the no-floor argument, what users experience across an HA upgrade, and the 2026.8.0 checklist.

  **Split rather than moved wholesale.** About half the file was family analysis and half this project's implementation history. Relocating everything would have made this project's validation record read as family policy; leaving everything put a dated liability where two other projects could not find it.

- **One project-specific correction preserved deliberately.** The original note warned that resolving `via_device_id` would mean threading a registry handle through every builder. It did not — the builders resolve the registry from `coordinator.hass` internally, so no new argument crossed the ~20 entity call sites. That correction stays here rather than in the shared record, because it is a fact about this codebase.

- **`AGENTS.md`** — the "full rationale" pointer now names both files, so a reader lands on the family analysis rather than only this project's slice.

### Notes

- **The split found a live gap in a sibling.** `huawei_router_5g` still uses the deprecated `via_device` tuple at two call sites with no compat shim — warnings from HA 2026.8, broken parent links at 2027.8. It had never been checked against this analysis, because the analysis was filed here. Recorded in the shared file as a dated gap; **not scoped**, that project has not been touched.
- **This project remains the reference implementation** — all three shims, the only one with call sites for all three. The shared record notes that `zte_router_5g` implementing two is correct there, not incomplete.
- **Open family action carried into the shared record:** the shims are verified against the HA `dev` branch and mock-patched flags, not a native 2026.8 build. If a signature shifted late in the cycle, `hasattr` flips `True` and the new branch calls something with the wrong arguments — worse than no shim. That checklist now applies to every project holding shims, not just this one.

## [1.0.1-dev5] - 2026-07-27 - Standards Test Coverage Recorded

**No code changed in this project.** `dev_standards` **1.13.0 / 1.14.0** introduce the `**Test:**` tag and a **Standards Test Coverage** matrix; this entry records what that matrix now says about `unifi_network_monitor`, so the gaps are visible here rather than only in the shared standard.

### Notes

Six sections now carry a `**Test:**` tag — tagged only where breaking the standard is **silent** and the check is **exact**. This project's cells:

| §   | What the test must assert                                    | Status         |
| :-- | :----------------------------------------------------------- | :------------- |
| 6   | rounding applied at parse time                               | **PENDING**    |
| 9   | stored secrets never pre-filled into a schema                | **PENDING**    |
| 10  | session-terminating call awaited on unload                   | **PENDING**    |
| 12  | translations + icons reconciled against code / live entities | **PENDING**    |
| 14  | runtime sweep: every published attribute unrecorded          | **UNVERIFIED** |
| 21  | live `store.key` among the keys removal actually deletes     | **UNVERIFIED** |

**None of these is a newly-introduced defect — the behavior is correct in every case. What is missing is the guard.** Specifically:

- **§6** — `_safe_float` (`coordinator.py:389`) rounds to 3 dp correctly. But `test_safe_float_valid` asserts `_safe_float("37.2") == approx(37.2)`, which **passes unchanged if the rounding is deleted**. The standard's tag calls this trap out by name.
- **§10** — `api.logout()` exists and is called on unload; `test_init.py` mocks it and never asserts it was awaited. The sibling project's equivalent assertion was mutation-proved today.
- **§12** — no reconciliation test of any kind. **The highest-value gap in the table**: this is the project where `entity-translations` was recorded DONE across two IQS scans while a live entity had no `strings.json` entry, and where four Alerts sensors shipped with default icons. `zte_router_5g`'s equivalent test was itself found blind on five platforms today and rebuilt — port the **rebuilt** version, not the original.
- **§9** — `config_flow.py` uses `suggested_value` three times, all for rogue-AP ignore lists, **none for credentials**. Checked explicitly while tagging: no defect exists today.
- **§14 / §21** — tests exist but have never been executed (container down), so neither has cleared the §11 mutation bar. `UNVERIFIED`, deliberately not `DONE`.

> [!IMPORTANT]
>
> `UNVERIFIED` in the Standards Test Coverage matrix means "the test exists but has not been shown to fail on a real regression". It is **not** the same as `PARTIAL` in the Section Conformance matrix, which means "implemented, but a bullet unmet". The two tables sit close together and the tokens were deliberately kept distinct.

## [1.0.1-dev4] - 2026-07-27 - §14 Attributes Are Unrecorded by Default

Implements `dev_standards` §14 as revised at **Standard Version 1.12.0**: `_unrecorded_attributes` must cover every key an entity can publish, with no per-attribute judgement and no undocumented exceptions.

> [!IMPORTANT]
>
> **Unvalidated.** This project's devcontainer was not running, so no pytest, mypy or coverage run backs these changes — including the new test file, which has **never been executed**. `ruff format` and `ruff check` were run against this project's own `pyproject.toml` and `.validate/pyproject_common.toml` by copying the files into a running sibling container; both clean. The new test's `MIN_ENTITIES_SWEPT` floor is a guess at this project's fixture richness and may need tuning on first run.

### Fixed

- **`strongest_rogue_rssi` and `threshold` were recorded on every poll.** `UnifiRogueProximityBinarySensor` declared no `_unrecorded_attributes` of its own, inheriting only `{"about"}` from the mixin, so both keys went to the recorder on each state change.

  `strongest_rogue_rssi` is the one that costs something: it is an RSSI that moves every poll. The reasoning was already written down **in this project** — `UnifiGatewaySensor` excludes `rogue_aps` with the comment "the rogue list churns every poll" — but was never carried across to the sensor built on the same data.

- **`application_version`, `application_build` and `device_type` were recorded** on `UnifiGatewaySensor`. Not a decision: the exclusion set was written when the attributes were the bulky ones and was never extended as the attribute set grew. Cheap individually — static values change rarely — but the point of 1.12.0 is that this is exactly the kind of small per-attribute call that drifts, and had drifted in three of four projects.

### Added

- **`tests/test_entity_hygiene.py`** — ported from `zte_router_5g`, where it caught this project's class of defect first. A runtime sweep sets up the integration against a real `hass`, iterates every live entity, and asserts each published attribute key is in that entity's `_unrecorded_attributes`, with an explicit empty `ALLOWED_RECORDED` allow-list.

  It patches `Entity.entity_registry_enabled_default` to `True` so disabled-by-default entities are included. That patch is not decoration: in `zte_router_5g` the sweep was **verified by mutation to be ineffective without it**, and adding it immediately exposed a defect that both a static source scan and the ordinary test suite had missed.

  Three narrower static assertions accompany the sweep as regression guards for the specific misses above.

### Notes

- **This project had no test for recorder hygiene at all** before now, which is why its `_unrecorded_attributes` sets had drifted while `zte_router_5g`'s were caught automatically. §14 1.12.0 now requires the test in every project — the rule is enforced by a test rather than by review precisely because a list that must track a property will not track it.
- The §19 health sensor was **already correct** here: seven published attributes, all seven plus `about` excluded. That was care rather than construction — nothing enforced it until now.

## [1.0.1-dev3] - 2026-07-27 - Cross-Project Alignment

Follows a three-way review of `unifi_network_monitor`, `zte_router_5g` and `wifi_ssid_monitor`, checking that the three meet the shared standards the **same way** rather than merely meeting them. This project was the reference implementation for most of the shared patterns, so the changes here are small — one real documentation defect and two consistency fixes.

### Fixed

- **README Integration Health example referenced two attributes that do not exist.** The automation rendered `last_good_scan` where the coordinator writes **`last_good_update`**, so the template produced an empty value where it promised the time of the last good poll; and the explanatory note listed **`checks_failed`**, which this integration has never published (that was `wifi_ssid_monitor`'s name for the concept). Both corrected, and the note now lists the attributes actually available: `severity`, `degraded_capabilities`, `last_good_update`, `drift`, `auth_mode`, `v3_available`. Found by diffing the README against the coordinator during the cross-project review — copy-pasting the example previously gave a silently incomplete notification.

### Changed

- **Three hardcoded `consecutive_failures <= 3` comparisons replaced with `FETCH_STRIKE_LIMIT`.** The constant already existed in `const.py` and was already used in six other places — these three sites simply predated it, leaving the §8 threshold defined in one place and asserted in four. No behavior change; the value is unchanged at 3. `zte_router_5g` has been aligned onto this same name and placement.
- **`tests/test_integration_health_outage.py` renamed to `tests/test_integration_health.py`**, and **`tests/test_diagnostics_redaction.py` renamed to `tests/test_diagnostics_sanitization.py`**. New convention across all three projects: name the test file after the **standard** it covers, not the platform or the symptom. The diagnostics rename is more than cosmetic — `dev_standards` §20 exists precisely to distinguish sanitization from redaction, so the old filename named the approach the standard rejects, and anyone opening it would have expected to find `TO_REDACT` assertions.

### Notes

- **This project remains the reference for the shared device-registry work.** `_compat.py` was ported to `zte_router_5g` this week (minus `owning_entry_ids`, which that integration has no call site for); `.notes/device_registry/device_model_2026_08.md` stays the single rationale document for all projects.
- No source behavior changed in this entry — the fixes are a documentation correction and a constant substitution.

## [1.0.1-dev2] - 2026-07-26 - README Section Moved; Automation Cross-Links

### Changed

- **README**: Moved Control and Actions Section. Added many internal links to the example automations.

## [1.0.1-dev1] - 2026-07-26 - Health Automation Example; AGENTS Restructured; Bumps

### Changed

- **README**: Added an example automation to README to cover the INtegration Health problem sensor. Also standardized formatting of html tags.
- **AGENTS**: Rewrite of AGENTS.md to move content shared across projects to a shared file, and to move sensor entity counts to using `docs/all_sensors.md`as the definitive source.

### Bumps

- **Shared CI**: Bump `.github` Shared CI Validation via SHA from v2.0.6 to v2.0.7
- **Validate Bump**: Update `ruff` from 0.15.21 to 0.15.22
- **Validate Bump**: Update `codespell` from 2.42 to 2.43
- **Validate Bump**: Bumped PHACC `pytest-homeassistant-custom-component` from 0.13.347 to 0.13.348

---

## [1.0.0] - 2026-07-22 - Initial Public Release

### Summary

- This is the initial public release of UniFi Network Monitor a Home Assistant integration to connect to your **Ubiquiti UniFi Network** via your UniFi Gateway (e.g. UDM Pro or similar). It is designed to run in conjunction with and be complementary to the official Home Assistant UniFi Network Integration, but it does not require it.

- The focus is on providing information that the core integration does not, such as: Internet **data usage**, **Speedtest** data, WAN latency and IP address, **Rogue Access Point** insights and summary stats, and UniFi system-log **alerts**.

- It works in single or dual WAN mode. In dual WAN mode, it provides per WAN (WAN1, WAN2) info for Internet data usage; Speedtest results; latency; IP addresses and load-balancing status, and if set, balance-weight, plus the ability to change load balancing weight.

- This integration does not provide any client tracking (i.e. device trackers) beyond summary counts, as that is handled by the core Integration.

- This is **the right integration for you** if you run a UniFi Network on a UDM Gateway and want:
  - **Internet Data usage** - Daily and monthly download, upload and totals (per WAN if in dual WAN mode).

  - **Speedtest tracking** - per-WAN download/upload/ping history, plus one-click manual runs.

  - **Rogue AP Info** - rogue access-point detection with a configurable proximity alert, band / ignore-list filtering, and an on-demand query action.

  - **Alerts** - UniFi system-log alerts (High / Very High), with an event and a query action for automations.

  - **Load Balancing** - Failover and load-balancing status, load-balancing weights and weight setting.

  - **WAN Stats** - Per WAN latency, status, assigned name, internal and external IP address and uptime.

  - **Gateway diagnostics** - OS and Application version, last backup, and storage use.

### Changed

- **Initial Public Release**: First release on GitHub

---

### Format

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Entry structure — headers, titles, category headings and the split between this file and its counterpart — follows `.shared/dev_std/changelog_format.md`.
