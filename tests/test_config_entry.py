from typing import Dict
from unittest.mock import patch, MagicMock

import homeassistant.helpers.entity_registry as er
from homeassistant.core import HomeAssistant
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


@patch.object(WibeeeAPI, 'async_fetch_device_info', autospec=True)
@patch.object(er, 'async_entries_for_config_entry', autospec=True)
async def test_migrate_entry_2_to_3(mock_async_entries_for_config_entry, mock_async_fetch_device_info, hass: HomeAssistant):
    info = DeviceInfo('Upstairs', 'abcdabcdabcd', '10.9.8', 'WBM', '127.0.0.2')
    mock_async_fetch_device_info.return_value = info

    entry = MockConfigEntry(domain='wibeee', data={'host': '127.0.0.2'}, options={'scan_interval': 30, 'nest_upstream': 'proxy_disabled'},
                            version=2)
    mock_async_entries_for_config_entry.side_effect = lambda _, entry_id: [] if entry_id != entry.entry_id else [
        MagicMock(spec=er.RegistryEntry, has_entity_name=True, unique_id='_abcdabcdabcd_apparent_power_1'),
        MagicMock(spec=er.RegistryEntry, has_entity_name=True, unique_id='_abcdabcdabcd_active_energy_1'),
        MagicMock(spec=er.RegistryEntry, has_entity_name=True, unique_id='_abcdabcdabcd_vrms_1'),
    ]

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    configured_entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert configured_entry.data == {
        'host': '127.0.0.2',  # to set up polling or refresh available sensors
        'mac_address': 'abcdabcdabcd',  # to set up local push
        'wibeee_id': 'Upstairs',  # Wibeee id, needed for values.xml API
    }
    assert configured_entry.options == {'scan_interval': 0.0, 'nest_upstream': 'proxy_null'}
    assert configured_entry.version == 3


@patch.object(er, 'async_entries_for_config_entry', autospec=True)
async def test_migrate_entry_2_to_3_offline(mock_async_entries_for_config_entry, hass: HomeAssistant):
    entry = MockConfigEntry(domain='wibeee', data={'host': '127.0.0.2'}, options={'scan_interval': 30, 'nest_upstream': 'proxy_disabled'},
                            version=2)
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
