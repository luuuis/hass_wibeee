import json
import logging
from typing import Callable, Dict, Tuple, NamedTuple, Awaitable, Optional
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
    nest_proxy = NestProxy()

    # disable persistent HTTP connections as the Wibeee Cloud will otherwise
    # time out our connections, causing a ServerDisconnectedError below.
    connector = aiohttp.TCPConnector(force_close=True)
    session = aiohttp.ClientSession(connector=connector)

    @callback
    def close_session(ev: EventType) -> None:
        session.detach()
        connector.close()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, close_session)

    def nest_forward(decode_data: Callable[[web.Request], Awaitable[Tuple[str, Dict]]]) -> _HandlerType:
        async def handler(req: web.Request) -> web.StreamResponse:
            mac_addr, push_data, forward_body = await decode_data(req)
            device_info = nest_proxy.get_device_info(mac_addr)

            if device_info is None:
                LOGGER.debug("Ignoring unexpected push data from %s received as %s %s: %s", mac_addr, req.method, req.path, push_data)
                return web.Response(status=404)  # Not Found

            LOGGER.debug("Updating sensors using push data from %s received as %s %s: %s", mac_addr, req.method, req.path, push_data)
            device_info.handle_push_data(push_data)

            if device_info.upstream == NEST_NULL_UPSTREAM:
                # don't send to any upstream.
                LOGGER.debug("Accepted local-only push data from %s in %s %s: %s", mac_addr, req.method, req.path, push_data)
                return web.Response(status=202)  # Accepted

            url = f'{device_info.upstream}{req.path_qs}'
            try:
                LOGGER.debug("Forwarding push data from %s using %s %s: %s", mac_addr, req.method, url, push_data)
                res = await session.request(req.method, url, data=forward_body)
                res_body = await res.read()
                if res.status < 200 or res.status > 299:
                    LOGGER.warning('Wibeee Cloud returned %d for forwarded request: %s', res.status, res_body)

                return web.Response(status=res.status, headers=res.headers, body=res_body)

            except aiohttp.ClientError as e:
                LOGGER.error('Wibeee Cloud HTTP error during %d %s', req.method, req.path, exc_info=e)
                return web.Response(status=500)  # Server Error

        return handler

    app = aiohttp.web.Application()
    app.add_routes([
        web.get('/Wibeee/receiver', nest_forward(extract_query_params)),
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


async def extract_query_params(req: web.Request) -> Tuple[str, Dict, Optional[str]]:
    """Extracts Wibeee data from query params."""
    query = {k: v for k, v in parse_qsl(req.query_string)}
    return query['mac'], query, await req.text() if req.can_read_body else None


async def extract_json_body(req: web.Request) -> Tuple[Optional[str], Dict, str]:
    """Extracts Wibeee data from JSON request body."""
    body = await req.text() if req.can_read_body else None
    LOGGER.debug("Parsing JSON in %s %s", req.method, req.path, body)
    parsed_body = None
    parse_error = None
    try:
        parsed_body = {} if body is None else json.loads(body)

    except json.decoder.JSONDecodeError as e:
        # Wibeee will send invalid JSON at times. make a desperate attempt to fix the JSON and try again. (╯°□°）╯︵ ┻━┻
        fixed_body = body.replace(',,', ',').replace('""', '","')
        if fixed_body != body:
            try:
                parsed_body = json.loads(fixed_body)
                LOGGER.debug("Fixed invalid JSON in %s %s [%s]: %s", req.method, req.path, e, body)
            except json.decoder.JSONDecodeError:
                parse_error = e
        else:
            parse_error = e

    if parse_error:
        LOGGER.debug("Error parsing JSON in %s %s: %s", req.method, req.path, body, exc_info=parse_error)
        return None, {}, body

    return parsed_body.get('mac', None), parsed_body, json.dumps(parsed_body)


async def unknown_path_handler(req: web.Request) -> web.StreamResponse:
    LOGGER.debug("Ignoring unexpected %s %s", req.method, req.path)
    return web.Response(status=200)
