"""The untaken half of every defensive branch in ``coordinator.py``.

Phase 2 item 21 of the August 2026 plan (§M) — the last module, and the one the
plan deliberately left until after `diagnostics.py`: 26 partials over 929
statements is proportionate, whereas 20 over 193 was not.

Two shapes dominate, and the tests are built around them:

**Loop-continue guards.** ``for x in …: if <not wanted>: continue``. With a
single-element fixture, "skipped and continued" and "skipped and stopped" are
indistinguishable — both produce nothing. Every loop test here therefore uses at
least two items with the **unwanted one first**, and asserts the later item was
still processed. That is the only arrangement in which a guard that stopped the
loop fails.

**First-wins guards.** ``if last_x is None: last_x = …``. The untaken half is
the *second* matching record, so these need two alerts of the same severity and
an assertion that the **first** one won.

The parse block is wrapped in a broad ``except`` that logs and moves on, so a
test asserting only "no exception" would pass against a parse that silently gave
up. Every assertion here is on a parsed value.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.util import dt as dt_util

from custom_components.unifi_network_monitor.api import UnifiAuthError
from custom_components.unifi_network_monitor.coordinator import (
    UnifiNetworkDataUpdateCoordinator,
    _extract_wan_networkconf,
    _parse_gateway,
    _parse_health,
    build_ap_name_map,
)

MOCK_MAC = "aa:bb:cc:dd:ee:ff"


def _now() -> datetime:
    return dt_util.now()


# ---------------------------------------------------------------------------
# build_ap_name_map — a device with no MAC must not stop the sweep
# ---------------------------------------------------------------------------


def test_ap_name_map_skips_a_device_with_no_mac_and_keeps_going() -> None:
    """A MAC-less record is stepped over; the AP after it is still mapped.

    A device with no MAC cannot be keyed, and the map is what turns a rogue
    detection into a human-readable "detected by" name. A guard that stopped
    here would leave every AP after the malformed one unnamed.
    """
    result = build_ap_name_map(
        [
            {"name": "No MAC At All"},
            {"mac": "AA:BB:CC:11:22:33", "name": "Study AP"},
        ]
    )

    assert result == {"aa:bb:cc:11:22:33": "Study AP"}


def test_ap_name_map_falls_back_from_name_to_model_to_mac() -> None:
    """The three-step fallback, so a nameless AP is still identifiable."""
    result = build_ap_name_map(
        [
            {"mac": "AA:BB:CC:11:22:33", "model": "U6-Pro"},
            {"mac": "DD:EE:FF:44:55:66"},
        ]
    )

    assert result["aa:bb:cc:11:22:33"] == "U6-Pro"
    assert result["dd:ee:ff:44:55:66"] == "DD:EE:FF:44:55:66"


# ---------------------------------------------------------------------------
# _extract_wan_networkconf — a third WAN group is neither WAN1 nor WAN2
# ---------------------------------------------------------------------------


def test_extract_wan_ignores_an_unrecognised_wan_group() -> None:
    """A WAN whose group is neither WAN nor WAN2 is skipped, not misfiled.

    The unrecognised entry is placed **before** the real WAN2 so a guard that
    stopped iterating would return ``wan2 = None`` — and the weight write would
    then refuse with "not yet loaded" on hardware that is perfectly fine.
    """
    wan1, wan2 = _extract_wan_networkconf(
        [
            {"purpose": "wan", "wan_networkgroup": "WAN3", "_id": "third"},
            {"purpose": "wan", "wan_networkgroup": "WAN", "_id": "first"},
            {"purpose": "wan", "wan_networkgroup": "WAN2", "_id": "second"},
        ]
    )

    assert wan1 is not None
    assert wan1["_id"] == "first"
    assert wan2 is not None
    assert wan2["_id"] == "second"


# ---------------------------------------------------------------------------
# _parse_gateway — temperature, storage and uplink guards
# ---------------------------------------------------------------------------


def _gw(**extra: Any) -> dict[str, Any]:
    return {"mac": MOCK_MAC, "name": "Gateway", "model": "UDMPRO", **extra}


def test_parse_gateway_skips_an_unknown_temperature_type() -> None:
    """A sensor type the firmware added is ignored; the board reading survives.

    The unknown type is listed first, so a guard that stopped the loop would
    lose the board temperature entirely.
    """
    result = _parse_gateway(
        _gw(
            temperatures=[
                {"type": "phy", "value": 55.0},
                {"type": "board", "value": 41.5},
            ]
        ),
        _now(),
    )

    assert result["board_temp"] == 41.5


def test_parse_gateway_skips_a_non_persistent_mount_point() -> None:
    """Only ``/persistent`` is reported; another mount must not stop the scan."""
    result = _parse_gateway(
        _gw(
            storage=[
                {"mount_point": "/var/log", "used": 1, "size": 2},
                {"mount_point": "/persistent", "used": 250, "size": 1000},
            ]
        ),
        _now(),
    )

    assert result["storage_used"] == 250
    assert result["storage_used_pct"] == 25.0


def test_parse_gateway_leaves_the_percentage_unset_when_size_is_zero() -> None:
    """A reported size of zero cannot yield a percentage — and must not divide.

    ``storage_used`` is still published: the raw figure is real even when the
    ratio is not, and blanking both would hide a working reading.
    """
    result = _parse_gateway(
        _gw(
            storage=[
                {"mount_point": "/persistent", "used": 250, "size": 0},
                {"mount_point": "/data", "used": 1, "size": 2},
            ]
        ),
        _now(),
    )

    assert result["storage_used"] == 250
    assert result["storage_used_pct"] is None


def test_parse_gateway_with_no_uplink_reports_no_internet() -> None:
    """An empty uplink block leaves internet False and speedtest unknown.

    ``False`` and ``None`` are different answers here: the switch is genuinely
    not up, but nothing has been said about a speedtest.
    """
    result = _parse_gateway(_gw(uplink={}), _now())

    assert result["internet"] is False
    assert result["speedtest_status"] is None


# ---------------------------------------------------------------------------
# _parse_health — an unknown subsystem must not stop the parse
# ---------------------------------------------------------------------------


def test_parse_health_skips_an_unknown_subsystem_and_keeps_going() -> None:
    """UniFi can add a subsystem; the ones after it must still be read.

    This is the branch with the widest blast radius in the module — every
    health sensor after an unrecognised subsystem would go ``unknown`` on a
    controller update, which reads as an outage rather than as a parse gap.
    """
    result = _parse_health(
        [
            {"subsystem": "something_new", "status": "ok"},
            {"subsystem": "vpn", "status": "ok"},
        ],
        _now(),
    )

    assert result["vpn_status"] == "ok"


# ---------------------------------------------------------------------------
# Boot-time derivation — a cached entry carrying no boot_time
# ---------------------------------------------------------------------------


async def test_bad_uptime_with_a_cached_entry_missing_its_boot_time(
    hass: Any, mock_config_entry: Any
) -> None:
    """A cached record without a ``boot_time`` yields None, not a crash.

    Reachable from a store written by an older version, or from a record whose
    write was interrupted. The guard reads its own persisted state, so per the
    plan's rule it is never a candidate for deletion.
    """
    mock_config_entry.add_to_hass(hass)
    coordinator = UnifiNetworkDataUpdateCoordinator(
        hass, mock_config_entry, MagicMock()
    )
    coordinator._boot_times = {MOCK_MAC: {"last_uptime": 100}}

    assert coordinator.get_stable_boot_time(MOCK_MAC, None, _now()) is None


async def test_bad_uptime_returns_the_cached_boot_time_when_present(
    hass: Any, mock_config_entry: Any
) -> None:
    """The other half — a good cached value survives a bad uptime reading."""
    mock_config_entry.add_to_hass(hass)
    coordinator = UnifiNetworkDataUpdateCoordinator(
        hass, mock_config_entry, MagicMock()
    )
    cached = "2026-08-01T00:00:00+00:00"
    coordinator._boot_times = {MOCK_MAC: {"boot_time": cached}}

    result = coordinator.get_stable_boot_time(MOCK_MAC, -1, _now())

    assert result == dt_util.parse_datetime(cached)


# ---------------------------------------------------------------------------
# Site resolution — an error that matches none of the known signatures
# ---------------------------------------------------------------------------


# The parsed configuration is injected into the gateway dict only when a gateway
# device was found in stat/device, so every full-update test needs one present —
# otherwise the assertions below would read a gateway that was never built and
# fail for a reason unrelated to the branch under test.
_GATEWAY_DEVICE: dict[str, Any] = {
    "mac": MOCK_MAC,
    "name": "Gateway",
    "model": "UDMPRO",
    "state": 1,
}


def _api(**overrides: Any) -> MagicMock:
    api = MagicMock()
    api.api_key = "key"
    api.get_devices = AsyncMock(return_value=[dict(_GATEWAY_DEVICE)])
    api.get_health = AsyncMock(return_value=[])
    api.get_sysinfo = AsyncMock(return_value=[])
    api.get_networkconf = AsyncMock(return_value=[])
    api.get_settings = AsyncMock(return_value=[])
    api.get_daily_gateway = AsyncMock(return_value=[])
    api.get_monthly_gateway = AsyncMock(return_value=[])
    api.get_rogueaps = AsyncMock(return_value=[])
    api.get_guests = AsyncMock(return_value=[])
    api.get_backups = AsyncMock(return_value=[])
    api.get_speedtest_results = AsyncMock(return_value=[])
    api.get_wlanconf = AsyncMock(return_value=[])
    api.get_system_logs = AsyncMock(return_value=[])
    api.get_sites = AsyncMock(return_value=[])
    api.get_wan_interfaces = AsyncMock(return_value=[])
    api.get_vpn_tunnels = AsyncMock(return_value=[])
    api.get_firewall_policies = AsyncMock(return_value=[])
    for name, value in overrides.items():
        setattr(api, name, value)
    return api


async def test_a_transient_site_error_does_not_latch_failed(
    hass: Any, mock_config_entry: Any
) -> None:
    """An unrecognised error leaves ``site_uuid`` unset so the next poll retries.

    Latching ``"failed"`` on any error would turn one timeout into permanently
    unavailable VPN, firewall and WAN-name sensors until a reload — the
    signatures are matched precisely so that a transient fault stays transient.
    """
    mock_config_entry.add_to_hass(hass)
    api = _api(get_sites=AsyncMock(side_effect=RuntimeError("connection reset")))
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)

    await coordinator._async_update_data()

    assert coordinator.site_uuid != "failed"


@pytest.mark.parametrize(
    "error",
    [
        RuntimeError("HTTP error 404"),
        RuntimeError("HTTP error 400"),
        RuntimeError("API key rejected"),
        UnifiAuthError("bad key"),
    ],
)
async def test_a_permanent_site_error_latches_failed(
    hass: Any, mock_config_entry: Any, error: Exception
) -> None:
    """The four signatures that mean "this will not start working"."""
    mock_config_entry.add_to_hass(hass)
    api = _api(get_sites=AsyncMock(side_effect=error))
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)

    await coordinator._async_update_data()

    assert coordinator.site_uuid == "failed"


# ---------------------------------------------------------------------------
# Settings, rogue, backups and speedtest parse guards
# ---------------------------------------------------------------------------


async def test_an_unrelated_setting_does_not_stop_the_ips_scan(
    hass: Any, mock_config_entry: Any
) -> None:
    """The ``ips`` block is found even when another setting precedes it."""
    mock_config_entry.add_to_hass(hass)
    api = _api(
        get_settings=AsyncMock(
            return_value=[
                {"key": "mgmt", "x": 1},
                {"key": "ips", "ips_mode": "idsIps", "ad_blocking_enabled": True},
            ]
        )
    )
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)

    result = await coordinator._async_update_data()

    assert result["gateway"]["ips_mode"] == "idsIps"
    assert result["gateway"]["ad_blocking"] is True


async def test_rogue_history_is_not_touched_when_security_is_off(
    hass: Any, mock_config_entry: Any
) -> None:
    """Security off means nothing is written to the persistent rogue history.

    The strongest-rogue view is still computed from whatever arrived, because
    the sensor reports what it was given. The history and the bus events are the
    part the toggle governs, and they must stay untouched.
    """
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={**mock_config_entry.options, "enable_security_monitoring": False},
    )
    api = _api()
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)

    await coordinator._async_update_data()

    assert coordinator.rogue_history == {}


async def test_a_backup_with_no_timestamp_yields_no_last_backup(
    hass: Any, mock_config_entry: Any
) -> None:
    """A backup record missing its time cannot date the last backup."""
    mock_config_entry.add_to_hass(hass)
    api = _api(get_backups=AsyncMock(return_value=[{"name": "auto.unf"}]))
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)

    result = await coordinator._async_update_data()

    assert result["gateway"]["last_backup"] is None


async def test_a_single_speedtest_result_populates_wan1_only(
    hass: Any, mock_config_entry: Any
) -> None:
    """One result with no interface metadata is WAN1; WAN2 stays unknown."""
    mock_config_entry.add_to_hass(hass)
    api = _api(
        get_speedtest_results=AsyncMock(
            return_value=[{"time": 1, "download_mbps": 500, "upload_mbps": 50}]
        )
    )
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)

    result = await coordinator._async_update_data()

    assert result["gateway"]["wan1_speedtest_download"] == 500
    assert result["gateway"]["wan2_speedtest_download"] is None


async def test_two_speedtests_far_apart_are_not_treated_as_a_pair(
    hass: Any, mock_config_entry: Any
) -> None:
    """Results more than ten minutes apart are two WAN1 runs, not WAN1+WAN2.

    Without the window, yesterday's run would be published as WAN2's current
    speed — a plausible-looking number for a link that may not exist.
    """
    mock_config_entry.add_to_hass(hass)
    api = _api(
        get_speedtest_results=AsyncMock(
            return_value=[
                {"time": 10_000_000, "download_mbps": 500},
                {"time": 1_000_000, "download_mbps": 100},
            ]
        )
    )
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)

    result = await coordinator._async_update_data()

    assert result["gateway"]["wan1_speedtest_download"] == 500
    assert result["gateway"]["wan2_speedtest_download"] is None


async def test_a_speedtest_result_with_no_time_leaves_lastrun_unset(
    hass: Any, mock_config_entry: Any
) -> None:
    """A result without a timestamp still yields speeds, but no "last run"."""
    mock_config_entry.add_to_hass(hass)
    api = _api(
        get_speedtest_results=AsyncMock(
            return_value=[
                {"interface_name": "eth8", "download_mbps": 500},
                {"interface_name": "eth9", "download_mbps": 200},
            ]
        )
    )
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)

    result = await coordinator._async_update_data()

    assert result["gateway"]["wan1_speedtest_download"] == 500
    assert result["gateway"]["wan2_speedtest_download"] == 200
    assert result["gateway"]["wan1_speedtest_lastrun"] is None


async def test_a_networkconf_entry_without_a_vlan_is_not_counted(
    hass: Any, mock_config_entry: Any
) -> None:
    """A WAN network has no VLAN and must not inflate the configured count."""
    mock_config_entry.add_to_hass(hass)
    api = _api(
        get_networkconf=AsyncMock(
            return_value=[
                {"purpose": "wan", "wan_networkgroup": "WAN"},
                {"purpose": "corporate", "vlan": 10, "enabled": True},
            ]
        )
    )
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)

    result = await coordinator._async_update_data()

    assert result["gateway"]["configured_vlans"] == 1


# ---------------------------------------------------------------------------
# System-log alerts — severity dispatch, the 24h window, and first-wins
# ---------------------------------------------------------------------------


def _log(severity: str, when: datetime, key: str) -> dict[str, Any]:
    return {
        "severity": severity,
        "timestamp": int(dt_util.as_timestamp(when) * 1000),
        "key": key,
        "id": key,
    }


async def _gateway_from_logs(
    hass: Any, entry: Any, logs: list[dict[str, Any]]
) -> dict[str, Any]:
    entry.add_to_hass(hass)
    api = _api(get_system_logs=AsyncMock(return_value=logs))
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, entry, api)
    result = await coordinator._async_update_data()
    gateway: dict[str, Any] = result["gateway"]
    return gateway


async def test_an_alert_older_than_24h_is_reported_but_not_counted(
    hass: Any, mock_config_entry: Any
) -> None:
    """The 24h counter and the "most recent" title answer different questions.

    An alert from last week is still the latest one if nothing has happened
    since, so it must appear as ``last_very_high`` while contributing nothing to
    the 24-hour count. Zeroing the title too would make a quiet week look like a
    broken sensor.
    """
    old = _now() - timedelta(days=3)
    gateway = await _gateway_from_logs(
        hass, mock_config_entry, [_log("VERY_HIGH", old, "OLD_CRIT")]
    )

    assert gateway["alerts_very_high_24h"] == 0
    assert gateway["last_very_high"] is not None


async def test_a_high_alert_older_than_24h_is_reported_but_not_counted(
    hass: Any, mock_config_entry: Any
) -> None:
    """The same distinction on the HIGH branch, which has its own counter."""
    old = _now() - timedelta(days=3)
    gateway = await _gateway_from_logs(
        hass, mock_config_entry, [_log("HIGH", old, "OLD_HIGH")]
    )

    assert gateway["alerts_high_24h"] == 0
    assert gateway["last_high"] is not None


async def test_the_first_very_high_alert_wins_and_the_rest_still_count(
    hass: Any, mock_config_entry: Any
) -> None:
    """Latest-first ordering means the first match is the newest — it wins.

    The second alert must still increment the counter, so this pins both halves
    at once: overwriting would report the older title, and ``break``-ing would
    undercount.
    """
    recent = _now() - timedelta(hours=1)
    older = _now() - timedelta(hours=2)
    gateway = await _gateway_from_logs(
        hass,
        mock_config_entry,
        [_log("VERY_HIGH", recent, "NEWEST"), _log("VERY_HIGH", older, "OLDER")],
    )

    assert gateway["alerts_very_high_24h"] == 2
    assert gateway["last_very_high_attrs"]["id"] == "NEWEST"


async def test_the_first_high_alert_wins_and_the_rest_still_count(
    hass: Any, mock_config_entry: Any
) -> None:
    """Same again on the HIGH branch."""
    recent = _now() - timedelta(hours=1)
    older = _now() - timedelta(hours=2)
    gateway = await _gateway_from_logs(
        hass,
        mock_config_entry,
        [_log("HIGH", recent, "NEWEST"), _log("HIGH", older, "OLDER")],
    )

    assert gateway["alerts_high_24h"] == 2
    assert gateway["last_high_attrs"]["id"] == "NEWEST"


async def test_a_low_severity_alert_is_ignored_without_stopping_the_scan(
    hass: Any, mock_config_entry: Any
) -> None:
    """LOW and MEDIUM are not tracked; they must not hide what follows.

    The LOW entry is placed **first** deliberately — the sensors poll only
    HIGH/VERY_HIGH, so a guard that stopped on an untracked severity would drop
    every real alert behind it and report a quiet network.
    """
    recent = _now() - timedelta(hours=1)
    gateway = await _gateway_from_logs(
        hass,
        mock_config_entry,
        [_log("LOW", recent, "NOISE"), _log("HIGH", recent, "REAL")],
    )

    assert gateway["alerts_high_24h"] == 1
    assert gateway["last_high_attrs"]["id"] == "REAL"


async def test_an_alert_with_no_timestamp_is_treated_as_outside_the_window(
    hass: Any, mock_config_entry: Any
) -> None:
    """A missing timestamp cannot be shown to be recent, so it is not counted."""
    gateway = await _gateway_from_logs(
        hass,
        mock_config_entry,
        [{"severity": "HIGH", "key": "NO_TIME", "id": "NO_TIME"}],
    )

    assert gateway["alerts_high_24h"] == 0
    assert gateway["last_high"] is not None


# ---------------------------------------------------------------------------
# Gateway registration with no MAC (__init__.py)
# ---------------------------------------------------------------------------


async def test_setup_skips_gateway_registration_without_a_mac(
    hass: Any, mock_config_entry: Any
) -> None:
    """A partially-configured entry has no MAC, so no root device is created.

    Registering one anyway would mint a device whose identifier is ``(DOMAIN,
    None)`` and which nothing could ever match or clean up.
    """
    from unittest.mock import patch

    from homeassistant.helpers import device_registry as dr

    from custom_components.unifi_network_monitor import async_setup_entry
    from custom_components.unifi_network_monitor.const import DOMAIN

    mock_config_entry.add_to_hass(hass)
    data = dict(mock_config_entry.data)
    data.pop("mac", None)
    hass.config_entries.async_update_entry(mock_config_entry, data=data)

    before = len(dr.async_get(hass).devices)

    with (
        patch(
            "custom_components.unifi_network_monitor.UnifiNetworkAPI",
            return_value=_api(),
        ),
        patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()),
    ):
        assert await async_setup_entry(hass, mock_config_entry) is True

    devices = dr.async_get(hass).devices
    assert len(devices) == before
    assert not any((DOMAIN, None) in device.identifiers for device in devices.values())


# ---------------------------------------------------------------------------
# The last of the parse guards
# ---------------------------------------------------------------------------


def test_parse_gateway_ignores_an_uplink_that_is_not_the_wan_port() -> None:
    """Only the uplink commented ``WAN`` supplies the public address.

    An uplink block is present and up — so ``internet`` is True — but it is not
    the WAN port, and taking its address would publish an internal one as the
    subscriber's public IP.
    """
    result = _parse_gateway(
        _gw(uplink={"up": True, "comment": "LAN", "ip": "10.0.0.9"}), _now()
    )

    assert result["internet"] is True
    assert result["wan1_local_ip"] is None


async def test_speedtest_falls_back_to_default_interfaces_without_a_gateway(
    hass: Any, mock_config_entry: Any
) -> None:
    """With no gateway in stat/device the default interface names are used.

    Reachable while the gateway is rebooting: the speedtest history is still
    served by the controller, so the results must still map rather than being
    dropped for want of an ifname lookup.
    """
    mock_config_entry.add_to_hass(hass)
    api = _api(
        get_devices=AsyncMock(return_value=[]),
        get_speedtest_results=AsyncMock(
            return_value=[
                {"interface_name": "eth8", "download_mbps": 500, "time": 2},
                {"interface_name": "eth9", "download_mbps": 200, "time": 1},
            ]
        ),
    )
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)

    result = await coordinator._async_update_data()

    # No gateway device means no gateway dict to publish into, but the parse
    # must have completed rather than aborted — the devices key proves it ran.
    assert result["gateway"] == {}
    assert result["devices"] == {}


async def test_speedtest_with_only_wan2_metadata_leaves_wan1_unset(
    hass: Any, mock_config_entry: Any
) -> None:
    """One tagged result that is not WAN1: WAN2 is filled, WAN1 stays unknown.

    Two branches at once — the interface loop runs to completion without ever
    finding a WAN1 match (so it never breaks early), and the ``w1`` mapping is
    skipped. Publishing WAN2's figures as WAN1's would be worse than unknown.
    """
    mock_config_entry.add_to_hass(hass)
    api = _api(
        get_speedtest_results=AsyncMock(
            return_value=[
                {"interface_name": "eth9", "download_mbps": 200, "time": 1},
            ]
        )
    )
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)

    result = await coordinator._async_update_data()

    assert result["gateway"]["wan1_speedtest_download"] is None
    assert result["gateway"]["wan2_speedtest_download"] == 200


async def test_nothing_is_polled_counted_or_fired_when_alerts_are_off(
    hass: Any, mock_config_entry: Any
) -> None:
    """With Alerts disabled nothing is fetched, counted or announced.

    An automation subscribed to the event must go quiet, not merely quieter —
    and the endpoint must stop being polled, which is the whole point of a
    feature toggle that gates a fetch rather than only an entity.
    """
    from custom_components.unifi_network_monitor.const import EVENT_NEW_ALERT

    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={**mock_config_entry.options, "enable_logs_alerts": False},
    )
    api = _api(
        get_system_logs=AsyncMock(
            return_value=[_log("HIGH", _now() - timedelta(hours=1), "REAL")]
        )
    )
    coordinator = UnifiNetworkDataUpdateCoordinator(hass, mock_config_entry, api)

    fired: list[Any] = []
    hass.bus.async_listen(EVENT_NEW_ALERT, lambda event: fired.append(event.data))

    result = await coordinator._async_update_data()
    await hass.async_block_till_done()

    # Alerts off skips the system-log fetch outright, so there is nothing to
    # count and nothing to announce. Both are asserted: a toggle that silenced
    # the event while still polling would be a wasted request every cycle.
    assert result["gateway"]["alerts_high_24h"] == 0
    assert fired == []


# ---------------------------------------------------------------------------
# Why four `isinstance(..., list)` guards in the parse block are unreachable
# ---------------------------------------------------------------------------


async def test_every_optional_fetch_returns_a_list_whatever_the_api_returns(
    hass: Any, mock_config_entry: Any
) -> None:
    """``_fetch_optional`` normalises with ``list()``, on success and on failure.

    This is the fact that makes the parse block's ``isinstance(x, list)`` checks
    on wlanconf, networkconf, vpn tunnels and firewall policies **unreachable**:
    the immediate caller has already guaranteed a list, so the false branch
    cannot be entered from a poll. Recorded as a test rather than as a comment
    because it is the guarantee the redundancy rests on — if this ever stops
    holding, those four guards stop being dead and this test says so first.

    Not deleting them here: five defensive checks in the parse path are the
    owner's call, and it is parked (§P) rather than taken unilaterally at the
    end of a test phase.
    """
    mock_config_entry.add_to_hass(hass)
    coordinator = UnifiNetworkDataUpdateCoordinator(
        hass, mock_config_entry, MagicMock()
    )

    # A tuple from the API still arrives as a list.
    fresh = await coordinator._fetch_optional(
        AsyncMock(return_value=({"a": 1},)), "probe"
    )
    assert isinstance(fresh, list)
    assert fresh == [{"a": 1}]

    # And so does the held payload on the failure path.
    held = await coordinator._fetch_optional(
        AsyncMock(side_effect=RuntimeError("drift")), "probe"
    )
    assert isinstance(held, list)
    assert held == [{"a": 1}]
