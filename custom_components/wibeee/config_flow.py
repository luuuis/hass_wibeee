"""Config flow for Wibeee integration."""

import logging
from datetime import timedelta
from typing import Any

import voluptuous as vol
from homeassistant import config_entries, exceptions
from homeassistant.const import (CONF_HOST)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac

from .api import WibeeeAPI
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: HomeAssistant, user_input: dict) -> [str, str, dict[str, Any]]:
    """Validate the user input allows us to connect. """
    session = async_get_clientsession(hass)
    api = WibeeeAPI(session, user_input[CONF_HOST], timeout=timedelta(seconds=1))
    try:
        device = await api.async_fetch_device_info(retries=5)
    except Exception as e:
        raise NoDeviceInfo from e

    mac_addr = format_mac(device['mac_addr'])
    unique_id = mac_addr
    name = f"Wibeee {mac_addr.replace(':', '')[-6:].upper()}"

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

            except NoDeviceInfo:
                # host is not a Wibeee...
                errors[CONF_HOST] = "no_device_info"

            except Exception:
                _LOGGER.exception("Unexpected exception", exc_info=True)
                errors["base"] = "unknown"

        return await self._show_setup_form(errors)

    async def async_step_import(self, conf: dict):
        """Import a configuration from config.yaml."""
        return await self.async_step_user(user_input={CONF_HOST: conf[CONF_HOST]})

    async def _show_setup_form(self, errors=None):
        """Show the setup form to the user."""
        schema = vol.Schema({vol.Required(CONF_HOST): str, })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors or {})


class NoDeviceInfo(exceptions.HomeAssistantError):
    """Error to indicate we couldn't get info from Wibeee."""
