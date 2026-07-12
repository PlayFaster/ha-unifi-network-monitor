"""Config flow for UniFi Network Monitor."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import AbortFlow, section
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import UnifiAuthError, UnifiConnectionError, UnifiNetworkAPI
from .const import (
    CONF_API_KEY,
    CONF_ENABLE_DUAL_WAN,
    CONF_ENABLE_LOGS_ALERTS,
    CONF_ENABLE_SECURITY_MONITORING,
    CONF_ENABLE_SPEEDTEST,
    CONF_ENABLE_WAN_USAGE,
    CONF_ROGUE_IGNORE_APS,
    CONF_ROGUE_IGNORE_SSIDS,
    CONF_SCAN_INTERVAL,
    CONF_SITE,
    CONF_UNIFI_DEVICE_MODE,
    DEFAULT_ENABLE_DUAL_WAN,
    DEFAULT_ENABLE_LOGS_ALERTS,
    DEFAULT_ENABLE_SECURITY_MONITORING,
    DEFAULT_ENABLE_SPEEDTEST,
    DEFAULT_ENABLE_WAN_USAGE,
    DEFAULT_NAME,
    DEFAULT_ROGUE_IGNORE_APS,
    DEFAULT_ROGUE_IGNORE_SSIDS,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SITE,
    DEFAULT_UNIFI_DEVICE_MODE,
    DEVICE_MODE_ALL,
    DEVICE_MODE_NONE,
    DEVICE_MODE_SATISFACTION,
    DOMAIN,
    clamp_device_mode,
)

_LOGGER = logging.getLogger(__name__)

# Collapsible form section grouping the feature toggles.
SECTION_SENSOR_GROUPS = "sensor_groups"


def _clean_host(host: str) -> str:
    """Strip protocol prefix and trailing slashes from a host entry."""
    clean = host.strip()
    if "://" in clean:
        clean = clean.split("://", 1)[1]
    return clean.rstrip("/")


def _core_present(hass: HomeAssistant) -> bool:
    """Return True when the HA-native UniFi (core) integration is configured."""
    return "unifi" in hass.config_entries.async_domains()


def _device_mode_selector(core_present: bool) -> SelectSelector:
    """Per-UniFi-device mode selector; satisfaction-only is core-present only."""
    options = [DEVICE_MODE_NONE]
    if core_present:
        options.append(DEVICE_MODE_SATISFACTION)
    options.append(DEVICE_MODE_ALL)
    return SelectSelector(
        SelectSelectorConfig(
            options=options,
            translation_key="unifi_device_mode",
            mode=SelectSelectorMode.LIST,
        )
    )


def _connection_fields(defaults: dict[str, Any]) -> dict[Any, Any]:
    """Return the connection portion of a flow schema (credentials blank)."""
    _password = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
    return {
        vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
        vol.Optional(CONF_API_KEY, default=""): _password,
        vol.Optional(CONF_USERNAME, default=defaults.get(CONF_USERNAME, "")): str,
        vol.Optional(CONF_PASSWORD, default=""): _password,
        vol.Optional(CONF_SITE, default=defaults.get(CONF_SITE, DEFAULT_SITE)): str,
    }


def _device_mode_field(defaults: dict[str, Any], core_present: bool) -> dict[Any, Any]:
    """Return the single per-UniFi-device mode selector field."""
    return {
        vol.Required(
            CONF_UNIFI_DEVICE_MODE,
            default=clamp_device_mode(
                defaults.get(CONF_UNIFI_DEVICE_MODE, DEFAULT_UNIFI_DEVICE_MODE),
                core_present,
            ),
        ): _device_mode_selector(core_present)
    }


def _sensor_groups_section(defaults: dict[str, Any], include_all: bool = True) -> section:
    """Build the collapsible 'Sensor groups' section of feature toggles.

    Shown only in the Configure/Reconfigure flow (initial setup is connection
    only). All five group toggles are presented, expanded.
    """
    fields: dict[Any, Any] = {
        vol.Required(
            CONF_ENABLE_SPEEDTEST,
            default=defaults.get(CONF_ENABLE_SPEEDTEST, DEFAULT_ENABLE_SPEEDTEST),
        ): bool,
        vol.Required(
            CONF_ENABLE_WAN_USAGE,
            default=defaults.get(CONF_ENABLE_WAN_USAGE, DEFAULT_ENABLE_WAN_USAGE),
        ): bool,
        vol.Required(
            CONF_ENABLE_SECURITY_MONITORING,
            default=defaults.get(
                CONF_ENABLE_SECURITY_MONITORING,
                DEFAULT_ENABLE_SECURITY_MONITORING,
            ),
        ): bool,
        vol.Required(
            CONF_ENABLE_DUAL_WAN,
            default=defaults.get(CONF_ENABLE_DUAL_WAN, DEFAULT_ENABLE_DUAL_WAN),
        ): bool,
        vol.Required(
            CONF_ENABLE_LOGS_ALERTS,
            default=defaults.get(CONF_ENABLE_LOGS_ALERTS, DEFAULT_ENABLE_LOGS_ALERTS),
        ): bool,
    }
    return section(vol.Schema(fields), {"collapsed": False})


def _user_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Build the initial setup schema — connection only.

    Entity-scope choices (per-device mode + feature-group toggles) are made in
    the Configure/Reconfigure flow, not at initial setup.
    """
    return vol.Schema(_connection_fields(defaults))


def _settings_schema(defaults: dict[str, Any], core_present: bool) -> vol.Schema:
    """Reconfigure/options schema — setup fields plus all feature toggles."""
    fields = _connection_fields(defaults)
    fields.update(_device_mode_field(defaults, core_present))
    fields[vol.Required(SECTION_SENSOR_GROUPS)] = _sensor_groups_section(defaults)
    # Rogue-AP ignore lists (advanced; comma-separated, wildcards via fnmatch).
    fields[
        vol.Optional(
            CONF_ROGUE_IGNORE_SSIDS,
            default=defaults.get(
                CONF_ROGUE_IGNORE_SSIDS, DEFAULT_ROGUE_IGNORE_SSIDS
            ),
        )
    ] = str
    fields[
        vol.Optional(
            CONF_ROGUE_IGNORE_APS,
            default=defaults.get(CONF_ROGUE_IGNORE_APS, DEFAULT_ROGUE_IGNORE_APS),
        )
    ] = str
    return vol.Schema(fields)


def _flatten_sections(user_input: dict[str, Any]) -> dict[str, Any]:
    """Lift the sensor-groups section's fields to the top level for processing."""
    flat = dict(user_input)
    group = flat.pop(SECTION_SENSOR_GROUPS, None)
    if isinstance(group, dict):
        flat.update(group)
    return flat


def _edit_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Build the reconfigure/options/reauth schema.

    Credential fields (API key, password) are intentionally left blank so the
    stored values cannot be retrieved via the UI eye-icon.  Non-sensitive fields
    (host, username, site) are pre-filled for convenience.
    """
    _password = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
            vol.Optional(CONF_API_KEY, default=""): _password,
            vol.Optional(CONF_USERNAME, default=defaults.get(CONF_USERNAME, "")): str,
            vol.Optional(CONF_PASSWORD, default=""): _password,
            vol.Optional(CONF_SITE, default=defaults.get(CONF_SITE, DEFAULT_SITE)): str,
        }
    )


def _merge_credentials(
    user_input: dict[str, Any], existing: dict[str, Any]
) -> dict[str, Any]:
    """Return user_input with blank credential fields filled from existing options."""
    merged = dict(user_input)
    for key in (CONF_API_KEY, CONF_PASSWORD):
        if not (merged.get(key) or "").strip():
            merged[key] = existing.get(key) or ""
    return merged


def _validate_auth_fields(
    user_input: dict[str, Any],
    existing: dict[str, Any] | None = None,
) -> str | None:
    """Return an error key if credentials are insufficient, else None.

    When editing, blank submitted fields fall back to ``existing`` stored values.
    """
    stored = existing or {}
    has_api_key = bool(
        (user_input.get(CONF_API_KEY) or "").strip()
        or (stored.get(CONF_API_KEY) or "").strip()
    )
    has_user_pass = bool(
        (
            (user_input.get(CONF_USERNAME) or "").strip()
            or (stored.get(CONF_USERNAME) or "").strip()
        )
        and (
            (user_input.get(CONF_PASSWORD) or "").strip()
            or (stored.get(CONF_PASSWORD) or "").strip()
        )
    )
    if not has_api_key and not has_user_pass:
        return "auth_required"
    return None


async def _validate_connection(
    hass: HomeAssistant, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Connect to UDM Pro and return gateway identity dict."""
    session = async_get_clientsession(hass)
    api = UnifiNetworkAPI(
        session,
        user_input[CONF_HOST],
        api_key=(user_input.get(CONF_API_KEY) or "").strip() or None,
        username=(user_input.get(CONF_USERNAME) or "").strip() or None,
        password=(user_input.get(CONF_PASSWORD) or "").strip() or None,
        site=user_input.get(CONF_SITE, DEFAULT_SITE),
    )
    return await api.validate_connection()


class UnifiNetworkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial setup config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial user step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input = _flatten_sections(user_input)
            user_input[CONF_HOST] = _clean_host(user_input[CONF_HOST])
            auth_error = _validate_auth_fields(user_input)
            if auth_error:
                errors["base"] = auth_error
            else:
                try:
                    info = await _validate_connection(self.hass, user_input)

                    unique_id = info["mac"] or user_input[CONF_HOST]
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=DEFAULT_NAME,
                        data=info,
                        options={
                            **user_input,
                            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                        },
                    )

                except AbortFlow:
                    raise
                except UnifiAuthError:
                    errors["base"] = "invalid_auth"
                except UnifiConnectionError:
                    errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception("Unexpected error during config flow setup")
                    errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=_user_schema(user_input or {}),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            user_input = _flatten_sections(user_input)
            user_input[CONF_HOST] = _clean_host(user_input[CONF_HOST])
            existing = dict(entry.options)
            auth_error = _validate_auth_fields(user_input, existing=existing)
            if auth_error:
                errors["base"] = auth_error
            else:
                merged = _merge_credentials(user_input, existing)
                try:
                    await _validate_connection(self.hass, merged)
                    # Update options and let the entry's update listener reload
                    # (keeps reconfigure and the options flow behaving identically).
                    self.hass.config_entries.async_update_entry(
                        entry, options={**entry.options, **merged}
                    )
                    return self.async_abort(reason="reconfigure_successful")
                except UnifiAuthError:
                    errors["base"] = "invalid_auth"
                except UnifiConnectionError:
                    errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception("Unexpected error during reconfigure")
                    errors["base"] = "unknown"

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_settings_schema(dict(entry.options), _core_present(self.hass)),
            errors=errors,
            description_placeholders={"host": entry.options.get(CONF_HOST, "")},
        )

    async def async_step_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Begin reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm new credentials during reauth."""
        errors: dict[str, str] = {}
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        host = entry.options.get(CONF_HOST, "") if entry else ""

        if user_input is not None:
            user_input[CONF_HOST] = _clean_host(user_input[CONF_HOST])
            existing = dict(entry.options) if entry else {}
            auth_error = _validate_auth_fields(user_input, existing=existing)
            if auth_error:
                errors["base"] = auth_error
            else:
                merged = _merge_credentials(user_input, existing)
                try:
                    await _validate_connection(self.hass, merged)
                    if entry is None:
                        return self.async_abort(reason="reauth_successful")
                    self.hass.config_entries.async_update_entry(
                        entry, options={**entry.options, **merged}
                    )
                    await self.hass.config_entries.async_reload(entry.entry_id)
                    return self.async_abort(reason="reauth_successful")
                except UnifiAuthError:
                    errors["base"] = "invalid_auth"
                except UnifiConnectionError:
                    errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception("Unexpected error during reauth")
                    errors["base"] = "unknown"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=_edit_schema(dict(entry.options) if entry else {}),
            errors=errors,
            description_placeholders={"host": host},
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> UnifiNetworkOptionsFlow:
        """Return the options flow handler."""
        return UnifiNetworkOptionsFlow(entry)


class UnifiNetworkOptionsFlow(config_entries.OptionsFlow):
    """Handle options reconfiguration."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize."""
        self._entry = entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage connection options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input = _flatten_sections(user_input)
            user_input[CONF_HOST] = _clean_host(user_input[CONF_HOST])
            existing = dict(self._entry.options)
            auth_error = _validate_auth_fields(user_input, existing=existing)
            if auth_error:
                errors["base"] = auth_error
            else:
                merged = _merge_credentials(user_input, existing)
                try:
                    await _validate_connection(self.hass, merged)
                    return self.async_create_entry(
                        title="", data={**self._entry.options, **merged}
                    )
                except UnifiAuthError:
                    errors["base"] = "invalid_auth"
                except UnifiConnectionError:
                    errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception("Unexpected error during options update")
                    errors["base"] = "unknown"

        return self.async_show_form(
            step_id="init",
            data_schema=_settings_schema(
                dict(self._entry.options), _core_present(self.hass)
            ),
            errors=errors,
        )
