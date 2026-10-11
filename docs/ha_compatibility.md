# Home Assistant Compatibility

What Home Assistant versions this integration supports and the status of any changing core APIs.

**Reviewed 2026-09-30.**

> [!IMPORTANT]
>
> **Nothing in this integration requires action before Home Assistant 2027.8.** All version-sensitive Home Assistant APIs are either shimmed with dynamic fallbacks or pass explicit parameters.

---

## Supported versions

| Type | Version / Status | Note |
| :-- | :-- | :-- |
| **Minimum** | **2025.2.0** | Declared in `README.md` |
| **Tested against** | **2026.9.4** | `pytest-homeassistant-custom-component` 0.13.367 (development container) |
| **Enforced by** | `hacs.json` | `"homeassistant": "2025.2.0"` |
| **Functional floor** | `data_entry_flow.section` | Introduced in HA 2024.11 |
| **Python** | 3.13 or later | Required by Home Assistant 2025.2.0. Tests run on Python 3.14 |

---

## Deprecation & compatibility ledger

| API / Feature | Deprecated in | Removed in | Integration Exposure | Status |
| :-- | :-- | :-- | :-- | :-- |
| `DeviceInfo.via_device` identifier tuple | 2026.8 | **2027.8** | Sub-device parent links | **Shimmed** — `_compat.via_device_link()` |
| `async_get_device(identifiers=…)` | 2026.8 | **2027.8** | Device lookups | **Shimmed** — `_compat.device_by_identifier()` |
| `DeviceEntry.config_entries` | 2026.8 | **2027.10** | Device ownership checks | **Shimmed** — `_compat.owning_entry_ids()` |
| Implicit coordinator `config_entry` detection | 2024.8 | **2026.8** | `DataUpdateCoordinator` | **Done** — passed explicitly |
| `BaseTrackerEntity.battery_level` | 2026.6 | **2027.7** | None — no tracker platform | **N/A** |
| `TrackerEntity.location_name` | 2026.6 | **2027.7** | None — no tracker platform | **N/A** |
| `voluptuous` imports | N/A (replaced by probatio in 2026.9) | None announced | Config flow and schemas | **Compatible**: HA aliases `voluptuous` to probatio via `install_as_voluptuous()` |
| Flow and service schema types (probatio) | 2026.10, type hints only | None announced | `voluptuous` imports in the config flow, services and schemas | **Compliant**: runtime is unaffected, and a shared `pyproject.toml` override makes Mypy treat `voluptuous` as untyped. Mypy run pending (C-037). |
| Device-class enums in `const` modules | 2026.10, type hints only | None announced | `BinarySensorDeviceClass` imported from the platform package | **Compliant**: the package re-export still works, and a shared `pyproject.toml` override makes Mypy count it as an export. Mypy run pending (C-037). |

---

## Upcoming milestones

- **Home Assistant 2027.8:** When core removes the legacy `via_device` tuple and `async_get_device` identifier lookups, the corresponding legacy branches in `_compat.py` can be retired. Until then, `_compat.py` provides transparent backward and forward compatibility without raising warnings.
- **Home Assistant 2027.10:** When core removes `DeviceEntry.config_entries` (moved from 2027.8, announced 2026-09-15), the `config_entries` branch of `_compat.owning_entry_ids()` can be retired.
- **Home Assistant 2026.10:** core types flow and service schemas as probatio and moves the device-class enums to `const` modules. This affects type checking only. The two Mypy overrides in the shared `pyproject.toml` are removed when the integration imports probatio directly or the floor passes the move.

---

## Version Control

| Version | Date | Author | Description |
| :-- | :-- | :-- | :-- |
| **v1.0.0** | 2026-08-21 | Antigravity | Initial creation conforming to lean project compatibility format (Option A). |
| **v1.1.0** | 2026-09-23 | Claude | Compatibility audit: tested-against updated to 2026.9.3; `voluptuous` → probatio row added; `DeviceEntry.config_entries` removal moved to 2027.10. |
| **v1.1.1** | 2026-09-23 | Claude | Added Python row to supported versions; recorded the planned 2025.2.0 minimum for the next release. |
| **v1.2.0** | 2026-09-23 | Claude | Minimum raised from 2024.11.0 to 2025.2.0 (Python 3.13); planned-floor milestone removed. |
| **v1.3.0** | 2026-09-30 | Claude | Compatibility audit: tested-against updated to 2026.9.4 (`pytest-homeassistant-custom-component` 0.13.367); rows for probatio-typed schemas and `const`-module device classes; 2026.10 milestone. |
