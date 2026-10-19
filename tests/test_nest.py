import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from homeassistant.const import EVENT_HOMEASSISTANT_STOP

from custom_components.wibeee.const import NEST_NULL_UPSTREAM
from custom_components.wibeee.nest import create_application, get_nest_proxy, DeviceConfig


@pytest_asyncio.fixture
async def nest_fixture(aiohttp_client, socket_enabled):
    handle_push_data = MagicMock()
    device_config = DeviceConfig(handle_push_data, NEST_NULL_UPSTREAM)
    app = create_application(lambda _: device_config)
    client = await aiohttp_client(app)

    return [handle_push_data, client]


PUSH_DATA = {'mac': '001122334455', 'ip': '127.0.0.1', 'soft': '3.3.614', 'model': 'WBM', 'time': '1740333343', 'v1': '242.75',
             'v2': '0.00', 'v3': '0.00', 'vt': '0.00', 'i1': '3.59', 'i2': '0.00', 'i3': '0.00', 'it': '0.00', 'p1': '871', 'p2': '0',
             'p3': '0', 'pt': '0', 'a1': '610', 'a2': '0', 'a3': '0', 'at': '0', 'r1': '-615', 'r2': '0', 'r3': '0', 'rt': '0',
             'q1': '49.93', 'q2': '0.00', 'q3': '0.00', 'qt': '0.00', 'f1': '0.700', 'f2': '0.000', 'f3': '0.000', 'ft': '0.000',
             'e1': '6439820', 'e2': '0', 'e3': '0', 'et': '0', 'o1': '0', 'o2': '0', 'o3': '0', 'ot': '0'}


@pytest.mark.parametrize("method, path, param, response", [
    ("get", "receiver", "params", ""),
    ("get", "receiverAvg", "params", "<<<WBAVG "),
    ("get", "receiverLeap", "params", "<<<WGRADIENT=007 "),
    ("post", "receiverAvgPost", "json", "<<<WBAVG "),
])
async def test_null_upstream(nest_fixture, method, path, param, response):
    handle_push_data, client = nest_fixture

    res = await getattr(client, method)(f'/Wibeee/{path}', **({param: PUSH_DATA}))
    assert res.status == 200
    assert await res.text() == response

    handle_push_data.assert_called_with(PUSH_DATA)


async def test_null_upstream_json(nest_fixture):
    handle_push_data, client = nest_fixture

    res = await client.post(f'/Wibeee/receiverJSON', json=PUSH_DATA)
    assert res.status == 200

    response: str = await res.text()
    start = "<<<WBJSON "
    assert response.startswith(start)
    response_timestamp = response[len(start):]
    assert float(response_timestamp) == pytest.approx(time.time(), abs=5)
    handle_push_data.assert_called_with(PUSH_DATA)


async def test_proxy_retries_until_listening(hass, caplog):
    """The proxy keeps retrying when there is no LAN address yet or binding fails, e.g. while booting."""
    started = asyncio.Event()
    binds = []
    sleeps = []
    real_sleep = asyncio.sleep

    class FlakyTCPSite:
        def __init__(self, runner, host, port):
            binds.append((host, port))

        async def start(self):
            if len(binds) == 1:
                raise OSError(99, 'Cannot assign requested address')
            started.set()

    async def fake_sleep(delay, *args, **kwargs):
        if delay:
            sleeps.append(delay)
        await real_sleep(0)

    source_ips = AsyncMock(side_effect=['127.0.0.1', '192.168.1.10', '192.168.1.10'])
    with (
        patch('custom_components.wibeee.nest.async_get_source_ip', source_ips),
        patch('custom_components.wibeee.nest.web.TCPSite', FlakyTCPSite),
        patch('asyncio.sleep', fake_sleep),
    ):
        await get_nest_proxy(hass)
        await asyncio.wait_for(started.wait(), timeout=5)

    assert binds == [('192.168.1.10', 8600), ('192.168.1.10', 8600)]
    assert sleeps == [5, 10]
    assert 'Wibeee Nest proxy listening on http://192.168.1.10:8600' in caplog.text

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()


async def test_proxy_starts_on_first_try(hass, caplog):
    """The proxy starts immediately when a LAN address is available, with no retries."""
    started = asyncio.Event()
    sleeps = []
    real_sleep = asyncio.sleep

    class ReadyTCPSite:
        def __init__(self, runner, host, port):
            pass

        async def start(self):
            started.set()

    async def fake_sleep(delay, *args, **kwargs):
        if delay:
            sleeps.append(delay)
        await real_sleep(0)

    source_ip = AsyncMock(return_value='192.168.1.10')
    with (
        patch('custom_components.wibeee.nest.async_get_source_ip', source_ip),
        patch('custom_components.wibeee.nest.web.TCPSite', ReadyTCPSite),
        patch('asyncio.sleep', fake_sleep),
    ):
        await get_nest_proxy(hass)
        await asyncio.wait_for(started.wait(), timeout=5)

    assert sleeps == []
    assert 'Wibeee Nest proxy listening on http://192.168.1.10:8600' in caplog.text

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()


async def test_proxy_backoff_capped_at_60s(hass):
    """Retry delay doubles each time but is capped at 60s."""
    started = asyncio.Event()
    attempts = []
    sleeps = []
    real_sleep = asyncio.sleep

    class FailFiveThenSucceedTCPSite:
        def __init__(self, runner, host, port):
            attempts.append((host, port))

        async def start(self):
            if len(attempts) <= 5:
                raise OSError(99, 'Cannot assign requested address')
            started.set()

    async def fake_sleep(delay, *args, **kwargs):
        if delay:
            sleeps.append(delay)
        await real_sleep(0)

    source_ip = AsyncMock(return_value='192.168.1.10')
    with (
        patch('custom_components.wibeee.nest.async_get_source_ip', source_ip),
        patch('custom_components.wibeee.nest.web.TCPSite', FailFiveThenSucceedTCPSite),
        patch('asyncio.sleep', fake_sleep),
    ):
        await get_nest_proxy(hass)
        await asyncio.wait_for(started.wait(), timeout=5)

    # delay doubles each retry (5→10→20→40→60) and is capped at 60s
    assert sleeps == [5, 10, 20, 40, 60]

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()


async def test_proxy_runner_cleaned_up_on_shutdown(hass):
    """The AppRunner is cleaned up when HA stops."""
    started = asyncio.Event()
    mock_runner = AsyncMock()

    class ReadyTCPSite:
        def __init__(self, runner, host, port):
            pass

        async def start(self):
            started.set()

    source_ip = AsyncMock(return_value='192.168.1.10')
    with (
        patch('custom_components.wibeee.nest.async_get_source_ip', source_ip),
        patch('custom_components.wibeee.nest.web.AppRunner', return_value=mock_runner),
        patch('custom_components.wibeee.nest.web.TCPSite', ReadyTCPSite),
    ):
        await get_nest_proxy(hass)
        await asyncio.wait_for(started.wait(), timeout=5)

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()

    mock_runner.cleanup.assert_awaited_once()
