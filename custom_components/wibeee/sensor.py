"""
Support for Energy consumption Sensors from Circutor via local Web API

Device's website: http://wibeee.circutor.com/
Documentation: https://github.com/luuuis/hass_wibeee/

"""

REQUIREMENTS = ["xmltodict"]

import logging
from collections import namedtuple
from datetime import timedelta

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import (ConfigEntry, SOURCE_IMPORT)
from homeassistant.const import (
    FREQUENCY_HERTZ,
    POWER_WATT,
    POWER_VOLT_AMPERE,
    POWER_VOLT_AMPERE_REACTIVE,
    ELECTRIC_POTENTIAL_VOLT,
    ELECTRIC_CURRENT_AMPERE,
    ENERGY_WATT_HOUR,
    CONF_HOST,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    CONF_UNIQUE_ID,
    STATE_UNAVAILABLE,
    PERCENTAGE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import StateType
from homeassistant.util import slugify

from .api import WibeeeAPI
from .const import (DOMAIN, DEFAULT_SCAN_INTERVAL, DEFAULT_TIMEOUT, CONF_NEST_PROXY_ENABLE)
from .nest import get_nest_proxy
from .util import short_mac

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Wibeee Energy Consumption Sensor'

# Not known in HA yet so we do as the Fronius integration.
#
# https://github.com/home-assistant/core/blob/75abf87611d8ad5627126a3fe09fdddc8402237c/homeassistant/components/fronius/sensor.py#L43
ENERGY_VOLT_AMPERE_REACTIVE_HOUR = 'varh'

ENERGY_CLASSES = [SensorDeviceClass.ENERGY, ENERGY_VOLT_AMPERE_REACTIVE_HOUR]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.time_period,
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.time_period,
    vol.Optional(CONF_UNIQUE_ID, default=True): cv.boolean
})


class SensorType(namedtuple('SensorType', [
    'status_xml_suffix',
    'nest_push_prefix',
    'unique_name',
    'friendly_name',
    'unit',
    'device_class',
])):
    """\
    SensorType: Wibeee supported sensor definition.

    status_xml_suffix - the suffix used for elements in `status.xml` output (e.g.: "vrms")
    nest_push_prefix  - optional prefix used in Wibeee Nest push requests such as receiverLeap (e.g.: "v")
    friendly_name     - used to build the sensor name and entity id (e.g.: "Phase Voltage")
    unique_name       - used to build the sensor unique_id (e.g.: "Vrms")
    unit              - unit to use for the sensor (e.g.: "V")
    device_class      - optional device class to use for the sensor (e.g.: "voltage")
    """


KNOWN_SENSORS = [
    SensorType('vrms', 'v', 'Vrms', 'Phase Voltage', ELECTRIC_POTENTIAL_VOLT, SensorDeviceClass.VOLTAGE),
    SensorType('irms', 'i', 'Irms', 'Current', ELECTRIC_CURRENT_AMPERE, SensorDeviceClass.CURRENT),
    SensorType('frecuencia', 'q', 'Frequency', 'Frequency', FREQUENCY_HERTZ, device_class=None),
    SensorType('p_activa', 'a', 'Active_Power', 'Active Power', POWER_WATT, SensorDeviceClass.POWER),
    SensorType('p_reactiva_ind', 'r', 'Inductive_Reactive_Power', 'Inductive Reactive Power', POWER_VOLT_AMPERE_REACTIVE, SensorDeviceClass.REACTIVE_POWER),
    SensorType('p_reactiva_cap', None, 'Capacitive_Reactive_Power', 'Capacitive Reactive Power', POWER_VOLT_AMPERE_REACTIVE, SensorDeviceClass.REACTIVE_POWER),
    SensorType('p_aparent', 'p', 'Apparent_Power', 'Apparent Power', POWER_VOLT_AMPERE, SensorDeviceClass.APPARENT_POWER),
    SensorType('factor_potencia', 'f', 'Power_Factor', 'Power Factor', '', SensorDeviceClass.POWER_FACTOR),
    SensorType('energia_activa', 'e', 'Active_Energy', 'Active Energy', ENERGY_WATT_HOUR, SensorDeviceClass.ENERGY),
    SensorType('energia_reactiva_ind', 'o', 'Inductive_Reactive_Energy', 'Inductive Reactive Energy', ENERGY_VOLT_AMPERE_REACTIVE_HOUR, SensorDeviceClass.ENERGY),
    SensorType('energia_reactiva_cap', None, 'Capacitive_Reactive_Energy', 'Capacitive Reactive Energy', ENERGY_VOLT_AMPERE_REACTIVE_HOUR, SensorDeviceClass.ENERGY),
]

KNOWN_MODELS = {
    'WBM': 'Wibeee 1Ph',
    'WBT': 'Wibeee 3Ph',
    'WTD': 'Wibeee 3Ph RN',
    'WX2': 'Wibeee MAX 2S',
    'WX3': 'Wibeee MAX 3S',
    'WXX': 'Wibeee MAX MS',
    'WBB': 'Wibeee BOX',
    'WB3': 'Wibeee BOX S3P',
    'W3P': 'Wibeee 3Ph 3W',
    'WGD': 'Wibeee GND',
    'WBP': 'Wibeee PLUG',
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


def create_sensors(device, status) -> list['WibeeeSensor']:
    xml_suffixes = {sensor_type.status_xml_suffix: sensor_type for sensor_type in KNOWN_SENSORS}
    phase_xml_suffixes = [(key[4:].split("_", 1), value) for key, value in status.items() if key.startswith('fase')]
    known_sensors = [(phase, xml_suffixes[suffix], value) for ((phase, suffix), value) in phase_xml_suffixes if suffix in xml_suffixes]

    return [WibeeeSensor(device, phase, sensor_type, initial_value) for (phase, sensor_type, initial_value) in known_sensors]


def update_sensors(sensors, update_source, lookup_key, data):
    sensors_with_updates = [s for s in sensors if lookup_key(s) in data]
    _LOGGER.debug('Received %d sensor values from %s: %s', len(sensors_with_updates), update_source, data, sensors_with_updates)
    for s in sensors_with_updates:
        value = data.get(lookup_key(s))
        s.update_value(value, update_source)


def setup_local_polling(hass: HomeAssistant, api: WibeeeAPI, sensors: list['WibeeeSensor'], scan_interval: timedelta):
    def status_xml_param(sensor: WibeeeSensor) -> str:
        return sensor.status_xml_param

    async def fetching_data(now=None):
        try:
            fetched = await api.async_fetch_status(retries=3)
            update_sensors(sensors, 'status.xml', status_xml_param, fetched)
        except Exception as err:
            if now is None:
                raise PlatformNotReady from err

    # update_sensors(sensors, 'initial status.xml', status_xml_param, initial_status)
    return async_track_time_interval(hass, fetching_data, scan_interval)


async def async_setup_local_push(hass: HomeAssistant, device, sensors: list['WibeeeSensor']):
    mac_address = device['macAddr']
    nest_proxy = await get_nest_proxy(hass)

    def nest_push_param(s: WibeeeSensor) -> str:
        return s.nest_push_param

    def on_pushed_data(pushed_data: dict) -> None:
        update_sensors(sensors, 'Nest push', nest_push_param, pushed_data)

    def unregister_listener():
        nest_proxy.unregister_device(mac_address)

    nest_proxy.register_device(mac_address, on_pushed_data)
    return unregister_listener


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> bool:
    """Set up a Wibeee from a config entry."""
    _LOGGER.debug(f"Setting up Wibeee Sensors for '{entry.unique_id}'...")

    session = async_get_clientsession(hass)
    host = entry.data[CONF_HOST]
    scan_interval = timedelta(seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL.total_seconds()))
    timeout = timedelta(seconds=entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT.total_seconds()))
    use_nest_proxy = entry.options.get(CONF_NEST_PROXY_ENABLE)

    if use_nest_proxy:
        # first set up the Nest proxy. it's important to do this first because the device will not respond to status.xml
        # calls if it is unable to push data up to Wibeee Nest, causing this integration to fail at start-up.
        await get_nest_proxy(hass)

    api = WibeeeAPI(session, host, min(timeout, scan_interval))
    device = await api.async_fetch_device_info(retries=5)
    initial_status = await api.async_fetch_status(retries=10)

    sensors = create_sensors(device, initial_status)
    for sensor in sensors:
        _LOGGER.debug("Adding '%s' (unique_id=%s)", sensor, sensor.unique_id)
    async_add_entities(sensors, True)

    disposers = hass.data[DOMAIN][entry.entry_id]['disposers']

    remove_fetch_listener = setup_local_polling(hass, api, sensors, scan_interval)
    disposers.update(fetch_status=remove_fetch_listener)

    if use_nest_proxy:
        remove_push_listener = await async_setup_local_push(hass, device, sensors)
        disposers.update(push_listener=remove_push_listener)

    _LOGGER.info(f"Setup completed for '{entry.unique_id}' (host={host}, scan_interval={scan_interval}, timeout={timeout})")
    return True


class WibeeeSensor(SensorEntity):
    """Implementation of Wibeee sensor."""

    def __init__(self, device, sensor_phase: str, sensor_type: SensorType, initial_value: StateType):
        """Initialize the sensor."""
        [device_name, mac_addr] = [device['id'], device['macAddr']]
        entity_id = slugify(f"{DOMAIN} {mac_addr} {sensor_type.friendly_name} L{sensor_phase}")
        self._attr_native_unit_of_measurement = sensor_type.unit
        self._attr_native_value = initial_value
        self._attr_available = True
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING if sensor_type.device_class in ENERGY_CLASSES else SensorStateClass.MEASUREMENT
        self._attr_device_class = sensor_type.device_class
        self._attr_unique_id = f"_{mac_addr}_{sensor_type.unique_name.lower()}_{sensor_phase}"
        self._attr_name = f"{device_name} {sensor_type.friendly_name} L{sensor_phase}"
        self._attr_should_poll = False
        self._attr_device_info = _make_device_info(device, sensor_phase)
        self.entity_id = f"sensor.{entity_id}"  # we don't want this derived from the name
        self.status_xml_param = f"fase{sensor_phase}_{sensor_type.status_xml_suffix}"
        self.nest_push_param = f"{sensor_type.nest_push_prefix}{sensor_phase}"

    @callback
    def update_value(self, value, update_source='') -> None:
        """Updates this sensor from the fetched status value."""
        if self.enabled:
            self._attr_native_value = value
            self._attr_available = self.state is not STATE_UNAVAILABLE
            self.async_schedule_update_ha_state()
            _LOGGER.debug("Updating from %s: %s", update_source, self)


def _make_device_info(device, sensor_phase) -> DeviceInfo:
    mac_addr = device['macAddr']
    is_clamp = sensor_phase != '4'

    device_name = f'Wibeee {short_mac(mac_addr)}'
    device_model = KNOWN_MODELS.get(device['model'], 'Wibeee Energy Meter')

    return DeviceInfo(
        # identifiers and links
        identifiers={(DOMAIN, f'{mac_addr}_L{sensor_phase}' if is_clamp else mac_addr)},
        via_device=(DOMAIN, f'{mac_addr}') if is_clamp else None,

        # and now for the humans :)
        name=device_name if not is_clamp else f"{device_name} Line {sensor_phase}",
        model=device_model if not is_clamp else f'{device_model} Clamp',
        manufacturer='Smilics',
        configuration_url=f"http://{device['ipAddr']}/" if not is_clamp else None,
        sw_version=f"{device['softVersion']}" if not is_clamp else None,
    )