import asyncio
import logging
from datetime import timedelta
from typing import NamedTuple, Optional, Dict
from urllib.parse import quote_plus

import aiohttp
import xmltodict
from homeassistant.components.diagnostics import async_redact_data
from homeassistant.helpers.typing import StateType

from .util import scrub_values_xml

_LOGGER = logging.getLogger(__name__)

StatusResponse = dict[str, StateType]

_VALUES_SCRUB_KEYS = ['securKey', 'ssid']
"""Values that we'll attempt to scrub from the values.xml response."""


class DeviceInfo(NamedTuple):
    id: str
    "Device ID (default is 'WIBEEE')"
    macAddr: str
    "MAC address (formatted for use in HA)"
    softVersion: str
    "Firmware version"
    model: str
    "Wibeee Model (single or 3-phase, etc)"
    ipAddr: str
    "IP address"


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

    async def async_fetch_values(self, device_id: str, var_names: list[str] = None, retries: int = 0) -> Dict[str, any]:
        """Fetches the values from Wibeee as a dict, optionally retries"""
        if var_names:
            var_ids = [f"{quote_plus(device_id)}.{quote_plus(var)}" for var in var_names]
            query = f'var={"&".join(var_ids)}'
        else:
            query = f'id={quote_plus(device_id)}'

        values = await self.async_fetch_url(f'http://{self.host}/services/user/values.xml?{query}', retries, scrub_keys=_VALUES_SCRUB_KEYS)

        # <values><variable><id>macAddr</id><value>11:11:11:11:11:11</value></variable></values>
        values_vars = {var['id']: var['value'] for var in values['values']['variable']}

        # attempt to scrub WiFi secrets before they make it into logs, etc.
        return async_redact_data(values_vars, _VALUES_SCRUB_KEYS)

    async def async_fetch_device_info(self, retries: int = 0) -> Optional[DeviceInfo]:
        # <devices><id>WIBEEE</id></devices>
        devices = await self.async_fetch_url(f'http://{self.host}/services/user/devices.xml', retries)
        device_id = devices['devices']['id']

        var_names = ['macAddr', 'softVersion', 'model', 'ipAddr']
        device_vars = await self.async_fetch_values(device_id, var_names, retries)

        return DeviceInfo(
            device_id,
            device_vars['macAddr'].replace(':', ''),
            device_vars['softVersion'],
            device_vars['model'],
            device_vars['ipAddr'],
        ) if set(var_names) <= set(device_vars.keys()) else None

    async def async_fetch_url(self, url: str, retries: int = 0, scrub_keys: list[str] = []):
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
                if _LOGGER.isEnabledFor(logging.DEBUG):
                    _LOGGER.debug("RAW Response from %s: %s)", url, scrub_values_xml(scrub_keys, await resp.read()))

                xml_as_dict = xmltodict.parse(xml_data)
                return xml_as_dict

            except Exception as exc:
                if try_n == retries:
                    retry_info = f' after {try_n} retries' if retries > 0 else ''
                    _LOGGER.error('Error getting %s%s: %s: %s', url, retry_info, exc.__class__.__name__, exc)
                    return {}
                else:
                    _LOGGER.debug('Error getting %s, will retry. %s: %s', url, exc.__class__.__name__, exc)
                    return await fetch_with_retries(try_n + 1)

        return await fetch_with_retries(0)
