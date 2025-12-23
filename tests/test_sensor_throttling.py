from datetime import timedelta
from unittest.mock import patch

from freezegun import freeze_time
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wibeee.api import WibeeeAPI
from custom_components.wibeee.sensor import DeviceInfo
from .test_helpers import build_values


async def setup_wibeee_sensors(hass: HomeAssistant, throttle_seconds: int = None) -> tuple[DeviceInfo, MockConfigEntry]:
    """Setup Wibeee sensors for testing with optional throttle configuration."""
    dev = DeviceInfo('test_device', 'aabbccddeeff', '100.1', 'WBM', '1.2.3.4')

    options = {}
    if throttle_seconds is not None:
        options['throttle_sensors'] = throttle_seconds

    entry = MockConfigEntry(
        domain='wibeee',
        data=dict(host=dev.ipAddr, mac_address=dev.macAddr, wibeee_id=dev.id),
        options=options,
        version=5
    )
    entry.add_to_hass(hass)

    return dev, entry


@patch.object(WibeeeAPI, 'async_fetch_values', autospec=True)
@patch.object(WibeeeAPI, 'async_fetch_device_info', autospec=True)
async def test_sensor_throttling_enabled(mock_async_fetch_device_info, mock_async_fetch_values, hass: HomeAssistant):
    """Test that sensor updates are throttled when throttle is configured."""
    # Setup test device and entry
    dev, entry = await setup_wibeee_sensors(hass, throttle_seconds=2)

    with freeze_time("2025-01-01 12:00:00") as frozen_time:
        mock_async_fetch_device_info.return_value = dev
        mock_async_fetch_values.return_value = build_values(dev, {'vrms1': '230'})

        # Setup sensors
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Verify initial sensor state
        voltage_state = hass.states.get('sensor.test_device_ddeeff_l1_phase_voltage')
        assert voltage_state.state == '230'

        # Push first update - should go through immediately
        voltage_sensor = hass.data['sensor'].get_entity('sensor.test_device_ddeeff_l1_phase_voltage')
        voltage_sensor.update_value('235')
        await hass.async_block_till_done()

        voltage_state = hass.states.get('sensor.test_device_ddeeff_l1_phase_voltage')
        assert voltage_state.state == '235'

        # Push second update immediately - should be throttled (blocked)
        voltage_sensor.update_value('240')
        await hass.async_block_till_done()

        voltage_state = hass.states.get('sensor.test_device_ddeeff_l1_phase_voltage')
        assert voltage_state.state == '235'  # Should still be old value

        # Advance time by 1 second - still within throttle window
        frozen_time.tick(timedelta(seconds=1))
        voltage_sensor.update_value('245')
        await hass.async_block_till_done()

        voltage_state = hass.states.get('sensor.test_device_ddeeff_l1_phase_voltage')
        assert voltage_state.state == '235'  # Should still be old value

        # Advance time past throttle window (2+ seconds from first update)
        frozen_time.tick(timedelta(seconds=1.1))  # Total: 2.1 seconds
        voltage_sensor.update_value('250')
        await hass.async_block_till_done()

        voltage_state = hass.states.get('sensor.test_device_ddeeff_l1_phase_voltage')
        assert voltage_state.state == '250'  # Should now update


@patch.object(WibeeeAPI, 'async_fetch_values', autospec=True)
@patch.object(WibeeeAPI, 'async_fetch_device_info', autospec=True)
async def test_sensor_throttling_disabled(mock_async_fetch_device_info, mock_async_fetch_values, hass: HomeAssistant):
    """Test that sensor updates are not throttled when throttle is set to 0."""

    # Setup test device and entry with throttling disabled
    dev, entry = await setup_wibeee_sensors(hass, throttle_seconds=0)
    mock_async_fetch_device_info.return_value = dev
    mock_async_fetch_values.return_value = build_values(dev, {'vrms1': '230'})

    # Setup sensors
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Verify initial sensor state
    voltage_state = hass.states.get('sensor.test_device_ddeeff_l1_phase_voltage')
    assert voltage_state.state == '230'

    # Push first update - should go through
    voltage_sensor = hass.data['sensor'].get_entity('sensor.test_device_ddeeff_l1_phase_voltage')
    voltage_sensor.update_value('235')
    await hass.async_block_till_done()

    voltage_state = hass.states.get('sensor.test_device_ddeeff_l1_phase_voltage')
    assert voltage_state.state == '235'

    # Push second update immediately - should NOT be throttled (goes through)
    voltage_sensor.update_value('240')
    await hass.async_block_till_done()

    voltage_state = hass.states.get('sensor.test_device_ddeeff_l1_phase_voltage')
    assert voltage_state.state == '240'  # Should update immediately

    # Push third update immediately - should also go through
    voltage_sensor.update_value('245')
    await hass.async_block_till_done()

    voltage_state = hass.states.get('sensor.test_device_ddeeff_l1_phase_voltage')
    assert voltage_state.state == '245'  # Should update immediately


@patch.object(WibeeeAPI, 'async_fetch_values', autospec=True)
@patch.object(WibeeeAPI, 'async_fetch_device_info', autospec=True)
async def test_sensor_throttling_default(mock_async_fetch_device_info, mock_async_fetch_values, hass: HomeAssistant):
    """Test that sensor updates use default throttle when not configured."""

    with freeze_time("2025-01-01 12:00:00") as frozen_time:
        # Setup test device and entry with default throttling (no options set)
        dev, entry = await setup_wibeee_sensors(hass)  # No throttle_seconds = uses default
        mock_async_fetch_device_info.return_value = dev
        mock_async_fetch_values.return_value = build_values(dev, {'vrms1': '230'})

        # Setup sensors
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Verify initial sensor state
        voltage_state = hass.states.get('sensor.test_device_ddeeff_l1_phase_voltage')
        assert voltage_state.state == '230'

        # Push first update
        voltage_sensor = hass.data['sensor'].get_entity('sensor.test_device_ddeeff_l1_phase_voltage')
        voltage_sensor.update_value('235')
        await hass.async_block_till_done()

        voltage_state = hass.states.get('sensor.test_device_ddeeff_l1_phase_voltage')
        assert voltage_state.state == '235'

        # Push second update immediately - should be throttled
        voltage_sensor.update_value('240')
        await hass.async_block_till_done()

        voltage_state = hass.states.get('sensor.test_device_ddeeff_l1_phase_voltage')
        assert voltage_state.state == '235'  # Should still be old value (throttled)

        # Advance time past default throttle window (5+ seconds)
        frozen_time.tick(timedelta(seconds=5.1))
        voltage_sensor.update_value('250')
        await hass.async_block_till_done()

        voltage_state = hass.states.get('sensor.test_device_ddeeff_l1_phase_voltage')
        assert voltage_state.state == '250'  # Should now update
