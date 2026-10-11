# Internal Detailed Changelog: UniFi Network Monitor

All changes to this project will be documented in this file. This is the detailed changelog, to include non user facing changes and intra-release changes.

> [!IMPORTANT]>
>
> ## Authoring Rules for AI Agents & Maintainers (`changelog_format.md`)
>
> 1. **Header Titles (`CF-101`)**: Must be direct, technical noun phrases in the format `Subsystem: Action and Outcome`.
>    - **Banned**: Narrative riddles, poetic titles, full sentences, or literary abstractions ("Establishment", "Overhaul", "A Dead Field", "Advent").
> 2. **Bullet Points (`CF-202`)**: Lead with bold outcome/verdict first (`- **[Subject/Verdict]**: [concrete technical explanation]`).
>    - **Banned**: Conversational storytelling, journey narration ("We noticed...", "After looking into..."), or burying the fix at the end.
> 3. **Voice & Register**: Direct, objective systems engineering prose (US spelling).
> 4. **Granular Bumps Invariance**: Dependency updates must use individual bullets (`- **Validate Bump**: Update <pkg> from <v1> to <v2>`). Never collapse or summarize multiple bumps into one prose sentence.
> 5. **Standard Headings Only (`CF-201`)**: Open with `### Summary`, then use only: Added, Changed, Fixed, Removed, Security, Deprecated, Bumps, Tests, Verified, Notes, Documentation, Deferred, Declined, Known, Records. Never invent synonyms.

---

- [Internal Detailed Changelog: UniFi Network Monitor](#internal-detailed-changelog-unifi-network-monitor)
  - [\[1.1.0-dev10\] - 2026-10-11 - Shared Tooling Sync: HA Core isort Adopted; Probatio Script Import and Mypy Overrides; Doc Wording Changed](#110-dev10---2026-10-11---shared-tooling-sync-ha-core-isort-adopted-probatio-script-import-and-mypy-overrides-doc-wording-changed)
  - [\[1.1.0-dev9\] - 2026-09-23 - AGENTS.md: Guard Test Table Trimmed; Rationale Moved to docs/test\_guards.md](#110-dev9---2026-09-23---agentsmd-guard-test-table-trimmed-rationale-moved-to-docstest_guardsmd)
  - [\[1.1.0-dev8\] - 2026-09-23 - Breaking: Minimum Home Assistant Raised to 2025.2.0 for Python 3.13](#110-dev8---2026-09-23---breaking-minimum-home-assistant-raised-to-202520-for-python-313)
  - [\[1.1.0-dev7\] - 2026-09-08 - Documentation: Project Complexity \& Health Scorecard Added](#110-dev7---2026-09-08---documentation-project-complexity--health-scorecard-added)
  - [\[1.1.0-dev6\] - 2026-08-26 - Linting: McCabe Complexity Rule (C901) \& Temporary Suppressions](#110-dev6---2026-08-26---linting-mccabe-complexity-rule-c901--temporary-suppressions)
  - [\[1.1.0-dev5\] - 2026-08-26 - Documentation: Comprehensive Changelog Readability and Header Standardization](#110-dev5---2026-08-26---documentation-comprehensive-changelog-readability-and-header-standardization)
  - [\[1.1.0-dev4\] - 2026-08-24 - Notes Queue: `.notes/tasks/` Created; The Topic Folders Sorted](#110-dev4---2026-08-24---notes-queue-notestasks-created-the-topic-folders-sorted)
  - [\[1.1.0-dev3\] - 2026-08-14 - Tooling Bumps: Zizmor, MyPy, JSONSchema, and PHACC](#110-dev3---2026-08-14---tooling-bumps-zizmor-mypy-jsonschema-and-phacc)
  - [\[1.0.1-dev22\] - 2026-08-08 - Refresh Now Failure Reporting; Diagnostics and About Verified Live](#101-dev22---2026-08-08---refresh-now-failure-reporting-diagnostics-and-about-verified-live)
  - [\[1.0.1-dev21\] - 2026-08-08 - Code Review: Refresh Now Failure Reporting Finding and Architecture Audit](#101-dev21---2026-08-08---code-review-refresh-now-failure-reporting-finding-and-architecture-audit)
  - [\[1.0.1-dev20\] - 2026-08-08 - Boundary Test Coverage: Alert Truncation, Device-Parse Guards, and Rogue Sorting](#101-dev20---2026-08-08---boundary-test-coverage-alert-truncation-device-parse-guards-and-rogue-sorting)
  - [\[1.0.1-dev19\] - 2026-08-08 - Mutation Testing: Diagnostics Token Scrubbing Assertions](#101-dev19---2026-08-08---mutation-testing-diagnostics-token-scrubbing-assertions)
  - [\[1.0.1-dev18\] - 2026-08-08 - Zero Partial Branches: Five Unreachable Guards Removed](#101-dev18---2026-08-08---zero-partial-branches-five-unreachable-guards-removed)
  - [\[1.0.1-dev17\] - 2026-08-08 - Documentation: Internet Group Sensor About Attributes Coverage Expansion](#101-dev17---2026-08-08---documentation-internet-group-sensor-about-attributes-coverage-expansion)
  - [\[1.0.1-dev16\] - 2026-08-08 - Documentation: Write-Classification Register and Roadmap Reconciliation](#101-dev16---2026-08-08---documentation-write-classification-register-and-roadmap-reconciliation)
  - [\[1.0.1-dev15\] - 2026-08-08 - Branch Coverage Complete: Sixteen of Seventeen Modules at 100%](#101-dev15---2026-08-08---branch-coverage-complete-sixteen-of-seventeen-modules-at-100)
  - [\[1.0.1-dev14\] - 2026-08-08 - Branch Coverage: Fifteen of Seventeen Modules at 100%](#101-dev14---2026-08-08---branch-coverage-fifteen-of-seventeen-modules-at-100)
  - [\[1.0.1-dev13\] - 2026-08-08 - Standards Sweeps and Translation Reconciliation; Zero-Assertion Tests Fix](#101-dev13---2026-08-08---standards-sweeps-and-translation-reconciliation-zero-assertion-tests-fix)
  - [\[1.0.1-dev12\] - 2026-08-08 - WAN Weight Write Hardening and Projected Data Usage](#101-dev12---2026-08-08---wan-weight-write-hardening-and-projected-data-usage)
  - [\[1.0.1-dev11\] - 2026-08-08 - Test Infrastructure: Device-Registry Mock Helpers and Ruff Clean Baseline](#101-dev11---2026-08-08---test-infrastructure-device-registry-mock-helpers-and-ruff-clean-baseline)
  - [\[1.0.1-dev10\] - 2026-08-08 - Reauth Entry Resolution; README Corrections](#101-dev10---2026-08-08---reauth-entry-resolution-readme-corrections)
  - [\[1.0.1-dev9\] - 2026-08-07 - Documentation: README Automation Examples and Formatting Alignment](#101-dev9---2026-08-07---documentation-readme-automation-examples-and-formatting-alignment)
  - [\[1.0.1-dev8\] - 2026-08-07 - CI and Workflow Tooling Bumps; Branch and Mutation Testing Coverage](#101-dev8---2026-08-07---ci-and-workflow-tooling-bumps-branch-and-mutation-testing-coverage)
  - [\[1.0.1-dev7\] - 2026-07-28 - README Automation Example Glitch Guards and Float Rounding](#101-dev7---2026-07-28---readme-automation-example-glitch-guards-and-float-rounding)
  - [\[1.0.1-dev6\] - 2026-07-27 - Device-Registry Record Split](#101-dev6---2026-07-27---device-registry-record-split)
  - [\[1.0.1-dev5\] - 2026-07-27 - Dev Standards Architectural Invariants Test Coverage Matrix](#101-dev5---2026-07-27---dev-standards-architectural-invariants-test-coverage-matrix)
  - [\[1.0.1-dev4\] - 2026-07-27 - Recorder Hygiene: Unrecorded Attribute Exclusions and Entity Sweep](#101-dev4---2026-07-27---recorder-hygiene-unrecorded-attribute-exclusions-and-entity-sweep)
  - [\[1.0.1-dev3\] - 2026-07-27 - Cross-Project Alignment: Health Attribute Naming and Test Renames](#101-dev3---2026-07-27---cross-project-alignment-health-attribute-naming-and-test-renames)
  - [\[1.0.1-dev2\] - 2026-07-26 - Documentation: README Controls Reorganization and Automation Cross-Links](#101-dev2---2026-07-26---documentation-readme-controls-reorganization-and-automation-cross-links)
  - [\[1.0.1-dev1\] - 2026-07-26 - Documentation and Tooling: Health Automation Example, AGENTS Structure, and CI Bumps](#101-dev1---2026-07-26---documentation-and-tooling-health-automation-example-agents-structure-and-ci-bumps)
  - [\[1.0.0\] - 2026-07-22 - Initial Public Release](#100---2026-07-22---initial-public-release)
  - [Document Audit Status](#document-audit-status)

## [1.1.0-dev10] - 2026-10-11 - Shared Tooling Sync: HA Core isort Adopted; Probatio Script Import and Mypy Overrides; Doc Wording Changed

### Summary

Records the uncommitted changes since `[1.1.0-dev3]` that `[1.1.0-dev4]` to `[1.1.0-dev9]` do not cover. Most arrive through the shared sync and the cross-project items first recorded in ZTE (`3.4.1-dev1`, `3.4.3-dev3`, `3.4.5-dev2`). No entity, option or service changes; one health-attribute string changes.

### Changed

- **Imports re-sorted project-wide**: `ruff check --fix` under the new `[lint.isort]` settings rewrote imports in 11 component modules, `scripts/hardware_check.py` and about 20 test files, as in the Huawei, ZTE and WiFi projects. `[1.1.0-dev6]` records only `test_coordinator.py` and `test_sensor.py`.
- **HA core Ruff rules adopted (`pyproject_common.toml`)**: `C` and `ICN002` added to `select`; `[lint.isort]` with HA core's four settings; `[lint.mccabe] max-complexity = 25`; Google pydocstyle convention; pytest-style parentheses; banned `async_timeout`, `pytz` and `tests` imports; HA core's import-alias table.
- **Python 3.13 declared for uv**: synced `pyproject.toml` gains a `[project]` block with `requires-python = ">=3.13"`.
- **Test imports of shared fixtures allowed**: `TID251` added to the `tests/` per-file ignores.
- **Coverage gate enforced at 100%**: `[tool.coverage.report] fail_under = 100`.
- **Mypy probatio errors suppressed (C-037)**: `voluptuous` treated as untyped (core #182112, probatio); `binary_sensor` and `button` allow implicit re-export (core #182211). Overrides at `pyproject.toml:87` and `:96`. Mypy Strict on 2026-10-11 reports no probatio or device-class errors.
- **Hardware check installs probatio first (C-036)**: `import homeassistant  # noqa: F401` added before the package import in `scripts/hardware_check.py`. Not yet run; the 2026-10-11 run stopped with no config-entry store.
- **Integration Health capability renamed**: `_DRIFT_CAPABILITY["gateway"]` changed from "Gateway telemetry" to "Gateway metrics", visible in the `degraded_capabilities` attribute.
- **Documentent Spelling**: comments in `coordinator.py` and `sensor.py`, README, `DEVELOPMENT.md`, `api_endpoints.md` and `value_min_max.md`; "behaviour" and "behavioural" changed to US spelling (C-028, partial).
- **Prettier excluded from Markdown**: `*.md` override removed from `.prettierrc.json`, the pre-commit hook limited to `json` and `yaml`, and `.prettierignore` added at the project root.
- **Component assets copied into `mutants/`**: `setup.cfg` `also_copy` adds `icons.json`, `strings.json`, `services.yaml`, `quality_scale.yaml` and `translations/` (C-034; mutation run pending).
- **Local tool folders ignored**: `.gitignore` adds `.coverage.*`, `.mdbase/`, `.scratch_*` and `.agents/`.

### Bumps

- **Validate Bump**: Update `ruff` from 0.16.1 to 0.16.10
- **Validate Bump**: Update `pytest-homeassistant-custom-component` from 0.13.355 to 0.13.372
- **Validate Bump**: Update `check-jsonschema` from 0.38.0 to 0.38.2
- **Validate Bump**: Update `mypy` from 2.3.0 to 2.4.0
- **Validate Bump**: Update `zizmor` from 1.29.0 to 1.30.1
- **CI Bump**: Update shared `codeql.yaml` from v2.0.10 (`bd40d66`) to v2.0.17 (`3f917d1`)
- **CI Bump**: Update shared `release.yaml` from v2.0.10 (`bd40d66`) to v2.0.17 (`3f917d1`)
- **CI Bump**: Update shared `validate.yaml` from v2.0.10 (`bd40d66`) to v2.0.17 (`3f917d1`)

### Removed

- **`python-typing-update` pre-commit hook removed**: hook and its `version_matrix.json` row deleted.

### Documentation

- **Monthly-figures source note in README**: under Internet Usage, explains that monthly figures come from the controller, with a Utility Meter helper pointer; Repair-issue wording in Integration Health; minor table wording.
- **Sensor documents regenerated**: `all_sensors.md`, `about_attribute_list.md` and `value_min_max.md` rewritten by `check_sensor_manifest.py --sync-docs`; hand-maintained entity counts removed (manifest: 141 entities).
- **Sensor-manifest sync named in `AGENTS.md`**: the entity-inventory pointer names `--sync-docs` and `--verify-ha`.
- **`docs/ha_compatibility.md` first committed**: per-project ledger maintained by the `update_ha_compatibility` prompt alongside `ha_minimum_version_matrix.md` §3.2; reviewed 2026-09-30, tested against 2026.9.4.
- **Rejected port endpoints recorded**: `DEVELOPMENT.md` records why `stat/portforward` and `rest/portconf` were not used.
- **Public `[1.1.0]` title restated**: `CHANGELOG.md` title rewritten as a noun phrase.

### Known

- `Fix and Validate All` 2026-10-11: 2 tests fail on 2026.10 device-registry deprecations (`devices` as a mapping, `async_get_device`); coverage 99.95%; Mypy 1 error at `services.py:375` (`ChildDeviceEntry`); Repo Links broken `../dev_std/dev_standards.md` in `about_attribute_list.md`; markdownlint MD001/MD051 in this file and MD028 at `AGENTS.md:20`; McCabe 83 and 31 (suppressed, `[1.1.0-dev6]`).
- **C-028 residual British spellings**: `Cancelling` at `coordinator.py:967` and `number.py:107`, `cancelled` at `coordinator.py:970`, `Organisation` at `sensor.py:990` (user-facing `about` text) and `favour` at `_compat.py:67`.

## [1.1.0-dev9] - 2026-09-23 - AGENTS.md: Guard Test Table Trimmed; Rationale Moved to docs/test_guards.md

### Summary

`AGENTS.md` aligned with the updated `agents_md_index.md` specification. The "Tests that will stop you" table is trimmed to one line per row, with each row's rationale moved verbatim to a new `docs/test_guards.md`. Junction paths are no longer written as markdown links, and the Home Assistant compatibility ledger pointer is added. No code or test changes.

### Changed

- **Tests that will stop you**: 14 rows, each `Add or change this | This fails | Do this`; the section shrinks from 875 to 442 words. The heading drops "and why they exist", and the section ends with the instruction to add a new guard's row here and its rationale to `docs/test_guards.md`.
- **Guard tests added to the table**: 3 tests that fail on an ordinary change (adding, changing or removing an entity, action, translation, repair issue, option or write) and were not listed. Their docstrings are recorded as rationale in `docs/test_guards.md`.
- **Junction links**: 7 markdown links to `.shared/` and `.notes/` converted to inline code. `AGENTS.md` is committed to the public repository, where those junctions do not exist, so the links were broken for GitHub readers.
- **Compatibility ledger pointer**: the mandatory block pointing to `docs/ha_compatibility.md` added after the entity inventory pointer.
- **Duplicated rule removed**: the `translation_key` / `_attr_has_entity_name` line under Architecture restated `agent_conventions.md` §4, which the Key Patterns section already points to.

### Added

- **`docs/test_guards.md`**: rationale for every guard test in the table, in two sections: the former rationale column copied verbatim, and the docstrings of the tests added to the table.

### Notes

- **Source**: `agents_md_align` run of 2026-09-23 (`shared/SharedNotes/prompts/prompt_run_logs/agents_md_align/agents_md_align_20260923_1638.md`).

## [1.1.0-dev8] - 2026-09-23 - Breaking: Minimum Home Assistant Raised to 2025.2.0 for Python 3.13

### Summary

The minimum supported Home Assistant version rises from 2024.11.0 to 2025.2.0. Home Assistant 2025.2.0 is the first release that requires Python 3.13, so this change makes Python 3.13 the minimum runtime. No integration code changes.

### Changed, breaking

- **Minimum Home Assistant version**: `hacs.json` `homeassistant` raised from `2024.11.0` to `2025.2.0`. HACS treats this key as the minimum required Home Assistant version, so installations on earlier releases are not offered this version.
- **README requirements**: minimum Home Assistant `2025.2`, minimum Python `3.13+`.

### Documentation

- **`docs/ha_compatibility.md`**: Minimum, Enforced-by and Python rows updated to 2025.2.0 and Python 3.13; the planned-floor milestone removed.

### Notes

- **Rationale**: the previous floor implied Python 3.12 (Home Assistant 2024.6 to 2025.1), which was verified by compilation only. Tests run on Python 3.14, Ruff targets `py313`, and `pyproject.toml` declares `requires-python >=3.13`. The new floor makes the declared, linted and packaged Python minimums agree.
- **Impact**: Home Assistant public analytics (2026-09-23, 687,049 opted-in installations) place 4.6% of installations below 2025.2.0.
- **Functional floor unchanged**: the features the code depends on predate 2025.2.0, and `_compat.py` is unaffected because its branches detect 2026.8 device-registry features. The cross-project rationale is in `ha_minimum_version_matrix.md` §6 and §7.5.

## [1.1.0-dev7] - 2026-09-08 - Documentation: Project Complexity & Health Scorecard Added

### Added

- **`docs/project_complexity.md` architectural health scorecard**: Added a tracked project scorecard documenting current structural complexity metrics, including PlayFaster Health Index score, unmasked McCabe cyclomatic complexity ($V(G)$), routine statement length distributions, module sizes, entity platform declarative efficiency, test surface, and code suppressions.

---

## [1.1.0-dev6] - 2026-08-26 - Linting: McCabe Complexity Rule (C901) & Temporary Suppressions

### Summary

Adopted Home Assistant Core's McCabe cyclomatic complexity linting rule (`C901` with `max-complexity = 25`) across shared configurations. Added targeted temporary `# noqa: C901` suppressions to UniFi's monolithic coordinator update loop and diagnostic sanitization function while architectural refactoring is tracked under cross-project queue item `mccabe_complexity_reduction.md`.

### Changed

- **Temporary Complexity Suppressions**: Added `# noqa: C901` directives to `_async_update_data` in `coordinator.py` (complexity 83) and `async_get_config_entry_diagnostics` in `diagnostics.py` (complexity 31). These functions manage multi-endpoint data fetching and diagnostic redaction for gateways, APs, switches, clients, and traffic, which require dedicated structural decomposition into sub-device helper routines.
- **Import Ordering & Syntax Cleanups**: Formatted test imports in `tests/test_coordinator.py` and `tests/test_sensor.py` to satisfy `I001`.

## [1.1.0-dev5] - 2026-08-26 - Documentation: Comprehensive Changelog Readability and Header Standardization

### Summary

Documentation pass across `docs/changelog_local.md`. Standardized section headers into scannable 3–10 word noun phrases, added opening `### Summary` orientation blocks to all historical entries, and rebuilt the Table of Contents anchor links.

Documentation only. No code, no tests, no entity changes.

### Changed

- **Standardized Section Headers**: Replaced narrative/sentence titles with factual noun phrases matching `changelog_format.md` v1.2.0.
- **Added Lead-In Summaries**: Wrapped existing opening context into explicit `### Summary` blocks across all entries to establish an immediate high-level abstract for readers coming in cold.
- **Synchronized Table of Contents**: Rebuilt TOC links to ensure exact alignment with updated headers.

## [1.1.0-dev4] - 2026-08-24 - Notes Queue: `.notes/tasks/` Created; The Topic Folders Sorted

### Summary

Reorganized `.notes/` task queue into the standardized `tasks/` structure and archived legacy topic folders.

Documentation only. `tasks_folder_migrate` run against this project — over **every** `.notes/` subfolder, not the usual two.

### Changed

- **This project files by topic, not into `issues/`.** `issues/` held one entry, and that one is a folder a shared prompt writes to. The plans were in `setup_options/` (16 documents), `device_registry/` and `info/`. Running the prompt's usual `issues/` then `info/` passes would have reported the project clean while leaving seventeen documents unexamined; the prompt now enumerates every subfolder.
- **Nineteen entries classified:** 19 to `tasks/closed/`, 1 to `info/`, 3 left where they were — `issues/testing_deeper/`, `brand_icon_options/` which holds only images, and two reference notes. `check_queue_format.py --project ha-unifi-network-monitor` reports `PASSED`, and there are **no open local tasks**.
- **`setup_options/` archived as a unit.** The initial planning series, delivered: `const.py` carries five `CONF_ENABLE_*` group flags plus `CONF_ENABLE_DUAL_WAN`, `config_flow.py` carries `SECTION_SENSOR_GROUPS`, `cleanup.py` exists, the alerts sensors and `EVENT_NEW_ROGUE_AP` / `get_rogue_aps` are in place, `integration_health` is in `binary_sensor.py`, and the README lists the Security sub-device.
- **`.notes/proj_structure.md` corrected.** It named `setup_options/` and `device_registry/` as live folders and described `issues/` as the issue tracker. `tasks/` and `issues/` are now described as they are, and the two emptied folders are gone from the table.
- **`device_model_2026_08.md` moved to `info/`.** Phase 1 is implemented and validated; Phase 2 is owned by `docs/ROADMAP.md`'s "Formal child devices (#1414)" and by the cross-project `child_devices_2026_09.md`, so the note is design detail rather than a task. `device_registry/` is now empty.

### Fixed — stale records

- **`updates_202608/status_plan.md` contradicted itself.** Its header records the August plan as executed in `[1.0.1-dev11]`–`[1.0.1-dev18]`; its §M table still read "red suite: **Not started**" and "Phases 1–5: **Not started**". The closure stamp records which half is right and why.
- **The cross-project `test_quality_metrics.md` carried this project as outstanding on all three measures.** All three closed on 2026-08-08 and nothing was written back: `[1.0.1-dev11]` fixed the three failing `test_cleanup.py` tests — **the fault was in the tests, not `cleanup.py`**, the opposite of what that file's §4 assumed — `[1.0.1-dev13]` took zero-assertion tests to 0 of 687, and `[1.0.1-dev18]` reached 100% branch coverage with 0 partials at 811 tests. The rows and §4 are corrected there.
- **Three live pointers to `.notes/device_registry/`** in the cross-project queue were repointed at `info/`. Dated records citing the old path — changelog entries and a 2026-08-08 sensor review — were left alone.

## [1.1.0-dev3] - 2026-08-14 - Tooling Bumps: Zizmor, MyPy, JSONSchema, and PHACC

### Summary

Maintenance updates for development dependencies and shared CI tools.

### Bumps

- **Validate Bump**: Update `zizmor` from 1.28.0 to 1.29.0
- **Validate Bump**: Update `mypy` from 2.1.0 to 2.3.0
- **Validate Bump**: Update `check-jsonschema` from 0.37.4 to 0.38.0
- **Validate Bump**: Bumped PHACC `pytest-homeassistant-custom-component` from 0.13.354 to 0.13.355

## [1.0.1-dev22] - 2026-08-08 - Refresh Now Failure Reporting; Diagnostics and About Verified Live

### Summary

Closes the three items the phased work had parked or deferred. Two of them needed the live instance and the owner supplied access; the third was the code review's only finding.

### Fixed

- **Refresh Now now tells the caller when it failed** (`button.py`, `coordinator.py`). The Phase 7 finding: `async_press` awaited the **debounced** `async_request_refresh`, which records failure on `last_update_success` but does not propagate it — so the button could not raise, and an automation pressing it reported success even when the gateway was unreachable. `SpeedtestButton` two entities away already raised.

  Adds `async_force_refresh_now`, a non-debounced variant, so the outcome is known when the call returns; the button reads `last_update_success` and raises `HomeAssistantError` with a new `refresh_failed` translation key.

  **`_force_refresh_once` still consumed on attempt, not on success** — deliberate. Consuming on success re-arms the pause bypass until a fetch works, which turns a paused integration into a polling one for as long as the gateway stays down. The un-surfaced failure was the defect; the consumption rule was not.

### Added

- **Three tests**, taking the suite to **842**. Two cover the button (non-debounced path taken, raises on failure) and one covers `async_force_refresh_now` through its public surface. Plus **the first direct assertion of the §13 pause-bypass itself** — Refresh Now overriding Pause Polling had no test at all, despite being the named regression this family has shipped twice. It also asserts the bypass is genuinely one-shot.

- **Five `About` entries in `docs/all_sensors.md`**, filled from live text: the WAN1/WAN2 speedtest buttons, the Integration Health and Rogue AP Proximity binary sensors, and the Rogue Detection Period select.

### Notes

- **§20 Diagnostics closed — verified against a real, populated capture**, not by reading code. This module held `diagnostics: done` across two IQS scans while leaking real identifiers, so source-reading was not acceptable evidence. The capture carried 95 gateway keys, 20 devices, 5 rogue-history entries and a live alert block. Scanning the whole file found **0 raw MACs and 0 private IPs**; identifiers are tokenised or redacted on every surface, and the alert **free text** is scrubbed inline — the path that cannot be confirmed from source.

- **The live `About` reconciliation needed the source key mapping, not string matching.** Live carries 48 against the doc's 46. Three naive comparisons in a row produced artefacts, because the doc's Key column holds `translation_key` (`gateway_board_temp`) while `unique_id` holds `key` (`board_temp`) — comparing them directly is vacuous. Mapped properly, the arithmetic closes: 46 − 3 disabled entities that cannot appear live = 43 overlap, + 5 undocumented = 48. The five were all non-sensor platforms, which is why a sensor-focused column had missed them.

## [1.0.1-dev21] - 2026-08-08 - Code Review: Refresh Now Failure Reporting Finding and Architecture Audit

### Summary

Phase 7 code review of the integration codebase. Found one medium design inconsistency in Refresh Now failure reporting; verified fifteen security and architecture checks clean.

Phase 7 of the August 2026 plan — `code_review`, run last with Phases 0–6 supplied as established preconditions so it did not re-derive them. **No code changed.** Report at `.notes/code_review/code_review_20260808_2010.md`.

**Zero Critical, zero High, one Medium, zero Low.** Quiet because it is the seventh pass over the same code in two days and the six before it did the finding.

### Notes

- **The finding — Refresh Now cannot report failure to an automation** (`button.py:94-96`). `async_force_refresh` awaits `async_request_refresh`, Home Assistant's **debounced** refresh, which records failure on `last_update_success` and does not propagate it to the caller. So `async_press` cannot raise, and a script or automation pressing the button always reports success even when the refresh failed. `SpeedtestButton` two entities away does re-raise `HomeAssistantError`; the inconsistency inside one file is what makes this a finding rather than a design choice.

  **The named `dev_standards` §13 regression is not present** — Refresh Now correctly overrides Pause Polling, which is exactly what `_force_refresh_once` is for.

  **Parked rather than applied**, in §P of the status plan: it changes behavior on a user-facing control, needs a new translation key, and carries a real trade-off over whether the one-shot flag should be consumed on attempt or on success.

- **Fifteen checks came back clean and are recorded as such** — the useful half of a result like this. Among them: no bare-tuple `except`, no `or 0 >` precedence bug, no blocking I/O in async, no bare `asyncio.create_task`, no direct `hass.data` mutation, no unguarded `coordinator.data[...]`, and both masked-error classes clean in `api.py`, where every broad `except Exception` re-raises as a typed domain exception.

- **The data-volume unit defect cannot exist here.** Every volume sensor declares `native_unit_of_measurement=BYTES` and carries raw bytes, leaving the conversion to HA — there is not a single manual divisor (`1024**3` or `1_000_000_000`) anywhere in the codebase.

- **Two greps would have become false findings.** `services.py` contains zero occurrences of `HomeAssistantError` but raises `ServiceValidationError`, its subclass, on every invalid path; and five service schemas declare `device_id`, which here really is a device-registry UUID resolved through the registry. Both are recorded in the report so the next review does not raise them.

- **Method stated in the report deliberately:** pattern-driven analysis across all 17 source files, not a verbatim read of 26,000 lines. Every mechanical pattern in categories 1–7 and the masked-errors companion was scanned and each hit read in context. A review that claims a full read it did not perform is worse than one that states its method.

## [1.0.1-dev20] - 2026-08-08 - Boundary Test Coverage: Alert Truncation, Device-Parse Guards, and Rogue Sorting

### Summary

Phase 6 boundary testing review and test harness expansion. Added alert truncation, device-parse exception coverage, 24-hour rogue window edge tests, and rogue-AP attribute ordering assertions.

Phase 6 of the August 2026 plan — `testing_deeper_lev1_review` then `lev1_implement`. Run after mutation, as that prompt requires: both hunt boundary gaps, and mutation finds them mechanically. **Five findings, none requiring a source change** — every one was a test gap, and no source defect was found.

Both mandated syntax checks are clean across all 17 source files: zero bare-tuple `except A, B:` and zero `except A or B:`.

### Added

- **`alert_title` boundary and substitution tests** (`tests/test_alerts.py`, 5 new).

  Two findings, one function. The truncation guard `len(title) > ALERT_TITLE_MAX` was only ever tested at 9 and 260 characters — far below and far above — and **mutation had already proved the gap**: `alert_title__mutmut_17` relaxed `>` to `>=` and survived. The trap is that the obvious assertion cannot catch it either, because under the mutant a 255-character title becomes 254 characters plus an ellipsis, which is **still 255 long**. Only equality with the input distinguishes them, so that is what the new tests assert.

  Separately, `test_alert_title_with_params` was named for a behavior it never checked: it asserted length and ellipsis only, both of which hold if `{device}` is left as a literal placeholder or the parameters dict is dropped entirely. **Six of the eight surviving `alert_title` mutants were parameter-dropping variants.** The substitution assertions now live in their own tests with a title short enough that truncation cannot hide the result — the reason they could never have worked in the original.

- **Five-type exception coverage for the device-parse guard** (`tests/test_coordinator_branches.py`, 1 parametrised over 5).

  Eight identical `except (AttributeError, KeyError, TypeError, ValueError, IndexError)` handlers guard the parse blocks in `_async_update_data`. The suite raised exactly one of the five, so narrowing any tuple to `except ValueError:` would have passed every test. Branch coverage could not see it: it records that the handler was entered, not which types can enter it. The stake is blast radius — these guards exist so one malformed device is skipped with a warning, and losing one lets the exception escape `_async_update_data` and fail the whole update, taking every entity unavailable over a single bad record.

- **The 24-hour rogue window tested at 24 hours** (`tests/test_coordinator.py`, 1 new). `rogue_new_24h` compares `first > cutoff`; the existing test used 2 hours and 3 days, so nothing distinguished `>` from `>=` or would have noticed the window width changing. Now pinned to the microsecond either side of the edge.

- **The rogue-AP attribute cap, flag and ordering** (`tests/test_sensor.py`, 2 new). `rogue_aps_truncated` had **zero occurrences in the entire test suite** and `ROGUE_ATTR_MAX` zero test references, leaving the cap, the flag and the sort order all unverified. Ordering mattered most: the attribute publishes 25 of a possibly much larger set, so an inverted `signal` key would have quietly exposed the 25 **weakest** rogue APs while still being the right length and still flagging truncation correctly. Input is built weakest-first so a sort that does nothing also fails.

### Notes

- **Two of the five findings were in modules mutation cannot reach.** `coordinator.py` and `sensor.py` are excluded from the mutation module list because their tests mock the API and the coordinator, so no mutation run will ever surface a gap in them. That is the argument for running both passes rather than treating mutation as sufficient.
- **No mutation re-run was made for this entry.** `cache_invalidation_files = tests/*.py` means these test additions discard all 1045 verdicts, so confirming the two mutation-visible kills costs a full run. Recorded as owed rather than performed — see the recommendations file's Implementation Notes for the expected delta.
- Analysis report: `.notes/issues/testing_deeper/recommendations_20260808.md`.

## [1.0.1-dev19] - 2026-08-08 - Mutation Testing: Diagnostics Token Scrubbing Assertions

### Summary

Mutation testing analysis on `diagnostics.py`. Added 12 mutation-targeted tests verifying exact token sequence and redaction substitution, eliminating 79 surviving mutants.

### Added

- **`tests/test_diagnostics_mutation.py` — 12 tests**, taking the suite to **825 passing** at 100% line and 100% branch coverage, 0 partials.

  These come from the mutation run, which put **87 surviving mutants** in `diagnostics.py` — the largest cluster in the project. Reading them found one cause, not 87:

  > the diagnostics tests asserted that the output carried **no secret**, and never that it carried the **right token**.

  `assert "entry" in result` and `assert x == "**REDACTED**"` are satisfied by a scrub that is skipped, nulled, or written to the wrong key — because `None` contains no MAC either. It is the same defect the projection tests had at `[1.0.1-dev18]`, in different clothes: asserting an answer is _plausible_ rather than _right_.

  What the new tests pin, by exact value: the token sequence (`device-1`, `device-2`, `rogue-1`, stable on reuse); longest-first substitution, where one identifier is nested inside another; a literal of **exactly** the minimum length; the `_learn` type guard; full-record equality for `_scrub_device`; the alert `DEVICE` and blank-block branches; a fully populated capture asserted token by token; and a device known by two MACs.

### Fixed

- **A device alert block naming a public IP was relying on a branch nothing tested.**

  `_scrub_alert_block` ends with a shape-based backstop that pushes every remaining string through `text()`, which matches MACs and **private** ranges. Every existing test used `192.168.x.x`, so the backstop covered for the explicit `ip` branch and the two were indistinguishable. A routable address is removed **only** by the explicit branch. The new test uses one.

  No behavior changed — the branch was correct. What changed is that it is now load-bearing in the suite rather than shadowed by a wider net.

### Changed

- **Read-side dict-key mutants are no longer triaged as noise.** The shared guidance retires string and dict-key mutants as snapshot noise at roughly a third of survivors. That holds for a key being **written**, where the mutation renames an output field and exposes nothing. On a scrubber it inverts: `out.get("XXipXX")` makes the branch fall through and the **real value survives into the output**. Around 34 of the 46 mutants in `async_get_config_entry_diagnostics` are read-side; only ~12 are cosmetic renames, and those die for free, because indexing `result["coordinator"]["integration_health"]` raises `KeyError` when the key moves.

- **`.notes/issues/testing_deeper/mutation_equivalents.md` populated — with three entries and no more.** 284 mutants survived the run and the overwhelming majority are **killable but not worth killing**, which is a different verdict. Only `_is_mac`'s empty-string default and the two `boot_times` pass-1 mutants are genuinely unkillable, each recorded with the reason stated as behavior.

  The last two are also a code observation: if pass 1's `boot_times` loop cannot change the output, those four lines are redundant. **Deliberately not refactored** — deleting code to satisfy a mutation score is how a real guard gets removed. Left for the Phase 6 review.

### Verified

- `pytest tests/` — **825 passed**, 0 failed. **100% line and 100% branch**: 2939 statements, 0 missing, 864 branches, **0 partial**.
- `ruff check .` and `ruff format --check .` clean across 68 files. `mypy custom_components/` clean at 17 files, standard and strict.

  **Scope note, because this was got wrong during the phase.** A verification pass ran `mypy custom_components/ tests`, reported 155 errors and parked it as a gap. `tests` is not in the project's command and never was: `.vscode/tasks.json` and `.pre-commit-config.yaml` both scope mypy to `custom_components/`, matching Home Assistant core, whose pre-commit pins mypy to `^(homeassistant|pylint)/` while naming `tests/` explicitly for `ruff-format`. **Ruff covers tests; mypy does not, deliberately.** The parked row was withdrawn.

### Notes

- Mutation, three runs. The second confirmed the `[1.0.1-dev18]` projection work at **761 killed / 284 survived** — exactly `+5 killed / −5 survived` against the first, by count rather than by inference. The third verified this entry's work at **840 killed / 205 survived of 1045, 0 timeouts**: **+79 kills from 12 tests**.
- **`diagnostics.py`: 87 survivors → 8**, and all 8 were triaged and written up _before_ the verifying run — three equivalents and five killable-but-not-worth-killing. No unexplained residue.
- **The §14 / §21 Standards Test Coverage cells stay `UNVERIFIED`.** Both rest on `sensor.py`, whose 45+ survivors are all mocked-coordinator mutants and therefore evidence about the harness, not the behavior. Clearing them on a run that could not have tested them would repeat the exact error this phase exists to catch.

## [1.0.1-dev18] - 2026-08-08 - Zero Partial Branches: Five Unreachable Guards Removed

### Summary

Cleaned up five unreachable branches in `coordinator.py`, reaching 100% branch coverage with 0 partial branches across all 17 integration modules.

### Removed

- **Five unreachable branches in `coordinator.py`**, taking the project to **100% branch coverage with 0 partials** across all 17 modules.

  Four were `isinstance(x, list)` checks on the wlanconf, networkconf, VPN-tunnel and firewall-policy payloads. They can never be false. Every one of those values reaches the parse block from `_fetch_optional`, which ends with `data = list(await method())` and returns a held **list** on its failure path; when a feature toggle is off, `_skip_fetch` substitutes and returns `[]`; and the `asyncio.gather` has **no** `return_exceptions`, so it never puts an exception object in the tuple where a list is expected. Three independent producers, all lists.

  The fifth was `elif len(sorted_speedtest) == 1:`, which required a list of length zero — impossible inside the enclosing `if speedtest_raw:`. It becomes a plain `else` with the reasoning stated in a comment.

  **Why remove rather than keep.** They cost nothing at runtime, but they were unreachable code that told the next reader a non-list payload was a real case worth handling, and they left five permanent partials — which meant "partials must be zero" could never be an enforceable rule, and an unenforceable rule is how the next genuine gap hides. The safety they appeared to provide is now held by `test_every_optional_fetch_returns_a_list_whatever_the_api_returns`, which fails the moment normalisation stops — earlier and louder than a dead `if` ever would.

### Changed

- **`AGENTS.md` gains a zero-partials row** in the "Tests that will stop you" table. The bar is now zero, so a partial is a signal rather than noise, and an unreachable branch should be deleted rather than left to erode the number.

### Verified

- `pytest tests/` — **811 passed**, 0 failed. **100% line and 100% branch**: 2939 statements, 0 missing, 864 branches, **0 partial**.
- `ruff check`, `ruff format --check`, `mypy --strict`, prettier, markdownlint and codespell all clean.

## [1.0.1-dev17] - 2026-08-08 - Documentation: Internet Group Sensor About Attributes Coverage Expansion

### Summary

Added 23 new unrecorded `about:` guidance notes to entity descriptions, focusing primarily on the Internet and WAN sensor groups.

Phase 4 of the August 2026 update plan. No behavior changes — `about:` is an unrecorded attribute, so it never reaches the recorder however often a state changes.

### Added

- **23 new `about:` notes**, taking the description-level count from 15 to 38 and the total across every platform from 23 to 46. The **Internet** group was the target and goes from 3 of 35 to **18 of 35**: it holds the WAN availability, latency and usage metrics that a note earns most on, and it had one. Speedtest goes 0 → 4, Status 2 → 4, System 0 → 2.

  The notes chosen answer questions the entity name does not. WAN1 Latency is an average over UniFi's own monitoring window while Internet Latency is measured per poll, and mistaking one for the other produces automations that watch the wrong signal. Local and Public IP legitimately differ on a CGNAT connection. ISP Organisation shows a wholesaler where ISP Name shows the reseller, which reads as a bug. The monthly and daily totals are clamped to a running maximum because UniFi recomputes the open bucket each poll — the most surprising behavior in this integration, and invisible from the value. And every Speedtest figure is exactly as old as its Last Run, with nothing on the sensor to say so.

### Changed

- **`docs/all_sensors.md`: the `About` column is populated** (46 entities), regenerated from source across all six platform modules and matching both `about=` on a description and `_attr_about` on a class.
- **The deliberate omissions are recorded** rather than left as gaps. A note on all 130 entities would train users to ignore notes, so four categories are stated with reasons: WAN2 twins of an annotated WAN1 sensor (identical meaning — except Availability and Latency, which are annotated because those two are what get read during a failover); self-describing counts; the download/upload halves of an annotated total; and binary sensors whose name is already the question. Gateway remains at 1 of 17 by choice and is named as the next candidate in `docs/ROADMAP.md`.

### Verified

- `pytest tests/` — **811 passed**, 0 failed. Coverage unchanged at 100% line / 99% branch. `ruff`, `ruff format`, `mypy --strict`, prettier, markdownlint and codespell all clean.
- **Not done:** the column is source-derived, not refreshed from the live instance. That final step of the item is parked — see the plan's §P.

## [1.0.1-dev16] - 2026-08-08 - Documentation: Write-Classification Register and Roadmap Reconciliation

### Summary

Phase 3 documentation reconciliation. Created `docs/ROADMAP.md`, implemented the §22 write-classification register and hardware verification scripts, and documented 34 numeric guard bands.

Phase 3 of the August 2026 update plan — every documentation change in one release, so prettier, markdownlint, codespell and the link check run once over the lot instead of after each edit.

### Added

- **`docs/ROADMAP.md`**, per `roadmap_format.md` v1.2.0. Three To Be Done items, two Maybes with the trigger that would justify each, two Blocked items with the obstacle named, two Revisit decisions with observable reopening triggers, and three Declines. **No Done group** — membership there is by provenance, and this is the project's first roadmap, so the group will populate as items are met rather than being backfilled from the changelog.
- **`scripts/write_classification.py`** — the §22 register. `trigger_speedtest` is `SAFE`; `update_networkconf` is `ATTENDED` because it changes which link the household's traffic uses and a script cannot judge whether that recovered. `NEVER_AUTOMATED` is defined and deliberately empty.
- **`scripts/hardware_check.py`** — exercises the one `SAFE` write against a real gateway. It confirms the command is accepted **and then waits for a new result to land**, because "the controller took the request" and "the gateway ran a speedtest" are different claims and only the second is worth asserting. The `ATTENDED` write is not offered here at all, not even behind a prompt.
- **`tests/test_write_classification.py`** — nine tests. A new command in `api.py` fails the suite until someone classifies it; a `SAFE` classification fails unless the hardware check really calls it; and the hardware check fails if it ever calls an `ATTENDED` write. The write detector keys on the **endpoint, not the verb**, because this controller answers queries with `POST` — a verb-based detector would report five read methods as writes and produce a register nobody reads.
- **An `About` column in `docs/all_sensors.md`**, marking the 23 entities that declare an unrecorded `about:` note.
- **A "Tests that will stop you" table in `AGENTS.md`** — thirteen rows covering every sweep, what fails, and what to do. Every allow-list named in it is empty by design, so adding to one is a visible act.

### Changed

- **`docs/value_min_max.md`: the AP satisfaction-score decision is applied.** The three score sensors are documented at `min = 0`, and the old rationale — which argued for `-1` and warned that `0` would wrongly suppress newly provisioned APs — is replaced. `-1` is an _indicator_ that the score has not been computed, not a measurement; admitting it would put a non-percentage on a percentage sensor where it would chart, average and enter long-term statistics as though an AP had scored below zero. Suppression is the intended outcome, and `unknown` is the honest answer. **The code was always right; this document was the side that was wrong.**
- **All 34 previously-undocumented guard bands are documented**, in three new sections — Internet & WAN, Speedtest, and Configuration Counts. That is `sensor_review`'s 32 plus the two Projected Usage sensors added at `[1.0.1-dev12]`, which reconciles exactly. `docs/value_min_max.md` now matches the code in both directions with **zero** undocumented bands.
- **`docs/DEVELOPMENT.md` records the `PARALLEL_UPDATES` reasoning**, traced per write path rather than settled by the house rule about read-only entities. `0` is correct on all six platforms — and the exercise is what found the debounce-cancel hazard fixed at `[1.0.1-dev12]`, which a concurrency cap would not have prevented.
- **The API-key menu path in `strings.json` and `translations/en.json`** now matches the README: **UniFi Network → Integrations → Create New API Key**. The setup form previously showed a different path from the documentation, and the form is the one users follow.
- **Section counts in `docs/all_sensors.md`**: Security 19→20, System 9→10 (both stale headers), Internet 39→41 for the Projected Usage sensors. Base total 128→130, with the registered and enabled figures in the mode table moved by +2 and the reason stated inline.
- **README** documents the Projected Usage sensors, including that the confidence attribute is how to judge them and that they deliberately carry no `state_class`.
- **`AGENTS.md`**: forward work now points at `docs/ROADMAP.md` rather than being restated; the stale claim that `validate.yaml` still carries a placeholder `CHANGEME` gist_id is removed (it is populated); and the coverage note is re-verified rather than rewritten — **100% line, 99% branch, 802 tests, 0 statements missing**.

### Notes

- **Standards Test Coverage matrix — four cells move, two stay.** The matrix lives inside the dated `[1.0.1-dev5]` entry and is left as written; this note is the correction.
  - **§10** (session-terminating call awaited on unload) — `PENDING` → **met**. `tests/test_teardown_contract.py` asserts `logout()` is awaited, that the store flush is ordered before it, that a failing logout does not block the unload, and that the platform-unload result is propagated.
  - **§12** (translations + icons reconciled against code) — `PENDING` → **met**. `tests/test_translations_icons.py` reconciles in all three directions against **module source**, plus exception messages in both directions. This was recorded as the highest-value gap in the table.
  - **§14 / §21** — stay `UNVERIFIED`. Their stated reason ("the test exists but has never been executed — container down") is obsolete: both execute and pass, and §21's asserts the live-key comparison rather than the tautology. But `UNVERIFIED` means _not yet shown to fail on a real regression_, which is mutation testing's job, and that run is in progress. , but their stated reason no longer holds.\*\* That reason — "the test exists but has never been executed (container down)" — is obsolete: both tests execute and pass, and §21's asserts the live-key comparison rather than the tautology. The cells are held deliberately until mutation testing shows them failing on a real regression, which is what `UNVERIFIED` means. The historical entry is left as written rather than edited; this note is the correction.
- Two further cells in that matrix are now met by Phase 2 and will be re-graded alongside: **§10** (session-terminating call awaited on unload) and **§12** (translations and icons reconciled against code).

### Verified

- `pytest tests/` — **811 passed**, 0 failed. `ruff check`, `ruff format --check` and `mypy --strict` clean.
- prettier, markdownlint (project config), codespell and the markdown link check all clean across `README.md`, `AGENTS.md` and `docs/`.

## [1.0.1-dev15] - 2026-08-08 - Branch Coverage Complete: Sixteen of Seventeen Modules at 100%

### Summary

Added 34 coordinator branch tests in `test_coordinator_branches.py`, achieving 100% branch coverage across 16 of 17 integration modules.

Phase 2 of the August 2026 update plan, finished. No production behavior changes.

### Added

- **`tests/test_coordinator_branches.py`** (34 tests) takes `coordinator.py` from 26 partial branches to 5, and `__init__.py` to zero. Covers the AP name map's MAC-less record, an unrecognised WAN group, the gateway parse's temperature / storage / zero-size-division / non-WAN-uplink guards, an unknown health subsystem, a cached boot time with no timestamp, site resolution in both the transient and the permanent direction, four speedtest mapping paths, and all five system-log alert branches — including that an alert older than 24 hours is still reported as the most recent one while contributing nothing to the 24-hour count.

### Verified

- `pytest tests/` — **802 passed**, 0 failed. **100% line** (2944 statements, 0 missing), **99% branch**.
- **Partial branches 27 → 5**, with **16 of 17 modules at 100% branch**.
- **All five remaining partials are unreachable, not untested.** Four are `isinstance(x, list)` checks on payloads that `_fetch_optional` has already normalised with `list()` on both its success and its failure path; the fifth needs a speedtest list of length zero, which the enclosing truthiness check prevents. They are left in place pending an owner decision rather than removed, and a new test pins the normalisation guarantee the redundancy rests on — if that ever stops holding, the test fails before the guards become live again.
- Assertion audit **PASSED** (0 of 766); `ruff check`, `ruff format --check` and `mypy --strict` clean.

## [1.0.1-dev14] - 2026-08-08 - Branch Coverage: Fifteen of Seventeen Modules at 100%

### Summary

Added branch coverage suites for diagnostics and non-coordinator platform modules, closing 32 partial branches.

Phase 2 of the August 2026 update plan, continued. No production behavior changes — this is the untaken half of every defensive branch outside the coordinator.

### Added

- **`tests/test_diagnostics_branches.py`** (34 tests) takes `diagnostics.py` from 20 partial branches to **zero**. It was done first on the plan's instruction, and not because it had the most: it is the module whose failure mode is silent, and the one that held `diagnostics: done` across two IQS scans while leaking device MACs, user-assigned names, internal IPs, the subscriber's ISP and third-party SSIDs. Covers the scrubber's empty- and short-identifier guards, every "wrong type where a dict was expected" path, and the backstop that scrubs alert parameter types UniFi has not published yet.
- **`tests/test_platform_branches.py`** clears the remaining partials in `binary_sensor`, `button`, `select`, `switch` and `services`, plus two more in `cleanup`. Both the static setup pass and the dynamic-discovery pass are covered for devices and VPN tunnels.

### Fixed

- **Three diagnostics tests were passing vacuously.** They asserted against the key `rogue_aps` where the module uses `rogue_aps_list`, so they checked that an untouched key was untouched — and passed. Branch coverage is what surfaced it: the partial refused to close. Line coverage could not have shown this.

### Verified

- `pytest tests/` — **768 passed**, 0 failed. **100% line** (2944 statements, 0 missing), **99% branch**.
- **Partial branches 59 → 27**, with 15 of 17 modules at 100% branch. The remaining 26 are all in `coordinator.py` and one in `__init__.py`.
- **Not one branch turned out to be dead code** — 33 of 33 this pass, after 12-of-12 and 11-of-11 on the sibling projects.
- Assertion audit **PASSED** (0 of 735); `ruff check`, `ruff format --check` and `mypy --strict` clean.

## [1.0.1-dev13] - 2026-08-08 - Standards Sweeps and Translation Reconciliation; Zero-Assertion Tests Fix

### Summary

Test baseline overhaul. Added guard-band and translation reconciliation sweeps, enforced zero-assertion fixes, and introduced shared device registry test helpers.

Phase 2 of the August 2026 update plan — the test baseline. No production behavior changes; this release is entirely about what the suite can catch.

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

## [1.0.1-dev12] - 2026-08-08 - WAN Weight Write Hardening and Projected Data Usage

### Summary

Hardened WAN weight write path with fresh network configuration reads and shielded debounce tasks. Scoped repairs per config entry and introduced Projected Usage sensors.

Phase 1 of the August 2026 update plan — the behavior changes. A failing test was written and seen to fail for every item before any source changed.

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

## [1.0.1-dev11] - 2026-08-08 - Test Infrastructure: Device-Registry Mock Helpers and Ruff Clean Baseline

### Summary

Resolved test-side mock mismatches in `test_cleanup.py` across Home Assistant versions and cleared all Ruff lint warnings.

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

## [1.0.1-dev10] - 2026-08-08 - Reauth Entry Resolution; README Corrections

### Summary

Reauth config flow entry resolution aligned with core helpers; updated README speedtest controls and minimum Home Assistant version requirements.

Back-filled 2026-08-08. This work shipped as commit `d5289f2` and the changelog was not updated at the time, leaving the history jumping dev9 → dev11. Recorded here from the commit rather than from memory.

Made in response to `readme_review` `REVIEW_MODE=Full`, whose findings were dispositioned individually — 1a.1 and 1b fixed, 2a.1/2a.2/2a.3/2b.1/2b.2 fixed, **1a.2 rejected** (the README's API-key path is the correct one) and §3 rejected.

### Fixed

- **The stated minimum Home Assistant version was three releases below what the code actually required.** `config_flow.py` enforces 2024.11.0; the README and `hacs.json` said 2024.8.0. Both corrected to **2024.11.0**, so a user on an unsupported version is told before install rather than at setup.

### Changed

- **`async_step_reauth_confirm` now resolves its entry through `self._get_reauth_entry()`**, matching `async_step_reconfigure`'s use of `_get_reconfigure_entry()`. The framework resolves the entry and raises `UnknownEntry` when it is gone, so the four `entry is None` branches were removed — they were reachable only by bypassing the flow manager. `test_config_flow_reauth_confirm_entry_gone` was updated to assert the raise instead of an abort.
- **README**: WAN1/WAN2 Run buttons documented under a new **🚄 Speedtest** control group (2a.2); a line on sending diagnostics from a non-UDM-Pro gateway (2a.3); and **⚙**, **🔏**, **🚄** added to the three control sub-headings, each verified single-codepoint and not already used in a heading (2b.1).

### Notes

- **`readme_review` 2a.4 was disputed and re-verified — the finding stands.** The claim was that a `numeric_state` trigger cannot fire from `unknown` to a value. It can: `condition.py` returns `False` for a non-numeric state rather than raising, which _arms_ the trigger, and the return to an in-range value then fires it. Proved twice — by reading `homeassistant/helpers/condition.py:1565` and by a behavioral test showing `50 → unknown → 50` fires. The premise would have been correct against the older `ConditionError` behavior. Guards were added to the affected examples subsequently.

## [1.0.1-dev9] - 2026-08-07 - Documentation: README Automation Examples and Formatting Alignment

### Summary

Formatting pass and entity domain correction in README automation examples.

### Changed

- **Formats**: Formats and Lints for previous dev8
- **README**: Corrected Automation Examples in `README.md` , several used `sensor.unifi_network_system_polling_interval`instead of `number.`.

## [1.0.1-dev8] - 2026-08-07 - CI and Workflow Tooling Bumps; Branch and Mutation Testing Coverage

### Summary

Shared CI bump to v2.0.10, automated release zip asset generation, and test configuration for branch coverage and mutation testing.

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

## [1.0.1-dev7] - 2026-07-28 - README Automation Example Glitch Guards and Float Rounding

### Summary

Reinforced example automations in `README.md` with trigger state filters and float rounding to prevent false alerts and long decimal outputs.

Reinforced example automations in `README.md` to prevent false triggers during controller disconnects, network glitches, or entity unavailability, and rounded numeric outputs.

### Changed

- **`README.md` Example Automations Glitch Protection**:
  - **`Internet Down` & `WAN Failover`**: Added `not_from: ["unknown", "unavailable"]` state trigger filters to ensure controller reconnects or startup transitions do not fire false outage/failover alerts.
  - **`High WAN Data Usage`**: Applied `| float(0) | round(0)` formatting to monthly usage rendering in notification messages to prevent raw 8+ decimal place floats.
  - **`Slow Speedtest`**: Applied `| float(0) | round(0)` formatting to verified speedtest download results.

---

## [1.0.1-dev6] - 2026-07-27 - Device-Registry Record Split

### Summary

Split device registry documentation between family-wide shared issues analysis and local implementation history.

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

## [1.0.1-dev5] - 2026-07-27 - Dev Standards Architectural Invariants Test Coverage Matrix

### Summary

Recorded Standards Test Coverage baseline against `dev_standards` 1.13.0 / 1.14.0 across six core sections.

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

## [1.0.1-dev4] - 2026-07-27 - Recorder Hygiene: Unrecorded Attribute Exclusions and Entity Sweep

### Summary

Implemented `dev_standards` §14 unrecorded attributes coverage across all entities and ported runtime hygiene test sweep.

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

## [1.0.1-dev3] - 2026-07-27 - Cross-Project Alignment: Health Attribute Naming and Test Renames

### Summary

Aligned health sensor attribute naming and test filenames with sibling integrations and shared standards.

Follows a three-way review of `unifi_network_monitor`, `zte_router_5g` and `wifi_ssid_monitor`, checking that the three meet the shared standards the **same way** rather than merely meeting them. This project was the reference implementation for most of the shared patterns, so the changes here are small — one real documentation defect and two consistency fixes.

### Fixed

- **README Integration Health example referenced two attributes that do not exist.** The automation rendered `last_good_scan` where the coordinator writes **`last_good_update`**, so the template produced an empty value where it promised the time of the last good poll; and the explanatory note listed **`checks_failed`**, which this integration has never published (that was `wifi_ssid_monitor`'s name for the concept). Both corrected, and the note now lists the attributes actually available: `severity`, `degraded_capabilities`, `last_good_update`, `drift`, `auth_mode`, `v3_available`. Found by diffing the README against the coordinator during the cross-project review — copy-pasting the example previously gave a silently incomplete notification.

### Changed

- **Three hardcoded `consecutive_failures <= 3` comparisons replaced with `FETCH_STRIKE_LIMIT`.** The constant already existed in `const.py` and was already used in six other places — these three sites simply predated it, leaving the §8 threshold defined in one place and asserted in four. No behavior change; the value is unchanged at 3. `zte_router_5g` has been aligned onto this same name and placement.
- **`tests/test_integration_health_outage.py` renamed to `tests/test_integration_health.py`**, and **`tests/test_diagnostics_redaction.py` renamed to `tests/test_diagnostics_sanitization.py`**. New convention across all three projects: name the test file after the **standard** it covers, not the platform or the symptom. The diagnostics rename is more than cosmetic — `dev_standards` §20 exists precisely to distinguish sanitization from redaction, so the old filename named the approach the standard rejects, and anyone opening it would have expected to find `TO_REDACT` assertions.

### Notes

- **This project remains the reference for the shared device-registry work.** `_compat.py` was ported to `zte_router_5g` this week (minus `owning_entry_ids`, which that integration has no call site for); `.notes/device_registry/device_model_2026_08.md` stays the single rationale document for all projects.
- No source behavior changed in this entry — the fixes are a documentation correction and a constant substitution.

## [1.0.1-dev2] - 2026-07-26 - Documentation: README Controls Reorganization and Automation Cross-Links

### Summary

Reorganized controls and actions in `README.md` and added cross-links to example automations.

### Changed

- **README**: Moved Control and Actions Section. Added many internal links to the example automations.

## [1.0.1-dev1] - 2026-07-26 - Documentation and Tooling: Health Automation Example, AGENTS Structure, and CI Bumps

### Summary

Added Integration Health automation example to README, restructured AGENTS.md for shared standards, and bumped shared CI tools.

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

---

## Document Audit Status

- **Headers Checked**: Initialized (Pending verification)
- **Bullets Checked**: Initialized (Pending verification)
- **Specification**: Follows `changelog_format.md` (maintainer engineering voice; zero data loss)
