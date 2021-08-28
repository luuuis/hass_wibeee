"""
Support for Energy consumption Sensors from Circutor via local Web API

Device's website: http://wibeee.circutor.com/
Documentation: https://github.com/luuuis/hass_wibeee/

"""

REQUIREMENTS = ["xmltodict"]

import aiohttp
import asyncio
import logging
import voluptuous as vol
from datetime import timedelta

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
    CONF_TIMEOUT,
)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.event import async_track_time_interval

import xmltodict

from homeassistant.helpers.aiohttp_client import async_get_clientsession

__version__ = '0.0.2'

_LOGGER = logging.getLogger(__name__)

BASE_URL = 'http://{0}:{1}/{2}'
PORT = 80
API_PATH = 'en/status.xml'

DOMAIN = 'wibeee_energy'
DEFAULT_NAME = 'Wibeee Energy Consumption Sensor'
DEFAULT_HOST = ''
DEFAULT_RESOURCE = 'http://{}/en/status.xml'
DEFAULT_SCAN_INTERVAL = timedelta(seconds=15)
DEFAULT_TIMEOUT = timedelta(seconds=10)
DEFAULT_PHASES = 3

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.time_period,
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.time_period,
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
    scan_interval = config.get(CONF_SCAN_INTERVAL)
    timeout = config.get(CONF_TIMEOUT)
    wibeee_data = WibeeeData(hass, sensor_name_suffix, url_api, scan_interval, timeout)

    # Then make first call and get sensors
    await wibeee_data.set_sensors()

    _LOGGER.debug(f"Start polling {url_api} with scan_interval: {scan_interval}")
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

    def __init__(self, hass, sensor_name_suffix, url_api, scan_interval, timeout):
        """Initialize the data object."""

        self.hass = hass
        self.sensor_name_suffix = sensor_name_suffix
        self.url_api = url_api
        self.timeout = min(timeout, scan_interval)
        self.min_wait = timedelta(milliseconds=100)
        self.max_wait = min(timedelta(seconds=5), scan_interval)
        _LOGGER.info("Initializing WibeeeData with url: %s, scan_interval: %s, timeout %s, max_wait: %s", url_api, scan_interval,
                     self.timeout, self.max_wait)

        self.session = async_get_clientsession(hass)

        self.sensors = None
        self.data = None
        self.ready = asyncio.Event()

    async def async_fetch_status(self, retries=0):
        """Fetches the status XML from Wibeee as a dict, optionally retries"""

        async def fetch_with_retries(try_n):
            if try_n > 0:
                wait = min(pow(2, try_n) * self.min_wait.total_seconds(), self.max_wait.total_seconds())
                _LOGGER.debug("Waiting %0.3fs to retry %s...", wait, self.url_api)
                await asyncio.sleep(wait)

            try:
                resp = await self.session.get(self.url_api, timeout=self.timeout.total_seconds())
                if resp.status != 200:
                    raise aiohttp.ClientResponseError(
                        resp.request_info,
                        resp.history,
                        status=resp.status,
                        message=resp.reason,
                        headers=resp.headers,
                    )

                xml_data = await resp.text()
                _LOGGER.debug("RAW Response from %s: %s)", self.url_api, xml_data)
                dict_data = xmltodict.parse(xml_data)
                return dict_data["response"]

            except Exception as exc:
                if try_n == retries:
                    retry_info = f' after {try_n} retries' if retries > 0 else ''
                    _LOGGER.error('Error getting %s%s: %s: %s', self.url_api, retry_info, exc.__class__.__name__, exc, exc_info=True)
                    raise
                else:
                    _LOGGER.warning('Error getting %s, will retry. %s: %s', self.url_api, exc.__class__.__name__, exc, exc_info=True)
                    return await fetch_with_retries(try_n=try_n + 1)

        return await fetch_with_retries(try_n=0)

    async def set_sensors(self):
        """Make first Get call to Initialize sensor names"""
        self.data = await self.async_fetch_status(retries=10)

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

    async def fetching_data(self, now=None):
        """ Function to fetch REST Data and transform XML to data to DICT format """
        try:
            self.data = await self.async_fetch_status(retries=3)
        except Exception as err:
            if now is not None:
                self.ready.clear()
                return
            raise PlatformNotReady from err

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
