import logging
from typing import Dict
from unittest.mock import patch

import homeassistant.helpers.entity_registry as er
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry, entity_registry
from homeassistant.helpers.entity_platform import EntityPlatform
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components import wibeee
from custom_components.wibeee.api import WibeeeAPI
from custom_components.wibeee.sensor import DeviceInfo, WibeeeSensor, KNOWN_SENSORS, SlotNum


def _build_values(info: DeviceInfo, sensor_values: Dict[str, any]) -> Dict[str, any]:
    return {
        'id': info.id,
        'softVersion': info.softVersion,
        'ipAddr': info.ipAddr,
        'macAddr': info.macAddr,
    } | sensor_values


@patch.object(WibeeeAPI, 'async_fetch_values', autospec=True)
@patch.object(WibeeeAPI, 'async_fetch_device_info', autospec=True)
@patch.object(EntityPlatform, 'async_add_entities', wraps=EntityPlatform.async_add_entities, autospec=True)
async def test_sensor_ids_and_names(spy_async_add_entities, mock_async_fetch_device_info, mock_async_fetch_values, hass: HomeAssistant):
    devices_data = [
        [
            DeviceInfo('Wibeee', 'xxxxxx1paabb', '10.9.8', 'WBM', '1.2.3.4'),
            {'vrms1': '230', 'pac1': '10000'},
        ], [
            DeviceInfo('Wibeee', 'xxxxxx3pccdd', '7.6.5', 'WBT', '4.3.2.1'),
            {'vrms1': '200', 'vrmst': '1000'},
        ],
    ]

    entries = [MockConfigEntry(domain='wibeee', version=4, data={'host': info.ipAddr, 'mac_address': info.macAddr, 'wibeee_id': info.id})
               for info, sensors in devices_data]

    def assert_via_devices():
        # ensure via_device is correct, HA will start to fail if not.
        registry_devices = [re for e in entries for re in async_devices_for_config_entry(hass, e)]
        via_devices = {re.name: re.via_device_id for re in registry_devices}
        device_ids = {re.name: re.id for re in registry_devices}

        assert via_devices == {
            'Wibeee 3PCCDD': None,
            'Wibeee 3PCCDD L1': device_ids.get('Wibeee 3PCCDD', 'missing id for device'),
            'Wibeee 1PAABB': None,
            'Wibeee 1PAABB L1': device_ids.get('Wibeee 1PAABB', 'missing id for device'),
        }

    def assert_unique_ids():
        reg_entries = [reg_e for conf_e in entries for reg_e in async_entities_for_config_entry(hass, conf_e)]

        unique_ids = {reg_e.entity_id: reg_e.unique_id for reg_e in reg_entries}
        assert unique_ids == {
            'sensor.wibeee_1paabb_firmware': '_xxxxxx1paabb_firmware_5',
            'sensor.wibeee_1paabb_mac_address': '_xxxxxx1paabb_mac_address_5',
            'sensor.wibeee_1paabb_ip_address': '_xxxxxx1paabb_ip_address_5',
            'sensor.wibeee_1paabb_l1_active_power': '_xxxxxx1paabb_active_power_1',
            'sensor.wibeee_1paabb_l1_phase_voltage': '_xxxxxx1paabb_vrms_1',

            'sensor.wibeee_3pccdd_firmware': '_xxxxxx3pccdd_firmware_5',
            'sensor.wibeee_3pccdd_mac_address': '_xxxxxx3pccdd_mac_address_5',
            'sensor.wibeee_3pccdd_ip_address': '_xxxxxx3pccdd_ip_address_5',
            'sensor.wibeee_3pccdd_phase_voltage': '_xxxxxx3pccdd_vrms_4',
            'sensor.wibeee_3pccdd_l1_phase_voltage': '_xxxxxx3pccdd_vrms_1',
        }

    def assert_entity_names():
        entities = {id: hass.states.get(id) for id in hass.states.async_entity_ids('sensor')}
        names = {id: entities[id].name for id in entities.keys() if 'restored' not in entities[id].attributes}
        assert names == {
            'sensor.wibeee_1paabb_firmware': 'Wibeee 1PAABB Firmware',
            'sensor.wibeee_1paabb_mac_address': 'Wibeee 1PAABB MAC Address',
            'sensor.wibeee_1paabb_ip_address': 'Wibeee 1PAABB IP Address',
            'sensor.wibeee_1paabb_l1_active_power': 'Wibeee 1PAABB L1 Active Power',
            'sensor.wibeee_1paabb_l1_phase_voltage': 'Wibeee 1PAABB L1 Phase Voltage',

            'sensor.wibeee_3pccdd_firmware': 'Wibeee 3PCCDD Firmware',
            'sensor.wibeee_3pccdd_mac_address': 'Wibeee 3PCCDD MAC Address',
            'sensor.wibeee_3pccdd_ip_address': 'Wibeee 3PCCDD IP Address',
            'sensor.wibeee_3pccdd_phase_voltage': 'Wibeee 3PCCDD Phase Voltage',
            'sensor.wibeee_3pccdd_l1_phase_voltage': 'Wibeee 3PCCDD L1 Phase Voltage',
        }

    def assert_entity_values(expected):
        entities = {id: hass.states.get(id) for id in hass.states.async_entity_ids('sensor')}
        values = {id: entities[id].state for id in entities.keys()}
        assert values == expected

    device_infos = {info.ipAddr: info for info, sensors in devices_data}
    device_values = {i.ipAddr: _build_values(i, sensors) for i, sensors in devices_data}

    mock_async_fetch_device_info.side_effect = lambda self, retries=0: device_infos[self.host]
    mock_async_fetch_values.side_effect = lambda self, device_id, var_names=None, retries=0: device_values[self.host]

    for entry in entries:
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert_via_devices()
    assert_unique_ids()
    assert_entity_names()
    assert_entity_values({
        'sensor.wibeee_1paabb_firmware': '10.9.8',
        'sensor.wibeee_1paabb_mac_address': 'xxxxxx1paabb',
        'sensor.wibeee_1paabb_ip_address': '1.2.3.4',
        'sensor.wibeee_1paabb_l1_active_power': '10000',
        'sensor.wibeee_1paabb_l1_phase_voltage': '230',

        'sensor.wibeee_3pccdd_firmware': '7.6.5',
        'sensor.wibeee_3pccdd_mac_address': 'xxxxxx3pccdd',
        'sensor.wibeee_3pccdd_ip_address': '4.3.2.1',
        'sensor.wibeee_3pccdd_phase_voltage': '1000',
        'sensor.wibeee_3pccdd_l1_phase_voltage': '200',
    })

    assert mock_async_fetch_device_info.call_count == 2
    assert mock_async_fetch_values.call_count == 2

    # unload & setup each config entry again, simulating a restart
    for entry in entries:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # reloading the config entry should not call Wibeee API any further
    assert mock_async_fetch_device_info.call_count == 2
    assert mock_async_fetch_values.call_count == 2

    assert_via_devices()
    assert_unique_ids()
    assert_entity_names()
    assert_entity_values({
        'sensor.wibeee_3pccdd_mac_address': 'unknown',
        'sensor.wibeee_3pccdd_ip_address': 'unknown',
        'sensor.wibeee_3pccdd_firmware': 'unknown',
        'sensor.wibeee_3pccdd_phase_voltage': 'unknown',
        'sensor.wibeee_3pccdd_l1_phase_voltage': 'unknown',
        'sensor.wibeee_1paabb_mac_address': 'unknown',
        'sensor.wibeee_1paabb_ip_address': 'unknown',
        'sensor.wibeee_1paabb_firmware': 'unknown',
        'sensor.wibeee_1paabb_l1_active_power': 'unknown',
        'sensor.wibeee_1paabb_l1_phase_voltage': 'unknown',
    })


@patch.object(WibeeeAPI, 'async_fetch_values', autospec=True)
@patch.object(WibeeeAPI, 'async_fetch_device_info', autospec=True)
async def test_known_sensors(mock_async_fetch_device_info, mock_async_fetch_values, hass: HomeAssistant, caplog):
    from custom_components.wibeee.sensor import KNOWN_SENSORS

    caplog.set_level(logging.WARNING)

    info = DeviceInfo('Wibeee 1Ph', '001100110011', '10.9.8', 'WBM', '1.2.3.4')
    mock_async_fetch_device_info.return_value = info
    values = _build_values(info, {f'{s.poll_var_prefix}{s.slots[0].value}': '123' for s in KNOWN_SENSORS})
    mock_async_fetch_values.return_value = values

    entry = MockConfigEntry(domain='wibeee', data={'host': '1.2.3.4'})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    warnings = [(logger, msg) for logger, _, msg in caplog.record_tuples if logger != 'homeassistant.loader' and 'wibeee' in msg]
    assert len(warnings) is 0


async def test_device_configuration_url(hass: HomeAssistant):
    dev = DeviceInfo('ozymandias', 'abcdabcdabcd', '100.1', 'WBB', '1.2.3.4')
    sensor_type = [s for s in KNOWN_SENSORS if s.unique_name == 'IP_Address'][0]
    slot_num = SlotNum[sensor_type.slots[0].name]
    sensor = [WibeeeSensor(dev.macAddr, wibeee.sensor._make_device_info(dev, slot_num, None), slot_num, sensor_type, None)][0]

    entry = MockConfigEntry(domain='wibeee', data=dict(host=dev.ipAddr, mac_addr=dev.macAddr, wibeee_id=dev.id), version=4)
    entry.add_to_hass(hass)
    device_registry.async_get(hass).async_get_or_create(**dict(config_entry_id=entry.entry_id, **sensor.device_info))

    await hass.config_entries.async_setup(entry.entry_id)
    on_data_pushed = await wibeee.sensor.setup_update_devices_local_push(hass, entry, [sensor])
    await hass.async_block_till_done()

    def assert_configuration_url(url: str):
        devices = async_devices_for_config_entry(hass, entry)
        configuration_url = devices[0].configuration_url if devices else None
        assert configuration_url == url

    assert_configuration_url('http://1.2.3.4/')

    on_data_pushed({sensor.nest_push_param: '4.3.2.1'})
    on_data_pushed(dict(foo='bar'))
    await hass.async_block_till_done()

    assert_configuration_url('http://4.3.2.1/')


def async_devices_for_config_entry(hass: HomeAssistant, entry: ConfigEntry):
    return device_registry.async_entries_for_config_entry(device_registry.async_get(hass), config_entry_id=entry.entry_id)


def async_entities_for_config_entry(hass: HomeAssistant, entry: ConfigEntry):
    return entity_registry.async_entries_for_config_entry(er.async_get(hass), config_entry_id=entry.entry_id)
