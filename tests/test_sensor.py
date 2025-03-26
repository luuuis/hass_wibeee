import logging
from typing import Dict
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry
from homeassistant.helpers.entity_platform import EntityPlatform
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wibeee.api import WibeeeAPI
from custom_components.wibeee.sensor import DeviceInfo, WibeeeSensor


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
            {'vrms1': '230'},
        ], [
            DeviceInfo('Wibeee', 'xxxxxx3pccdd', '7.6.5', 'WBT', '4.3.2.1'),
            {'vrms1': '200', 'vrmst': '1000'},
        ],
    ]

    entries = [MockConfigEntry(domain='wibeee', data={'host': info.ipAddr}, version=2) for info, sensors in devices_data]
    device_infos = {info.ipAddr: info for info, sensors in devices_data}
    device_values = {i.ipAddr: _build_values(i, sensors) for i, sensors in devices_data}

    mock_async_fetch_device_info.side_effect = lambda self, retries=0: device_infos[self.host]
    mock_async_fetch_values.side_effect = lambda self, device_id, var_names=None, retries=0: device_values[self.host]

    for entry in entries:
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = device_registry.async_get(hass)
    registry_devices = [re for e in entries for re in device_registry.async_entries_for_config_entry(registry, e.entry_id)]
    via_devices = {re.name: re.via_device_id for re in registry_devices}
    device_ids = {re.name: re.id for re in registry_devices}

    assert via_devices == {
        'Wibeee 3PCCDD': None,
        'Wibeee 3PCCDD L1': device_ids['Wibeee 3PCCDD'],
        'Wibeee 1PAABB L1': None,
    }

    # ensure via_device is correct, HA will start to fail if not.
    added_sensors: list[WibeeeSensor] = [e for call_args in spy_async_add_entities.call_args_list for e in call_args.args[1]]
    assert {s.entity_id: s._attr_device_info['via_device'] for s in added_sensors} == {
        'sensor.wibeee_3pccdd_phase_voltage': None,
        'sensor.wibeee_3pccdd_l1_phase_voltage': ('wibeee', 'xxxxxx3pccdd'),
        'sensor.wibeee_1paabb_l1_phase_voltage': None,
    }

    entities = {id: hass.states.get(id) for id in hass.states.async_entity_ids('sensor')}

    names = {id: entities[id].name for id in entities.keys()}
    assert names == {
        'sensor.wibeee_3pccdd_phase_voltage': 'Wibeee 3PCCDD Phase Voltage',
        'sensor.wibeee_3pccdd_l1_phase_voltage': 'Wibeee 3PCCDD L1 Phase Voltage',
        'sensor.wibeee_1paabb_l1_phase_voltage': 'Wibeee 1PAABB L1 Phase Voltage',
    }

    values = {id: entities[id].state for id in entities.keys()}
    assert values == {
        'sensor.wibeee_3pccdd_phase_voltage': '1000',
        'sensor.wibeee_3pccdd_l1_phase_voltage': '200',
        'sensor.wibeee_1paabb_l1_phase_voltage': '230',
    }


@patch.object(WibeeeAPI, 'async_fetch_values', autospec=True)
@patch.object(WibeeeAPI, 'async_fetch_device_info', autospec=True)
async def test_migrate_entry(mock_async_fetch_device_info, mock_async_fetch_values, hass: HomeAssistant):
    entry = MockConfigEntry(domain='wibeee', data={'host': '127.0.0.2'}, version=1)
    info = DeviceInfo('ozymandias', 'abcdabcdabcd', '4.5.6', 'WBB', '127.0.0.2')
    mock_async_fetch_device_info.return_value = info

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    configured_entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert configured_entry.data == {
        'host': '127.0.0.2',  # to set up polling or refresh available sensors
        'mac_address': 'abcdabcdabcd',  # to set up local push
        'wibeee_id': 'ozymandias',  # Wibeee id, needed for values.xml API
    }
    assert configured_entry.version == 3


@patch.object(WibeeeAPI, 'async_fetch_values', autospec=True)
@patch.object(WibeeeAPI, 'async_fetch_device_info', autospec=True)
async def test_known_sensors(mock_async_fetch_device_info, mock_async_fetch_values, hass: HomeAssistant, caplog):
    from custom_components.wibeee.sensor import KNOWN_SENSORS

    caplog.set_level(logging.WARNING)

    info = DeviceInfo('Wibeee 1Ph', '001100110011', '10.9.8', 'WBM', '1.2.3.4')
    mock_async_fetch_device_info.return_value = info
    values = _build_values(info, {f'{s.poll_var_prefix}1': '123' for s in KNOWN_SENSORS})
    mock_async_fetch_values.return_value = values

    entry = MockConfigEntry(domain='wibeee', data={'host': '1.2.3.4'})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    warnings = [msg for logger, _, msg in caplog.record_tuples if logger == 'homeassistant.components.sensor' and 'wibeee' in msg]
    assert len(warnings) is 0
