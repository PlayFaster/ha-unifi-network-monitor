# Changelog

All notable changes to the UniFi Network Monitor project will be documented in this file.

## [1.1.0] - 2026-08-08 - Projected Usage; WAN Weight Write Hardened; Refresh Now Reports Failure

### Summary

- Two new sensors forecast your end-of-month data usage per WAN, from data already being collected.
- Setting the WAN load-balance weight is now reliable — it no longer risks reverting other controller settings, and the two weights can no longer be left disagreeing.
- Less database growth: several attributes were being written to the recorder on every poll and no longer are.
- Refresh Now now reports failure instead of quietly doing nothing.

### ⚠️ Action Required

- **If you have automations that press Refresh Now, check them.** The button now raises an error when the controller cannot be reached, and in Home Assistant an action that raises **stops the rest of the automation**. An automation that refreshes and then notifies you could stop before the notification — which matters most during an outage, when the controller is exactly what is unreachable.

  Add `continue_on_error: true` to the button press where the later steps matter more:

  ```yaml
  - action: button.press
    target:
      entity_id: button.unifi_network_system_refresh_now
    continue_on_error: true
  ```

  The example automations in the README have been updated. The WAN Speedtest buttons already behaved this way, so the same guidance applies to them.

### Added

- **Projected monthly usage**: two sensors forecast end-of-calendar-month data usage for each WAN, blending the current run rate with the previous cycle so early-month figures are not wild. `WAN1/WAN2 Projected Usage`, derived from counters already polled — no extra requests to your gateway. They carry no `state_class`, so a forecast never reaches long-term statistics; confidence is published as the `confidence`, `basis`, `cycle_day` and `cycle_start` attributes.

### Fixed

- **WAN load-balance weight**: setting the weight could write back a stale copy of your network configuration, undoing other changes made on the controller since the integration last polled. It now re-reads the configuration immediately before writing.

- **WAN load-balance weight consistency**: rapid changes could previously leave WAN1 and WAN2 not summing to 100 without anything reporting it. The pair is now written as one uninterruptible operation and confirmed afterwards, and a pending change is applied rather than discarded if the entity is removed mid-write.

- **Database growth**: `strongest_rogue_rssi`, the proximity threshold, `application_version`, `application_build` and `device_type` were written to the recorder on every poll. They are now excluded, as originally intended.

- **Refresh Now**: the button reported success even when the controller could not be reached. It now raises, so a script can tell the refresh did not happen. See **Action Required** above.

- **Stated Home Assistant minimum version**: the README and `hacs.json` advertised 2024.8.0 while the integration actually requires **2024.11.0**. Corrected, so an incompatible install is caught before setup rather than during it.

### Changed

- **Repair issues are now scoped to the config entry**, so with two gateways one entry's repair notice can no longer overwrite the other's. Visible text is unchanged.

- **Reauthentication screen** now explains what leaving a credential field blank does, instead of leaving it to be guessed.

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

- [Changelog](#changelog)
  - [\[1.1.0\] - 2026-08-08 - Projected Usage; WAN Weight Write Hardened; Refresh Now Reports Failure](#110---2026-08-08---projected-usage-wan-weight-write-hardened-refresh-now-reports-failure)
  - [\[1.0.0\] - 2026-07-22 - Initial Public Release](#100---2026-07-22---initial-public-release)

---
