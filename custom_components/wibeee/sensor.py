"""
Support for Energy consumption Sensors from Circutor via local Web API

Vendor docs: https://support.wibeee.com/space/CH/184025089/XML
Documentation: https://github.com/luuuis/hass_wibeee/

"""

REQUIREMENTS = ["xmltodict"]

import logging
from datetime import timedelta
from typing import NamedTuple, Optional

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
    CONF_HOST,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    CONF_UNIQUE_ID,
    STATE_UNAVAILABLE,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfApparentPower,
    UnitOfReactivePower,
    UnitOfElectricPotential,
    UnitOfElectricCurrent,
    UnitOfEnergy,
)
from homeassistant.core import HomeAssistant, callback, CALLBACK_TYPE
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo as HassDeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import StateType
from homeassistant.util import slugify

from .api import WibeeeAPI, DeviceInfo
from .const import (
    DOMAIN,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    CONF_NEST_UPSTREAM,
    NEST_PROXY_DISABLED,
)
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


class SensorType(NamedTuple):
    """
    Wibeee supported sensor definition.
    """
    poll_var_prefix: Optional[str]
    "prefix used for elements in `values.xml` output (e.g.: 'vrms')"
    push_var_prefix: Optional[str]
    "prefix used in Wibeee Nest push requests such as receiverLeap (e.g.: 'v')"
    unique_name: str
    "used to build the sensor unique_id (e.g.: 'Vrms')"
    friendly_name: str
    "used to build the sensor name and entity id (e.g.: 'Phase Voltage')"
    unit: Optional[str]
    "unit to use for the sensor (e.g.: 'V')"
    device_class: Optional[str]
    "optional device class to use for the sensor (e.g.: 'voltage')"


KNOWN_SENSORS = [
    SensorType('vrms', 'v', 'Vrms', 'Phase Voltage', UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE),
    SensorType('irms', 'i', 'Irms', 'Current', UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT),
    SensorType('freq', 'q', 'Frequency', 'Frequency', UnitOfFrequency.HERTZ, device_class=None),
    SensorType('pac', 'a', 'Active_Power', 'Active Power', UnitOfPower.WATT, SensorDeviceClass.POWER),
    SensorType('preac', 'r', 'Reactive_Power', 'Reactive Power', UnitOfReactivePower.VOLT_AMPERE_REACTIVE, SensorDeviceClass.REACTIVE_POWER),
    SensorType(None, 'r', 'Inductive_Reactive_Power', 'Inductive Reactive Power', UnitOfReactivePower.VOLT_AMPERE_REACTIVE, SensorDeviceClass.REACTIVE_POWER),
    SensorType(None, None, 'Capacitive_Reactive_Power', 'Capacitive Reactive Power', UnitOfReactivePower.VOLT_AMPERE_REACTIVE, SensorDeviceClass.REACTIVE_POWER),
    SensorType('pap', 'p', 'Apparent_Power', 'Apparent Power', UnitOfApparentPower.VOLT_AMPERE, SensorDeviceClass.APPARENT_POWER),
    SensorType('fpot', 'f', 'Power_Factor', 'Power Factor', None, SensorDeviceClass.POWER_FACTOR),
    SensorType('eac', 'e', 'Active_Energy', 'Active Energy', UnitOfEnergy.WATT_HOUR, SensorDeviceClass.ENERGY),
    SensorType('eaccons', None, 'Active_Energy_Consumed', 'Active Energy Consumed', UnitOfEnergy.WATT_HOUR, SensorDeviceClass.ENERGY),
    SensorType('eacprod', None, 'Active_Energy_Produced', 'Active Energy Produced', UnitOfEnergy.WATT_HOUR, SensorDeviceClass.ENERGY),
    SensorType('ereact', 'o', 'Inductive_Reactive_Energy', 'Inductive Reactive Energy', ENERGY_VOLT_AMPERE_REACTIVE_HOUR, ENERGY_VOLT_AMPERE_REACTIVE_HOUR),
    SensorType('ereactc', None, 'Capacitive_Reactive_Energy', 'Capacitive Reactive Energy', ENERGY_VOLT_AMPERE_REACTIVE_HOUR, ENERGY_VOLT_AMPERE_REACTIVE_HOUR),
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

_PH4 = '4'
"""A pseudo-phase that holds the overall metric in 3-phase devices."""


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


class StatusElement(NamedTuple):
    phase: str
    xml_name: str
    sensor_type: SensorType


def get_status_elements() -> list[StatusElement]:
    """Returns the expected elements in the status XML response for this device."""

    def get_xml_names(s: SensorType) -> list[(str, str)]:
        return [(_PH4 if ph == 't' else ph, f"{s.poll_var_prefix}{ph}") for ph in ['1', '2', '3', 't']]

    return [
        StatusElement(phase, xml_name, sensor_type)
        for sensor_type in KNOWN_SENSORS if sensor_type.poll_var_prefix is not None
        for phase, xml_name in get_xml_names(sensor_type)
    ]


def update_sensors(sensors, update_source, lookup_key, data):
    if _LOGGER.isEnabledFor(logging.DEBUG):
        sensors_with_updates = [s for s in sensors if lookup_key(s) in data]
        _LOGGER.debug('Received %d sensor values from %s: %s', len(sensors_with_updates), update_source, data)

    for s in sensors:
        value = data.get(lookup_key(s), STATE_UNAVAILABLE)
        s.update_value(value, update_source)


def setup_local_polling(hass: HomeAssistant, api: WibeeeAPI, device: DeviceInfo, sensors: list['WibeeeSensor'], scan_interval: timedelta) -> CALLBACK_TYPE:
    if scan_interval.total_seconds() == 0:
        return lambda: None

    def poll_xml_param(sensor: WibeeeSensor) -> str:
        return sensor.status_xml_param

    async def fetching_data(now=None):
        fetched = {}
        try:
            fetched = await api.async_fetch_values(device.id, retries=3)
        except Exception as err:
            if now is None:
                raise PlatformNotReady from err

        update_sensors(sensors, 'values.xml', poll_xml_param, fetched)

    return async_track_time_interval(hass, fetching_data, scan_interval)


async def async_setup_local_push(hass: HomeAssistant, entry: ConfigEntry, device: DeviceInfo, sensors: list['WibeeeSensor']):
    mac_address = device.macAddr
    nest_proxy = await get_nest_proxy(hass)

    def on_pushed_data(pushed_data: dict) -> None:
        pushed_sensors = [s for s in sensors if s.nest_push_param in pushed_data]
        update_sensors(pushed_sensors, 'Nest push', lambda s: s.nest_push_param, pushed_data)

    def unregister_listener():
        nest_proxy.unregister_device(mac_address)

    upstream = entry.options.get(CONF_NEST_UPSTREAM)
    nest_proxy.register_device(mac_address, on_pushed_data, upstream)
    return unregister_listener


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> bool:
    """Set up a Wibeee from a config entry."""
    _LOGGER.debug(f"Setting up Wibeee Sensors for '{entry.unique_id}'...")

    session = async_get_clientsession(hass)
    host = entry.data[CONF_HOST]
    scan_interval = timedelta(seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL.total_seconds()))
    timeout = timedelta(seconds=entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT.total_seconds()))
    use_nest_proxy = entry.options.get(CONF_NEST_UPSTREAM, NEST_PROXY_DISABLED) != NEST_PROXY_DISABLED

    if use_nest_proxy:
        # first set up the Nest proxy. it's important to do this first because the device will not respond to status.xml
        # calls if it is unable to push data up to Wibeee Nest, causing this integration to fail at start-up.
        await get_nest_proxy(hass)

    api = WibeeeAPI(session, host, min(timeout, scan_interval))
    device = await api.async_fetch_device_info(retries=5)
    fetched_values = await api.async_fetch_values(device.id, retries=10)
    status_elements = [e for e in get_status_elements() if e.xml_name in fetched_values]

    phases = [e.phase for e in status_elements]
    via_device = device if _PH4 in phases else None
    devices = {phase: _make_device_info(device, phase, via_device=via_device if phase != _PH4 else None) for phase in phases}

    sensors = [
        WibeeeSensor(device, devices[e.phase], e.phase, e.sensor_type, e.xml_name, fetched_values.get(e.xml_name))
        for e in reversed(sorted(status_elements, key=lambda e: e.phase))  # ensure "total" sensors are added first
    ]

    for sensor in sensors:
        _LOGGER.debug("Adding '%s' (unique_id=%s)", sensor, sensor.unique_id)
    async_add_entities(sensors, True)

    disposers = hass.data[DOMAIN][entry.entry_id]['disposers']

    remove_fetch_listener = setup_local_polling(hass, api, device, sensors, scan_interval)
    disposers.update(fetch_status=remove_fetch_listener)

    if use_nest_proxy:
        remove_push_listener = await async_setup_local_push(hass, entry, device, sensors)
        disposers.update(push_listener=remove_push_listener)

    _LOGGER.info(f"Setup completed for '{entry.unique_id}' (host={host}, scan_interval={scan_interval}, timeout={timeout})")
    return True


class WibeeeSensor(SensorEntity):
    """Implementation of Wibeee sensor."""

    def __init__(self, device: DeviceInfo, device_info: HassDeviceInfo, sensor_phase: str, sensor_type: SensorType, status_xml_param: str,
                 initial_value: StateType):
        """Initialize the sensor."""
        [device_name, mac_addr] = [device.id, device.macAddr]
        entity_id = slugify(f"{DOMAIN} {mac_addr} {sensor_type.friendly_name} L{sensor_phase}")
        self._attr_native_unit_of_measurement = sensor_type.unit
        self._attr_native_value = initial_value
        self._attr_available = True
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING if sensor_type.device_class in ENERGY_CLASSES else SensorStateClass.MEASUREMENT
        self._attr_device_class = sensor_type.device_class
        self._attr_unique_id = f"_{mac_addr}_{sensor_type.unique_name.lower()}_{sensor_phase}"
        self._attr_name = f"{device_name} {sensor_type.friendly_name} L{sensor_phase}"
        self._attr_should_poll = False
        self._attr_device_info = device_info
        self.entity_id = f"sensor.{entity_id}"  # we don't want this derived from the name
        self.status_xml_param = status_xml_param
        self.nest_push_param = f"{sensor_type.push_var_prefix}{'t' if sensor_phase == _PH4 else sensor_phase}"

    @callback
    def update_value(self, value: StateType, update_source: str = '') -> None:
        """Updates this sensor from the fetched status value."""
        if self.enabled:
            self._attr_native_value = value
            self._attr_available = value is not STATE_UNAVAILABLE
            self.async_schedule_update_ha_state()
            _LOGGER.debug("Updating from %s: %s", update_source, self)


def _make_device_info(device: DeviceInfo, sensor_phase: str, via_device: DeviceInfo | None) -> HassDeviceInfo:
    mac_addr = device.macAddr
    is_clamp = sensor_phase != _PH4

    device_name = f'Wibeee {short_mac(mac_addr)}'
    device_model = KNOWN_MODELS.get(device.model, 'Wibeee Energy Meter')

    return HassDeviceInfo(
        # identifiers and links
        identifiers={(DOMAIN, f'{mac_addr}_L{sensor_phase}' if is_clamp else mac_addr)},
        via_device=(DOMAIN, f'{via_device.macAddr}') if via_device else None,

        # and now for the humans :)
        name=device_name if not is_clamp else f"{device_name} Line {sensor_phase}",
        model=device_model if not is_clamp else f'{device_model} Clamp',
        manufacturer='Smilics',
        configuration_url=f"http://{device.ipAddr}/" if not is_clamp else None,
        sw_version=f"{device.softVersion}" if not is_clamp else None,
    )
