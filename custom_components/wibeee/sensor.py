"""
Support for Energy consumption Sensors from Circutor via local Web API

Device's website: http://wibeee.circutor.com/
Documentation: https://github.com/luuuis/hass_wibeee/

"""

REQUIREMENTS = ["xmltodict"]

import asyncio

import logging
import voluptuous as vol
from datetime import timedelta

import aiohttp
import async_timeout

import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
)

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
)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.event import async_track_time_interval

import xmltodict

from homeassistant.helpers.aiohttp_client import async_get_clientsession

__version__ = '0.0.2'

_LOGGER = logging.getLogger(__name__)


BASE_URL = 'http://{0}:{1}/{2}'
PORT=80
API_PATH = 'en/status.xml'


DOMAIN = 'wibeee_energy'
DEFAULT_NAME = 'Wibeee Energy Consumption Sensor'
DEFAULT_HOST = ''
DEFAULT_RESOURCE = 'http://{}/en/status.xml'
DEFAULT_SCAN_INTERVAL = timedelta(seconds=15)
DEFAULT_PHASES = 3

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.time_period,
})

SENSOR_TYPES = {
    'vrms': ['Vrms', ELECTRIC_POTENTIAL_VOLT, DEVICE_CLASS_VOLTAGE],
    'irms': ['Irms', ELECTRIC_CURRENT_AMPERE, DEVICE_CLASS_CURRENT],
    'frecuencia': ['Frequency', FREQUENCY_HERTZ, None],
    'p_activa': ['Active Power', POWER_WATT, DEVICE_CLASS_POWER],
    'p_reactiva_ind': ['Inductive Reactive Power', 'VArL', DEVICE_CLASS_POWER],
    'p_reactiva_cap': ['Capacitive Reactive Power', 'VArC', DEVICE_CLASS_POWER],
    'p_aparent': ['Apparent Power', POWER_VOLT_AMPERE, DEVICE_CLASS_POWER],
    'factor_potencia': ['Power Factor', '', DEVICE_CLASS_POWER_FACTOR],
    'energia_activa': ['Active Energy', ENERGY_WATT_HOUR, DEVICE_CLASS_ENERGY],
    'energia_reactiva_ind': ['Inductive Reactive Energy', 'VArLh', DEVICE_CLASS_ENERGY],
    'energia_reactiva_cap': ['Capacitive Reactive Energy', 'VArCh', DEVICE_CLASS_ENERGY]
}

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the RESTful sensor."""
    _LOGGER.debug("Setting up Wibeee Sensors...")

    sensor_name_suffix = "wibeee"
    host = config.get(CONF_HOST)
    url_api = BASE_URL.format(host, PORT, API_PATH)

    # Create a WIBEEE DATA OBJECT
    wibeee_data = WibeeeData(hass, sensor_name_suffix, url_api)

    # Then make first call and get sensors
    await wibeee_data.set_sensors()

    scan_interval = config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    _LOGGER.info(f"Start polling {url_api} with scan_interval: {scan_interval}")
    async_track_time_interval(hass, wibeee_data.fetching_data, scan_interval)

    # Add Entities
    if not wibeee_data.sensors:
        raise PlatformNotReady
    if not wibeee_data.data:
        raise PlatformNotReady

    async_add_entities(wibeee_data.sensors, True)

    # Setup Completed
    _LOGGER.debug("Setup completed!")

    return True


class WibeeeSensor(SensorEntity):
    """Implementation of Wibeee sensor."""

    def __init__(self, wibeee_data, name_prefix, sensor_id, sensor_phase, sensor_name, sensor_value):
        """Initialize the sensor."""
        friendly_name, unit, device_class = SENSOR_TYPES[sensor_name]
        self._wibeee_data = wibeee_data
        self._entity = sensor_id
        self._name_prefix = name_prefix
        self._sensor_phase = "Phase" + sensor_phase
        self._sensor_name = friendly_name.replace(" ", "_")
        self._unit_of_measurement = unit
        self._state = sensor_value
        self._attr_state_class = STATE_CLASS_MEASUREMENT
        self._attr_device_class = device_class

    @property
    def name(self):
        """Return the name of the sensor."""
        # -> friendly_name
        return self._name_prefix + "_" + self._sensor_phase + "_" + self._sensor_name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def should_poll(self):
        """No polling needed."""
        return False


class WibeeeData(object):
    """Gets the latest data from Wibeee sensors."""
    def __init__(self, hass, sensor_name_suffix, url_api):
        """Initialize the data object."""
        _LOGGER.debug("Initializating WibeeeData with url:%s", url_api)

        self.hass = hass
        self.sensor_name_suffix = sensor_name_suffix
        self.url_api = url_api

        self.timeout = 10
        self.session = async_get_clientsession(hass)

        self.sensors = None
        self.data = None


    async def set_sensors(self):
        """Make first Get call to Initialize sensor names"""
        try:
            with async_timeout.timeout(10, loop=self.hass.loop):
                resp = await self.session.get(self.url_api)
            resp.raise_for_status()
            if resp.status != 200:
                try_again("{} returned {}".format(self.url_api, resp.status))
                return(None)
            else:
                xml_data = await resp.text()
                _LOGGER.debug("RAW Response from %s: %s)", self.url_api, xml_data)
                dict_data = xmltodict.parse(xml_data)
                self.data = dict_data["response"]
                _LOGGER.debug("Dict Response: %s)", self.data)
        except ValueError as error:
            raise ValueError("Unable to obtain any response from %s, %s", self.url_api, error)

        # Create tmp sensor array
        tmp_sensors = []

        for key, value in self.data.items():
            if key.startswith("fase"):
                try:
                    _LOGGER.debug("Processing sensor [key:%s] [value:%s]", key, value)
                    sensor_id = key
                    sensor_phase, sensor_name = key[4:].split("_", 1)
                    sensor_value = value

                    _LOGGER.debug("Adding entity [phase:%s][sensor:%s][value:%s]", sensor_phase, sensor_id, sensor_value)
                    if sensor_name in SENSOR_TYPES:
                        tmp_sensors.append(WibeeeSensor(self, self.sensor_name_suffix, sensor_id, sensor_phase, sensor_name, sensor_value))
                except:
                    _LOGGER.error(f"Unable to create WibeeeSensor Entities for key {key} and value {value}")

        # Add sensors
        self.sensors = tmp_sensors


    #@Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def fetching_data(self, *_):
        """ Function to fetch REST Data and transform XML to data to DICT format """
        try:
            with async_timeout.timeout(10, loop=self.hass.loop):
                resp = await self.session.get(self.url_api)
            resp.raise_for_status()
            if resp.status != 200:
                try_again("{} returned {}".format(self.url_api, resp.status))
                return(None)
            else:
                xml_data = await resp.text()
                dict_data = xmltodict.parse(xml_data)
                self.data = dict_data["response"]
        except (requests.exceptions.HTTPError, aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
            _LOGGER.error('{}: {}'.format(exc.__class__.__name__, str(exc)))
            return(None)
        except:
            _LOGGER.error('unexpected exception for get %s', self.url_api)
            return(None)

        self.updating_sensors()


    def updating_sensors(self, *_):
        """Find the current data from self.data."""
        if not self.data:
            return

        # Update all sensors
        for sensor in self.sensors:
            new_state = None
            if self.data[sensor._entity]:
                sensor._state = self.data[sensor._entity]
                sensor.async_schedule_update_ha_state()
                _LOGGER.debug("[sensor:%s] %s)", sensor._entity, sensor._state)
