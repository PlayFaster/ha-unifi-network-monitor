# Home Assistant Compatibility

What Home Assistant versions this integration supports and the status of any changing core APIs.

**Reviewed 2026-11-01.**

> [!IMPORTANT]
>
> **Nothing in this integration requires action before Home Assistant 2027.8.** All version-sensitive Home Assistant APIs are either shimmed with dynamic fallbacks or pass explicit parameters.

---

## Supported versions

| Type | Version / Status | Note |
| :-- | :-- | :-- |
| **Minimum** | **2025.2.0** | Declared in `README.md` |
| **Tested against** | **2026.10.4** | `pytest-homeassistant-custom-component` 0.13.375 (development container) |
| **Enforced by** | `hacs.json` | `"homeassistant": "2025.2.0"` |
| **Functional floor** | `data_entry_flow.section` | Introduced in HA 2024.11 |
| **Python** | 3.13 or later | Required by Home Assistant 2025.2.0. Tests run on Python 3.14 |

---

## Deprecation & compatibility ledger

| API / Feature | Deprecated in | Removed in | Integration Exposure | Status |
| :-- | :-- | :-- | :-- | :-- |
| `DeviceInfo.via_device` identifier tuple (`HAC-012`) | 2026.8 | **2027.8** | Sub-device parent links | **Already Handled**: `_compat.via_device_link()` |
| `async_get_device(identifiers=…)` (`HAC-012`) | 2026.8 | **2027.8** | Device lookups | **Already Handled**: `_compat.device_by_identifier()` |
| `DeviceRegistry.devices` used as a mapping (`HAC-014`) | 2026.10 | Not announced | Tests only | **Not Needed**: component code does not use it; two tests iterate the registry instead (`[1.1.0-dev11]`) |
| `DeviceRegistry.async_get` returns `DeviceEntry \| ChildDeviceEntry` | 2026.9 (typing) | — | `services.py` device lookup | **Clear** — `_compat.owning_entry_ids()` accepts either (`[1.1.0-dev11]`) |
| `DeviceEntry.config_entries` (`HAC-013`) | 2026.8 | **2027.10** | Device ownership checks | **Already Handled**: `_compat.owning_entry_ids()` |
| Implicit coordinator `config_entry` detection (`HAC-016`) | 2024.8 | **2026.8** | `DataUpdateCoordinator` | **Already Handled**: passed explicitly |
| `BaseTrackerEntity.battery_level` (`HAC-015`) | 2026.6 | **2027.7** | None — no tracker platform | **Not Needed** |
| `TrackerEntity.location_name` (`HAC-015`) | 2026.6 | **2027.7** | None — no tracker platform | **Not Needed** |
| `voluptuous` imports (`HAC-009`) | N/A (replaced by probatio in 2026.9) | None announced | Config flow and schemas | **Held**: works through Home Assistant's `install_as_voluptuous()` alias. Done when HA removes or announces removal of the alias, which needs a 2026.9.0 floor (`HAC-009`, triage 2026-11-04). |
| Flow and service schema types (probatio) (`HAC-010`) | 2026.10, type hints only | None announced | `voluptuous` imports in the config flow, services and schemas | **Already Handled**: runtime is unaffected, and a shared `pyproject.toml` override makes Mypy treat `voluptuous` as untyped. Mypy Strict passes (C-037). |
| Device-class enums in `const` modules (`HAC-011`) | 2026.10, type hints only | None announced | `BinarySensorDeviceClass` imported from the platform package | **Already Handled**: the package re-export still works, and a shared `pyproject.toml` override makes Mypy count it as an export. Mypy Strict passes (C-037). |
| `DeviceInfo` dict compatibility layer (`HAC-002`) | 2026.11 (dataclass) | Not announced | `helpers.py` sub-device builders call `.update()` | **Queued**: cross-project item `device_info_dataclass_2026_11.md` |
| Entity re-added on entity ID change without `async_entity_id_changed` (`HAC-004`) | 2026.11 | **2027.11** | `number.py` lifecycle hook | **Not Needed**: no lifecycle hook in this integration depends on the entity ID, so in-place renaming, the default from 2027.11, is correct for it. Checked by reading the hooks and every use of the entity ID; not live-tested (`HAC-004`, triage 2026-11-04). |
| `PERCENTAGE` as a unit of measurement (`HAC-005`) | 2026.7 | Not announced | 15 sensors | **Held**: `PERCENTAGE` and `UnitOfRatio.PERCENTAGE` give the same `"%"` value, so nothing can break. Done when HA rejects `PERCENTAGE` units or the floor reaches 2026.7.0 (`HAC-005`, triage 2026-11-04). |
| Boolean return from config entry methods (`HAC-019`) | 2026.11, core integrations only | Not announced for custom integrations | `async_setup_entry` and `async_unload_entry` return booleans (`__init__.py:224` setup, `:245` unload) | **Held**: booleans work for custom integrations; forced by Home Assistant reporting them; floor none, a feature-detected shim covers it |

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
| **v1.4.0** | 2026-10-28 | Claude | Retroactive compatibility audit: tested-against 2026.10.2 (0.13.373); ledger rows cite `ha_compat_findings_register.md` IDs; rows added for this integration's new exposures. |
| **v1.4.1** | 2026-11-01 | Claude | Compatibility audit: tested-against 2026.10.4 (`pytest-homeassistant-custom-component` 0.13.375). |
| **v1.4.2** | 2026-11-15 | Claude | Compatibility audit: ledger row for `HAC-019`. |
| **v1.4.3** | 2026-11-15 | Claude | `HAC-019` Status cell set to Held by triage. |
