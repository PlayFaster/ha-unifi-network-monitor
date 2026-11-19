# Project Complexity & Health: ha-unifi-network-monitor

**Last Measured:** 2026-11-19T18:18:52.487446+00:00 · **Release:** `1.1.2` · **Dev Version:** `1.1.2-dev3`

## 1. Executive Summary

| Metric | Value | Verdict / Evaluation |
| :-- | :-: | :-- |
| **PlayFaster Health Index** | **`29` / 100** | `ACTION REQUIRED` ($\ge 90$ Excellent · $\ge 80$ Good · $\ge 70$ Warning) |
| **Max McCabe Complexity ($V(G)$)** | **87** | `FAIL (>=24)` in `_async_update_data` ($< 20$ Pass · $20–23$ Warn · $\ge 24$ Fail) |
| **Mean Complexity per Routine** | **2.73** | Across 401 routines (Ideal $< 4.0$ per routine) |
| **Danger Routines ($\ge 20$)** | **3** | Zero tolerance (refactor or decompose) |
| **Elevated Routines ($10–19$)** | **7** | Monitor closely; candidate for cleanup |
| **Mean Routine Length** | **14.3 code lines** | Target $\le 15$ code lines ideal |
| **Largest Routine Length** | **805 code lines** | `_async_update_data` in `custom_components/unifi_network_monitor/coordinator.py` (Target $\le 40$ ideal, $> 80$ warn, $> 150$ fail) |
| **Routines > 80 Code Lines** | **6** | Candidate for functional decomposition |
| **Largest Module** | **2,170 code lines** | `coordinator.py` (Warn $> 1,500$ code lines module bloat) |
| **Modules > 1,500 Code Lines** | **2** | Candidate for module decomposition |
| **Code Suppressions (`# noqa`)** | **6** | Zero preferred; review regularly |
| **Type Suppressions (`# type: ignore`)** | **0** | Mypy strict compliance |
| **Source Python SLOC** | **8,516** | Across 20 files in custom_components/ (code statements) |
| **Docstring Volume** | **1,193 lines** | Interface and contract documentation |
| **Comment Density** | **7.9%** | 671 inline comment lines (Healthy implementation rationale) |
| **Platform Declarations SLOC** | **2,892 lines** | Across 6 platform files |
| **Core Engine / Driver SLOC** | **5,624 lines** | Across 14 coordinator/API/helper files |
| **Static Entities** | **141 entities** | Scale indicator (`all_sensors.md`) |
| **Platform SLOC / Entity** | **20.5 lines/entity** | Target 20 – 45 lines/entity declarative efficiency |
| **Test-to-Source Ratio** | **1.84×** | 15,644 test lines ($\ge 1.5×$ recommended) |
| **Pytest Coverage** | **100%** | 1135 tests executed |
| **Test Decision Density** | **0.93 tests/branch** | 1135 tests across 1226 branches (Target $\ge 0.80$ · Strong regression depth) |
| **Assertion Completeness** | **100.0%** | 1045 test functions, 0 unasserted (`test_assertions.txt`) |
| **Dynamic Sequence Depth** | **7 consecutive polls** | Deepest test lifecycle without stubbed seams (`test_depth.txt`) |
| **Pytest Duration** | **870.60s** | Full test suite wall-clock execution time |

## 2. High Complexity Routines ($\ge 10$)

| Score | Routine Symbol | Location | Status |
| :-: | :-- | :-- | :-- |
| **87** | `_async_update_data` | `coordinator.py:1913` | `FAIL (SUPPRESSED)` |
| **23** | `plan_device_cleanup` | `cleanup.py:88` | `WARN` |
| **20** | `parse_rogue_aps` | `coordinator.py:261` | `WARN` |
| **19** | `async_setup_entry` | `binary_sensor.py:644` | `ELEVATED` |
| **18** | `_compute_integration_health` | `coordinator.py:1617` | `ELEVATED` |
| **14** | `_learn_gateway_and_devices` | `diagnostics.py:552` | `ELEVATED` |
| **12** | `_fetch_alerts` | `services.py:133` | `ELEVATED` |
| **11** | `_request` | `api.py:289` | `ELEVATED` |
| **11** | └─ `_handle_coordinator_update` | `binary_sensor.py:724` | `ELEVATED (nested)` |
| **10** | `_scrub_gateway` | `diagnostics.py:639` | `ELEVATED` |
| **10** | `_migrate_registries` | `identity.py:227` | `ELEVATED` |

## 3. Active Code Suppressions (`custom_components/`)

| Line | Rule Bypassed | File |
| :-: | :-- | :-- |
| 1867 | `BLE001` | `coordinator.py` |
| 1913 | `C901` | `coordinator.py` |
| 1957 | `BLE001` | `coordinator.py` |
| 104 | `S104` | `diagnostics.py` |
| 450 | `BLE001` | `diagnostics.py` |
| 218 | `BLE001` | `uptime.py` |

## 4. Comment Quality & Density Audits

### 4.1 High Comment Density Files (> 25% comments/code)

| Module | Rationale / Advisory |
| :-- | :-- |
| `const.py` | Inspect for commented-out dead code or procedural narration |

### 4.2 Contiguous Comment Blocks (> 8 lines)

| Location | Length | Advisory |
| :-- | :-: | :-- |
| `const.py:159` | 11 lines | Long procedural block; consider moving architecture notes to docs |
| `diagnostics.py:73` | 9 lines | Long procedural block; consider moving architecture notes to docs |
