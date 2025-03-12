import logging
from datetime import timedelta

import aiohttp
from aioresponses import aioresponses
from pytest_homeassistant_custom_component.common import load_fixture

from custom_components.wibeee import api

DEVICE_INFO = api.DeviceInfo(id='X', macAddr='111111111111', softVersion='4.4.124', model='WB3', ipAddr='10.10.10.100')
TIMEOUT = timedelta(seconds=5)


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
                body=load_fixture('test_api_values.xml'),
            )

            wibeee = api.WibeeeAPI(session, '1.2.3.4', timeout=TIMEOUT)
            device_info = await wibeee.async_fetch_device_info()
            assert device_info == DEVICE_INFO


async def test_fetch_values(caplog):
    caplog.set_level(logging.DEBUG)
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(
                "http://1.2.3.4/services/user/values.xml?id=WIBEEE",
                status=200,
                body=load_fixture('test_api_values.xml'),
            )

            wibeee = api.WibeeeAPI(session, '1.2.3.4', timeout=TIMEOUT)
            values = await wibeee.async_fetch_values("WIBEEE")

            assert values.items() >= ({
                'macAddr': '11:11:11:11:11:11',
                'softVersion': '4.4.124',
                'model': 'WB3',
                'ipAddr': '10.10.10.100',
                'ssid': '**REDACTED**',
                'securKey': '**REDACTED**',
                'vrms2': '235.06',
            }).items()

            secrets = {
                'securKey': 'MY_WIFI_PASS',
                'ssid': 'MY_SSID',
            }
            for k, v in secrets.items():
                assert k in caplog.text
                assert v not in caplog.text
