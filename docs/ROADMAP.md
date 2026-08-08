# Roadmap: UniFi Network Monitor

A Home Assistant custom integration for Ubiquiti UniFi networks anchored by a UDM Pro, distributed via HACS. It polls the controller's classic and v3 APIs and publishes sensors, binary sensors, buttons, numbers, switches and a select across seven sub-devices, plus optional per-AP and per-switch entities. The feature set is broadly complete; what remains is verification work, two feature ideas, and a handful of decisions worth recording so they are not re-argued.

**This is the project's first roadmap document.** There is therefore no **Done** group: membership there is by provenance — an item qualifies only if it was on the roadmap and was subsequently built — and nothing has been on this roadmap before today. Features that shipped without ever appearing here do not belong in it, however significant. The group will populate as items below are met.

**Reviewed 2026-08-08** against `AGENTS.md`, `docs/DEVELOPMENT.md`, the August 2026 update plan (`.notes/info/updates_202608/status_plan.md`), and the four Phase 0 review reports.

---

## To Be Done

### `about` note coverage across the entity set

Populate the unrecorded `about:` attribute on more entities. It currently sits at 23 declared notes (26 live, because one class-level note serves two entities) out of 130, and the distribution is the real problem rather than the total: **Internet carries 1 note across 41 entities**, while Security and Alerts — the newest feature areas — are at 12 of 20 and 4 of 4.

Not a sweep. A note on every entity trains users to ignore notes, so the work is to annotate where the answer is genuinely non-obvious — the WAN availability, latency and usage metrics, the Gateway hardware readings, and the Speedtest group — and to **record the deliberate omissions** so a future count does not read as neglect.

- **Value:** ⭐⭐⭐
- **Effort:** Medium

### Mutation testing, starting from a measured module list

Decide `.validate/mutmut_modules.txt` by measurement rather than by guess, then run and triage. `diagnostics.py` is the first candidate on the numbers — 193 statements, 124 branches, and the module whose failure mode is silent.

Two traps are already paid for elsewhere and must not be re-learned: `only_mutate` needs an **indented newline list**, because the comma-separated form silently generates zero mutants and reports success; and `mutants/` must **never** be deleted, since it is both the incremental cache and the results store.

**One live dependency, created by this project on 2026-08-08.** `scripts/` now exists (the write-classification register and hardware check), and `tests/test_write_classification.py` imports from it. mutmut copies only `source_paths` and `tests` into `mutants/`, so the run aborts before it starts unless `also_copy = scripts/` is present. That setting is in the shared workbench template but **this project has no `setup.cfg` yet** — it arrives on the next sync. Confirm it is there first, or the failure looks unrelated to the cause.

- **Value:** ⭐⭐⭐
- **Effort:** High

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

### §20 Diagnostics verification against a populated capture

Grade the diagnostics output against `dev_standards.md` §20 by reading a **regenerated download with the optional data populated** — alerts, threat detections, and secondary hardware present.

**Blocked by:** the absence of such a capture. The rig does not currently produce alerts or detections on demand, and every empty branch in the sanitiser reads as clean whether it is or not.

This is not a theoretical concern on this project specifically. It is the one that held `diagnostics: done` across two full IQS scans while leaking device MACs, user-assigned device names, internal IPs, the subscriber's ISP and third-party SSIDs — and every one of those was found by reading real output, not by reasoning from source. Reasoning from source has produced a false clean verdict here **twice**.

**Nothing is queued behind this.** The outcome would be informative rather than enabling; no other work waits on it.

- **Value:** ⭐⭐⭐⭐
- **Effort:** Low once unblocked — it is a read-and-compare, not a build.

### Cross-model verification beyond the UDM Pro

Confirm the gateway parse against a second gateway model — a UDM SE, UDM Base, UCG-Ultra or UNVR. `GATEWAY_MODELS` lists nine, and exactly one has ever been exercised.

**Blocked by:** having one gateway. Every non-UDM-Pro path in `_parse_gateway` is inferred from the API documentation and from what a UDM Pro returns.

- **Value:** ⭐⭐⭐
- **Effort:** Low once unblocked.

---

## Revisit

### `PARALLEL_UPDATES = 1` on the number platform

**Not doing it. `0` is correct on all six platforms.**

**Detail.** The decision was reached by tracing each write path rather than by quoting the house rule about read-only entities, and the trace is recorded in `docs/DEVELOPMENT.md`. The speedtest button is safe at `0` because a duplicate `cmd/devmgr` speedtest command is rejected or queued by the controller and corrupts nothing. The load-balance number is a more interesting case — its WAN1 + WAN2 = 100 invariant is held across two separate PUTs — but the entity already serialises itself by cancelling its previous debounce task, so `1` would change nothing. The genuine hazard there was that the cancel landed _between_ the two writes, and it was fixed by shielding the pair, not by capping concurrency.

**What would reopen it:** a new write path that does **not** serialise itself — a service call, or a control without a debounce, that issues a multi-step write against the same object.

### The AP satisfaction-score guard band

**Not admitting UniFi's `-1`. The floor stays at `0`.**

**Detail.** `-1` is an _indicator_ that the score has not been computed yet, not a measurement. Admitting it would put a non-percentage value on a percentage sensor, where it would chart, average and enter long-term statistics as though an AP had scored below zero. A floor of `0` turns the sentinel into `unknown`, which is the correct answer to "what is the score?" when there is not one. `docs/value_min_max.md` previously argued the opposite and has been corrected — the code was always right.

**What would reopen it:** UniFi giving `-1` a second meaning, such as a real negative score. Unlikely, and it would be visible as scores clustering at exactly `-1` on APs that have been up for days.

---

## Declined

### Merging devices with the core `unifi` integration

**Not doing it. Monitor owns its own device tree.**

**Detail.** Devices are identity-only — `identifiers={(DOMAIN, …)}` with deliberately no `connections={(CONNECTION_NETWORK_MAC, …)}` — so they never collide with core UniFi's. Merging depended on the shared MAC connection, which HA 2026.8 no longer honours; keeping it would have produced two different behaviours across the 2026.8 line (merged on ≤2026.7, split on 2026.8+). Dropping it gives one no-merge model on every version with **no minimum-version floor**, which is worth more than the shared device card.

Monitor stays core-**aware** at the entity level, which is the part that actually mattered: when core `unifi` is installed, sensors that duplicate what it already provides are created but disabled by default. So the redundancy is avoided without sharing a device.

### Automatic cleanup of orphaned entities on an options change

**Not doing it. Cleanup is explicit-only.**

**Detail.** Unchecking a sensor group leaves its entities behind as orphans, and removing them automatically would make a reconfigure destructive. Someone narrowing the scope to debug a poll would lose entity history and any automation referencing them, with no undo. Removal is therefore driven by the **Clean Up Unused Entities** button or the `cleanup_unused_entities` action, which defaults to `dry_run: true` and returns a report before anything is deleted.

### An upper guard band on accumulating counters

**Not doing it. Byte totals are bounded below at `0` and have no ceiling.**

**Detail.** A ceiling on a total is a data-loss bug, not a safety net: the first time real usage crossed the invented number the sensor would go `unknown` and stay there for the remainder of the cycle. The static sweep in `tests/test_standards_guards.py` asserts the _absence_ of a `max_limit` on every `TOTAL_INCREASING` sensor, so this decision is enforced rather than merely recorded. The upper-bound requirement is scoped to percentages, which are the only quantity here with a real ceiling.

---

## Summary

Forward work only, ordered by Value.

| Item                                                     | Group      | Value    | Effort             |
| :------------------------------------------------------- | :--------- | :------- | :----------------- |
| §20 Diagnostics verification against a populated capture | Blocked    | ⭐⭐⭐⭐ | Low once unblocked |
| `about` note coverage across the entity set              | To Be Done | ⭐⭐⭐   | Medium             |
| Mutation testing, starting from a measured module list   | To Be Done | ⭐⭐⭐   | High               |
| Cross-model verification beyond the UDM Pro              | Blocked    | ⭐⭐⭐   | Low once unblocked |
| Prior-cycle blending for the Projected Usage sensors     | To Be Done | ⭐⭐     | Medium             |
| Formal child devices (#1414)                             | Maybe      | ⭐⭐     | Medium             |
| A `problem` binary sensor for guard-band suppression     | Maybe      | ⭐       | Low                |

---

## Version Control

| Version | Date       | Change                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| :------ | :--------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| v1.0.0  | 2026-08-08 | Initial, per `roadmap_format.md` v1.2.0. Records three forward items, two Maybes with stated triggers, two Blocked items with the obstacle named and the note that nothing is queued behind the diagnostics one, two Revisit decisions with observable reopening triggers, and three Declines. **No Done group**, because membership there is by provenance and this is the first roadmap this project has had — the group will populate as the items above are met rather than being backfilled from the changelog. Created as item 27 of the August 2026 update plan. |
