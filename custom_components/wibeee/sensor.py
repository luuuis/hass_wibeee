"""
Support for Energy consumption Sensors from Circutor via local Web API

Device's website: http://wibeee.circutor.com/
Documentation: https://github.com/luuuis/hass_wibeee/

"""

REQUIREMENTS = ["xmltodict"]

import logging

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
)
from homeassistant.config_entries import (ConfigEntry, SOURCE_IMPORT)
from homeassistant.const import (
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_POWER_FACTOR,
    DEVICE_CLASS_VOLTAGE,
    FREQUENCY_HERTZ,
    POWER_WATT,
    POWER_VOLT_AMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ELECTRIC_CURRENT_AMPERE,
    ENERGY_WATT_HOUR,
    CONF_HOST,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    CONF_UNIQUE_ID,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import slugify

from .api import WibeeeAPI
from .const import (DOMAIN, DEFAULT_SCAN_INTERVAL, DEFAULT_TIMEOUT)

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Wibeee Energy Consumption Sensor'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.time_period,
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.time_period,
    vol.Optional(CONF_UNIQUE_ID, default=True): cv.boolean
})

SENSOR_TYPES = {
    'vrms': ['Vrms', 'Phase Voltage', ELECTRIC_POTENTIAL_VOLT, DEVICE_CLASS_VOLTAGE],
    'irms': ['Irms', 'Current', ELECTRIC_CURRENT_AMPERE, DEVICE_CLASS_CURRENT],
    'frecuencia': ['Frequency', 'Frequency', FREQUENCY_HERTZ, None],
    'p_activa': ['Active_Power', 'Active Power', POWER_WATT, DEVICE_CLASS_POWER],
    'p_reactiva_ind': ['Inductive_Reactive_Power', 'Inductive Reactive Power', 'VArL', DEVICE_CLASS_POWER],
    'p_reactiva_cap': ['Capacitive_Reactive_Power', 'Capacitive Reactive Power', 'VArC', DEVICE_CLASS_POWER],
    'p_aparent': ['Apparent_Power', 'Apparent Power', POWER_VOLT_AMPERE, DEVICE_CLASS_POWER],
    'factor_potencia': ['Power_Factor', 'Power Factor', '', DEVICE_CLASS_POWER_FACTOR],
    'energia_activa': ['Active_Energy', 'Active Energy', ENERGY_WATT_HOUR, DEVICE_CLASS_ENERGY],
    'energia_reactiva_ind': ['Inductive_Reactive_Energy', 'Inductive Reactive Energy', 'VArLh', DEVICE_CLASS_ENERGY],
    'energia_reactiva_cap': ['Capacitive_Reactive_Energy', 'Capacitive Reactive Energy', 'VArCh', DEVICE_CLASS_ENERGY]
}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Import existing configuration from YAML."""
    _LOGGER.warning(
        "Loading Wibeee via platform setup is deprecated; Please remove it from the YAML configuration"
    )
    hass.async_create_task(hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=config,
    ))


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> bool:
    """Set up a Wibeee from a config entry."""
    _LOGGER.debug("Setting up Wibeee Sensors...")

    session = async_get_clientsession(hass)
    host = entry.data[CONF_HOST]
    scan_interval = entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    timeout = entry.data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)

    api = WibeeeAPI(session, host, min(timeout, scan_interval))
    device = await api.async_fetch_device_info(retries=5)
    status = await api.async_fetch_status(retries=10)

    sensors = WibeeeSensor.make_device_sensors(device, status)
    for sensor in sensors:
        _LOGGER.debug("Adding '%s' (unique_id=%s)", sensor, sensor.unique_id)
    async_add_entities(sensors, True)

    async def fetching_data(now=None):
        """Fetch from API and update sensors."""
        try:
            fetched = await api.async_fetch_status(retries=3)
            for s in sensors:
                s.update_from_status(fetched)
        except Exception as err:
            if now is None:
                raise PlatformNotReady from err

    _LOGGER.debug(f"Start polling {host} with scan_interval: {scan_interval}")
    remove_listener = async_track_time_interval(hass, fetching_data, scan_interval)
    hass.data[DOMAIN][entry.entry_id]['disposers'].update(fetch_status=remove_listener)

    _LOGGER.debug("Setup completed!")
    return True


class WibeeeSensor(SensorEntity):
    """Implementation of Wibeee sensor."""

    def __init__(self, device, xml_name: str, sensor_phase: str, sensor_type: str, sensor_value):
        """Initialize the sensor."""
        ha_name, friendly_name, unit, device_class = SENSOR_TYPES[sensor_type]
        [device_name, mac_addr] = [device['id'], device['mac_addr']]
        entity_id = slugify(f"{DOMAIN} {mac_addr} {friendly_name} L{sensor_phase}")
        self._xml_name = xml_name
        self._attr_native_unit_of_measurement = unit
        self._attr_native_value = sensor_value
        self._attr_available = True
        self._attr_state_class = STATE_CLASS_MEASUREMENT
        self._attr_device_class = device_class
        self._attr_unique_id = f"_{mac_addr}_{ha_name.lower()}_{sensor_phase}"
        self._attr_name = f"{device_name} {friendly_name} L{sensor_phase}"
        self._attr_should_poll = False
        self.entity_id = f"sensor.{entity_id}"  # we don't want this derived from the name

    @callback
    def update_from_status(self, status) -> None:
        """Updates this sensor from the fetched status."""
        if self.enabled:
            self._attr_native_value = status.get(self._xml_name, STATE_UNAVAILABLE)
            self._attr_available = self.state is not STATE_UNAVAILABLE
            self.async_schedule_update_ha_state()
            _LOGGER.debug("Updating '%s'", self)

    @staticmethod
    def make_device_sensors(device, status) -> list['WibeeeSensor']:
        """Returns a list of the sensors discovered on the device."""
        phase_values = [(key, value, key[4:].split("_", 1)) for key, value in status.items() if key.startswith('fase')]
        known_values = [(key, phase, stype, value) for (key, value, (phase, stype)) in phase_values]
        return [WibeeeSensor(device, key, phase, stype, value) for (key, phase, stype, value) in known_values if stype in SENSOR_TYPES]
