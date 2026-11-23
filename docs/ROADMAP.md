<!-- Generated from task queues by .workbench/generate_roadmap.py. Do not edit by hand. -->
# Roadmap: ha-unifi-network-monitor

A Home Assistant custom integration for Ubiquiti UniFi networks running on a UniFi OS gateway. It polls the controller's classic and v3 APIs and publishes sensors, binary sensors, buttons, numbers, switches and a select across seven sub-devices, plus optional per-AP and per-switch entities. The feature set is broadly complete; what remains is verification work, two feature ideas, and a handful of decisions worth recording so they are not re-argued.

**Membership of Done is by provenance** — an item qualifies only if it was on this roadmap and was subsequently built. Features that shipped without ever appearing here do not belong in it, however significant. The group was empty when this document was created on 2026-08-08 and gained its first three entries the same day, as the August 2026 update cycle met them.

**Reviewed 2026-08-08**, and again after the August cycle closed at `[1.1.0]`, against `AGENTS.md`, `docs/DEVELOPMENT.md`, the August 2026 update plan (`.notes/info/updates_202608/status_plan.md`), and the four Phase 0 review reports.

---

## Declined

### The AP satisfaction-score guard band

Admitting UniFi -1 AP satisfaction scores was declined; percentage sensors keep the 0–100% floor.

**Reason:** 2026-11-19: Admitting UniFi's `-1` AP satisfaction score was declined; percentage sensors maintain the `0–100%` contract and suppress `-1` (no connected clients) to `unknown` (`sensor.py:1340-1370, 1491-1512`).

### Automatic cleanup of orphaned entities on an options change

Automatic silent purging of orphaned entities on options change was declined in favor of explicit user confirmation.

**Reason:** 2026-08-08: Automatic entity cleanup on options reconfiguration was declined; cleanup remains an explicit user action to prevent accidental deletion of historical statistics.

### Merging devices with the core unifi integration

Merging monitor entities into core UniFi integration device entries was declined to preserve clean isolation.

**Reason:** 2026-08-08: Device merging with core UniFi integration was declined to maintain independent lifecycle, clean diagnostics, and prevent cross-integration collisions.

### PARALLEL_UPDATES = 1 on the number platform

Setting PARALLEL_UPDATES = 1 on the number platform was declined; PARALLEL_UPDATES = 0 is already settled across all six platforms.

**Reason:** 2026-11-19: Setting `PARALLEL_UPDATES = 1` on `number.py` was declined; `PARALLEL_UPDATES = 0` is already settled and documented across all six platforms (`C-027`, `docs/DEVELOPMENT.md`), `_DebouncedWriteEntity` (`number.py:102-165`) debounces writes and cancels prior pending tasks, and only one number entity (`wan1_load_balance_weight`) writes to the controller.

### Prior-cycle blending for the Projected Usage sensors

Blending historical monthly cycle usage for projection smoothing was declined to avoid persistent cycle storage.

**Reason:** 2026-10-16: Projected Usage smoothing via historical cycle blending was declined to avoid persistent cycle-history storage and plan reset complexity, matching the decision in ZTE.

### Renaming entities that repeat their sub-device word

Renaming nine entities repeating their sub-device word was declined to prevent breaking existing entity IDs in user dashboards.

**Reason:** 2026-10-15: Renaming nine entities repeating their sub-device word was declined as all nine are keeps under cross-project chore C-030 to prevent breaking user dashboards and automations.

### An upper guard band on accumulating counters

Imposing an upper ceiling guard band on accumulating byte counters was declined because byte counters have no natural ceiling.

**Reason:** 2026-08-08: Upper guard bands on byte counters were declined as accumulating network totals have no valid fixed ceiling and monotonic resets handle roll-over cleanly.
