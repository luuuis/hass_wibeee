import logging
from typing import Callable, Dict, Tuple, NamedTuple, Awaitable
from urllib.parse import parse_qsl

from homeassistant.components.network import async_get_source_ip
from homeassistant.components.network.const import PUBLIC_TARGET_IP
from homeassistant.core import callback
from homeassistant.helpers import singleton
from homeassistant.helpers.typing import EventType

from .const import NEST_NULL_UPSTREAM

LOGGER = logging.getLogger(__name__)

import aiohttp
from aiohttp import web
from aiohttp.web_routedef import _HandlerType

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.core import HomeAssistant
from homeassistant.const import EVENT_HOMEASSISTANT_STOP


class DeviceConfig(NamedTuple):
    handle_push_data: Callable[[Dict], None]
    """Callback that will receive push data."""
    upstream: str
    """The upstream server to forward data to"""


class NestProxy(object):
    _listeners: Dict[str, DeviceConfig] = {}

    def register_device(self, mac_address: str, push_data_listener: Callable[[Dict], None], upstream: str):
        self._listeners[mac_address] = DeviceConfig(
            handle_push_data=push_data_listener,
            upstream=upstream
        )

    def unregister_device(self, mac_address: str):
        self._listeners.pop(mac_address)

    def get_device_info(self, mac_addr: str) -> DeviceConfig:
        return self._listeners.get(mac_addr, None)


@singleton.singleton("wibeee_nest_proxy")
async def get_nest_proxy(
        hass: HomeAssistant,
        local_port=8600,
) -> NestProxy:
    session = async_get_clientsession(hass)
    nest_proxy = NestProxy()

    def nest_forward(decode_data: Callable[[web.Request], Awaitable[Tuple[str, Dict]]]) -> _HandlerType:
        async def handler(req: web.Request) -> web.StreamResponse:
            mac_addr, push_data = await decode_data(req)
            device_info = nest_proxy.get_device_info(mac_addr)

            if device_info is None:
                LOGGER.debug("Ignoring pushed data from %s: %s", mac_addr, push_data)
                return web.Response(status=403)

            device_info.handle_push_data(push_data)

            if device_info.upstream == NEST_NULL_UPSTREAM:
                # don't send to any upstream.
                return web.Response(status=200)

            url = f'{device_info.upstream}{req.path_qs}'
            req_body = (await req.read()) if req.can_read_body else None

            res = await session.request(req.method, url, data=req_body, **req.headers)
            res_body = await res.read()

            return web.Response(headers=res.headers, body=res_body)

        return handler

    app = aiohttp.web.Application()
    app.add_routes([
        web.get('/Wibeee/receiverAvg', nest_forward(extract_query_params)),
        web.get('/Wibeee/receiverLeap', nest_forward(extract_query_params)),
        web.post('/Wibeee/receiverAvgPost', nest_forward(extract_json_body)),
        web.post('/Wibeee/receiverJSON', nest_forward(extract_json_body)),
        web.route('*', '/{anypath:.*}', unknown_path_handler),
    ])

    # don't listen on public IP
    local_ip = await async_get_source_ip(hass, target_ip=PUBLIC_TARGET_IP)

    # access log only if DEBUG level is enabled
    access_log = logging.getLogger(f'{__name__}.access')
    access_log.setLevel(access_log.getEffectiveLevel() + 10)

    server = hass.loop.create_task(web._run_app(app, host=local_ip, port=local_port, access_log=access_log))
    LOGGER.info('Wibeee Nest proxy listening on http://%s:%d', local_ip, local_port)

    @callback
    def shutdown_proxy(ev: EventType) -> None:
        LOGGER.info('Wibeee Nest proxy shutting down')
        server.cancel()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shutdown_proxy)
    return nest_proxy


async def extract_query_params(req: web.Request) -> Tuple[str, Dict]:
    """Extracts Wibeee data from query params."""
    query = {k: v for k, v in parse_qsl(req.query_string)}
    return query['mac'], query


async def extract_json_body(req: web.Request) -> Tuple[str, Dict]:
    """Extracts Wibeee data from JSON request body."""
    body = await req.json()
    return body.get('mac', None), body


async def unknown_path_handler(req: web.Request) -> web.StreamResponse:
    LOGGER.debug("Ignoring unexpected %s %s", req.method, req.path)
    return web.Response(status=200)
