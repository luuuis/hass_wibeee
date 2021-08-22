"""
Support for Energy consumption Sensors from Circutor via local Web API

Device's website: http://wibeee.circutor.com/
Documentation: https://github.com/juanjoSanz/hass_wibeee/

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
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    POWER_WATT,
    ENERGY_KILO_WATT_HOUR,
    ENERGY_WATT_HOUR,
    CONF_HOST,
    CONF_SCAN_INTERVAL,
    CONF_RESOURCE,
    CONF_METHOD,
    ATTR_ATTRIBUTION
)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.event import async_track_time_interval

import xmltodict

ATTRIBUTION = (
    "Circutor's energy consumption sensor"
)

DOMAIN="WIBEEE"

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity

__version__ = '0.0.2'

_LOGGER = logging.getLogger(__name__)


BASE_URL = 'http://{0}:{1}/{2}'
PORT=80
API_PATH = 'en/status.xml'


DOMAIN = 'wibeee_energy'
DEFAULT_NAME = 'Wibeee Energy Consumption Sensor'
DEFAULT_HOST = ''
DEFAULT_RESOURCE = 'http://{}/en/status.xml'
DEFAULT_SCAN_INTERVAL = 60
DEFAULT_PHASES = 3

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_RESOURCE, default=DEFAULT_RESOURCE): cv.string,
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.positive_int,
})

SCAN_INTERVAL = timedelta(seconds=15)

SENSOR_TYPES = {
    'vrms': ['Vrms', 'V'],
    'irms': ['Irms', 'A'],
    'frecuencia': ['Frequency', 'Hz'],
    'p_activa': ['Active Power', POWER_WATT],
    'p_reactiva_ind': ['Inductive Reactive Power', 'VArL'],
    'p_reactiva_cap': ['Capacitive Reactive Power', 'VArC'],
    'p_aparent': ['Apparent Power', 'VA'],
    'factor_potencia': ['Power Factor', ''],
    'energia_activa': ['Active Energy', ENERGY_WATT_HOUR],
    'energia_reactiva_ind': ['Inductive Reactive Energy', 'VArLh'],
    'energia_reactiva_cap': ['Capacitive Reactive Energy', 'VArCh']
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

    async_track_time_interval(hass, wibeee_data.fetching_data, SCAN_INTERVAL)

    # Add Entities
    if not wibeee_data.sensors:
        raise PlatformNotReady
    if not wibeee_data.data:
        raise PlatformNotReady

    async_add_entities(wibeee_data.sensors, True)

    # Setup Completed
    _LOGGER.debug("Setup completed!")

    return True


class WibeeeSensor(Entity):
    """Implementation of Wibeee sensor."""

    def __init__(self, wibeee_data, name, sensor_id, sensor_phase, sensor_name, sensor_value):
        """Initialize the sensor."""
        self._wibeee_data = wibeee_data
        self._entity = sensor_id
        self._type = name
        self._sensor_phase = "Phase" + sensor_phase
        self._sensor_name = SENSOR_TYPES[sensor_name][0].replace(" ", "_")
        self._unit_of_measurement = SENSOR_TYPES[sensor_name][1]
        self._state = sensor_value
        self._icon = None

    @property
    def name(self):
        """Return the name of the sensor."""
        # -> friendly_name
        return self._type + "_" + self._sensor_phase + "_" + self._sensor_name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return self._icon

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        state_attr = {ATTR_ATTRIBUTION: ATTRIBUTION}
        return state_attr

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return 


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

        for key,value in self.data.items():
          try:
            _LOGGER.debug("Processing sensor [key:%s] [value:%s]", key, value)  
            sensor_id = key
            sensor_phase,sensor_name = key.split("_",1)
            sensor_phase = sensor_phase.replace("fase","")
            sensor_value = value
            _LOGGER.debug("Adding entity [phase:%s][sensor:%s][value:%s]", sensor_phase, sensor_id, sensor_value)
            tmp_sensors.append(WibeeeSensor(self, self.sensor_name_suffix, sensor_id, sensor_phase, sensor_name,sensor_value))
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
