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
async def test_device_registry(spy_async_add_entities, mock_async_fetch_device_info, mock_async_fetch_values, hass: HomeAssistant):
    devices_data = [
        [
            DeviceInfo('Wibeee 1Ph', '00:11:00:11:00:11', '10.9.8', 'WBM', '1.2.3.4'),
            {'vrms1': '230'},
        ], [
            DeviceInfo('Wibeee 3Ph', '11:00:11:00:11:00', '7.6.5', 'WBT', '4.3.2.1'),
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
        'Wibeee 001100': None,
        'Wibeee 001100 Line 1': device_ids['Wibeee 001100'],
        'Wibeee 110011 Line 1': None,
    }

    # ensure via_device is correct, HA will start to fail if not.
    added_sensors: list[WibeeeSensor] = [e for call_args in spy_async_add_entities.call_args_list for e in call_args.args[1]]
    assert {s.name: s._attr_device_info['via_device'] for s in added_sensors} == {
        'Wibeee 3Ph Phase Voltage L4': None,
        'Wibeee 3Ph Phase Voltage L1': ('wibeee', '11:00:11:00:11:00'),
        'Wibeee 1Ph Phase Voltage L1': None,
    }
