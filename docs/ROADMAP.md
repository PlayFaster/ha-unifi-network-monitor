# Roadmap: UniFi Network Monitor

A Home Assistant custom integration for Ubiquiti UniFi networks anchored by a UDM Pro, distributed via HACS. It polls the controller's classic and v3 APIs and publishes sensors, binary sensors, buttons, numbers, switches and a select across seven sub-devices, plus optional per-AP and per-switch entities. The feature set is broadly complete; what remains is verification work, two feature ideas, and a handful of decisions worth recording so they are not re-argued.

**Membership of Done is by provenance** — an item qualifies only if it was on this roadmap and was subsequently built. Features that shipped without ever appearing here do not belong in it, however significant. The group was empty when this document was created on 2026-08-08 and gained its first three entries the same day, as the August 2026 update cycle met them.

**Reviewed 2026-08-08**, and again after the August cycle closed at `[1.1.0]`, against `AGENTS.md`, `docs/DEVELOPMENT.md`, the August 2026 update plan (`.notes/info/updates_202608/status_plan.md`), and the four Phase 0 review reports.

---

## Done

### `about` note coverage across the entity set

_Original roadmap item, met 2026-08-08 (`[1.0.1-dev17]`, extended at `[1.1.0]`)._

Raised from 23 declared notes to **46 source-declared / 48 live**, and the distribution problem is what was actually fixed: Internet went from **1 note across 41 entities** to 18. Deliberate omissions are recorded rather than left to read as neglect. The final five came from the live instance and were all non-sensor platforms — the two speedtest buttons, two binary sensors and a select — which a sensor-focused pass had missed.

### Mutation testing, starting from a measured module list

_Original roadmap item, met 2026-08-08 (`[1.0.1-dev19]`)._

`.validate/mutmut_modules.txt` decided by measurement — `diagnostics.py`, `helpers.py`, `alerts.py`, `sensor.py`; everything else excluded with a written reason. Three runs, ending at **840 killed / 205 survived of 1045, 0 timeouts**.

It found what coverage could not. Five boundary and arithmetic gaps in the projection code, and 87 survivors in `diagnostics.py` with a single cause: the tests asserted the output carried **no secret** and never that it carried the **right token**, which a skipped or nulled scrub satisfies. Every remaining survivor carries a written verdict in `.notes/issues/testing_deeper/mutation_equivalents.md`.

One triage rule was corrected in the process and now sits in the shared guide: dict-key mutants are snapshot noise only when the key is **written**. A mutated key that is **read** makes the guard falsy and skips the branch, leaving the real value in the output.

### §20 Diagnostics verification against a populated capture

_Original roadmap item, met 2026-08-08 (`[1.0.1-dev22]`). Was **Blocked**; the owner supplied the capture._

Graded against a real capture carrying 95 gateway keys, 20 devices, 5 rogue-history entries and a live alert block — the populated data the item was blocked on. The whole file was scanned rather than the source read: **0 raw MACs and 0 private IPs**, keys and device names tokenized, `bssid` redacted, the alert `DEVICE` block reduced to its `gateway` label, `CONSOLE_NAME` blanked, and the alert **free text** scrubbed inline.

That last one is the part source-reading cannot confirm, and it is why this item existed: reasoning from source produced a false clean verdict here twice.

---

## To Be Done

### Prior-cycle blending for the Projected Usage sensors

`helpers.project_cycle_usage()` already accepts a `prior_rate` and blends it into the _unobserved remainder_ of the cycle, so the prior's influence decays structurally as the month runs. Nothing supplies it: `coordinator.build_usage_projection()` passes `None`, and the one-day denominator floor carries the early-cycle bound alone.

Supplying it means persisting the previous calendar month's total — a third `Store`, or a new key in the existing usage-watermark store. The gain is confined to the first few days of a month, which is exactly when the projection is least trustworthy and most likely to be looked at.

- **Value:** ⭐⭐
- **Effort:** Medium

---

## Maybe

### Formal child devices (HA architecture discussion #1414)

Re-parent the seven sub-devices and the per-AP/switch devices onto HA's formal child-device mechanism, replacing the current `via_device` / `via_device_id` linking that `_compat.via_device_link()` feature-detects.

**What would justify it:** the mechanism landing in a released HA with a documented API. It is tracked in `.notes/device_registry/device_model_2026_08.md` as Phase 2 and has been unshipped since 2026-07 for one reason — the discussion has not resolved, and building against an unsettled API is how a no-floor integration acquires a floor.

- **Value:** ⭐⭐
- **Effort:** Medium

### A `problem` binary sensor for guard-band suppression

One binary sensor, `on` when any numeric sensor is currently returning `None` because its value fell outside its guard band.

Today that suppression is invisible: the sensor reads `unknown` and nothing distinguishes "the controller sent an impossible value" from "there is genuinely no value yet". The Integration Health sensor covers endpoint staleness and schema drift but not band rejection.

**What would justify it:** evidence that band rejection actually happens in service. It has never been observed on this rig, and a sensor that is always `off` is worse than nothing.

- **Value:** ⭐
- **Effort:** Low

---

## Blocked

### Cross-model verification beyond the UDM Pro

Confirm the gateway parse against gateway models other than the UDM Pro. Detection is signature-first and `GATEWAY_MODELS` lists 27 codes; the parser is tested on variant payloads (v1.1.0-dev12).

- **UCG Ultra (`UDRULT`), read paths verified** from one user download on issue #23 (v1.1.0, Network 10.6.106): gateway selected by WAN signature with one candidate, all 18 endpoints answered, WAN1 data and port name (`eth4`) parsed, single-WAN WAN2 fields `None`, CPU temperature parsed and board temperature absent, WAN1 speedtest mapped. The same download exposed the combined month total failing on a single WAN (`.notes/tasks/wan_calc_month_total_none.md`).
- **Not verified:** any other model, such as UDR, UXG, UCG Max or Cloud Gateway Fiber; and the write paths (speedtest buttons, WAN weights, alert and rogue actions) on any model but the UDM Pro.

**Blocked by:** no way to generate downloads from other models. The project has one gateway, and evidence from another model arrives only when a user posts a diagnostics download, which since v1.1.0 carries the gateway, endpoint and route records needed to check the parse.

- **Value:** ⭐⭐⭐
- **Effort:** Low per model, once a download arrives.

---

## Revisit

### `PARALLEL_UPDATES = 1` on the number platform

**Not doing it. `0` is correct on all six platforms.**

**Detail.** The decision was reached by tracing each write path rather than by quoting the house rule about read-only entities, and the trace is recorded in `docs/DEVELOPMENT.md`. The speedtest button is safe at `0` because a duplicate `cmd/devmgr` speedtest command is rejected or queued by the controller and corrupts nothing. The load-balance number is a more interesting case — its WAN1 + WAN2 = 100 invariant is held across two separate PUTs — but the entity already serializes itself by cancelling its previous debounce task, so `1` would change nothing. The genuine hazard there was that the cancel landed _between_ the two writes, and it was fixed by shielding the pair, not by capping concurrency.

**What would reopen it:** a new write path that does **not** serialize itself — a service call, or a control without a debounce, that issues a multi-step write against the same object.

### The AP satisfaction-score guard band

**Not admitting UniFi's `-1`. The floor stays at `0`.**

**Detail.** `-1` is an _indicator_ that the score has not been computed yet, not a measurement. Admitting it would put a non-percentage value on a percentage sensor, where it would chart, average and enter long-term statistics as though an AP had scored below zero. A floor of `0` turns the sentinel into `unknown`, which is the correct answer to "what is the score?" when there is not one. `docs/value_min_max.md` previously argued the opposite and has been corrected — the code was always right.

**What would reopen it:** UniFi giving `-1` a second meaning, such as a real negative score. Unlikely, and it would be visible as scores clustering at exactly `-1` on APs that have been up for days.

---

## Declined

### Merging devices with the core `unifi` integration

**Not doing it. Monitor owns its own device tree.**

**Detail.** Devices are identity-only — `identifiers={(DOMAIN, …)}` with deliberately no `connections={(CONNECTION_NETWORK_MAC, …)}` — so they never collide with core UniFi's. Merging depended on the shared MAC connection, which HA 2026.8 no longer honours; keeping it would have produced two different behaviors across the 2026.8 line (merged on ≤2026.7, split on 2026.8+). Dropping it gives one no-merge model on every version with **no minimum-version floor**, which is worth more than the shared device card.

Monitor stays core-**aware** at the entity level, which is the part that actually mattered: when core `unifi` is installed, sensors that duplicate what it already provides are created but disabled by default. So the redundancy is avoided without sharing a device.

### Automatic cleanup of orphaned entities on an options change

**Not doing it. Cleanup is explicit-only.**

**Detail.** Unchecking a sensor group leaves its entities behind as orphans, and removing them automatically would make a reconfigure destructive. Someone narrowing the scope to debug a poll would lose entity history and any automation referencing them, with no undo. Removal is therefore driven by the **Clean Up Unused Entities** button or the `cleanup_unused_entities` action, which defaults to `dry_run: true` and returns a report before anything is deleted.

### An upper guard band on accumulating counters

**Not doing it. Byte totals are bounded below at `0` and have no ceiling.**

**Detail.** A ceiling on a total is a data-loss bug, not a safety net: the first time real usage crossed the invented number the sensor would go `unknown` and stay there for the remainder of the cycle. The static sweep in `tests/test_standards_guards.py` asserts the _absence_ of a `max_limit` on every `TOTAL_INCREASING` sensor, so this decision is enforced rather than merely recorded. The upper-bound requirement is scoped to percentages, which are the only quantity here with a real ceiling.

### Renaming entities that repeat their sub-device word

**Not doing it. All nine are keeps.**

**Detail.** Nine entities restate their sub-device in their name, so the full entity name, which Home Assistant builds from the device name and the entity name, repeats the word. The list is the complete scan, taken on 2026-10-12 across the 141 translated entity names against the six sub-device labels in `helpers.py` `build_sub_device_info`, and re-checked against source on 2026-10-15.

| Entity key | Platform | Sub-device | Name |
| :-- | :-- | :-- | :-- |
| `health_www_latency` | Sensor | Internet | Internet Latency |
| `health_www_drops` | Sensor | Internet | Internet Drops |
| `health_www_boot_time` | Sensor | Internet | Internet Online Since |
| `health_www_uptime` | Sensor | Internet | Internet Uptime Duration |
| `gateway_internet` | Binary sensor | Internet | Internet Connected |
| `health_www_ok` | Binary sensor | Internet | Internet OK |
| `health_vpn_status` | Sensor | Status | VPN Status |
| `gateway_wifi_ssid_status` | Binary sensor | Status | WiFi Status |
| `gateway_vpn_tunnel_status` | Binary sensor | Status | VPN Tunnel Status |

Home Assistant never renames an existing `entity_id`, so a rename benefits only a new install, while an automation or dashboard that references the current friendly name breaks without warning. `huawei_router_5g` and `zte_router_5g` kept theirs for the same reason. The convention applies to new entities from here on. Recorded against cross-project chore `C-030`, whose requirement is the scan and the recorded keeps, not a rename.

---

## Summary

Forward work only, ordered by Value.

| Item | Group | Value | Effort |
| :-- | :-- | :-- | :-- |
| Cross-model verification beyond the UDM Pro | Blocked | ⭐⭐⭐ | Low per model, once a download arrives |
| Prior-cycle blending for the Projected Usage sensors | To Be Done | ⭐⭐ | Medium |
| Formal child devices (#1414) | Maybe | ⭐⭐ | Medium |
| A `problem` binary sensor for guard-band suppression | Maybe | ⭐ | Low |

Three items left this table on 2026-08-08 and are now in **Done** — `about` note coverage, mutation testing, and the §20 diagnostics verification that had been the highest-value entry here. Only one blocked item remains, and nothing is queued behind it.

---

## Version Control

| Version | Date | Change |
| :-- | :-- | :-- |
| v1.1.3 | 2026-10-15 | Declined records the nine entity names that repeat their sub-device word as keeps (`C-030`); no entity is renamed. |
| v1.1.2 | 2026-10-15 | Cross-model verification entry records the UCG Ultra read paths verified from the issue #23 download, and names what is not verified; it stays **Blocked**, with the blocker restated as having no way to generate downloads from other models. |
| v1.1.1 | 2026-10-12 | Cross-model verification entry rewritten for the `1.1.0-dev12` signature-first gateway detection and the 27-code model list; it stays **Blocked** on having one gateway. |
| v1.1.0 | 2026-08-08 | **First three items met, and the Done group opened.** The August 2026 update cycle closed at `[1.1.0]`, meeting `about` note coverage (23 → 46 declared / 48 live, with the Internet distribution problem fixed at 1 → 18), mutation testing (module list decided by measurement; three runs ending 840 killed / 205 survived of 1045), and the **§20 diagnostics verification**, which moved out of **Blocked** when the owner supplied a populated capture — 0 raw MACs and 0 private IPs across the whole file, with the alert free text scrubbed inline. Removed a stale precondition from the mutation entry: it warned that the project had no `setup.cfg`, which stopped being true when the module list was written. The summary table drops to four forward items, one of them blocked. |
| v1.0.0 | 2026-08-08 | Initial, per `roadmap_format.md` v1.2.0. Records three forward items, two Maybes with stated triggers, two Blocked items with the obstacle named and the note that nothing is queued behind the diagnostics one, two Revisit decisions with observable reopening triggers, and three Declines. **No Done group**, because membership there is by provenance and this is the first roadmap this project has had — the group will populate as the items above are met rather than being backfilled from the changelog. Created as item 27 of the August 2026 update plan. |
