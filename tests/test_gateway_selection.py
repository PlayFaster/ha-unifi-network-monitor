"""Gateway model list and signature-first gateway selection (v1.1.0-dev12).

Issue #23: on a Cloud Gateway Ultra (``UDRULT``) the integration took a switch
as the gateway, because detection rested on a model list that lacked the code.
Selection is now signature first: the device carrying a WAN object, narrowed
by ``type``, online state and the model list (I2, I3).
"""

from __future__ import annotations

from typing import Any

from custom_components.unifi_network_monitor.const import (
    GATEWAY_MODELS,
    GATEWAY_TYPES,
    gateway_display_model,
)
from custom_components.unifi_network_monitor.gateway import select_gateway


def _dev(mac: str, **fields: Any) -> dict[str, Any]:
    return {"mac": mac, "state": 1, **fields}


_SWITCH = _dev("aa:00:00:00:00:01", model="USM8P210", type="usw")
_AP = _dev("aa:00:00:00:00:02", model="U6LR", type="uap")
_WAN = {"ifname": "eth4", "up": True}


def _flags(selection: Any) -> tuple[bool, bool]:
    return selection.type_match, selection.model_listed


# --- I2: model list -----------------------------------------------------------


def test_udrult_is_listed_and_product_names_and_nvrs_are_not() -> None:
    """The list holds stat/device codes, not product names or NVRs."""
    assert GATEWAY_MODELS["UDRULT"] == "UCG-Ultra"
    for absent in ("UNVR", "UNVRPRO", "UCG-Ultra", "UCG-Max", "UDMSE", "UDMBASE"):
        assert absent not in GATEWAY_MODELS
    assert {"udm", "ugw", "usg", "ucg", "uxg"} == GATEWAY_TYPES


def test_display_name_for_listed_code_and_raw_code_for_unlisted() -> None:
    """The card shows a product name where known and the raw code otherwise."""
    assert gateway_display_model("UDMPRO") == "UDM-Pro"
    assert gateway_display_model("UNLISTED9") == "UNLISTED9"
    assert gateway_display_model(None) is None


# --- I3: selection --------------------------------------------------------------


def test_udrult_with_a_wan_object_is_selected_by_signature() -> None:
    """The issue #23 gateway, behind a switch listed first."""
    gateway = _dev("aa:00:00:00:00:10", model="UDRULT", type="udm", wan1=_WAN)
    selection = select_gateway([_SWITCH, gateway])
    assert selection.device is gateway
    assert selection.reason == "wan_signature"
    assert _flags(selection) == (True, True)


def test_unlisted_model_with_a_wan_object_is_selected_by_signature() -> None:
    """An unseen gateway works without a list update."""
    gateway = _dev("aa:00:00:00:00:11", model="UNLISTED9", type="udm", wan1=_WAN)
    selection = select_gateway([_SWITCH, _AP, gateway])
    assert selection.device is gateway
    assert selection.reason == "wan_signature"
    assert _flags(selection) == (True, False)


def test_a_switch_listed_before_the_gateway_is_not_selected() -> None:
    """List order does not decide; the WAN object does."""
    gateway = _dev("aa:00:00:00:00:12", model="UDMPRO", type="udm", wan1=_WAN)
    assert select_gateway([_SWITCH, _AP, gateway]).device is gateway


def test_two_wan_carriers_one_offline_selects_the_online_one() -> None:
    """An offline carrier is not preferred over an online one."""
    offline = _dev("aa:00:00:00:00:13", model="UDMPRO", type="udm", wan1=_WAN)
    offline["state"] = 0
    online = _dev("aa:00:00:00:00:14", model="UDMPRO", type="udm", wan1=_WAN)
    selection = select_gateway([offline, online])
    assert selection.device is online
    assert selection.reason == "wan_signature"
    assert _flags(selection) == (True, True)


def test_two_wan_carriers_only_one_with_a_gateway_type() -> None:
    """The type narrows two carriers to the gateway."""
    odd = _dev("aa:00:00:00:00:15", model="X1", type="usw", wan1=_WAN)
    gateway = _dev("aa:00:00:00:00:16", model="X2", type="ucg", wan1=_WAN)
    selection = select_gateway([odd, gateway])
    assert selection.device is gateway
    assert selection.reason == "wan_signature"
    assert _flags(selection) == (True, False)


def test_no_wan_object_and_type_udm_selects_by_type() -> None:
    """With no WAN carrier, the gateway type selects."""
    gateway = _dev("aa:00:00:00:00:17", model="UNLISTED9", type="udm")
    selection = select_gateway([_SWITCH, gateway])
    assert selection.device is gateway
    assert selection.reason == "type"
    assert _flags(selection) == (True, False)


def test_no_wan_object_unknown_type_and_listed_model_selects_by_model() -> None:
    """With neither signature nor type, the model list selects."""
    gateway = _dev("aa:00:00:00:00:18", model="UDRULT", type="uxx")
    selection = select_gateway([_SWITCH, gateway])
    assert selection.device is gateway
    assert selection.reason == "model"
    assert _flags(selection) == (False, True)


def test_two_tied_gateways_are_ambiguous() -> None:
    """Two indistinguishable candidates select nothing."""
    one = _dev("aa:00:00:00:00:19", model="UDMPRO", type="udm", wan1=_WAN)
    two = _dev("aa:00:00:00:00:1a", model="UDMPRO", type="udm", wan1=_WAN)
    selection = select_gateway([one, two])
    assert selection.device is None
    assert selection.reason == "ambiguous"
    assert selection.candidates == (one, two)
    assert _flags(selection) == (False, False)


def test_no_gateway_is_none() -> None:
    """Switches and access points only: no gateway."""
    selection = select_gateway([_SWITCH, _AP])
    assert selection.device is None
    assert selection.reason == "none"
    assert _flags(selection) == (False, False)


def test_only_wan_carrier_offline_is_not_preferred_over_an_online_gateway_type() -> (
    None
):
    """An online gateway-type device wins over an offline WAN carrier."""
    carrier = _dev("aa:00:00:00:00:1b", model="X1", type="uxx", wan1=_WAN)
    carrier["state"] = 0
    typed = _dev("aa:00:00:00:00:1c", model="X2", type="udm")
    selection = select_gateway([carrier, typed])
    assert selection.device is typed
    assert selection.reason == "type"
    assert selection.signals == 1


def test_an_offline_gateway_is_still_identified() -> None:
    """Selection considers offline devices when nothing online qualifies."""
    gateway = _dev("aa:00:00:00:00:1d", model="UDMPRO", type="udm", wan1=_WAN)
    gateway["state"] = 0
    assert select_gateway([_SWITCH, gateway]).device is gateway


def test_empty_or_null_wan_objects_carry_no_signature() -> None:
    """``wan1: None`` and ``wan1: {}`` are not a WAN object."""
    for wan in (None, {}):
        device = _dev("aa:00:00:00:00:1e", model="X1", type="uxx", wan1=wan)
        assert select_gateway([device]).reason == "none"


def test_two_carriers_of_unknown_type_skip_the_type_narrowing() -> None:
    """A narrowing that would empty the set is skipped, not applied."""
    one = _dev("aa:00:00:00:00:1f", model="UDMPRO", type="uxx", wan1=_WAN)
    two = _dev("aa:00:00:00:00:20", model="X9", type="uyy", wan1=_WAN)
    selection = select_gateway([one, two])
    assert selection.device is one
    assert selection.reason == "wan_signature"


def test_two_online_gateway_type_carriers_one_listed_selects_the_listed() -> None:
    """The model list breaks a tie between two gateway-type carriers."""
    unlisted = _dev("aa:00:00:00:00:21", model="X9", type="udm", wan1=_WAN)
    listed = _dev("aa:00:00:00:00:22", model="UDMPRO", type="udm", wan1=_WAN)
    selection = select_gateway([unlisted, listed])
    assert selection.device is listed
    assert selection.reason == "wan_signature"


def test_a_tie_is_broken_in_favour_of_the_stored_mac() -> None:
    """A Shadow Mode style pair stays on the device the install already uses."""
    one = _dev("aa:00:00:00:00:23", model="UDMPRO", type="udm", wan1=_WAN)
    two = _dev("aa:00:00:00:00:24", model="UDMPRO", type="udm", wan1=_WAN)
    selection = select_gateway([one, two], stored_mac="AA-00-00-00-00-24")
    assert selection.device is two
    assert selection.reason == "wan_signature"


def test_a_missing_state_counts_as_online() -> None:
    """A device with no ``state`` key is treated as online."""
    gateway = {"mac": "aa:00:00:00:00:25", "type": "udm", "wan1": _WAN}
    offline = _dev("aa:00:00:00:00:26", type="udm", wan1=_WAN)
    offline["state"] = 0
    assert select_gateway([offline, gateway]).device is gateway


def test_an_offline_gateway_type_without_a_wan_object_is_still_identified() -> None:
    """The last pool: no online candidate and no WAN carrier, by type."""
    gateway = _dev("aa:00:00:00:00:27", model="X9", type="udm")
    gateway["state"] = 0
    selection = select_gateway([_SWITCH, gateway])
    assert selection.device is gateway
    assert selection.reason == "type"
