# Project Complexity & Health: ha-unifi-network-monitor

**Last Measured:** 2026-10-15T14:20:59.243808+00:00 · **Release:** `1.1.1` · **Dev Version:** `1.1.1-dev1`

## 1. Executive Summary

| Metric | Value | Verdict / Evaluation |
| :-- | :-: | :-- |
| **PlayFaster Health Index** | **`33` / 100** | `ACTION REQUIRED` ($\ge 90$ Excellent · $\ge 80$ Good · $\ge 70$ Warning) |
| **Max McCabe Complexity ($V(G)$)** | **88** | `FAIL (>=24)` in `_async_update_data` ($< 20$ Pass · $20–23$ Warn · $\ge 24$ Fail) |
| **Mean Complexity per Routine** | **2.68** | Across 353 routines (Ideal $< 4.0$ per routine) |
| **Danger Routines ($\ge 20$)** | **3** | Zero tolerance (refactor or decompose) |
| **Elevated Routines ($10–19$)** | **5** | Monitor closely; candidate for cleanup |
| **Mean Routine Length** | **14.1 code lines** | Target $\le 15$ code lines ideal |
| **Largest Routine Length** | **849 code lines** | `_async_update_data` in `coordinator.py` (Target $\le 40$ ideal, $> 80$ warn, $> 150$ fail) |
| **Routines > 80 Code Lines** | **4** | Candidate for functional decomposition |
| **Largest Module** | **1,981 code lines** | `coordinator.py` (Warn $> 1,500$ code lines module bloat) |
| **Modules > 1,500 Code Lines** | **2** | Candidate for module decomposition |
| **Code Suppressions (`# noqa`)** | **5** | Zero preferred; review regularly |
| **Type Suppressions (`# type: ignore`)** | **0** | Mypy strict compliance |
| **Source Python SLOC** | **7,657** | Across 19 files in custom_components/ (code statements) |
| **Docstring Volume** | **966 lines** | Interface and contract documentation |
| **Comment Density** | **7.7%** | 590 inline comment lines (Healthy implementation rationale) |
| **Platform Declarations SLOC** | **2,857 lines** | Across 6 platform files |
| **Core Engine / Driver SLOC** | **4,800 lines** | Across 13 coordinator/API/helper files |
| **Static Entities** | **141 entities** | Scale indicator (`all_sensors.md`) |
| **Platform SLOC / Entity** | **20.3 lines/entity** | Target 20 – 45 lines/entity declarative efficiency |
| **Test-to-Source Ratio** | **1.77×** | 13,558 test lines ($\ge 1.5×$ recommended) |
| **Pytest Coverage** | **100%** | 987 tests executed |
| **Pytest Duration** | **271.97s** | Full test suite wall-clock execution time |

## 2. High Complexity Routines ($\ge 10$)

| Score | Routine Symbol | Location | Status |
| :-: | :-- | :-- | :-- |
| **88** | `_async_update_data` | `coordinator.py:1644` | `FAIL (SUPPRESSED)` |
| **23** | `plan_device_cleanup` | `cleanup.py:88` | `WARN` |
| **20** | `parse_rogue_aps` | `coordinator.py:242` | `WARN` |
| **19** | `async_setup_entry` | `binary_sensor.py:629` | `ELEVATED` |
| **14** | `_learn_gateway_and_devices` | `diagnostics.py:556` | `ELEVATED` |
| **12** | `_fetch_alerts` | `services.py:133` | `ELEVATED` |
| **11** | └─ `_handle_coordinator_update` | `binary_sensor.py:709` | `ELEVATED (nested)` |
| **10** | `_scrub_gateway` | `diagnostics.py:643` | `ELEVATED` |
| **10** | `_migrate_registries` | `identity.py:227` | `ELEVATED` |

## 3. Active Code Suppressions (`custom_components/`)

| Line | Rule Bypassed | File |
| :-: | :-- | :-- |
| 1600 | `BLE001` | `coordinator.py` |
| 1644 | `C901` | `coordinator.py` |
| 1686 | `BLE001` | `coordinator.py` |
| 104 | `S104` | `diagnostics.py` |
| 454 | `BLE001` | `diagnostics.py` |

## 4. Comment Quality & Density Audits

### 4.1 High Comment Density Files (> 25% comments/code)

| Module | Rationale / Advisory |
| :-- | :-- |
| `const.py` | Inspect for commented-out dead code or procedural narration |

### 4.2 Contiguous Comment Blocks (> 8 lines)

| Location | Length | Advisory |
| :-- | :-: | :-- |
| `const.py:158` | 11 lines | Long procedural block; consider moving architecture notes to docs |
| `diagnostics.py:73` | 9 lines | Long procedural block; consider moving architecture notes to docs |
