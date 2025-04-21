"""
Support for Energy consumption Sensors from Circutor
Device's website: http://wibeee.circutor.com/
Documentation: https://github.com/luuuis/hass_wibeee/
"""
import logging
import os
import re

import homeassistant.helpers.entity_registry as er
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .api import WibeeeAPI
from .config_flow import validate_input
from .const import DOMAIN, CONF_NEST_UPSTREAM, NEST_DEFAULT_UPSTREAM, CONF_MAC_ADDRESS, CONF_WIBEEE_ID, NEST_NULL_UPSTREAM

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up platform from a ConfigEntry."""
    _LOGGER.info(f"Setup config entry '{entry.title}' (unique_id={entry.unique_id})")

    # Update things based on options
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    # Forward the setup to the sensor platform.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug(f"Unloading sensor entry for {entry.title} (unique_id={entry.unique_id})")
    unload_ok = await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    _LOGGER.info(f"Unloaded config entry '{entry.title}' (unique_id={entry.unique_id})")
    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    # Store the MAC address and ID in the ConfigEntry, saving us from gymnastics on each sensor restore later on
    if config_entry.version < 3:
        saved_data = config_entry.data

        # prior to #138 the Wibeee ID was used to generate the entity's name. leverage this fact to
        # reverse-engineer the MAC address and ID from the registry entities, avoiding an API call.
        entries = er.async_entries_for_config_entry(er.async_get(hass), config_entry.entry_id)
        unique_id_names = {e.unique_id: e.original_name for e in entries if not e.has_entity_name}

        mac_addr = os.path.commonprefix(list(unique_id_names.keys()))
        original_name = os.path.commonprefix(list(unique_id_names.values()))
        if len(unique_id_names) == len(entries) and re.match(r'_[0-9a-f]{12}_', mac_addr) and re.match(r'\w+ ', original_name):
            new_data = saved_data | {
                CONF_MAC_ADDRESS: mac_addr[1:-1],
                CONF_WIBEEE_ID: original_name[:-1],
            }
        else:
            _LOGGER.info("Unable to migrate offline based on %d entries: %s", len(entries), unique_id_names)
            _, _, new_data = await validate_input(hass, dict(saved_data))

        hass.config_entries.async_update_entry(config_entry, version=3, data=new_data)
        _LOGGER.info("Migration to version %s successful, saved: %s", config_entry.version, {'data': new_data})

    # remove 'scan_interval', remove 'proxy_disabled' option
    if config_entry.version < 4:
        upstream = config_entry.options.get(CONF_NEST_UPSTREAM, NEST_NULL_UPSTREAM)
        new_options = {k: v for k, v in config_entry.options.items() if k != 'scan_interval'} | {
            CONF_NEST_UPSTREAM: NEST_NULL_UPSTREAM if upstream == 'proxy_disabled' else upstream
        }

        hass.config_entries.async_update_entry(config_entry, version=4, options=new_options)
        _LOGGER.info("Migration to version %s successful, saved: %s", config_entry.version, {'options': new_options})

    return True
