"""Tests for energy sensor state class behavior.

Energy sensors use TOTAL (not TOTAL_INCREASING) because Wibeee captures net
energy flows that can be positive or negative.
"""
from datetime import timedelta
from unittest.mock import patch

import pytest
from freezegun import freeze_time
from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wibeee.api import WibeeeAPI
from custom_components.wibeee.sensor import (
    DeviceInfo,
    SensorType,
    SensorDeviceClass,
    ENERGY_VOLT_AMPERE_REACTIVE_HOUR,
    _is_zero_value,
    _is_counter_reset,
    update_sensors,
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


@pytest.mark.parametrize("prev,value,elapsed,expected", [
    pytest.param('439534', '718', timedelta(minutes=1), True, id='reset between pushes'),
    pytest.param('-467114', '-3', timedelta(minutes=1), True, id='signed counter reset'),
    pytest.param('5000', '1000', timedelta(hours=1), False, id='drop below max power'),
    pytest.param('-50', '2', timedelta(minutes=1), False, id='signed counter crossing zero'),
    pytest.param('1000', '100000', timedelta(minutes=1), False, id='increase above max power'),
    pytest.param('5000', '0', timedelta(hours=1), True, id='zero'),
    pytest.param('0', '0', timedelta(minutes=1), False, id='zero to zero'),
    pytest.param(None, '718', timedelta(minutes=1), False, id='no previous value'),
    pytest.param(STATE_UNAVAILABLE, '718', timedelta(minutes=1), False, id='previous unavailable'),
    pytest.param('439534', STATE_UNAVAILABLE, timedelta(minutes=1), False, id='unavailable'),
])
def test_is_counter_reset(prev, value, elapsed, expected):
    assert _is_counter_reset(prev, value, elapsed) == expected


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


@patch.object(WibeeeAPI, 'async_fetch_values', autospec=True)
@patch.object(WibeeeAPI, 'async_fetch_device_info', autospec=True)
async def test_energy_sensor_reset_between_pushes(mock_fetch_device_info, mock_fetch_values, hass: HomeAssistant):
    """A counter reset that is not observed as a zero is detected against the last received value, bypassing the throttle."""
    dev, entry = await _setup_energy_sensor(hass, throttle_seconds=60)
    mock_fetch_device_info.return_value = dev
    mock_fetch_values.return_value = build_values(dev, {'eac1': '1000'})

    with freeze_time("2025-06-28 10:00:00") as frozen_time:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        energy_sensor = hass.data['sensor'].get_entity('sensor.test_device_ddeeff_l1_active_energy')
        energy_sensor.update_value('1010')
        frozen_time.tick(timedelta(seconds=55))
        energy_sensor.update_value('439534')
        frozen_time.tick(timedelta(seconds=5))
        energy_sensor.update_value('718')
        await hass.async_block_till_done()

    state = hass.states.get('sensor.test_device_ddeeff_l1_active_energy')
    assert state.state == '718'
    assert state.attributes.get('last_reset') == '2025-06-28T10:01:00+00:00'


@pytest.mark.parametrize("elapsed,expect_reset", [
    (timedelta(seconds=30), True),
    (timedelta(hours=1), False),
])
@patch.object(WibeeeAPI, 'async_fetch_values', autospec=True)
@patch.object(WibeeeAPI, 'async_fetch_device_info', autospec=True)
async def test_energy_sensor_reset_threshold_scales_with_elapsed_time(mock_fetch_device_info, mock_fetch_values,
                                                                     hass: HomeAssistant, elapsed, expect_reset):
    """The same drop is a reset after a short gap but a plausible change after a long one."""
    dev, entry = await _setup_energy_sensor(hass)
    mock_fetch_device_info.return_value = dev
    mock_fetch_values.return_value = build_values(dev, {'eac1': '-5000'})

    with freeze_time("2025-06-28 10:00:00") as frozen_time:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        energy_sensor = hass.data['sensor'].get_entity('sensor.test_device_ddeeff_l1_active_energy')
        energy_sensor.update_value('-4990')
        frozen_time.tick(elapsed)
        energy_sensor.update_value('-1000')
        await hass.async_block_till_done()

    state = hass.states.get('sensor.test_device_ddeeff_l1_active_energy')
    assert state.state == '-1000'
    assert (state.attributes.get('last_reset') is not None) == expect_reset


@patch.object(WibeeeAPI, 'async_fetch_values', autospec=True)
@patch.object(WibeeeAPI, 'async_fetch_device_info', autospec=True)
async def test_energy_sensor_signed_counter_crossing_zero(mock_fetch_device_info, mock_fetch_values, hass: HomeAssistant):
    """A net energy counter crossing zero is not a reset."""
    dev, entry = await _setup_energy_sensor(hass)
    mock_fetch_device_info.return_value = dev
    mock_fetch_values.return_value = build_values(dev, {'eac1': '-50'})

    with freeze_time("2025-06-28 10:00:00") as frozen_time:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        energy_sensor = hass.data['sensor'].get_entity('sensor.test_device_ddeeff_l1_active_energy')
        energy_sensor.update_value('-20')
        frozen_time.tick(timedelta(minutes=1))
        energy_sensor.update_value('2')
        await hass.async_block_till_done()

    state = hass.states.get('sensor.test_device_ddeeff_l1_active_energy')
    assert state.state == '2'
    assert state.attributes.get('last_reset') is None


@patch.object(WibeeeAPI, 'async_fetch_values', autospec=True)
@patch.object(WibeeeAPI, 'async_fetch_device_info', autospec=True)
async def test_energy_sensor_counter_step_between_frequent_pushes(mock_fetch_device_info, mock_fetch_values, hass: HomeAssistant):
    """A counter that only steps once a minute is not reset when the step arrives seconds after the previous push."""
    dev, entry = await _setup_energy_sensor(hass)
    mock_fetch_device_info.return_value = dev
    mock_fetch_values.return_value = build_values(dev, {'eac1': '-5000'})

    with freeze_time("2025-06-28 10:00:00") as frozen_time:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        energy_sensor = hass.data['sensor'].get_entity('sensor.test_device_ddeeff_l1_active_energy')
        frozen_time.tick(timedelta(seconds=55))
        energy_sensor.update_value('-5000')
        frozen_time.tick(timedelta(seconds=5))
        energy_sensor.update_value('-4850')
        await hass.async_block_till_done()

    state = hass.states.get('sensor.test_device_ddeeff_l1_active_energy')
    assert state.state == '-4850'
    assert state.attributes.get('last_reset') is None


@patch.object(WibeeeAPI, 'async_fetch_values', autospec=True)
@patch.object(WibeeeAPI, 'async_fetch_device_info', autospec=True)
async def test_energy_sensor_reset_after_idle_period(mock_fetch_device_info, mock_fetch_values, hass: HomeAssistant):
    """A counter that has not changed for hours is still reset by a small non-zero value."""
    dev, entry = await _setup_energy_sensor(hass)
    mock_fetch_device_info.return_value = dev
    mock_fetch_values.return_value = build_values(dev, {'eac1': '439534'})

    with freeze_time("2025-06-28 10:00:00") as frozen_time:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        energy_sensor = hass.data['sensor'].get_entity('sensor.test_device_ddeeff_l1_active_energy')
        frozen_time.tick(timedelta(hours=10))
        energy_sensor.update_value('439534')
        frozen_time.tick(timedelta(seconds=30))
        energy_sensor.update_value('3')
        await hass.async_block_till_done()

    state = hass.states.get('sensor.test_device_ddeeff_l1_active_energy')
    assert state.state == '3'
    assert state.attributes.get('last_reset') is not None


@pytest.mark.parametrize("interruption,first_value_is_reset", [('unavailable', True), ('restart', False)])
@patch.object(WibeeeAPI, 'async_fetch_values', autospec=True)
@patch.object(WibeeeAPI, 'async_fetch_device_info', autospec=True)
async def test_energy_sensor_reset_after_interruption(mock_fetch_device_info, mock_fetch_values, hass: HomeAssistant,
                                                      interruption, first_value_is_reset):
    """The first value after being unavailable is compared with the last value before it, but not after a restart."""
    dev, entry = await _setup_energy_sensor(hass)
    mock_fetch_device_info.return_value = dev
    mock_fetch_values.return_value = build_values(dev, {'eac1': '-100000'})

    with freeze_time("2025-06-28 10:00:00") as frozen_time:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        energy_sensor = hass.data['sensor'].get_entity('sensor.test_device_ddeeff_l1_active_energy')
        if interruption == 'unavailable':
            energy_sensor.update_value(STATE_UNAVAILABLE)
        else:
            await hass.config_entries.async_unload(entry.entry_id)
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()
            energy_sensor = hass.data['sensor'].get_entity('sensor.test_device_ddeeff_l1_active_energy')

        frozen_time.tick(timedelta(minutes=1))
        energy_sensor.update_value('-5000')
        await hass.async_block_till_done()
        assert (hass.states.get('sensor.test_device_ddeeff_l1_active_energy').attributes.get('last_reset') is not None) == first_value_is_reset

        frozen_time.tick(timedelta(minutes=1))
        energy_sensor.update_value('-3')
        await hass.async_block_till_done()

    state = hass.states.get('sensor.test_device_ddeeff_l1_active_energy')
    assert state.state == '-3'
    assert state.attributes.get('last_reset') == '2025-06-28T10:02:00+00:00'


@patch.object(WibeeeAPI, 'async_fetch_values', autospec=True)
@patch.object(WibeeeAPI, 'async_fetch_device_info', autospec=True)
async def test_energy_sensor_reset_is_per_sensor(mock_fetch_device_info, mock_fetch_values, hass: HomeAssistant):
    """Each sensor on a device detects resets using its own previous value."""
    dev, entry = await _setup_energy_sensor(hass)
    mock_fetch_device_info.return_value = dev
    mock_fetch_values.return_value = build_values(dev, {'eac1': '100000', 'eac2': '50'})

    with freeze_time("2025-06-28 10:00:00") as frozen_time:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        sensors = [hass.data['sensor'].get_entity(f'sensor.test_device_ddeeff_l{n}_active_energy') for n in (1, 2)]
        update_sensors(sensors, 'Nest push', lambda s: s.nest_push_param, {'e1': '100010', 'e2': '60'})
        frozen_time.tick(timedelta(minutes=1))
        update_sensors(sensors, 'Nest push', lambda s: s.nest_push_param, {'e1': '5', 'e2': '40'})
        await hass.async_block_till_done()

    l1_state = hass.states.get('sensor.test_device_ddeeff_l1_active_energy')
    l2_state = hass.states.get('sensor.test_device_ddeeff_l2_active_energy')
    assert (l1_state.state, l2_state.state) == ('5', '40')
    assert l1_state.attributes.get('last_reset') is not None
    assert l2_state.attributes.get('last_reset') is None
