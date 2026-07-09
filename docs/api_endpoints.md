# UniFi API Endpoints Reference 🔗

This document details the UniFi Network API endpoints used (and deliberately not used) by this integration, including their purpose, patterns, and context.

---

## 🔧 Authentication Endpoints

These endpoints are used to manage authentication when API Key auth is not selected.

### `POST /api/auth/login`

- **Used**: Yes (Username/Password mode)
- **Purpose**: Authenticates credentials and returns a session cookie (`TOKEN`) and CSRF token header (`X-CSRF-Token` / `x-csrf-token`).

### `POST /api/auth/logout`

- **Used**: Yes (Username/Password mode)
- **Purpose**: Terminates the active session and clears local token/CSRF states.

---

## 🔘 Active Endpoints (Used)

These endpoints are called during regular polling cycles or user actions.

### `GET /proxy/network/api/s/{site}/stat/device`

- **Used**: Yes
- **Purpose**: Fetches status and telemetry for all network devices (gateways, switches, access points).
- **Payload**: Medium to Large (contains complete device tables).
- **Use Case**: Powers the main entities for devices, ports, CPU, memory, general hardware health, and WAN IP telemetry:
  - **WAN1 Local IP**: Extracted from `wan1.ip` (with fallback to `uplink.ip`).
  - **WAN2 Local IP**: Extracted from `wan2.ip`.
  - **WAN1 Public IP**: Extracted from `geo_info.WAN.address` or `active_geo_info.WAN.address`.
  - **WAN2 Public IP**: Extracted from `geo_info.WAN2.address` or `active_geo_info.WAN2.address`.

### `GET /proxy/network/api/s/{site}/stat/health`

- **Used**: Yes
- **Purpose**: Fetches system/subsystem-wide network health metrics (WAN, LAN, WLAN, VPN).
- **Use Case**: Used to populate system health indicators and binary status flags.

### `GET /proxy/network/api/s/{site}/stat/sysinfo`

- **Used**: Yes
- **Purpose**: Fetches general controller/gateway metadata (firmware version, model, uptime).
- **Use Case**: Helps validate connections and populate hardware metadata during startup.

### `GET /proxy/network/api/s/{site}/rest/networkconf`

- **Used**: Yes
- **Purpose**: Retrieves configuration settings for defined networks.
- **Use Case**: Used to read WAN configurations and load-balancing parameters.

### `PUT /proxy/network/api/s/{site}/rest/networkconf/{net_id}`

- **Used**: Yes
- **Purpose**: Updates specific network configurations.
- **Use Case**: Allows modifying network configurations directly from HA services or configuration flows.

### `GET /proxy/network/api/s/{site}/rest/setting`

- **Used**: Yes
- **Purpose**: Retrieves global site settings.
- **Use Case**: Used to fetch site-wide settings such as Threat Management policies or LED configurations.

### `POST /proxy/network/api/s/{site}/stat/report/daily.gw`

- **Used**: Yes
- **Purpose**: Requests historical daily gateway usage statistics (bytes upload/download) over a given date range.
- **Use Case**: Provides aggregated volume stats for long-term daily WAN monitoring.

### `POST /proxy/network/api/s/{site}/stat/report/monthly.gw`

- **Used**: Yes
- **Purpose**: Requests historical monthly gateway usage statistics over a given date range.
- **Use Case**: Provides aggregated volume stats for monthly billing-cycle tracking.

### `GET /proxy/network/api/s/{site}/stat/rogueap`

- **Used**: Yes
- **Purpose**: Identifies nearby rogue or interference-causing access points.
- **Use Case**: Exposes wireless security and environmental noise sensors.

### `GET /proxy/network/api/s/{site}/stat/guest`

- **Used**: Yes
- **Purpose**: Lists currently active guest users and their statistics.
- **Use Case**: Feeds counts and status info for guest networking.

### `POST /proxy/network/api/s/{site}/cmd/backup`

- **Used**: Yes
- **Purpose**: Initiates or retrieves details about controller backups.
- **Use Case**: Lists backup states and triggers routine backup tasks.

### `GET /proxy/network/v2/api/site/{site}/speedtest`

- **Used**: Yes (v2 API path)
- **Purpose**: Fetches historical speedtest runs and results.
- **Use Case**: Feeds the latency, download, and upload rate sensors from past automated or manual speedtests.

### `POST /proxy/network/api/s/{site}/cmd/devmgr`

- **Used**: Yes
- **Purpose**: Sends command payloads to the device manager.
- **Use Case**: Triggers a manual, on-demand speedtest on the gateway.

### `GET /proxy/network/api/s/{site}/rest/wlanconf`

- **Used**: Yes
- **Purpose**: Fetches WiFi/WLAN configuration details (such as SSID names and enabled states).
- **Use Case**: Used to calculate the total and active WiFi network counts, and the broadcast status of individual SSIDs.

### Official API v3 Endpoints (API Key / Integration v1 paths)

- **Used**: Yes (for supplementary configuration telemetry)
- **Purpose**: Modern official endpoints introduced for structured config querying.
- **⚠️ Auth mode — API key only**: unlike the classic `/proxy/network/api/s/{site}/…` endpoints (which work under either auth mode), these Integration (v1) endpoints are **only reachable with an API key**. Under username/password (cookie) auth `get_sites()` fails, `coordinator.site_uuid` latches to `"failed"`, and the seven sensors these endpoints feed (Rules Active/Configured/Disabled, VPN Connections Active/Total, WAN1/WAN2 Name) are permanently `unknown`. This is expected, not a bug — see `DEVELOPMENT.md` §5 "Gotcha — auth mode gates the v3 (integration) endpoints".
- **Endpoints Used**:
  - `GET /proxy/network/integration/v1/sites`: Resolves the human-readable site ID (e.g. `default`) to its target `site_uuid`.
  - `GET /proxy/network/integration/v1/sites/{site_uuid}/wans`: Fetches WAN physical interface metadata, including custom interface aliases (e.g. `WAN1_ISP1`).
  - `GET /proxy/network/integration/v1/sites/{site_uuid}/vpn/site-to-site-tunnels`: Retrieves site-to-site VPN tunnels and their connectivity states.
  - `GET /proxy/network/integration/v1/sites/{site_uuid}/vpn/servers`: Retrieves configured VPN servers.
  - `GET /proxy/network/integration/v1/sites/{site_uuid}/firewall/policies`: Retrieves firewall rules and policies.
- **Use Case**: Extracted to populate total/active telemetry counts for VPN connections, firewall rules, VLAN networks, and custom interface names. If any of these endpoints fail or return empty/404 on older controllers, the integration degrades gracefully and marks the corresponding telemetry sensors unavailable rather than crashing.

---

## ❌ Unused Endpoints

These endpoints are documented for reference but are **not** actively used by this integration.

### `GET /proxy/network/api/s/{site}/stat/device/{mac}`

- **Used**: **No**
- **Purpose**: Fetches telemetry for a single device matching the provided MAC address (e.g., the gateway).
- **Rationale for omission**: While this endpoint is utilized by some other integrations (like `Unifi-WAN`) for high-frequency ("fast") polling of live WAN rates, this integration uses a centralized polling approach via the full device list (`stat/device`). We poll the full list at a standard scan interval to avoid rate limiting and excessive requests on the UniFi OS controller.
- **Payload Difference**: It returns the exact same data schema/structure for the device as the parent `stat/device` endpoint, but filters the response to only return the single matching device, saving bandwidth and JSON parsing overhead when querying a single device frequently.

### `GET /proxy/network/api/s/{site}/stat/sta`

- **Used**: **No**
- **Purpose**: Returns information about all currently connected clients (stations).
- **Rationale for omission**: High overhead and noise. Client tracking is better handled by the native Home Assistant UniFi integration.

### `GET /proxy/network/api/s/{site}/stat/alluser`

- **Used**: **No**
- **Purpose**: Retrieves all historic or configured network clients.
- **Rationale for omission**: Large response size and low relevance to real-time gateway and device health monitoring.
