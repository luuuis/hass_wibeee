"""Config flow for Wibeee integration."""

import logging
from datetime import timedelta
from typing import Any

import voluptuous as vol
from homeassistant import config_entries, exceptions
from homeassistant.const import (CONF_HOST, CONF_SCAN_INTERVAL)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac

from .api import WibeeeAPI
from .const import (DOMAIN, DEFAULT_SCAN_INTERVAL, CONF_NEST_PROXY_ENABLE)
from .util import short_mac

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: HomeAssistant, user_input: dict) -> [str, str, dict[str, Any]]:
    """Validate the user input allows us to connect. """
    session = async_get_clientsession(hass)
    api = WibeeeAPI(session, user_input[CONF_HOST], timeout=timedelta(seconds=1))
    try:
        device = await api.async_fetch_device_info(retries=5)
    except Exception as e:
        raise NoDeviceInfo from e

    mac_addr = format_mac(device['macAddr'])
    unique_id = mac_addr
    name = f"Wibeee {short_mac(mac_addr)}"

    return name, unique_id, {CONF_HOST: user_input[CONF_HOST], }


class WibeeeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Wibeee config flow."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                title, unique_id, data = await validate_input(self.hass, user_input)
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(title=title, data=data)

            except AbortFlow:
                # allow this to escape the catch-all below
                raise

            except NoDeviceInfo:
                # host is not a Wibeee...
                errors[CONF_HOST] = "no_device_info"

            except Exception:
                _LOGGER.exception("Unexpected exception", exc_info=True)
                errors["base"] = "unknown"

        return await self._show_setup_form(conf=user_input, errors=errors)

    async def async_step_import(self, conf: dict):
        """Import a configuration from config.yaml."""
        return await self.async_step_user(user_input=conf)

    async def _show_setup_form(self, conf=None, errors=None):
        """Show the setup form to the user."""
        schema = vol.Schema({
            vol.Required(CONF_HOST, default=conf[CONF_HOST] if conf else None): str,
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors or {})

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return WibeeeOptionsFlowHandler(config_entry)


class WibeeeOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Wibeee."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL.total_seconds())
                ): int,
                vol.Optional(
                    CONF_NEST_PROXY_ENABLE,
                    default=self.config_entry.options.get(CONF_NEST_PROXY_ENABLE, False)
                ): bool
            }),
        )


class NoDeviceInfo(exceptions.HomeAssistantError):
    """Error to indicate we couldn't get info from Wibeee."""
