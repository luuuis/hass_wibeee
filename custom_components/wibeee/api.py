import asyncio
import logging
from datetime import timedelta
from urllib.parse import quote_plus

import aiohttp
import xmltodict

_LOGGER = logging.getLogger(__name__)


class WibeeeAPI(object):
    """Gets the latest data from Wibeee device."""

    def __init__(self, session: aiohttp.ClientSession, host: str, timeout: timedelta):
        """Initialize the data object."""
        self.session = session
        self.host = host
        self.timeout = timeout
        self.min_wait = timedelta(milliseconds=100)
        self.max_wait = min(timedelta(seconds=5), timeout)
        _LOGGER.info("Initializing WibeeeAPI with host: %s, timeout %s, max_wait: %s", host, self.timeout, self.max_wait)

    async def async_fetch_status(self, retries: int = 0):
        """Fetches the status XML from Wibeee as a dict, optionally retries"""
        status = await self.async_fetch_url(f'http://{self.host}/en/status.xml', retries)
        return status["response"]

    async def async_fetch_device_info(self, retries: int):
        # <devices><id>WIBEEE</id></devices>
        devices = await self.async_fetch_url(f'http://{self.host}/services/user/devices.xml', retries)
        device_id = devices['devices']['id']

        var_names = ['macAddr', 'softVersion', 'model', 'ipAddr']
        var_ids = [f"{quote_plus(device_id)}.{name}" for name in var_names]
        values = await self.async_fetch_url(f'http://{self.host}/services/user/values.xml?var={"&".join(var_ids)}', retries)

        # <values><variable><id>macAddr</id><value>11:11:11:11:11:11</value></variable></values>
        device_vars = {var['id']: var['value'] for var in values['values']['variable']}

        return {
            **device_vars,
            'macAddr': device_vars['macAddr'].replace(':', ''),
            'id': device_id,
        } if len(device_vars) == len(var_names) else None

    async def async_fetch_url(self, url, retries: int = 0):
        async def fetch_with_retries(try_n):
            if try_n > 0:
                wait = min(pow(2, try_n) * self.min_wait.total_seconds(), self.max_wait.total_seconds())
                _LOGGER.debug("Waiting %0.3fs to retry %s...", wait, url)
                await asyncio.sleep(wait)

            try:
                resp = await self.session.get(url, timeout=self.timeout.total_seconds())
                if resp.status != 200:
                    raise aiohttp.ClientResponseError(
                        resp.request_info,
                        resp.history,
                        status=resp.status,
                        message=resp.reason,
                        headers=resp.headers,
                    )

                xml_data = await resp.text()
                _LOGGER.debug("RAW Response from %s: %s)", url, xml_data)
                xml_as_dict = xmltodict.parse(xml_data)
                return xml_as_dict

            except Exception as exc:
                if try_n == retries:
                    retry_info = f' after {try_n} retries' if retries > 0 else ''
                    _LOGGER.error('Error getting %s%s: %s: %s', url, retry_info, exc.__class__.__name__, exc, exc_info=True)
                    return {}
                else:
                    _LOGGER.warning('Error getting %s, will retry. %s: %s', url, exc.__class__.__name__, exc, exc_info=True)
                    return await fetch_with_retries(try_n + 1)

        return await fetch_with_retries(0)
