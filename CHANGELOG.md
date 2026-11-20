# Changelog

All notable changes to the UniFi Network Monitor project will be documented in this file.

---

## [1.1.1] - 2026-10-16 - Release: Gateway Uptime, Diagnostics Privacy Hardening, and Single-WAN Fixes

### Summary

- **Diagnostics Privacy**: Diagnostics downloads scrub dictionary keys, nested alert parameters, and IPv6/public addresses, preventing SSIDs, tunnel names, and network details from leaking.
- **Uptime Reliability**: Gateway and link uptimes use controller start timestamps and drift-corrected latching, eliminating frozen or stale boot time reporting.
- **Single-WAN Fixes**: Monthly data totals and speedtest result pairing now handle single-WAN setups without becoming unavailable or swapping interfaces.
- **Immediate WAN Weight Feedback**: Adjusting the WAN load-balance weight updates the UI slider immediately while waiting for controller confirmation.
- **Health Severity Vocabulary**: Integration Health severity values are standardized to `ok`, `degraded`, and `error`.

### Thanks

- 🙏 **[@superscouby](https://github.com/superscouby)**: For helping to enable support for the UniFi Cloud Gateway Ultra model, and identifying several compatibility, code and diagnostic bugs.

### Fixed

- **Gateway and link uptime stale timestamps** *(refines System & Link Uptimes, introduced in 1.0.0)*: device boot times, including the gateway, are calculated directly from each device's start timestamp (`startup_timestamp`), preventing gateway uptime from freezing or becoming weeks stale. WAN1, WAN2, and Internet (`www`) link uptimes use a shared drift-corrected latch with persistent state across restarts.

- **Diagnostics redaction of keys and alert parameters** *(enhances Diagnostics, introduced in 1.0.0, refined in 1.1.0)*: state-map dictionary keys (such as SSIDs and VPN tunnel names) are tokenized rather than published as plain text, alert parameter blocks are scrubbed by default, and public IPv4 and IPv6 addresses are masked using whole-word matching that prevents redaction markers from corrupting.

- **Internet Month Total on single-WAN gateways** *(refines Internet Data Usage, introduced in 1.0.0)*: the monthly combined total treats unconfigured secondary WAN counters as zero rather than becoming unavailable when only one WAN connection is present.

- **Speedtest interface pairing on single-WAN gateways** *(refines Speedtest Tracking, introduced in 1.0.0)*: speedtest results without explicit interface tags are only paired across WAN1 and WAN2 when a secondary WAN interface is physically configured, preventing single-WAN results from misattributing to WAN2.

- **WAN load-balance weight slider responsiveness** *(refines WAN Load-Balance Control, introduced in 1.0.0, refined in 1.1.0)*: the number entity displays the newly set value immediately, maintaining the slider position until the controller confirms the write and reverting at once if the write fails.

### Changed

- **Integration Health severity vocabulary** *(refines Integration Health, introduced in 1.0.0)*: the `severity` attribute reports `ok`, `degraded`, or `error` (replacing `None`, `moderate`, and `serious`). The primary entity state (`problem`) remains `off` when healthy and `on` when issues are detected; user automations evaluating the `severity` attribute should update checks for `moderate` or `serious` to `degraded` or `error`.

- **Action icons formatting**: updated action icons in `icons.json` to Home Assistant's current nested format.

- **Concurrent login serialization**: controller authentication requests are serialized behind a dedicated lock, preventing simultaneous login attempts during session renewal.

### Added

- **Drift metrics on Integration Health**: added `drift_rate_pct`, `drift_rate_min_pct`, `drift_rate_max_pct`, `drift_intervals`, `drift_measured_seconds`, and `drift_deficit_seconds` attributes to the Integration Health sensor for link timing diagnosis.

- **Diagnostics uptime section**: diagnostics downloads include link latch anchors, counter history, and timing drift metrics.

### Under the hood

- **HTTP Seam & Test Coverage**: introduced a full-fidelity mock transport layer (`tests/transport.py`), expanding test suite coverage to 1,103 passing tests with 100% line and branch coverage (0 partial branches).
- **Diagnostics Decomposition**: refactored the diagnostics download pipeline into modular handlers, reducing complexity metrics below 20 and removing complexity exemptions.
- **Automated Leak Verification**: confirmed zero data leaks across 1,191 controller values using automated leak scanning (`scripts/diag_check.py`).

---

## [1.1.0] - 2026-10-12 - Release: Gateway Detection, Projected Data Usage, Diagnostics Hardening, and WAN Weight Controls

### Highlights

- **Gateway Detection**: Gateways detected by their WAN configuration, unlisted models included.

### Summary

- **Gateway Detection**: Gateways are detected by their WAN configuration rather than an exact model list, raising a repair if unconfirmed; existing installs that adopted the wrong device are corrected automatically on the next start when confirmed.
- **Projected Usage Sensors**: Two new sensors forecast end-of-calendar-month data usage per WAN from current cycle usage, without extra polling requests.
- **Diagnostics Visibility**: Diagnostics downloads provide clearer visibility into connection and request status, with strengthened redaction of local network names and identifiers.
- **WAN Balance Controls**: Setting WAN load-balance weights now applies adjustments cleanly and keeps paired weights in sync.
- **Database Hygiene**: Enforced unrecorded status for static sensor attributes so they do not needlessly grow the database.
- **Refresh Now**: The button raises an error if the gateway is unreachable rather than completing silently.

### ⚠️ Action Required

- **Home Assistant 2025.2.0 or newer is required**: the minimum supported Home Assistant version is now 2025.2.0 (Python 3.13+).

### Added

- **Signature-first gateway selection** *(refines Gateway Detection, introduced in 1.0.0)*: gateway identification prioritizes active WAN configurations and device roles rather than relying solely on a predefined model catalog, ensuring unlisted gateway models are reliably detected. Gateways that cannot be confirmed surface a repair issue with guidance.

- **Projected monthly usage**: two sensors forecast end-of-calendar-month data usage for each WAN from the current cycle's run rate. `WAN1/WAN2 Projected Usage` are derived from counters already polled with no extra requests to your gateway. They carry no `state_class`, preventing forecasts from skewing long-term statistics; confidence is published as `confidence`, `basis`, `cycle_day`, and `cycle_start` attributes.

- **Automatic gateway identity correction**: if an entry previously attached itself to another device due to an unlisted gateway model, setup detects the true gateway and moves unique IDs and device identifiers automatically, keeping existing entity IDs, history, and dashboards.

- **Detailed diagnostic captures** *(enhances Diagnostics, introduced in 1.0.0)*: diagnostics downloads include endpoint reachability records, login handshake metadata, gateway selection rationale, and structural summaries of refused controller requests (`last_rejection`) to assist troubleshooting without exposing sensitive values.

### Fixed

- **WAN load-balance weight consistency** *(refines WAN Load-Balance Control, introduced in 1.0.0)*: updating the WAN load-balance weight re-reads the active configuration immediately before writing and applies adjustments as an atomic pair, preventing timing discrepancies between WAN1 and WAN2.

- **Database growth** *(refines Recorder Exclusions, introduced in 1.0.0)*: `strongest_rogue_rssi`, `proximity_threshold`, `application_version`, `application_build`, and `device_type` were recorded on every poll. They are now excluded from the recorder database.

- **Refresh Now error reporting** *(refines Refresh Now, introduced in 1.0.0)*: the button raises an error when the controller cannot be reached, allowing automations and scripts to detect when a refresh did not complete.

- **Diagnostic redaction** *(enhances Diagnostics, introduced in 1.0.0)*: WAN and ISP names are removed from alert messages; ISP numbers (`ISP_ASN`) and non-default site names are redacted from diagnostic downloads.

- **Secondary WAN status on single-WAN setups**: gateways with only one configured WAN interface now report secondary WAN link status as `unknown` (`None`) rather than `False`.

### Changed

- **Minimum Home Assistant version raised to 2025.2.0**: requires Python 3.13+.

- **Repair issues are now scoped to the config entry** *(enhances Repair Issues from 1.0.0)*: repair notifications are now tied to the specific config entry, preventing entries from overwriting each other in multi-gateway environments.

- **Reauthentication screen** *(enhances Reauthentication from 1.0.0)*: clarifies the effect of leaving credential fields blank during reauthentication.

### Under the hood

- **Test Suite**: expanded to 967 tests achieving 100% line and branch coverage with zero partial branches.
- **Strict Typing**: Mypy Strict enforced across all 19 component source modules with zero type errors.
- **Code Standards**: adopted Home Assistant Core import sorting (`isort`) and McCabe cyclomatic complexity linting (`C901`).
- **Hardware Diagnostics Validation**: verified with automated leak analysis (`scripts/diag_check.py`) confirming 0 of 1,204 controller values in 21 categories found in the download.

---

## [1.0.0] - 2026-07-22 - Initial Public Release

### Highlights

- **Internet Data Usage**: daily and monthly totals, per WAN in dual-WAN mode.
- **Speedtest Tracking**: per-WAN results with one-click manual runs.
- **Rogue AP and Alerts**: rogue-AP detection and UniFi system-log alerts for automations.
- **WAN Load Balancing**: see failover status and set the WAN weight.

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
  - [\[1.1.1\] - 2026-10-16 - Release: Gateway Uptime, Diagnostics Privacy Hardening, and Single-WAN Fixes](#111---2026-10-16---release-gateway-uptime-diagnostics-privacy-hardening-and-single-wan-fixes)
  - [\[1.1.0\] - 2026-10-12 - Release: Gateway Detection, Projected Data Usage, Diagnostics Hardening, and WAN Weight Controls](#110---2026-10-12---release-gateway-detection-projected-data-usage-diagnostics-hardening-and-wan-weight-controls)
  - [\[1.0.0\] - 2026-07-22 - Initial Public Release](#100---2026-07-22---initial-public-release)

---
