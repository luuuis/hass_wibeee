"""
Support for Energy consumption Sensors from Circutor via local Web API

Vendor docs: https://support.wibeee.com/space/CH/184025089/XML
Documentation: https://github.com/luuuis/hass_wibeee/

"""
import logging
import re
from collections.abc import Iterable
from datetime import datetime, timedelta
from enum import Enum, unique
from types import MappingProxyType
from typing import NamedTuple, Optional, Callable, Any, TypeVar, Mapping

import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.device_registry as dr
import homeassistant.helpers.entity_registry as er
import homeassistant.helpers.issue_registry as ir
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
    EntityCategory,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfApparentPower,
    UnitOfReactivePower,
    UnitOfElectricPotential,
    UnitOfElectricCurrent,
    UnitOfEnergy,
    Platform,
)
from homeassistant.core import HomeAssistant, callback, CALLBACK_TYPE
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntry, DeviceRegistry
from homeassistant.helpers.entity import DeviceInfo as HassDeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.issue_registry import async_create_issue, async_delete_issue
from homeassistant.helpers.typing import StateType
from homeassistant.util.dt import as_local

from .api import WibeeeAPI, DeviceInfo, WibeeeID
from .const import (
    DOMAIN,
    DEFAULT_TIMEOUT,
    CONF_MAC_ADDRESS,
    CONF_NEST_UPSTREAM,
    CONF_WIBEEE_ID,
)
from .nest import get_nest_proxy
from .util import short_mac

_LOGGER = logging.getLogger(__name__)

T = TypeVar('T')

# Not known in HA yet so we do as the Fronius integration.
#
# https://github.com/home-assistant/core/blob/75abf87611d8ad5627126a3fe09fdddc8402237c/homeassistant/components/fronius/sensor.py#L43
ENERGY_VOLT_AMPERE_REACTIVE_HOUR = 'varh'

ENERGY_CLASSES = [SensorDeviceClass.ENERGY, ENERGY_VOLT_AMPERE_REACTIVE_HOUR]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_SCAN_INTERVAL, default=timedelta(seconds=0)): cv.time_period,
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.time_period,
    vol.Optional(CONF_UNIQUE_ID, default=True): cv.boolean
})


class SlotData(NamedTuple):
    poll_var_suffix: str
    """Slot alphanumeric suffix for use in APIs."""
    push_var_suffix: str
    """Slot numeric suffix for use in push vars."""
    unique_name_suffix: str
    """Slot numeric suffix for use internally in unique ids."""
    is_clamp: bool
    """Whether the slot corresponds to a clamp."""


@unique
class Slot(Enum):
    L1 = SlotData('1', '1', '1', is_clamp=True)
    L2 = SlotData('2', '2', '2', is_clamp=True)
    L3 = SlotData('3', '3', '3', is_clamp=True)
    Total = SlotData('t', '4', '4', is_clamp=False)
    Device = SlotData('', '', '5', is_clamp=False)


class SensorType(NamedTuple):
    """
    Wibeee supported sensor definition.
    """
    poll_var_prefix: str
    "prefix used for elements in `values.xml` output (e.g.: 'vrms')"
    push_var_prefix: str
    "prefix used in Wibeee Nest push requests such as receiverLeap (e.g.: 'v')"
    friendly_name: str
    "used to build the sensor name and entity id (e.g.: 'Phase Voltage')"
    unit: Optional[str] = None
    "unit to use for the sensor (e.g.: 'V')"
    device_class: Optional[str] = None
    "optional device class to use for the sensor (e.g.: 'voltage')"
    entity_category: Optional[EntityCategory] = None
    "optional entity category"
    slots: tuple[Slot] = (Slot.Total, Slot.L1, Slot.L2, Slot.L3)
    "slots where this sensor may be found"
    unique_name_override: Optional[str] = None
    "optional override used to build the sensor unique_id (e.g.: 'Vrms')"

    @property
    def unique_name(self: 'SensorType') -> str:
        return self.unique_name_override if self.unique_name_override else self.friendly_name.replace(' ', '_')

    @property
    def state_class(self: 'SensorType') -> SensorStateClass | None:
        if self.device_class in ENERGY_CLASSES:
            return SensorStateClass.TOTAL_INCREASING

        if self.unit or self.device_class:
            return SensorStateClass.MEASUREMENT

        return None


KNOWN_SENSORS = (
    # Energy sensors:
    SensorType('vrms', 'v', 'Phase Voltage', UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, unique_name_override='Vrms'),
    SensorType('irms', 'i', 'Current', UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, unique_name_override='Irms'),
    SensorType('freq', 'q', 'Frequency', UnitOfFrequency.HERTZ, SensorDeviceClass.FREQUENCY),
    SensorType('pac', 'a', 'Active Power', UnitOfPower.WATT, SensorDeviceClass.POWER),
    SensorType('preac', 'r', 'Reactive Power', UnitOfReactivePower.VOLT_AMPERE_REACTIVE, SensorDeviceClass.REACTIVE_POWER),
    SensorType('pap', 'p', 'Apparent Power', UnitOfApparentPower.VOLT_AMPERE, SensorDeviceClass.APPARENT_POWER),
    SensorType('fpot', 'f', 'Power Factor', None, SensorDeviceClass.POWER_FACTOR),
    SensorType('eac', 'e', 'Active Energy', UnitOfEnergy.WATT_HOUR, SensorDeviceClass.ENERGY),
    SensorType('ereactl', 'o', 'Inductive Reactive Energy', ENERGY_VOLT_AMPERE_REACTIVE_HOUR, ENERGY_VOLT_AMPERE_REACTIVE_HOUR),
    # Diagnostic sensors:
    SensorType('macAddr', 'mac', 'MAC Address', entity_category=EntityCategory.DIAGNOSTIC, slots=(Slot.Device,)),
    IP_SENSOR_TYPE := SensorType('ipAddr', 'ip', 'IP Address', entity_category=EntityCategory.DIAGNOSTIC, slots=(Slot.Device,)),
    SensorType('softVersion', 'soft', 'Firmware', entity_category=EntityCategory.DIAGNOSTIC, slots=(Slot.Device,)),
    SensorType('phasesSequence', 'ps', 'Phases Sequence', entity_category=EntityCategory.DIAGNOSTIC, slots=(Slot.Device,)),
)

KNOWN_MODELS: Mapping[str, str] = MappingProxyType({
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
})


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


def update_sensors(sensors: Iterable['WibeeeSensor'], update_source: str,
                   lookup_key: Callable[['WibeeeSensor'], str], data: dict[str, Any]):
    if _LOGGER.isEnabledFor(logging.DEBUG):
        sensors_with_updates = [s for s in sensors if lookup_key(s) in data]
        _LOGGER.debug('Received %d sensor values from %s: %s', len(sensors_with_updates), update_source, data)

    for s in sensors:
        value = data.get(lookup_key(s), STATE_UNAVAILABLE)
        s.update_value(value, update_source)


def setup_local_polling(hass: HomeAssistant, api: WibeeeAPI, wibeee_id: WibeeeID, sensors: list['WibeeeSensor'],
                        scan_interval: timedelta) -> CALLBACK_TYPE:
    if scan_interval.total_seconds() == 0:
        return lambda: None

    def poll_xml_param(sensor: WibeeeSensor) -> str:
        return sensor.status_xml_param

    async def fetching_data(now=None):
        fetched = {}
        try:
            fetched = await api.async_fetch_values(wibeee_id, retries=3)
        except Exception as err:
            if now is None:
                raise PlatformNotReady from err

        update_sensors(sensors, 'values.xml', poll_xml_param, fetched)

    return async_track_time_interval(hass, fetching_data, scan_interval)


async def async_setup_local_push(hass: HomeAssistant, entry: ConfigEntry, mac_address: str, sensors: list['WibeeeSensor']):
    nest_proxy = await get_nest_proxy(hass)
    update_devices = await _setup_update_devices_local_push(hass, entry)

    def on_pushed_data(pushed_data: dict) -> None:
        pushed_sensors = {s.unique_id: s for s in sensors if s.nest_push_param in pushed_data}
        update_sensors(pushed_sensors.values(), 'Nest push', lambda s: s.nest_push_param, pushed_data)
        update_devices(pushed_data)

    def unregister_listener():
        nest_proxy.unregister_device(mac_address)

    upstream = entry.options.get(CONF_NEST_UPSTREAM)
    nest_proxy.register_device(mac_address, on_pushed_data, upstream)
    return unregister_listener


async def _setup_update_devices_local_push(hass: HomeAssistant, entry: ConfigEntry) -> Callable[[dict[str, Any]], type(None)]:
    device_registry = dr.async_get(hass)
    update_devices = {d.id: str(d.identifiers) for d in dr.async_entries_for_config_entry(device_registry, entry.entry_id) if
                      d.configuration_url}
    ip_push_param = f"{IP_SENSOR_TYPE.push_var_prefix}{Slot.Device.value.push_var_suffix}"

    _LOGGER.debug('Registered devices to update from push param "%s": %s', ip_push_param, update_devices)

    async def _update_ip_address(ip_addr: str):
        for d_id, name in update_devices.items():
            configuration_url = _make_configuration_url(ip_addr)
            device_registry.async_update_device(d_id, configuration_url=configuration_url)
            _LOGGER.debug(f'Updated {name} (device_id={d_id}) with configuration_url={configuration_url}')

    def _update_devices(data: dict[str, Any]):
        if ip_push_param and ip_push_param in data:
            entry.async_create_task(hass, _update_ip_address(data[ip_push_param]), f'wibeee_update_device_{entry.entry_id}')

    return _update_devices


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> bool:
    """Set up a Wibeee from a config entry."""
    _LOGGER.debug(f"Setting up Wibeee Sensors for '{entry.unique_id}'...")

    session = async_get_clientsession(hass)
    host = entry.data[CONF_HOST]
    mac_addr = entry.data[CONF_MAC_ADDRESS]
    wibeee_id = entry.data[CONF_WIBEEE_ID]
    scan_interval = timedelta(seconds=0)
    timeout = timedelta(seconds=entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT.total_seconds()))

    # first set up the Nest proxy. it's important to do this first because the device will not respond to status.xml
    # calls if it is unable to push data up to Wibeee Nest, causing this integration to fail at start-up.
    await get_nest_proxy(hass)

    api = WibeeeAPI(session, host, timeout)

    async def create_fetched_entities() -> list['WibeeeSensor']:
        """Discover existing sensors using Wibeee APIs."""
        device = await api.async_fetch_device_info(retries=5)
        fetched_values = await api.async_fetch_values(device.id, retries=10)

        known_poll_var_slots = _known_sensor_slots(lambda sensor_type, slot: f"{sensor_type.poll_var_prefix}{slot.value.poll_var_suffix}")
        fetched_slots = {slot for v in fetched_values if v in known_poll_var_slots for _, slot in [known_poll_var_slots[v]]}
        non_clamp_slots = {s for s in fetched_slots if not s.value.is_clamp}

        devices = {slot: _make_device_info(device, slot, via_device=device if non_clamp_slots and slot.value.is_clamp else None)
                   for slot in fetched_slots}

        return [
            WibeeeSensor(mac_addr, device, slot, sensor_type, fetched_values.get(poll_var))
            for poll_var in fetched_values if poll_var in known_poll_var_slots
            for sensor_type, slot in [known_poll_var_slots[poll_var]]
            if (device := devices[slot])
        ]

    def rehydrate_saved_entities() -> list['WibeeeSensor']:
        """Attempt to restore previously-created sensors based on the Device and Entry registries without using Wibeee APIs."""
        device_registry = dr.async_get(hass)
        entity_registry = er.async_get(hass)

        # device | identifiers={(DOMAIN, f'{mac_addr}_L{sensor_phase}' if is_clamp else mac_addr)},
        reg_devices: dict[str, HassDeviceInfo] = {
            device_id: _rehydrate_device_info(device_registry, d)
            for d in dr.async_entries_for_config_entry(device_registry, entry.entry_id)
            if (ids := [i[1] for i in d.identifiers if i[0] == DOMAIN])
            for device_id in ids
        }

        known_unique_name_slots = _known_sensor_slots(lambda st, slot: f'{st.unique_name.lower()}_{slot.value.unique_name_suffix}')

        reg_sensors: list[WibeeeSensor] = [
            WibeeeSensor(device_mac_addr, device, slot, sensor_type, initial_value=None)
            for entity_entry in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
            if entity_entry.domain == Platform.SENSOR

            # sensor.unique_id = f"_{device_mac_addr}_{sensor_type.unique_name.lower()}_{sensor_phase}"
            if entity_entry.unique_id.count('_') >= 3
            for device_mac_addr, unique_name, slot_num_value in [re.search(r'_([^_]+)_(\w+)_(\d)', entity_entry.unique_id).groups()]
            if (unique_name_slot := f'{unique_name}_{slot_num_value}')

            if unique_name_slot in known_unique_name_slots
            for sensor_type, slot in [known_unique_name_slots[unique_name_slot]]

            if (device_id := f'{mac_addr}_L{slot.value.unique_name_suffix}' if slot.value.is_clamp else mac_addr)
            if device_id in reg_devices
            if (device := reg_devices[device_id])
        ]

        return reg_sensors

    sensors = rehydrate_saved_entities() or await create_fetched_entities()

    # Diag/Top sensors need to be added first because they are referenced by the other sensors.
    async_add_entities(sorted(sensors, key=lambda s: s.slot.value.unique_name_suffix, reverse=True), True)
    for sensor in sensors:
        _LOGGER.debug("Added '%s' (unique_id=%s)", sensor, sensor.unique_id)

    entry.async_on_unload(setup_local_polling(hass, api, wibeee_id, sensors, scan_interval))
    entry.async_on_unload(setup_repairs(hass, entry, sensors))
    entry.async_on_unload(await async_setup_local_push(hass, entry, mac_addr, sensors))

    _LOGGER.info(f"Setup completed for '{entry.unique_id}' (host={host}, mac_addr={mac_addr}, wibeee_id: {wibeee_id}, "
                 f"scan_interval={scan_interval}, timeout={timeout})")
    return True


def setup_repairs(hass: HomeAssistant, entry: ConfigEntry, sensors: list['WibeeeSensor']) -> CALLBACK_TYPE:
    issue_id = f'wibeee_stale_states_checker_{entry.entry_id}'
    stale_threshold = timedelta(minutes=1)

    async def check_for_stale_states(now: datetime):
        stale_cutoff_time = now - (stale_threshold * 1.5)
        stale_states = {sensor: state for sensor in sensors
                        if (state := hass.states.get(sensor.entity_id))
                        if state and state.last_reported < stale_cutoff_time}

        _LOGGER.debug("check_for_stale_states found %d stale states", len(stale_states))
        if stale_states:
            devices = [d for d in dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id) if not d.via_device_id]
            device_name = devices[0].name if devices else entry.data.get(CONF_WIBEEE_ID, "Wibeee")

            sensors_to_make_unavailable = [sensor for sensor in stale_states.keys() if sensor.available]
            if sensors_to_make_unavailable:
                update_sensors(sensors_to_make_unavailable, 'check_for_stale_states', lambda s: '', {})

            last_reported = max([state.last_reported for state in stale_states.values()])
            async_create_issue(hass, DOMAIN, issue_id,
                               is_fixable=False,
                               severity=ir.IssueSeverity.WARNING,
                               translation_key=f'local_push_not_received_all' if len(stale_states) == len(sensors)
                                               else 'local_push_not_received_partial',
                               translation_placeholders=dict(sensor_count=len(stale_states),
                                                             device_name=device_name,
                                                             last_reported=as_local(last_reported).ctime()),
                               learn_more_url='https://github.com/luuuis/hass_wibeee/tree/main?tab=readme-ov-file#-configuring-local-push')
        else:
            async_delete_issue(hass, DOMAIN, issue_id)

    return async_track_time_interval(hass, check_for_stale_states, stale_threshold * 2, name=issue_id)


class WibeeeSensor(SensorEntity):
    """Implementation of Wibeee sensor."""

    def __init__(self, mac_addr: str, device_info: HassDeviceInfo, slot: Slot, sensor_type: SensorType, initial_value: StateType):
        """Initialize the sensor."""
        self._attr_native_unit_of_measurement = sensor_type.unit
        self._attr_native_value = initial_value
        self._attr_available = True
        self._attr_state_class = sensor_type.state_class
        self._attr_device_class = sensor_type.device_class
        self._attr_entity_category = sensor_type.entity_category
        self._attr_unique_id = f"_{mac_addr}_{sensor_type.unique_name.lower()}_{slot.value.unique_name_suffix}"
        self._attr_name = f"{sensor_type.friendly_name}"
        self._attr_has_entity_name = True
        self._attr_should_poll = False
        self._attr_device_info = device_info
        self.slot = slot
        self.status_xml_param = f"{sensor_type.poll_var_prefix}{slot.value.poll_var_suffix}"
        self.nest_push_param = f"{sensor_type.push_var_prefix}{slot.value.push_var_suffix}"
        self.sensor_type = sensor_type

    @callback
    def update_value(self, value: StateType, update_source: str = '') -> None:
        """Updates this sensor from the fetched status value."""
        if self.enabled:
            self._attr_native_value = None if value is STATE_UNAVAILABLE else value
            self._attr_available = value is not STATE_UNAVAILABLE
            self.async_schedule_update_ha_state()
            _LOGGER.debug("Updating from %s: %s", update_source, self)


def _make_device_info(device: DeviceInfo, slot: Slot, via_device: DeviceInfo | None) -> HassDeviceInfo:
    mac_addr = device.macAddr
    is_clamp = slot.value.is_clamp

    unique_name = f'{device.id} {short_mac(device.macAddr)}'
    device_name = unique_name if not is_clamp else f'{unique_name} L{slot.value.poll_var_suffix}'
    device_model = KNOWN_MODELS.get(device.model, 'Wibeee Energy Meter')

    return HassDeviceInfo(
        # identifiers and links
        identifiers={(DOMAIN, f'{mac_addr}_L{slot.value.unique_name_suffix}' if is_clamp else mac_addr)},
        via_device=(DOMAIN, f'{via_device.macAddr}') if via_device else None,

        # and now for the humans :)
        name=device_name,
        model=device_model if not is_clamp else f'{device_model} Clamp',
        manufacturer='Smilics',
        configuration_url=_make_configuration_url(device.ipAddr) if not is_clamp else None,
        sw_version=f"{device.softVersion}" if not is_clamp else None,
    )


def _make_configuration_url(ip_addr: str) -> str:
    return f"http://{ip_addr}/"


def _rehydrate_device_info(device_registry: DeviceRegistry, d: DeviceEntry) -> HassDeviceInfo:
    via_device_id = device_registry.async_get(d.via_device_id)
    return HassDeviceInfo(identifiers=d.identifiers,
                          via_device=next(iter(via_device_id.identifiers)) if via_device_id else None,
                          name=d.name,
                          model=d.model,
                          manufacturer=d.manufacturer,
                          configuration_url=d.configuration_url,
                          sw_version=d.sw_version)


def _known_sensor_slots(make_key: Callable[[SensorType, Slot], T]) -> Mapping[T, tuple[SensorType, Slot]]:
    """Indexes all known (sensor type, slot) combinations by the provided function."""
    return MappingProxyType({make_key(sensor_type, slot): (sensor_type, slot)
                             for sensor_type in KNOWN_SENSORS
                             if sensor_type.poll_var_prefix and sensor_type.push_var_prefix
                             for slot in sensor_type.slots})
