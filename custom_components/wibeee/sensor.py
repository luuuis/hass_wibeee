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
from urllib.parse import quote_plus

from homeassistant.util import slugify
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
    CONF_UNIQUE_ID,
    STATE_UNAVAILABLE,
)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.event import async_track_time_interval

import xmltodict

from homeassistant.helpers.aiohttp_client import async_get_clientsession

__version__ = '0.0.2'

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Wibeee Energy Consumption Sensor'
DEFAULT_HOST = ''
DEFAULT_SCAN_INTERVAL = timedelta(seconds=15)
DEFAULT_TIMEOUT = timedelta(seconds=10)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
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
    """Set up the RESTful sensor."""
    _LOGGER.debug("Setting up Wibeee Sensors...")

    host = config.get(CONF_HOST)

    # Create a WIBEEE DATA OBJECT
    scan_interval = config.get(CONF_SCAN_INTERVAL)
    timeout = config.get(CONF_TIMEOUT)
    unique_id = config.get(CONF_UNIQUE_ID)
    wibeee_data = WibeeeData(hass, host, unique_id, scan_interval, timeout)

    # Then make first call and get sensors
    await wibeee_data.set_sensors()

    _LOGGER.debug(f"Start polling {host} with scan_interval: {scan_interval}")
    async_track_time_interval(hass, wibeee_data.fetching_data, scan_interval)

    async_add_entities(wibeee_data.sensors, True)

    # Setup Completed
    _LOGGER.debug("Setup completed!")

    return True


class WibeeeSensor(SensorEntity):
    """Implementation of Wibeee sensor."""

    def __init__(self, wibeee_data, device, sensor_id, sensor_phase, status_xml_name, sensor_value):
        """Initialize the sensor."""
        ha_name, friendly_name, unit, device_class = SENSOR_TYPES[status_xml_name]
        [device_name, mac_addr] = [device['id'], device['mac_addr']] if device else ["Wibeee", None]
        entity_id = slugify(f"Wibeee {mac_addr} {friendly_name} L{sensor_phase}" if mac_addr else f"wibeee_Phase{sensor_phase}_{ha_name}")
        self._wibeee_data = wibeee_data
        self._sensor_id = sensor_id
        self._attr_unit_of_measurement = unit
        self._attr_state = sensor_value
        self._attr_available = True
        self._attr_state_class = STATE_CLASS_MEASUREMENT
        self._attr_device_class = device_class
        self._attr_unique_id = f"_{mac_addr}_{ha_name.lower()}_{sensor_phase}" if mac_addr else None
        self._attr_name = f"{device_name} {friendly_name} L{sensor_phase}"
        self._attr_should_poll = False
        self.entity_id = f"sensor.{entity_id}"  # we don't want this derived from the name


class WibeeeData(object):
    """Gets the latest data from Wibeee sensors."""

    def __init__(self, hass, host, unique_id, scan_interval, timeout):
        """Initialize the data object."""

        self.hass = hass
        self.host = host
        self.unique_id = unique_id
        self.timeout = min(timeout, scan_interval)
        self.min_wait = timedelta(milliseconds=100)
        self.max_wait = min(timedelta(seconds=5), scan_interval)
        _LOGGER.info("Initializing WibeeeData with host: %s, scan_interval: %s, timeout %s, max_wait: %s", host, scan_interval,
                     self.timeout, self.max_wait)

        self.session = async_get_clientsession(hass)

        self.sensors = None

    async def async_fetch_status(self, retries=0):
        """Fetches the status XML from Wibeee as a dict, optionally retries"""
        status = await self.async_fetch_url(f'http://{self.host}/en/status.xml', retries)
        return status["response"]

    async def async_fetch_device_info(self, retries):
        try:
            # <devices><id>WIBEEE</id></devices>
            devices = await self.async_fetch_url(f'http://{self.host}/services/user/devices.xml', retries)
            device_id = devices['devices']['id']
            # <values><variable><id>macAddr</id><value>11:11:11:11:11:11</value></variable></values>
            values = await self.async_fetch_url(f'http://{self.host}/services/user/values.xml?var={quote_plus(device_id)}.macAddr', retries)
            mac_addr = values['values']['variable']['value']
            return dict(id=device_id, mac_addr=mac_addr.replace(":", "").lower()) if device_id and mac_addr else None
        except Exception:
            _LOGGER.warning("Error getting device info, sensors will not have a unique ID", exc_info=True)
            return None

    async def async_fetch_url(self, url, retries=0):
        async def fetch_with_retries(try_n):
            if try_n > 0:
                wait = min(pow(2, try_n) * self.min_wait.total_seconds(), self.max_wait.total_seconds())
                _LOGGER.debug("Waiting %0.3fs to retry %s...", wait, url)
                await asyncio.sleep(wait)

            try:
                resp = await self.session.get(url, timeout=self.timeout.total_seconds())
                if resp.status != 200:
                    raise aiohttp.ClientResponseError(
                        resp.request_info,
                        resp.history,
                        status=resp.status,
                        message=resp.reason,
                        headers=resp.headers,
                    )

                xml_data = await resp.text()
                _LOGGER.debug("RAW Response from %s: %s)", url, xml_data)
                xml_as_dict = xmltodict.parse(xml_data)
                return xml_as_dict

            except Exception as exc:
                if try_n == retries:
                    retry_info = f' after {try_n} retries' if retries > 0 else ''
                    _LOGGER.error('Error getting %s%s: %s: %s', url, retry_info, exc.__class__.__name__, exc, exc_info=True)
                    return {}
                else:
                    _LOGGER.warning('Error getting %s, will retry. %s: %s', url, exc.__class__.__name__, exc, exc_info=True)
                    return await fetch_with_retries(try_n + 1)

        return await fetch_with_retries(0)

    async def set_sensors(self):
        """Make first Get call to Initialize sensor names"""
        device = await self.async_fetch_device_info(retries=5) if self.unique_id else None
        status = await self.async_fetch_status(retries=10)

        # Create tmp sensor array
        tmp_sensors = []

        for key, value in status.items():
            if key.startswith("fase"):
                try:
                    sensor_id = key
                    sensor_phase, sensor_name = key[4:].split("_", 1)
                    sensor_value = value

                    if sensor_name in SENSOR_TYPES:
                        sensor = WibeeeSensor(self, device, sensor_id, sensor_phase, sensor_name, sensor_value)
                        _LOGGER.debug("Adding '%s' (unique_id=%s)", sensor, sensor.unique_id)
                        tmp_sensors.append(sensor)
                except:
                    _LOGGER.error(f"Unable to create WibeeeSensor Entities for key {key} and value {value}", exc_info=True)

        # Add sensors
        self.sensors = tmp_sensors

    async def fetching_data(self, now=None):
        """ Function to fetch REST Data and transform XML to data to DICT format """
        try:
            fetched = await self.async_fetch_status(retries=3)
        except Exception as err:
            fetched = {}
            if now is None:
                raise PlatformNotReady from err

        self.updating_sensors(sensor_data=fetched)

    def updating_sensors(self, sensor_data):
        """Update all sensor states from sensor_data."""
        for sensor in self.sensors:
            if sensor.enabled:
                sensor._attr_state = sensor_data.get(sensor._sensor_id, STATE_UNAVAILABLE)
                sensor._attr_available = sensor.state is not STATE_UNAVAILABLE
                sensor.async_schedule_update_ha_state()
                _LOGGER.debug("Updating '%s'", sensor)
