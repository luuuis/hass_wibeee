from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from wibeee.const import NEST_NULL_UPSTREAM
from wibeee.nest import create_application, DeviceConfig


@pytest_asyncio.fixture
async def nest_fixture(aiohttp_client):
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


@pytest.mark.asyncio
@pytest.mark.parametrize("method, path, param", [
    ("get", "receiver", "params"),
    ("get", "receiverAvg", "params"),
    ("get", "receiverLeap", "params"),
    ("post", "receiverAvgPost", "json"),
    ("post", "receiverJSON", "json"),
])
async def test_null_upstream(nest_fixture, method, path, param):
    handle_push_data, client = nest_fixture

    res = await getattr(client, method)(f'/Wibeee/{path}', **({param: PUSH_DATA}))
    assert res.status == 202

    handle_push_data.assert_called_with(PUSH_DATA)
