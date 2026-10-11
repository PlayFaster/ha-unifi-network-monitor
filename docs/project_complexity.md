# Project Complexity & Health: ha-unifi-network-monitor

**Last Measured:** 2026-10-11T16:26:39.128810+00:00 · **Release:** `1.1.0` · **Dev Version:** `1.1.0-dev10`

## 1. Executive Summary

| Metric | Value | Verdict / Evaluation |
| :-- | :-: | :-- |
| **PlayFaster Health Index** | **`33` / 100** | `ACTION REQUIRED` ($\ge 90$ Excellent · $\ge 80$ Good · $\ge 70$ Warning) |
| **Max McCabe Complexity ($V(G)$)** | **83** | `FAIL (>=24)` in `_async_update_data` ($< 20$ Pass · $20–23$ Warn · $\ge 24$ Fail) |
| **Mean Complexity per Routine** | **2.79** | Across 287 routines (Ideal $< 4.0$ per routine) |
| **Danger Routines ($\ge 20$)** | **4** | Zero tolerance (refactor or decompose) |
| **Elevated Routines ($10–19$)** | **3** | Monitor closely; candidate for cleanup |
| **Mean Routine Length** | **15.0 code lines** | Target $\le 15$ code lines ideal |
| **Largest Routine Length** | **796 code lines** | `_async_update_data` in `coordinator.py` (Target $\le 40$ ideal, $> 80$ warn, $> 150$ fail) |
| **Routines > 80 Code Lines** | **5** | Candidate for functional decomposition |
| **Largest Module** | **1,863 code lines** | `coordinator.py` (Warn $> 1,500$ code lines module bloat) |
| **Modules > 1,500 Code Lines** | **2** | Candidate for module decomposition |
| **Code Suppressions (`# noqa`)** | **4** | Zero preferred; review regularly |
| **Type Suppressions (`# type: ignore`)** | **0** | Mypy strict compliance |
| **Source Python SLOC** | **6,803** | Across 17 files in custom_components/ (code statements) |
| **Docstring Volume** | **820 lines** | Interface and contract documentation |
| **Comment Density** | **7.4%** | 501 inline comment lines (Healthy implementation rationale) |
| **Platform Declarations SLOC** | **2,852 lines** | Across 6 platform files |
| **Core Engine / Driver SLOC** | **3,951 lines** | Across 11 coordinator/API/helper files |
| **Static Entities** | **141 entities** | Scale indicator (`all_sensors.md`) |
| **Platform SLOC / Entity** | **20.2 lines/entity** | Target 20 – 45 lines/entity declarative efficiency |
| **Test-to-Source Ratio** | **1.67×** | 11,339 test lines ($\ge 1.5×$ recommended) |
| **Pytest Coverage** | **100%** | 846 tests executed |
| **Pytest Duration** | **154.56s** | Full test suite wall-clock execution time |

## 2. High Complexity Routines ($\ge 10$)

| Score | Routine Symbol | Location | Status |
| :-: | :-- | :-- | :-- |
| **83** | `_async_update_data` | `coordinator.py:1543` | `FAIL (SUPPRESSED)` |
| **31** | `async_get_config_entry_diagnostics` | `diagnostics.py:246` | `FAIL (SUPPRESSED)` |
| **23** | `plan_device_cleanup` | `cleanup.py:88` | `WARN` |
| **20** | `parse_rogue_aps` | `coordinator.py:241` | `WARN` |
| **19** | `async_setup_entry` | `binary_sensor.py:629` | `ELEVATED` |
| **12** | `_fetch_alerts` | `services.py:133` | `ELEVATED` |
| **11** | └─ `_handle_coordinator_update` | `binary_sensor.py:709` | `ELEVATED (nested)` |
| **10** | `_scrub_alert_block` | `diagnostics.py:205` | `ELEVATED` |

## 3. Active Code Suppressions (`custom_components/`)

| Line | Rule Bypassed | File |
| :-: | :-- | :-- |
| 1536 | `BLE001` | `coordinator.py` |
| 1543 | `C901` | `coordinator.py` |
| 1583 | `BLE001` | `coordinator.py` |
| 246 | `C901` | `diagnostics.py` |

## 4. Comment Quality & Density Audits

### 4.1 High Comment Density Files (> 25% comments/code)

| Module | Rationale / Advisory |
| :-- | :-- |
| `const.py` | Inspect for commented-out dead code or procedural narration |

### 4.2 Contiguous Comment Blocks (> 8 lines)

| Location | Length | Advisory |
| :-- | :-: | :-- |
| `const.py:158` | 11 lines | Long procedural block; consider moving architecture notes to docs |
| `diagnostics.py:32` | 9 lines | Long procedural block; consider moving architecture notes to docs |
