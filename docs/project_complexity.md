# Project Complexity & Health: ha-unifi-network-monitor

**Last Measured:** 2026-11-22T21:30:23.068673+00:00 · **Release:** `1.1.2` · **Dev Version:** `1.1.2-dev6`

## 1. Executive Summary

| Metric | Value | Verdict / Evaluation |
| :-- | :-: | :-- |
| **PlayFaster Health Index** | **`29` / 100** | `ACTION REQUIRED` ($\ge 90$ Excellent · $\ge 80$ Good · $\ge 70$ Warning) |
| **Max McCabe Complexity ($V(G)$)** | **86** | `FAIL (>=24)` in `_async_update_data` ($< 20$ Pass · $20–23$ Warn · $\ge 24$ Fail) |
| **Mean Complexity per Routine** | **2.76** | Across 409 routines (Ideal $< 4.0$ per routine) |
| **Danger Routines ($\ge 20$)** | **3** | Zero tolerance (refactor or decompose) |
| **Elevated Routines ($10–19$)** | **7** | Monitor closely; candidate for cleanup |
| **Mean Routine Length** | **14.3 code lines** | Target $\le 15$ code lines ideal |
| **Largest Routine Length** | **803 code lines** | `_async_update_data` in `custom_components/unifi_network_monitor/coordinator.py` (Target $\le 40$ ideal, $> 80$ warn, $> 150$ fail) |
| **Routines > 80 Code Lines** | **6** | Candidate for functional decomposition |
| **Largest Module** | **2,256 code lines** | `coordinator.py` (Warn $> 1,500$ code lines module bloat) |
| **Modules > 1,500 Code Lines** | **2** | Candidate for module decomposition |
| **Code Suppressions (`# noqa`)** | **6** | Zero preferred; review regularly |
| **Type Suppressions (`# type: ignore`)** | **0** | Mypy strict compliance |
| **Source Python SLOC** | **8,720** | Across 20 files in custom_components/ (code statements) |
| **Docstring Volume** | **1,228 lines** | Interface and contract documentation |
| **Comment Density** | **7.8%** | 682 inline comment lines (Healthy implementation rationale) |
| **Platform Declarations SLOC** | **2,953 lines** | Across 6 platform files |
| **Core Engine / Driver SLOC** | **5,767 lines** | Across 14 coordinator/API/helper files |
| **Static Entities** | **131 entities** | Scale indicator (`all_sensors.md`) |
| **Platform SLOC / Entity** | **22.5 lines/entity** | Target 20 – 45 lines/entity declarative efficiency |
| **Test-to-Source Ratio** | **1.87×** | 16,307 test lines ($\ge 1.5×$ recommended) |
| **Pytest Coverage** | **100%** | 1170 tests executed |
| **Test Decision Density** | **0.92 tests/branch** | 1170 tests across 1276 branches (Target $\ge 0.80$ · Strong regression depth) |
| **Assertion Completeness** | **100.0%** | 1070 test functions, 0 unasserted (`test_assertions.txt`) |
| **Dynamic Sequence Depth** | **7 consecutive polls** | Deepest test lifecycle without stubbed seams (`test_depth.txt`) |
| **Pytest Duration** | **332.96s** | Full test suite wall-clock execution time |

## 2. High Complexity Routines ($\ge 10$)

| Score | Routine Symbol | Location | Status |
| :-: | :-- | :-- | :-- |
| **86** | `_async_update_data` | `coordinator.py:2046` | `FAIL (SUPPRESSED)` |
| **23** | `plan_device_cleanup` | `cleanup.py:103` | `WARN` |
| **20** | `parse_rogue_aps` | `coordinator.py:262` | `WARN` |
| **19** | `async_setup_entry` | `binary_sensor.py:655` | `ELEVATED` |
| **18** | `_compute_integration_health` | `coordinator.py:1750` | `ELEVATED` |
| **14** | `_learn_gateway_and_devices` | `diagnostics.py:569` | `ELEVATED` |
| **12** | `_fetch_alerts` | `services.py:133` | `ELEVATED` |
| **11** | `_request` | `api.py:320` | `ELEVATED` |
| **11** | └─ `_handle_coordinator_update` | `binary_sensor.py:735` | `ELEVATED (nested)` |
| **10** | `_scrub_gateway` | `diagnostics.py:656` | `ELEVATED` |
| **10** | `_migrate_registries` | `identity.py:227` | `ELEVATED` |

## 3. Active Code Suppressions (`custom_components/`)

| Line | Rule Bypassed | File |
| :-: | :-- | :-- |
| 2000 | `BLE001` | `coordinator.py` |
| 2046 | `C901` | `coordinator.py` |
| 2090 | `BLE001` | `coordinator.py` |
| 117 | `S104` | `diagnostics.py` |
| 467 | `BLE001` | `diagnostics.py` |
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
| `diagnostics.py:86` | 9 lines | Long procedural block; consider moving architecture notes to docs |
