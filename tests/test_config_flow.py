"""Tests for the UniFi Network Monitor config flow."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.unifi_network_monitor.api import (
    UnifiAuthError,
    UnifiConnectionError,
    UnifiNetworkAPI,
)
from custom_components.unifi_network_monitor.config_flow import (
    UnifiNetworkConfigFlow,
    _clean_host,
    _merge_credentials,
    _validate_auth_fields,
    _validate_connection,
)
from custom_components.unifi_network_monitor.const import (
    CONF_ENABLE_DUAL_WAN,
    CONF_ENABLE_LOGS_ALERTS,
    CONF_ENABLE_SECURITY_MONITORING,
    CONF_ENABLE_SPEEDTEST,
    CONF_ENABLE_WAN_USAGE,
    CONF_ROGUE_IGNORE_APS,
    CONF_ROGUE_IGNORE_SSIDS,
    CONF_UNIFI_DEVICE_MODE,
    DEFAULT_ROGUE_IGNORE_APS,
    DEFAULT_ROGUE_IGNORE_SSIDS,
    DOMAIN,
)


@pytest.fixture(autouse=True)
def mock_setup_entry():
    """Mock setting up the config entry."""
    with patch(
        "custom_components.unifi_network_monitor.async_setup_entry",
        return_value=True,
    ) as mock:
        yield mock


VALID_INPUT = {
    "host": "192.168.1.1",
    "api_key": "test-key",
    "username": "",
    "password": "",
    "site": "default",
}

SETTINGS_INPUT = {
    "host": "192.168.1.1",
    "api_key": "test-key",
    "username": "",
    "password": "",
    "site": "default",
    CONF_UNIFI_DEVICE_MODE: "none",
    "sensor_groups": {
        CONF_ENABLE_SPEEDTEST: True,
        CONF_ENABLE_WAN_USAGE: True,
        CONF_ENABLE_SECURITY_MONITORING: True,
        CONF_ENABLE_DUAL_WAN: True,
        CONF_ENABLE_LOGS_ALERTS: True,
    },
    CONF_ROGUE_IGNORE_SSIDS: DEFAULT_ROGUE_IGNORE_SSIDS,
    CONF_ROGUE_IGNORE_APS: DEFAULT_ROGUE_IGNORE_APS,
}

REAUTH_INPUT = {
    "host": "192.168.1.1",
    "api_key": "test-key",
    "username": "",
    "password": "",
    "site": "default",
}

MOCK_IDENTITY = {
    "mac": "aa:bb:cc:dd:ee:ff",
    "model": "UDMPRO",
    "sw_version": "5.1.19",
}


@pytest.mark.usefixtures("socket_enabled")
async def test_config_flow_api_key_success(hass: Any) -> None:
    """Complete config flow succeeds with a valid API key."""
    with patch(
        "custom_components.unifi_network_monitor.config_flow._validate_connection",
        AsyncMock(return_value=MOCK_IDENTITY),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        assert result["type"] == FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=VALID_INPUT
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["mac"] == "aa:bb:cc:dd:ee:ff"


@pytest.mark.usefixtures("socket_enabled")
async def test_config_flow_cannot_connect(hass: Any) -> None:
    """Config flow shows error on connection failure."""
    with patch(
        "custom_components.unifi_network_monitor.config_flow._validate_connection",
        AsyncMock(side_effect=UnifiConnectionError("timeout")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=VALID_INPUT
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


@pytest.mark.usefixtures("socket_enabled")
async def test_config_flow_invalid_auth(hass: Any) -> None:
    """Config flow shows error on auth failure."""
    with patch(
        "custom_components.unifi_network_monitor.config_flow._validate_connection",
        AsyncMock(side_effect=UnifiAuthError("bad key")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=VALID_INPUT
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_auth"


@pytest.mark.usefixtures("socket_enabled")
async def test_config_flow_no_credentials_shows_error(hass: Any) -> None:
    """Config flow shows error when neither api_key nor user/pass provided."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "host": "192.168.1.1",
            "api_key": "",
            "username": "",
            "password": "",
            "site": "default",
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "auth_required"


@pytest.mark.usefixtures("socket_enabled")
async def test_config_flow_duplicate_aborts(hass: Any) -> None:
    """Second config flow for same device aborts with already_configured."""
    with patch(
        "custom_components.unifi_network_monitor.config_flow._validate_connection",
        AsyncMock(return_value=MOCK_IDENTITY),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=VALID_INPUT
        )

    with patch(
        "custom_components.unifi_network_monitor.config_flow._validate_connection",
        AsyncMock(return_value=MOCK_IDENTITY),
    ):
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], user_input=VALID_INPUT
        )

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


@pytest.mark.usefixtures("socket_enabled")
async def test_config_flow_reconfigure_success(hass: Any) -> None:
    """Reconfigure flow succeeds with valid credentials."""
    with patch(
        "custom_components.unifi_network_monitor.config_flow._validate_connection",
        AsyncMock(return_value=MOCK_IDENTITY),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=VALID_INPUT
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        entry_id = result["result"].entry_id

    updated_input = {**REAUTH_INPUT, "api_key": "new-key"}
    with patch(
        "custom_components.unifi_network_monitor.config_flow._validate_connection",
        AsyncMock(return_value=MOCK_IDENTITY),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reauth", "entry_id": entry_id},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=updated_input
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


@pytest.mark.usefixtures("socket_enabled")
async def test_config_flow_reauth_no_entry(hass: Any) -> None:
    """Reauth raises UnknownEntry for non-existent entry."""
    with patch(
        "custom_components.unifi_network_monitor.config_flow._validate_connection",
        AsyncMock(return_value=MOCK_IDENTITY),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "user"},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=VALID_INPUT
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY

    from homeassistant.config_entries import UnknownEntry

    with pytest.raises(UnknownEntry):
        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reauth", "entry_id": "nonexistent"},
        )


@pytest.mark.usefixtures("socket_enabled")
async def test_options_flow_success(hass: Any) -> None:
    """Options flow updates scan interval successfully."""
    with patch(
        "custom_components.unifi_network_monitor.config_flow._validate_connection",
        AsyncMock(return_value=MOCK_IDENTITY),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=VALID_INPUT
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        entry = result["result"]

    with patch(
        "custom_components.unifi_network_monitor.config_flow._validate_connection",
        AsyncMock(return_value=MOCK_IDENTITY),
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input=SETTINGS_INPUT,
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("socket_enabled")
async def test_config_flow_unexpected_error(hass: Any) -> None:
    """Config flow shows unknown error on unexpected exception."""
    with patch(
        "custom_components.unifi_network_monitor.config_flow._validate_connection",
        AsyncMock(side_effect=RuntimeError("boom")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=VALID_INPUT
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "unknown"


@pytest.mark.usefixtures("socket_enabled")
async def test_options_flow_cannot_connect(hass: Any) -> None:
    """Options flow shows connection error."""
    with patch(
        "custom_components.unifi_network_monitor.config_flow._validate_connection",
        AsyncMock(return_value=MOCK_IDENTITY),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=VALID_INPUT
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        entry = result["result"]

    with patch(
        "custom_components.unifi_network_monitor.config_flow._validate_connection",
        AsyncMock(side_effect=UnifiConnectionError("timeout")),
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input=SETTINGS_INPUT,
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "cannot_connect"


@pytest.mark.usefixtures("socket_enabled")
async def test_options_flow_invalid_auth(hass: Any) -> None:
    """Options flow shows auth error."""
    with patch(
        "custom_components.unifi_network_monitor.config_flow._validate_connection",
        AsyncMock(return_value=MOCK_IDENTITY),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=VALID_INPUT
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        entry = result["result"]

    with patch(
        "custom_components.unifi_network_monitor.config_flow._validate_connection",
        AsyncMock(side_effect=UnifiAuthError("bad key")),
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input=SETTINGS_INPUT,
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "invalid_auth"


# ------------------------------------------------------------------
# Helper function tests
# ------------------------------------------------------------------


def test_clean_host_strips_protocol() -> None:
    """_clean_host strips protocol prefix and trailing slash."""
    assert _clean_host("https://192.168.1.1/") == "192.168.1.1"


def test_merge_credentials_fills_blank_api_key() -> None:
    """_merge_credentials fills blank API key from existing."""
    result = _merge_credentials(
        {"host": "x", "api_key": "", "username": "", "password": ""},
        {"api_key": "stored-key", "password": ""},
    )
    assert result["api_key"] == "stored-key"


def test_merge_credentials_fills_blank_password() -> None:
    """_merge_credentials fills blank password from existing."""
    result = _merge_credentials(
        {"host": "x", "api_key": "", "username": "user", "password": ""},
        {"api_key": "", "password": "stored-pass"},
    )
    assert result["password"] == "stored-pass"


def test_validate_auth_fields_returns_none_when_api_key_provided() -> None:
    """_validate_auth_fields returns None when API key is provided."""
    result = _validate_auth_fields({"api_key": "key", "username": "", "password": ""})
    assert result is None


def test_validate_auth_fields_returns_none_when_user_pass_provided() -> None:
    """_validate_auth_fields returns None when username+password provided."""
    result = _validate_auth_fields({"api_key": "", "username": "u", "password": "p"})
    assert result is None


def test_validate_auth_fields_returns_auth_required() -> None:
    """_validate_auth_fields returns auth_required when no credentials."""
    result = _validate_auth_fields({"api_key": "", "username": "", "password": ""})
    assert result == "auth_required"


@pytest.mark.usefixtures("socket_enabled")
async def test_validate_connection_creates_api_and_validates(hass: Any) -> None:
    """_validate_connection creates an API instance and calls validate."""
    api_mock = AsyncMock(spec=UnifiNetworkAPI)
    api_mock.validate_connection = AsyncMock(return_value=MOCK_IDENTITY)

    with (
        patch(
            "custom_components.unifi_network_monitor.config_flow.async_get_clientsession",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.unifi_network_monitor.config_flow.UnifiNetworkAPI",
            return_value=api_mock,
        ),
    ):
        result = await _validate_connection(hass, VALID_INPUT)
    assert result == MOCK_IDENTITY


# ------------------------------------------------------------------
# Reconfigure step coverage
# ------------------------------------------------------------------


@pytest.mark.usefixtures("socket_enabled")
async def test_config_flow_reconfigure_step_success(hass: Any) -> None:
    """Reconfigure step succeeds with valid credentials."""
    with patch(
        "custom_components.unifi_network_monitor.config_flow._validate_connection",
        AsyncMock(return_value=MOCK_IDENTITY),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=VALID_INPUT
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        entry = result["result"]

    with patch(
        "custom_components.unifi_network_monitor.config_flow._validate_connection",
        AsyncMock(return_value=MOCK_IDENTITY),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reconfigure", "entry_id": entry.entry_id},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reconfigure"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={**SETTINGS_INPUT, "api_key": "updated-key"},
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"


async def test_config_flow_reconfigure_can_clear_ignore_list(hass: Any) -> None:
    """A rogue ignore list can be CLEARED via reconfigure (omitted key → blank).

    Regression: with ``default=<current value>`` the frontend omits the emptied
    optional and voluptuous restores the old value, so the field can't be cleared.
    Using ``suggested_value`` + ``default=""`` makes a blank submit clear it.
    """
    with patch(
        "custom_components.unifi_network_monitor.config_flow._validate_connection",
        AsyncMock(return_value=MOCK_IDENTITY),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=VALID_INPUT
        )
        entry = result["result"]

        # 1) Set an ignore list.
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reconfigure", "entry_id": entry.entry_id},
        )
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                **SETTINGS_INPUT,
                "api_key": "k",
                CONF_ROGUE_IGNORE_SSIDS: "Foo, Bar",
            },
        )
        assert entry.options[CONF_ROGUE_IGNORE_SSIDS] == "Foo, Bar"

        # 2) Clear it: the frontend omits the emptied optional entirely.
        cleared = {
            k: v for k, v in SETTINGS_INPUT.items() if k != CONF_ROGUE_IGNORE_SSIDS
        }
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reconfigure", "entry_id": entry.entry_id},
        )
        await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={**cleared, "api_key": "k"}
        )
        assert entry.options[CONF_ROGUE_IGNORE_SSIDS] == ""


@pytest.mark.usefixtures("socket_enabled")
async def test_config_flow_reconfigure_auth_error(hass: Any) -> None:
    """Reconfigure step shows auth error."""
    with patch(
        "custom_components.unifi_network_monitor.config_flow._validate_connection",
        AsyncMock(return_value=MOCK_IDENTITY),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=VALID_INPUT
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        entry = result["result"]

    with patch(
        "custom_components.unifi_network_monitor.config_flow._validate_connection",
        AsyncMock(side_effect=UnifiAuthError("bad key")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reconfigure", "entry_id": entry.entry_id},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={**SETTINGS_INPUT, "api_key": "bad-key"},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "invalid_auth"


@pytest.mark.usefixtures("socket_enabled")
async def test_config_flow_reconfigure_connection_error(hass: Any) -> None:
    """Reconfigure step shows connection error."""
    with patch(
        "custom_components.unifi_network_monitor.config_flow._validate_connection",
        AsyncMock(return_value=MOCK_IDENTITY),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=VALID_INPUT
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        entry = result["result"]

    with patch(
        "custom_components.unifi_network_monitor.config_flow._validate_connection",
        AsyncMock(side_effect=UnifiConnectionError("timeout")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reconfigure", "entry_id": entry.entry_id},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={**SETTINGS_INPUT, "api_key": "bad-key"},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "cannot_connect"


# ------------------------------------------------------------------
# Reauth_confirm additional error path coverage
# ------------------------------------------------------------------


@pytest.mark.usefixtures("socket_enabled")
async def test_config_flow_reauth_confirm_auth_error(hass: Any) -> None:
    """Reauth_confirm shows auth error."""
    with patch(
        "custom_components.unifi_network_monitor.config_flow._validate_connection",
        AsyncMock(return_value=MOCK_IDENTITY),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=VALID_INPUT
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        entry_id = result["result"].entry_id

    with patch(
        "custom_components.unifi_network_monitor.config_flow._validate_connection",
        AsyncMock(side_effect=UnifiAuthError("bad key")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reauth", "entry_id": entry_id},
        )
        # reauth calls reauth_confirm directly
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={**REAUTH_INPUT, "api_key": "bad-key"},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "invalid_auth"


# ------------------------------------------------------------------
# Options flow additional error path coverage
# ------------------------------------------------------------------


@pytest.mark.usefixtures("socket_enabled")
async def test_options_flow_unexpected_error(hass: Any) -> None:
    """Options flow shows unknown error on unexpected exception."""
    with patch(
        "custom_components.unifi_network_monitor.config_flow._validate_connection",
        AsyncMock(return_value=MOCK_IDENTITY),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=VALID_INPUT
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        entry = result["result"]

    with patch(
        "custom_components.unifi_network_monitor.config_flow._validate_connection",
        AsyncMock(side_effect=RuntimeError("boom")),
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input=SETTINGS_INPUT,
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "unknown"


# ------------------------------------------------------------------
# Additional error path coverage
# ------------------------------------------------------------------


@pytest.mark.usefixtures("socket_enabled")
async def test_config_flow_reconfigure_no_credentials(hass: Any) -> None:
    """Reconfigure merges empty creds with existing (line 192 is dead code)."""
    with patch(
        "custom_components.unifi_network_monitor.config_flow._validate_connection",
        AsyncMock(return_value=MOCK_IDENTITY),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=VALID_INPUT
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        entry = result["result"]

    with patch(
        "custom_components.unifi_network_monitor.config_flow._validate_connection",
        AsyncMock(return_value=MOCK_IDENTITY),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reconfigure", "entry_id": entry.entry_id},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                "host": "192.168.1.1",
                "api_key": "",
                "username": "",
                "password": "",
                "site": "default",
                CONF_UNIFI_DEVICE_MODE: "none",
                "sensor_groups": {
                    CONF_ENABLE_SPEEDTEST: True,
                    CONF_ENABLE_WAN_USAGE: True,
                    CONF_ENABLE_SECURITY_MONITORING: True,
                },
            },
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


@pytest.mark.usefixtures("socket_enabled")
async def test_config_flow_reconfigure_unexpected_error(hass: Any) -> None:
    """Reconfigure shows unknown error on unexpected exception (lines 205-207)."""
    with patch(
        "custom_components.unifi_network_monitor.config_flow._validate_connection",
        AsyncMock(return_value=MOCK_IDENTITY),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=VALID_INPUT
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        entry = result["result"]

    with patch(
        "custom_components.unifi_network_monitor.config_flow._validate_connection",
        AsyncMock(side_effect=RuntimeError("unexpected")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reconfigure", "entry_id": entry.entry_id},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=SETTINGS_INPUT,
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "unknown"


@pytest.mark.usefixtures("socket_enabled")
async def test_config_flow_reauth_confirm_no_credentials(hass: Any) -> None:
    """Reauth_confirm merges empty creds with existing (line 235 is dead code)."""
    with patch(
        "custom_components.unifi_network_monitor.config_flow._validate_connection",
        AsyncMock(return_value=MOCK_IDENTITY),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=VALID_INPUT
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        entry_id = result["result"].entry_id

    with patch(
        "custom_components.unifi_network_monitor.config_flow._validate_connection",
        AsyncMock(return_value=MOCK_IDENTITY),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reauth", "entry_id": entry_id},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                "host": "192.168.1.1",
                "api_key": "",
                "username": "",
                "password": "",
                "site": "default",
            },
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


@pytest.mark.usefixtures("socket_enabled")
async def test_config_flow_reauth_confirm_connection_error(hass: Any) -> None:
    """Reauth_confirm shows connection error (lines 249-250)."""
    with patch(
        "custom_components.unifi_network_monitor.config_flow._validate_connection",
        AsyncMock(return_value=MOCK_IDENTITY),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=VALID_INPUT
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        entry_id = result["result"].entry_id

    with patch(
        "custom_components.unifi_network_monitor.config_flow._validate_connection",
        AsyncMock(side_effect=UnifiConnectionError("timeout")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reauth", "entry_id": entry_id},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=REAUTH_INPUT,
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "cannot_connect"


@pytest.mark.usefixtures("socket_enabled")
async def test_config_flow_reauth_confirm_unexpected_error(hass: Any) -> None:
    """Reauth_confirm shows unknown error on unexpected exception (lines 251-253)."""
    with patch(
        "custom_components.unifi_network_monitor.config_flow._validate_connection",
        AsyncMock(return_value=MOCK_IDENTITY),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=VALID_INPUT
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        entry_id = result["result"].entry_id

    with patch(
        "custom_components.unifi_network_monitor.config_flow._validate_connection",
        AsyncMock(side_effect=RuntimeError("unexpected")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reauth", "entry_id": entry_id},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=REAUTH_INPUT,
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "unknown"


@pytest.mark.usefixtures("socket_enabled")
async def test_options_flow_no_credentials(hass: Any) -> None:
    """Options flow merges empty creds with existing (line 287 is dead code)."""
    with patch(
        "custom_components.unifi_network_monitor.config_flow._validate_connection",
        AsyncMock(return_value=MOCK_IDENTITY),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=VALID_INPUT
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        entry = result["result"]

    with patch(
        "custom_components.unifi_network_monitor.config_flow._validate_connection",
        AsyncMock(return_value=MOCK_IDENTITY),
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                "host": "192.168.1.1",
                "api_key": "",
                "username": "",
                "password": "",
                "site": "default",
                CONF_UNIFI_DEVICE_MODE: "none",
                "sensor_groups": {
                    CONF_ENABLE_SPEEDTEST: True,
                    CONF_ENABLE_WAN_USAGE: True,
                    CONF_ENABLE_SECURITY_MONITORING: True,
                },
            },
        )
    assert result["type"] == FlowResultType.CREATE_ENTRY


# ------------------------------------------------------------------
# auth_required branches when stored options also lack credentials
# (config_flow lines 192, 235, 287) — reachable only when the entry's
# options carry no credentials to fall back on.
# ------------------------------------------------------------------

# Options with no stored credentials (no api_key / username / password).
NO_CRED_OPTIONS = {
    "host": "192.168.1.1",
    "site": "default",
    CONF_UNIFI_DEVICE_MODE: "none",
    CONF_ENABLE_SPEEDTEST: True,
    CONF_ENABLE_WAN_USAGE: True,
    CONF_ENABLE_SECURITY_MONITORING: True,
    CONF_ENABLE_DUAL_WAN: True,
    CONF_ENABLE_LOGS_ALERTS: True,
    CONF_ROGUE_IGNORE_SSIDS: DEFAULT_ROGUE_IGNORE_SSIDS,
    CONF_ROGUE_IGNORE_APS: DEFAULT_ROGUE_IGNORE_APS,
}

BLANK_INPUT = {
    "host": "192.168.1.1",
    "api_key": "",
    "username": "",
    "password": "",
    "site": "default",
    CONF_UNIFI_DEVICE_MODE: "none",
    "sensor_groups": {
        CONF_ENABLE_SPEEDTEST: True,
        CONF_ENABLE_WAN_USAGE: True,
        CONF_ENABLE_SECURITY_MONITORING: True,
        CONF_ENABLE_DUAL_WAN: True,
        CONF_ENABLE_LOGS_ALERTS: True,
    },
    CONF_ROGUE_IGNORE_SSIDS: DEFAULT_ROGUE_IGNORE_SSIDS,
    CONF_ROGUE_IGNORE_APS: DEFAULT_ROGUE_IGNORE_APS,
}

REAUTH_BLANK_INPUT = {
    "host": "192.168.1.1",
    "api_key": "",
    "username": "",
    "password": "",
    "site": "default",
}


def _no_cred_entry() -> MockConfigEntry:
    """Return a config entry whose options carry no stored credentials."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="UniFi Network",
        unique_id="aa:bb:cc:dd:ee:ff",
        data={"mac": "aa:bb:cc:dd:ee:ff"},
        options=NO_CRED_OPTIONS,
    )


@pytest.mark.usefixtures("socket_enabled")
async def test_config_flow_reconfigure_auth_required(hass: Any) -> None:
    """Reconfigure shows auth_required when neither input nor options have creds."""
    entry = _no_cred_entry()
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reconfigure", "entry_id": entry.entry_id},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=dict(BLANK_INPUT)
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "auth_required"


@pytest.mark.usefixtures("socket_enabled")
async def test_config_flow_reauth_confirm_auth_required(hass: Any) -> None:
    """Reauth_confirm shows auth_required when neither input nor options have creds."""
    entry = _no_cred_entry()
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reauth", "entry_id": entry.entry_id},
    )
    assert result["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=dict(REAUTH_BLANK_INPUT)
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "auth_required"


async def test_config_flow_reauth_confirm_entry_gone(hass: Any) -> None:
    """Reauth_confirm aborts as successful when the entry no longer exists (line 241).

    Drives the handler directly with a context pointing at a non-existent entry so
    ``async_get_entry`` returns ``None`` after credentials validate successfully.
    """
    flow = UnifiNetworkConfigFlow()
    flow.hass = hass
    flow.handler = DOMAIN
    flow.flow_id = "test-reauth-entry-gone"
    flow.context = {"source": "reauth", "entry_id": "nonexistent"}

    with patch(
        "custom_components.unifi_network_monitor.config_flow._validate_connection",
        AsyncMock(return_value=MOCK_IDENTITY),
    ):
        result = await flow.async_step_reauth_confirm(user_input=dict(VALID_INPUT))

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


@pytest.mark.usefixtures("socket_enabled")
async def test_options_flow_auth_required(hass: Any) -> None:
    """Options flow shows auth_required when neither input nor options have creds."""
    entry = _no_cred_entry()
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=dict(BLANK_INPUT)
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "auth_required"


# ------------------------------------------------------------------
# _device_mode_selector with core present
# ------------------------------------------------------------------


@pytest.mark.usefixtures("socket_enabled")
async def test_device_mode_selector_core_present(hass: Any) -> None:
    """_device_mode_selector includes satisfaction with core present."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    core_entry = MockConfigEntry(
        domain="unifi",
        title="UniFi Network",
        unique_id="core_unifi",
    )
    core_entry.add_to_hass(hass)

    from custom_components.unifi_network_monitor.config_flow import (
        _device_mode_selector,
    )

    selector = _device_mode_selector(core_present=True)
    options = selector.config["options"]
    assert "satisfaction_only" in options
    assert "none" in options
    assert "all" in options


@pytest.mark.usefixtures("socket_enabled")
async def test_device_mode_selector_core_not_present(hass: Any) -> None:
    """_device_mode_selector omits satisfaction_only when core integration is absent."""
    from custom_components.unifi_network_monitor.config_flow import (
        _device_mode_selector,
    )

    selector = _device_mode_selector(core_present=False)
    options = selector.config["options"]
    assert "satisfaction_only" not in options
    assert "none" in options
    assert "all" in options


# ------------------------------------------------------------------
# Options flow with core integration registered
# ------------------------------------------------------------------


@pytest.mark.usefixtures("socket_enabled")
async def test_options_flow_core_present(hass: Any) -> None:
    """Options includes satisfaction_only when core integration present."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    core_entry = MockConfigEntry(
        domain="unifi",
        title="UniFi Network",
        unique_id="core_unifi",
    )
    core_entry.add_to_hass(hass)

    with patch(
        "custom_components.unifi_network_monitor.config_flow._validate_connection",
        AsyncMock(return_value=MOCK_IDENTITY),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=VALID_INPUT
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        entry = result["result"]

    with patch(
        "custom_components.unifi_network_monitor.config_flow._validate_connection",
        AsyncMock(return_value=MOCK_IDENTITY),
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "init"
