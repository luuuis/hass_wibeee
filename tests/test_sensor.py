import logging
from typing import Dict
from unittest.mock import patch, MagicMock

import homeassistant.helpers.entity_registry as er
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry
from homeassistant.helpers.entity_platform import EntityPlatform
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wibeee.api import WibeeeAPI
from custom_components.wibeee.sensor import DeviceInfo


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

    def assert_via_devices():
        # ensure via_device is correct, HA will start to fail if not.
        registry = device_registry.async_get(hass)
        registry_devices = [re for e in entries for re in device_registry.async_entries_for_config_entry(registry, e.entry_id)]
        via_devices = {re.name: re.via_device_id for re in registry_devices}
        device_ids = {re.name: re.id for re in registry_devices}

        assert via_devices == {
            'Wibeee 3PCCDD': None,
            'Wibeee 3PCCDD L1': device_ids.get('Wibeee 3PCCDD', 'missing id for device'),
            'Wibeee 1PAABB L1': None,
        }

    def assert_entity_names():
        entities = {id: hass.states.get(id) for id in hass.states.async_entity_ids('sensor')}
        names = {id: entities[id].name for id in entities.keys() if 'restored' not in entities[id].attributes}
        assert names == {
            'sensor.wibeee_3pccdd_phase_voltage': 'Wibeee 3PCCDD Phase Voltage',
            'sensor.wibeee_3pccdd_l1_phase_voltage': 'Wibeee 3PCCDD L1 Phase Voltage',
            'sensor.wibeee_1paabb_l1_active_power': 'Wibeee 1PAABB L1 Active Power',
            'sensor.wibeee_1paabb_l1_phase_voltage': 'Wibeee 1PAABB L1 Phase Voltage',
        }

    def assert_entity_values(expected):
        entities = {id: hass.states.get(id) for id in hass.states.async_entity_ids('sensor')}
        values = {id: entities[id].state for id in entities.keys()}
        assert values == expected

    entries = [MockConfigEntry(domain='wibeee', version=3, data={'host': info.ipAddr, 'mac_address': info.macAddr, 'wibeee_id': info.id})
               for info, sensors in devices_data]
    device_infos = {info.ipAddr: info for info, sensors in devices_data}
    device_values = {i.ipAddr: _build_values(i, sensors) for i, sensors in devices_data}

    mock_async_fetch_device_info.side_effect = lambda self, retries=0: device_infos[self.host]
    mock_async_fetch_values.side_effect = lambda self, device_id, var_names=None, retries=0: device_values[self.host]

    for entry in entries:
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert_via_devices()
    assert_entity_names()
    assert_entity_values({
        'sensor.wibeee_3pccdd_phase_voltage': '1000',
        'sensor.wibeee_3pccdd_l1_phase_voltage': '200',
        'sensor.wibeee_1paabb_l1_active_power': '10000',
        'sensor.wibeee_1paabb_l1_phase_voltage': '230',
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
    assert_entity_names()
    assert_entity_values({
        'sensor.wibeee_3pccdd_phase_voltage': 'unknown',
        'sensor.wibeee_3pccdd_l1_phase_voltage': 'unknown',
        'sensor.wibeee_1paabb_l1_active_power': 'unknown',
        'sensor.wibeee_1paabb_l1_phase_voltage': 'unknown',
    })


@patch.object(WibeeeAPI, 'async_fetch_device_info', autospec=True)
async def test_migrate_entry_1_to_3(mock_async_fetch_device_info, hass: HomeAssistant):
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
    assert configured_entry.options == {'scan_interval': 0.0, 'nest_upstream': 'proxy_null'}
    assert configured_entry.version == 3


@patch.object(er, 'async_entries_for_config_entry', autospec=True)
async def test_migrate_entry_2_to_3_offline(mock_async_entries_for_config_entry, hass: HomeAssistant):
    entry = MockConfigEntry(domain='wibeee', data={'host': '127.0.0.2'}, options={'scan_interval': 30, 'nest_upstream': 'proxy_disabled'}, version=2)
    mock_async_entries_for_config_entry.side_effect = lambda _, entry_id: [] if entry_id != entry.entry_id else [
        # self._attr_unique_id = f"_{mac_addr}_{sensor_type.unique_name.lower()}_{sensor_phase}"
        # self._attr_name = f"{device_name} {sensor_type.friendly_name} L{sensor_phase}"
        MagicMock(spec=er.RegistryEntry, has_entity_name=False, unique_id='_abcdabcdabcd_apparent_power_1', original_name='Downstairs Apparent Power L1'),
        MagicMock(spec=er.RegistryEntry, has_entity_name=False, unique_id='_abcdabcdabcd_active_energy_1', original_name='Downstairs Active Energy L1'),
        MagicMock(spec=er.RegistryEntry, has_entity_name=False, unique_id='_abcdabcdabcd_vrms_1', original_name='Downstairs Phase Voltage L1'),
    ]

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    configured_entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert configured_entry.data == {
        'host': '127.0.0.2',  # to set up polling or refresh available sensors
        'mac_address': 'abcdabcdabcd',  # to set up local push
        'wibeee_id': 'Downstairs',  # Wibeee id, needed for values.xml API
    }
    assert configured_entry.options == {'scan_interval': 0.0, 'nest_upstream': 'proxy_null'}
    assert configured_entry.version == 3


@patch.object(WibeeeAPI, 'async_fetch_values', autospec=True)
@patch.object(WibeeeAPI, 'async_fetch_device_info', autospec=True)
async def test_known_sensors(mock_async_fetch_device_info, mock_async_fetch_values, hass: HomeAssistant, caplog):
    from custom_components.wibeee.sensor import KNOWN_SENSORS

    caplog.set_level(logging.WARNING)

    info = DeviceInfo('Wibeee 1Ph', '001100110011', '10.9.8', 'WBM', '1.2.3.4')
    mock_async_fetch_device_info.return_value = info
    values = _build_values(info, {f'{s.poll_var_prefix}1': '123' for s in KNOWN_SENSORS.values()})
    mock_async_fetch_values.return_value = values

    entry = MockConfigEntry(domain='wibeee', data={'host': '1.2.3.4'})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    warnings = [msg for logger, _, msg in caplog.record_tuples if logger == 'homeassistant.components.sensor' and 'wibeee' in msg]
    assert len(warnings) is 0
