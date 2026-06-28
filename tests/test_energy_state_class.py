"""Tests for energy sensor state class behavior.

Energy sensors use TOTAL (not TOTAL_INCREASING) because Wibeee captures net
energy flows that can be positive or negative.
"""
from datetime import timedelta
from unittest.mock import patch

import pytest
from freezegun import freeze_time
from homeassistant.components.sensor import SensorStateClass
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wibeee.api import WibeeeAPI
from custom_components.wibeee.sensor import (
    DeviceInfo,
    SensorType,
    SensorDeviceClass,
    ENERGY_VOLT_AMPERE_REACTIVE_HOUR,
    _is_zero_value,
)
from .test_helpers import build_values


# --- Unit tests ---

def test_energy_sensor_state_class_is_total():
    """Energy sensors must use TOTAL, not TOTAL_INCREASING, to allow negative values."""
    energy_type = SensorType('eac', 'e', 'Active Energy', 'Wh', SensorDeviceClass.ENERGY)
    assert energy_type.state_class == SensorStateClass.TOTAL


def test_reactive_energy_sensor_state_class_is_total():
    """Reactive energy sensors (varh) also use TOTAL state class."""
    reactive_type = SensorType('ereactl', 'o', 'Inductive Reactive Energy', ENERGY_VOLT_AMPERE_REACTIVE_HOUR, ENERGY_VOLT_AMPERE_REACTIVE_HOUR)
    assert reactive_type.state_class == SensorStateClass.TOTAL


def test_non_energy_sensor_state_class_is_not_total():
    """Non-energy sensors use MEASUREMENT state class, not TOTAL."""
    power_type = SensorType('pac', 'a', 'Active Power', 'W', SensorDeviceClass.POWER)
    assert power_type.state_class == SensorStateClass.MEASUREMENT


@pytest.mark.parametrize("value,expected", [
    ('0', True),
    ('0.0', True),
    (0, True),
    (0.0, True),
    ('1', False),
    ('-1', False),
    ('0.1', False),
    (None, False),
    ('unavailable', False),
    ('unknown', False),
])
def test_is_zero_value(value, expected):
    assert _is_zero_value(value) == expected


# --- Integration tests ---

async def _setup_energy_sensor(hass: HomeAssistant, throttle_seconds: int = 0):
    """Set up a Wibeee device with an energy sensor for testing."""
    dev = DeviceInfo('test_device', 'aabbccddeeff', '100.1', 'WBM', '1.2.3.4')
    entry = MockConfigEntry(
        domain='wibeee',
        data=dict(host=dev.ipAddr, mac_address=dev.macAddr, wibeee_id=dev.id),
        options={'throttle_sensors': throttle_seconds},
        version=5
    )
    entry.add_to_hass(hass)
    return dev, entry


@patch.object(WibeeeAPI, 'async_fetch_values', autospec=True)
@patch.object(WibeeeAPI, 'async_fetch_device_info', autospec=True)
async def test_energy_sensor_state_class_in_ha(mock_fetch_device_info, mock_fetch_values, hass: HomeAssistant):
    """Energy sensor entity must report state_class=total in Home Assistant."""
    dev, entry = await _setup_energy_sensor(hass)
    mock_fetch_device_info.return_value = dev
    mock_fetch_values.return_value = build_values(dev, {'eac1': '1000'})

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get('sensor.test_device_ddeeff_l1_active_energy')
    assert state is not None
    assert state.attributes.get('state_class') == 'total'


@patch.object(WibeeeAPI, 'async_fetch_values', autospec=True)
@patch.object(WibeeeAPI, 'async_fetch_device_info', autospec=True)
async def test_energy_sensor_accepts_negative_values(mock_fetch_device_info, mock_fetch_values, hass: HomeAssistant):
    """Energy sensor must accept negative values without triggering last_reset."""
    dev, entry = await _setup_energy_sensor(hass)
    mock_fetch_device_info.return_value = dev
    mock_fetch_values.return_value = build_values(dev, {'eac1': '1000'})

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    energy_sensor = hass.data['sensor'].get_entity('sensor.test_device_ddeeff_l1_active_energy')
    energy_sensor.update_value('-27825')
    await hass.async_block_till_done()

    state = hass.states.get('sensor.test_device_ddeeff_l1_active_energy')
    assert state.state == '-27825'
    assert state.attributes.get('last_reset') is None


@patch.object(WibeeeAPI, 'async_fetch_values', autospec=True)
@patch.object(WibeeeAPI, 'async_fetch_device_info', autospec=True)
async def test_energy_sensor_zero_triggers_last_reset(mock_fetch_device_info, mock_fetch_values, hass: HomeAssistant):
    """When energy sensor transitions from non-zero to zero, last_reset must be set."""
    dev, entry = await _setup_energy_sensor(hass)
    mock_fetch_device_info.return_value = dev
    mock_fetch_values.return_value = build_values(dev, {'eac1': '1000'})

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    energy_sensor = hass.data['sensor'].get_entity('sensor.test_device_ddeeff_l1_active_energy')

    with freeze_time("2025-06-28 10:00:00"):
        energy_sensor.update_value('0')
        await hass.async_block_till_done()

    state = hass.states.get('sensor.test_device_ddeeff_l1_active_energy')
    assert state.state == '0'
    assert state.attributes.get('last_reset') is not None


@patch.object(WibeeeAPI, 'async_fetch_values', autospec=True)
@patch.object(WibeeeAPI, 'async_fetch_device_info', autospec=True)
async def test_energy_sensor_zero_bypasses_throttle(mock_fetch_device_info, mock_fetch_values, hass: HomeAssistant):
    """A zero value on an energy sensor bypasses throttle to immediately capture the reset."""
    dev, entry = await _setup_energy_sensor(hass, throttle_seconds=60)
    mock_fetch_device_info.return_value = dev
    mock_fetch_values.return_value = build_values(dev, {'eac1': '1000'})

    with freeze_time("2025-06-28 10:00:00") as frozen_time:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        energy_sensor = hass.data['sensor'].get_entity('sensor.test_device_ddeeff_l1_active_energy')

        # First update to consume the throttle window
        energy_sensor.update_value('1100')
        await hass.async_block_till_done()
        assert hass.states.get('sensor.test_device_ddeeff_l1_active_energy').state == '1100'

        # Immediately after, a normal update is throttled
        energy_sensor.update_value('1200')
        await hass.async_block_till_done()
        assert hass.states.get('sensor.test_device_ddeeff_l1_active_energy').state == '1100'

        # But a zero value (reset event) bypasses the throttle
        energy_sensor.update_value('0')
        await hass.async_block_till_done()
        assert hass.states.get('sensor.test_device_ddeeff_l1_active_energy').state == '0'
