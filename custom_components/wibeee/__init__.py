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
from homeassistant.const import Platform, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant

from .api import WibeeeAPI
from .config_flow import validate_input
from .const import DOMAIN, CONF_NEST_UPSTREAM, NEST_PROXY_DISABLED, NEST_DEFAULT_UPSTREAM, CONF_MAC_ADDRESS, CONF_WIBEEE_ID, \
    DEFAULT_SCAN_INTERVAL, NEST_NULL_UPSTREAM

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up platform from a ConfigEntry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {'disposers': {}}

    _LOGGER.info(f"Setup config entry '{entry.title}' (unique_id={entry.unique_id})")

    # Update things based on options
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    # Forward the setup to the sensor platform.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    disposers = hass.data[DOMAIN][entry.entry_id]['disposers']

    for name, dispose in list(disposers.items()):
        _LOGGER.debug(f"Dispose of '{name}', {dispose}")
        try:
            dispose()
            disposers.pop(name)
        except Exception:
            _LOGGER.error(f"Dispose failure for '{name}'", exc_info=True)

    _LOGGER.debug(f"Disposers finished.")

    dispose_ok = len(disposers) == 0
    unload_ok = False
    if dispose_ok:
        _LOGGER.debug(f"Unloading sensor entry for {entry.title} (unique_id={entry.unique_id})")
        unload_ok = await hass.config_entries.async_forward_entry_unload(entry, "sensor")
        if unload_ok:
            hass.data[DOMAIN].pop(entry.entry_id)

    _LOGGER.info(f"Unloaded config entry '{entry.title}' (unique_id={entry.unique_id})")
    return dispose_ok and unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    # Migrate from "Use Nest Proxy" checkbox to "Nest Cloud Service" select list
    if config_entry.version < 2:
        v1_conf_nest_proxy_enable = 'nest_proxy_enable'  # v1 config option that is no longer used.

        options = config_entry.options
        use_nest_proxy = options.get(v1_conf_nest_proxy_enable, False)
        nest_upstream = NEST_DEFAULT_UPSTREAM if use_nest_proxy else NEST_PROXY_DISABLED

        new_options = {k: v for k, v in options.items() if k != v1_conf_nest_proxy_enable} | {CONF_NEST_UPSTREAM: nest_upstream}

        hass.config_entries.async_update_entry(config_entry, version=2, options=new_options)
        _LOGGER.info("Migration to version %s successful, defaulting to: %s", config_entry.version, nest_upstream)

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

        upstream = config_entry.options[CONF_NEST_UPSTREAM]
        new_options = dict(config_entry.options) | {
            # in v4 we will no longer poll. disable polling on each entry individually for now.
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL.total_seconds(),
            CONF_NEST_UPSTREAM: NEST_NULL_UPSTREAM if upstream == NEST_PROXY_DISABLED else upstream
        }

        hass.config_entries.async_update_entry(config_entry, version=3, data=new_data, options=new_options)
        _LOGGER.info("Migration to version %s successful, saved: %s", config_entry.version, {'data': new_data, 'options': new_options})

    return True
