# Roadmap for future changes to the UniFi Network Monitor Home Assistant Custom Component

## Optionally EXclude WAN2 Entities

Allow a user to (re)Configure the integration to remove the WAN2 entities

- The use case is single WAN mode, not wanting the additional sensors present as unknown
  - Would require use of "Clean-Up" button / action afterward
- Useful, not not game-changing. At present the entities could just be disabled in the HA UI anyway.

## Security Sub-device - Expansion of Rogue Access Point Detection and Alerts

Move all security related entities to a new dedicated Security" sub-device, and expand the capabilities of the Rogue AP system

- Move Honeypot, Threat Management, Ad Blocking, Rules and NPN entities
- Add ignore / "known rogue" exclude SSID list to (re)Configure
  - Use case is ignore my neighbors WiFI
- Add ignore AP exclude list to (re)Configure
  - Use case is ignore the Garden AP

## Potential Other EXclude Groups

Based on implementing the Optionally EXclude WAN2 Entities above, the same capability could remove other groups

- Options would include
  - IP Addresses
    - Use case is privacy focussed, if you do not want your public IP in HA
  - Load Balancing Info
    - Would already be gone if WAN2 removed. Use case here is dial WAN but failover mode, don't need/want to track
