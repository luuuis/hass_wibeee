"""
Support for Energy consumption Sensors from Circutor
Device's website: http://wibeee.circutor.com/
Documentation: https://github.com/luuuis/hass_wibeee/
"""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_NEST_UPSTREAM, NEST_PROXY_DISABLED, NEST_DEFAULT_UPSTREAM

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
    if config_entry.version == 1:
        v1_conf_nest_proxy_enable = 'nest_proxy_enable'  # v1 config option that is no longer used.

        options = config_entry.options
        use_nest_proxy = options.get(v1_conf_nest_proxy_enable, False)
        nest_upstream = NEST_DEFAULT_UPSTREAM if use_nest_proxy else NEST_PROXY_DISABLED

        new_options = {k: v for k, v in options.items() if k != v1_conf_nest_proxy_enable} | {CONF_NEST_UPSTREAM: nest_upstream}

        config_entry.version = 2
        hass.config_entries.async_update_entry(config_entry, options=new_options)
        _LOGGER.info("Migration to version %s successful", config_entry.version)

    return True
