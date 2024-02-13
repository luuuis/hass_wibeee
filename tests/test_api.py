import os
from datetime import timedelta

import aiohttp
import pytest
from aioresponses import aioresponses

from wibeee import api

_THIS_DIR = os.path.dirname(os.path.realpath(__file__))


def read_file(filename: str) -> str:
    with open(os.path.join(_THIS_DIR, filename), encoding="utf-8") as file:
        return file.read()


DEVICE_INFO = api.DeviceInfo(id='X', macAddr='111111111111', softVersion='4.4.124', model='WB3', ipAddr='10.10.10.100', use_values2=False)


@pytest.mark.asyncio
async def test_fetch_device_info():
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(
                "http://1.2.3.4/services/user/devices.xml",
                status=200,
                body='<devices><id>X</id></devices>',
            )

            m.get(
                "http://1.2.3.4/services/user/values.xml?var=X.macAddr&X.softVersion&X.model&X.ipAddr",
                status=200,
                body=read_file('test_api_values.xml'),
            )

            wibeee = api.WibeeeAPI(session, '1.2.3.4', timeout=timedelta(seconds=5))
            device_info = await wibeee.async_fetch_device_info()
            assert device_info == DEVICE_INFO
